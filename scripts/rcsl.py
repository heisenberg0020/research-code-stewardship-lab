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
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from stewardship_lab import audit as audit_core
from stewardship_lab import release as release_core
from stewardship_lab import training as training_core


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

    isolated_name = ISOLATED_DIRECTORY_NAME.casefold()
    return any(part.casefold() == isolated_name for part in path.parts)


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
    try:
        parent = workspace.parent.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        print(
            f"Audit workspace parent must already exist and be accessible: {error}",
            file=sys.stderr,
        )
        return 1
    if not parent.is_dir():
        print("Audit workspace parent must be a directory.", file=sys.stderr)
        return 1
    workspace = parent / workspace.name
    if path_is_isolated(workspace):
        print(
            "Refusing to create a workspace inside isolated instructor material.",
            file=sys.stderr,
        )
        return 2
    if os.path.lexists(workspace):
        print(f"Refusing to overwrite existing path: {workspace}", file=sys.stderr)
        return 1

    sources = required_template_sources()
    source_contents: dict[str, str] = {}
    try:
        for name, source in sources:
            source_contents[name] = release_core._read_regular_path(
                source,
                label=f"public workspace template {name}",
                maximum_bytes=release_core.MAX_MANIFEST_BYTES,
            ).decode("utf-8")
    except (OSError, UnicodeDecodeError, release_core.ReleaseError) as error:
        print(f"Could not read a public workspace template: {error}", file=sys.stderr)
        print("No workspace was created.", file=sys.stderr)
        return 1

    structures = {name: stable_headings(content) for name, content in source_contents.items()}
    source_hashes = {
        name: hashlib.sha256(content.encode("utf-8")).hexdigest()
        for name, content in source_contents.items()
    }
    metadata_bytes = (
        json.dumps(
            workspace_metadata(level_number, structures, source_hashes),
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")
    owned: release_core.OwnedOutput | None = None
    try:
        owned = release_core._create_owned_output(workspace)
        for name, _ in sources:
            release_core._write_file_at(
                owned.descriptor,
                name,
                source_contents[name].encode("utf-8"),
            )
        release_core._write_file_at(
            owned.descriptor,
            WORKSPACE_METADATA_NAME,
            metadata_bytes,
        )
        os.fsync(owned.descriptor)
        release_core._assert_owned_output_identity(owned)
    except (OSError, release_core.ReleaseError) as error:
        if owned is not None:
            release_core._cleanup_owned_output(owned)
            release_core._close_owned_output(owned)
        print(f"Could not finish creating audit workspace: {error}", file=sys.stderr)
        print("No existing file was overwritten.", file=sys.stderr)
        return 1
    release_core._close_owned_output(owned)

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
        if type(metadata.get("schema_version")) is not int or metadata.get(
            "schema_version"
        ) not in (1, audit_core.SCHEMA_VERSION):
            general_issues.append("metadata schema_version is not supported")
        metadata_level = metadata.get("level")
        if type(metadata_level) is not int or metadata_level not in LEVELS:
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
        if type(level) is int and isinstance(title, str):
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


def command_overview() -> int:
    print("Research Code Stewardship Lab")
    print("Make runnable research code auditable before you trust its claims.")
    print()
    print("Choose an explicit mode:")
    print("  python scripts/rcsl.py train start --level 1")
    print("                                             Begin the human audit curriculum")
    print("  python scripts/rcsl.py train progress init --help")
    print("                                             Keep resumable attempts and human reviews")
    print("  python scripts/rcsl.py train validate    Run learner-visible public checks")
    print("  python scripts/rcsl.py audit --help      Audit a real, clean Git project")
    print()
    print("Levels: 1 Algorithm semantics · 2 Pipeline integrity ·")
    print("        3 Scientific validity · 4 Agent experiment governance · cross-layer Capstone")
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
        print(f"Next level: python scripts/rcsl.py train start --level {level_number + 1}")
    else:
        print("Course check: python scripts/rcsl.py train validate")
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


AUDIT_OUTPUT_LIMITATIONS = (
    "This checks local records and declared human decisions only; it is not a scientific verdict.",
    "Actor and reviewer names are labels, not authenticated identities or signatures.",
    "No audited-project code is executed and no network resource is fetched.",
)


def _path_is_within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        child_parts = tuple(part.casefold() for part in child.parts)
        parent_parts = tuple(part.casefold() for part in parent.parts)
        return (
            len(child_parts) >= len(parent_parts)
            and child_parts[: len(parent_parts)] == parent_parts
        )


def _print_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def command_audit_init(
    project: Path | str,
    output: Path | str,
    level_number: int,
    actor: str,
    reason: str,
) -> int:
    """Create a template workspace and bind it to one clean Git revision."""

    workspace = validate_workspace_path(output, action="create")
    if workspace is None:
        return 2
    snapshot = audit_core.inspect_clean_project(project)
    project_root = Path(str(snapshot["project_root"])).resolve()
    workspace_target = workspace.resolve(strict=False)
    if _path_is_within(workspace_target, project_root) or _path_is_within(
        project_root, workspace_target
    ):
        print("Audit workspace must be outside the bound Git project.", file=sys.stderr)
        return 1
    created = command_init_audit(level_number, workspace)
    if created:
        return created
    try:
        metadata = audit_core.bind_audit(
            project,
            workspace,
            actor=actor,
            rationale=reason,
        )
    except audit_core.AuditError:
        print(
            f"Public templates were created at {workspace}, but project binding failed. "
            "They were not overwritten or removed.",
            file=sys.stderr,
        )
        raise
    lifecycle = metadata["audit_lifecycle"]
    baseline = lifecycle["baseline"] if isinstance(lifecycle, dict) else {}
    print(f"Audit workspace CREATED: {workspace}")
    print(f"Bound read-only project: {project_root}")
    print(f"Baseline HEAD: {baseline.get('head') if isinstance(baseline, dict) else 'unknown'}")
    print("G0 decision: DRAFT")
    print("Next: complete research-contract-template.md, then record a named G0 decision.")
    print("No project code was executed, no network resource was fetched, and the project was not modified.")
    return 0


def command_audit_status(workspace: Path | str, *, as_json: bool) -> int:
    report = audit_core.build_report_data(workspace)
    verification = report["verification"]
    summary = report["summary"]
    gate = report["g0_gate"]
    if not isinstance(verification, dict) or not isinstance(summary, dict) or not isinstance(gate, dict):
        raise audit_core.AuditError("audit status data is invalid")
    payload: dict[str, object] = {
        "schema_version": 1,
        "operation_status": "read",
        "assessment_status": report["report_status"],
        "scope": report["validator_scope"],
        "limitations": report["limitations"],
        "workspace": verification["workspace"],
        "project": report["project"],
        "baseline": report["baseline"],
        "g0_gate": gate,
        "summary": summary,
        "event_count": verification["event_count"],
        "preflight_issue": report["preflight_issue"],
    }
    if as_json:
        _print_json(payload)
        return 0
    print(f"Audit workspace: {payload['workspace']}")
    print(f"G0 declared status: {str(gate.get('status')).upper()}")
    print(f"Findings: {summary.get('finding_count')} total · {summary.get('stale_finding_count')} stale")
    print(f"Ledger: CONSISTENT ({payload['event_count']} retained local events)")
    print(f"Report state: {str(payload['assessment_status']).upper()}")
    if payload["preflight_issue"]:
        print(f"Preflight: NOT READY — {payload['preflight_issue']}")
    else:
        print("Preflight: READY for the declared, human-approved scope")
    print(AUDIT_OUTPUT_LIMITATIONS[0])
    return 0


def command_audit_gate_check(workspace: Path | str, *, as_json: bool) -> int:
    assessment = audit_core.assess_g0_gate(workspace)
    payload = {
        "schema_version": 1,
        "operation_status": "read",
        "assessment_status": (
            "ready-for-preflight" if assessment["ready_for_preflight"] else "needs-human-decision"
        ),
        "scope": "G0 contract structure and declared-decision freshness only",
        "limitations": [assessment["limitation"]],
        "g0": assessment,
    }
    if as_json:
        _print_json(payload)
    else:
        print(f"G0 contract structure: {str(assessment['contract_structure']).upper()}")
        print(f"G0 declared status: {str(assessment['declared_status']).upper()}")
        print(
            "Decision matches current contract: "
            f"{'YES' if assessment['decision_matches_contract'] else 'NO'}"
        )
        print(f"Gate assessment: {str(payload['assessment_status']).upper()}")
        print(str(assessment["limitation"]))
    return 0 if assessment["ready_for_preflight"] else 1


def command_audit_gate_record(
    workspace: Path | str,
    decision: str,
    reviewer: str,
    rationale: str,
    actor: str | None,
) -> int:
    gate = audit_core.set_g0_gate(
        workspace,
        decision,
        reviewer=reviewer,
        rationale=rationale,
        actor=actor or reviewer,
    )
    print(f"G0 decision RECORDED: {str(gate['status']).upper()}")
    print(f"Declared reviewer: {gate['reviewer']}")
    print(AUDIT_OUTPUT_LIMITATIONS[1])
    return 0


def command_audit_preflight(workspace: Path | str, *, as_json: bool) -> int:
    result = audit_core.preflight(workspace)
    payload = {
        "schema_version": 1,
        "operation_status": "checked",
        "assessment_status": "ready-for-declared-scope",
        "scope": "clean Git baseline, current contract digest, declared G0 approval, and ledger integrity",
        "limitations": list(AUDIT_OUTPUT_LIMITATIONS),
        "preflight": result,
    }
    if as_json:
        _print_json(payload)
    else:
        print("Preflight: READY FOR DECLARED SCOPE")
        print(f"Baseline HEAD: {result['baseline']['head']}")
        print(AUDIT_OUTPUT_LIMITATIONS[0])
    return 0


def command_audit_rebaseline(
    workspace: Path | str, *, actor: str, reason: str
) -> int:
    baseline = audit_core.rebaseline(workspace, actor=actor, reason=reason)
    print("Baseline REPLACED and previous baseline retained in the local event history.")
    print(f"New HEAD: {baseline['head']}")
    print("G0 decision reset to DRAFT; old findings remain attached to their earlier baseline.")
    return 0


def command_audit_finding_add(args: argparse.Namespace) -> int:
    finding = audit_core.add_finding(
        args.workspace,
        finding_id=args.finding_id,
        title=args.title,
        layer=args.layer,
        competency=args.competency,
        severity=args.severity,
        claim=args.claim,
        first_broken_contract=args.first_contract,
        actor=args.actor,
    )
    print(f"Finding RECORDED: {finding['id']} · {finding['status']}")
    print("This records a claim for review; it does not establish that the claim is correct.")
    return 0


def command_audit_finding_list(workspace: Path | str, *, as_json: bool) -> int:
    report = audit_core.build_report_data(workspace)
    findings = report["findings"]
    if not isinstance(findings, list):
        raise audit_core.AuditError("audit finding list data is invalid")
    if as_json:
        _print_json(
            {
                "schema_version": 1,
                "operation_status": "read",
                "assessment_status": "not-assessed",
                "scope": "recorded finding snapshots",
                "limitations": [AUDIT_OUTPUT_LIMITATIONS[0]],
                "findings": findings,
            }
        )
        return 0
    if not findings:
        print("No findings recorded.")
    for finding in findings:
        print(
            f"{finding['id']} · {finding['layer']} · {finding['severity']} · "
            f"{finding['status']} · {finding['baseline_state']} baseline · {finding['title']}"
        )
    print(AUDIT_OUTPUT_LIMITATIONS[0])
    return 0


def command_audit_evidence_add(args: argparse.Namespace) -> int:
    finding = audit_core.add_evidence(
        args.workspace,
        args.finding,
        evidence_id=args.evidence_id,
        kind=args.kind,
        reference=args.reference,
        summary=args.summary,
        actor=args.actor,
    )
    print(f"Evidence RECORDED for {finding['id']}: {args.evidence_id} · {args.kind}")
    print("Presence in the record does not establish sufficiency, independence, or scientific correctness.")
    return 0


def command_audit_finding_transition(args: argparse.Namespace) -> int:
    finding = audit_core.transition_finding(
        args.workspace,
        args.finding,
        args.to_status,
        actor=args.actor,
        rationale=args.rationale,
    )
    print(f"Finding state RECORDED: {finding['id']} → {finding['status']}")
    print(AUDIT_OUTPUT_LIMITATIONS[0])
    return 0


def command_audit_verify(workspace: Path | str, *, as_json: bool) -> int:
    result = audit_core.verify_audit_workspace(workspace)
    payload = {
        "schema_version": 1,
        "operation_status": "checked",
        "assessment_status": "ledger-consistent",
        "scope": result["validator_scope"],
        "limitations": list(AUDIT_OUTPUT_LIMITATIONS),
        "verification": result,
    }
    if as_json:
        _print_json(payload)
    else:
        print("Ledger and current snapshots: CONSISTENT")
        print(f"Events: {result['event_count']} · Findings: {result['finding_count']}")
        print(f"Findings from an older baseline: {result['stale_finding_count']}")
        print(AUDIT_OUTPUT_LIMITATIONS[0])
    return 0


def command_audit_recover(workspace: Path | str, *, as_json: bool) -> int:
    result = audit_core.recover_audit(workspace)
    payload = {
        "schema_version": 1,
        "operation_status": result["status"],
        "assessment_status": "ledger-consistent",
        "scope": result["verification"]["validator_scope"],
        "limitations": list(AUDIT_OUTPUT_LIMITATIONS),
        "recovery": result,
    }
    if as_json:
        _print_json(payload)
    elif result["recovered"]:
        print(f"Interrupted audit commit RECOVERED: {result['transaction_id']}")
        print(f"Committed event: {result['event_hash']}")
        print(AUDIT_OUTPUT_LIMITATIONS[0])
    else:
        print("Audit workspace is CLEAN; no interrupted commit was present.")
        print(AUDIT_OUTPUT_LIMITATIONS[0])
    return 0


def command_audit_report(
    workspace_value: Path | str, output_value: Path | str, report_format: str
) -> int:
    workspace = validate_workspace_path(workspace_value, action="read")
    if workspace is None or not workspace.is_dir() or workspace.is_symlink():
        return 2
    output = normalized_user_path(output_value)
    if path_is_isolated(output) or path_is_isolated(output.resolve(strict=False)):
        print("Refusing to write a report into isolated instructor material.", file=sys.stderr)
        return 2
    if output.is_symlink() or output.exists():
        print(f"Refusing to overwrite existing report: {output}", file=sys.stderr)
        return 1
    parent = output.parent
    if parent.is_symlink() or not parent.is_dir():
        print(f"Report parent must be an existing regular directory: {parent}", file=sys.stderr)
        return 2
    workspace_root = workspace.resolve()
    try:
        output_parent = output.parent.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        print(f"Could not resolve report parent: {error}", file=sys.stderr)
        return 2
    if output_parent != workspace_root:
        print(
            "Report output must be a direct child of the audit workspace root.",
            file=sys.stderr,
        )
        return 1
    reserved_names = {
        ".rcsl-write.lock",
        audit_core.PENDING_COMMIT_NAME,
        WORKSPACE_METADATA_NAME,
        audit_core.EVENT_LOG_NAME,
        *WORKSPACE_TEMPLATE_FILENAMES,
    }
    reserved_names_casefolded = {name.casefold() for name in reserved_names}
    if output.name.casefold() in reserved_names_casefolded:
        print(f"Report filename is reserved by the audit workspace: {output.name}", file=sys.stderr)
        return 1
    parent_descriptor: int | None = None
    workspace_descriptor: int | None = None
    report_descriptor: int | None = None
    created = False
    try:
        parent_descriptor = release_core._open_directory_chain(workspace_root.parent)
        before = os.stat(
            workspace_root.name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        workspace_descriptor = os.open(
            workspace_root.name,
            release_core._directory_open_flags(),
            dir_fd=parent_descriptor,
        )
        opened = os.fstat(workspace_descriptor)
        if (
            not stat.S_ISDIR(before.st_mode)
            or (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino)
        ):
            raise release_core.ReleaseError(
                "audit workspace identity changed while preparing the report"
            )

        if report_format == "markdown":
            content = audit_core.render_report_markdown(workspace_root)
        else:
            content = json.dumps(
                audit_core.build_report_data(workspace_root),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ) + "\n"

        current = os.stat(
            workspace_root.name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        if (
            not stat.S_ISDIR(current.st_mode)
            or (current.st_dev, current.st_ino) != (opened.st_dev, opened.st_ino)
        ):
            raise release_core.ReleaseError(
                "audit workspace identity changed while rendering the report"
            )
        report_descriptor = os.open(
            output.name,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            0o600,
            dir_fd=workspace_descriptor,
        )
        created = True
        handle = os.fdopen(report_descriptor, "wb")
        report_descriptor = None
        with handle:
            handle.write(content.encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        os.fsync(workspace_descriptor)
        current = os.stat(
            workspace_root.name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        if (
            not stat.S_ISDIR(current.st_mode)
            or (current.st_dev, current.st_ino) != (opened.st_dev, opened.st_ino)
        ):
            raise release_core.ReleaseError(
                "audit workspace identity changed while writing the report"
            )
    except FileExistsError:
        print(f"Refusing to overwrite existing report: {output}", file=sys.stderr)
        return 1
    except (OSError, release_core.ReleaseError) as error:
        if created and workspace_descriptor is not None:
            try:
                os.unlink(output.name, dir_fd=workspace_descriptor)
            except OSError:
                pass
        print(f"Could not write report: {error}", file=sys.stderr)
        return 2
    finally:
        if report_descriptor is not None:
            os.close(report_descriptor)
        if workspace_descriptor is not None:
            os.close(workspace_descriptor)
        if parent_descriptor is not None:
            os.close(parent_descriptor)
    print(f"Review report CREATED: {output}")
    print("The report is a rendered evidence record, not a scientific PASS or release approval.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "RCSL has two human workflows: train is an audit curriculum "
            "(it never trains a model), while audit manages evidence for a real Git "
            "project. Release commands create explicitly bounded case artifacts."
        )
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    train_parser = subcommands.add_parser(
        "train",
        help="Use the human research-code audit curriculum; this never trains a model.",
        description=(
            "Human research-code audit curriculum. This mode never trains a model "
            "and its public checks are not scientific verdicts."
        ),
    )
    train_commands = train_parser.add_subparsers(dest="train_command", required=True)
    train_commands.add_parser("overview", help="Show curriculum routes and boundaries.")
    train_commands.add_parser("doctor", help="Show Python and optional torch availability.")
    train_commands.add_parser("validate", help="Run learner-visible public package checks.")
    train_start = train_commands.add_parser("start", help="Show materials for one audit level.")
    train_start.add_argument(
        "--level",
        type=int,
        choices=tuple(LEVELS),
        required=True,
        help="Curriculum level to begin (1 through 4).",
    )

    train_progress = train_commands.add_parser(
        "progress",
        help="Manage an external, resumable learner record with declared human reviews.",
        description=(
            "Manage local training attempts and human review records. Automatic checks "
            "assess structure only; they do not judge answers or scientific correctness."
        ),
    )
    progress_commands = train_progress.add_subparsers(
        dest="progress_command", required=True
    )
    progress_init = progress_commands.add_parser(
        "init", help="Create a new local training workspace outside this repository."
    )
    progress_init.add_argument("--output", type=Path, required=True)
    progress_init.add_argument(
        "--learner", required=True, help="Declared learner label; not authenticated identity."
    )

    progress_status = progress_commands.add_parser(
        "status", help="Show separate attempt, structure, and human-review states."
    )
    progress_status.add_argument("workspace", type=Path)
    progress_status.add_argument("--json", action="store_true")

    progress_check = progress_commands.add_parser(
        "check", help="Check worksheet structure only; never calculate correctness or maturity."
    )
    progress_check.add_argument("workspace", type=Path)
    progress_check.add_argument("--target", choices=training_core.TARGETS, required=True)
    progress_check.add_argument("--json", action="store_true")

    progress_submit = progress_commands.add_parser(
        "submit", help="Freeze a structurally complete worksheet as an immutable attempt."
    )
    progress_submit.add_argument("workspace", type=Path)
    progress_submit.add_argument("--target", choices=training_core.TARGETS, required=True)
    progress_submit.add_argument("--note", default="")
    progress_submit.add_argument(
        "--operation-id", help="Stable retry ID for exactly-once local mutation semantics."
    )

    progress_review = progress_commands.add_parser(
        "review", help="Append one named human review bound to a frozen attempt."
    )
    progress_review.add_argument("workspace", type=Path)
    progress_review.add_argument("--target", choices=training_core.TARGETS, required=True)
    progress_review.add_argument("--attempt", default="latest")
    progress_review.add_argument("--reviewer", required=True)
    progress_review.add_argument("--decision", choices=training_core.REVIEW_DECISIONS, required=True)
    for flag in ("recognize", "prove", "direct", "steward"):
        progress_review.add_argument(
            f"--{flag}", choices=training_core.RATING_VALUES, required=True
        )
    progress_review.add_argument("--rationale", required=True)
    progress_review.add_argument("--strengths", required=True)
    progress_review.add_argument("--gaps", required=True)
    progress_review.add_argument("--operation-id")

    progress_export = progress_commands.add_parser(
        "export", help="Create a redacted, non-overwriting report inside the workspace."
    )
    progress_export.add_argument("workspace", type=Path)
    progress_export.add_argument("--output", type=Path, required=True)
    progress_export.add_argument("--format", choices=("markdown", "json"), default="markdown")

    export_parser = subcommands.add_parser(
        "export",
        help="Build or verify an honest public case-release artifact.",
        description=(
            "Export the current historically public case as an Open Demo. Removing "
            "controlled files does not make an already public case blind."
        ),
    )
    export_commands = export_parser.add_subparsers(
        dest="export_command", required=True
    )
    open_demo = export_commands.add_parser(
        "open-demo",
        help="Create a new non-overwriting Open Demo bundle outside this repository.",
    )
    open_demo.add_argument("--output", type=Path, required=True)
    open_demo.add_argument(
        "--actor",
        required=True,
        help="Declared builder label; this is not authenticated identity.",
    )
    open_demo.add_argument(
        "--run-public-checks",
        action="store_true",
        help="Run the optional Level 1-4 public runtime checks before export.",
    )
    export_verify = export_commands.add_parser(
        "verify",
        help="Verify bundle bytes and checksums; makes no scientific verdict.",
    )
    export_verify.add_argument("bundle", type=Path)
    export_verify.add_argument("--json", action="store_true")

    package_parser = subcommands.add_parser(
        "package",
        help="Assemble or verify separated Blind Challenge package candidates.",
        description=(
            "Build a local private staging area from three explicit, never-public "
            "source roots. Successful assembly is not access control or release approval."
        ),
    )
    package_commands = package_parser.add_subparsers(
        dest="package_command", required=True
    )
    blind_package = package_commands.add_parser(
        "blind",
        help="Assemble Challenge, Evaluator, and Maintainer candidates without execution.",
    )
    blind_package.add_argument(
        "--manifest",
        type=Path,
        required=True,
        help=(
            "Strict source manifest outside this public repository; on POSIX its "
            "file and parent directory must grant no group/other permissions."
        ),
    )
    blind_package.add_argument("--challenge-source", type=Path, required=True)
    blind_package.add_argument("--evaluator-source", type=Path, required=True)
    blind_package.add_argument("--maintainer-source", type=Path, required=True)
    blind_package.add_argument("--output", type=Path, required=True)
    blind_package.add_argument(
        "--actor",
        required=True,
        help="Declared builder label; this is not authenticated identity.",
    )
    package_verify = package_commands.add_parser(
        "verify",
        help="Verify all three staged packages and private control bindings.",
    )
    package_verify.add_argument("staging", type=Path)
    package_verify.add_argument("--json", action="store_true")

    audit_parser = subcommands.add_parser(
        "audit",
        help=(
            "Manage a local evidence lifecycle for one clean Git project; "
            "does not execute project code or make a scientific verdict."
        ),
        description=(
            "Manage a local evidence lifecycle for one clean Git project. "
            "This mode does not execute project code, use the network, modify the target, "
            "or make a scientific verdict."
        ),
    )
    audit_commands = audit_parser.add_subparsers(dest="audit_command", required=True)

    audit_init = audit_commands.add_parser(
        "init",
        help="Create an external workspace bound to one clean Git HEAD; no source execution.",
    )
    audit_init.add_argument("--project", type=Path, required=True, help="Clean Git worktree to bind read-only.")
    audit_init.add_argument("--output", type=Path, required=True, help="New workspace outside the project.")
    audit_init.add_argument("--level", type=int, choices=tuple(LEVELS), required=True)
    audit_init.add_argument("--actor", required=True, help="Declared actor label; not authenticated identity.")
    audit_init.add_argument(
        "--reason",
        default="Initial clean Git baseline recorded for a bounded research-code audit.",
        help="Why this project revision is the initial audit baseline.",
    )

    audit_status = audit_commands.add_parser(
        "status", help="Read binding, G0, finding, ledger, and preflight summary."
    )
    audit_status.add_argument("workspace", type=Path)
    audit_status.add_argument("--json", action="store_true", help="Emit stable machine-readable JSON.")

    audit_lint = audit_commands.add_parser(
        "lint", help="Check template structure only; never judges a finding or claim."
    )
    audit_lint.add_argument("workspace", type=Path)

    audit_gate = audit_commands.add_parser(
        "gate", help="Check or record the declared human G0 decision."
    )
    gate_commands = audit_gate.add_subparsers(dest="gate_command", required=True)
    gate_check = gate_commands.add_parser(
        "check", help="Read G0 structure and decision freshness; grants no authority."
    )
    gate_check.add_argument("workspace", type=Path)
    gate_check.add_argument("--json", action="store_true")
    gate_record = gate_commands.add_parser(
        "record", help="Record a named human decision bound to the current contract bytes."
    )
    gate_record.add_argument("workspace", type=Path)
    gate_record.add_argument("--decision", choices=audit_core.G0_STATUSES, required=True)
    gate_record.add_argument("--reviewer", required=True)
    gate_record.add_argument("--rationale", required=True)
    gate_record.add_argument("--actor", help="Recorder label; defaults to reviewer.")

    audit_preflight = audit_commands.add_parser(
        "preflight",
        help="Check approved G0, current contract, clean unchanged Git HEAD, and ledger integrity.",
    )
    audit_preflight.add_argument("workspace", type=Path)
    audit_preflight.add_argument("--json", action="store_true")

    audit_rebaseline = audit_commands.add_parser(
        "rebaseline", help="Bind a new clean HEAD explicitly and reset G0 to draft."
    )
    audit_rebaseline.add_argument("workspace", type=Path)
    audit_rebaseline.add_argument("--actor", required=True)
    audit_rebaseline.add_argument("--reason", required=True)

    audit_finding = audit_commands.add_parser(
        "finding", help="Add, list, or transition structured audit findings."
    )
    finding_commands = audit_finding.add_subparsers(dest="finding_command", required=True)
    finding_add = finding_commands.add_parser(
        "add", help="Record a finding against the active baseline; truth remains unassessed."
    )
    finding_add.add_argument("workspace", type=Path)
    finding_add.add_argument("--id", dest="finding_id", required=True)
    finding_add.add_argument("--title", required=True)
    finding_add.add_argument("--layer", choices=audit_core.LAYERS, required=True)
    finding_add.add_argument("--competency", choices=audit_core.COMPETENCIES, required=True)
    finding_add.add_argument("--severity", choices=audit_core.SEVERITIES, required=True)
    finding_add.add_argument("--claim", required=True)
    finding_add.add_argument("--first-contract", required=True)
    finding_add.add_argument("--actor", required=True)
    finding_list = finding_commands.add_parser("list", help="List recorded finding snapshots.")
    finding_list.add_argument("workspace", type=Path)
    finding_list.add_argument("--json", action="store_true")
    finding_transition = finding_commands.add_parser(
        "transition", help="Record one allowed, reasoned lifecycle transition."
    )
    finding_transition.add_argument("workspace", type=Path)
    finding_transition.add_argument("--finding", required=True)
    finding_transition.add_argument("--to", dest="to_status", choices=audit_core.FINDING_STATUSES, required=True)
    finding_transition.add_argument("--actor", required=True)
    finding_transition.add_argument("--rationale", required=True)

    audit_evidence = audit_commands.add_parser(
        "evidence", help="Attach typed evidence to one finding without judging sufficiency."
    )
    evidence_commands = audit_evidence.add_subparsers(dest="evidence_command", required=True)
    evidence_add = evidence_commands.add_parser("add", help="Append a typed evidence record.")
    evidence_add.add_argument("workspace", type=Path)
    evidence_add.add_argument("--finding", required=True)
    evidence_add.add_argument("--id", dest="evidence_id", required=True)
    evidence_add.add_argument("--kind", choices=audit_core.EVIDENCE_KINDS, required=True)
    evidence_add.add_argument("--reference", required=True)
    evidence_add.add_argument("--summary", required=True)
    evidence_add.add_argument("--actor", required=True)

    audit_verify = audit_commands.add_parser(
        "verify",
        help="Check local metadata, finding snapshots, and hash-chain consistency only.",
    )
    audit_verify.add_argument("workspace", type=Path)
    audit_verify.add_argument("--json", action="store_true")

    audit_recover = audit_commands.add_parser(
        "recover",
        help="Explicitly finish one interrupted lifecycle commit, then verify it.",
    )
    audit_recover.add_argument("workspace", type=Path)
    audit_recover.add_argument("--json", action="store_true")

    audit_report = audit_commands.add_parser(
        "report", help="Render a review record; does not approve science or release."
    )
    report_commands = audit_report.add_subparsers(dest="report_command", required=True)
    report_build = report_commands.add_parser(
        "build", help="Create a non-overwriting Markdown or JSON report inside the workspace."
    )
    report_build.add_argument("workspace", type=Path)
    report_build.add_argument("--output", type=Path, required=True)
    report_build.add_argument("--format", choices=("markdown", "json"), default="markdown")

    return parser


def _dispatch_train(args: argparse.Namespace) -> int:
    if args.train_command == "overview":
        return command_overview()
    if args.train_command == "doctor":
        return command_doctor()
    if args.train_command == "start":
        return command_start(args.level)
    if args.train_command == "validate":
        return command_validate()
    if args.train_command == "progress":
        if args.progress_command == "init":
            training_core.initialize_workspace(args.output, learner_label=args.learner)
            print(f"Training workspace CREATED: {args.output}")
            print("Edit worksheets/*.md, then run train progress check and submit.")
            print("Automatic checks are structural only; this public case is not a verified blind challenge.")
            return 0
        if args.progress_command == "status":
            status = training_core.get_status(args.workspace)
            if args.json:
                print(json.dumps(status, indent=2, sort_keys=True, ensure_ascii=False))
            else:
                print(f"Overall state: {status['overall_state']}")
                print(f"Exposure state: {status['exposure_state']}")
                for target, record in status["targets"].items():
                    print(
                        f"{target}: attempt={record['attempt_state']}; "
                        f"structure={record['structure_state']}; "
                        f"human-review={record['human_review_state']}; "
                        f"draft={record['current_draft_state']}"
                    )
                print("No automatic result above is a scientific or maturity verdict.")
            return 0
        if args.progress_command == "check":
            assessment = training_core.check_worksheet(args.workspace, args.target)
            if args.json:
                print(json.dumps(assessment, indent=2, sort_keys=True, ensure_ascii=False))
            else:
                print(f"{args.target} structure: {assessment['structure_status'].upper()}")
                for heading in assessment["missing_sections"]:
                    print(f"  Missing section: {heading}")
                for heading in assessment["empty_sections"]:
                    print(f"  Empty section: {heading}")
                if assessment["placeholder_count"]:
                    print(f"  Template prompts remaining: {assessment['placeholder_count']}")
                print("Semantic, scientific, and maturity assessment: NOT PERFORMED")
            return 0 if assessment["structure_status"] == "complete" else 1
        if args.progress_command == "submit":
            attempt = training_core.submit_attempt(
                args.workspace,
                args.target,
                note=args.note,
                operation_id=args.operation_id,
            )
            print(f"Attempt FROZEN: {attempt['id']} ({attempt['worksheet_sha256']})")
            print("State: AWAITING HUMAN REVIEW")
            print("This submission has structural completeness only, not a correctness verdict.")
            return 0
        if args.progress_command == "review":
            review = training_core.record_review(
                args.workspace,
                args.target,
                attempt_id=args.attempt,
                reviewer=args.reviewer,
                decision=args.decision,
                ratings={
                    "Recognize": args.recognize,
                    "Prove": args.prove,
                    "Direct": args.direct,
                    "Steward": args.steward,
                },
                rationale=args.rationale,
                strengths=args.strengths,
                gaps=args.gaps,
                operation_id=args.operation_id,
            )
            print(f"Human review RECORDED: {review['id']} for {review['attempt_id']}")
            print(f"Declared decision: {review['decision']}")
            print("The CLI validated record consistency; it did not generate or verify the judgment.")
            return 0
        if args.progress_command == "export":
            output = training_core.export_progress(
                args.workspace, args.output, format_name=args.format
            )
            print(f"Redacted training progress CREATED: {output}")
            print("The export contains declared records, not scientific certification.")
            return 0
    raise AssertionError(f"Unhandled train command: {args.train_command}")


def _dispatch_audit(args: argparse.Namespace) -> int:
    if args.audit_command == "init":
        return command_audit_init(args.project, args.output, args.level, args.actor, args.reason)
    if args.audit_command == "status":
        return command_audit_status(args.workspace, as_json=args.json)
    if args.audit_command == "lint":
        return command_lint_audit(args.workspace)
    if args.audit_command == "gate":
        if args.gate_command == "check":
            return command_audit_gate_check(args.workspace, as_json=args.json)
        if args.gate_command == "record":
            return command_audit_gate_record(
                args.workspace,
                args.decision,
                args.reviewer,
                args.rationale,
                args.actor,
            )
    if args.audit_command == "preflight":
        return command_audit_preflight(args.workspace, as_json=args.json)
    if args.audit_command == "rebaseline":
        return command_audit_rebaseline(args.workspace, actor=args.actor, reason=args.reason)
    if args.audit_command == "finding":
        if args.finding_command == "add":
            return command_audit_finding_add(args)
        if args.finding_command == "list":
            return command_audit_finding_list(args.workspace, as_json=args.json)
        if args.finding_command == "transition":
            return command_audit_finding_transition(args)
    if args.audit_command == "evidence" and args.evidence_command == "add":
        return command_audit_evidence_add(args)
    if args.audit_command == "verify":
        return command_audit_verify(args.workspace, as_json=args.json)
    if args.audit_command == "recover":
        return command_audit_recover(args.workspace, as_json=args.json)
    if args.audit_command == "report" and args.report_command == "build":
        return command_audit_report(args.workspace, args.output, args.format)
    raise AssertionError(f"Unhandled audit command: {args.audit_command}")


def _dispatch_release(args: argparse.Namespace) -> int:
    if args.command == "export":
        if args.export_command == "open-demo":
            output = release_core.export_open_demo(
                args.output,
                actor=args.actor,
                run_public_checks=args.run_public_checks,
            )
            print(f"Open Demo bundle CREATED: {output}")
            print("Release mode: OPEN DEMO · HISTORICALLY PUBLIC")
            print(
                "The bundle is not a Blind Challenge and its checks are not a scientific verdict."
            )
            return 0
        if args.export_command == "verify":
            result = release_core.verify_export(args.bundle)
            if args.json:
                print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
            else:
                print(f"Bundle integrity: {result['integrity_status'].upper()}")
                print("Scientific correctness: NOT ASSESSED")
            return 0
    if args.command == "package":
        if args.package_command == "blind":
            output = release_core.package_blind(
                args.manifest,
                challenge_source=args.challenge_source,
                evaluator_source=args.evaluator_source,
                maintainer_source=args.maintainer_source,
                output=args.output,
                actor=args.actor,
            )
            print(f"Blind package staging CREATED: {output}")
            print("Assembly state: ASSEMBLED · AWAITING CONTROLLED PLACEMENT")
            print(
                "This local staging area is not access control, grading validation, or release approval."
            )
            return 0
        if args.package_command == "verify":
            result = release_core.verify_blind_staging(args.staging)
            if args.json:
                print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
            else:
                print(f"Staging integrity: {result['integrity_status'].upper()}")
                print(f"Assembly state: {result['assembly_state']}")
                print("Operational release: NOT APPROVED")
            return 0
    raise AssertionError(f"Unhandled release command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "train":
            return _dispatch_train(args)
        if args.command == "audit":
            return _dispatch_audit(args)
        if args.command in {"export", "package"}:
            return _dispatch_release(args)
    except training_core.TrainingError as error:
        print(f"Training operation refused: {error}", file=sys.stderr)
        return 1
    except audit_core.AuditError as error:
        print(f"Audit operation refused: {error}", file=sys.stderr)
        return 1
    except release_core.ReleaseError as error:
        print(f"Release operation refused: {error}", file=sys.stderr)
        return 1
    except OSError as error:
        print(f"Local operation failed: {error}", file=sys.stderr)
        return 2
    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
