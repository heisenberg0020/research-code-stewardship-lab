"""Lifecycle tests for the public, filesystem-local audit core."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

import stewardship_lab.audit as audit_core
import stewardship_lab.audit_evidence as evidence_core

from stewardship_lab.audit import (
    PENDING_COMMIT_NAME,
    _is_within,
    AuditError,
    add_evidence,
    add_finding,
    bind_audit,
    build_report_data,
    inspect_clean_project,
    import_content_evidence,
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

    def _convert_current_gate_to_legacy_projection(self) -> None:
        """Synthesize the v2 reference-only state produced before B-plus."""

        metadata_path = self.workspace / "audit-workspace.json"
        event_path = self.workspace / "audit-events.jsonl"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        lifecycle = metadata["audit_lifecycle"]
        lifecycle.pop("content_binding")
        events = [
            json.loads(line)
            for line in event_path.read_text(encoding="utf-8").splitlines()
        ]
        projection = events[-1]["payload"]["lifecycle_projection"]
        projection.pop("content_binding")
        events[-1]["payload"]["metadata_sha256"] = audit_core._metadata_hash(metadata)
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self._write_rehashed_events(events)

    def _write_rehashed_events(self, events: list[dict[str, object]]) -> None:
        previous_hash: str | None = None
        rebuilt: list[dict[str, object]] = []
        for sequence, event in enumerate(events, start=1):
            body = {key: value for key, value in event.items() if key != "event_hash"}
            body["seq"] = sequence
            body["prev_hash"] = previous_hash
            event_hash = audit_core._event_hash(body)
            rebuilt.append({**body, "event_hash": event_hash})
            previous_hash = event_hash
        (self.workspace / "audit-events.jsonl").write_text(
            "".join(
                json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n"
                for event in rebuilt
            ),
            encoding="utf-8",
        )

    def _move_workspace_inside_ignored_project(self) -> Path:
        moved = self.project / ".ignored-audit-workspace"
        exclude = self.project / ".git" / "info" / "exclude"
        existing = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
        separator = "" if not existing or existing.endswith("\n") else "\n"
        exclude.write_text(
            existing + separator + "/.ignored-audit-workspace/\n",
            encoding="utf-8",
        )
        self.workspace.rename(moved)
        self.workspace = moved
        self.assertEqual(
            self._git(self.project, "status", "--porcelain=v1", "--untracked-files=all"),
            "",
        )
        return moved

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

    def _import_evidence(
        self,
        *,
        finding_id: str = "F-001",
        evidence_id: str = "E-001",
        kind: str = "observed",
        summary: str = "The imported fixture bytes support the lifecycle record.",
        contents: bytes = b"bounded fixture evidence\n",
        logical_ref: str | None = None,
    ) -> dict[str, object]:
        sources = self.root / "explicit-evidence-sources"
        sources.mkdir(exist_ok=True)
        source = sources / f"{evidence_id}.txt"
        source.write_bytes(contents)
        return import_content_evidence(
            self.workspace,
            finding_id,
            evidence_id=evidence_id,
            evidence_type="artifact",
            kind=kind,
            source_kind="external",
            source_path=source,
            source_ref=logical_ref or f"evidence/{evidence_id}/result.txt",
            summary=summary,
            actor="Auditor",
            artifact_role="result",
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

    def test_relocated_workspace_inside_ignored_project_refuses_reads_and_mutations(
        self,
    ) -> None:
        moved = self._move_workspace_inside_ignored_project()
        observed_paths = (
            moved / "audit-workspace.json",
            moved / "audit-events.jsonl",
        )
        before = {path: path.read_bytes() for path in observed_paths}

        with self.assertRaisesRegex(AuditError, "remain outside"):
            verify_audit_workspace(moved)
        with self.assertRaisesRegex(AuditError, "remain outside"):
            list_findings(moved)
        with self.assertRaisesRegex(AuditError, "remain outside"):
            set_g0_gate(
                moved,
                "blocked",
                reviewer="Named Reviewer",
                rationale="A relocated workspace must not be writable.",
                actor="Named Reviewer",
            )

        self.assertEqual(before, {path: path.read_bytes() for path in observed_paths})
        self.assertEqual(
            self._git(self.project, "status", "--porcelain=v1", "--untracked-files=all"),
            "",
        )

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

    def test_approved_g0_uses_stable_lineage_and_retains_rotated_cases(self) -> None:
        remote = "https://example.invalid/fixture/project.git"
        self._git(self.project, "remote", "add", "origin", remote)
        self._approve()
        metadata_path = self.workspace / "audit-workspace.json"
        event_path = self.workspace / "audit-events.jsonl"
        lifecycle = json.loads(metadata_path.read_text(encoding="utf-8"))[
            "audit_lifecycle"
        ]
        first = lifecycle["content_binding"]
        first_event = json.loads(event_path.read_text(encoding="utf-8").splitlines()[0])
        expected_subject = "audit/lineage/" + hashlib.sha256(
            b"rcsl-audit-lineage-v1\0" + first_event["event_hash"].encode("ascii")
        ).hexdigest()
        self.assertEqual(first["case_ref"]["subject_id"], expected_subject)
        project_root = str(self.project.resolve())
        self.assertNotIn(project_root, expected_subject)
        self.assertNotIn(remote, expected_subject)
        for source in (project_root, remote):
            self.assertNotEqual(
                expected_subject,
                "audit/lineage/" + hashlib.sha256(source.encode("utf-8")).hexdigest(),
            )
        self.assertNotEqual(
            expected_subject,
            "audit/git-project/"
            + hashlib.sha256(project_root.encode("utf-8")).hexdigest(),
        )
        self.assertEqual(
            first["case_ref"]["case_id"], lifecycle["baseline"]["id"]
        )

        moved = self.root / "moved-public-audit-workspace"
        self.workspace.rename(moved)
        self.workspace = moved
        metadata_path = self.workspace / "audit-workspace.json"
        self.assertEqual(
            verify_audit_workspace(self.workspace)["current_case_ref"],
            first["case_ref"],
        )

        set_g0_gate(
            self.workspace,
            "blocked",
            reviewer="Named Reviewer",
            rationale="A non-approved decision must preserve the prior binding.",
            actor="Named Reviewer",
        )
        blocked = json.loads(metadata_path.read_text(encoding="utf-8"))[
            "audit_lifecycle"
        ]
        self.assertEqual(blocked["content_binding"], first)
        self.assertEqual(
            verify_audit_workspace(self.workspace)["content_store"][
                "referenced_case_manifests"
            ],
            1,
        )

        contract = self.workspace / "research-contract-template.md"
        contract.write_text(
            contract.read_text(encoding="utf-8") + "\nA material scope change.\n",
            encoding="utf-8",
        )
        set_g0_gate(
            self.workspace,
            "approved",
            reviewer="Named Reviewer",
            rationale="Approve the changed exact contract bytes.",
            actor="Named Reviewer",
        )
        rotated = json.loads(metadata_path.read_text(encoding="utf-8"))[
            "audit_lifecycle"
        ]["content_binding"]
        self.assertEqual(
            rotated["case_ref"]["subject_id"], first["case_ref"]["subject_id"]
        )
        self.assertEqual(rotated["case_ref"]["case_id"], first["case_ref"]["case_id"])
        self.assertNotEqual(
            rotated["case_ref"]["case_sha256"], first["case_ref"]["case_sha256"]
        )
        verification = verify_audit_workspace(self.workspace)
        self.assertEqual(verification["evidence_profile"], "content-bound-v1")
        self.assertEqual(verification["content_binding_state"], "current")
        self.assertEqual(verification["current_case_ref"], rotated["case_ref"])
        self.assertEqual(
            verification["content_store"]["referenced_case_manifests"], 2
        )
        self.assertEqual(verification["content_store"]["orphan_case_manifests"], 0)

        event_path = self.workspace / "audit-events.jsonl"
        original_events = event_path.read_bytes()
        events = [
            json.loads(line) for line in original_events.decode("utf-8").splitlines()
        ]
        current_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        for event in events[:-1]:
            projection = event["payload"].get("lifecycle_projection")
            if not isinstance(projection, dict) or "content_binding" not in projection:
                continue
            projection["content_binding"] = rotated
            projected_metadata = json.loads(json.dumps(current_metadata))
            projected_metadata["audit_lifecycle"] = projection
            event["payload"]["metadata_sha256"] = audit_core._metadata_hash(
                projected_metadata
            )
        self._write_rehashed_events(events)
        with self.assertRaisesRegex(AuditError, "projected baseline and G0 gate"):
            verify_audit_workspace(self.workspace)
        event_path.write_bytes(original_events)

        prior_manifest = self.workspace.joinpath(
            *evidence_core.CASE_STORE_PARTS,
            f"{first['case_ref']['case_sha256']}.json",
        )
        executable_manifest = json.loads(prior_manifest.read_text(encoding="utf-8"))
        executable_manifest["artifacts"][0]["executable"] = True
        executable_case = evidence_core.case_ref(executable_manifest)
        executable_binding = {**first, "case_ref": executable_case}
        executable_path = prior_manifest.with_name(
            f"{executable_case['case_sha256']}.json"
        )
        executable_path.write_bytes(evidence_core.canonical_json_bytes(executable_manifest))
        executable_path.chmod(0o600)
        events = [
            json.loads(line) for line in original_events.decode("utf-8").splitlines()
        ]
        for event in events[:-1]:
            projection = event["payload"].get("lifecycle_projection")
            if not isinstance(projection, dict) or "content_binding" not in projection:
                continue
            projection["content_binding"] = executable_binding
            projected_metadata = json.loads(json.dumps(current_metadata))
            projected_metadata["audit_lifecycle"] = projection
            event["payload"]["metadata_sha256"] = audit_core._metadata_hash(
                projected_metadata
            )
        self._write_rehashed_events(events)
        with self.assertRaisesRegex(AuditError, "projected baseline and G0 gate"):
            verify_audit_workspace(self.workspace)
        event_path.write_bytes(original_events)

        prior_manifest.unlink()
        with self.assertRaisesRegex(AuditError, "no matching case manifest"):
            verify_audit_workspace(self.workspace)

    def test_legacy_duplicate_gate_fields_require_migration_for_approval_and_preflight(
        self,
    ) -> None:
        contract = self.workspace / "research-contract-template.md"
        legacy_fields = (
            "\n- Status (`draft`, `approved`, or `blocked`): approved\n"
            "- Decision (`approve`, `revise`, or `stop`): approve\n"
            "- Approver and date: Named Reviewer, 2026-09-13\n"
        )
        self._complete_contract()
        contract.write_text(
            contract.read_text(encoding="utf-8") + legacy_fields,
            encoding="utf-8",
        )
        with self.assertRaisesRegex(AuditError, "legacy duplicate decision fields"):
            set_g0_gate(
                self.workspace,
                "approved",
                reviewer="Named Reviewer",
                rationale="Legacy duplicate fields cannot authorize the gate.",
                actor="Named Reviewer",
            )

        self._approve()
        contract.write_text(
            contract.read_text(encoding="utf-8") + legacy_fields,
            encoding="utf-8",
        )
        with self.assertRaisesRegex(AuditError, "legacy duplicate decision fields"):
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
            self._import_evidence(
                finding_id="F-001",
                evidence_id="E-new-epoch",
                kind="observed",
                summary="New-baseline evidence must not be mixed into an old finding.",
            )

    def test_rebaseline_preserves_a_stale_binding_until_the_next_approval(self) -> None:
        finding = self._new_finding()
        prior_case = finding["case_ref"]
        baseline = rebaseline(
            self.workspace,
            actor="Audit Owner",
            reason="Begin a new audit epoch without inventing a new case decision.",
        )
        metadata = json.loads(
            (self.workspace / "audit-workspace.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            metadata["audit_lifecycle"]["content_binding"]["case_ref"], prior_case
        )
        self.assertNotEqual(baseline["id"], prior_case["case_id"])
        stale = verify_audit_workspace(self.workspace)
        self.assertEqual(stale["content_binding_state"], "stale")
        self.assertEqual(stale["content_store"]["referenced_case_manifests"], 1)
        stale_report = build_report_data(self.workspace)
        self.assertEqual(stale_report["findings"][0]["case_state"], "stale")
        self.assertFalse(stale_report["findings"][0]["case_current"])

        self._approve()
        current = verify_audit_workspace(self.workspace)
        self.assertEqual(current["content_binding_state"], "current")
        self.assertNotEqual(current["current_case_ref"], prior_case)
        self.assertEqual(current["current_case_ref"]["case_id"], baseline["id"])
        report = build_report_data(self.workspace)
        self.assertEqual(report["findings"][0]["case_state"], "stale")
        self.assertEqual(current["content_store"]["referenced_case_manifests"], 2)

    def test_finding_evidence_and_legal_transitions_reach_closed(self) -> None:
        finding = self._new_finding()
        self.assertEqual(finding["status"], "open")
        self.assertEqual(list_findings(self.workspace)[0]["id"], "F-001")
        self._import_evidence(
            finding_id="F-001",
            evidence_id="E-001",
            kind="observed",
            summary="The fixture evidence supports the recorded lifecycle claim.",
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

    def test_content_import_binds_the_record_event_and_global_evidence_id(self) -> None:
        finding = self._new_finding()
        imported = self._import_evidence()
        record = imported["evidence"][0]
        self.assertEqual(record["case_ref"], finding["case_ref"])
        self.assertEqual(record["artifact_ref"]["path"], record["source"]["ref"])
        events = [
            json.loads(line)
            for line in (self.workspace / "audit-events.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        self.assertEqual(
            events[-1]["payload"]["evidence_ref"],
            evidence_core.content_evidence_record_ref(record),
        )
        verification = verify_audit_workspace(self.workspace)
        self.assertEqual(verification["content_finding_count"], 1)
        self.assertEqual(verification["content_evidence_count"], 1)

        self._new_finding("F-002")
        with self.assertRaisesRegex(AuditError, "content evidence id already exists"):
            self._import_evidence(finding_id="F-002", evidence_id="E-001")

    def test_content_record_ref_and_required_cas_objects_fail_closed(self) -> None:
        self._new_finding()
        imported = self._import_evidence()
        record = imported["evidence"][0]
        event_path = self.workspace / "audit-events.jsonl"
        original_events = event_path.read_bytes()
        events = [
            json.loads(line) for line in original_events.decode("utf-8").splitlines()
        ]
        events[-1]["payload"]["kind"] = "asserted"
        self._write_rehashed_events(events)
        with self.assertRaisesRegex(AuditError, "kind does not match"):
            verify_audit_workspace(self.workspace)

        event_path.write_bytes(original_events)
        events = [
            json.loads(line) for line in original_events.decode("utf-8").splitlines()
        ]
        events[-1]["payload"]["evidence_ref"]["record_sha256"] = "0" * 64
        self._write_rehashed_events(events)
        with self.assertRaisesRegex(AuditError, "does not bind the inline record"):
            verify_audit_workspace(self.workspace)
        event_path.write_bytes(original_events)

        case = imported["case_ref"]
        manifest_path = self.workspace.joinpath(
            *evidence_core.CASE_STORE_PARTS, f"{case['case_sha256']}.json"
        )
        manifest_bytes = manifest_path.read_bytes()
        manifest_path.unlink()
        with self.assertRaisesRegex(AuditError, "no matching case manifest"):
            verify_audit_workspace(self.workspace)
        manifest_path.write_bytes(manifest_bytes)
        manifest_path.chmod(0o600)

        artifact = record["artifact_ref"]
        blob_path = self.workspace.joinpath(
            *evidence_core.BLOB_STORE_PARTS, artifact["sha256"]
        )
        blob_path.write_bytes(b"tampered evidence bytes")
        with self.assertRaisesRegex(AuditError, "content address"):
            verify_audit_workspace(self.workspace)

    def test_replay_enforces_event_time_case_and_prior_content_evidence(self) -> None:
        self._new_finding()
        self._import_evidence()
        contract = self.workspace / "research-contract-template.md"
        contract.write_text(
            contract.read_text(encoding="utf-8") + "\nA rotated event-time scope.\n",
            encoding="utf-8",
        )
        set_g0_gate(
            self.workspace,
            "approved",
            reviewer="Named Reviewer",
            rationale="Rotate the active case before the adversarial event move.",
            actor="Named Reviewer",
        )
        event_path = self.workspace / "audit-events.jsonl"
        original_events = event_path.read_bytes()
        events = [
            json.loads(line) for line in original_events.decode("utf-8").splitlines()
        ]
        evidence_index = next(
            index
            for index, event in enumerate(events)
            if event["event_type"] == "finding_evidence_added"
        )
        events.append(events.pop(evidence_index))
        self._write_rehashed_events(events)
        with self.assertRaisesRegex(AuditError, "event-time approved audit case"):
            verify_audit_workspace(self.workspace)
        event_path.write_bytes(original_events)

        add_finding(
            self.workspace,
            finding_id="F-zero-evidence",
            title="Zero-evidence terminal replay fixture",
            layer="L1",
            competency="C1",
            severity="low",
            claim="A terminal label cannot manufacture prior content evidence.",
            first_broken_contract="The content evidence gate is still empty.",
            actor="Auditor",
        )
        self._advance_to_mitigated("F-zero-evidence")
        finding_path = self.workspace / "findings" / "F-zero-evidence.json"
        finding = json.loads(finding_path.read_text(encoding="utf-8"))
        finding["status"] = "verified"
        finding["actor"] = "Fabricated Reviewer"
        finding["updated_at"] = "2026-09-13T01:02:03Z"
        finding_path.write_text(json.dumps(finding, indent=2) + "\n", encoding="utf-8")
        events = [
            json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines()
        ]
        events.append(
            {
                "schema_version": 2,
                "timestamp": "2026-09-13T01:02:03Z",
                "event_type": "finding_status_changed",
                "actor": "Fabricated Reviewer",
                "payload": {
                    "finding_id": "F-zero-evidence",
                    "from_status": "mitigated",
                    "to_status": "verified",
                    "rationale": "This rehashed label has no qualifying content record.",
                    "finding_sha256": audit_core._finding_hash(finding),
                },
            }
        )
        self._write_rehashed_events(events)
        with self.assertRaisesRegex(AuditError, "prior qualifying content evidence"):
            verify_audit_workspace(self.workspace)

    def test_terminal_state_requires_a_qualifying_content_record(self) -> None:
        self._new_finding()
        add_evidence(
            self.workspace,
            "F-001",
            evidence_id="E-reference",
            kind="reproduced",
            reference="historical/result.txt",
            summary="Even a reproduced label is still only a reference record.",
            actor="Auditor",
        )
        self._import_evidence(evidence_id="E-asserted", kind="asserted")
        verification = verify_audit_workspace(self.workspace)
        report = build_report_data(self.workspace)
        self.assertEqual(verification["content_evidence_count"], 1)
        self.assertEqual(len(report["findings"][0]["evidence"]), 2)
        self.assertIn("historical/result.txt", render_report_markdown(self.workspace))
        self._advance_to_mitigated()
        with self.assertRaisesRegex(AuditError, "observed, derived, or reproduced"):
            transition_finding(
                self.workspace,
                "F-001",
                "verified",
                actor="Named Reviewer",
                rationale="An assertion alone must not pass the terminal gate.",
            )
        self._import_evidence(evidence_id="E-observed", kind="observed")
        self.assertEqual(
            transition_finding(
                self.workspace,
                "F-001",
                "verified",
                actor="Named Reviewer",
                rationale="The current case now has a qualifying byte-bound record.",
            )["status"],
            "verified",
        )

    def test_reference_evidence_accepts_legacy_finding_but_rejects_stale_case(self) -> None:
        self._approve()
        self._convert_current_gate_to_legacy_projection()
        legacy = add_finding(
            self.workspace,
            finding_id="F-legacy-current",
            title="Current legacy finding",
            layer="L1",
            competency="C1",
            severity="low",
            claim="This finding predates content binding at the same baseline.",
            first_broken_contract="A reference-only historical record.",
            actor="Auditor",
        )
        self.assertNotIn("case_ref", legacy)
        self._approve()
        updated = add_evidence(
            self.workspace,
            "F-legacy-current",
            evidence_id="E-legacy-current",
            kind="observed",
            reference="historical/result.txt",
            summary="A current-baseline legacy finding remains appendable.",
            actor="Auditor",
        )
        self.assertEqual(updated["evidence"][0]["id"], "E-legacy-current")

        bound = add_finding(
            self.workspace,
            finding_id="F-bound-old-case",
            title="Content-bound finding before case rotation",
            layer="L1",
            competency="C1",
            severity="low",
            claim="This finding remains tied to its exact contract case.",
            first_broken_contract="The exact case must not be blurred.",
            actor="Auditor",
        )
        self.assertIn("case_ref", bound)
        contract = self.workspace / "research-contract-template.md"
        contract.write_text(
            contract.read_text(encoding="utf-8") + "\nA rotated audit scope.\n",
            encoding="utf-8",
        )
        set_g0_gate(
            self.workspace,
            "approved",
            reviewer="Named Reviewer",
            rationale="Approve the rotated exact contract case.",
            actor="Named Reviewer",
        )
        with self.assertRaisesRegex(AuditError, "older audit case"):
            add_evidence(
                self.workspace,
                "F-bound-old-case",
                evidence_id="E-stale-case",
                kind="observed",
                reference="stale/result.txt",
                summary="A stale content case must not receive later reference evidence.",
                actor="Auditor",
            )

    def test_evidence_gated_transition_requires_evidence_and_clean_approved_preflight(
        self,
    ) -> None:
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

        self._import_evidence(
            finding_id="F-001",
            evidence_id="E-001",
            kind="observed",
            summary="Record the evidence before attempting an evidence-gated declared state.",
        )
        set_g0_gate(
            self.workspace,
            "draft",
            reviewer="Named Reviewer",
            rationale="Return the fixture gate to draft to exercise the evidence gate.",
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
                rationale="A dirty project cannot support an evidence-gated declared state.",
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

    def test_recovery_refuses_relocated_workspace_inside_ignored_project(self) -> None:
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
                raise AuditError("simulated snapshot failure")
            original_write(path, content)

        with mock.patch.object(audit_core, "_atomic_write_text", side_effect=fail_snapshot):
            with self.assertRaisesRegex(AuditError, "audit recover"):
                set_g0_gate(
                    self.workspace,
                    "blocked",
                    reviewer="Named Reviewer",
                    rationale="Create a pending gate transition for relocation testing.",
                    actor="Named Reviewer",
                )

        moved = self._move_workspace_inside_ignored_project()
        observed_paths = (
            moved / "audit-workspace.json",
            moved / "audit-events.jsonl",
            moved / PENDING_COMMIT_NAME,
        )
        before = {path: path.read_bytes() for path in observed_paths}
        with self.assertRaisesRegex(AuditError, "remain outside"):
            recover_audit(moved)
        self.assertEqual(before, {path: path.read_bytes() for path in observed_paths})
        self.assertEqual(
            self._git(self.project, "status", "--porcelain=v1", "--untracked-files=all"),
            "",
        )

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
                self._import_evidence(
                    finding_id="F-001",
                    evidence_id="E-recover",
                    kind="observed",
                    summary="This evidence snapshot was written before the event failed.",
                )

        pending = json.loads(
            (self.workspace / PENDING_COMMIT_NAME).read_text(encoding="utf-8")
        )
        record = pending["snapshot_after"]["evidence"][0]
        blob = self.workspace.joinpath(
            *evidence_core.BLOB_STORE_PARTS, record["artifact_ref"]["sha256"]
        )
        original_blob = blob.read_bytes()
        blob.write_bytes(b"tampered while recovery is pending")
        with self.assertRaisesRegex(AuditError, "content address"):
            recover_audit(self.workspace)
        self.assertTrue((self.workspace / PENDING_COMMIT_NAME).is_file())
        blob.write_bytes(original_blob)
        recovered = recover_audit(self.workspace)
        finding = list_findings(self.workspace)[0]
        self.assertEqual(recovered["verification"]["event_count"], event_count + 1)
        self.assertEqual([item["id"] for item in finding["evidence"]], ["E-recover"])
        self.assertEqual(
            recover_audit(self.workspace)["verification"]["event_count"],
            event_count + 1,
        )

    def test_content_blob_published_before_pending_failure_is_a_valid_orphan(self) -> None:
        self._new_finding()
        finding_path = self.workspace / "findings" / "F-001.json"
        event_path = self.workspace / "audit-events.jsonl"
        before = {path: path.read_bytes() for path in (finding_path, event_path)}
        with mock.patch.object(
            audit_core,
            "_write_pending_commit",
            side_effect=AuditError("simulated pending intent failure"),
        ):
            with self.assertRaisesRegex(AuditError, "simulated pending intent failure"):
                self._import_evidence(
                    evidence_id="E-orphan",
                    contents=b"valid content that never reached the lifecycle ledger\n",
                )

        self.assertEqual(before, {path: path.read_bytes() for path in before})
        self.assertFalse((self.workspace / PENDING_COMMIT_NAME).exists())
        verification = verify_audit_workspace(self.workspace)
        self.assertEqual(verification["content_evidence_count"], 0)
        self.assertEqual(
            verification["content_store"]["orphan_evidence_blobs"], 1
        )

    def test_invalid_direct_content_metadata_does_not_publish_an_orphan_blob(self) -> None:
        self._new_finding()
        source = self.root / "invalid-direct-metadata.txt"
        source.write_bytes(b"source bytes that must not be stored for bad metadata\n")
        blob_store = self.workspace.joinpath(*evidence_core.BLOB_STORE_PARTS)
        before = sorted(path.name for path in blob_store.iterdir())
        common = {
            "workspace": self.workspace,
            "finding_id": "F-001",
            "evidence_id": "E-invalid-direct",
            "evidence_type": "artifact",
            "kind": "observed",
            "source_kind": "external",
            "source_path": source,
            "source_ref": "runs/invalid-direct-metadata.txt",
            "summary": "A declared local fixture.",
            "actor": "Auditor",
            "artifact_role": "result",
        }
        with self.assertRaisesRegex(AuditError, "summary must be a non-empty string"):
            import_content_evidence(**(common | {"summary": "   "}))
        with self.assertRaisesRegex(AuditError, "artifact_role must be a non-empty string"):
            import_content_evidence(**(common | {"artifact_role": "   "}))
        with self.assertRaisesRegex(AuditError, "exit_code must be a signed 32-bit integer"):
            import_content_evidence(
                **(
                    common
                    | {
                        "evidence_type": "command-result",
                        "artifact_role": None,
                        "declared_command": "fixture result generated elsewhere",
                        "exit_code": 2**31,
                    }
                )
            )
        add_evidence(
            self.workspace,
            "F-001",
            evidence_id="E-invalid-direct",
            kind="observed",
            reference="runs/invalid-direct-metadata.txt",
            summary="This legacy pointer must not share an ID with an imported record.",
            actor="Auditor",
        )
        with self.assertRaisesRegex(AuditError, "evidence already exists"):
            import_content_evidence(**common)
        self.assertEqual(sorted(path.name for path in blob_store.iterdir()), before)
        self.assertEqual(verify_audit_workspace(self.workspace)["content_evidence_count"], 0)

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
                self._import_evidence(
                    finding_id="F-001",
                    evidence_id="E-oversize",
                    kind="observed",
                    summary="x" * (current_limit * 2),
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
                self._import_evidence(
                    finding_id="F-001",
                    evidence_id="E-capacity",
                    kind="observed",
                    summary="No evidence capacity remains.",
                )
        with mock.patch.object(audit_core, "MAX_TOTAL_EVIDENCE", 0):
            with self.assertRaisesRegex(AuditError, "aggregate limit"):
                self._import_evidence(
                    finding_id="F-001",
                    evidence_id="E-total-capacity",
                    kind="observed",
                    summary="No aggregate evidence capacity remains.",
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

        with self.assertRaisesRegex(AuditError, "payload does not match"):
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

    def test_legacy_v1_interrupted_bind_recovers_metadata_and_first_event(self) -> None:
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
        pending_path = workspace / PENDING_COMMIT_NAME
        legacy_pending = json.loads(pending_path.read_text(encoding="utf-8"))
        legacy_pending["schema_version"] = audit_core.LEGACY_PENDING_COMMIT_SCHEMA_VERSION
        for field in (
            "snapshot_after_sha256",
            "event_log_before_sha256",
            "event_log_after_sha256",
            "content_sha256",
        ):
            legacy_pending.pop(field)
        pending_path.write_text(
            json.dumps(legacy_pending, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        recovered = recover_audit(workspace)
        self.assertEqual(recovered["verification"]["event_count"], 1)
        self.assertTrue((workspace / "findings").is_dir())
        self.assertTrue(verify_audit_workspace(workspace)["ok"])

    def test_interrupted_bind_refuses_zero_byte_event_log_as_a_third_state(self) -> None:
        workspace = self.root / "zero-byte-bind-workspace"
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
                    rationale="Leave a durable bind intent for third-state testing.",
                )

        event_log = workspace / "audit-events.jsonl"
        event_log.write_bytes(b"")
        pending_before = (workspace / PENDING_COMMIT_NAME).read_bytes()
        with self.assertRaisesRegex(AuditError, "neither the recorded before-image"):
            recover_audit(workspace)
        self.assertEqual(event_log.read_bytes(), b"")
        self.assertEqual((workspace / PENDING_COMMIT_NAME).read_bytes(), pending_before)

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
        event["payload"]["lifecycle_projection"]["g0_gate"]["rationale"] = (
            "edited after the event was recorded"
        )
        event_path.write_text(json.dumps(event) + "\n", encoding="utf-8")

        with self.assertRaisesRegex(AuditError, "hash does not match"):
            verify_audit_workspace(self.workspace)

    def test_new_lifecycle_events_store_a_full_projection_as_the_only_claim(self) -> None:
        self._approve()
        rebaseline(
            self.workspace,
            actor="Audit Owner",
            reason="Exercise each projected lifecycle transition.",
        )
        metadata = json.loads(
            (self.workspace / "audit-workspace.json").read_text(encoding="utf-8")
        )
        events = [
            json.loads(line)
            for line in (self.workspace / "audit-events.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        lifecycle_events = [
            event
            for event in events
            if event["event_type"] in audit_core.LIFECYCLE_EVENT_TYPES
        ]

        self.assertEqual(
            [event["event_type"] for event in lifecycle_events],
            ["workspace_bound", "g0_gate_set", "baseline_replaced"],
        )
        for event in lifecycle_events:
            self.assertEqual(
                set(event["payload"]),
                {"metadata_sha256", "lifecycle_projection"},
            )
            self.assertEqual(
                event["payload"]["lifecycle_projection"]["event_projection_mode"],
                audit_core.LIFECYCLE_PROJECTION_MODE,
            )
        self.assertEqual(
            lifecycle_events[-1]["payload"]["lifecycle_projection"],
            metadata["audit_lifecycle"],
        )

    def test_rehashed_gate_projection_tamper_is_rejected(self) -> None:
        self._approve()
        event_path = self.workspace / "audit-events.jsonl"
        events = [
            json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines()
        ]
        events[-1]["payload"]["lifecycle_projection"]["g0_gate"]["rationale"] = (
            "A rehashed event still cannot contradict its metadata snapshot."
        )
        self._write_rehashed_events(events)

        with self.assertRaisesRegex(AuditError, "projection does not match"):
            verify_audit_workspace(self.workspace)

    def test_rehashed_projection_rejects_foreign_subject_and_binding_removal(self) -> None:
        self._approve()
        metadata_path = self.workspace / "audit-workspace.json"
        event_path = self.workspace / "audit-events.jsonl"
        original_metadata = metadata_path.read_bytes()
        original_events = event_path.read_bytes()
        metadata = json.loads(original_metadata)
        events = [
            json.loads(line) for line in original_events.decode("utf-8").splitlines()
        ]
        foreign_subject = "audit/git-project/" + "0" * 64
        metadata["audit_lifecycle"]["content_binding"]["case_ref"][
            "subject_id"
        ] = foreign_subject
        events[-1]["payload"]["lifecycle_projection"]["content_binding"][
            "case_ref"
        ]["subject_id"] = foreign_subject
        events[-1]["payload"]["metadata_sha256"] = audit_core._metadata_hash(metadata)
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self._write_rehashed_events(events)
        with self.assertRaisesRegex(AuditError, "audit lineage"):
            verify_audit_workspace(self.workspace)
        metadata_path.write_bytes(original_metadata)
        event_path.write_bytes(original_events)

        set_g0_gate(
            self.workspace,
            "blocked",
            reviewer="Named Reviewer",
            rationale="Create a later projection whose binding must remain sticky.",
            actor="Named Reviewer",
        )
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        events = [
            json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines()
        ]
        metadata["audit_lifecycle"].pop("content_binding")
        events[-1]["payload"]["lifecycle_projection"].pop("content_binding")
        events[-1]["payload"]["metadata_sha256"] = audit_core._metadata_hash(metadata)
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self._write_rehashed_events(events)

        with self.assertRaisesRegex(AuditError, "must not disappear"):
            verify_audit_workspace(self.workspace)

    def test_rehashed_projection_downgrade_is_rejected(self) -> None:
        event_path = self.workspace / "audit-events.jsonl"
        events = [
            json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines()
        ]
        events[0]["payload"] = {
            "metadata_sha256": events[0]["payload"]["metadata_sha256"]
        }
        self._write_rehashed_events(events)

        with self.assertRaisesRegex(AuditError, "requires a full lifecycle event projection"):
            verify_audit_workspace(self.workspace)

    def test_rehashed_rebaseline_projection_must_reset_g0(self) -> None:
        rebaseline(
            self.workspace,
            actor="Audit Owner",
            reason="Create a second lifecycle projection for tamper testing.",
        )
        metadata_path = self.workspace / "audit-workspace.json"
        event_path = self.workspace / "audit-events.jsonl"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        events = [
            json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines()
        ]
        metadata["audit_lifecycle"]["g0_gate"]["status"] = "approved"
        events[-1]["payload"]["lifecycle_projection"]["g0_gate"]["status"] = "approved"
        events[-1]["payload"]["metadata_sha256"] = audit_core._metadata_hash(metadata)
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self._write_rehashed_events(events)

        with self.assertRaisesRegex(AuditError, "must reset G0 to draft"):
            verify_audit_workspace(self.workspace)

    def test_legacy_v2_events_remain_readable_and_migrate_on_next_write(self) -> None:
        metadata_path = self.workspace / "audit-workspace.json"
        event_path = self.workspace / "audit-events.jsonl"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        lifecycle = metadata["audit_lifecycle"]
        lifecycle.pop("event_projection_mode")
        events = [
            json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines()
        ]
        baseline = lifecycle["baseline"]
        gate = lifecycle["g0_gate"]
        events[0]["payload"] = {
            "project_root": lifecycle["project"]["root"],
            "baseline_head": baseline["head"],
            "baseline_id": baseline["id"],
            "baseline_branch": baseline["branch"],
            "g0_status": gate["status"],
            "rationale": gate["rationale"],
            "metadata_sha256": audit_core._metadata_hash(metadata),
            "contract_sha256": gate["contract_sha256"],
        }
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self._write_rehashed_events(events)

        self.assertTrue(verify_audit_workspace(self.workspace)["ok"])
        set_g0_gate(
            self.workspace,
            "blocked",
            reviewer="Named Reviewer",
            rationale="The next lifecycle write establishes the strict projection anchor.",
            actor="Named Reviewer",
        )
        migrated_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        migrated_events = [
            json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(
            migrated_metadata["audit_lifecycle"]["event_projection_mode"],
            audit_core.LIFECYCLE_PROJECTION_MODE,
        )
        self.assertEqual(
            migrated_events[-1]["payload"]["lifecycle_projection"],
            migrated_metadata["audit_lifecycle"],
        )
        self.assertTrue(verify_audit_workspace(self.workspace)["ok"])

    def test_legacy_reference_terminal_history_remains_readable(self) -> None:
        self._approve()
        self._convert_current_gate_to_legacy_projection()
        orphan_blob = next(
            self.workspace.joinpath(*evidence_core.BLOB_STORE_PARTS).iterdir()
        )
        orphan_blob.write_bytes(b"tampered preparation orphan")
        self.assertEqual(
            verify_audit_workspace(self.workspace)["evidence_profile"],
            "reference-only",
        )
        add_finding(
            self.workspace,
            finding_id="F-legacy",
            title="Legacy terminal fixture",
            layer="L1",
            competency="C1",
            severity="low",
            claim="A historical terminal record remains readable.",
            first_broken_contract="Historical reference-only evidence.",
            actor="Auditor",
        )
        add_evidence(
            self.workspace,
            "F-legacy",
            evidence_id="E-legacy",
            kind="observed",
            reference="historical/result.txt",
            summary="This is a pre-content-binding reference record.",
            actor="Auditor",
        )
        self._advance_to_mitigated("F-legacy")
        with self.assertRaisesRegex(AuditError, "content-bound audit case"):
            transition_finding(
                self.workspace,
                "F-legacy",
                "verified",
                actor="Named Reviewer",
                rationale="New terminal transitions require the current profile.",
            )

        finding_path = self.workspace / "findings" / "F-legacy.json"
        finding = json.loads(finding_path.read_text(encoding="utf-8"))
        finding["status"] = "verified"
        finding["actor"] = "Historical Reviewer"
        finding["updated_at"] = "2026-09-13T01:02:03Z"
        finding_path.write_text(json.dumps(finding, indent=2) + "\n", encoding="utf-8")
        event_path = self.workspace / "audit-events.jsonl"
        events = [
            json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines()
        ]
        events.append(
            {
                "schema_version": 2,
                "timestamp": "2026-09-13T01:02:03Z",
                "event_type": "finding_status_changed",
                "actor": "Historical Reviewer",
                "payload": {
                    "finding_id": "F-legacy",
                    "from_status": "mitigated",
                    "to_status": "verified",
                    "rationale": "Recorded before the content-bound terminal rule.",
                    "finding_sha256": audit_core._finding_hash(finding),
                },
            }
        )
        self._write_rehashed_events(events)
        verification = verify_audit_workspace(self.workspace)
        self.assertTrue(verification["ok"])
        self.assertEqual(list_findings(self.workspace)[0]["status"], "verified")

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

        if audit_core._fcntl is None:
            self.skipTest("POSIX advisory locks unavailable")
        lock = self.workspace / audit_core.LOCK_FILE_NAME
        holder = subprocess.Popen(
            (
                sys.executable,
                "-c",
                (
                    "import fcntl, os, sys; "
                    "fd=os.open(sys.argv[1], os.O_CREAT|os.O_RDWR, 0o600); "
                    "fcntl.flock(fd, fcntl.LOCK_EX); "
                    "print('locked', flush=True); sys.stdin.read()"
                ),
                str(lock),
            ),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            self.assertIsNotNone(holder.stdout)
            self.assertEqual(holder.stdout.readline().strip(), "locked")
            with self.assertRaisesRegex(AuditError, "locked by another writer"):
                verify_audit_workspace(self.workspace)
            with self.assertRaisesRegex(AuditError, "locked by another"):
                set_g0_gate(
                    self.workspace,
                    "blocked",
                    reviewer="Named Reviewer",
                    rationale="This mutation must not race another writer.",
                    actor="Named Reviewer",
                )
        finally:
            holder.kill()
            holder.communicate(timeout=5)

        # A killed writer leaves the fixed lock file, but not a kernel lock.
        self.assertTrue(lock.is_file())
        gate = set_g0_gate(
            self.workspace,
            "blocked",
            reviewer="Named Reviewer",
            rationale="A dead writer must not require manual lock-file cleanup.",
            actor="Named Reviewer",
        )
        self.assertEqual(gate["status"], "blocked")
        self.assertTrue(verify_audit_workspace(self.workspace)["ok"])

    def test_reader_refuses_a_writer_snapshot_event_intermediate_state(self) -> None:
        event_path = self.workspace / "audit-events.jsonl"
        event_count = len(event_path.read_text(encoding="utf-8").splitlines())
        snapshot_written = threading.Event()
        finish_write = threading.Event()
        writer_errors: list[BaseException] = []
        original_write = audit_core._atomic_write_text
        paused = False

        def pause_after_snapshot(path: Path, content: str) -> None:
            nonlocal paused
            original_write(path, content)
            if (
                not paused
                and path.name == "audit-workspace.json"
                and (self.workspace / PENDING_COMMIT_NAME).exists()
            ):
                paused = True
                snapshot_written.set()
                if not finish_write.wait(timeout=5):
                    raise AuditError("timed out waiting to finish simulated write")

        def mutate() -> None:
            try:
                set_g0_gate(
                    self.workspace,
                    "blocked",
                    reviewer="Named Reviewer",
                    rationale="Pause between the snapshot and event after-images.",
                    actor="Named Reviewer",
                )
            except BaseException as error:  # pragma: no cover - asserted below.
                writer_errors.append(error)

        with mock.patch.object(audit_core, "_atomic_write_text", side_effect=pause_after_snapshot):
            writer = threading.Thread(target=mutate)
            writer.start()
            self.assertTrue(snapshot_written.wait(timeout=5))
            try:
                with self.assertRaisesRegex(AuditError, "locked by another writer"):
                    verify_audit_workspace(self.workspace)
            finally:
                finish_write.set()
                writer.join(timeout=5)

        self.assertFalse(writer.is_alive())
        self.assertEqual(writer_errors, [])
        verification = verify_audit_workspace(self.workspace)
        self.assertEqual(verification["event_count"], event_count + 1)

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

    def test_incomplete_report_is_not_called_preflight_current(self) -> None:
        report = build_report_data(self.workspace)
        markdown = render_report_markdown(self.workspace)
        self.assertEqual(report["report_status"], "preflight-not-current")
        self.assertIn("Report status: **PREFLIGHT-NOT-CURRENT**", markdown)
        self.assertNotIn("Report status: **PREFLIGHT-CURRENT**", markdown)

    def test_report_data_and_markdown_are_preflight_current_and_non_mutating(
        self,
    ) -> None:
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
        self.assertEqual(report["report_status"], "preflight-current")
        self.assertTrue(report["findings"][0]["baseline_current"])
        self.assertIn("PREFLIGHT-CURRENT", markdown)
        self.assertIn("Declared lifecycle state", markdown)
        self.assertIn("declared lifecycle labels", markdown)
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
        self._import_evidence(
            finding_id="F-escape",
            evidence_id="E-escape",
            kind="observed",
            logical_ref="evidence/E-escape/artifact`).txt",
            summary="Observed [link](https://example.invalid).\n## Forged evidence",
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
