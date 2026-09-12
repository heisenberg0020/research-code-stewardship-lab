from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "rcsl.py"


def run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *arguments],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


class RcslCommandTests(unittest.TestCase):
    def test_overview_orients_new_learners(self) -> None:
        result = run_cli("overview")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Make runnable research code auditable", result.stdout)
        self.assertIn("start --level 1", result.stdout)
        self.assertIn("validate", result.stdout)

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

    def test_help_explains_the_available_commands(self) -> None:
        result = run_cli("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("overview", result.stdout)
        self.assertIn("doctor", result.stdout)
        self.assertIn("start", result.stdout)
        self.assertIn("install-skill", result.stdout)

    def test_invalid_level_is_rejected(self) -> None:
        result = run_cli("start", "--level", "5")
        self.assertEqual(result.returncode, 2)
        self.assertIn("invalid choice", result.stderr)


if __name__ == "__main__":
    unittest.main()
