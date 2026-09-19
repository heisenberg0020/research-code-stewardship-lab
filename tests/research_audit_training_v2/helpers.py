from __future__ import annotations

import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
V2 = ROOT / "LLM4SBR_research_audit_training_v2"
PYTHON = ("conda", "run", "-n", "ml", "python")


def run_python(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["CUDA_VISIBLE_DEVICES"] = ""
    return subprocess.run(
        (*PYTHON, *args),
        cwd=cwd or ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def student_files() -> list[Path]:
    blocked = "DO_NOT_OPEN_UNTIL_FINISHED"
    files: list[Path] = []
    for directory, names, filenames in os.walk(V2):
        names[:] = [name for name in names if name not in {blocked, "__pycache__"}]
        root = Path(directory)
        files.extend(root / name for name in filenames)
    return sorted(files)
