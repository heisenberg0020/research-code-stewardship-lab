"""Phase 3A tests for honest Open Demo and separated Blind packaging."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from stewardship_lab import release as release_core


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "rcsl.py"
ZERO_DIGEST = "0" * 64
ROLES = ("challenge", "evaluator", "maintainer")
SENSITIVITY = {
    "challenge": "public",
    "evaluator": "controlled-evaluator",
    "maintainer": "controlled-maintainer",
}


def run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def root_digest(entries: list[dict[str, object]]) -> str:
    records = [
        {
            "path": entry["path"],
            "sha256": entry["sha256"],
            "size": entry["size"],
            "executable": entry["executable"],
        }
        for entry in entries
    ]
    records.sort(key=lambda item: str(item["path"]))
    encoded = json.dumps(
        records,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return sha256(encoded)


def rewrite_package_checksums(package: Path) -> bytes:
    lines = []
    for path in sorted(item for item in package.rglob("*") if item.is_file()):
        relative = path.relative_to(package).as_posix()
        if relative == "CHECKSUMS.sha256":
            continue
        lines.append(f"{sha256(path.read_bytes())}  {relative}")
    data = ("\n".join(lines) + "\n").encode("utf-8")
    (package / "CHECKSUMS.sha256").write_bytes(data)
    return data


def write_json(path: Path, payload: object) -> bytes:
    data = (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    path.write_bytes(data)
    return data


def run_standalone(package: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(package / "verify_package.py")],
        cwd=package,
        capture_output=True,
        text=True,
        check=False,
    )


def refresh_manifest_payload_record(package: Path, relative: str) -> dict[str, object]:
    manifest_path = package / "PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload_path = package / relative
    records = [record for record in manifest["files"] if record["path"] == relative]
    if len(records) != 1:
        raise AssertionError(f"expected one manifest record for {relative}")
    records[0]["sha256"] = sha256(payload_path.read_bytes())
    records[0]["size"] = payload_path.stat().st_size
    write_json(manifest_path, manifest)
    rewrite_package_checksums(package)
    return manifest


class PackageParityAssertions:
    def assert_rejected_by_main_and_standalone(
        self: unittest.TestCase,
        package: Path,
        *,
        main_message: str | None = None,
        standalone_message: str | None = None,
    ) -> None:
        if main_message is None:
            with self.assertRaises(release_core.ReleaseError):
                release_core.verify_export(package)
        else:
            with self.assertRaisesRegex(release_core.ReleaseError, main_message):
                release_core.verify_export(package)
        result = run_standalone(package)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("Traceback", result.stderr)
        if standalone_message is not None:
            self.assertIn(standalone_message, result.stderr)


class BlindFixture:
    """A wholly synthetic, never-public three-root fixture outside the repo."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.guard_marker = root / "package-code-ran.txt"
        self.sources = {role: root / f"{role}-source" for role in ROLES}
        self.payloads: dict[str, dict[str, bytes]] = {
            "challenge": {
                "LICENSE": b"Synthetic test license\n",
                "README.md": b"# Synthetic challenge\n\nInspect the public result contract.\n",
                "run.sh": b"#!/bin/sh\nprintf '%s\\n' 'synthetic challenge'\n",
                "task.json": b'{"case":"synthetic","submission":"result.json"}\n',
            },
            "evaluator": {
                "LICENSE": b"Synthetic test license\n",
                "grade.py": (
                    b"from __future__ import annotations\n\n"
                    b"def grade(value: int) -> bool:\n    return value == 7\n"
                ),
                "execution_guard.py": (
                    b"import os\nfrom pathlib import Path\n"
                    b"Path(os.environ['RCSL_GUARD_MARKER']).write_text('executed')\n"
                ),
            },
            "maintainer": {
                "LICENSE": b"Synthetic test license\n",
                "DESIGN.md": b"# Controlled design record\n\nSynthetic fixture only.\n",
            },
        }
        for role, source in self.sources.items():
            source.mkdir()
            for relative, data in self.payloads[role].items():
                destination = source / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
                if role == "challenge" and relative == "run.sh":
                    destination.chmod(0o700)
        self.manifest = self._manifest()
        self.manifest_path = root / "BLIND_SOURCE.input.json"
        self.write_manifest()

    def _entries(self, role: str) -> list[dict[str, object]]:
        return [
            {
                "path": relative,
                "sha256": sha256(data),
                "size": len(data),
                "executable": bool(
                    (self.sources[role] / relative).stat().st_mode & 0o111
                ),
                "role": role,
                "license_id": "synthetic-license",
                "sensitivity": SENSITIVITY[role],
            }
            for relative, data in sorted(self.payloads[role].items())
        ]

    def _manifest(self) -> dict[str, object]:
        package_files = {role: self._entries(role) for role in ROLES}
        return {
            "schema_version": 1,
            "manifest_type": "rcsl-blind-source",
            "release_id": "synthetic-release-001",
            "case_id": "synthetic/case-001",
            "case_version": "1.0.0",
            "release_mode": "blind-challenge",
            "created_at": "2026-09-12T00:00:00Z",
            "novelty_attestation": {
                "state": "human-declared-never-public",
                "reviewer": "Synthetic Fixture Reviewer",
                "reviewed_at": "2026-09-12T00:00:00Z",
                "evidence_refs": ["fixture://novelty-review"],
            },
            "source_bindings": {
                role: {
                    "revision": f"synthetic-{role}-revision",
                    "revision_type": "content-digest",
                    "clean_state": "human-declared-clean",
                    "root_digest": root_digest(package_files[role]),
                }
                for role in ROLES
            },
            "package_files": package_files,
            "licenses": [
                {
                    "id": "synthetic-license",
                    "terms": "Synthetic fixture terms",
                    "redistribution": "allowed",
                    "notice_path": "LICENSE",
                    "approval_ref": "fixture://license-review",
                }
            ],
            "scoring": {
                "protocol_id": "synthetic-score-v1",
                "version": "1.0.0",
                "digest": sha256(b"synthetic frozen scoring protocol"),
                "automatic_scope": "Schema and exact synthetic output checks only.",
                "human_gate": "A human reviews meaning and claim boundaries.",
                "independent_reviewer_ref": "fixture://scoring-review",
            },
            "isolation": {
                "challenge_audience": "Synthetic learner allowlist.",
                "evaluator_audience": "Synthetic evaluator allowlist.",
                "maintainer_audience": "Synthetic maintainer allowlist.",
                "access_plan_ref": "fixture://access-plan",
                "submission_channel_ref": "fixture://submission-channel",
            },
            "validation": {
                "public_record_refs": ["fixture://public-validation"],
                "controlled_record_refs": ["fixture://controlled-validation"],
                "leakage_review_ref": "fixture://leakage-review",
                "repeatability_review_ref": "fixture://repeatability-review",
            },
            "withdrawal": {
                "owner_label": "Synthetic Withdrawal Owner",
                "contact_or_process_ref": "fixture://withdrawal-process",
                "triggers": ["answer leakage", "integrity failure"],
                "procedure_ref": "fixture://revocation-procedure",
            },
            "claims_not_made": [
                "This synthetic package proves scientific correctness.",
                "Local staging enforces remote access control.",
            ],
            "human_approvals": [
                {
                    "gate": gate,
                    "reviewer": f"Synthetic {gate} reviewer",
                    "reviewed_at": "2026-09-12T00:00:00Z",
                    "rationale": f"Synthetic evidence-bound {gate} decision.",
                    "evidence_refs": [f"fixture://{gate}-approval"],
                }
                for gate in release_core.APPROVAL_GATES
            ],
        }

    def write_manifest(self, manifest: dict[str, object] | None = None) -> Path:
        self.manifest_path.write_text(
            json.dumps(
                self.manifest if manifest is None else manifest,
                indent=2,
                sort_keys=True,
                ensure_ascii=True,
            )
            + "\n",
            encoding="utf-8",
        )
        if os.name == "posix":
            self.manifest_path.chmod(0o600)
        return self.manifest_path

    def package(self, output_name: str = "private-staging") -> Path:
        output = self.root / output_name
        with mock.patch.dict(
            os.environ, {"RCSL_GUARD_MARKER": str(self.guard_marker)}
        ):
            release_core.package_blind(
                self.manifest_path,
                challenge_source=self.sources["challenge"],
                evaluator_source=self.sources["evaluator"],
                maintainer_source=self.sources["maintainer"],
                output=output,
                actor="Synthetic Builder",
            )
        return output


