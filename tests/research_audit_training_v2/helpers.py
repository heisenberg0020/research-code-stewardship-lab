from __future__ import annotations

import hashlib
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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def student_files() -> list[Path]:
    blocked = "DO_NOT_OPEN_UNTIL_FINISHED"
    return sorted(
        path
        for path in V2.rglob("*")
        if path.is_file() and blocked not in path.parts and "__pycache__" not in path.parts
    )


def tree_digest(paths: list[Path]) -> dict[str, str]:
    return {str(path.relative_to(ROOT)): sha256(path) for path in paths}
