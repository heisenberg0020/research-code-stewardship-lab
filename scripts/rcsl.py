#!/usr/bin/env python3
"""Public navigation, audit-workspace scaffolding, and checks for RCSL."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TRAINING_ROOT = REPOSITORY_ROOT / "LLM4SBR_research_audit_training_v2"
PUBLIC_CHECK_RUNNER = TRAINING_ROOT / "run_all_public_checks.py"
SKILL_SOURCE = REPOSITORY_ROOT / "skills" / "research-code-audit-training"
ASSET_DIRECTORY = SKILL_SOURCE / "assets"

WORKSPACE_METADATA_NAME = "audit-workspace.json"
WORKSPACE_TEMPLATE_FILENAMES = (
    "research-contract-template.md",
    "evidence-passport-template.md",
    "triage-card-template.md",
    "delegation-contract-template.md",
)
ISOLATED_DIRECTORY_NAME = "DO_NOT_OPEN_UNTIL_FINISHED"
HEADING_PATTERN = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)
PLACEHOLDER_PATTERN = re.compile(
    r"\{\{[^{}\n]+\}\}|\[TODO\]|\[填写\]|待填写|^\s*(?:TODO|TBD)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
CAPABILITIES = {
    "C1": "Research mandate and judgment",
    "C2": "Rapid triage and localization",
    "C3": "Delegation and agent assurance",
    "C4": "Architecture and maintainability",
    "C5": "Security, privacy, and ethics",
    "C6": "Incident response and correction",
    "C7": "Evidence communication",
}
CAPABILITY_IDS = tuple(CAPABILITIES)
MATURITY_BANDS = ("Recognize", "Prove", "Direct", "Steward")


@dataclass(frozen=True)
class LevelGuide:
    """Learner-visible files and one neutral public check for a training level."""

    title: str
    directory: str
    documents: tuple[str, ...]
    command: str


@dataclass
class WorkspaceInspection:
    """Structural findings for a user-created, public audit workspace."""

    workspace: Path
    metadata: dict[str, object] | None
    general_issues: list[str]
    template_issues: dict[str, list[str]]

    @property
    def completed_template_count(self) -> int:
        return sum(not issues for issues in self.template_issues.values())

    @property
    def is_complete(self) -> bool:
        return not self.general_issues and all(
            not issues for issues in self.template_issues.values()
        )


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


def normalized_user_path(value: Path | str) -> Path:
    """Normalize a user path lexically, without resolving or reading its target."""

    expanded = Path(value).expanduser()
    return Path(os.path.abspath(os.fspath(expanded)))


def path_is_isolated(path: Path) -> bool:
    """Reject a path before any filesystem operation reaches instructor material."""

    return ISOLATED_DIRECTORY_NAME in path.parts


def validate_workspace_path(value: Path | str, *, action: str) -> Path | None:
    """Return a safe local workspace path or explain why the request is refused."""

    workspace = normalized_user_path(value)
    if path_is_isolated(workspace):
        print(
            f"Refusing to {action} an isolated instructor-material path.",
            file=sys.stderr,
        )
        return None
    try:
        canonical = workspace.resolve(strict=False)
    except (OSError, RuntimeError) as error:
        print(f"Could not validate audit workspace path: {error}", file=sys.stderr)
        return None
    if path_is_isolated(canonical):
        print(
            f"Refusing to {action} a path that resolves into isolated instructor material.",
            file=sys.stderr,
        )
        return None
    return workspace


def markdown_headings(content: str) -> list[str]:
    """Return stable Markdown heading text in source order."""

    return [
        match.group(1).strip().rstrip("#").strip()
        for match in HEADING_PATTERN.finditer(content)
    ]


def stable_headings(content: str) -> list[str]:
    """Keep the template's fixed structure, not headings that are themselves fields."""

    return [
        heading for heading in markdown_headings(content) if not PLACEHOLDER_PATTERN.search(heading)
    ]


