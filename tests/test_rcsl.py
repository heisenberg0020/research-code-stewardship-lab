from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
import re
import subprocess
import sys
import tempfile
import unittest
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
        result = run_cli("overview")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Make runnable research code auditable", result.stdout)
        self.assertIn("start --level 1", result.stdout)
        self.assertIn("validate", result.stdout)
        self.assertIn("init-audit", result.stdout)

    def test_doctor_reports_python_and_torch_status(self) -> None:
        result = run_cli("doctor")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Python:", result.stdout)
        self.assertIn("torch:", result.stdout)

    def test_start_only_lists_public_level_materials(self) -> None:
        result = run_cli("start", "--level", "1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Level 1: Algorithm semantics", result.stdout)
        self.assertIn("level_1_algorithm_semantics/PAPER_MAP.md", result.stdout)
        self.assertIn("run_smoke.py", result.stdout)

    def test_legacy_install_skill_dry_run_still_works(self) -> None:
        result = run_cli("install-skill", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Dry run only", result.stdout)

    def test_help_explains_old_and_new_commands(self) -> None:
        result = run_cli("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        for command in (
            "overview",
            "doctor",
            "start",
            "install-skill",
            "init-audit",
            "lint-audit",
            "status-audit",
        ):
            self.assertIn(command, result.stdout)

    def test_invalid_level_is_rejected(self) -> None:
        result = run_cli("start", "--level", "5")
        self.assertEqual(result.returncode, 2)
        self.assertIn("invalid choice", result.stderr)

    def test_real_public_templates_create_a_local_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "audit"
            result = run_cli(
                "init-audit",
                "--level",
                "2",
                "--output",
                str(workspace),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Created public audit workspace", result.stdout)
            self.assertTrue((workspace / "research-contract-template.md").is_file())
            metadata = json.loads((workspace / "audit-workspace.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["level"], 2)
            self.assertEqual(metadata["validator_scope"], "structural_only")

            for filename in metadata["template_files"]:
                path = workspace / filename
                completed = re.sub(
                    r"\{\{[^{}\n]+\}\}",
                    "Documented evidence",
                    path.read_text(encoding="utf-8"),
                )
                path.write_text(completed, encoding="utf-8")
            lint_result = run_cli("lint-audit", str(workspace))
            self.assertEqual(lint_result.returncode, 0, lint_result.stdout + lint_result.stderr)
            self.assertIn("Structure status: COMPLETE", lint_result.stdout)


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
        returncode, stdout, stderr = run_module_cli(
            self.module,
            "init-audit",
            "--level",
            "1",
            "--output",
            str(workspace),
        )
        self.assertEqual(returncode, 0, stderr)
        self.assertIn("Created public audit workspace", stdout)
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

        returncode, stdout, stderr = run_module_cli(
            self.module,
            "init-audit",
            "--level",
            "1",
            "--output",
            str(workspace),
        )

        self.assertEqual(returncode, 1)
        self.assertEqual(stdout, "")
        self.assertIn("Refusing to overwrite", stderr)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "unchanged")

    def test_incomplete_workspace_fails_lint_but_status_reports_progress(self) -> None:
        workspace = self.initialize_workspace()

        returncode, stdout, stderr = run_module_cli(self.module, "lint-audit", str(workspace))
        self.assertEqual(returncode, 1, stderr)
        self.assertIn("Structure status: INCOMPLETE", stdout)
        self.assertIn("unresolved template placeholders", stdout)

        returncode, stdout, stderr = run_module_cli(self.module, "status-audit", str(workspace))
        self.assertEqual(returncode, 0, stderr)
        self.assertIn("Template progress: 0/4", stdout)

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

        returncode, stdout, stderr = run_module_cli(self.module, "lint-audit", str(workspace))
        self.assertEqual(returncode, 0, stderr)
        self.assertIn("Template progress: 4/4", stdout)
        self.assertIn("Structure status: COMPLETE", stdout)
        self.assertIn("does not judge research or scientific correctness", stdout)

    def test_isolated_path_is_refused_before_workspace_creation(self) -> None:
        workspace = self.root / self.module.ISOLATED_DIRECTORY_NAME / "audit"
        returncode, stdout, stderr = run_module_cli(
            self.module,
            "init-audit",
            "--level",
            "1",
            "--output",
            str(workspace),
        )
        self.assertEqual(returncode, 2)
        self.assertEqual(stdout, "")
        self.assertIn("isolated instructor-material path", stderr)
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
        returncode, stdout, stderr = run_module_cli(
            self.module,
            "init-audit",
            "--level",
            "1",
            "--output",
            str(workspace),
        )
        self.assertEqual(returncode, 2)
        self.assertEqual(stdout, "")
        self.assertIn("resolves into isolated instructor material", stderr)
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

    def test_explicit_train_and_audit_help_are_available(self) -> None:
        train = run_cli("train", "start", "--level", "1")
        self.assertEqual(train.returncode, 0, train.stderr)
        self.assertIn("Level 1: Algorithm semantics", train.stdout)

        audit = run_cli("audit", "--help")
        self.assertEqual(audit.returncode, 0, audit.stderr)
        for command in ("init", "status", "gate", "preflight", "finding", "evidence", "verify", "report"):
            self.assertIn(command, audit.stdout)
        self.assertIn("project code", audit.stdout)
        self.assertIn("scientific verdict", audit.stdout)

    def test_real_audit_cli_completes_a_review_record(self) -> None:
        original_head = self._git("rev-parse", "HEAD")
        original_status = self._git("status", "--porcelain")
        original_readme = (self.project / "README.md").read_bytes()
        self._initialize_bound_workspace()
        self._complete_templates()

        gate_check = run_cli("audit", "gate", "check", str(self.workspace), "--json")
        self.assertEqual(gate_check.returncode, 1, gate_check.stderr)
        self.assertEqual(json.loads(gate_check.stdout)["assessment_status"], "needs-human-decision")

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

        preflight = run_cli("audit", "preflight", str(self.workspace), "--json")
        self.assertEqual(preflight.returncode, 0, preflight.stderr)
        self.assertEqual(
            json.loads(preflight.stdout)["assessment_status"],
            "ready-for-declared-scope",
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
            json.loads(verification.stdout)["assessment_status"], "ledger-consistent"
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
        self.assertIn("Report status: **REVIEW-READY**", report_path.read_text(encoding="utf-8"))

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
        ):
            refused_reserved = run_cli(
                "audit",
                "report",
                "build",
                str(self.workspace),
                "--output",
                str(reserved_report),
            )
            self.assertEqual(refused_reserved.returncode, 1)
            self.assertFalse(reserved_report.exists())

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
        self.assertEqual(status_payload["assessment_status"], "review-ready")
        self.assertEqual(status_payload["summary"]["finding_count"], 1)

        legacy_lint = run_cli("lint-audit", str(self.workspace))
        self.assertEqual(legacy_lint.returncode, 0, legacy_lint.stdout + legacy_lint.stderr)
        self.assertIn("Structure status: COMPLETE", legacy_lint.stdout)

        self.assertEqual(self._git("rev-parse", "HEAD"), original_head)
        self.assertEqual(self._git("status", "--porcelain"), original_status)
        self.assertEqual((self.project / "README.md").read_bytes(), original_readme)

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
