#!/usr/bin/env python3
"""Static structural and leakage checks for a four-level audit package."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


LEVELS = (
    "level_1_algorithm_semantics",
    "level_2_pipeline_integrity",
    "level_3_scientific_validity",
    "level_4_agent_experiment_governance",
)
LETTERS = tuple("ABCDE")
TEXT_SUFFIXES = {".py", ".md", ".json", ".jsonl", ".csv", ".yaml", ".yml"}
LEAK = re.compile(
    r"trusted_candidate|correct candidate|known fault|"
    r"正确候选\s*[:：]|答案\s*[:：]\s*[A-E]",
    re.IGNORECASE,
)


def candidate_container(level: Path) -> Path | None:
    for name in ("candidates", "dossiers", "runs"):
        path = level / name
        if path.is_dir():
            return path
    return None


def validate(root: Path, *, public_export: bool = False) -> list[str]:
    errors: list[str] = []
    if not root.is_dir():
        return [f"not a directory: {root}"]

    for name in (
        "README.md",
        "CASE_FILE.md",
        "CASE_FILE_EN.md",
        "FRAMEWORK_OVERVIEW.md",
        "PROGRESSION.md",
        "CAPSTONE_BRIEF.md",
    ):
        if not (root / name).is_file():
            errors.append(f"missing root file: {name}")

    for level_name in LEVELS:
        level = root / level_name
        if not level.is_dir():
            errors.append(f"missing level: {level_name}")
            continue
        required_level_entries = ["README.md", "ANSWER_SHEET.md"]
        if not public_export:
            required_level_entries.append("DO_NOT_OPEN_UNTIL_FINISHED")
        for name in required_level_entries:
            if not (level / name).exists():
                errors.append(f"{level_name}: missing {name}")
        container = candidate_container(level)
        if container is None:
            errors.append(f"{level_name}: missing candidates/dossiers/runs container")
        else:
            actual = {p.stem if p.is_file() else p.name for p in container.iterdir()}
            missing = set(LETTERS) - actual
            if missing:
                errors.append(f"{level_name}: missing candidate labels {sorted(missing)}")

        hidden = level / "DO_NOT_OPEN_UNTIL_FINISHED"
        if public_export and hidden.exists():
            errors.append(f"{level_name}: public export retains instructor material")
        elif hidden.is_dir() and not (hidden / "answer_manifest.json").is_file():
            errors.append(f"{level_name}: missing isolated answer_manifest.json")

    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if "DO_NOT_OPEN_UNTIL_FINISHED" in path.parts or "__pycache__" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if LEAK.search(text):
            errors.append(f"possible answer leak: {path.relative_to(root)}")
        if "DO_NOT_OPEN_UNTIL_FINISHED" in text and path.name in {
            "verify_package.py",
            "run_all_public_checks.py",
        }:
            errors.append(f"public verifier references hidden material: {path.relative_to(root)}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--public-export",
        action="store_true",
        help="Validate an exported learner surface where instructor directories must be absent.",
    )
    parser.add_argument("package", type=Path)
    args = parser.parse_args()
    errors = validate(args.package.resolve(), public_export=args.public_export)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("PASS: static package structure and public-surface leakage checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
