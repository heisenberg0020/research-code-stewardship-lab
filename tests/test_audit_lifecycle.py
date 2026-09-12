"""Lifecycle tests for the public, filesystem-local audit core."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import stewardship_lab.audit as audit_core

from stewardship_lab.audit import (
    PENDING_COMMIT_NAME,
    _is_within,
    AuditError,
    add_evidence,
    add_finding,
    bind_audit,
    build_report_data,
    inspect_clean_project,
    list_findings,
    preflight,
    recover_audit,
    rebaseline,
    render_report_markdown,
    set_g0_gate,
    transition_finding,
    verify_audit_workspace,
)


PUBLIC_FILES = (
    "research-contract-template.md",
    "evidence-passport-template.md",
    "triage-card-template.md",
    "delegation-contract-template.md",
)

CONTRACT_HEADINGS = (
    "G0 Research Contract",
    "Identity and decision",
    "Research mandate",
    "Success, failure, and stopping",
    "Sources, rights, and legitimacy",
    "Human authority and delegation",
    "Assumptions and unknowns",
    "Human gate decision",
)


class AuditLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self._git(self.project, "init")
        self._commit("README.md", "# Fixture project\n", "initial project")

        self.workspace = self.root / "public-audit-workspace"
        self._make_workspace(self.workspace)
        bind_audit(
            self.project,
            self.workspace,
            actor="Audit Owner",
            rationale="Bind a clean fixture project for lifecycle testing.",
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _git(self, project: Path, *arguments: str) -> str:
        result = subprocess.run(
            ("git", "-C", str(project), *arguments),
            capture_output=True,
            check=False,
            text=True,
        )
        if result.returncode:
            self.fail(result.stderr.strip() or result.stdout.strip())
        return result.stdout.strip()

    def _commit(self, relative_path: str, contents: str, message: str) -> None:
        path = self.project / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")
        self._git(self.project, "add", relative_path)
        self._git(
            self.project,
            "-c",
            "user.name=Lifecycle Test",
            "-c",
            "user.email=lifecycle@example.invalid",
            "commit",
            "-m",
            message,
        )

    def _make_workspace(self, workspace: Path) -> None:
        workspace.mkdir()
        metadata = {
            "schema_version": 1,
            "workspace_type": "rcsl-public-audit-workspace",
            "validator_scope": "structural_only",
        }
        (workspace / "audit-workspace.json").write_text(
            json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
        )
        for filename in PUBLIC_FILES:
            content = "# Public audit template\n\n{{fill_this_in}}\n"
            if filename == "research-contract-template.md":
                sections = "\n\n".join(
                    f"## {heading}\n\n{{{{complete_this_section}}}}"
                    for heading in CONTRACT_HEADINGS[1:]
                )
                content = f"# {CONTRACT_HEADINGS[0]}\n\n{sections}\n"
            (workspace / filename).write_text(content, encoding="utf-8")

    def _complete_contract(self) -> None:
        sections = []
        for heading in CONTRACT_HEADINGS[1:]:
            if heading == "Assumptions and unknowns":
                body = (
                    "| Item | Evidence | Consequence | Owner |\n"
                    "| --- | --- | --- | --- |\n"
                    "| Fixture assumption | Local fixture | Bounded | Test owner |"
                )
            else:
                body = "- Recorded fixture value: bounded and reviewed for this lifecycle test."
            sections.append(f"## {heading}\n\n{body}")
        content = "\n\n".join(sections)
        (self.workspace / "research-contract-template.md").write_text(
            f"# {CONTRACT_HEADINGS[0]}\n\n{content}\n", encoding="utf-8"
        )

    def _approve(self) -> None:
        self._complete_contract()
        set_g0_gate(
            self.workspace,
            "approve",
            reviewer="Named Reviewer",
            rationale="The completed public contract is ready for this bounded review.",
            actor="Named Reviewer",
        )

    def _new_finding(self, finding_id: str = "F-001") -> dict[str, object]:
        self._approve()
        return add_finding(
            self.workspace,
            finding_id=finding_id,
            title="Fixture lifecycle finding",
            layer="L1",
            competency="C1",
            severity="medium",
            claim="The fixture exposes a bounded, reproducible lifecycle condition.",
            first_broken_contract="The declared review contract has not yet been satisfied.",
            actor="Auditor",
        )

    def _advance_to_mitigated(self, finding_id: str = "F-001") -> None:
        for status in ("triaged", "accepted", "mitigated"):
            transition_finding(
                self.workspace,
                finding_id,
                status,
                actor="Auditor",
                rationale=f"Move fixture finding to {status}.",
            )

    def test_dirty_project_refuses_a_new_bind(self) -> None:
        (self.project / "uncommitted.txt").write_text("dirty\n", encoding="utf-8")
        second_workspace = self.root / "second-public-workspace"
        self._make_workspace(second_workspace)

        with self.assertRaisesRegex(AuditError, "clean"):
            bind_audit(
                self.project,
                second_workspace,
                actor="Auditor",
                rationale="This should be refused for a dirty project.",
            )

    def test_git_inspection_disables_configured_fsmonitor_hook(self) -> None:
        marker = self.root / "fsmonitor-was-called"
        hook = self.root / "fsmonitor-hook"
        hook.write_text(
            "#!/bin/sh\n"
            f"touch '{marker}'\n"
            "printf '0\\n'\n",
            encoding="utf-8",
        )
        hook.chmod(0o700)
        self._git(self.project, "config", "core.fsmonitor", str(hook))

        snapshot = inspect_clean_project(self.project)

        self.assertEqual(snapshot["project_root"], str(self.project.resolve()))
        self.assertFalse(marker.exists())

    def test_workspace_inside_project_refuses_a_new_bind(self) -> None:
        inner_workspace = self.project / "public-workspace-inside-project"
        self._make_workspace(inner_workspace)
        self._git(self.project, "add", str(inner_workspace.relative_to(self.project)))
        self._git(
            self.project,
            "-c",
            "user.name=Lifecycle Test",
            "-c",
            "user.email=lifecycle@example.invalid",
            "commit",
            "-m",
            "add inner public workspace",
        )

        with self.assertRaisesRegex(AuditError, "outside"):
            bind_audit(
                self.project,
                inner_workspace,
                actor="Auditor",
                rationale="An in-project workspace is unsafe for a bound audit.",
            )

    def test_containment_is_conservative_for_case_variants(self) -> None:
        case_variant = self.project.with_name(self.project.name.swapcase()) / "audit"
        self.assertTrue(_is_within(case_variant, self.project))

    def test_placeholders_block_g0_approval_then_approved_preflight_succeeds(self) -> None:
        with self.assertRaisesRegex(AuditError, "placeholders"):
            set_g0_gate(
                self.workspace,
                "approve",
                reviewer="Named Reviewer",
                rationale="Attempt approval before completing the contract.",
                actor="Named Reviewer",
            )

        self._approve()
        result = preflight(self.workspace)
        self.assertTrue(result["ok"])
        self.assertEqual(result["g0_gate"]["status"], "approved")

    def test_empty_contract_sections_and_unapproved_finding_are_refused(self) -> None:
        heading_only = "\n\n".join(f"## {heading}" for heading in CONTRACT_HEADINGS[1:])
        (self.workspace / "research-contract-template.md").write_text(
            f"# {CONTRACT_HEADINGS[0]}\n\n{heading_only}\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(AuditError, "empty required sections"):
            set_g0_gate(
                self.workspace,
                "approved",
                reviewer="Named Reviewer",
                rationale="Heading-only text must not count as a contract.",
                actor="Named Reviewer",
            )
        with self.assertRaisesRegex(AuditError, "G0 gate"):
            add_finding(
                self.workspace,
                finding_id="F-unapproved",
                title="Must not be attributed before G0",
                layer="L1",
                competency="C1",
                severity="low",
                claim="This should be refused.",
                first_broken_contract="G0 is not approved.",
                actor="Auditor",
            )

    def test_contract_change_after_approval_requires_a_new_decision(self) -> None:
        self._approve()
        contract = self.workspace / "research-contract-template.md"
        contract.write_text(
            contract.read_text(encoding="utf-8") + "\nA material scope change.\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(AuditError, "changed after the recorded decision"):
            preflight(self.workspace)

    def test_head_drift_requires_rebaseline_and_old_findings_are_stale(self) -> None:
        self._new_finding()
        self._approve()
        self._commit("changed.txt", "new committed revision\n", "change bound project")

        with self.assertRaisesRegex(AuditError, "HEAD drift"):
            preflight(self.workspace)

        new_baseline = rebaseline(
            self.workspace,
            actor="Audit Owner",
            reason="The reviewed project revision intentionally changed.",
        )
        self.assertTrue(new_baseline["head"])
        with self.assertRaisesRegex(AuditError, "G0 gate"):
            preflight(self.workspace)

        self._approve()
        self.assertTrue(preflight(self.workspace)["ok"])
        verification = verify_audit_workspace(self.workspace)
        self.assertEqual(verification["stale_finding_count"], 1)
        report = build_report_data(self.workspace)
        self.assertFalse(report["findings"][0]["baseline_current"])
        self.assertEqual(report["findings"][0]["baseline_state"], "stale")

    def test_rebaseline_uses_a_new_id_even_at_the_same_head(self) -> None:
        finding = self._new_finding()
        prior_id = finding["baseline_snapshot"]["id"]
        baseline = rebaseline(
            self.workspace,
            actor="Audit Owner",
            reason="Start a separately reviewed audit epoch at the same commit.",
        )
        self.assertNotEqual(prior_id, baseline["id"])
        self.assertEqual(verify_audit_workspace(self.workspace)["stale_finding_count"], 1)
        self._approve()
        with self.assertRaisesRegex(AuditError, "older baseline"):
            add_evidence(
                self.workspace,
                "F-001",
                evidence_id="E-new-epoch",
                kind="observed",
                reference="fixture.txt",
                summary="New-baseline evidence must not be mixed into an old finding.",
                actor="Auditor",
            )

    def test_finding_evidence_and_legal_transitions_reach_closed(self) -> None:
        finding = self._new_finding()
        self.assertEqual(finding["status"], "open")
        self.assertEqual(list_findings(self.workspace)[0]["id"], "F-001")
        add_evidence(
            self.workspace,
            "F-001",
            evidence_id="E-001",
            kind="observed",
            reference="tests/fixture-output.txt",
            summary="The fixture evidence supports the recorded lifecycle claim.",
            actor="Auditor",
        )
        self._advance_to_mitigated()
        self._approve()
        verified = transition_finding(
            self.workspace,
            "F-001",
            "verified",
            actor="Named Reviewer",
            rationale="Evidence is recorded and the current baseline passed preflight.",
        )
        closed = transition_finding(
            self.workspace,
            "F-001",
            "closed",
            actor="Named Reviewer",
            rationale="The verified finding has been formally closed.",
        )
        self.assertEqual(verified["status"], "verified")
        self.assertEqual(closed["status"], "closed")
        self.assertTrue(verify_audit_workspace(self.workspace)["ok"])

    def test_terminal_transition_requires_evidence_and_clean_approved_preflight(self) -> None:
        self._new_finding()
        self._advance_to_mitigated()

        with self.assertRaisesRegex(AuditError, "evidence"):
            transition_finding(
                self.workspace,
                "F-001",
                "verified",
                actor="Auditor",
                rationale="This is intentionally missing evidence.",
            )

        add_evidence(
            self.workspace,
            "F-001",
            evidence_id="E-001",
            kind="observed",
            reference="tests/fixture-output.txt",
            summary="Record the evidence before attempting a trusted terminal state.",
            actor="Auditor",
        )
        set_g0_gate(
            self.workspace,
            "draft",
            reviewer="Named Reviewer",
            rationale="Return the fixture gate to draft to exercise the terminal guard.",
            actor="Named Reviewer",
        )
        with self.assertRaisesRegex(AuditError, "G0 gate"):
            transition_finding(
                self.workspace,
                "F-001",
                "verified",
                actor="Auditor",
                rationale="The G0 gate is still a draft.",
            )

        self._approve()
        dirty_path = self.project / "working-tree-change.txt"
        dirty_path.write_text("not committed\n", encoding="utf-8")
        with self.assertRaisesRegex(AuditError, "clean"):
            transition_finding(
                self.workspace,
                "F-001",
                "verified",
                actor="Auditor",
                rationale="A dirty project cannot support a trusted terminal state.",
            )
        dirty_path.unlink()
        self.assertEqual(
            transition_finding(
                self.workspace,
                "F-001",
                "verified",
                actor="Auditor",
                rationale="The project is clean and the approved gate now permits verification.",
            )["status"],
            "verified",
        )

    def test_duplicate_and_illegal_transitions_are_rejected(self) -> None:
        self._new_finding()
        with self.assertRaisesRegex(AuditError, "already exists"):
            self._new_finding()
        with self.assertRaisesRegex(AuditError, "illegal finding transition"):
            transition_finding(
                self.workspace,
                "F-001",
                "verified",
                actor="Auditor",
                rationale="Open findings cannot skip directly to verification.",
            )

    def test_snapshot_write_failure_is_explicitly_and_idempotently_recovered(self) -> None:
        self._complete_contract()
        event_path = self.workspace / "audit-events.jsonl"
        event_count = len(event_path.read_text(encoding="utf-8").splitlines())
        original_write = audit_core._atomic_write_text
        failed = False

        def fail_snapshot(path: Path, content: str) -> None:
            nonlocal failed
            if (
                not failed
                and path.name == "audit-workspace.json"
                and (self.workspace / PENDING_COMMIT_NAME).exists()
            ):
                failed = True
                raise AuditError("could not write audit-workspace.json: simulated ENOSPC")
            original_write(path, content)

        with mock.patch.object(audit_core, "_atomic_write_text", side_effect=fail_snapshot):
            with self.assertRaisesRegex(AuditError, "audit recover"):
                set_g0_gate(
                    self.workspace,
                    "approved",
                    reviewer="Named Reviewer",
                    rationale="Recover this interrupted gate decision.",
                    actor="Named Reviewer",
                )

        self.assertTrue((self.workspace / PENDING_COMMIT_NAME).is_file())
        with self.assertRaisesRegex(AuditError, "audit recover"):
            verify_audit_workspace(self.workspace)
        with self.assertRaisesRegex(AuditError, "audit recover"):
            list_findings(self.workspace)

        recovered = recover_audit(self.workspace)
        self.assertEqual(recovered["status"], "recovered")
        self.assertEqual(recovered["verification"]["event_count"], event_count + 1)
        self.assertEqual(recovered["verification"]["g0_gate"]["status"], "approved")
        self.assertFalse((self.workspace / PENDING_COMMIT_NAME).exists())

        clean = recover_audit(self.workspace)
        self.assertEqual(clean["status"], "clean")
        self.assertFalse(clean["recovered"])
        self.assertEqual(clean["verification"]["event_count"], event_count + 1)

    def test_pending_intent_write_failure_leaves_public_state_unchanged(self) -> None:
        metadata_path = self.workspace / "audit-workspace.json"
        event_path = self.workspace / "audit-events.jsonl"
        before = {path: path.read_bytes() for path in (metadata_path, event_path)}
        original_write = audit_core._atomic_write_text

        def fail_pending(path: Path, content: str) -> None:
            if path.name == PENDING_COMMIT_NAME:
                raise AuditError("could not write pending commit: simulated ENOSPC")
            original_write(path, content)

        with mock.patch.object(audit_core, "_atomic_write_text", side_effect=fail_pending):
            with self.assertRaisesRegex(AuditError, "simulated ENOSPC"):
                set_g0_gate(
                    self.workspace,
                    "blocked",
                    reviewer="Named Reviewer",
                    rationale="No public file may change without a durable intent.",
                    actor="Named Reviewer",
                )

        self.assertEqual(before, {path: path.read_bytes() for path in before})
        self.assertFalse((self.workspace / PENDING_COMMIT_NAME).exists())

    def test_event_write_failure_recovers_the_snapshot_without_duplicate_evidence(self) -> None:
        self._new_finding()
        event_path = self.workspace / "audit-events.jsonl"
        event_count = len(event_path.read_text(encoding="utf-8").splitlines())
        original_write = audit_core._atomic_write_text
        failed = False

        def fail_event(path: Path, content: str) -> None:
            nonlocal failed
            if (
                not failed
                and path.name == "audit-events.jsonl"
                and (self.workspace / PENDING_COMMIT_NAME).exists()
            ):
                failed = True
                raise AuditError("could not write audit-events.jsonl: simulated ENOSPC")
            original_write(path, content)

        with mock.patch.object(audit_core, "_atomic_write_text", side_effect=fail_event):
            with self.assertRaisesRegex(AuditError, "audit recover"):
                add_evidence(
                    self.workspace,
                    "F-001",
                    evidence_id="E-recover",
                    kind="observed",
                    reference="fixture.txt",
                    summary="This evidence snapshot was written before the event failed.",
                    actor="Auditor",
                )

        recovered = recover_audit(self.workspace)
        finding = list_findings(self.workspace)[0]
        self.assertEqual(recovered["verification"]["event_count"], event_count + 1)
        self.assertEqual([item["id"] for item in finding["evidence"]], ["E-recover"])

    def test_cleanup_failure_recovers_without_duplicating_the_committed_event(self) -> None:
        event_count = len(
            (self.workspace / "audit-events.jsonl").read_text(encoding="utf-8").splitlines()
        )
        with mock.patch.object(
            audit_core,
            "_delete_pending_commit",
            side_effect=AuditError("simulated cleanup failure"),
        ):
            with self.assertRaisesRegex(AuditError, "audit recover"):
                set_g0_gate(
                    self.workspace,
                    "blocked",
                    reviewer="Named Reviewer",
                    rationale="The committed after-images must be recovered idempotently.",
                    actor="Named Reviewer",
                )

        recovered = recover_audit(self.workspace)
        self.assertEqual(recovered["verification"]["event_count"], event_count + 1)
        self.assertFalse((self.workspace / PENDING_COMMIT_NAME).exists())

    def test_candidate_limits_fail_before_creating_a_pending_commit(self) -> None:
        self._new_finding()
        metadata_path = self.workspace / "audit-workspace.json"
        finding_path = self.workspace / "findings" / "F-001.json"
        event_path = self.workspace / "audit-events.jsonl"
        before = {
            path: path.read_bytes() for path in (metadata_path, finding_path, event_path)
        }
        current_limit = max(
            metadata_path.stat().st_size,
            finding_path.stat().st_size,
            (self.workspace / "research-contract-template.md").stat().st_size,
        ) + 256

        with mock.patch.object(audit_core, "MAX_AUDIT_FILE_BYTES", current_limit):
            with self.assertRaisesRegex(AuditError, "byte limit"):
                add_evidence(
                    self.workspace,
                    "F-001",
                    evidence_id="E-oversize",
                    kind="observed",
                    reference="fixture.txt",
                    summary="x" * (current_limit * 2),
                    actor="Auditor",
                )

        event_bytes = len(event_path.read_bytes())
        with mock.patch.object(audit_core, "MAX_EVENT_LOG_BYTES", event_bytes + 1):
            with self.assertRaisesRegex(AuditError, "event log would exceed"):
                set_g0_gate(
                    self.workspace,
                    "blocked",
                    reviewer="Named Reviewer",
                    rationale="This event cannot fit.",
                    actor="Named Reviewer",
                )

        event_count = len(event_path.read_text(encoding="utf-8").splitlines())
        with mock.patch.object(audit_core, "MAX_EVENTS", event_count):
            with self.assertRaisesRegex(AuditError, "event limit"):
                set_g0_gate(
                    self.workspace,
                    "blocked",
                    reviewer="Named Reviewer",
                    rationale="This event exceeds the count boundary.",
                    actor="Named Reviewer",
                )

        with mock.patch.object(audit_core, "MAX_EVIDENCE_PER_FINDING", 0):
            with self.assertRaisesRegex(AuditError, "evidence limit"):
                add_evidence(
                    self.workspace,
                    "F-001",
                    evidence_id="E-capacity",
                    kind="observed",
                    reference="fixture.txt",
                    summary="No evidence capacity remains.",
                    actor="Auditor",
                )
        with mock.patch.object(audit_core, "MAX_TOTAL_EVIDENCE", 0):
            with self.assertRaisesRegex(AuditError, "aggregate limit"):
                add_evidence(
                    self.workspace,
                    "F-001",
                    evidence_id="E-total-capacity",
                    kind="observed",
                    reference="fixture.txt",
                    summary="No aggregate evidence capacity remains.",
                    actor="Auditor",
                )
        with mock.patch.object(audit_core, "MAX_FINDINGS", 1):
            with self.assertRaisesRegex(AuditError, "finding limit"):
                add_finding(
                    self.workspace,
                    finding_id="F-capacity",
                    title="No finding capacity remains",
                    layer="L1",
                    competency="C1",
                    severity="low",
                    claim="The candidate must be rejected before any write.",
                    first_broken_contract="Finding count limit",
                    actor="Auditor",
                )

        self.assertEqual(before, {path: path.read_bytes() for path in before})
        self.assertFalse((self.workspace / PENDING_COMMIT_NAME).exists())

    def test_inconsistent_prospective_commit_fails_before_writing_intent(self) -> None:
        metadata_path = self.workspace / "audit-workspace.json"
        event_path = self.workspace / "audit-events.jsonl"
        before = {path: path.read_bytes() for path in (metadata_path, event_path)}
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

        with self.assertRaisesRegex(AuditError, "metadata hash does not match"):
            audit_core._commit_lifecycle_change(
                self.workspace,
                snapshot_relative_path="audit-workspace.json",
                snapshot_payload=metadata,
                event_type="g0_gate_set",
                actor="Fault injector",
                event_payload={"metadata_sha256": "0" * 64},
            )

        self.assertEqual(before, {path: path.read_bytes() for path in before})
        self.assertFalse((self.workspace / PENDING_COMMIT_NAME).exists())

    def test_interrupted_bind_recovers_directory_metadata_and_first_event(self) -> None:
        workspace = self.root / "recover-bind-workspace"
        self._make_workspace(workspace)
        with mock.patch.object(
            audit_core,
            "_ensure_empty_findings_directory",
            side_effect=AuditError("simulated directory failure"),
        ):
            with self.assertRaisesRegex(AuditError, "audit recover"):
                bind_audit(
                    self.project,
                    workspace,
                    actor="Audit Owner",
                    rationale="Recover an interrupted initial bind.",
                )

        self.assertTrue((workspace / PENDING_COMMIT_NAME).is_file())
        self.assertFalse((workspace / "findings").exists())
        recovered = recover_audit(workspace)
        self.assertEqual(recovered["verification"]["event_count"], 1)
        self.assertTrue((workspace / "findings").is_dir())
        self.assertTrue(verify_audit_workspace(workspace)["ok"])

    def test_recovery_refuses_to_overwrite_an_unknown_third_state(self) -> None:
        self._complete_contract()
        original_write = audit_core._atomic_write_text

        def fail_snapshot(path: Path, content: str) -> None:
            if (
                path.name == "audit-workspace.json"
                and (self.workspace / PENDING_COMMIT_NAME).exists()
            ):
                raise AuditError("simulated snapshot failure")
            original_write(path, content)

        with mock.patch.object(audit_core, "_atomic_write_text", side_effect=fail_snapshot):
            with self.assertRaises(AuditError):
                set_g0_gate(
                    self.workspace,
                    "approved",
                    reviewer="Named Reviewer",
                    rationale="Create a recoverable intent.",
                    actor="Named Reviewer",
                )

        metadata_path = self.workspace / "audit-workspace.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["unexpected-third-state"] = True
        metadata_path.write_text(json.dumps(metadata) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(AuditError, "neither the recorded before-image"):
            recover_audit(self.workspace)
        self.assertTrue((self.workspace / PENDING_COMMIT_NAME).is_file())

    def test_verify_detects_a_tampered_event(self) -> None:
        event_path = self.workspace / "audit-events.jsonl"
        event = json.loads(event_path.read_text(encoding="utf-8").splitlines()[0])
        event["payload"]["rationale"] = "edited after the event was recorded"
        event_path.write_text(json.dumps(event) + "\n", encoding="utf-8")

        with self.assertRaisesRegex(AuditError, "hash does not match"):
            verify_audit_workspace(self.workspace)

    def test_schema_versions_and_event_sequences_require_exact_integers(self) -> None:
        self._new_finding()
        metadata_path = self.workspace / "audit-workspace.json"
        event_path = self.workspace / "audit-events.jsonl"
        finding_path = self.workspace / "findings" / "F-001.json"
        original_metadata = metadata_path.read_bytes()
        original_events = event_path.read_bytes()
        original_finding = finding_path.read_bytes()

        cases = (
            ("metadata-version", metadata_path, ("schema_version",), True, "lifecycle schema"),
            (
                "lifecycle-version",
                metadata_path,
                ("audit_lifecycle", "schema_version"),
                2.0,
                "lifecycle schema",
            ),
            ("finding-version", finding_path, ("schema_version",), True, "finding schema"),
            ("event-sequence", event_path, (0, "seq"), 1.0, "schema version or sequence"),
        )
        for name, path, components, invalid, message in cases:
            with self.subTest(name=name):
                metadata_path.write_bytes(original_metadata)
                event_path.write_bytes(original_events)
                finding_path.write_bytes(original_finding)
                if path == event_path:
                    payload = [
                        json.loads(line)
                        for line in original_events.decode("utf-8").splitlines()
                    ]
                else:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                target = payload
                for component in components[:-1]:
                    target = target[component]
                target[components[-1]] = invalid
                if path == event_path:
                    path.write_text(
                        "".join(json.dumps(item) + "\n" for item in payload),
                        encoding="utf-8",
                    )
                else:
                    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
                with self.assertRaisesRegex(AuditError, message):
                    verify_audit_workspace(self.workspace)

        metadata_path.write_bytes(original_metadata)
        event_path.write_bytes(original_events)
        finding_path.write_bytes(original_finding)

    def test_verify_replays_event_semantics_even_after_rehashing(self) -> None:
        self._new_finding()
        event_path = self.workspace / "audit-events.jsonl"
        events = [json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines()]
        finding = json.loads(
            (self.workspace / "findings" / "F-001.json").read_text(encoding="utf-8")
        )
        finding_hash = hashlib.sha256(
            json.dumps(
                finding,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        body = {
            "schema_version": 2,
            "seq": len(events) + 1,
            "timestamp": "2026-09-12T00:00:00Z",
            "event_type": "finding_status_changed",
            "actor": "Fabricated actor",
            "payload": {
                "finding_id": "F-001",
                "from_status": "open",
                "to_status": "closed",
                "rationale": "This illegal jump was rehashed.",
                "finding_sha256": finding_hash,
            },
            "prev_hash": events[-1]["event_hash"],
        }
        event_hash = hashlib.sha256(
            json.dumps(
                body,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        events.append({**body, "event_hash": event_hash})
        event_path.write_text(
            "".join(json.dumps(event, sort_keys=True) + "\n" for event in events),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(AuditError, "violates the finding lifecycle"):
            verify_audit_workspace(self.workspace)

    def test_verify_detects_a_structurally_valid_tampered_finding(self) -> None:
        self._new_finding()
        finding_path = self.workspace / "findings" / "F-001.json"
        finding = json.loads(finding_path.read_text(encoding="utf-8"))
        finding["title"] = "A changed title that still has a valid finding schema"
        finding_path.write_text(json.dumps(finding, indent=2) + "\n", encoding="utf-8")

        with self.assertRaisesRegex(AuditError, "finding hash does not match"):
            verify_audit_workspace(self.workspace)

        with self.assertRaisesRegex(AuditError, "finding hash does not match"):
            add_evidence(
                self.workspace,
                "F-001",
                evidence_id="E-launder",
                kind="observed",
                reference="fixture.txt",
                summary="A later mutation must not bless a tampered finding.",
                actor="Auditor",
            )

    def test_verify_detects_metadata_tampering(self) -> None:
        metadata_path = self.workspace / "audit-workspace.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["audit_lifecycle"]["g0_gate"]["rationale"] = "edited outside the ledger"
        metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

        with self.assertRaisesRegex(AuditError, "metadata hash does not match"):
            verify_audit_workspace(self.workspace)
        with self.assertRaisesRegex(AuditError, "metadata hash does not match"):
            rebaseline(self.workspace, actor="Auditor", reason="Must not bless tampering.")

    def test_findings_symlink_and_concurrent_writer_lock_are_refused(self) -> None:
        findings = self.workspace / "findings"
        findings.rmdir()
        external = self.root / "external-findings"
        external.mkdir()
        try:
            findings.symlink_to(external, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"directory symlinks unavailable: {error}")
        with self.assertRaisesRegex(AuditError, "findings directory"):
            list_findings(self.workspace)
        findings.unlink()
        findings.mkdir()

        lock = self.workspace / ".rcsl-write.lock"
        lock.write_text("fixture writer\n", encoding="utf-8")
        try:
            with self.assertRaisesRegex(AuditError, "locked by another writer"):
                set_g0_gate(
                    self.workspace,
                    "blocked",
                    reviewer="Named Reviewer",
                    rationale="This mutation must not race another writer.",
                    actor="Named Reviewer",
                )
        finally:
            lock.unlink()

    def test_isolated_directory_alias_is_refused_case_insensitively(self) -> None:
        isolated_alias = self.root / "do_not_open_until_finished"
        isolated_alias.mkdir()
        with self.assertRaisesRegex(AuditError, "isolated instructor material"):
            bind_audit(
                self.project,
                isolated_alias,
                actor="Auditor",
                rationale="This path must be rejected before access.",
            )

    def test_draft_report_is_not_called_review_ready(self) -> None:
        report = build_report_data(self.workspace)
        markdown = render_report_markdown(self.workspace)
        self.assertEqual(report["report_status"], "draft")
        self.assertIn("Report status: **DRAFT**", markdown)
        self.assertNotIn("Report status: **REVIEW-READY**", markdown)

    def test_report_data_and_markdown_are_review_ready_and_non_mutating(self) -> None:
        self._new_finding()
        observed_paths = (
            self.workspace / "audit-workspace.json",
            self.workspace / "audit-events.jsonl",
            self.workspace / "findings" / "F-001.json",
        )
        before = {path: path.read_bytes() for path in observed_paths}

        report = build_report_data(self.workspace)
        markdown = render_report_markdown(self.workspace)

        self.assertEqual(report["validator_scope"], "local_hash_chain_lifecycle_integrity_only")
        self.assertEqual(report["report_status"], "review-ready")
        self.assertTrue(report["findings"][0]["baseline_current"])
        self.assertIn("REVIEW-READY", markdown)
        self.assertNotIn("scientific PASS", markdown)
        self.assertEqual(before, {path: path.read_bytes() for path in observed_paths})

    def test_markdown_report_escapes_record_fields(self) -> None:
        self._complete_contract()
        set_g0_gate(
            self.workspace,
            "approved",
            reviewer="Reviewer\n## Forged reviewer",
            rationale="Review label escaping fixture.",
            actor="Auditor",
        )
        add_finding(
            self.workspace,
            finding_id="F-escape",
            title="Title | [forged](https://example.invalid)",
            layer="L1",
            competency="C1",
            severity="medium",
            claim="Claim\n# Forged claim `code`",
            first_broken_contract="A literal *contract* marker.",
            actor="Auditor",
        )
        add_evidence(
            self.workspace,
            "F-escape",
            evidence_id="E-escape",
            kind="observed",
            reference="artifact`)\n## Forged evidence",
            summary="Observed [link](https://example.invalid).",
            actor="Auditor",
        )

        markdown = render_report_markdown(self.workspace)

        self.assertNotIn("\n## Forged", markdown)
        self.assertNotIn("[forged](https://example.invalid)", markdown)
        self.assertNotIn("[link](https://example.invalid)", markdown)
        self.assertNotIn("`code`", markdown)
        self.assertIn("&#35;&#35; Forged reviewer", markdown)
        self.assertIn("&#91;forged&#93;&#40;https://example.invalid&#41;", markdown)


if __name__ == "__main__":
    unittest.main()