def required_template_sources() -> tuple[tuple[str, Path], ...]:
    """List the only public files an audit workspace is permitted to copy."""

    return tuple((name, ASSET_DIRECTORY / name) for name in WORKSPACE_TEMPLATE_FILENAMES)


def workspace_metadata(
    level_number: int,
    structures: dict[str, list[str]],
    source_hashes: dict[str, str],
) -> dict[str, object]:
    """Build deterministic, learner-visible metadata for a local audit workspace."""

    level = LEVELS[level_number]
    level_root = TRAINING_ROOT / level.directory
    return {
        "schema_version": 1,
        "workspace_type": "rcsl-public-audit-workspace",
        "validator_scope": "structural_only",
        "course": "Research Code Stewardship Lab",
        "reference_case": "LLM4SBR Research Audit Training v2",
        "level": level_number,
        "level_title": level.title,
        "public_level_directory": relative(level_root),
        "public_documents": [relative(level_root / document) for document in level.documents],
        "public_check_command": level.command,
        "template_files": list(WORKSPACE_TEMPLATE_FILENAMES),
        "required_sections": structures,
        "source_template_sha256": source_hashes,
        "capabilities": CAPABILITIES,
        "capability_ids": list(CAPABILITY_IDS),
        "maturity_bands": list(MATURITY_BANDS),
    }


