#!/usr/bin/env python3
"""A small, public-only command entry point for Research Code Stewardship Lab."""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TRAINING_ROOT = REPOSITORY_ROOT / "LLM4SBR_research_audit_training_v2"
PUBLIC_CHECK_RUNNER = TRAINING_ROOT / "run_all_public_checks.py"
SKILL_SOURCE = REPOSITORY_ROOT / "skills" / "research-code-audit-training"


@dataclass(frozen=True)
class LevelGuide:
    """Learner-visible files and one neutral public check for a training level."""

    title: str
    directory: str
    documents: tuple[str, ...]
    command: str


LEVELS: dict[int, LevelGuide] = {
    1: LevelGuide(
        title="Algorithm semantics",
        directory="level_1_algorithm_semantics",
        documents=("README.md", "PAPER_MAP.md", "ANSWER_SHEET.md"),
        command=(
            "python LLM4SBR_research_audit_training_v2/"
            "level_1_algorithm_semantics/run_smoke.py"
        ),
    ),
    2: LevelGuide(
        title="Pipeline integrity",
        directory="level_2_pipeline_integrity",
        documents=("README.md", "FROZEN_PIPELINE_SPEC.md", "ANSWER_SHEET.md"),
        command=(
            "python LLM4SBR_research_audit_training_v2/"
            "level_2_pipeline_integrity/run_smoke.py"
        ),
    ),
    3: LevelGuide(
        title="Scientific validity",
        directory="level_3_scientific_validity",
        documents=("README.md", "REVIEW_CRITERIA.md", "ANSWER_SHEET.md"),
        command=(
            "python LLM4SBR_research_audit_training_v2/"
            "level_3_scientific_validity/validate_evidence_schema.py"
        ),
    ),
    4: LevelGuide(
        title="Agent experiment governance",
        directory="level_4_agent_experiment_governance",
        documents=("README.md", "FROZEN_PROTOCOL.md", "ANSWER_SHEET.md"),
        command=(
            "python LLM4SBR_research_audit_training_v2/"
            "level_4_agent_experiment_governance/validate_ledger_schema.py"
        ),
    ),
}


def relative(path: Path) -> str:
    """Display repository-local public paths consistently."""

    return path.relative_to(REPOSITORY_ROOT).as_posix()


def command_overview() -> int:
    print("Research Code Stewardship Lab")
    print("Make runnable research code auditable before you trust its claims.")
    print()
    print("Choose a route:")
    print("  python scripts/rcsl.py start --level 1   Begin the four-level learner path")
    print("  python scripts/rcsl.py doctor            Check Python and torch availability")
    print("  python scripts/rcsl.py validate          Run all public regression checks")
    print("  python scripts/rcsl.py install-skill --dry-run")
    print("                                             Preview the optional Codex skill setup")
    print()
    print("Levels: 1 Algorithm semantics · 2 Pipeline integrity ·")
    print("        3 Scientific validity · 4 Agent experiment governance")
    return 0


def command_doctor() -> int:
    print("Research Code Stewardship Lab doctor")
    print(f"Python: {sys.version.split()[0]} ({sys.executable})")

    if importlib.util.find_spec("torch") is None:
        print("torch: unavailable")
        print("Install the learner dependency with: python -m pip install -r requirements.txt")
        return 0

    try:
        torch = importlib.import_module("torch")
    except Exception as error:  # pragma: no cover - depends on a broken local install
        print(f"torch: unavailable ({error.__class__.__name__})")
        print("Reinstall with: python -m pip install -r requirements.txt")
        return 0

    version = getattr(torch, "__version__", "installed")
    print(f"torch: available ({version})")
    return 0


def command_start(level_number: int) -> int:
    level = LEVELS[level_number]
    level_root = TRAINING_ROOT / level.directory

    print(f"Level {level_number}: {level.title}")
    print("Read these public documents:")
    for document in level.documents:
        print(f"  - {relative(level_root / document)}")
    print()
    print("Then run the neutral public check from the repository root:")
    print(f"  {level.command}")
    print()
    print("Use the worksheet above to record your audit evidence before continuing.")
    if level_number < len(LEVELS):
        print(f"Next level: python scripts/rcsl.py start --level {level_number + 1}")
    else:
        print("Course check: python scripts/rcsl.py validate")
    return 0


def command_validate() -> int:
    if not PUBLIC_CHECK_RUNNER.is_file():
        print(f"Public check runner is missing: {relative(PUBLIC_CHECK_RUNNER)}", file=sys.stderr)
        return 1

    print("Running the four learner-visible regression checks…", flush=True)
    result = subprocess.run(
        [sys.executable, str(PUBLIC_CHECK_RUNNER)],
        cwd=REPOSITORY_ROOT,
        check=False,
    )
    return result.returncode


def command_install_skill() -> int:
    destination = "~/.codex/skills/research-code-audit-training"
    print("Dry run only — no files changed.")
    print(f"Source: {relative(SKILL_SOURCE)}")
    print(f"Destination: {destination}")
    print("To install manually, copy the source directory to the destination's parent directory.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Public-only navigation and verification for Research Code Stewardship Lab."
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    subcommands.add_parser("overview", help="Show the available learner routes.")
    subcommands.add_parser("doctor", help="Show Python and torch availability.")
    subcommands.add_parser("validate", help="Run all public regression checks.")

    start_parser = subcommands.add_parser("start", help="Show public materials for one level.")
    start_parser.add_argument(
        "--level",
        type=int,
        choices=tuple(LEVELS),
        required=True,
        help="Training level to begin (1 through 4).",
    )

    install_parser = subcommands.add_parser(
        "install-skill", help="Preview installation of the optional Codex skill."
    )
    install_parser.add_argument(
        "--dry-run",
        action="store_true",
        required=True,
        help="Preview only; this command never changes files.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "overview":
        return command_overview()
    if args.command == "doctor":
        return command_doctor()
    if args.command == "start":
        return command_start(args.level)
    if args.command == "validate":
        return command_validate()
    if args.command == "install-skill":
        return command_install_skill()
    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
