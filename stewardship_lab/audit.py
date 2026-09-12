"""Public, filesystem-local lifecycle support for real research-code audits.

This module deliberately operates only on an explicitly supplied audit workspace,
the Git project bound to it, and four well-known workspace files. It never walks
training-package directories or resolves instructor-only material.
"""

from __future__ import annotations

import copy
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import wraps
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import uuid


SCHEMA_VERSION = 2
WORKSPACE_METADATA_NAME = "audit-workspace.json"
FINDINGS_DIRECTORY_NAME = "findings"
EVENT_LOG_NAME = "audit-events.jsonl"
ISOLATED_DIRECTORY_NAME = "DO_NOT_OPEN_UNTIL_FINISHED"

PUBLIC_TEMPLATE_FILENAMES = (
    "research-contract-template.md",
    "evidence-passport-template.md",
    "triage-card-template.md",
    "delegation-contract-template.md",
)

LAYERS = ("L1", "L2", "L3", "L4", "cross-cutting")
COMPETENCIES = ("C1", "C2", "C3", "C4", "C5", "C6", "C7")
SEVERITIES = ("critical", "high", "medium", "low", "info")
EVIDENCE_KINDS = ("asserted", "observed", "derived", "reproduced", "contradicted")
G0_STATUSES = ("draft", "approved", "blocked")
G0_STATUS_ALIASES = {
    "draft": "draft",
    "approve": "approved",
    "approved": "approved",
    "block": "blocked",
    "blocked": "blocked",
}
FINDING_STATUSES = ("open", "triaged", "accepted", "mitigated", "verified", "closed", "dismissed", "blocked")
FINDING_TRANSITIONS = {
    "open": {"triaged", "dismissed", "blocked"},
    "triaged": {"open", "accepted", "dismissed", "blocked"},
    "accepted": {"mitigated", "blocked"},
    "mitigated": {"accepted", "verified", "blocked"},
    "verified": {"accepted", "closed"},
    "closed": {"open"},
    "dismissed": {"open"},
    "blocked": {"triaged", "dismissed"},
}
TRUSTED_TERMINAL_STATUSES = ("verified", "closed")
FINDING_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z")
CONTRACT_PLACEHOLDER_PATTERN = re.compile(
    r"\{\{[^{}\n]+\}\}|\[TODO\]|\[填写\]|待填写|^\s*(?:TODO|TBD)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
MARKDOWN_HEADING_PATTERN = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)
RESEARCH_CONTRACT_REQUIRED_HEADINGS = (
    "G0 Research Contract",
    "Identity and decision",
    "Research mandate",
    "Success, failure, and stopping",
    "Sources, rights, and legitimacy",
    "Human authority and delegation",
    "Assumptions and unknowns",
    "Human gate decision",
)


class AuditError(RuntimeError):
    """Raised when an audit lifecycle operation would be unsafe or inconsistent."""


@contextmanager
def _workspace_write_lock(workspace: Path):
    """Serialize local writers with an atomic, fail-closed lock file.

    A process crash can leave the lock behind. The error deliberately asks for
    human review instead of guessing that an existing lock is stale.
    """

    lock_path = workspace / ".rcsl-write.lock"
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise AuditError(
            "audit workspace is locked by another writer; if no writer is active, "
            "review and remove .rcsl-write.lock manually"
        ) from error
    except OSError as error:
        raise AuditError(f"could not acquire audit workspace write lock: {error}") from error
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(f"pid={os.getpid()}\n")
            handle.flush()
            os.fsync(handle.fileno())
        yield
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass
        except OSError as error:
            raise AuditError(f"could not release audit workspace write lock: {error}") from error


def _serialized_workspace_mutation(workspace_argument_index: int):
    """Decorate a public mutation whose workspace is one positional argument."""

    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            if len(args) > workspace_argument_index:
                workspace_value = args[workspace_argument_index]
            else:
                workspace_value = kwargs.get("workspace")
            if workspace_value is None:
                raise AuditError("workspace is required")
            workspace = _existing_directory(workspace_value, "audit workspace")
            with _workspace_write_lock(workspace):
                return function(*args, **kwargs)

        return wrapped

    return decorate


def _serialized_bind(function):
    """Check bind containment before its workspace lock can dirty the project."""

    @wraps(function)
    def wrapped(project, workspace, *args, **kwargs):
        project_snapshot = _git_snapshot(project, require_clean=True)
        workspace_path = _existing_directory(workspace, "audit workspace")
        project_root = Path(_require_text(project_snapshot.get("project_root"), "project root"))
        if _is_within(workspace_path, project_root) or _is_within(project_root, workspace_path):
            raise AuditError("audit workspace must be outside the bound Git project")
        with _workspace_write_lock(workspace_path):
            return function(project, workspace, *args, **kwargs)

    return wrapped


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _require_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AuditError(f"{field} must be a non-empty string")
    return value.strip()


def _safe_path(value: str | Path, role: str) -> Path:
    """Normalize a user path lexically before performing any filesystem operation."""

    path = Path(os.path.abspath(os.path.expanduser(os.fspath(value))))
    isolated_name = ISOLATED_DIRECTORY_NAME.casefold()
    if any(part.casefold() == isolated_name for part in path.parts):
        raise AuditError(f"{role} must not point to isolated instructor material")
    return path