def command_init_audit(level_number: int, output: Path | str) -> int:
    """Create a new local workspace from public templates without overwriting anything."""

    workspace = validate_workspace_path(output, action="create")
    if workspace is None:
        return 2
    if workspace.is_symlink() or workspace.exists():
        print(f"Refusing to overwrite existing path: {workspace}", file=sys.stderr)
        return 1

    sources = required_template_sources()
    missing = [source for _, source in sources if source.is_symlink() or not source.is_file()]
    if missing:
        print("Required public workspace templates are unavailable:", file=sys.stderr)
        for source in missing:
            print(f"  - {relative(source)}", file=sys.stderr)
        print("No workspace was created.", file=sys.stderr)
        return 1

    source_contents: dict[str, str] = {}
    try:
        for name, source in sources:
            source_contents[name] = source.read_text(encoding="utf-8")
    except OSError as error:
        print(f"Could not read a public workspace template: {error}", file=sys.stderr)
        print("No workspace was created.", file=sys.stderr)
        return 1

    structures = {name: stable_headings(content) for name, content in source_contents.items()}
    source_hashes = {
        name: hashlib.sha256(content.encode("utf-8")).hexdigest()
        for name, content in source_contents.items()
    }
    try:
        workspace.mkdir(parents=True, exist_ok=False)
        for name, _ in sources:
            (workspace / name).write_text(source_contents[name], encoding="utf-8")
        (workspace / WORKSPACE_METADATA_NAME).write_text(
            json.dumps(
                workspace_metadata(level_number, structures, source_hashes),
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
    except OSError as error:
        print(f"Could not finish creating audit workspace: {error}", file=sys.stderr)
        print(f"Any newly created files remain at: {workspace}", file=sys.stderr)
        return 1

    print(f"Created public audit workspace: {workspace}")
    print(f"Level {level_number}: {LEVELS[level_number].title}")
    print("Next: replace every double-braced prompt in the four Markdown files.")
    print(f"Progress: python scripts/rcsl.py status-audit {workspace}")
    print(f"Final structure check: python scripts/rcsl.py lint-audit {workspace}")
    return 0


def read_workspace_metadata(path: Path, issues: list[str]) -> dict[str, object] | None:
    """Read only the known public metadata file, never arbitrary workspace content."""

    if path.is_symlink():
        issues.append(f"{WORKSPACE_METADATA_NAME} must not be a symlink")
        return None
    if not path.is_file():
        issues.append(f"missing {WORKSPACE_METADATA_NAME}")
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        issues.append(f"could not read {WORKSPACE_METADATA_NAME}: {error.__class__.__name__}")
        return None
    if not isinstance(payload, dict):
        issues.append(f"{WORKSPACE_METADATA_NAME} must contain a JSON object")
        return None
    return payload


def inspect_audit_workspace(value: Path | str) -> WorkspaceInspection | None:
    """Inspect only explicit public workspace files for structural completeness."""

    workspace = validate_workspace_path(value, action="inspect")
    if workspace is None:
        return None
    if workspace.is_symlink() or not workspace.is_dir():
        print(f"Audit workspace is not a regular directory: {workspace}", file=sys.stderr)
        return None

    general_issues: list[str] = []
    metadata = read_workspace_metadata(workspace / WORKSPACE_METADATA_NAME, general_issues)
    required_sections: dict[str, object] = {}
    if metadata is not None:
        required_keys = (
            "schema_version",
            "workspace_type",
            "validator_scope",
            "course",
            "reference_case",
            "level",
            "level_title",
            "public_level_directory",
            "public_documents",
            "public_check_command",
            "template_files",
            "required_sections",
            "source_template_sha256",
            "capabilities",
            "capability_ids",
            "maturity_bands",
        )
        for key in required_keys:
            if key not in metadata:
                general_issues.append(f"metadata is missing required key: {key}")
        if metadata.get("workspace_type") != "rcsl-public-audit-workspace":
            general_issues.append("metadata workspace_type is not recognized")
        if metadata.get("validator_scope") != "structural_only":
            general_issues.append("metadata validator_scope is not structural_only")
        if metadata.get("schema_version") != 1:
            general_issues.append("metadata schema_version is not supported")
        metadata_level = metadata.get("level")
        if not isinstance(metadata_level, int) or metadata_level not in LEVELS:
            general_issues.append("metadata level is not a supported course level")
        if metadata.get("template_files") != list(WORKSPACE_TEMPLATE_FILENAMES):
            general_issues.append("metadata template_files does not match the public workspace contract")
        if metadata.get("capability_ids") != list(CAPABILITY_IDS):
            general_issues.append("metadata capability_ids does not match the competency model")
        if metadata.get("capabilities") != CAPABILITIES:
            general_issues.append("metadata capabilities does not match the competency model")
        if metadata.get("maturity_bands") != list(MATURITY_BANDS):
            general_issues.append("metadata maturity_bands does not match the competency model")
        source_hashes = metadata.get("source_template_sha256")
        hashes_are_valid = isinstance(source_hashes, dict) and set(source_hashes) == set(
            WORKSPACE_TEMPLATE_FILENAMES
        )
        if hashes_are_valid:
            hashes_are_valid = all(
                isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
                for value in source_hashes.values()
            )
        if not hashes_are_valid:
            general_issues.append("metadata source_template_sha256 is incomplete")
        candidate_sections = metadata.get("required_sections")
        if isinstance(candidate_sections, dict):
            required_sections = candidate_sections
        else:
            general_issues.append("metadata required_sections must be an object")

    template_issues: dict[str, list[str]] = {}
    for filename in WORKSPACE_TEMPLATE_FILENAMES:
        issues: list[str] = []
        template = workspace / filename
        if template.is_symlink():
            issues.append("must not be a symlink")
        elif not template.is_file():
            issues.append("missing expected workspace file")
        else:
            try:
                content = template.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as error:
                issues.append(f"could not read file: {error.__class__.__name__}")
            else:
                headings = markdown_headings(content)
                if not content.strip():
                    issues.append("file is empty")
                if not headings:
                    issues.append("missing a Markdown heading")
                if PLACEHOLDER_PATTERN.search(content):
                    issues.append("contains unresolved template placeholders")
                expected_sections = required_sections.get(filename)
                if not isinstance(expected_sections, list):
                    issues.append("metadata is missing the template's required section list")
                else:
                    for section in expected_sections:
                        if not isinstance(section, str) or not section.strip():
                            issues.append("metadata contains an invalid required section")
                            break
                        if section not in headings:
                            issues.append(f"missing required section: {section}")
        template_issues[filename] = issues

    return WorkspaceInspection(
        workspace=workspace,
        metadata=metadata,
        general_issues=general_issues,
        template_issues=template_issues,
    )


def print_workspace_inspection(inspection: WorkspaceInspection) -> None:
    """Render a structural-only status report for a public audit workspace."""

    total = len(WORKSPACE_TEMPLATE_FILENAMES)
    print(f"Audit workspace: {inspection.workspace}")
    if inspection.metadata is not None:
        level = inspection.metadata.get("level")
        title = inspection.metadata.get("level_title")
        if isinstance(level, int) and isinstance(title, str):
            print(f"Course level: {level} · {title}")
    print(f"Template progress: {inspection.completed_template_count}/{total} structurally complete")

    if inspection.is_complete:
        print("Structure status: COMPLETE")
    else:
        print("Structure status: INCOMPLETE")
        for issue in inspection.general_issues:
            print(f"  - workspace: {issue}")
        for filename, issues in inspection.template_issues.items():
            for issue in issues:
                print(f"  - {filename}: {issue}")
    print("This checks workspace structure only; it does not judge research or scientific correctness.")


def command_lint_audit(workspace_path: Path | str) -> int:
    """Return nonzero for an incomplete local audit workspace."""

    inspection = inspect_audit_workspace(workspace_path)
    if inspection is None:
        return 2
    print_workspace_inspection(inspection)
    return 0 if inspection.is_complete else 1


def command_status_audit(workspace_path: Path | str) -> int:
    """Show local audit-workspace progress without treating incompleteness as an error."""

    inspection = inspect_audit_workspace(workspace_path)
    if inspection is None:
        return 2
    print_workspace_inspection(inspection)
    return 0


def command_overview() -> int:
    print("Research Code Stewardship Lab")
    print("Make runnable research code auditable before you trust its claims.")
    print()
    print("Choose a route:")
    print("  python scripts/rcsl.py start --level 1   Begin the four-level learner path")
    print("  python scripts/rcsl.py doctor            Check Python and torch availability")
    print("  python scripts/rcsl.py validate          Run all public regression checks")
    print("  python scripts/rcsl.py init-audit --level 1 --output ./my-audit")
    print("                                             Create a local public audit workspace")
    print("  python scripts/rcsl.py lint-audit ./my-audit")
    print("                                             Check its structural completeness")
    print("  python scripts/rcsl.py status-audit ./my-audit")
    print("                                             Show progress without failing on drafts")
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
        description="Public navigation, audit-workspace scaffolding, and verification for RCSL."
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

    init_audit_parser = subcommands.add_parser(
        "init-audit", help="Create a non-overwriting local audit workspace from public templates."
    )
    init_audit_parser.add_argument(
        "--level",
        type=int,
        choices=tuple(LEVELS),
        required=True,
        help="Course level this audit workspace supports (1 through 4).",
    )
    init_audit_parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="New local directory to create. It must not already exist.",
    )

    lint_audit_parser = subcommands.add_parser(
        "lint-audit", help="Check a local audit workspace for structural completeness."
    )
    lint_audit_parser.add_argument("workspace", type=Path, help="Audit workspace directory to inspect.")

    status_audit_parser = subcommands.add_parser(
        "status-audit", help="Show structural progress for a local audit workspace."
    )
    status_audit_parser.add_argument("workspace", type=Path, help="Audit workspace directory to inspect.")

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
    if args.command == "init-audit":
        return command_init_audit(args.level, args.output)
    if args.command == "lint-audit":
        return command_lint_audit(args.workspace)
    if args.command == "status-audit":
        return command_status_audit(args.workspace)
    if args.command == "validate":
        return command_validate()
    if args.command == "install-skill":
        return command_install_skill()
    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
