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


if __name__ == "__main__":
    unittest.main()
