"""Phase 4A tests for the offline, boundary-preserving static view."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest
from unittest import mock

from stewardship_lab import release as release_core
from stewardship_lab import view as view_core


ROOT = Path(__file__).resolve().parents[1]


def tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def rewrite_view_controls(view: Path) -> None:
    """Rebind a deliberately modified fixture for schema-level rejection tests."""

    manifest_path = view / "VIEW_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    by_path = {record["path"]: record for record in manifest["files"]}
    for relative, record in by_path.items():
        payload = (view / relative).read_bytes()
        record["sha256"] = view_core._sha256_bytes(payload)
        record["size"] = len(payload)
    manifest_path.write_bytes(view_core._json_bytes(manifest))
    payload_paths = sorted(
        path.relative_to(view).as_posix()
        for path in view.rglob("*")
        if path.is_file() and path.name != "CHECKSUMS.sha256"
    )
    checksums = "".join(
        f"{view_core._sha256_bytes((view / relative).read_bytes())}  {relative}\n"
        for relative in payload_paths
    )
    (view / "CHECKSUMS.sha256").write_text(checksums, encoding="utf-8")


def rewrite_evidence(view: Path, kind: str, payload: dict[str, object]) -> None:
    """Rebind one tampered evidence fixture, including deterministic HTML."""

    manifest_path = view / "VIEW_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    evidence_record = next(item for item in manifest["evidence"] if item["kind"] == kind)
    old_path = evidence_record["path"]
    data = view_core._json_bytes(payload)
    digest = view_core._sha256_bytes(data)
    new_path = f"data/evidence/{kind}-{digest}.json"
    (view / new_path).write_bytes(data)
    (view / new_path).chmod(0o600)
    if new_path != old_path:
        (view / old_path).unlink()
    evidence_record.update({"path": new_path, "sha256": digest, "size": len(data)})
    file_record = next(item for item in manifest["files"] if item["path"] == old_path)
    file_record.update({"path": new_path, "sha256": digest, "size": len(data)})
    manifest["files"].sort(key=lambda item: item["path"])

    registry = json.loads(
        (view / "data" / "CASE_REGISTRY.json").read_text(encoding="utf-8")
    )
    evidence = {}
    for item in manifest["evidence"]:
        evidence[item["kind"]] = json.loads((view / item["path"]).read_text(encoding="utf-8"))
    (view / "index.html").write_bytes(
        view_core._render_html(registry, evidence, manifest["privacy_classification"])
    )
    manifest_path.write_bytes(view_core._json_bytes(manifest))
    rewrite_view_controls(view)


def rebind_modified_open_demo(package: Path) -> None:
    """Refresh an Open Demo fixture after changing one retained source file."""

    source_root = package / release_core.OPEN_DEMO_SOURCE.name
    source_records = []
    for path in sorted(item for item in source_root.rglob("*") if item.is_file()):
        payload = path.read_bytes()
        source_records.append(
            {
                "path": path.relative_to(source_root).as_posix(),
                "sha256": view_core._sha256_bytes(payload),
                "size": len(payload),
                "executable": bool(path.stat().st_mode & 0o111),
            }
        )
    source_digest = release_core._root_digest(source_records)
    validation_path = package / "VALIDATION_RECORD.json"
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    validation["validated_source_tree_sha256"] = source_digest
    validation_path.write_bytes(view_core._json_bytes(validation))

    manifest_path = package / "PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source_tree_sha256"] = source_digest
    for record in manifest["files"]:
        payload = (package / record["path"]).read_bytes()
        record["sha256"] = view_core._sha256_bytes(payload)
        record["size"] = len(payload)
    manifest_path.write_bytes(view_core._json_bytes(manifest))
    lines = []
    for path in sorted(item for item in package.rglob("*") if item.is_file()):
        relative = path.relative_to(package).as_posix()
        if relative == "CHECKSUMS.sha256":
            continue
        lines.append(f"{view_core._sha256_bytes(path.read_bytes())}  {relative}")
    (package / "CHECKSUMS.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


class StaticViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.shared_temporary = tempfile.TemporaryDirectory()
        cls.shared_root = Path(cls.shared_temporary.name)
        cls.open_demo = cls.shared_root / "open-demo"
        release_core.export_open_demo(cls.open_demo, actor="Static View Fixture")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.shared_temporary.cleanup()

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def build(self, name: str = "view", **kwargs: object) -> Path:
        output = self.root / name
        view_core.build_static_view([self.open_demo], output, **kwargs)
        return output

    def test_build_is_offline_deterministic_exact_and_verifiable(self) -> None:
        first = self.build("first")
        second = self.build("second")

        self.assertEqual(tree_bytes(first), tree_bytes(second))
        self.assertEqual(
            {path.relative_to(first).as_posix() for path in first.rglob("*") if path.is_dir()},
            {"data", "data/evidence"},
        )
        self.assertEqual(
            set(tree_bytes(first)),
            {
                "CHECKSUMS.sha256",
                "VIEW_BOUNDARY.md",
                "VIEW_MANIFEST.json",
                "data/CASE_REGISTRY.json",
                "index.html",
                "style.css",
            },
        )
        result = view_core.verify_static_view(first)
        self.assertEqual(result["integrity_status"], "pass")
        self.assertEqual(result["privacy_classification"], "open-demo-only-offline")
        self.assertEqual(result["scientific_correctness"], "not_assessed")
        html = (first / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("<script", html.casefold())
        self.assertNotIn("href=\"http", html.casefold())
        self.assertNotIn("src=", html.casefold())
        self.assertIn("default-src &#x27;none&#x27;", html)
        self.assertIn("font-src &#x27;none&#x27;", html)
        self.assertIn("Apache-2.0", html)

        if os.name == "posix":
            for path in [first, *(item for item in first.rglob("*") if item.is_dir())]:
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700)
            for path in (item for item in first.rglob("*") if item.is_file()):
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_requires_at_least_one_open_demo_and_refuses_existing_or_repo_output(self) -> None:
        with self.assertRaisesRegex(view_core.ViewError, "at least one"):
            view_core.build_static_view([], self.root / "none")

        existing = self.root / "existing"
        existing.mkdir()
        sentinel = existing / "keep.txt"
        sentinel.write_text("keep", encoding="utf-8")
        with self.assertRaisesRegex(view_core.ViewError, "overwrite|existing"):
            view_core.build_static_view([self.open_demo], existing)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")

        repo_output = ROOT / "phase4-view-must-not-exist"
        with self.assertRaisesRegex(view_core.ViewError, "outside"):
            view_core.build_static_view([self.open_demo], repo_output)
        self.assertFalse(repo_output.exists())

    def test_role_package_and_blind_staging_are_rejected_before_payload_walk(self) -> None:
        role = self.root / "challenge"
        role.mkdir()
        (role / "PACKAGE_MANIFEST.json").write_text(
            '{"manifest_type":"rcsl-role-package","package_role":"challenge"}\n',
            encoding="utf-8",
        )
        os.mkfifo(role / "payload-must-not-be-read")
        with self.assertRaisesRegex(view_core.ViewError, "role package|Blind"):
            view_core.build_static_view([role], self.root / "role-view")

        staging = self.root / "blind-staging"
        staging.mkdir()
        (staging / "CONTROL_MANIFEST.json").write_text("{}\n", encoding="utf-8")
        (staging / "challenge").mkdir()
        os.mkfifo(staging / "challenge" / "payload-must-not-be-read")
        with self.assertRaisesRegex(view_core.ViewError, "Blind staging"):
            view_core.build_static_view([staging], self.root / "staging-view")

        missing_manifest = self.root / "missing-manifest-staging"
        missing_manifest.mkdir()
        for name in ("challenge", "evaluator", "maintainer"):
            (missing_manifest / name).mkdir()
        with self.assertRaisesRegex(view_core.ViewError, "Blind staging"):
            view_core.build_static_view(
                [missing_manifest], self.root / "missing-manifest-view"
            )

        unclassified = self.root / "unclassified"
        unclassified.mkdir()
        with self.assertRaisesRegex(view_core.ViewError, "PACKAGE_MANIFEST"):
            view_core.build_static_view(
                [unclassified], self.root / "unclassified-view"
            )

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO regression requires POSIX")
    def test_manifest_fifo_and_regular_to_fifo_race_fail_without_blocking(self) -> None:
        fifo_root = self.root / "fifo-package"
        fifo_root.mkdir()
        os.mkfifo(fifo_root / "PACKAGE_MANIFEST.json")
        with self.assertRaisesRegex(view_core.ViewError, "regular file"):
            view_core._peek_release_manifest(fifo_root.resolve())

        race_root = self.root / "race-package"
        race_root.mkdir()
        manifest_path = race_root / "PACKAGE_MANIFEST.json"
        manifest_path.write_text(
            '{"manifest_type":"rcsl-open-demo-package"}\n', encoding="utf-8"
        )
        original_open = os.open
        swapped = False
        observed_flags = 0

        def swap_before_open(path: object, flags: int, *args: object, **kwargs: object) -> int:
            nonlocal swapped, observed_flags
            if path == "PACKAGE_MANIFEST.json" and not swapped:
                swapped = True
                observed_flags = flags
                manifest_path.unlink()
                os.mkfifo(manifest_path)
            return original_open(path, flags, *args, **kwargs)

        with mock.patch.object(os, "open", side_effect=swap_before_open):
            with self.assertRaisesRegex(view_core.ViewError, "regular file|changed"):
                view_core._peek_release_manifest(race_root.resolve())
        self.assertTrue(observed_flags & getattr(os, "O_NONBLOCK", 0))

    def test_open_registry_is_an_allowlist_without_actor_or_controlled_metadata(self) -> None:
        output = self.build()
        registry = json.loads(
            (output / "data" / "CASE_REGISTRY.json").read_text(encoding="utf-8")
        )
        serialized = json.dumps(registry, sort_keys=True).casefold()
        self.assertNotIn("declared_actor", serialized)
        self.assertNotIn("actor_authentication", serialized)
        self.assertNotIn('"reviewer":', serialized)
        self.assertNotIn("controlled", serialized)
        self.assertEqual(registry["cases"][0]["scientific_correctness"], "not_assessed")
        self.assertEqual(registry["cases"][0]["measurement_validity"], "not_assessed")
        self.assertEqual(registry["cases"][0]["release_mode"], "open-demo")
        self.assertIn("licenses", registry["cases"][0])
        self.assertIn("known_limitations", registry["cases"][0])
        self.assertIn("claims_not_made", registry["cases"][0])
        self.assertIn("package_manifest_sha256", registry["cases"][0])
        self.assertIn("package_checksums_sha256", registry["cases"][0])
        self.assertIn("package_file_count", registry["cases"][0])
        self.assertNotIn("created_at", registry["cases"][0])

    def test_one_case_version_cannot_bind_multiple_source_trees(self) -> None:
        changed = self.root / "changed-open-demo"
        shutil.copytree(self.open_demo, changed)
        readme = changed / release_core.OPEN_DEMO_SOURCE.name / "README.md"
        readme.write_text(
            readme.read_text(encoding="utf-8") + "\nA distinct retained source tree.\n",
            encoding="utf-8",
        )
        rebind_modified_open_demo(changed)
        with self.assertRaisesRegex(view_core.ViewError, "multiple source trees"):
            view_core.build_static_view(
                [self.open_demo, changed], self.root / "ambiguous-version"
            )

        output = self.build("registry-collision")
        registry_path = output / "data" / "CASE_REGISTRY.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        second = dict(registry["cases"][0])
        second["source_tree_sha256"] = "e" * 64
        second["package_manifest_sha256"] = "f" * 64
        registry["cases"].append(second)
        registry["cases"].sort(
            key=lambda record: (
                record["case_id"],
                record["case_version"],
                record["package_manifest_sha256"],
            )
        )
        registry_path.write_bytes(view_core._json_bytes(registry))
        manifest_path = output / "VIEW_MANIFEST.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["case_count"] = 2
        manifest_path.write_bytes(view_core._json_bytes(manifest))
        rewrite_view_controls(output)
        with self.assertRaisesRegex(view_core.ViewError, "multiple source trees"):
            view_core.verify_static_view(output)

    def test_audit_and_training_projection_is_useful_escaped_and_identity_redacted(self) -> None:
        project_root = str(self.root / "secret-project")
        workspace_root = str(self.root / "secret-workspace")
        audit_report = {
            "schema_version": 2,
            "validator_scope": "local_hash_chain_lifecycle_integrity_only",
            "report_status": "review-ready",
            "preflight": {"ok": True},
            "limitations": ["source limitation"],
            "verification": {
                "workspace": workspace_root,
                "project": {"root": project_root},
                "event_count": 3,
                "last_event_hash": "a" * 64,
            },
            "baseline": {
                "id": "baseline-1",
                "head": "b" * 40,
                "branch": "main",
                "captured_at": "2026-09-12T00:00:00Z",
                "actor": "Secret Owner",
                "reason": "reason",
            },
            "g0_gate": {
                "status": "approved",
                "reviewer": "Secret Reviewer",
                "actor": "Secret Owner",
                "rationale": "approved",
                "updated_at": "2026-09-12T00:00:00Z",
                "contract_sha256": "c" * 64,
            },
            "summary": {
                "finding_count": 1,
                "stale_finding_count": 0,
                "by_status": {"open": 1},
                "by_layer": {"L1": 1},
                "by_competency": {"C1": 1},
                "by_severity": {"high": 1},
            },
            "findings": [
                {
                    "schema_version": 2,
                    "id": "F-1",
                    "title": "<script>alert('x')</script>",
                    "layer": "L1",
                    "competency": "C1",
                    "severity": "high",
                    "claim": f"Failure under {project_root}/model.py",
                    "first_broken_contract": "Metric contract",
                    "status": "open",
                    "actor": "Secret Auditor",
                    "created_at": "2026-09-12T00:00:00Z",
                    "updated_at": "2026-09-12T00:00:00Z",
                    "baseline_snapshot": {"project_root": project_root},
                    "baseline_state": "current",
                    "baseline_current": True,
                    "evidence": [
                        {
                            "id": "E-1",
                            "kind": "observed",
                            "reference": f"{workspace_root}/raw.txt",
                            "summary": "Observed <b>failure</b>",
                            "actor": "Secret Auditor",
                            "recorded_at": "2026-09-12T00:00:00Z",
                        }
                    ],
                }
            ],
        }
        training_status = {
            "workspace_type": "rcsl-training-progress",
            "case_id": view_core.training_core.CASE_ID,
            "case_revision": "d" * 64,
            "exposure_state": "open-demo-honor-isolation",
            "validator_scope": view_core.training_core.VALIDATOR_SCOPE,
            "overall_state": "in-progress",
            "next_recommended_target": "L1",
            "scientific_correctness": "not_assessed",
            "maturity_assessment": "human-only",
            "targets": {
                target: {
                    "attempt_state": "submitted" if target == "L1" else "not-submitted",
                    "structure_state": "complete" if target == "L1" else "incomplete",
                    "human_review_state": "needs-revision" if target == "L1" else "not-reviewed",
                    "maturity_assessment": "human-only",
                    "semantic_assessment": "not_performed",
                    "scientific_correctness": "not_assessed",
                    "attempt_count": 1 if target == "L1" else 0,
                    "latest_attempt_id": "L1-A001" if target == "L1" else None,
                    "latest_attempt_sha256": "e" * 64 if target == "L1" else None,
                    "draft_changes_since_submission": False,
                    "current_draft_state": "matches-latest-submission" if target == "L1" else "not-submitted",
                    "active_reviews": ([{
                        "review_id": "L1-R001",
                        "reviewer": "reviewer-1",
                        "decision": "revise",
                        "ratings": {
                            "Recognize": "demonstrated",
                            "Prove": "partial",
                            "Direct": "not-observed",
                            "Steward": "not-observed",
                        },
                        "gap_recorded": True,
                    }, {
                        "review_id": "L1-R002",
                        "reviewer": "reviewer-2",
                        "decision": "revise",
                        "ratings": {
                            "Recognize": "partial",
                            "Prove": "partial",
                            "Direct": "demonstrated",
                            "Steward": "not-observed",
                        },
                        "gap_recorded": True,
                    }] if target == "L1" else []),
                    "rating_disagreements": ({
                        "Recognize": ["demonstrated", "partial"],
                        "Direct": ["demonstrated", "not-observed"],
                    } if target == "L1" else {}),
                    "historical_review_count": 0,
                    "evidence_gap_count": 2 if target == "L1" else 0,
                }
                for target in ("L1", "L2", "L3", "L4", "capstone")
            },
            "privacy_note": "Learner labels and free-form review text are omitted.",
            "export_boundary": "No worksheet snapshots are exported.",
        }
        audit_input = self.root / "audit-input"
        training_input = self.root / "training-input"
        audit_input.mkdir()
        training_input.mkdir()
        with (
            mock.patch.object(view_core.audit_core, "build_report_data", return_value=audit_report),
            mock.patch.object(view_core.training_core, "get_redacted_status", return_value=training_status),
        ):
            output = self.build(
                audit_workspace=audit_input,
                training_workspace=training_input,
            )

        verification = view_core.verify_static_view(output)
        self.assertEqual(
            verification["privacy_classification"], "local-sensitive-not-deployable"
        )
        files = tree_bytes(output)
        audit_path = next(path for path in files if path.startswith("data/evidence/audit-"))
        training_path = next(path for path in files if path.startswith("data/evidence/training-"))
        audit_data = json.loads(files[audit_path])
        training_data = json.loads(files[training_path])
        combined = json.dumps([audit_data, training_data], sort_keys=True)
        self.assertNotIn("Secret Owner", combined)
        self.assertNotIn("Secret Reviewer", combined)
        self.assertNotIn("Secret Auditor", combined)
        self.assertNotIn(project_root, combined)
        self.assertNotIn(workspace_root, combined)
        self.assertNotIn('"actor"', combined)
        self.assertNotIn('"reviewer"', combined)
        self.assertEqual(audit_data["preflight_state"], "ready")
        self.assertNotIn("id", audit_data["baseline"])
        self.assertIn("source limitation", audit_data["limitations"])
        self.assertTrue(audit_data["findings"][0]["baseline_current"])
        self.assertEqual(
            training_data["targets"]["L1"]["declared_reviews"][0]["reviewer_alias"],
            "reviewer-1",
        )
        self.assertEqual(audit_data["findings"][0]["evidence"][0]["kind"], "observed")

        html = files["index.html"].decode("utf-8")
        self.assertIn("&lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt;", html)
        self.assertNotIn("<script>alert", html)
        self.assertIn("Observed &lt;b&gt;failure&lt;/b&gt;", html)
        self.assertIn("reviewer-1", html)
        self.assertIn("reviewer-2", html)
        self.assertIn("Prove=partial", html)
        self.assertLess(html.index("Recognize: demonstrated, partial"), html.index("Direct: demonstrated, not-observed"))

        training_tampered = self.root / "training-derived-tamper"
        shutil.copytree(output, training_tampered)
        inconsistent_training = json.loads(json.dumps(training_data))
        inconsistent_training["targets"]["L1"]["human_review_state"] = "human-passed"
        rewrite_evidence(training_tampered, "training", inconsistent_training)
        with self.assertRaisesRegex(view_core.ViewError, "review state"):
            view_core.verify_static_view(training_tampered)

        boundary_training = json.loads(json.dumps(training_data))
        boundary_record = boundary_training["targets"]["L1"]
        boundary_record["historical_review_count"] = 998
        boundary_record["declared_reviews"][0]["review_id"] = "L1-R999"
        boundary_record["declared_reviews"][1]["review_id"] = "L1-R1000"
        view_core._validate_training_projection(boundary_training)

        audit_tampered = self.root / "audit-summary-tamper"
        shutil.copytree(output, audit_tampered)
        inconsistent_audit = json.loads(json.dumps(audit_data))
        inconsistent_audit["summary"]["by_severity"]["high"] = 0
        inconsistent_audit["summary"]["by_severity"]["low"] = 1
        rewrite_evidence(audit_tampered, "audit", inconsistent_audit)
        with self.assertRaisesRegex(view_core.ViewError, "summary"):
            view_core.verify_static_view(audit_tampered)

        stale_audit = json.loads(json.dumps(audit_data))
        stale_audit["report_status"] = "draft"
        stale_audit["findings"][0]["baseline_current"] = False
        stale_audit["findings"][0]["baseline_state"] = "stale"
        stale_audit["summary"]["stale_finding_count"] = 1
        view_core._validate_audit_projection(stale_audit)

        with mock.patch.object(view_core, "MAX_AUDIT_EVIDENCE", 0):
            with self.assertRaisesRegex(view_core.ViewError, "evidence limit"):
                view_core._validate_audit_projection(audit_data)

    def test_text_caps_count_utf8_bytes(self) -> None:
        with self.assertRaisesRegex(view_core.ViewError, "UTF-8"):
            view_core._require_text("界界", field="fixture", maximum=5)
        for reference in (
            " /private/secret.txt",
            "\n/etc/passwd",
            "\tfile:///private/secret.txt",
            "\\\\server\\share\\secret.txt",
        ):
            self.assertEqual(
                view_core._safe_reference(reference, roots=()),
                "[local-reference-redacted]",
            )

    def test_real_training_adapter_produces_a_redacted_local_sensitive_snapshot(self) -> None:
        workspace = self.root / "training-workspace"
        view_core.training_core.initialize_workspace(
            workspace, learner_label="Identity Must Not Leave Workspace"
        )
        output = self.build("training-view", training_workspace=workspace)
        result = view_core.verify_static_view(output)
        self.assertEqual(result["evidence_kinds"], ["training"])
        projection_path = next(
            path
            for path in output.glob("data/evidence/training-*.json")
        )
        serialized = projection_path.read_text(encoding="utf-8")
        self.assertNotIn("Identity Must Not Leave Workspace", serialized)
        self.assertNotIn('"learner_label"', serialized)
        self.assertEqual(
            result["privacy_classification"],
            view_core.LOCAL_PRIVACY_CLASSIFICATION,
        )
        if hasattr(os, "mkfifo"):
            (workspace / view_core.training_core.PROGRESS_FILENAME).unlink()
            os.mkfifo(workspace / view_core.training_core.PROGRESS_FILENAME)
            with self.assertRaisesRegex(view_core.ViewError, "regular file"):
                self.build("training-fifo-view", training_workspace=workspace)

    def test_real_audit_adapter_keeps_findings_local_and_removes_machine_paths(self) -> None:
        project = self.root / "audited-project"
        project.mkdir()
        for arguments in (
            ("init",),
            ("add", "README.md"),
            (
                "-c",
                "user.name=Static View Test",
                "-c",
                "user.email=view@example.invalid",
                "commit",
                "-m",
                "fixture",
            ),
        ):
            if arguments == ("add", "README.md"):
                (project / "README.md").write_text("# Audit fixture\n", encoding="utf-8")
            result = subprocess.run(
                ("git", "-C", str(project), *arguments),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
        workspace = self.root / "audit-workspace"
        workspace.mkdir()
        (workspace / "audit-workspace.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "workspace_type": "rcsl-public-audit-workspace",
                    "validator_scope": "structural_only",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        for filename in view_core.audit_core.PUBLIC_TEMPLATE_FILENAMES:
            (workspace / filename).write_text(
                "# Public fixture\n\n{{fill_this_in}}\n", encoding="utf-8"
            )
        view_core.audit_core.bind_audit(
            project,
            workspace,
            actor="Identity Must Stay Local",
            rationale="Bind a clean fixture for a read-only view.",
        )

        with mock.patch.object(
            view_core.audit_core,
            "_verified_audit_snapshot",
            wraps=view_core.audit_core._verified_audit_snapshot,
        ) as snapshot:
            output = self.build("audit-view", audit_workspace=workspace)
        self.assertEqual(snapshot.call_count, 1)
        result = view_core.verify_static_view(output)
        self.assertEqual(result["evidence_kinds"], ["audit"])
        projection_path = next(output.glob("data/evidence/audit-*.json"))
        serialized = projection_path.read_text(encoding="utf-8")
        self.assertNotIn("Identity Must Stay Local", serialized)
        self.assertNotIn(str(project.resolve()), serialized)
        self.assertNotIn(str(workspace.resolve()), serialized)
        self.assertNotIn('"actor"', serialized)
        self.assertNotIn('"reviewer"', serialized)

        metadata = json.loads(
            (workspace / view_core.audit_core.WORKSPACE_METADATA_NAME).read_text(
                encoding="utf-8"
            )
        )
        lifecycle = metadata["audit_lifecycle"]
        baseline = lifecycle["baseline"]
        project_record = lifecycle["project"]
        injected_path = workspace / view_core.audit_core.FINDINGS_DIRECTORY_NAME / "INJECTED.json"
        injected_finding = {
            "schema_version": view_core.audit_core.SCHEMA_VERSION,
            "id": "INJECTED",
            "title": "Injected between adapter passes",
            "layer": "L1",
            "competency": "C1",
            "severity": "low",
            "claim": "This unlogged finding must never reach the projection.",
            "first_broken_contract": "Single verified snapshot",
            "status": "open",
            "actor": "Attacker",
            "created_at": baseline["captured_at"],
            "updated_at": baseline["captured_at"],
            "baseline_snapshot": {
                "project_root": project_record["root"],
                "id": baseline["id"],
                "head": baseline["head"],
                "branch": baseline["branch"],
                "captured_at": baseline["captured_at"],
            },
            "evidence": [],
        }
        original_load_findings = view_core.audit_core._load_findings

        def inject_then_restore(root: Path) -> list[dict[str, object]]:
            injected_path.write_text(
                json.dumps(injected_finding) + "\n", encoding="utf-8"
            )
            try:
                return original_load_findings(root)
            finally:
                injected_path.unlink(missing_ok=True)

        with mock.patch.object(
            view_core.audit_core,
            "_load_findings",
            side_effect=inject_then_restore,
        ):
            with self.assertRaisesRegex(view_core.ViewError, "no lifecycle hash event"):
                self.build("audit-injected-race-view", audit_workspace=workspace)
        self.assertFalse(injected_path.exists())

        if hasattr(os, "mkfifo"):
            event_path = workspace / view_core.audit_core.EVENT_LOG_NAME
            original_preflight = view_core._preflight_audit_workspace_limits

            def swap_event_after_preflight(root: Path) -> None:
                original_preflight(root)
                event_path.unlink()
                os.mkfifo(event_path)

            with mock.patch.object(
                view_core,
                "_preflight_audit_workspace_limits",
                side_effect=swap_event_after_preflight,
            ):
                with self.assertRaisesRegex(view_core.ViewError, "regular event log"):
                    self.build("audit-fifo-race-view", audit_workspace=workspace)

    def test_audit_event_line_count_is_bounded_before_list_growth(self) -> None:
        workspace = self.root / "event-count-workspace"
        workspace.mkdir()
        (workspace / view_core.audit_core.EVENT_LOG_NAME).write_text(
            "{}\n{}\n", encoding="utf-8"
        )
        with mock.patch.object(view_core.audit_core, "MAX_EVENTS", 1):
            with self.assertRaisesRegex(view_core.audit_core.AuditError, "event limit"):
                view_core.audit_core._read_events(workspace, allow_missing=False)

    def test_build_does_not_execute_package_code_or_use_network(self) -> None:
        marker = self.root / "ran.txt"
        malicious = self.root / "open-demo-copy"
        shutil.copytree(self.open_demo, malicious)
        payload = malicious / "LLM4SBR_research_audit_training_v2" / "view_guard.py"
        payload.write_text(f"from pathlib import Path\nPath({str(marker)!r}).touch()\n")
        with mock.patch.object(subprocess, "run", side_effect=AssertionError("process execution")):
            with self.assertRaisesRegex(view_core.ViewError, "verification failed"):
                view_core.build_static_view(
                    [malicious], self.root / "invalid-no-exec"
                )
            output = self.root / "valid-no-exec"
            view_core.build_static_view([self.open_demo], output)
        self.assertFalse(marker.exists())
        self.assertTrue(output.exists())

    def test_resource_caps_fail_before_unbounded_work(self) -> None:
        with self.assertRaisesRegex(view_core.ViewError, "at most"):
            view_core.build_static_view(
                [self.open_demo] * (view_core.MAX_OPEN_DEMOS + 1),
                self.root / "too-many-inputs",
            )

        output = self.build("too-many-files")
        for index in range(view_core.MAX_VIEW_FILES + 1):
            extra = output / f"extra-{index:02d}.txt"
            extra.write_text("bounded\n", encoding="utf-8")
            extra.chmod(0o600)
        with self.assertRaisesRegex(view_core.ViewError, "file limit"):
            view_core.verify_static_view(output)

        hostile_root = self.root / "hostile-root"
        hostile_root.mkdir()
        for index in range(view_core.MAX_RELEASE_ROOT_ENTRIES + 1):
            (hostile_root / f"entry-{index:04d}").touch()
        fd_directory = Path("/dev/fd")
        before = len(list(fd_directory.iterdir())) if fd_directory.is_dir() else None
        with self.assertRaisesRegex(view_core.ViewError, "entry safety limit"):
            view_core._peek_release_manifest(hostile_root.resolve())
        after = len(list(fd_directory.iterdir())) if fd_directory.is_dir() else None
        if before is not None and after is not None:
            self.assertLessEqual(after, before)

    def test_verifier_rejects_tampering_extra_directories_symlinks_and_modes(self) -> None:
        tampered = self.build("tampered")
        (tampered / "index.html").write_text("tampered\n", encoding="utf-8")
        with self.assertRaisesRegex(view_core.ViewError, "checksum|manifest"):
            view_core.verify_static_view(tampered)

        extra = self.build("extra")
        (extra / "empty-extra").mkdir()
        (extra / "empty-extra").chmod(0o700)
        with self.assertRaisesRegex(view_core.ViewError, "directory inventory"):
            view_core.verify_static_view(extra)

        linked = self.build("linked")
        (linked / "style.css").unlink()
        (linked / "style.css").symlink_to(self.root / "outside.css")
        with self.assertRaisesRegex(view_core.ViewError, "symlink"):
            view_core.verify_static_view(linked)

        if os.name == "posix":
            wrong_mode = self.build("wrong-mode")
            (wrong_mode / "index.html").chmod(0o644)
            with self.assertRaisesRegex(view_core.ViewError, "mode"):
                view_core.verify_static_view(wrong_mode)

    def test_verifier_rejects_rehashed_html_or_schema_instead_of_trusting_checksums(self) -> None:
        html_view = self.build("html-schema")
        (html_view / "index.html").write_text(
            "<!doctype html><script src=\"https://example.invalid/x.js\"></script>\n",
            encoding="utf-8",
        )
        rewrite_view_controls(html_view)
        with self.assertRaisesRegex(view_core.ViewError, "rendered HTML"):
            view_core.verify_static_view(html_view)

        schema_view = self.build("manifest-schema")
        manifest_path = schema_view / "VIEW_MANIFEST.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["schema_version"] = True
        manifest_path.write_bytes(view_core._json_bytes(manifest))
        rewrite_view_controls(schema_view)
        with self.assertRaisesRegex(view_core.ViewError, "schema version"):
            view_core.verify_static_view(schema_view)

        canonical_view = self.build("noncanonical-json")
        registry_path = canonical_view / "data" / "CASE_REGISTRY.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        registry_path.write_text(
            json.dumps(registry, separators=(",", ":")), encoding="utf-8"
        )
        rewrite_view_controls(canonical_view)
        with self.assertRaisesRegex(view_core.ViewError, "not canonical"):
            view_core.verify_static_view(canonical_view)

    def test_verifier_rechecks_file_bytes_and_nested_directory_identities(self) -> None:
        atomic_file = self.build("atomic-file-swap")
        replacement = self.root / "replacement.html"
        replacement.write_text("<script>unverified()</script>\n", encoding="utf-8")
        replacement.chmod(0o600)
        original_render = view_core._render_html

        def swap_file(*args: object, **kwargs: object) -> bytes:
            os.replace(replacement, atomic_file / "index.html")
            return original_render(*args, **kwargs)

        with mock.patch.object(view_core, "_render_html", side_effect=swap_file):
            with self.assertRaisesRegex(view_core.ViewError, "identity changed"):
                view_core.verify_static_view(atomic_file)

        restored_metadata = self.build("same-metadata-byte-swap")
        index_path = restored_metadata / "index.html"
        original_bytes = index_path.read_bytes()
        original_stat = index_path.stat()

        def mutate_and_restore_metadata(*args: object, **kwargs: object) -> bytes:
            with index_path.open("r+b") as handle:
                handle.write(b"X")
            os.utime(
                index_path,
                ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns),
            )
            return original_render(*args, **kwargs)

        with mock.patch.object(
            view_core, "_render_html", side_effect=mutate_and_restore_metadata
        ):
            with self.assertRaisesRegex(view_core.ViewError, "identity changed"):
                view_core.verify_static_view(restored_metadata)
        self.assertEqual(index_path.stat().st_ino, original_stat.st_ino)
        self.assertEqual(index_path.stat().st_size, len(original_bytes))

        atomic_directory = self.build("atomic-directory-swap")
        moved_data = atomic_directory / "data-original"

        def swap_directory(*args: object, **kwargs: object) -> bytes:
            (atomic_directory / "data").rename(moved_data)
            (atomic_directory / "data").mkdir(mode=0o700)
            return original_render(*args, **kwargs)

        with mock.patch.object(view_core, "_render_html", side_effect=swap_directory):
            with self.assertRaisesRegex(
                view_core.ViewError, "identity changed|entries changed"
            ):
                view_core.verify_static_view(atomic_directory)

    def test_output_identity_change_fails_closed_without_deleting_replacement(self) -> None:
        output = self.root / "swapped"
        moved = self.root / "owned-moved"
        original_write = view_core._write_view_tree

        def swap_after_write(owned: release_core.OwnedOutput, files: dict[str, bytes]) -> None:
            original_write(owned, files)
            output.rename(moved)
            output.mkdir()
            (output / "attacker-sentinel.txt").write_text("keep", encoding="utf-8")

        with mock.patch.object(view_core, "_write_view_tree", side_effect=swap_after_write):
            with self.assertRaisesRegex(view_core.ViewError, "identity"):
                view_core.build_static_view([self.open_demo], output)
        self.assertEqual(
            (output / "attacker-sentinel.txt").read_text(encoding="utf-8"), "keep"
        )

        observed_borrowed_descriptors: list[int] = []
        original_collect = view_core._collect_view_tree

        def observe_owned_collection(
            root: object, **kwargs: object
        ) -> view_core._FrozenView:
            descriptor = kwargs.get("borrowed_descriptor")
            self.assertIsInstance(descriptor, int)
            observed_borrowed_descriptors.append(int(descriptor))
            return original_collect(root, **kwargs)

        with mock.patch.object(
            view_core, "_collect_view_tree", side_effect=observe_owned_collection
        ):
            self.build("owned-fd-self-verification")
        self.assertEqual(len(observed_borrowed_descriptors), 1)

        clean_replacement = self.build("clean-path-replacement")
        attacked_output = self.root / "owned-index-attack"
        moved_owned = self.root / "owned-index-attack-moved"
        original_owned_verify = view_core._verify_owned_static_view

        def swap_tamper_restore(
            owned: release_core.OwnedOutput,
        ) -> dict[str, object]:
            attacked_output.rename(moved_owned)
            clean_replacement.rename(attacked_output)
            (moved_owned / "index.html").write_text(
                "<script>tampered-owned-index()</script>\n", encoding="utf-8"
            )
            (moved_owned / "index.html").chmod(0o600)
            try:
                return original_owned_verify(owned)
            finally:
                attacked_output.rename(clean_replacement)
                moved_owned.rename(attacked_output)

        with mock.patch.object(
            view_core, "_verify_owned_static_view", side_effect=swap_tamper_restore
        ):
            with self.assertRaisesRegex(view_core.ViewError, "identity|checksum"):
                view_core.build_static_view([self.open_demo], attacked_output)
        self.assertIn(
            "tampered-owned-index",
            (attacked_output / "index.html").read_text(encoding="utf-8"),
        )

    def test_parent_swap_fails_before_creation_and_failed_cleanup_is_nonrecursive(self) -> None:
        parent = self.root / "output-parent"
        parent.mkdir()
        moved_parent = self.root / "output-parent-original"
        output = parent / "view"
        original_verified = view_core._verified_open_demo

        def swap_parent(bundle: object) -> object:
            verified = original_verified(bundle)
            parent.rename(moved_parent)
            parent.symlink_to(self.open_demo, target_is_directory=True)
            return verified

        with mock.patch.object(view_core, "_verified_open_demo", side_effect=swap_parent):
            with self.assertRaisesRegex(view_core.ViewError, "parent identity"):
                view_core.build_static_view([self.open_demo], output)
        self.assertFalse((self.open_demo / "view").exists())

        partial = self.root / "partial-with-replaced-child"
        moved_data = self.root / "builder-data-original"
        original_write = view_core._write_view_tree

        def replace_child_then_fail(
            owned: release_core.OwnedOutput, files: dict[str, bytes]
        ) -> None:
            original_write(owned, files)
            (partial / "data").rename(moved_data)
            (partial / "data").mkdir(mode=0o700)
            (partial / "data" / "attacker-sentinel.txt").write_text(
                "keep", encoding="utf-8"
            )
            raise view_core.ViewError("forced post-write failure")

        with mock.patch.object(view_core, "_write_view_tree", side_effect=replace_child_then_fail):
            with self.assertRaisesRegex(view_core.ViewError, "forced"):
                view_core.build_static_view([self.open_demo], partial)
        self.assertEqual(
            (partial / "data" / "attacker-sentinel.txt").read_text(encoding="utf-8"),
            "keep",
        )

    def test_open_demo_root_swap_after_peek_never_traverses_replacement(self) -> None:
        package = self.root / "open-demo-race"
        shutil.copytree(self.open_demo, package)
        original_package = self.root / "open-demo-race-original"
        original_verify = release_core._verify_checksum_tree_at

        def swap_before_freeze(root: object, **kwargs: object) -> dict[str, object]:
            self.assertIsInstance(root, int)
            package.rename(original_package)
            package.mkdir()
            (package / "PACKAGE_MANIFEST.json").write_text(
                '{"manifest_type":"rcsl-role-package","package_role":"maintainer"}\n',
                encoding="utf-8",
            )
            os.mkfifo(package / "payload-must-not-be-read")
            return original_verify(root, **kwargs)

        with mock.patch.object(
            release_core, "_verify_checksum_tree_at", side_effect=swap_before_freeze
        ):
            with self.assertRaisesRegex(view_core.ViewError, "identity changed"):
                view_core.build_static_view([package], self.root / "root-swap-view")

    def test_classified_root_controls_are_rechecked_before_any_descent(self) -> None:
        mutations = ("missing-manifest", "manifest-directory", "readiness-marker")
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                package = self.root / f"classified-{mutation}"
                shutil.copytree(self.open_demo, package)
                original_verify = release_core._verify_checksum_tree_at
                original_read = release_core._read_regular_file_at
                reads_after_mutation: list[str] = []

                def mutate_then_verify(
                    descriptor: int, **kwargs: object
                ) -> dict[str, object]:
                    manifest = package / "PACKAGE_MANIFEST.json"
                    if mutation == "missing-manifest":
                        manifest.unlink()
                        nested = package / "ordinary"
                    elif mutation == "manifest-directory":
                        manifest.unlink()
                        nested = manifest
                    else:
                        (package / "readiness-workspace.json").write_text(
                            "{}\n", encoding="utf-8"
                        )
                        nested = package / "controlled-records"
                    nested.mkdir()
                    (nested / "synthetic-payload.txt").write_text(
                        "must not be read\n", encoding="utf-8"
                    )
                    reads_after_mutation.clear()
                    return original_verify(descriptor, **kwargs)

                def observe_read(
                    descriptor: int, name: str, **kwargs: object
                ) -> bytes:
                    reads_after_mutation.append(str(kwargs.get("label", name)))
                    return original_read(descriptor, name, **kwargs)

                with mock.patch.object(
                    release_core,
                    "_verify_checksum_tree_at",
                    side_effect=mutate_then_verify,
                ), mock.patch.object(
                    release_core, "_read_regular_file_at", side_effect=observe_read
                ):
                    with self.assertRaisesRegex(
                        view_core.ViewError, "root control file|forbidden root marker"
                    ):
                        view_core.build_static_view(
                            [package], self.root / f"classified-{mutation}-view"
                        )
                self.assertFalse(
                    any("synthetic-payload" in label for label in reads_after_mutation)
                )

    def test_protected_input_and_output_overlap_are_refused(self) -> None:
        protected = self.root / "DO_NOT_OPEN_UNTIL_FINISHED" / "bundle"
        protected.mkdir(parents=True)
        with self.assertRaisesRegex(view_core.ViewError, "protected"):
            view_core.build_static_view([protected], self.root / "protected-view")

        protected_output = (
            self.root / "DO_NOT_OPEN_UNTIL_FINISHED" / "view-must-not-exist"
        )
        with self.assertRaisesRegex(view_core.ViewError, "protected"):
            view_core.build_static_view([self.open_demo], protected_output)
        self.assertFalse(protected_output.exists())

        inside_bundle = self.open_demo / "view-must-not-exist"
        with self.assertRaisesRegex(view_core.ViewError, "overlap"):
            view_core.build_static_view([self.open_demo], inside_bundle)
        self.assertFalse(inside_bundle.exists())


if __name__ == "__main__":
    unittest.main()