class OpenDemoReleaseTests(PackageParityAssertions, unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_export_is_explicitly_open_demo_verifiable_and_excludes_isolated_tree(self) -> None:
        bundle = self.root / "open-demo"
        result = run_cli(
            "export",
            "open-demo",
            "--output",
            str(bundle),
            "--actor",
            "Test Builder",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("HISTORICALLY PUBLIC", result.stdout)

        manifest = json.loads(
            (bundle / "PACKAGE_MANIFEST.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["release_mode"], "open-demo")
        self.assertEqual(
            manifest["exposure_state"], "historically-public-honor-isolation"
        )
        self.assertEqual(manifest["scientific_correctness"], "not_assessed")
        self.assertFalse(
            any(
                part.casefold() == release_core.ISOLATED_DIRECTORY_NAME.casefold()
                for path in bundle.rglob("*")
                for part in path.relative_to(bundle).parts
            )
        )
        validation = json.loads(
            (bundle / "VALIDATION_RECORD.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            validation["validated_source_tree_sha256"], manifest["source_tree_sha256"]
        )
        self.assertEqual(validation["records"][0]["outcome"], "passed")
        self.assertEqual(validation["records"][1]["outcome"], "not-run")

        verify = run_cli("export", "verify", str(bundle), "--json")
        self.assertEqual(verify.returncode, 0, verify.stderr)
        self.assertEqual(json.loads(verify.stdout)["integrity_status"], "pass")
        standalone = subprocess.run(
            [sys.executable, str(bundle / "verify_package.py")],
            cwd=bundle,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(standalone.returncode, 0, standalone.stderr)
        self.assertIn("retained bytes only", standalone.stdout)

        invalid_validation_bundle = self.root / "open-demo-invalid-validation"
        shutil.copytree(bundle, invalid_validation_bundle)
        validation_path = invalid_validation_bundle / "VALIDATION_RECORD.json"
        invalid_validation = json.loads(validation_path.read_text(encoding="utf-8"))
        invalid_validation["environment"] = {}
        invalid_validation["records"] = [{"invented": "PASS"}]
        validation_path.write_text(
            json.dumps(invalid_validation, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        invalid_manifest_path = invalid_validation_bundle / "PACKAGE_MANIFEST.json"
        invalid_manifest = json.loads(
            invalid_manifest_path.read_text(encoding="utf-8")
        )
        for record in invalid_manifest["files"]:
            if record["path"] == "VALIDATION_RECORD.json":
                record["sha256"] = sha256(validation_path.read_bytes())
                record["size"] = validation_path.stat().st_size
        invalid_manifest_path.write_text(
            json.dumps(invalid_manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        rewrite_package_checksums(invalid_validation_bundle)
        bad_standalone = subprocess.run(
            [sys.executable, str(invalid_validation_bundle / "verify_package.py")],
            cwd=invalid_validation_bundle,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(bad_standalone.returncode, 0)
        self.assertIn("validation environment", bad_standalone.stderr)
        with self.assertRaisesRegex(release_core.ReleaseError, "environment"):
            release_core.verify_export(invalid_validation_bundle)

        readme = next(bundle.glob("LLM4SBR_research_audit_training_v2/README.md"))
        readme.write_text(readme.read_text(encoding="utf-8") + "\ntampered\n")
        with self.assertRaisesRegex(release_core.ReleaseError, "checksum mismatch"):
            release_core.verify_export(bundle)

    def test_open_demo_schema_and_validation_numeric_types_fail_closed(self) -> None:
        original = self.root / "open-demo-schema-base"
        release_core.export_open_demo(original, actor="Schema Test Builder")

        manifest_bool = self.root / "open-demo-manifest-bool"
        shutil.copytree(original, manifest_bool)
        manifest_path = manifest_bool / "PACKAGE_MANIFEST.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["schema_version"] = True
        write_json(manifest_path, manifest)
        rewrite_package_checksums(manifest_bool)
        self.assert_rejected_by_main_and_standalone(
            manifest_bool,
            main_message="schema version",
            standalone_message="Open Demo boundary",
        )

        validation_bool = self.root / "open-demo-validation-bool"
        shutil.copytree(original, validation_bool)
        validation_path = validation_bool / "VALIDATION_RECORD.json"
        validation = json.loads(validation_path.read_text(encoding="utf-8"))
        validation["schema_version"] = True
        write_json(validation_path, validation)
        refresh_manifest_payload_record(validation_bool, "VALIDATION_RECORD.json")
        self.assert_rejected_by_main_and_standalone(
            validation_bool,
            main_message="schema version",
            standalone_message="validation binding",
        )

        float_exit = self.root / "open-demo-float-exit"
        shutil.copytree(original, float_exit)
        validation_path = float_exit / "VALIDATION_RECORD.json"
        validation = json.loads(validation_path.read_text(encoding="utf-8"))
        validation["records"][0]["exit_code"] = 0.0
        write_json(validation_path, validation)
        refresh_manifest_payload_record(float_exit, "VALIDATION_RECORD.json")
        self.assert_rejected_by_main_and_standalone(
            float_exit,
            main_message="floating-point JSON",
        )

    def test_open_demo_rejects_non_object_manifest_and_rehashed_root_injection(self) -> None:
        original = self.root / "open-demo-object-base"
        release_core.export_open_demo(original, actor="Schema Test Builder")

        non_object = self.root / "open-demo-non-object"
        shutil.copytree(original, non_object)
        (non_object / "PACKAGE_MANIFEST.json").write_bytes(b"[]\n")
        rewrite_package_checksums(non_object)
        self.assert_rejected_by_main_and_standalone(
            non_object, main_message="one JSON object"
        )

        injected = self.root / "open-demo-root-injection"
        shutil.copytree(original, injected)
        extra_path = injected / "EXTRA.txt"
        extra_path.write_text("not an allowlisted Open Demo artifact\n", encoding="utf-8")
        manifest_path = injected / "PACKAGE_MANIFEST.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"].append(
            {
                "path": "EXTRA.txt",
                "sha256": sha256(extra_path.read_bytes()),
                "size": extra_path.stat().st_size,
            }
        )
        manifest["files"].sort(key=lambda record: record["path"])
        write_json(manifest_path, manifest)
        rewrite_package_checksums(injected)
        self.assert_rejected_by_main_and_standalone(
            injected,
            main_message="unbound non-source",
            standalone_message="unbound Open Demo non-source",
        )

    def test_open_demo_rejects_a_rehashed_verifier_replacement(self) -> None:
        bundle = self.root / "open-demo-verifier-replacement"
        release_core.export_open_demo(bundle, actor="Schema Test Builder")
        verifier = bundle / "verify_package.py"
        verifier.write_bytes(verifier.read_bytes() + b"\n# replaced after export\n")
        refresh_manifest_payload_record(bundle, "verify_package.py")
        with self.assertRaisesRegex(release_core.ReleaseError, "trusted verifier"):
            release_core.verify_export(bundle)

    def test_open_demo_license_notice_path_is_case_exact(self) -> None:
        bundle = self.root / "open-demo-license-path-case"
        release_core.export_open_demo(bundle, actor="Path Test Builder")
        manifest_path = bundle / "PACKAGE_MANIFEST.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["licenses"][0]["notice"], "LICENSE")
        manifest["licenses"][0]["notice"] = "license"
        write_json(manifest_path, manifest)
        rewrite_package_checksums(bundle)
        self.assert_rejected_by_main_and_standalone(bundle)

    def test_export_refuses_existing_and_repository_outputs_without_changes(self) -> None:
        existing = self.root / "existing"
        existing.mkdir()
        sentinel = existing / "keep.txt"
        sentinel.write_text("keep", encoding="utf-8")
        with self.assertRaisesRegex(release_core.ReleaseError, "overwrite"):
            release_core.export_open_demo(existing, actor="Builder")
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")

        in_repo = ROOT / "phase3-open-demo-must-not-exist"
        self.assertFalse(in_repo.exists())
        with self.assertRaisesRegex(release_core.ReleaseError, "outside"):
            release_core.export_open_demo(in_repo, actor="Builder")
        self.assertFalse(in_repo.exists())


class BlindPackageTests(PackageParityAssertions, unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.fixture = BlindFixture(self.root)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_shipped_manifest_template_is_current_but_not_directly_releasable(self) -> None:
        compile(
            release_core._standalone_verifier(),
            "<generated verify_package.py>",
            "exec",
        )
        template_path = (
            ROOT
            / "skills"
            / "research-code-audit-training"
            / "assets"
            / "blind-source-manifest-template.json"
        )
        template = json.loads(template_path.read_text(encoding="utf-8"))
        self.assertEqual(template["manifest_type"], "rcsl-blind-source")
        self.assertEqual(
            {record["gate"] for record in template["human_approvals"]},
            set(release_core.APPROVAL_GATES),
        )
        for role in ROLES:
            self.assertTrue(
                all(
                    isinstance(record["executable"], bool)
                    for record in template["package_files"][role]
                )
            )
        with self.assertRaisesRegex(release_core.ReleaseError, "placeholder"):
            release_core._validate_blind_manifest(template)

    def test_blind_manifest_must_stay_private_and_outside_the_public_repo(self) -> None:
        public_template = (
            ROOT
            / "skills"
            / "research-code-audit-training"
            / "assets"
            / "blind-source-manifest-template.json"
        )
        with self.assertRaisesRegex(release_core.ReleaseError, "outside the public"):
            release_core._load_blind_manifest(public_template)

        if os.name != "posix":
            return

        self.fixture.manifest_path.chmod(0o644)
        try:
            with self.assertRaisesRegex(
                release_core.ReleaseError, "group or other permissions"
            ):
                release_core._load_blind_manifest(self.fixture.manifest_path)
        finally:
            self.fixture.manifest_path.chmod(0o600)

        wide_parent = self.root / "wide-manifest-parent"
        wide_parent.mkdir(mode=0o700)
        private_manifest = wide_parent / "BLIND_SOURCE.input.json"
        shutil.copy2(self.fixture.manifest_path, private_manifest)
        private_manifest.chmod(0o600)
        wide_parent.chmod(0o755)
        try:
            with self.assertRaisesRegex(
                release_core.ReleaseError, "parent.*group or other permissions"
            ):
                release_core._load_blind_manifest(private_manifest)
        finally:
            wide_parent.chmod(0o700)

    def test_separated_staging_is_private_bound_and_never_executes_package_code(self) -> None:
        staging = self.fixture.package()
        self.assertEqual(stat.S_IMODE(staging.stat().st_mode), 0o700)
        self.assertFalse(self.fixture.guard_marker.exists())
        self.assertTrue((staging / "challenge" / "run.sh").stat().st_mode & 0o100)
        self.assertEqual(
            {path.name for path in staging.iterdir()},
            {"challenge", "evaluator", "maintainer", "CONTROL_MANIFEST.json", "BUILD_RECORD.json"},
        )
        result = release_core.verify_blind_staging(staging)
        self.assertEqual(result["integrity_status"], "pass")
        self.assertEqual(
            result["assembly_state"], "assembled-awaiting-controlled-placement"
        )
        self.assertEqual(result["operational_release"], "not_approved")

        challenge_manifest_path = staging / "challenge" / "PACKAGE_MANIFEST.json"
        challenge_manifest_data = challenge_manifest_path.read_bytes()
        challenge_manifest = json.loads(challenge_manifest_data)
        self.assertEqual(challenge_manifest["package_role"], "challenge")
        self.assertTrue(
            {
                "source_manifest_sha256",
                "challenge_manifest_sha256",
                "evaluator_manifest_sha256",
                "scoring_digest",
            }.isdisjoint(challenge_manifest)
        )
        control = json.loads(
            (staging / "CONTROL_MANIFEST.json").read_text(encoding="utf-8")
        )
        for controlled_role in ("evaluator", "maintainer"):
            self.assertNotIn(
                control["packages"][controlled_role]["manifest_sha256"].encode(),
                challenge_manifest_data,
            )

        isolated_challenge = self.root / "learner-receives-only-this"
        for role in ROLES:
            package = self.root / (
                "learner-receives-only-this"
                if role == "challenge"
                else f"isolated-valid-{role}"
            )
            shutil.copytree(staging / role, package)
            standalone = run_standalone(package)
            self.assertEqual(standalone.returncode, 0, standalone.stderr)
            self.assertIn("PACKAGE INTEGRITY: PASS", standalone.stdout)

        isolated_run = isolated_challenge / "run.sh"
        isolated_run.chmod(0o600)
        mode_check = subprocess.run(
            [sys.executable, str(isolated_challenge / "verify_package.py")],
            cwd=isolated_challenge,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(mode_check.returncode, 0)
        self.assertIn("source inventory record mismatch", mode_check.stderr)
        isolated_run.chmod(0o700)

        manifest_path = isolated_challenge / "PACKAGE_MANIFEST.json"
        altered_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        del altered_manifest["licenses"]
        manifest_path.write_text(
            json.dumps(altered_manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        checksum_path = isolated_challenge / "CHECKSUMS.sha256"
        checksum_lines = []
        for line in checksum_path.read_text(encoding="utf-8").splitlines():
            _, relative = line.split("  ", 1)
            digest = sha256((isolated_challenge / relative).read_bytes())
            checksum_lines.append(f"{digest}  {relative}")
        checksum_path.write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
        contract_check = subprocess.run(
            [sys.executable, str(isolated_challenge / "verify_package.py")],
            cwd=isolated_challenge,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(contract_check.returncode, 0)
        self.assertIn("role-package boundary", contract_check.stderr)

    def test_build_record_binds_tool_state_and_rejects_rehashed_tampering(self) -> None:
        baseline = self.fixture.package("build-record-baseline")
        build_path = baseline / "BUILD_RECORD.json"
        build = json.loads(build_path.read_text(encoding="utf-8"))
        self.assertEqual(
            build["tool_revision_scope"], "repository-head-not-byte-identity"
        )
        self.assertIn(build["tool_worktree_state"], {"clean", "dirty"})
        self.assertEqual(build["packager_sha256"], release_core._packager_sha256())
        self.assertEqual(
            build["verifier_sha256"], sha256(release_core._standalone_verifier())
        )

        mutations = {
            "build-revision-scope": lambda record: record.__setitem__(
                "tool_revision_scope", "unbound"
            ),
            "build-worktree-state": lambda record: record.__setitem__(
                "tool_worktree_state", "unknown"
            ),
            "build-packager-digest": lambda record: record.__setitem__(
                "packager_sha256", ZERO_DIGEST
            ),
            "build-verifier-digest": lambda record: record.__setitem__(
                "verifier_sha256", ZERO_DIGEST
            ),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                staging = self.root / name
                shutil.copytree(baseline, staging)
                build_path = staging / "BUILD_RECORD.json"
                build = json.loads(build_path.read_text(encoding="utf-8"))
                mutate(build)
                build_data = write_json(build_path, build)
                control_path = staging / "CONTROL_MANIFEST.json"
                control = json.loads(control_path.read_text(encoding="utf-8"))
                control["build_record_sha256"] = sha256(build_data)
                write_json(control_path, control)
                with self.assertRaises(release_core.ReleaseError):
                    release_core.verify_blind_staging(staging)

    def test_frozen_role_packages_are_reproducible_and_tampering_is_detected(self) -> None:
        first = self.fixture.package("staging-one")
        second = self.fixture.package("staging-two")
        for role in ROLES:
            first_files = {
                path.relative_to(first / role).as_posix(): path.read_bytes()
                for path in (first / role).rglob("*")
                if path.is_file()
            }
            second_files = {
                path.relative_to(second / role).as_posix(): path.read_bytes()
                for path in (second / role).rglob("*")
                if path.is_file()
            }
            self.assertEqual(first_files, second_files)

        unbound = first / "unbound-root-note.txt"
        unbound.write_text("must not be ignored", encoding="utf-8")
        with self.assertRaisesRegex(release_core.ReleaseError, "unbound"):
            release_core.verify_blind_staging(first)
        unbound.unlink()

        target = first / "challenge" / "task.json"
        target.write_bytes(target.read_bytes() + b"\n")
        with self.assertRaisesRegex(release_core.ReleaseError, "checksum mismatch"):
            release_core.verify_blind_staging(first)

        executable = second / "challenge" / "run.sh"
        executable.chmod(0o600)
        with self.assertRaisesRegex(release_core.ReleaseError, "source inventory"):
            release_core.verify_blind_staging(second)
        executable.chmod(0o700)

        build_record = second / "BUILD_RECORD.json"
        build_record.write_bytes(build_record.read_bytes() + b"\n")
        with self.assertRaisesRegex(release_core.ReleaseError, "build record digest"):
            release_core.verify_blind_staging(second)

    def test_rehashed_unlisted_role_payload_is_still_rejected(self) -> None:
        staging = self.fixture.package("unbound-payload-staging")
        package = staging / "maintainer"
        injected = package / "UNDECLARED.bin"
        injected.write_bytes(b"not in the frozen source inventory")
        injected.chmod(0o600)

        manifest_path = package / "PACKAGE_MANIFEST.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"].append(
            {
                "path": "UNDECLARED.bin",
                "sha256": sha256(injected.read_bytes()),
                "size": injected.stat().st_size,
            }
        )
        manifest["files"].sort(key=lambda item: item["path"])
        manifest_path.write_text(
            json.dumps(
                manifest,
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n",
            encoding="utf-8",
        )
        checksum_data = rewrite_package_checksums(package)

        control_path = staging / "CONTROL_MANIFEST.json"
        control = json.loads(control_path.read_text(encoding="utf-8"))
        control["packages"]["maintainer"] = {
            "manifest_sha256": sha256(manifest_path.read_bytes()),
            "checksums_sha256": sha256(checksum_data),
        }
        control_path.write_text(
            json.dumps(control, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

        with self.assertRaisesRegex(release_core.ReleaseError, "unbound payload"):
            release_core.verify_export(package)
        with self.assertRaisesRegex(release_core.ReleaseError, "unbound payload"):
            release_core.verify_blind_staging(staging)
        standalone = subprocess.run(
            [sys.executable, str(package / "verify_package.py")],
            cwd=package,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(standalone.returncode, 0)
        self.assertIn("unbound payload", standalone.stderr)

    def test_manifest_allowlist_digest_and_source_object_fail_closed(self) -> None:
        extra = self.fixture.sources["challenge"] / "unlisted.txt"
        extra.write_text("not in the manifest", encoding="utf-8")
        output = self.root / "must-not-exist-extra"
        with self.assertRaisesRegex(release_core.ReleaseError, "allowlist"):
            self.fixture.package(output.name)
        self.assertFalse(output.exists())
        extra.unlink()

        cases: list[tuple[str, object, str]] = []
        wrong_digest = deepcopy(self.fixture.manifest)
        wrong_digest["package_files"]["challenge"][0]["sha256"] = ZERO_DIGEST
        cases.append(("digest", wrong_digest, "source bytes"))
        wrong_size = deepcopy(self.fixture.manifest)
        wrong_size["package_files"]["challenge"][0]["size"] += 1
        cases.append(("size", wrong_size, "source bytes"))
        wrong_root = deepcopy(self.fixture.manifest)
        wrong_root["source_bindings"]["challenge"]["root_digest"] = ZERO_DIGEST
        cases.append(("root", wrong_root, "root digest"))
        extra_key = deepcopy(self.fixture.manifest)
        extra_key["unexpected"] = True
        cases.append(("extra-key", extra_key, "unexpected fields"))
        collision = deepcopy(self.fixture.manifest)
        duplicate = deepcopy(collision["package_files"]["challenge"][1])
        duplicate["path"] = duplicate["path"].casefold()
        collision["package_files"]["challenge"].append(duplicate)
        cases.append(("collision", collision, "path collision"))
        non_nfc = deepcopy(self.fixture.manifest)
        non_nfc["package_files"]["challenge"][1]["path"] = "Cafe\u0301.md"
        cases.append(("non-nfc", non_nfc, "NFC-normalized"))
        list_revision_type = deepcopy(self.fixture.manifest)
        list_revision_type["source_bindings"]["challenge"]["revision_type"] = ["git"]
        cases.append(("revision-type-list", list_revision_type, "revision_type"))
        list_redistribution = deepcopy(self.fixture.manifest)
        list_redistribution["licenses"][0]["redistribution"] = ["allowed"]
        cases.append(("redistribution-list", list_redistribution, "redistribution"))
        list_license_id = deepcopy(self.fixture.manifest)
        list_license_id["package_files"]["challenge"][0]["license_id"] = [
            "synthetic-license"
        ]
        cases.append(("license-id-list", list_license_id, "license_id"))
        invalid_unicode = deepcopy(self.fixture.manifest)
        invalid_unicode["claims_not_made"][0] = "\ud800"
        cases.append(("invalid-unicode", invalid_unicode, "invalid Unicode"))
        leaking_scoring_version = deepcopy(self.fixture.manifest)
        leaking_scoring_version["scoring"]["version"] = (
            "controlled expected answer is SEVEN"
        )
        cases.append(("leaking-scoring-version", leaking_scoring_version, "semantic version"))

        for name, manifest, message in cases:
            with self.subTest(name=name):
                self.fixture.write_manifest(manifest)
                candidate = self.root / f"must-not-exist-{name}"
                with self.assertRaisesRegex(release_core.ReleaseError, message):
                    self.fixture.package(candidate.name)
                self.assertFalse(candidate.exists())
        self.fixture.write_manifest()

    def test_malformed_json_is_rejected_before_any_output(self) -> None:
        malformed = {
            "duplicate": b'{"schema_version":1,"schema_version":1}',
            "nan": b'{"schema_version":NaN}',
            "float": b'{"schema_version":1.0}',
            "overflowing-float": b'{"value":1e10000}',
            "deep": (b'{"value":' + b"[" * 101 + b"0" + b"]" * 101 + b"}"),
        }
        for name, data in malformed.items():
            with self.subTest(name=name):
                self.fixture.manifest_path.write_bytes(data)
                output = self.root / f"must-not-exist-{name}"
                with self.assertRaises(release_core.ReleaseError):
                    self.fixture.package(output.name)
                self.assertFalse(output.exists())
        self.fixture.write_manifest()

        legal_brackets_in_string = json.dumps(
            {"value": '"' + "[" * 101}, separators=(",", ":")
        ).encode("utf-8")
        parsed = release_core._strict_json_bytes(
            legal_brackets_in_string, field="escaped-string fixture"
        )
        self.assertEqual(parsed["value"], '"' + "[" * 101)

        nested: object = 0
        for _ in range(101):
            nested = [nested]
        escaped_then_deep = json.dumps(
            {"escaped": '"', "deep": nested}, separators=(",", ":")
        ).encode("utf-8")
        with self.assertRaisesRegex(release_core.ReleaseError, "nesting exceeds"):
            release_core._strict_json_bytes(
                escaped_then_deep, field="deep escaped fixture"
            )

    def test_schema_versions_and_file_metadata_require_exact_json_types(self) -> None:
        source_cases: list[tuple[str, dict[str, object], str]] = []
        source_schema_bool = deepcopy(self.fixture.manifest)
        source_schema_bool["schema_version"] = True
        source_cases.append(("source-schema-bool", source_schema_bool, "schema version"))
        source_size_bool = deepcopy(self.fixture.manifest)
        source_size_bool["package_files"]["challenge"][0]["size"] = True
        source_cases.append(("source-size-bool", source_size_bool, "size"))
        source_executable_int = deepcopy(self.fixture.manifest)
        source_executable_int["package_files"]["challenge"][0]["executable"] = 1
        source_cases.append(
            ("source-executable-int", source_executable_int, "executable")
        )

        for name, manifest, message in source_cases:
            with self.subTest(name=name):
                self.fixture.write_manifest(manifest)
                output = self.root / f"must-not-exist-{name}"
                with self.assertRaisesRegex(release_core.ReleaseError, message):
                    self.fixture.package(output.name)
                self.assertFalse(output.exists())
        self.fixture.write_manifest()

        baseline = self.fixture.package("schema-type-baseline")

        role_mutations = {
            "role-schema-bool": lambda manifest: manifest.__setitem__(
                "schema_version", True
            ),
            "role-size-bool": lambda manifest: manifest["source_inventory"][0].__setitem__(
                "size", True
            ),
            "role-executable-int": lambda manifest: manifest["source_inventory"][0].__setitem__(
                "executable", 1
            ),
            "role-schema-float": lambda manifest: manifest.__setitem__(
                "schema_version", 1.0
            ),
        }
        for name, mutate in role_mutations.items():
            with self.subTest(name=name):
                package = self.root / name
                shutil.copytree(baseline / "challenge", package)
                manifest_path = package / "PACKAGE_MANIFEST.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                mutate(manifest)
                write_json(manifest_path, manifest)
                rewrite_package_checksums(package)
                self.assert_rejected_by_main_and_standalone(package)

        control_bool = self.root / "control-schema-bool"
        shutil.copytree(baseline, control_bool)
        control_path = control_bool / "CONTROL_MANIFEST.json"
        control = json.loads(control_path.read_text(encoding="utf-8"))
        control["schema_version"] = True
        write_json(control_path, control)
        with self.assertRaisesRegex(release_core.ReleaseError, "schema version"):
            release_core.verify_blind_staging(control_bool)

        build_bool = self.root / "build-schema-bool"
        shutil.copytree(baseline, build_bool)
        build_path = build_bool / "BUILD_RECORD.json"
        build = json.loads(build_path.read_text(encoding="utf-8"))
        build["schema_version"] = True
        build_data = write_json(build_path, build)
        control_path = build_bool / "CONTROL_MANIFEST.json"
        control = json.loads(control_path.read_text(encoding="utf-8"))
        control["build_record_sha256"] = sha256(build_data)
        write_json(control_path, control)
        with self.assertRaisesRegex(release_core.ReleaseError, "schema version"):
            release_core.verify_blind_staging(build_bool)

    def test_semver_and_template_placeholders_fail_closed(self) -> None:
        invalid_versions = (
            "1.0.0-01",
            "1.0.0-..",
            "1.0.0-alpha..beta",
            "1.0.0+...",
            "01.0.0",
            "1.0",
        )
        for field_path in (("case_version",), ("scoring", "version")):
            for version in invalid_versions:
                with self.subTest(field_path=field_path, version=version):
                    manifest = deepcopy(self.fixture.manifest)
                    target = manifest
                    for component in field_path[:-1]:
                        target = target[component]
                    target[field_path[-1]] = version
                    with self.assertRaisesRegex(
                        release_core.ReleaseError, "semantic version"
                    ):
                        release_core._validate_blind_manifest(manifest)

        valid_versions = (
            "0.0.0",
            "1.0.0-alpha",
            "1.0.0-alpha.1",
            "1.2.3-beta.2+build-5",
        )
        for version in valid_versions:
            with self.subTest(valid_version=version):
                manifest = deepcopy(self.fixture.manifest)
                manifest["case_version"] = version
                manifest["scoring"]["version"] = version
                release_core._validate_blind_manifest(manifest)

        placeholder_cases: list[tuple[str, dict[str, object]]] = []
        placeholder_release = deepcopy(self.fixture.manifest)
        placeholder_release["release_id"] = "replace-release"
        placeholder_cases.append(("placeholder-release-id", placeholder_release))
        placeholder_case = deepcopy(self.fixture.manifest)
        placeholder_case["case_id"] = "your-case"
        placeholder_cases.append(("placeholder-case-id", placeholder_case))
        placeholder_path = deepcopy(self.fixture.manifest)
        placeholder_path["package_files"]["challenge"][0]["path"] = "{{file}}.txt"
        placeholder_cases.append(("placeholder-path", placeholder_path))
        placeholder_text = deepcopy(self.fixture.manifest)
        placeholder_text["scoring"]["automatic_scope"] = (
            "REPLACE: describe the automatic scoring scope"
        )
        placeholder_cases.append(("placeholder-text", placeholder_text))
        for name, manifest in placeholder_cases:
            with self.subTest(name=name):
                with self.assertRaisesRegex(release_core.ReleaseError, "placeholder"):
                    release_core._validate_blind_manifest(manifest)

        baseline = self.fixture.package("semver-placeholder-baseline")
        role_cases: list[tuple[str, object]] = [
            (
                "role-invalid-semver",
                lambda manifest: manifest.__setitem__("case_version", "1.0.0-01"),
            ),
            (
                "role-placeholder-id",
                lambda manifest: manifest.__setitem__("release_id", "replace-release"),
            ),
            (
                "role-placeholder-path",
                lambda manifest: manifest["source_inventory"][0].__setitem__(
                    "path", "{{file}}.txt"
                ),
            ),
            (
                "role-license-path-case",
                lambda manifest: manifest["licenses"][0].__setitem__(
                    "notice_path", "license"
                ),
            ),
        ]
        for name, mutate in role_cases:
            with self.subTest(name=name):
                package = self.root / name
                shutil.copytree(baseline / "challenge", package)
                manifest_path = package / "PACKAGE_MANIFEST.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                mutate(manifest)
                write_json(manifest_path, manifest)
                rewrite_package_checksums(package)
                self.assert_rejected_by_main_and_standalone(package)

    def test_timestamps_require_canonical_utc_rfc3339_in_main_and_standalone(self) -> None:
        invalid_timestamps = (
            "2026-09-12 00:00:00Z",
            "2026-09-12T00:00Z",
            "2026-09-12t00:00:00Z",
            "2026-09-12T00:00:00+00:00",
        )
        for timestamp in invalid_timestamps:
            with self.subTest(source_timestamp=timestamp):
                manifest = deepcopy(self.fixture.manifest)
                manifest["created_at"] = timestamp
                with self.assertRaisesRegex(release_core.ReleaseError, "RFC3339"):
                    release_core._validate_blind_manifest(manifest)

        fractional = deepcopy(self.fixture.manifest)
        fractional["created_at"] = "2026-09-12T00:00:00.123456Z"
        for approval in fractional["human_approvals"]:
            approval["reviewed_at"] = "2026-09-12T00:00:00.123456Z"
        release_core._validate_blind_manifest(fractional)

        baseline = self.fixture.package("timestamp-baseline")
        for index, timestamp in enumerate(invalid_timestamps):
            with self.subTest(role_timestamp=timestamp):
                package = self.root / f"role-invalid-timestamp-{index}"
                shutil.copytree(baseline / "challenge", package)
                manifest_path = package / "PACKAGE_MANIFEST.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest["created_at"] = timestamp
                write_json(manifest_path, manifest)
                rewrite_package_checksums(package)
                self.assert_rejected_by_main_and_standalone(package)

    def test_controlled_digests_cannot_use_zero_placeholders(self) -> None:
        baseline = self.fixture.package("digest-placeholder-baseline")
        cases = {
            "evaluator-scoring-zero": lambda manifest: manifest[
                "scoring_reference"
            ].__setitem__("digest", ZERO_DIGEST),
            "evaluator-source-manifest-zero": lambda manifest: manifest.__setitem__(
                "source_manifest_sha256", ZERO_DIGEST
            ),
            "evaluator-challenge-manifest-zero": lambda manifest: manifest.__setitem__(
                "challenge_manifest_sha256", ZERO_DIGEST
            ),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name):
                package = self.root / name
                shutil.copytree(baseline / "evaluator", package)
                manifest_path = package / "PACKAGE_MANIFEST.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                mutate(manifest)
                write_json(manifest_path, manifest)
                rewrite_package_checksums(package)
                self.assert_rejected_by_main_and_standalone(package)

    def test_leakage_record_rejects_equal_bool_float_and_extra_key_values(self) -> None:
        baseline = self.fixture.package("leakage-schema-baseline")
        mutations = {
            "leakage-schema-bool": lambda leakage: leakage.__setitem__(
                "schema_version", True
            ),
            "leakage-text-count-float": lambda leakage: leakage.__setitem__(
                "text_files_scanned", float(leakage["text_files_scanned"])
            ),
            "leakage-binary-count-bool": lambda leakage: leakage.__setitem__(
                "binary_files_path_only", bool(leakage["binary_files_path_only"])
            ),
            "leakage-extra-key": lambda leakage: leakage.__setitem__(
                "unexpected", True
            ),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                package = self.root / name
                shutil.copytree(baseline / "challenge", package)
                leakage_path = package / "LEAKAGE_SCAN.json"
                leakage = json.loads(leakage_path.read_text(encoding="utf-8"))
                mutate(leakage)
                write_json(leakage_path, leakage)
                refresh_manifest_payload_record(package, "LEAKAGE_SCAN.json")
                self.assert_rejected_by_main_and_standalone(package)

    def test_private_scoring_digest_requires_trusted_leakage_verification(self) -> None:
        digest = str(self.fixture.manifest["scoring"]["digest"])
        leaked_path = self.fixture.sources["challenge"] / "opaque.txt"
        leaked_data = (digest.upper() + "\n").encode("ascii")
        leaked_path.write_bytes(leaked_data)
        self.fixture.payloads["challenge"]["opaque.txt"] = leaked_data
        self.fixture.manifest = self.fixture._manifest()
        self.fixture.write_manifest()

        refused_output = self.root / "must-not-exist-private-digest"
        with self.assertRaisesRegex(
            release_core.ReleaseError, "exact-sensitive-value"
        ):
            self.fixture.package(refused_output.name)
        self.assertFalse(refused_output.exists())

        original_scan = release_core._scan_challenge

        def public_rules_only(
            files: dict[str, bytes], *, private_values: object = ()
        ) -> dict[str, object]:
            del private_values
            return original_scan(files)

        with mock.patch.object(
            release_core, "_scan_challenge", side_effect=public_rules_only
        ):
            staging = self.fixture.package("legacy-private-digest-staging")

        isolated = run_standalone(staging / "challenge")
        self.assertEqual(isolated.returncode, 0, isolated.stderr)
        self.assertIn("cannot test absence of unknown private values", isolated.stdout)
        with self.assertRaisesRegex(
            release_core.ReleaseError, "exact-sensitive-value"
        ):
            release_core.verify_blind_staging(staging)

        leaked_path.unlink()
        del self.fixture.payloads["challenge"]["opaque.txt"]
        approval_ref = str(self.fixture.manifest["licenses"][0]["approval_ref"])
        approval_path = self.fixture.sources["challenge"] / "opaque-ref.txt"
        approval_data = (approval_ref + "\n").encode("utf-8")
        approval_path.write_bytes(approval_data)
        self.fixture.payloads["challenge"]["opaque-ref.txt"] = approval_data
        self.fixture.manifest = self.fixture._manifest()
        self.fixture.write_manifest()

        approval_output = self.root / "must-not-exist-private-approval-ref"
        with self.assertRaisesRegex(
            release_core.ReleaseError, "exact-sensitive-value"
        ):
            self.fixture.package(approval_output.name)
        self.assertFalse(approval_output.exists())

        with mock.patch.object(
            release_core, "_scan_challenge", side_effect=public_rules_only
        ):
            approval_staging = self.fixture.package(
                "legacy-private-approval-ref-staging"
            )
        approval_isolated = run_standalone(approval_staging / "challenge")
        self.assertEqual(approval_isolated.returncode, 0, approval_isolated.stderr)
        self.assertIn(
            "cannot test absence of unknown private values",
            approval_isolated.stdout,
        )
        with self.assertRaisesRegex(
            release_core.ReleaseError, "exact-sensitive-value"
        ):
            release_core.verify_blind_staging(approval_staging)

    def test_standalone_fails_closed_on_unreadable_directories_and_caps(self) -> None:
        baseline = self.fixture.package("standalone-resource-baseline")

        oversized = self.root / "standalone-oversized-file"
        shutil.copytree(baseline / "challenge", oversized)
        oversized_path = oversized / "oversized.bin"
        with oversized_path.open("wb") as stream:
            stream.truncate(release_core.MAX_FILE_BYTES + 1)
        result = run_standalone(oversized)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("package file too large", result.stderr)

        over_total = self.root / "standalone-over-total-cap"
        shutil.copytree(baseline / "challenge", over_total)
        sparse_count = release_core.MAX_PACKAGE_TOTAL_BYTES // release_core.MAX_FILE_BYTES + 1
        for index in range(sparse_count):
            path = over_total / f"sparse-{index:02d}.bin"
            with path.open("wb") as stream:
                stream.truncate(release_core.MAX_FILE_BYTES)
        result = run_standalone(over_total)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("package capacity exceeded", result.stderr)

        if os.name != "posix" or not hasattr(os, "geteuid") or os.geteuid() == 0:
            return
        unreadable = self.root / "standalone-unreadable-directory"
        shutil.copytree(baseline / "challenge", unreadable)
        blocked = unreadable / "blocked"
        blocked.mkdir()
        blocked.chmod(0)
        try:
            try:
                os.listdir(blocked)
            except PermissionError:
                pass
            else:
                self.skipTest("filesystem does not enforce unreadable directories")
            result = run_standalone(unreadable)
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertNotIn("Traceback", result.stderr)
        finally:
            blocked.chmod(0o700)

    def test_wrong_json_leaf_types_never_escape_as_internal_exceptions(self) -> None:
        leaves: list[tuple[object, ...]] = []

        def visit(value: object, path: tuple[object, ...] = ()) -> None:
            if isinstance(value, dict):
                for key, nested in value.items():
                    visit(nested, path + (key,))
            elif isinstance(value, list):
                for index, nested in enumerate(value):
                    visit(nested, path + (index,))
            else:
                leaves.append(path)

        visit(self.fixture.manifest)
        for path in leaves:
            with self.subTest(path=path):
                malformed = deepcopy(self.fixture.manifest)
                parent: object = malformed
                for component in path[:-1]:
                    parent = parent[component]
                parent[path[-1]] = []
                try:
                    release_core._validate_blind_manifest(malformed)
                except release_core.ReleaseError:
                    continue
                except Exception as error:  # pragma: no cover - assertion reports the type
                    self.fail(f"{path} raised internal {type(error).__name__}: {error}")
                self.fail(f"{path} accepted an invalid list value")

    def test_leakage_patterns_and_source_filesystem_tricks_are_refused(self) -> None:
        challenge = self.fixture.sources["challenge"]
        cases = {
            "answer-map.json": b'{"safe":"looking"}\n',
            "notes.md": b"expected_answer: seven\n",
            "bridge.py": b"from evaluator import private_score\n",
            "quoted-key.json": b'{"expected_answer":"seven"}\n',
            "dict-key.py": b"record = {'expected_answer': 'seven'}\n",
            "leak.ipynb": b'{"cells":[],"expected_answer":"seven"}\n',
            ".git/objects/aa/history": b"compressed-history-placeholder\x00",
        }
        for filename, data in cases.items():
            with self.subTest(filename=filename):
                path = challenge / filename
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                self.fixture.payloads["challenge"][filename] = data
                self.fixture.manifest = self.fixture._manifest()
                self.fixture.write_manifest()
                safe_name = filename.replace(".", "-").replace("/", "-")
                output = self.root / f"must-not-exist-{safe_name}"
                with self.assertRaisesRegex(release_core.ReleaseError, "leakage rule") as raised:
                    self.fixture.package(output.name)
                self.assertNotIn("seven", str(raised.exception))
                self.assertFalse(output.exists())
                path.unlink()
                del self.fixture.payloads["challenge"][filename]
        self.fixture.manifest = self.fixture._manifest()
        self.fixture.write_manifest()

        symlink = challenge / "linked.txt"
        symlink.symlink_to(challenge / "README.md")
        with self.assertRaisesRegex(release_core.ReleaseError, "symlink"):
            self.fixture.package("must-not-exist-symlink")
        symlink.unlink()

        if hasattr(os, "mkfifo"):
            fifo = challenge / "pipe"
            os.mkfifo(fifo)
            with self.assertRaisesRegex(release_core.ReleaseError, "non-regular"):
                self.fixture.package("must-not-exist-fifo")
            fifo.unlink()

    def test_path_overlap_existing_output_and_injected_write_failure_leave_no_artifact(self) -> None:
        existing = self.root / "already-there"
        existing.mkdir()
        sentinel = existing / "keep.txt"
        sentinel.write_text("keep", encoding="utf-8")
        with self.assertRaisesRegex(release_core.ReleaseError, "overwrite"):
            self.fixture.package(existing.name)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")

        nested_output = self.fixture.sources["challenge"] / "nested-output"
        with self.assertRaisesRegex(release_core.ReleaseError, "overlap"):
            release_core.package_blind(
                self.fixture.manifest_path,
                challenge_source=self.fixture.sources["challenge"],
                evaluator_source=self.fixture.sources["evaluator"],
                maintainer_source=self.fixture.sources["maintainer"],
                output=nested_output,
                actor="Builder",
            )
        self.assertFalse(nested_output.exists())

        failed_output = self.root / "must-be-cleaned"
        with mock.patch.object(
            release_core,
            "_write_file_at",
            side_effect=release_core.ReleaseError("injected write failure"),
        ):
            with self.assertRaisesRegex(release_core.ReleaseError, "injected"):
                self.fixture.package(failed_output.name)
        self.assertFalse(failed_output.exists())

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are unavailable")
    def test_output_swap_cannot_redirect_controlled_writes(self) -> None:
        output = self.root / "race-output"
        moved = self.root / "original-output-moved"
        redirect = self.root / "attacker-redirect"
        redirect.mkdir()
        original_writer = release_core._write_tree_at
        swapped = False

        def swap_then_write(*args, **kwargs):
            nonlocal swapped
            if not swapped:
                os.rename(output, moved)
                output.symlink_to(redirect, target_is_directory=True)
                swapped = True
            return original_writer(*args, **kwargs)

        with mock.patch.object(
            release_core, "_write_tree_at", side_effect=swap_then_write
        ):
            with self.assertRaisesRegex(release_core.ReleaseError, "identity changed"):
                self.fixture.package(output.name)
        self.assertTrue(output.is_symlink())
        self.assertEqual(list(redirect.iterdir()), [])
        self.assertTrue(moved.is_dir())
        self.assertEqual(list(moved.iterdir()), [])

    @unittest.skipUnless(os.name == "posix", "POSIX mode bits are not available")
    def test_verifier_rejects_group_or_world_readable_private_staging(self) -> None:
        staging = self.fixture.package("permission-staging")
        staging.chmod(0o777)
        with self.assertRaisesRegex(release_core.ReleaseError, "permissions"):
            release_core.verify_blind_staging(staging)
        staging.chmod(0o700)

        evaluator_file = staging / "evaluator" / "grade.py"
        evaluator_file.chmod(0o644)
        with self.assertRaisesRegex(release_core.ReleaseError, "permissions"):
            release_core.verify_blind_staging(staging)
        evaluator_file.chmod(0o600)
        self.assertEqual(
            release_core.verify_blind_staging(staging)["integrity_status"], "pass"
        )

    def test_cli_reports_limited_assembly_state_and_json_verification(self) -> None:
        output = self.root / "cli-staging"
        result = run_cli(
            "package",
            "blind",
            "--manifest",
            str(self.fixture.manifest_path),
            "--challenge-source",
            str(self.fixture.sources["challenge"]),
            "--evaluator-source",
            str(self.fixture.sources["evaluator"]),
            "--maintainer-source",
            str(self.fixture.sources["maintainer"]),
            "--output",
            str(output),
            "--actor",
            "CLI Builder",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("AWAITING CONTROLLED PLACEMENT", result.stdout)
        self.assertIn("not access control", result.stdout)

        verify = run_cli("package", "verify", str(output), "--json")
        self.assertEqual(verify.returncode, 0, verify.stderr)
        payload = json.loads(verify.stdout)
        self.assertEqual(payload["integrity_status"], "pass")
        self.assertEqual(payload["operational_release"], "not_approved")

    def test_invalid_public_paths_are_reported_as_release_errors(self) -> None:
        for verifier in (
            release_core.verify_export,
            release_core.verify_blind_staging,
        ):
            with self.subTest(verifier=verifier.__name__):
                with self.assertRaises(release_core.ReleaseError):
                    verifier("bad\x00path")

    def test_generated_overhead_has_reserved_verification_capacity(self) -> None:
        self.assertGreaterEqual(
            release_core.MAX_PACKAGE_FILES, release_core.MAX_FILES + 16
        )
        self.assertGreater(
            release_core.MAX_PACKAGE_TOTAL_BYTES, release_core.MAX_TOTAL_BYTES
        )


if __name__ == "__main__":
    unittest.main()