def _existing_directory(value: str | Path, role: str) -> Path:
    path = _safe_path(value, role)
    if path.is_symlink() or not path.is_dir():
        raise AuditError(f"{role} must be an existing regular directory: {path}")
    resolved = path.resolve()
    isolated_name = ISOLATED_DIRECTORY_NAME.casefold()
    if any(part.casefold() == isolated_name for part in resolved.parts):
        raise AuditError(f"{role} must not resolve into isolated instructor material")
    return resolved


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        # Be deliberately conservative on case-insensitive filesystems.  Path
        # preserves the caller's spelling on macOS, so relative_to() alone can
        # miss that /Repo/audit and /repo/audit name the same location.
        child_parts = tuple(part.casefold() for part in child.parts)
        parent_parts = tuple(part.casefold() for part in parent.parts)
        return (
            len(child_parts) >= len(parent_parts)
            and child_parts[: len(parent_parts)] == parent_parts
        )


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _atomic_write_text(path: Path, content: str) -> None:
    """Write one public lifecycle file atomically in its own directory."""

    if path.is_symlink():
        raise AuditError(f"refusing to replace a symlink: {path}")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except OSError as error:
        raise AuditError(f"could not write {path.name}: {error}") from error
    finally:
        if temporary_path.exists() or temporary_path.is_symlink():
            temporary_path.unlink(missing_ok=True)


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    _atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _read_json_object(path: Path, label: str) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise AuditError(f"missing regular {label}: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AuditError(f"could not read {label}: {error.__class__.__name__}") from error
    if not isinstance(payload, dict):
        raise AuditError(f"{label} must contain a JSON object")
    return payload


def _event_hash(event_body: dict[str, object]) -> str:
    return hashlib.sha256(_canonical_json(event_body).encode("utf-8")).hexdigest()


def _finding_hash(finding: dict[str, object]) -> str:
    """Return a stable digest for one full finding snapshot."""

    return hashlib.sha256(_canonical_json(finding).encode("utf-8")).hexdigest()


def _metadata_hash(metadata: dict[str, object]) -> str:
    """Return a stable digest for the current workspace metadata snapshot."""

    return hashlib.sha256(_canonical_json(metadata).encode("utf-8")).hexdigest()


def _file_sha256(path: Path, label: str) -> str:
    """Hash one known public file without following a symlink."""

    if path.is_symlink() or not path.is_file():
        raise AuditError(f"missing regular {label}: {path}")
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        raise AuditError(f"could not read {label}: {error.__class__.__name__}") from error


def _validate_event_chain(events: list[dict[str, object]]) -> None:
    expected_keys = {
        "schema_version",
        "seq",
        "timestamp",
        "event_type",
        "actor",
        "payload",
        "prev_hash",
        "event_hash",
    }
    previous_hash: str | None = None
    for sequence, event in enumerate(events, start=1):
        if set(event) != expected_keys:
            raise AuditError(f"event {sequence} has an unexpected schema")
        if (
            type(event.get("schema_version")) is not int
            or event.get("schema_version") != SCHEMA_VERSION
            or type(event.get("seq")) is not int
            or event.get("seq") != sequence
        ):
            raise AuditError(f"event {sequence} has an invalid schema version or sequence")
        if event.get("prev_hash") != previous_hash:
            raise AuditError(f"event {sequence} breaks the previous-hash chain")
        _require_text(event.get("timestamp"), f"event {sequence} timestamp")
        _require_text(event.get("event_type"), f"event {sequence} event_type")
        _require_text(event.get("actor"), f"event {sequence} actor")
        if not isinstance(event.get("payload"), dict):
            raise AuditError(f"event {sequence} payload must be an object")
        supplied_hash = event.get("event_hash")
        if not isinstance(supplied_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", supplied_hash):
            raise AuditError(f"event {sequence} has an invalid event_hash")
        body = {key: value for key, value in event.items() if key != "event_hash"}
        if _event_hash(body) != supplied_hash:
            raise AuditError(f"event {sequence} hash does not match its content")
        previous_hash = supplied_hash


def _read_events(workspace: Path, *, allow_missing: bool) -> list[dict[str, object]]:
    event_path = workspace / EVENT_LOG_NAME
    if event_path.is_symlink():
        raise AuditError("event log must not be a symlink")
    if not event_path.is_file():
        if allow_missing and not event_path.exists():
            return []
        raise AuditError(f"missing regular event log: {event_path}")
    try:
        lines = event_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as error:
        raise AuditError(f"could not read event log: {error.__class__.__name__}") from error
    events: list[dict[str, object]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            raise AuditError(f"event log contains an empty line at {line_number}")
        try:
            event = json.loads(line)
        except json.JSONDecodeError as error:
            raise AuditError(f"event log has invalid JSON at line {line_number}") from error
        if not isinstance(event, dict):
            raise AuditError(f"event log line {line_number} must be an object")
        events.append(event)
    _validate_event_chain(events)
    return events


def _append_event(
    workspace: Path,
    *,
    event_type: str,
    actor: str,
    payload: dict[str, object],
) -> dict[str, object]:
    """Append a hash-chained event by atomically replacing the public JSONL file."""

    events = _read_events(workspace, allow_missing=True)
    previous_hash = events[-1]["event_hash"] if events else None
    body: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "seq": len(events) + 1,
        "timestamp": _utc_now(),
        "event_type": _require_text(event_type, "event_type"),
        "actor": _require_text(actor, "actor"),
        "payload": payload,
        "prev_hash": previous_hash,
    }
    event = {**body, "event_hash": _event_hash(body)}
    events.append(event)
    _atomic_write_text(
        workspace / EVENT_LOG_NAME,
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in events),
    )
    return copy.deepcopy(event)


def _run_git(project: Path, *arguments: str) -> str:
    git_environment = os.environ.copy()
    git_environment["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        result = subprocess.run(
            ("git", "-c", "core.fsmonitor=false", "-C", str(project), *arguments),
            text=True,
            capture_output=True,
            check=False,
            env=git_environment,
        )
    except OSError as error:
        raise AuditError(f"could not execute git: {error}") from error
    if result.returncode:
        details = result.stderr.strip() or result.stdout.strip() or "unknown git failure"
        raise AuditError(f"git {' '.join(arguments)} failed: {details}")
    return result.stdout.strip()


def _git_snapshot(project: str | Path, *, require_clean: bool) -> dict[str, object]:
    candidate = _existing_directory(project, "project")
    root_text = _run_git(candidate, "rev-parse", "--show-toplevel")
    project_root = _existing_directory(root_text, "Git project root")
    head = _run_git(project_root, "rev-parse", "HEAD")
    branch_output = _run_git(project_root, "branch", "--show-current")
    if require_clean:
        status = _run_git(project_root, "status", "--porcelain=v1", "--untracked-files=all")
        if status:
            raise AuditError("project must be clean before this lifecycle operation")
    return {
        "project_root": str(project_root),
        "head": head,
        "branch": branch_output or None,
    }


def inspect_clean_project(project: str | Path) -> dict[str, object]:
    """Return a clean Git project's root, HEAD, and branch without executing its code."""

    return copy.deepcopy(_git_snapshot(project, require_clean=True))


def _validate_public_workspace(workspace_value: str | Path) -> tuple[Path, dict[str, object]]:
    workspace = _existing_directory(workspace_value, "audit workspace")
    metadata = _read_json_object(workspace / WORKSPACE_METADATA_NAME, "audit workspace metadata")
    if metadata.get("workspace_type") != "rcsl-public-audit-workspace":
        raise AuditError("workspace is not a public RCSL audit workspace")
    for filename in PUBLIC_TEMPLATE_FILENAMES:
        template = workspace / filename
        if template.is_symlink() or not template.is_file():
            raise AuditError(f"workspace is missing required public template: {filename}")
    return workspace, metadata


def _assert_research_contract_complete(workspace: Path) -> None:
    """Require the public G0 contract to be structurally completed before approval."""

    contract_path = workspace / "research-contract-template.md"
    if contract_path.is_symlink() or not contract_path.is_file():
        raise AuditError("G0 approval requires a regular public research contract")
    try:
        contract = contract_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise AuditError(f"could not read public research contract: {error.__class__.__name__}") from error
    heading_matches = list(MARKDOWN_HEADING_PATTERN.finditer(contract))
    headings = {
        match.group(1).strip().rstrip("#").strip() for match in heading_matches
    }
    missing = [heading for heading in RESEARCH_CONTRACT_REQUIRED_HEADINGS if heading not in headings]
    if missing:
        raise AuditError(f"G0 research contract is missing required sections: {', '.join(missing)}")
    if CONTRACT_PLACEHOLDER_PATTERN.search(contract):
        raise AuditError("G0 research contract still contains unresolved placeholders")
    empty_sections: list[str] = []
    for index, match in enumerate(heading_matches):
        heading = match.group(1).strip().rstrip("#").strip()
        if heading not in RESEARCH_CONTRACT_REQUIRED_HEADINGS[1:]:
            continue
        end = heading_matches[index + 1].start() if index + 1 < len(heading_matches) else len(contract)
        section = contract[match.end() : end]
        lines = [
            line.strip()
            for line in section.splitlines()
            if line.strip() and not line.lstrip().startswith("<!--")
        ]
        substantive = [
            line
            for line in lines
            if not re.fullmatch(r"[-*]\s+[^:]+:\s*", line)
            and not re.fullmatch(r"\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?", line)
        ]
        if heading == "Assumptions and unknowns":
            table_rows = [line for line in substantive if line.startswith("|")]
            if len(table_rows) < 2:
                empty_sections.append(heading)
        elif not substantive:
            empty_sections.append(heading)
    if empty_sections:
        raise AuditError(
            "G0 research contract has empty required sections: " + ", ".join(empty_sections)
        )


def _lifecycle_from_metadata(metadata: dict[str, object]) -> dict[str, object]:
    if type(metadata.get("schema_version")) is not int or metadata.get("schema_version") != SCHEMA_VERSION:
        raise AuditError("audit workspace does not use lifecycle schema v2")
    lifecycle = metadata.get("audit_lifecycle")
    if not isinstance(lifecycle, dict):
        raise AuditError("audit workspace is not bound to a Git project")
    if type(lifecycle.get("schema_version")) is not int or lifecycle.get("schema_version") != SCHEMA_VERSION:
        raise AuditError("audit lifecycle schema version is not supported")
    if lifecycle.get("validator_scope") != "integrity_only":
        raise AuditError("audit lifecycle validator scope is not recognized")
    if lifecycle.get("findings_directory") != FINDINGS_DIRECTORY_NAME:
        raise AuditError("audit lifecycle findings directory is not recognized")
    if lifecycle.get("event_log") != EVENT_LOG_NAME:
        raise AuditError("audit lifecycle event log is not recognized")

    project = lifecycle.get("project")
    baseline = lifecycle.get("baseline")
    gate = lifecycle.get("g0_gate")
    if not isinstance(project, dict) or not isinstance(baseline, dict) or not isinstance(gate, dict):
        raise AuditError("audit lifecycle is missing project, baseline, or G0 gate metadata")
    _require_text(project.get("root"), "project root")
    for field in ("id", "head", "captured_at", "actor", "reason"):
        _require_text(baseline.get(field), f"baseline {field}")
    branch = baseline.get("branch")
    if branch is not None and not isinstance(branch, str):
        raise AuditError("baseline branch must be a string or null")
    if gate.get("status") not in G0_STATUSES:
        raise AuditError("G0 gate status is not recognized")
    for field in ("reviewer", "rationale", "actor", "updated_at"):
        _require_text(gate.get(field), f"G0 gate {field}")
    contract_sha256 = gate.get("contract_sha256")
    if not isinstance(contract_sha256, str) or not re.fullmatch(
        r"[0-9a-f]{64}", contract_sha256
    ):
        raise AuditError("G0 gate contract_sha256 is invalid")
    return lifecycle


def _load_bound_workspace(workspace_value: str | Path) -> tuple[Path, dict[str, object], dict[str, object]]:
    workspace, metadata = _validate_public_workspace(workspace_value)
    lifecycle = _lifecycle_from_metadata(metadata)
    return workspace, metadata, lifecycle


def _finding_path(workspace: Path, finding_id: str) -> Path:
    if not FINDING_ID_PATTERN.fullmatch(finding_id):
        raise AuditError("finding_id may contain only letters, digits, dot, underscore, and hyphen")
    return _validated_findings_directory(workspace) / f"{finding_id}.json"


def _validated_findings_directory(workspace: Path) -> Path:
    directory = workspace / FINDINGS_DIRECTORY_NAME
    if directory.is_symlink() or not directory.is_dir():
        raise AuditError("findings directory is missing or is not a regular directory")
    resolved = directory.resolve()
    if not _is_within(resolved, workspace.resolve()):
        raise AuditError("findings directory must remain inside the audit workspace")
    return directory


def _validate_evidence_item(item: object, finding_id: str, seen_ids: set[str]) -> None:
    if not isinstance(item, dict):
        raise AuditError(f"finding {finding_id} evidence entries must be objects")
    for field in ("id", "kind", "reference", "summary", "actor", "recorded_at"):
        _require_text(item.get(field), f"finding {finding_id} evidence {field}")
    evidence_id = item["id"]
    if not isinstance(evidence_id, str) or not FINDING_ID_PATTERN.fullmatch(evidence_id):
        raise AuditError(f"finding {finding_id} evidence id is invalid")
    if evidence_id in seen_ids:
        raise AuditError(f"finding {finding_id} contains duplicate evidence id: {evidence_id}")
    if item.get("kind") not in EVIDENCE_KINDS:
        raise AuditError(
            f"finding {finding_id} evidence kind must be one of: "
            f"{', '.join(EVIDENCE_KINDS)}"
        )
    seen_ids.add(evidence_id)


def _validate_finding(finding: object, *, expected_id: str | None = None) -> dict[str, object]:
    if not isinstance(finding, dict):
        raise AuditError("finding file must contain a JSON object")
    required = (
        "schema_version",
        "id",
        "title",
        "layer",
        "competency",
        "severity",
        "claim",
        "first_broken_contract",
        "status",
        "actor",
        "created_at",
        "updated_at",
        "baseline_snapshot",
        "evidence",
    )
    for field in required:
        if field not in finding:
            raise AuditError(f"finding is missing required field: {field}")
    if type(finding.get("schema_version")) is not int or finding.get("schema_version") != SCHEMA_VERSION:
        raise AuditError("finding schema version is not supported")
    finding_id = _require_text(finding.get("id"), "finding id")
    if not FINDING_ID_PATTERN.fullmatch(finding_id):
        raise AuditError("finding id is invalid")
    if expected_id is not None and finding_id != expected_id:
        raise AuditError("finding id does not match its filename")
    for field in ("title", "claim", "first_broken_contract", "actor", "created_at", "updated_at"):
        _require_text(finding.get(field), f"finding {field}")
    if finding.get("layer") not in LAYERS:
        raise AuditError("finding layer is not recognized")
    if finding.get("competency") not in COMPETENCIES:
        raise AuditError("finding competency is not recognized")
    if finding.get("severity") not in SEVERITIES:
        raise AuditError("finding severity is not recognized")
    if finding.get("status") not in FINDING_STATUSES:
        raise AuditError("finding status is not recognized")
    baseline_snapshot = finding.get("baseline_snapshot")
    if not isinstance(baseline_snapshot, dict):
        raise AuditError("finding baseline_snapshot must be an object")
    for field in ("project_root", "id", "head", "captured_at"):
        _require_text(baseline_snapshot.get(field), f"finding baseline_snapshot {field}")
    snapshot_branch = baseline_snapshot.get("branch")
    if snapshot_branch is not None and not isinstance(snapshot_branch, str):
        raise AuditError("finding baseline_snapshot branch must be a string or null")
    evidence = finding.get("evidence")
    if not isinstance(evidence, list):
        raise AuditError("finding evidence must be a list")
    seen_ids: set[str] = set()
    for item in evidence:
        _validate_evidence_item(item, finding_id, seen_ids)
    return finding


def _load_finding(workspace: Path, finding_id: str) -> dict[str, object]:
    path = _finding_path(workspace, finding_id)
    return _validate_finding(_read_json_object(path, "finding"), expected_id=finding_id)


def _load_findings(workspace: Path) -> list[dict[str, object]]:
    directory = _validated_findings_directory(workspace)
    findings: list[dict[str, object]] = []
    for path in sorted(directory.iterdir(), key=lambda item: item.name):
        if path.name == ISOLATED_DIRECTORY_NAME:
            raise AuditError("findings directory contains an isolated-material path")
        if path.is_symlink() or not path.is_file() or path.suffix != ".json":
            raise AuditError(f"findings directory contains an unexpected entry: {path.name}")
        finding_id = path.stem
        findings.append(_validate_finding(_read_json_object(path, "finding"), expected_id=finding_id))
    return findings


def _finding_matches_current_baseline(
    finding: dict[str, object], lifecycle: dict[str, object]
) -> bool:
    baseline = lifecycle.get("baseline")
    snapshot = finding.get("baseline_snapshot")
    project = lifecycle.get("project")
    if not isinstance(baseline, dict) or not isinstance(snapshot, dict) or not isinstance(project, dict):
        return False
    return (
        snapshot.get("project_root") == project.get("root")
        and snapshot.get("id") == baseline.get("id")
        and snapshot.get("head") == baseline.get("head")
        and snapshot.get("branch") == baseline.get("branch")
        and snapshot.get("captured_at") == baseline.get("captured_at")
    )


def _verify_finding_event_hashes(
    findings: list[dict[str, object]], events: list[dict[str, object]]
) -> None:
    """Ensure every current finding matches its last recorded lifecycle snapshot."""

    latest_hashes: dict[str, str] = {}
    finding_event_types = {
        "finding_created",
        "finding_evidence_added",
        "finding_status_changed",
    }
    for event in events:
        event_type = event.get("event_type")
        payload = event.get("payload")
        if event_type not in finding_event_types:
            continue
        if not isinstance(payload, dict):
            raise AuditError("finding lifecycle event payload is invalid")
        finding_id = payload.get("finding_id")
        recorded_hash = payload.get("finding_sha256")
        if not isinstance(finding_id, str) or not FINDING_ID_PATTERN.fullmatch(finding_id):
            raise AuditError("finding lifecycle event has an invalid finding_id")
        if not isinstance(recorded_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", recorded_hash):
            raise AuditError("finding lifecycle event has an invalid finding_sha256")
        latest_hashes[finding_id] = recorded_hash

    actual = {str(finding["id"]): _finding_hash(finding) for finding in findings}
    for finding_id, recorded_hash in latest_hashes.items():
        if finding_id not in actual:
            raise AuditError(f"event log references a missing finding: {finding_id}")
        if actual[finding_id] != recorded_hash:
            raise AuditError(f"finding hash does not match its latest event: {finding_id}")
    for finding_id in actual:
        if finding_id not in latest_hashes:
            raise AuditError(f"finding has no lifecycle hash event: {finding_id}")


def _verify_metadata_event_hash(
    metadata: dict[str, object], events: list[dict[str, object]]
) -> None:
    """Tie current mutable metadata to its most recent lifecycle event."""

    lifecycle_event_types = {"workspace_bound", "g0_gate_set", "baseline_replaced"}
    latest_hash: str | None = None
    for event in events:
        if event.get("event_type") not in lifecycle_event_types:
            continue
        payload = event.get("payload")
        if not isinstance(payload, dict):
            raise AuditError("workspace lifecycle event payload is invalid")
        recorded_hash = payload.get("metadata_sha256")
        if not isinstance(recorded_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", recorded_hash):
            raise AuditError("workspace lifecycle event has an invalid metadata_sha256")
        latest_hash = recorded_hash
    if latest_hash is None:
        raise AuditError("event log has no workspace metadata snapshot")
    if _metadata_hash(metadata) != latest_hash:
        raise AuditError("workspace metadata hash does not match its latest lifecycle event")


def _verify_event_semantics(
    findings: list[dict[str, object]], events: list[dict[str, object]]
) -> None:
    """Replay the small public lifecycle state machine for internal consistency."""

    if not events or events[0].get("event_type") != "workspace_bound":
        raise AuditError("event history must start with exactly one workspace_bound event")
    statuses: dict[str, str] = {}
    evidence_ids: dict[str, set[str]] = {}
    for index, event in enumerate(events):
        event_type = event.get("event_type")
        payload = event.get("payload")
        if not isinstance(payload, dict):
            raise AuditError("event payload is invalid")
        if event_type == "workspace_bound":
            if index != 0:
                raise AuditError("workspace_bound may appear only as the first event")
        elif event_type in {"g0_gate_set", "baseline_replaced"}:
            continue
        elif event_type == "finding_created":
            finding_id = payload.get("finding_id")
            if not isinstance(finding_id, str) or finding_id in statuses:
                raise AuditError("finding_created has a missing or duplicate finding_id")
            if payload.get("status") != "open":
                raise AuditError("finding_created must begin with open status")
            statuses[finding_id] = "open"
            evidence_ids[finding_id] = set()
        elif event_type == "finding_evidence_added":
            finding_id = payload.get("finding_id")
            evidence_id = payload.get("evidence_id")
            if not isinstance(finding_id, str) or finding_id not in statuses:
                raise AuditError("evidence event references an unknown finding")
            if not isinstance(evidence_id, str) or evidence_id in evidence_ids[finding_id]:
                raise AuditError("evidence event has a missing or duplicate evidence_id")
            evidence_ids[finding_id].add(evidence_id)
        elif event_type == "finding_status_changed":
            finding_id = payload.get("finding_id")
            before = payload.get("from_status")
            after = payload.get("to_status")
            if not isinstance(finding_id, str) or finding_id not in statuses:
                raise AuditError("status event references an unknown finding")
            if before != statuses[finding_id] or after not in FINDING_TRANSITIONS.get(str(before), set()):
                raise AuditError("status event violates the finding lifecycle")
            statuses[finding_id] = str(after)
        else:
            raise AuditError(f"event history contains an unknown event type: {event_type}")
    actual_statuses = {str(finding["id"]): str(finding["status"]) for finding in findings}
    if actual_statuses != statuses:
        raise AuditError("finding statuses do not match replayed event history")
    actual_evidence = {
        str(finding["id"]): {
            str(item["id"])
            for item in finding["evidence"]
            if isinstance(item, dict) and "id" in item
        }
        for finding in findings
    }
    if actual_evidence != evidence_ids:
        raise AuditError("finding evidence does not match replayed event history")


@_serialized_bind
def bind_audit(
    project: str | Path,
    workspace: str | Path,
    *,
    actor: str,
    rationale: str,
) -> dict[str, object]:
    """Bind a clean Git project to an existing external public audit workspace.

    The newly bound workspace starts with a G0 ``draft`` gate. A named reviewer
    must explicitly approve it before :func:`preflight` can succeed.
    """

    actor = _require_text(actor, "actor")
    rationale = _require_text(rationale, "rationale")
    project_snapshot = _git_snapshot(project, require_clean=True)
    workspace_path, metadata = _validate_public_workspace(workspace)
    project_root = Path(_require_text(project_snapshot.get("project_root"), "project root"))
    if _is_within(workspace_path, project_root) or _is_within(project_root, workspace_path):
        raise AuditError("audit workspace must be outside the bound Git project")
    if "audit_lifecycle" in metadata:
        raise AuditError("audit workspace is already bound")
    if type(metadata.get("schema_version")) is not int or metadata.get("schema_version") not in (1, SCHEMA_VERSION):
        raise AuditError("audit workspace schema version is not supported for binding")

    findings_directory = workspace_path / FINDINGS_DIRECTORY_NAME
    event_log = workspace_path / EVENT_LOG_NAME
    if findings_directory.is_symlink() or findings_directory.exists():
        raise AuditError("audit workspace already contains a findings directory")
    if event_log.is_symlink() or event_log.exists():
        raise AuditError("audit workspace already contains an event log")

    now = _utc_now()
    baseline = {
        "id": f"baseline-{uuid.uuid4()}",
        "head": project_snapshot["head"],
        "branch": project_snapshot["branch"],
        "captured_at": now,
        "actor": actor,
        "reason": rationale,
    }
    gate = {
        "status": "draft",
        "reviewer": actor,
        "rationale": rationale,
        "actor": actor,
        "updated_at": now,
        "contract_sha256": _file_sha256(
            workspace_path / "research-contract-template.md", "public research contract"
        ),
    }
    upgraded = copy.deepcopy(metadata)
    upgraded["schema_version"] = SCHEMA_VERSION
    upgraded["audit_lifecycle"] = {
        "schema_version": SCHEMA_VERSION,
        "validator_scope": "integrity_only",
        "project": {"root": project_snapshot["project_root"]},
        "baseline": baseline,
        "g0_gate": gate,
        "findings_directory": FINDINGS_DIRECTORY_NAME,
        "event_log": EVENT_LOG_NAME,
    }

    try:
        findings_directory.mkdir()
    except OSError as error:
        raise AuditError(f"could not create findings directory: {error}") from error
    _append_event(
        workspace_path,
        event_type="workspace_bound",
        actor=actor,
        payload={
            "project_root": project_snapshot["project_root"],
            "baseline_head": project_snapshot["head"],
            "baseline_id": baseline["id"],
            "baseline_branch": project_snapshot["branch"],
            "g0_status": "draft",
            "rationale": rationale,
            "metadata_sha256": _metadata_hash(upgraded),
            "contract_sha256": gate["contract_sha256"],
        },
    )
    _atomic_write_json(workspace_path / WORKSPACE_METADATA_NAME, upgraded)
    return copy.deepcopy(upgraded)


@_serialized_workspace_mutation(0)
def set_g0_gate(
    workspace: str | Path,
    status: str,
    *,
    reviewer: str,
    rationale: str,
    actor: str,
) -> dict[str, object]:
    """Set the named, explained G0 decision for a bound audit workspace."""

    if not isinstance(status, str):
        raise AuditError("G0 status must be a string")
    canonical_status = G0_STATUS_ALIASES.get(status)
    if canonical_status is None:
        raise AuditError(f"G0 status must be one of: {', '.join(G0_STATUS_ALIASES)}")
    reviewer = _require_text(reviewer, "reviewer")
    rationale = _require_text(rationale, "rationale")
    actor = _require_text(actor, "actor")
    workspace_path, metadata, lifecycle = _load_bound_workspace(workspace)
    verify_audit_workspace(workspace_path)
    if canonical_status == "approved":
        _assert_research_contract_complete(workspace_path)
    updated = copy.deepcopy(metadata)
    updated_lifecycle = updated["audit_lifecycle"]
    if not isinstance(updated_lifecycle, dict):
        raise AuditError("audit lifecycle is not writable")
    gate = {
        "status": canonical_status,
        "reviewer": reviewer,
        "rationale": rationale,
        "actor": actor,
        "updated_at": _utc_now(),
        "contract_sha256": _file_sha256(
            workspace_path / "research-contract-template.md", "public research contract"
        ),
    }
    updated_lifecycle["g0_gate"] = gate
    _atomic_write_json(workspace_path / WORKSPACE_METADATA_NAME, updated)
    _append_event(
        workspace_path,
        event_type="g0_gate_set",
        actor=actor,
        payload={
            "status": canonical_status,
            "reviewer": reviewer,
            "rationale": rationale,
            "metadata_sha256": _metadata_hash(updated),
            "contract_sha256": gate["contract_sha256"],
        },
    )
    return copy.deepcopy(gate)


def assess_g0_gate(workspace: str | Path) -> dict[str, object]:
    """Assess declared G0 structure and decision freshness without mutating it."""

    workspace_path, _, lifecycle = _load_bound_workspace(workspace)
    verify_audit_workspace(workspace_path)
    gate = lifecycle.get("g0_gate")
    if not isinstance(gate, dict):
        raise AuditError("G0 gate metadata is invalid")
    try:
        _assert_research_contract_complete(workspace_path)
        contract_structure = "complete"
        structure_issue: str | None = None
    except AuditError as error:
        contract_structure = "incomplete"
        structure_issue = str(error)
    current_hash = _file_sha256(
        workspace_path / "research-contract-template.md", "public research contract"
    )
    decision_current = current_hash == gate.get("contract_sha256")
    ready = (
        contract_structure == "complete"
        and decision_current
        and gate.get("status") == "approved"
    )
    report = {
        "schema_version": SCHEMA_VERSION,
        "contract_structure": contract_structure,
        "structure_issue": structure_issue,
        "declared_status": gate.get("status"),
        "declared_reviewer": gate.get("reviewer"),
        "decision_matches_contract": decision_current,
        "ready_for_preflight": ready,
        "limitation": (
            "This is a declared human decision and structural check, not identity "
            "authentication or scientific approval."
        ),
    }
    return report


def preflight(workspace: str | Path) -> dict[str, object]:
    """Require a clean, unchanged baseline and an approved G0 gate before work."""

    verify_audit_workspace(workspace)
    _, _, lifecycle = _load_bound_workspace(workspace)
    gate = lifecycle["g0_gate"]
    baseline = lifecycle["baseline"]
    project = lifecycle["project"]
    if not isinstance(gate, dict) or gate.get("status") != "approved":
        raise AuditError("G0 gate must be approved before preflight can pass")
    if not isinstance(baseline, dict) or not isinstance(project, dict):
        raise AuditError("audit lifecycle baseline is invalid")
    expected_contract_hash = gate.get("contract_sha256")
    current_contract_hash = _file_sha256(
        _existing_directory(workspace, "audit workspace") / "research-contract-template.md",
        "public research contract",
    )
    if current_contract_hash != expected_contract_hash:
        raise AuditError(
            "G0 research contract changed after the recorded decision; record a new gate decision"
        )
    current = _git_snapshot(_require_text(project.get("root"), "project root"), require_clean=True)
    if current["project_root"] != project.get("root"):
        raise AuditError("bound Git project root has changed")
    if current["head"] != baseline.get("head"):
        raise AuditError("project HEAD drift detected; use explicit rebaseline after review")
    if current["branch"] != baseline.get("branch"):
        raise AuditError("project branch drift detected; use explicit rebaseline after review")
    return {
        "ok": True,
        "project": copy.deepcopy(current),
        "baseline": copy.deepcopy(baseline),
        "g0_gate": copy.deepcopy(gate),
    }


@_serialized_workspace_mutation(0)
def rebaseline(workspace: str | Path, *, actor: str, reason: str) -> dict[str, object]:
    """Explicitly replace a clean Git baseline and reopen G0 review."""

    actor = _require_text(actor, "actor")
    reason = _require_text(reason, "reason")
    workspace_path, metadata, lifecycle = _load_bound_workspace(workspace)
    verify_audit_workspace(workspace_path)
    project = lifecycle["project"]
    if not isinstance(project, dict):
        raise AuditError("audit lifecycle project is invalid")
    current = _git_snapshot(_require_text(project.get("root"), "project root"), require_clean=True)
    now = _utc_now()
    baseline = {
        "id": f"baseline-{uuid.uuid4()}",
        "head": current["head"],
        "branch": current["branch"],
        "captured_at": now,
        "actor": actor,
        "reason": reason,
    }
    updated = copy.deepcopy(metadata)
    updated_lifecycle = updated["audit_lifecycle"]
    if not isinstance(updated_lifecycle, dict):
        raise AuditError("audit lifecycle is not writable")
    previous_baseline = updated_lifecycle.get("baseline")
    updated_lifecycle["baseline"] = baseline
    updated_lifecycle["g0_gate"] = {
        "status": "draft",
        "reviewer": actor,
        "rationale": f"Baseline replaced: {reason}",
        "actor": actor,
        "updated_at": now,
        "contract_sha256": _file_sha256(
            workspace_path / "research-contract-template.md", "public research contract"
        ),
    }
    _atomic_write_json(workspace_path / WORKSPACE_METADATA_NAME, updated)
    _append_event(
        workspace_path,
        event_type="baseline_replaced",
        actor=actor,
        payload={
            "reason": reason,
            "previous_head": previous_baseline.get("head") if isinstance(previous_baseline, dict) else None,
            "previous_baseline_id": previous_baseline.get("id") if isinstance(previous_baseline, dict) else None,
            "new_baseline_id": baseline["id"],
            "new_head": current["head"],
            "new_branch": current["branch"],
            "g0_status": "draft",
            "metadata_sha256": _metadata_hash(updated),
            "contract_sha256": updated_lifecycle["g0_gate"]["contract_sha256"],
        },
    )
    return copy.deepcopy(baseline)


@_serialized_workspace_mutation(0)
def add_finding(
    workspace: str | Path,
    *,
    finding_id: str,
    title: str,
    layer: str,
    competency: str,
    severity: str,
    claim: str,
    first_broken_contract: str,
    actor: str,
) -> dict[str, object]:
    """Add one public finding with an initially open lifecycle state.

    The finding is attributed to the active baseline, so a clean, approved
    :func:`preflight` is mandatory before it is recorded.
    """

    workspace_path, _, lifecycle = _load_bound_workspace(workspace)
    preflight(workspace_path)
    finding_id = _require_text(finding_id, "finding_id")
    path = _finding_path(workspace_path, finding_id)
    if path.is_symlink() or path.exists():
        raise AuditError(f"finding already exists: {finding_id}")
    if layer not in LAYERS:
        raise AuditError(f"layer must be one of: {', '.join(LAYERS)}")
    if competency not in COMPETENCIES:
        raise AuditError(f"competency must be one of: {', '.join(COMPETENCIES)}")
    if severity not in SEVERITIES:
        raise AuditError(f"severity must be one of: {', '.join(SEVERITIES)}")
    now = _utc_now()
    baseline = lifecycle.get("baseline")
    project = lifecycle.get("project")
    if not isinstance(baseline, dict) or not isinstance(project, dict):
        raise AuditError("audit lifecycle baseline is invalid")
    finding = {
        "schema_version": SCHEMA_VERSION,
        "id": finding_id,
        "title": _require_text(title, "title"),
        "layer": layer,
        "competency": competency,
        "severity": severity,
        "claim": _require_text(claim, "claim"),
        "first_broken_contract": _require_text(first_broken_contract, "first_broken_contract"),
        "status": "open",
        "actor": _require_text(actor, "actor"),
        "created_at": now,
        "updated_at": now,
        "baseline_snapshot": {
            "project_root": _require_text(project.get("root"), "project root"),
            "id": _require_text(baseline.get("id"), "baseline id"),
            "head": _require_text(baseline.get("head"), "baseline head"),
            "branch": baseline.get("branch"),
            "captured_at": _require_text(baseline.get("captured_at"), "baseline captured_at"),
        },
        "evidence": [],
    }
    _atomic_write_json(path, finding)
    _append_event(
        workspace_path,
        event_type="finding_created",
        actor=finding["actor"],
        payload={
            "finding_id": finding_id,
            "layer": layer,
            "competency": competency,
            "severity": severity,
            "status": "open",
            "finding_sha256": _finding_hash(finding),
        },
    )
    return copy.deepcopy(finding)


def list_findings(workspace: str | Path) -> list[dict[str, object]]:
    """Return schema-validated findings in stable filename order."""

    workspace_path, _, _ = _load_bound_workspace(workspace)
    return copy.deepcopy(_load_findings(workspace_path))


@_serialized_workspace_mutation(0)
def add_evidence(
    workspace: str | Path,
    finding_id: str,
    *,
    evidence_id: str,
    kind: str,
    reference: str,
    summary: str,
    actor: str,
) -> dict[str, object]:
    """Append evidence against the current approved baseline without judging truth."""

    workspace_path, _, lifecycle = _load_bound_workspace(workspace)
    preflight(workspace_path)
    finding = _load_finding(workspace_path, finding_id)
    if not _finding_matches_current_baseline(finding, lifecycle):
        raise AuditError(
            "evidence must not be attached to a finding from an older baseline; "
            "create a new finding ID for the current baseline"
        )
    evidence_id = _require_text(evidence_id, "evidence_id")
    if not FINDING_ID_PATTERN.fullmatch(evidence_id):
        raise AuditError("evidence_id may contain only letters, digits, dot, underscore, and hyphen")
    evidence = finding["evidence"]
    if not isinstance(evidence, list):
        raise AuditError("finding evidence is invalid")
    if any(isinstance(item, dict) and item.get("id") == evidence_id for item in evidence):
        raise AuditError(f"evidence already exists: {evidence_id}")
    canonical_kind = _require_text(kind, "kind")
    if canonical_kind not in EVIDENCE_KINDS:
        raise AuditError(f"kind must be one of: {', '.join(EVIDENCE_KINDS)}")
    entry = {
        "id": evidence_id,
        "kind": canonical_kind,
        "reference": _require_text(reference, "reference"),
        "summary": _require_text(summary, "summary"),
        "actor": _require_text(actor, "actor"),
        "recorded_at": _utc_now(),
    }
    evidence.append(entry)
    finding["actor"] = entry["actor"]
    finding["updated_at"] = entry["recorded_at"]
    _atomic_write_json(_finding_path(workspace_path, finding_id), finding)
    _append_event(
        workspace_path,
        event_type="finding_evidence_added",
        actor=entry["actor"],
        payload={
            "finding_id": finding_id,
            "evidence_id": evidence_id,
            "kind": entry["kind"],
            "finding_sha256": _finding_hash(finding),
        },
    )
    return copy.deepcopy(finding)


@_serialized_workspace_mutation(0)
def transition_finding(
    workspace: str | Path,
    finding_id: str,
    new_status: str,
    *,
    actor: str,
    rationale: str,
) -> dict[str, object]:
    """Apply one legal, explicitly explained finding-state transition.

    Non-terminal transitions remain available without :func:`preflight` so a
    reviewer can triage a changing project. Moving to ``verified`` or ``closed``
    requires recorded evidence, the current baseline snapshot, and a clean,
    approved preflight.
    """

    workspace_path, _, lifecycle = _load_bound_workspace(workspace)
    verify_audit_workspace(workspace_path)
    finding = _load_finding(workspace_path, finding_id)
    actor = _require_text(actor, "actor")
    rationale = _require_text(rationale, "rationale")
    current_status = finding.get("status")
    if not isinstance(current_status, str) or new_status not in FINDING_TRANSITIONS.get(current_status, set()):
        raise AuditError(f"illegal finding transition: {current_status} -> {new_status}")
    if new_status in TRUSTED_TERMINAL_STATUSES:
        evidence = finding.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise AuditError(f"{new_status} requires at least one recorded evidence item")
        if not _finding_matches_current_baseline(finding, lifecycle):
            raise AuditError(
                f"{new_status} requires a finding created against the current baseline; "
                "create a new finding ID after rebaseline"
            )
        preflight(workspace_path)
    finding["status"] = new_status
    finding["actor"] = actor
    finding["updated_at"] = _utc_now()
    _atomic_write_json(_finding_path(workspace_path, finding_id), finding)
    _append_event(
        workspace_path,
        event_type="finding_status_changed",
        actor=actor,
        payload={
            "finding_id": finding_id,
            "from_status": current_status,
            "to_status": new_status,
            "rationale": rationale,
            "finding_sha256": _finding_hash(finding),
        },
    )
    return copy.deepcopy(finding)


def verify_audit_workspace(workspace: str | Path) -> dict[str, object]:
    """Verify public metadata and local hash-chain consistency only.

    This check detects inconsistencies between current finding snapshots and
    their logged lifecycle hashes. It is not a scientific, legal, or deployment
    correctness determination.
    """

    workspace_path, metadata, lifecycle = _load_bound_workspace(workspace)
    findings = _load_findings(workspace_path)
    events = _read_events(workspace_path, allow_missing=False)
    if not events:
        raise AuditError("bound audit workspace must contain at least one lifecycle event")
    _verify_metadata_event_hash(metadata, events)
    _verify_finding_event_hashes(findings, events)
    _verify_event_semantics(findings, events)
    stale_count = sum(
        not _finding_matches_current_baseline(finding, lifecycle) for finding in findings
    )
    return {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "validator_scope": "local_hash_chain_lifecycle_integrity_only",
        "workspace": str(workspace_path),
        "project": copy.deepcopy(lifecycle["project"]),
        "baseline": copy.deepcopy(lifecycle["baseline"]),
        "g0_gate": copy.deepcopy(lifecycle["g0_gate"]),
        "finding_count": len(findings),
        "stale_finding_count": stale_count,
        "event_count": len(events),
        "last_event_hash": events[-1]["event_hash"],
    }


def build_report_data(workspace: str | Path) -> dict[str, object]:
    """Return report-ready data without creating or modifying any file."""

    verification = verify_audit_workspace(workspace)
    workspace_path, _, lifecycle = _load_bound_workspace(workspace)
    findings = _load_findings(workspace_path)
    report_findings: list[dict[str, object]] = []
    by_status = {status: 0 for status in FINDING_STATUSES}
    by_layer = {layer: 0 for layer in LAYERS}
    by_competency = {competency: 0 for competency in COMPETENCIES}
    by_severity = {severity: 0 for severity in SEVERITIES}
    for finding in findings:
        by_status[str(finding["status"])] += 1
        by_layer[str(finding["layer"])] += 1
        by_competency[str(finding["competency"])] += 1
        by_severity[str(finding["severity"])] += 1
        report_finding = copy.deepcopy(finding)
        baseline_current = _finding_matches_current_baseline(finding, lifecycle)
        report_finding["baseline_current"] = baseline_current
        report_finding["baseline_state"] = "current" if baseline_current else "stale"
        report_findings.append(report_finding)
    try:
        preflight_result: dict[str, object] | None = preflight(workspace_path)
        preflight_issue: str | None = None
    except AuditError as error:
        preflight_result = None
        preflight_issue = str(error)
    stale_finding_count = sum(
        1 for finding in report_findings if not finding["baseline_current"]
    )
    report_status = (
        "review-ready"
        if preflight_result is not None and stale_finding_count == 0
        else "draft"
    )
    report: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "validator_scope": "local_hash_chain_lifecycle_integrity_only",
        "report_status": report_status,
        "limitations": [
            "Local hash-chain consistency is not external immutability or identity authentication.",
            "Recorded evidence and human declarations are not automatically judged for scientific correctness.",
            "No audited-project code is executed and no network resource is fetched by this report builder.",
        ],
        "preflight": preflight_result,
        "preflight_issue": preflight_issue,
        "verification": verification,
        "project": copy.deepcopy(lifecycle["project"]),
        "baseline": copy.deepcopy(lifecycle["baseline"]),
        "g0_gate": copy.deepcopy(lifecycle["g0_gate"]),
        "summary": {
            "finding_count": len(findings),
            "stale_finding_count": stale_finding_count,
            "by_status": by_status,
            "by_layer": by_layer,
            "by_competency": by_competency,
            "by_severity": by_severity,
        },
        "findings": report_findings,
    }
    final_verification = verify_audit_workspace(workspace_path)
    if (
        final_verification.get("last_event_hash") != verification.get("last_event_hash")
        or final_verification.get("event_count") != verification.get("event_count")
    ):
        raise AuditError("audit workspace changed while the report snapshot was being built")
    return report


_MARKDOWN_TEXT_ESCAPES = str.maketrans(
    {character: f"&#{ord(character)};" for character in "&<>|`*_[]()#\\"}
)


def _markdown_text(value: object) -> str:
    """Render untrusted record text without letting it create Markdown syntax."""

    return (
        str(value)
        .translate(_MARKDOWN_TEXT_ESCAPES)
        .replace("\r", "&#13;")
        .replace("\n", "<br />")
    )


def _markdown_code(value: object) -> str:
    return f"<code>{_markdown_text(value)}</code>"


def _markdown_cell(value: object) -> str:
    return _markdown_text(value)


def render_report_markdown(workspace: str | Path) -> str:
    """Render a Markdown view of :func:`build_report_data` without writing it."""

    report = build_report_data(workspace)
    project = report["project"]
    baseline = report["baseline"]
    gate = report["g0_gate"]
    summary = report["summary"]
    if not isinstance(project, dict) or not isinstance(baseline, dict) or not isinstance(gate, dict):
        raise AuditError("report lifecycle data is invalid")
    if not isinstance(summary, dict):
        raise AuditError("report summary is invalid")
    lines = [
        "# Research Code Stewardship Audit Report",
        "",
        f"> Report status: **{str(report.get('report_status')).upper()}**. This status describes record readiness only; it does not declare scientific correctness, legal compliance, or deployment readiness.",
        "",
        "## Bound project",
        "",
        f"- Root: {_markdown_code(project.get('root'))}",
        f"- Baseline ID: {_markdown_code(baseline.get('id'))}",
        f"- Baseline HEAD: {_markdown_code(baseline.get('head'))}",
        f"- Baseline branch: {_markdown_code(baseline.get('branch'))}",
        f"- G0 gate: **{_markdown_text(gate.get('status'))}** — reviewer: {_markdown_text(gate.get('reviewer'))}",
        f"- Preflight issue: {_markdown_text(report.get('preflight_issue') or 'None recorded')}",
        "",
        "## Finding summary",
        "",
        f"- Total findings: {summary.get('finding_count')}",
        f"- Findings from an older baseline: {summary.get('stale_finding_count')}",
        f"- By status: {summary.get('by_status')}",
        f"- By severity: {summary.get('by_severity')}",
        "",
        "## Findings",
        "",
        "| ID | Layer | Competency | Severity | Status | Baseline | Title |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    findings = report["findings"]
    if not isinstance(findings, list):
        raise AuditError("report findings are invalid")
    for finding in findings:
        if not isinstance(finding, dict):
            raise AuditError("report finding is invalid")
        lines.append(
            "| {id} | {layer} | {competency} | {severity} | {status} | {baseline} | {title} |".format(
                id=_markdown_cell(finding.get("id")),
                layer=_markdown_cell(finding.get("layer")),
                competency=_markdown_cell(finding.get("competency")),
                severity=_markdown_cell(finding.get("severity")),
                status=_markdown_cell(finding.get("status")),
                baseline=_markdown_cell(finding.get("baseline_state")),
                title=_markdown_cell(finding.get("title")),
            )
        )
    lines.extend(["", "## Finding details", ""])
    if not findings:
        lines.append("No findings were recorded in this snapshot.")
    for finding in findings:
        evidence = finding.get("evidence")
        if not isinstance(evidence, list):
            raise AuditError("report finding evidence is invalid")
        lines.extend(
            [
                f"### {_markdown_cell(finding.get('id'))} — {_markdown_cell(finding.get('title'))}",
                "",
                f"- Claim under review: {_markdown_cell(finding.get('claim'))}",
                f"- First broken contract: {_markdown_cell(finding.get('first_broken_contract'))}",
                f"- Baseline state: {_markdown_cell(finding.get('baseline_state'))}",
                f"- Evidence records: {len(evidence)}",
            ]
        )
        for item in evidence:
            if not isinstance(item, dict):
                raise AuditError("report evidence item is invalid")
            lines.append(
                "  - {id} [{kind}] — {summary} ({reference})".format(
                    id=_markdown_cell(item.get("id")),
                    kind=_markdown_cell(item.get("kind")),
                    summary=_markdown_cell(item.get("summary")),
                    reference=_markdown_code(item.get("reference")),
                )
            )
    limitations = report.get("limitations")
    if not isinstance(limitations, list) or not all(
        isinstance(item, str) for item in limitations
    ):
        raise AuditError("report limitations are invalid")
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {_markdown_text(item)}" for item in limitations)
    return "\n".join(lines) + "\n"
