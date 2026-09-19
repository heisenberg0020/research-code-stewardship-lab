from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import hashlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "rcsl.py"

TEMPLATE_CONTENTS = {
    "research-contract-template.md": "# Research contract\n\n## Scope\n\n{{research_scope}}\n",
    "evidence-passport-template.md": "# Evidence passport\n\n## Sources\n\n{{evidence_sources}}\n",
    "triage-card-template.md": "# Triage card\n\n## Finding\n\n{{finding_summary}}\n",
    "delegation-contract-template.md": "# Delegation contract\n\n## Authority\n\n{{authority_boundary}}\n",
}


def run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *arguments],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def load_rcsl_module():
    """Load the script so workspace tests can use isolated temporary public assets."""

    module_name = "rcsl_workspace_test_module"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, SCRIPT)
    if spec is None or spec.loader is None:
        raise ImportError(SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def run_module_cli(module, *arguments: str) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        returncode = module.main(list(arguments))
    return returncode, stdout.getvalue(), stderr.getvalue()


class RcslCommandTests(unittest.TestCase):
    def test_overview_orients_new_learners(self) -> None:
        result = run_cli("train", "overview")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Make runnable research code auditable", result.stdout)
        self.assertIn("start --level 1", result.stdout)
        self.assertIn("validate", result.stdout)

    def test_doctor_reports_python_and_torch_status(self) -> None:
        result = run_cli("train", "doctor")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Python:", result.stdout)
        self.assertIn("torch:", result.stdout)

    def test_start_only_lists_public_level_materials(self) -> None:
        result = run_cli("train", "start", "--level", "1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Level 1: Algorithm semantics", result.stdout)
        self.assertIn("level_1_algorithm_semantics/PAPER_MAP.md", result.stdout)
        self.assertIn("run_smoke.py", result.stdout)

    def test_help_exposes_only_supported_command_families(self) -> None:
        result = run_cli("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        for command in ("train", "audit", "export", "package"):
            self.assertIn(command, result.stdout)
        for removed in ("view", "install-skill", "init-audit", "lint-audit", "status-audit"):
            self.assertNotIn(removed, result.stdout)

    def test_invalid_level_is_rejected(self) -> None:
        result = run_cli("train", "start", "--level", "5")
        self.assertEqual(result.returncode, 2)
        self.assertIn("invalid choice", result.stderr)


class AuditWorkspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.module = load_rcsl_module()
        self.assets = self.root / "public-assets"
        self.assets.mkdir()
        for filename, content in TEMPLATE_CONTENTS.items():
            (self.assets / filename).write_text(content, encoding="utf-8")
        self.module.ASSET_DIRECTORY = self.assets

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def initialize_workspace(self, name: str = "audit") -> Path:
        workspace = self.root / name
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            returncode = self.module.command_init_audit(1, workspace)
        self.assertEqual(returncode, 0, stderr.getvalue())
        self.assertEqual(stdout.getvalue(), "")
        return workspace

    def test_init_copies_only_expected_public_templates_and_metadata(self) -> None:
        workspace = self.initialize_workspace()

        self.assertEqual(
            {path.name for path in workspace.iterdir()},
            set(TEMPLATE_CONTENTS) | {self.module.WORKSPACE_METADATA_NAME},
        )
        for filename, content in TEMPLATE_CONTENTS.items():
            self.assertEqual((workspace / filename).read_text(encoding="utf-8"), content)

        metadata = json.loads(
            (workspace / self.module.WORKSPACE_METADATA_NAME).read_text(encoding="utf-8")
        )
        self.assertEqual(metadata["workspace_type"], "rcsl-public-audit-workspace")
        self.assertEqual(metadata["validator_scope"], "structural_only")
        self.assertEqual(metadata["level"], 1)
        self.assertEqual(metadata["template_files"], list(self.module.WORKSPACE_TEMPLATE_FILENAMES))
        self.assertIn("public_check_command", metadata)
        self.assertEqual(metadata["capability_ids"], list(self.module.CAPABILITY_IDS))
        self.assertEqual(metadata["capabilities"], self.module.CAPABILITIES)
        self.assertEqual(metadata["maturity_bands"], list(self.module.MATURITY_BANDS))
        self.assertEqual(set(metadata["source_template_sha256"]), set(TEMPLATE_CONTENTS))

    def test_init_refuses_to_overwrite_existing_target(self) -> None:
        workspace = self.root / "existing-audit"
        workspace.mkdir()
        sentinel = workspace / "keep-me.txt"
        sentinel.write_text("unchanged", encoding="utf-8")

        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            returncode = self.module.command_init_audit(1, workspace)

        self.assertEqual(returncode, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("Refusing to overwrite", stderr.getvalue())
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "unchanged")

    def test_init_directory_swap_cannot_overwrite_redirect_target(self) -> None:
        workspace = self.root / "swapped-audit"
        displaced = self.root / "displaced-audit"
        redirect_target = self.root / "redirect-target"
        redirect_target.mkdir()
        sentinels = {}
        for filename in (*TEMPLATE_CONTENTS, self.module.WORKSPACE_METADATA_NAME):
            sentinel = redirect_target / filename
            sentinel.write_text(f"keep {filename}\n", encoding="utf-8")
            sentinels[filename] = sentinel.read_bytes()

        real_mkdir = os.mkdir
        swapped = False

        def swap_after_create(path, mode=0o777, *, dir_fd=None):
            nonlocal swapped
            result = real_mkdir(path, mode, dir_fd=dir_fd)
            if path == workspace.name and dir_fd is not None and not swapped:
                os.rename(
                    workspace.name,
                    displaced.name,
                    src_dir_fd=dir_fd,
                    dst_dir_fd=dir_fd,
                )
                os.symlink(
                    redirect_target,
                    workspace.name,
                    dir_fd=dir_fd,
                    target_is_directory=True,
                )
                swapped = True
            return result

        with mock.patch.object(self.module.os, "mkdir", side_effect=swap_after_create):
            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                returncode = self.module.command_init_audit(1, workspace)

        self.assertTrue(swapped)
        self.assertEqual(returncode, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("No existing file was overwritten", stderr.getvalue())
        for filename, expected in sentinels.items():
            self.assertEqual((redirect_target / filename).read_bytes(), expected)

    def test_incomplete_workspace_fails_lint_but_status_reports_progress(self) -> None:
        workspace = self.initialize_workspace()

        stdout = io.StringIO()
        with redirect_stdout(stdout):
            returncode = self.module.command_lint_audit(workspace)
        self.assertEqual(returncode, 1)
        self.assertIn("Structure status: INCOMPLETE", stdout.getvalue())
        self.assertIn("unresolved template placeholders", stdout.getvalue())
        inspection = self.module.inspect_audit_workspace(workspace)
        self.assertEqual(inspection.completed_template_count, 0)

    def test_workspace_metadata_requires_exact_integer_schema_and_level(self) -> None:
        for field, value, message in (
            ("schema_version", True, "schema_version is not supported"),
            ("level", True, "level is not a supported"),
        ):
            with self.subTest(field=field):
                workspace = self.initialize_workspace(f"invalid-{field}")
                metadata_path = workspace / self.module.WORKSPACE_METADATA_NAME
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                metadata[field] = value
                metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
                inspection = self.module.inspect_audit_workspace(workspace)
                self.assertIsNotNone(inspection)
                self.assertTrue(
                    any(message in issue for issue in inspection.general_issues)
                )

    def test_completed_workspace_passes_structural_lint(self) -> None:
        workspace = self.initialize_workspace()
        replacements = {
            "{{research_scope}}": "A bounded public audit.",
            "{{evidence_sources}}": "Paper and public run logs.",
            "{{finding_summary}}": "A reproducible observation.",
            "{{authority_boundary}}": "Human approval is required.",
        }
        for filename, content in TEMPLATE_CONTENTS.items():
            completed = content
            for placeholder, value in replacements.items():
                completed = completed.replace(placeholder, value)
            (workspace / filename).write_text(completed, encoding="utf-8")

        evidence = workspace / "evidence-passport-template.md"
        evidence.write_text(
            evidence.read_text(encoding="utf-8") + "\nObserved a TODO comment in source.\n",
            encoding="utf-8",
        )

        stdout = io.StringIO()
        with redirect_stdout(stdout):
            returncode = self.module.command_lint_audit(workspace)
        self.assertEqual(returncode, 0)
        self.assertIn("Template progress: 4/4", stdout.getvalue())
        self.assertIn("Structure status: COMPLETE", stdout.getvalue())
        self.assertIn("does not judge research or scientific correctness", stdout.getvalue())

    def test_isolated_path_is_refused_before_workspace_creation(self) -> None:
        workspace = self.root / self.module.ISOLATED_DIRECTORY_NAME / "audit"
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            returncode = self.module.command_init_audit(1, workspace)
        self.assertEqual(returncode, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("isolated instructor-material path", stderr.getvalue())
        self.assertFalse(workspace.exists())

    def test_path_resolving_into_isolated_material_is_refused(self) -> None:
        isolated = self.root / self.module.ISOLATED_DIRECTORY_NAME
        isolated.mkdir()
        alias = self.root / "public-looking-alias"
        try:
            alias.symlink_to(isolated, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"directory symlinks unavailable: {error}")

        workspace = alias / "audit"
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            returncode = self.module.command_init_audit(1, workspace)
        self.assertEqual(returncode, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("resolves into isolated instructor material", stderr.getvalue())
        self.assertFalse(workspace.exists())


class DualModeCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self._git("init")
        (self.project / "README.md").write_text("# Audit fixture\n", encoding="utf-8")
        self._git("add", "README.md")
        self._git(
            "-c",
            "user.name=RCSL CLI Test",
            "-c",
            "user.email=rcsl-cli@example.invalid",
            "commit",
            "-m",
            "initial fixture",
        )
        self.workspace = self.root / "audit-workspace"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _git(self, *arguments: str) -> str:
        result = subprocess.run(
            ("git", "-C", str(self.project), *arguments),
            capture_output=True,
            check=False,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def _initialize_bound_workspace(self) -> None:
        result = run_cli(
            "audit",
            "init",
            "--project",
            str(self.project),
            "--output",
            str(self.workspace),
            "--level",
            "2",
            "--actor",
            "CLI Auditor",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Audit workspace CREATED", result.stdout)
        self.assertIn("G0 decision: DRAFT", result.stdout)

    def _complete_templates(self) -> None:
        metadata = json.loads(
            (self.workspace / "audit-workspace.json").read_text(encoding="utf-8")
        )
        for filename in metadata["template_files"]:
            path = self.workspace / filename
            completed = re.sub(
                r"\{\{[^{}\n]+\}\}",
                "Documented evidence and named owner",
                path.read_text(encoding="utf-8"),
            )
            path.write_text(completed, encoding="utf-8")

    def _approve_and_add_finding(self) -> None:
        self._initialize_bound_workspace()
        self._complete_templates()
        gate = run_cli(
            "audit", "gate", "record", str(self.workspace),
            "--decision", "approved", "--reviewer", "Research Owner",
            "--rationale", "The bounded public contract was reviewed.",
        )
        self.assertEqual(gate.returncode, 0, gate.stderr)
        finding = run_cli(
            "audit", "finding", "add", str(self.workspace),
            "--id", "F-001", "--title", "Retained source needs human review",
            "--layer", "L1", "--competency", "C1", "--severity", "medium",
            "--claim", "The retained source must be compared with the research contract.",
            "--first-contract", "The reviewer must see the exact source bytes.",
            "--actor", "CLI Auditor",
        )
        self.assertEqual(finding.returncode, 0, finding.stderr)

    def test_content_import_cli_reaches_declared_terminal_states_without_changing_project(self) -> None:
        original_head = self._git("rev-parse", "HEAD")
        original_status = self._git("status", "--porcelain")
        original_readme = (self.project / "README.md").read_bytes()
        expected_sha = hashlib.sha256(original_readme).hexdigest()
        self._approve_and_add_finding()

        imported = run_cli(
            "audit", "evidence", "import", str(self.workspace),
            "--finding", "F-001", "--id", "E-README", "--type", "artifact",
            "--kind", "observed", "--source-kind", "project-relative",
            "--source-path", "README.md", "--artifact-role", "source-under-review",
            "--summary", "Retained committed README bytes for a named human review.",
            "--actor", "CLI Auditor",
        )
        self.assertEqual(imported.returncode, 0, imported.stderr)
        self.assertIn(f"sha256:{expected_sha}", imported.stdout)
        self.assertIn("One explicit file was retained", imported.stdout)
        self.assertIn("not source authenticity", imported.stdout)

        for state in ("triaged", "accepted", "mitigated", "verified", "closed"):
            transition = run_cli(
                "audit", "finding", "transition", str(self.workspace),
                "--finding", "F-001", "--to", state,
                "--rationale", f"Named reviewer recorded the {state} declaration.",
                "--actor", "Research Owner",
            )
            self.assertEqual(transition.returncode, 0, transition.stderr)
            self.assertIn(f"→ {state}", transition.stdout)
            self.assertIn("not independent verification", transition.stdout)

        verification = run_cli("audit", "verify", str(self.workspace), "--json")
        self.assertEqual(verification.returncode, 0, verification.stderr)
        verified_payload = json.loads(verification.stdout)
        self.assertEqual(verified_payload["assessment_status"], "local-records-consistent")
        self.assertEqual(verified_payload["evidence_profile"], "content-bound-v1")
        self.assertEqual(verified_payload["content_binding_state"], "current")
        self.assertEqual(verified_payload["verification"]["content_evidence_count"], 1)
        case = verified_payload["retained_case_ref"]
        self.assertIsInstance(case, dict)

        status = run_cli("audit", "status", str(self.workspace), "--json")
        self.assertEqual(status.returncode, 0, status.stderr)
        status_payload = json.loads(status.stdout)
        self.assertEqual(status_payload["assessment_status"], "preflight-current")
        self.assertEqual(status_payload["evidence_profile"], "content-bound-v1")
        self.assertEqual(status_payload["content_binding_state"], "current")
        self.assertEqual(status_payload["retained_case_ref"], case)
        self.assertEqual(status_payload["summary"]["finding_count"], 1)
        self.assertIn("not independent verification", " ".join(status_payload["limitations"]))

        listed = run_cli("audit", "finding", "list", str(self.workspace), "--json")
        self.assertEqual(listed.returncode, 0, listed.stderr)
        finding = json.loads(listed.stdout)["findings"][0]
        self.assertEqual(finding["status"], "closed")
        self.assertEqual(finding["case_state"], "current")
        self.assertEqual(finding["case_ref"], case)
        record = finding["evidence"][0]
        self.assertEqual(record["record_type"], "rcsl-content-evidence")
        self.assertEqual(record["case_ref"], case)
        self.assertEqual(record["artifact_ref"]["sha256"], expected_sha)
        self.assertEqual(record["artifact_ref"]["size"], len(original_readme))
        self.assertEqual(record["artifact_ref"]["path"], "README.md")
        self.assertEqual(record["source"], {"kind": "project-relative", "path": "README.md"})

        events = [
            json.loads(line)
            for line in (self.workspace / "audit-events.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        evidence_event = next(
            event for event in events
            if event["event_type"] == "finding_evidence_added"
            and event["payload"]["evidence_id"] == "E-README"
        )
        record_ref = evidence_event["payload"]["evidence_ref"]
        envelope = {
            "schema_version": 1,
            "domain": "rcsl-record-binding",
            "record_type": "evidence",
            "record_id": "E-README",
            "case_sha256": case["case_sha256"],
            "record": record,
        }
        expected_record_sha = hashlib.sha256(
            json.dumps(envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        self.assertEqual(record_ref, {
            "record_type": "evidence",
            "record_id": "E-README",
            "record_sha256": expected_record_sha,
            "case_sha256": case["case_sha256"],
        })

        report_path = self.workspace / "content-review.json"
        report = run_cli(
            "audit", "report", "build", str(self.workspace),
            "--output", str(report_path), "--format", "json",
        )
        self.assertEqual(report.returncode, 0, report.stderr)
        self.assertIn("not a scientific PASS", report.stdout)
        report_payload = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report_payload["current_case_ref"], case)
        self.assertEqual(report_payload["findings"][0]["evidence"][0]["artifact_ref"]["sha256"], expected_sha)
        self.assertEqual(report_payload["findings"][0]["status"], "closed")

        self.assertEqual(self._git("rev-parse", "HEAD"), original_head)
        self.assertEqual(self._git("status", "--porcelain"), original_status)
        self.assertEqual((self.project / "README.md").read_bytes(), original_readme)

    def test_content_import_cli_wires_declared_command_and_environment_without_execution(self) -> None:
        self._approve_and_add_finding()
        command_bytes = b"local synthetic command result\n"
        command_source = self.root / "command-result.txt"
        command_source.write_bytes(command_bytes)
        sentinel = self.root / "declared-command-was-not-run"
        declared_command = f"touch {sentinel}"
        command_import = run_cli(
            "audit", "evidence", "import", str(self.workspace),
            "--finding", "F-001", "--id", "E-COMMAND", "--type", "command-result",
            "--kind", "observed", "--source-kind", "external",
            "--source-path", str(command_source), "--source-ref", "runs/command-result.txt",
            "--declared-command", declared_command, "--exit-code", "0",
            "--summary", "An already-created local result; command and exit code are declarations.",
            "--actor", "CLI Auditor",
        )
        self.assertEqual(command_import.returncode, 0, command_import.stderr)
        self.assertFalse(sentinel.exists())
        self.assertIn("declared command was not executed", command_import.stdout)

        environment_bytes = b"Python fixture environment\n"
        environment_source = self.root / "environment.txt"
        environment_source.write_bytes(environment_bytes)
        environment_import = run_cli(
            "audit", "evidence", "import", str(self.workspace),
            "--finding", "F-001", "--id", "E-ENV", "--type", "environment",
            "--kind", "derived", "--source-kind", "external",
            "--source-path", str(environment_source), "--source-ref", "runs/environment.txt",
            "--environment-scope", "local-test-interpreter",
            "--summary", "Retained a bounded environment description for review.",
            "--actor", "CLI Auditor",
        )
        self.assertEqual(environment_import.returncode, 0, environment_import.stderr)

        listed = run_cli("audit", "finding", "list", str(self.workspace), "--json")
        self.assertEqual(listed.returncode, 0, listed.stderr)
        records = {
            record["id"]: record
            for record in json.loads(listed.stdout)["findings"][0]["evidence"]
        }
        self.assertEqual(set(records), {"E-COMMAND", "E-ENV"})
        command_record = records["E-COMMAND"]
        self.assertEqual(command_record["evidence_type"], "command-result")
        self.assertEqual(command_record["declared_command"], declared_command)
        self.assertEqual(command_record["exit_code"], 0)
        self.assertEqual(command_record["source"], {"kind": "external", "ref": "runs/command-result.txt"})
        self.assertEqual(command_record["artifact_ref"]["sha256"], hashlib.sha256(command_bytes).hexdigest())
        environment_record = records["E-ENV"]
        self.assertEqual(environment_record["evidence_type"], "environment")
        self.assertEqual(environment_record["environment_scope"], "local-test-interpreter")
        self.assertEqual(environment_record["artifact_ref"]["sha256"], hashlib.sha256(environment_bytes).hexdigest())
        self.assertEqual(environment_record["case_ref"], command_record["case_ref"])
        self.assertFalse(sentinel.exists())

    def test_content_import_cli_rejects_invalid_source_options_and_symlink(self) -> None:
        self._approve_and_add_finding()
        external = self.root / "explicit-external.txt"
        external.write_text("public fixture\n", encoding="utf-8")
        common = (
            "audit", "evidence", "import", str(self.workspace),
            "--finding", "F-001", "--type", "artifact", "--kind", "observed",
            "--source-kind", "external", "--source-path", str(external),
            "--summary", "A selected local fixture.", "--actor", "CLI Auditor",
        )
        missing_ref = run_cli(*common, "--id", "E-NO-REF", "--artifact-role", "result")
        self.assertEqual(missing_ref.returncode, 1)
        self.assertIn("external import requires --source-ref", missing_ref.stderr)
        self.assertEqual(missing_ref.stdout, "")

        wrong_type = run_cli(
            *common, "--id", "E-WRONG-TYPE", "--source-ref", "runs/fixture.txt",
            "--artifact-role", "result", "--environment-scope", "unexpected",
        )
        self.assertEqual(wrong_type.returncode, 1)
        self.assertIn("artifact import accepts only", wrong_type.stderr)
        self.assertEqual(wrong_type.stdout, "")

        relative_external = run_cli(
            "audit", "evidence", "import", str(self.workspace),
            "--finding", "F-001", "--id", "E-RELATIVE", "--type", "artifact",
            "--kind", "observed", "--source-kind", "external",
            "--source-path", "explicit-external.txt", "--source-ref", "runs/fixture.txt",
            "--artifact-role", "result", "--summary", "A relative external path is ambiguous.",
            "--actor", "CLI Auditor",
        )
        self.assertEqual(relative_external.returncode, 1)
        self.assertIn("absolute", relative_external.stderr)
        self.assertEqual(relative_external.stdout, "")

        alias = self.root / "explicit-source-alias.txt"
        try:
            alias.symlink_to(external)
        except OSError as error:
            self.skipTest(f"file symlinks unavailable: {error}")
        symlink = run_cli(
            "audit", "evidence", "import", str(self.workspace),
            "--finding", "F-001", "--id", "E-SYMLINK", "--type", "artifact",
            "--kind", "observed", "--source-kind", "external",
            "--source-path", str(alias), "--source-ref", "runs/fixture.txt",
            "--artifact-role", "result", "--summary", "Symlinks must be rejected.",
            "--actor", "CLI Auditor",
        )
        self.assertEqual(symlink.returncode, 1)
        self.assertIn("non-symlink file", symlink.stderr)
        self.assertEqual(symlink.stdout, "")

        verification = run_cli("audit", "verify", str(self.workspace), "--json")
        self.assertEqual(verification.returncode, 0, verification.stderr)
        self.assertEqual(json.loads(verification.stdout)["verification"]["content_evidence_count"], 0)

    def test_content_import_cli_rejects_malformed_metadata_before_storing_bytes(self) -> None:
        self._approve_and_add_finding()
        source = self.root / "metadata-source.txt"
        source.write_text("public fixture\n", encoding="utf-8")
        blob_store = self.workspace / "evidence" / "blobs" / "sha256"
        before = sorted(path.name for path in blob_store.iterdir())
        base = (
            "audit", "evidence", "import", str(self.workspace),
            "--finding", "F-001", "--kind", "observed",
            "--source-kind", "external", "--source-path", str(source),
            "--source-ref", "runs/metadata-source.txt",
            "--summary", "A selected public fixture.", "--actor", "CLI Auditor",
        )
        invalid = (
            ("E-ROLE", "artifact", ("--artifact-role", "   "), "--artifact-role"),
            ("E-ENV", "environment", ("--environment-scope", "   "), "--environment-scope"),
            (
                "E-COMMAND", "command-result",
                ("--declared-command", "   ", "--exit-code", "0"),
                "--declared-command",
            ),
            (
                "E-EXIT", "command-result",
                ("--declared-command", "external fixture", "--exit-code", "2147483648"),
                "signed 32-bit",
            ),
        )
        for evidence_id, evidence_type, extra, issue in invalid:
            with self.subTest(evidence_id=evidence_id):
                result = run_cli(*base, "--id", evidence_id, "--type", evidence_type, *extra)
                self.assertEqual(result.returncode, 1)
                self.assertIn(issue, result.stderr)
                self.assertEqual(result.stdout, "")
                self.assertEqual(sorted(path.name for path in blob_store.iterdir()), before)
        verification = run_cli("audit", "verify", str(self.workspace), "--json")
        self.assertEqual(verification.returncode, 0, verification.stderr)
        self.assertEqual(json.loads(verification.stdout)["verification"]["content_evidence_count"], 0)

    def test_status_text_distinguishes_stale_case_from_stale_baseline(self) -> None:
        self._approve_and_add_finding()
        contract = self.workspace / "research-contract-template.md"
        contract.write_text(
            contract.read_text(encoding="utf-8") + "\nA changed reviewed scope.\n",
            encoding="utf-8",
        )
        rotated = run_cli(
            "audit", "gate", "record", str(self.workspace),
            "--decision", "approved", "--reviewer", "Research Owner",
            "--rationale", "The revised contract bytes were separately reviewed.",
        )
        self.assertEqual(rotated.returncode, 0, rotated.stderr)
        status = run_cli("audit", "status", str(self.workspace))
        self.assertEqual(status.returncode, 0, status.stderr)
        self.assertIn("0 stale baseline", status.stdout)
        self.assertIn("1 stale case", status.stdout)
        self.assertIn("PREFLIGHT-NOT-CURRENT", status.stdout)
        listed = run_cli("audit", "finding", "list", str(self.workspace), "--json")
        self.assertEqual(listed.returncode, 0, listed.stderr)
        old_finding = json.loads(listed.stdout)["findings"][0]
        self.assertEqual(old_finding["case_state"], "stale")
        review_path = self.workspace / "stale-case-review.md"
        report = run_cli(
            "audit", "report", "build", str(self.workspace),
            "--output", str(review_path), "--format", "markdown",
        )
        self.assertEqual(report.returncode, 0, report.stderr)
        review_text = review_path.read_text(encoding="utf-8")
        self.assertIn("Findings from an older baseline: 0", review_text)
        self.assertIn("Findings from an older case: 1", review_text)
        self.assertIn("Case state: stale", review_text)
        self.assertIn(old_finding["case_ref"]["case_sha256"], review_text)

    def test_reference_only_evidence_and_stale_case_cannot_reach_current_terminal_gate(self) -> None:
        self._approve_and_add_finding()
        reference = run_cli(
            "audit", "evidence", "add", str(self.workspace),
            "--finding", "F-001", "--id", "E-REF", "--kind", "observed",
            "--reference", "README.md@HEAD", "--summary", "A pointer is not retained bytes.",
            "--actor", "CLI Auditor",
        )
        self.assertEqual(reference.returncode, 0, reference.stderr)
        self.assertIn("reference-only entry", reference.stdout)
        for state in ("triaged", "accepted", "mitigated"):
            transition = run_cli(
                "audit", "finding", "transition", str(self.workspace),
                "--finding", "F-001", "--to", state,
                "--rationale", "Named owner declaration before content review.",
                "--actor", "Research Owner",
            )
            self.assertEqual(transition.returncode, 0, transition.stderr)
        refused = run_cli(
            "audit", "finding", "transition", str(self.workspace),
            "--finding", "F-001", "--to", "verified",
            "--rationale", "Reference-only evidence is intentionally insufficient.",
            "--actor", "Research Owner",
        )
        self.assertEqual(refused.returncode, 1)
        self.assertIn("content-bound evidence", refused.stderr)

        (self.project / "README.md").write_text("# Audit fixture, revised\n", encoding="utf-8")
        self._git("add", "README.md")
        self._git(
            "-c", "user.name=RCSL CLI Test",
            "-c", "user.email=rcsl-cli@example.invalid",
            "commit", "-m", "next clean fixture revision",
        )
        rebaseline = run_cli(
            "audit", "rebaseline", str(self.workspace),
            "--actor", "Research Owner", "--reason", "A new committed revision needs a new case.",
        )
        self.assertEqual(rebaseline.returncode, 0, rebaseline.stderr)
        status = run_cli("audit", "status", str(self.workspace), "--json")
        self.assertEqual(status.returncode, 0, status.stderr)
        status_payload = json.loads(status.stdout)
        self.assertEqual(status_payload["content_binding_state"], "stale")
        self.assertEqual(status_payload["summary"]["stale_finding_count"], 1)
        listed = run_cli("audit", "finding", "list", str(self.workspace), "--json")
        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assertEqual(json.loads(listed.stdout)["findings"][0]["case_state"], "stale")
        new_gate = run_cli(
            "audit", "gate", "record", str(self.workspace),
            "--decision", "approved", "--reviewer", "Research Owner",
            "--rationale", "The new clean revision was reviewed as a separate case.",
        )
        self.assertEqual(new_gate.returncode, 0, new_gate.stderr)
        current_status = run_cli("audit", "status", str(self.workspace), "--json")
        self.assertEqual(current_status.returncode, 0, current_status.stderr)
        self.assertEqual(json.loads(current_status.stdout)["content_binding_state"], "current")
        stale_import = run_cli(
            "audit", "evidence", "import", str(self.workspace),
            "--finding", "F-001", "--id", "E-STALE", "--type", "artifact",
            "--kind", "observed", "--source-kind", "project-relative",
            "--source-path", "README.md", "--artifact-role", "source-under-review",
            "--summary", "Old finding must not accept new-case source bytes.",
            "--actor", "CLI Auditor",
        )
        self.assertEqual(stale_import.returncode, 1)
        self.assertIn("older baseline", stale_import.stderr)
        self.assertEqual(self._git("status", "--porcelain"), "")

    def test_explicit_train_and_audit_help_are_available(self) -> None:
        train = run_cli("train", "start", "--level", "1")
        self.assertEqual(train.returncode, 0, train.stderr)
        self.assertIn("Level 1: Algorithm semantics", train.stdout)

        audit = run_cli("audit", "--help")
        self.assertEqual(audit.returncode, 0, audit.stderr)
        for command in (
            "init",
            "status",
            "gate",
            "preflight",
            "finding",
            "evidence",
            "verify",
            "recover",
            "report",
        ):
            self.assertIn(command, audit.stdout)
        self.assertIn("project code", audit.stdout)
        self.assertIn("scientific verdict", audit.stdout)

    def test_real_audit_cli_completes_a_review_record(self) -> None:
        original_head = self._git("rev-parse", "HEAD")
        original_status = self._git("status", "--porcelain")
        original_readme = (self.project / "README.md").read_bytes()
        self._initialize_bound_workspace()
        self._complete_templates()

        recovery = run_cli("audit", "recover", str(self.workspace), "--json")
        self.assertEqual(recovery.returncode, 0, recovery.stderr)
        recovery_payload = json.loads(recovery.stdout)
        self.assertEqual(recovery_payload["operation_status"], "clean")
        self.assertEqual(
            recovery_payload["assessment_status"], "local-records-consistent"
        )
        self.assertFalse(recovery_payload["recovery"]["recovered"])

        gate_check = run_cli("audit", "gate", "check", str(self.workspace), "--json")
        self.assertEqual(gate_check.returncode, 1, gate_check.stderr)
        gate_check_payload = json.loads(gate_check.stdout)
        self.assertEqual(gate_check_payload["assessment_status"], "needs-human-decision")
        self.assertFalse(gate_check_payload["g0"]["g0_prerequisites_met"])

        gate_record = run_cli(
            "audit",
            "gate",
            "record",
            str(self.workspace),
            "--decision",
            "approved",
            "--reviewer",
            "Research Owner",
            "--rationale",
            "The bounded contract and protected evaluation rules were reviewed.",
        )
        self.assertEqual(gate_record.returncode, 0, gate_record.stderr)

        gate_check = run_cli("audit", "gate", "check", str(self.workspace), "--json")
        self.assertEqual(gate_check.returncode, 0, gate_check.stderr)
        gate_check_payload = json.loads(gate_check.stdout)
        self.assertEqual(
            gate_check_payload["assessment_status"], "g0-prerequisites-met"
        )
        self.assertTrue(gate_check_payload["g0"]["g0_prerequisites_met"])

        preflight = run_cli("audit", "preflight", str(self.workspace), "--json")
        self.assertEqual(preflight.returncode, 0, preflight.stderr)
        self.assertEqual(
            json.loads(preflight.stdout)["assessment_status"],
            "preflight-passed",
        )

        finding = run_cli(
            "audit",
            "finding",
            "add",
            str(self.workspace),
            "--id",
            "F-001",
            "--title",
            "Checkpoint lineage requires review",
            "--layer",
            "L2",
            "--competency",
            "C2",
            "--severity",
            "medium",
            "--claim",
            "The reported model may not match the declared checkpoint lineage.",
            "--first-contract",
            "Each reported run must identify the evaluated checkpoint.",
            "--actor",
            "CLI Auditor",
        )
        self.assertEqual(finding.returncode, 0, finding.stderr)
        self.assertIn("declared lifecycle state=open", finding.stdout)

        evidence = run_cli(
            "audit",
            "evidence",
            "add",
            str(self.workspace),
            "--finding",
            "F-001",
            "--id",
            "E-001",
            "--kind",
            "observed",
            "--reference",
            "configs/eval.yaml@HEAD",
            "--summary",
            "The evaluation configuration names no checkpoint digest.",
            "--actor",
            "CLI Auditor",
        )
        self.assertEqual(evidence.returncode, 0, evidence.stderr)

        verification = run_cli("audit", "verify", str(self.workspace), "--json")
        self.assertEqual(verification.returncode, 0, verification.stderr)
        self.assertEqual(
            json.loads(verification.stdout)["assessment_status"],
            "local-records-consistent",
        )

        report_path = self.workspace / "review.md"
        report = run_cli(
            "audit",
            "report",
            "build",
            str(self.workspace),
            "--output",
            str(report_path),
            "--format",
            "markdown",
        )
        self.assertEqual(report.returncode, 0, report.stderr)
        self.assertIn("not a scientific PASS", report.stdout)
        report_text = report_path.read_text(encoding="utf-8")
        self.assertIn("Report status: **PREFLIGHT-CURRENT**", report_text)
        self.assertIn("Declared lifecycle state", report_text)
        self.assertIn("declared lifecycle labels", report_text)
        if os.name == "posix":
            self.assertEqual(report_path.stat().st_mode & 0o777, 0o600)

        duplicate_report = run_cli(
            "audit",
            "report",
            "build",
            str(self.workspace),
            "--output",
            str(report_path),
        )
        self.assertEqual(duplicate_report.returncode, 1)
        self.assertIn("Refusing to overwrite", duplicate_report.stderr)

        outside_report = self.root / "outside-report.md"
        refused_report = run_cli(
            "audit",
            "report",
            "build",
            str(self.workspace),
            "--output",
            str(outside_report),
        )
        self.assertEqual(refused_report.returncode, 1)
        self.assertFalse(outside_report.exists())

        for reserved_report in (
            self.workspace / "findings" / "report.md",
            self.workspace / ".rcsl-write.lock",
            self.workspace / ".RCSL-WRITE.LOCK",
            self.workspace / ".rcsl-audit-pending.json",
            self.workspace / ".RCSL-AUDIT-PENDING.JSON",
        ):
            existed_before = os.path.lexists(reserved_report)
            bytes_before = (
                reserved_report.read_bytes()
                if reserved_report.is_file() and not reserved_report.is_symlink()
                else None
            )
            refused_reserved = run_cli(
                "audit",
                "report",
                "build",
                str(self.workspace),
                "--output",
                str(reserved_report),
            )
            self.assertEqual(refused_reserved.returncode, 1)
            self.assertEqual(os.path.lexists(reserved_report), existed_before)
            if bytes_before is not None:
                self.assertEqual(reserved_report.read_bytes(), bytes_before)

        isolated_alias = self.root / "do_not_open_until_finished" / "report.md"
        refused_isolated_alias = run_cli(
            "audit",
            "report",
            "build",
            str(self.workspace),
            "--output",
            str(isolated_alias),
        )
        self.assertEqual(refused_isolated_alias.returncode, 2)
        self.assertIn("isolated instructor material", refused_isolated_alias.stderr)

        status = run_cli("audit", "status", str(self.workspace), "--json")
        self.assertEqual(status.returncode, 0, status.stderr)
        status_payload = json.loads(status.stdout)
        self.assertEqual(status_payload["assessment_status"], "preflight-current")
        self.assertEqual(status_payload["summary"]["finding_count"], 1)

        lint = run_cli("audit", "lint", str(self.workspace))
        self.assertEqual(lint.returncode, 0, lint.stdout + lint.stderr)
        self.assertIn("Structure status: COMPLETE", lint.stdout)
        self.assertEqual(self._git("rev-parse", "HEAD"), original_head)
        self.assertEqual(self._git("status", "--porcelain"), original_status)
        self.assertEqual((self.project / "README.md").read_bytes(), original_readme)

    def test_report_workspace_swap_cannot_redirect_or_overwrite_output(self) -> None:
        self._initialize_bound_workspace()
        module = load_rcsl_module()
        displaced = self.root / "displaced-workspace"
        redirect_target = self.root / "report-redirect"
        redirect_target.mkdir()
        report_name = "review-race.md"
        sentinel = redirect_target / report_name
        sentinel.write_text("do not overwrite\n", encoding="utf-8")

        def swap_workspace(_workspace):
            self.workspace.rename(displaced)
            self.workspace.symlink_to(redirect_target, target_is_directory=True)
            return "# Rendered report\n"

        with mock.patch.object(
            module.audit_core,
            "render_report_markdown",
            side_effect=swap_workspace,
        ):
            returncode, stdout, stderr = run_module_cli(
                module,
                "audit",
                "report",
                "build",
                str(self.workspace),
                "--output",
                str(self.workspace / report_name),
                "--format",
                "markdown",
            )

        self.assertEqual(returncode, 2)
        self.assertEqual(stdout, "")
        self.assertIn("identity changed", stderr)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "do not overwrite\n")
        self.assertFalse((displaced / report_name).exists())

    def test_bound_lint_rejects_workspace_relocated_inside_ignored_project(self) -> None:
        self._initialize_bound_workspace()
        self._complete_templates()
        relocated = self.project / ".rcsl-audit-workspace"
        exclude = self.project / ".git" / "info" / "exclude"
        exclude.write_text(
            exclude.read_text(encoding="utf-8") + "\n.rcsl-audit-workspace/\n",
            encoding="utf-8",
        )
        self.workspace.rename(relocated)

        result = run_cli("audit", "lint", str(relocated))

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertIn("outside the bound Git project", result.stderr)
        self.assertEqual(self._git("status", "--porcelain"), "")

    def test_bound_lint_fails_closed_while_a_commit_is_pending(self) -> None:
        self._initialize_bound_workspace()
        pending = self.workspace / ".rcsl-audit-pending.json"
        pending.write_text("{}\n", encoding="utf-8")

        result = run_cli("audit", "lint", str(self.workspace))

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertIn("audit recover", result.stderr)

    def test_dirty_project_is_refused_before_workspace_creation(self) -> None:
        (self.project / "dirty.txt").write_text("uncommitted\n", encoding="utf-8")
        result = run_cli(
            "audit",
            "init",
            "--project",
            str(self.project),
            "--output",
            str(self.workspace),
            "--level",
            "1",
            "--actor",
            "CLI Auditor",
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("project must be clean", result.stderr)
        self.assertFalse(self.workspace.exists())

    def test_case_variant_inside_project_is_refused_before_creation(self) -> None:
        case_variant_project = self.project.with_name(self.project.name.swapcase())
        apparent_workspace = case_variant_project / "audit-case-alias"
        result = run_cli(
            "audit",
            "init",
            "--project",
            str(self.project),
            "--output",
            str(apparent_workspace),
            "--level",
            "1",
            "--actor",
            "CLI Auditor",
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("outside the bound Git project", result.stderr)
        self.assertFalse((self.project / "audit-case-alias").exists())


if __name__ == "__main__":
    unittest.main()
