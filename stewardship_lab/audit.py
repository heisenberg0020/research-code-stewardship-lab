"""Public, filesystem-local lifecycle support for real research-code audits.

This module deliberately operates only on an explicitly supplied audit workspace,
the Git project bound to it, and four well-known workspace files. It never walks
training-package directories or resolves instructor-only material.
"""

from __future__ import annotations

import copy
from contextlib import contextmanager
from datetime import datetime, timezone
import errno
from functools import wraps
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import threading
import uuid

from . import audit_evidence as _audit_evidence
from .bindings import BindingError, case_ref, subject_ref, validate_case_ref

try:  # POSIX advisory locks are the required local concurrency primitive.
    import fcntl as _fcntl
except ImportError:  # pragma: no cover - exercised only on non-POSIX Python.
    _fcntl = None


SCHEMA_VERSION = 2
WORKSPACE_METADATA_NAME = "audit-workspace.json"
FINDINGS_DIRECTORY_NAME = "findings"
EVENT_LOG_NAME = "audit-events.jsonl"
PENDING_COMMIT_NAME = ".rcsl-audit-pending.json"
LOCK_FILE_NAME = ".rcsl-write.lock"
LEGACY_PENDING_COMMIT_SCHEMA_VERSION = 1
PENDING_COMMIT_SCHEMA_VERSION = 2
LIFECYCLE_PROJECTION_MODE = "full_v1"
ISOLATED_DIRECTORY_NAME = "DO_NOT_OPEN_UNTIL_FINISHED"
MAX_AUDIT_FILE_BYTES = 16_000_000
MAX_EVENT_LOG_BYTES = 48_000_000
# A pending commit contains one bounded snapshot and one event encoded in JSON.
# The factor of two leaves room for JSON string escaping.
MAX_PENDING_COMMIT_BYTES = 2 * (MAX_AUDIT_FILE_BYTES + MAX_EVENT_LOG_BYTES) + 1_000_000
MAX_FINDINGS = 10_000
MAX_EVIDENCE_PER_FINDING = 10_000
MAX_TOTAL_EVIDENCE = 50_000
MAX_EVENTS = 100_000

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
LIFECYCLE_EVENT_TYPES = frozenset(
    {"workspace_bound", "g0_gate_set", "baseline_replaced"}
)
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
EVIDENCE_GATED_STATUSES = ("verified", "closed")
CONTENT_TERMINAL_KINDS = frozenset({"observed", "derived", "reproduced"})
REFERENCE_ONLY_PROFILE = "reference-only"
CONTENT_BOUND_PROFILE = "content-bound-v1"
FINDING_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z")
CONTRACT_PLACEHOLDER_PATTERN = re.compile(
    r"\{\{[^{}\n]+\}\}|\[TODO\]|\[填写\]|待填写|^\s*(?:TODO|TBD)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
LEGACY_CONTRACT_DECISION_PATTERN = re.compile(
    r"^\s*[-*]\s+(?:"
    r"Status\s+\(`draft`,\s*`approved`,\s*or\s*`blocked`\)"
    r"|Decision\s+\(`approve`,\s*`revise`,\s*or\s*`stop`\)"
    r"|Approver\s+and\s+date"
    r")\s*:",
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


_WORKSPACE_LOCK_STATE = threading.local()


@contextmanager
def _workspace_advisory_lock(workspace: Path, *, exclusive: bool):
    """Hold one process-scoped advisory lock on a fixed workspace lock file.

    Closing the descriptor releases the kernel lock, including after process
    death.  The harmless lock file deliberately remains in place.  Reentrant
    shared reads (and reads inside an exclusive mutation) reuse the outer lock;
    a shared-to-exclusive upgrade is refused instead of risking deadlock.
    """

    if _fcntl is None:
        raise AuditError(
            "audit workspace locking requires POSIX fcntl.flock; this platform "
            "is not supported"
        )
    key = str(workspace)
    states = getattr(_WORKSPACE_LOCK_STATE, "states", None)
    if states is None:
        states = {}
        _WORKSPACE_LOCK_STATE.states = states
    existing = states.get(key)
    if existing is not None:
        if exclusive and not existing["exclusive"]:
            raise AuditError(
                "cannot upgrade an audit workspace read lock to a write lock"
            )
        existing["depth"] += 1
        try:
            yield
        finally:
            existing["depth"] -= 1
        return

    lock_path = workspace / LOCK_FILE_NAME
    descriptor: int | None = None
    try:
        descriptor = os.open(
            lock_path,
            os.O_CREAT
            | os.O_RDWR
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            0o600,
        )
    except OSError as error:
        raise AuditError(f"could not open audit workspace lock: {error}") from error
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise AuditError("audit workspace lock path must be a regular file")
        operation = (_fcntl.LOCK_EX if exclusive else _fcntl.LOCK_SH) | _fcntl.LOCK_NB
        try:
            _fcntl.flock(descriptor, operation)
        except OSError as error:
            if error.errno in {errno.EACCES, errno.EAGAIN}:
                role = "another reader or writer" if exclusive else "another writer"
                raise AuditError(f"audit workspace is locked by {role}") from error
            raise AuditError(
                f"could not acquire audit workspace advisory lock: {error}"
            ) from error
        states[key] = {
            "depth": 1,
            "descriptor": descriptor,
            "exclusive": exclusive,
        }
        yield
    finally:
        current = states.get(key)
        if current is not None and current.get("descriptor") == descriptor:
            states.pop(key, None)
        if descriptor is not None:
            try:
                _fcntl.flock(descriptor, _fcntl.LOCK_UN)
            except OSError:
                # close() still releases the process-scoped lock.
                pass
            os.close(descriptor)


@contextmanager
def audit_workspace_read_lock(workspace_value: str | Path):
    """Expose one fail-closed shared boundary for composite CLI reads."""

    workspace = _existing_directory(workspace_value, "audit workspace")
    with _workspace_advisory_lock(workspace, exclusive=False):
        _assert_no_pending_commit(workspace)
        try:
            yield workspace
        finally:
            _assert_no_pending_commit(workspace)


def _serialized_workspace_read(workspace_argument_index: int):
    """Decorate a public read whose workspace is one positional argument."""

    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            if len(args) > workspace_argument_index:
                workspace_value = args[workspace_argument_index]
            else:
                workspace_value = kwargs.get("workspace", kwargs.get("workspace_value"))
            if workspace_value is None:
                raise AuditError("workspace is required")
            with audit_workspace_read_lock(workspace_value):
                return function(*args, **kwargs)

        return wrapped

    return decorate


def _serialized_workspace_mutation(
    workspace_argument_index: int, *, allow_pending: bool = False
):
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
            with _workspace_advisory_lock(workspace, exclusive=True):
                if not allow_pending:
                    _assert_no_pending_commit(workspace)
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
        with _workspace_advisory_lock(workspace_path, exclusive=True):
            _assert_no_pending_commit(workspace_path)
            return function(project, workspace, *args, **kwargs)

    return wrapped


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _require_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AuditError(f"{field} must be a non-empty string")
    return value.strip()


def _content_call(function, *args, **kwargs):
    """Translate the content-binding module's errors at the audit boundary."""

    try:
        return function(*args, **kwargs)
    except _audit_evidence.AuditEvidenceError as error:
        raise AuditError(f"audit content binding is invalid: {error}") from error


def _binding_call(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except BindingError as error:
        raise AuditError(f"audit content binding is invalid: {error}") from error


def _content_binding(lifecycle: dict[str, object]) -> dict[str, object] | None:
    if "content_binding" not in lifecycle:
        return None
    return _content_call(
        _audit_evidence.validate_content_binding,
        lifecycle["content_binding"],
    )


def _audit_lineage_subject_ref(
    events: list[dict[str, object]],
) -> dict[str, str]:
    """Derive an unauthenticated local lineage from the immutable bind event."""

    if not events or events[0].get("event_type") != "workspace_bound":
        raise AuditError("audit lineage requires the first workspace_bound event")
    first_hash = events[0].get("event_hash")
    if not isinstance(first_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", first_hash):
        raise AuditError("audit lineage requires a valid first event hash")
    digest = hashlib.sha256(
        b"rcsl-audit-lineage-v1\0" + first_hash.encode("ascii")
    ).hexdigest()
    return _binding_call(
        subject_ref,
        f"audit/lineage/{digest}",
        "git-project",
    )


def _research_contract_bytes(workspace: Path) -> bytes:
    return _read_regular_bytes(
        workspace / _audit_evidence.CONTRACT_ARTIFACT_PATH,
        "public research contract",
        maximum_bytes=MAX_AUDIT_FILE_BYTES,
    )


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


def _fsync_directory(directory: Path) -> None:
    """Make a completed rename/unlink durable on supported local POSIX filesystems."""

    if os.name != "posix":
        return
    descriptor: int | None = None
    try:
        descriptor = os.open(
            directory,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
        )
        os.fsync(descriptor)
    except OSError as error:
        raise AuditError(
            f"could not make directory update durable for {directory}: {error}"
        ) from error
    finally:
        if descriptor is not None:
            os.close(descriptor)


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
        _fsync_directory(path.parent)
    except OSError as error:
        raise AuditError(f"could not write {path.name}: {error}") from error
    finally:
        if temporary_path.exists() or temporary_path.is_symlink():
            temporary_path.unlink(missing_ok=True)


def _json_snapshot_text(payload: dict[str, object], label: str) -> str:
    """Serialize and bound one prospective public snapshot before any write."""

    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if len(text.encode("utf-8")) > MAX_AUDIT_FILE_BYTES:
        raise AuditError(f"{label} exceeds the {MAX_AUDIT_FILE_BYTES}-byte limit")
    return text


def _sha256_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _optional_regular_text(path: Path, label: str, *, maximum_bytes: int) -> str | None:
    """Read an optional regular UTF-8 file without treating a missing file as corruption."""

    try:
        path.lstat()
    except FileNotFoundError:
        return None
    if path.is_symlink() or not path.is_file():
        raise AuditError(f"{label} must be a regular file when present: {path}")
    try:
        return _read_regular_bytes(path, label, maximum_bytes=maximum_bytes).decode("utf-8")
    except UnicodeDecodeError as error:
        raise AuditError(f"could not read {label}: {error.__class__.__name__}") from error


def _read_regular_bytes(path: Path, label: str, *, maximum_bytes: int) -> bytes:
    descriptor: int | None = None
    try:
        expected = path.lstat()
        if not stat.S_ISREG(expected.st_mode) or path.is_symlink():
            raise AuditError(f"missing regular {label}: {path}")
        descriptor = os.open(
            path,
            os.O_RDONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0),
        )
        before = os.fstat(descriptor)
        expected_identity = (
            expected.st_dev,
            expected.st_ino,
            expected.st_size,
            expected.st_mtime_ns,
            expected.st_mode,
        )
        before_identity = (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_mode,
        )
        if not stat.S_ISREG(before.st_mode) or before_identity != expected_identity:
            raise AuditError(f"{label} changed before it could be read safely")
        if before.st_size > maximum_bytes:
            raise AuditError(f"{label} exceeds the {maximum_bytes}-byte limit")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(65_536, maximum_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > maximum_bytes:
                raise AuditError(f"{label} exceeds the {maximum_bytes}-byte limit")
        after = os.fstat(descriptor)
        after_identity = (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_mode,
        )
        if after_identity != before_identity:
            raise AuditError(f"{label} changed while it was being read")
        return b"".join(chunks)
    except AuditError:
        raise
    except OSError as error:
        raise AuditError(f"could not read {label}: {error.__class__.__name__}") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _read_json_object(
    path: Path, label: str, *, maximum_bytes: int = MAX_AUDIT_FILE_BYTES
) -> dict[str, object]:
    try:
        payload = json.loads(
            _read_regular_bytes(path, label, maximum_bytes=maximum_bytes).decode("utf-8")
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
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

    return hashlib.sha256(
        _read_regular_bytes(path, label, maximum_bytes=MAX_AUDIT_FILE_BYTES)
    ).hexdigest()


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


def _parse_events_text(text: str) -> list[dict[str, object]]:
    """Parse and validate one already-bounded event-log after-image."""

    events: list[dict[str, object]] = []
    for line_number, line in enumerate(io.StringIO(text), start=1):
        if len(events) >= MAX_EVENTS:
            raise AuditError(f"event log exceeds the {MAX_EVENTS}-event limit")
        line = line.rstrip("\r\n")
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


def _event_log_text(events: list[dict[str, object]]) -> str:
    if len(events) > MAX_EVENTS:
        raise AuditError(f"event log would exceed the {MAX_EVENTS}-event limit")
    _validate_event_chain(events)
    text = "".join(
        json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n" for event in events
    )
    if len(text.encode("utf-8")) > MAX_EVENT_LOG_BYTES:
        raise AuditError(f"event log would exceed the {MAX_EVENT_LOG_BYTES}-byte limit")
    return text


def _read_events(workspace: Path, *, allow_missing: bool) -> list[dict[str, object]]:
    event_path = workspace / EVENT_LOG_NAME
    if event_path.is_symlink():
        raise AuditError("event log must not be a symlink")
    if not event_path.is_file():
        if allow_missing and not event_path.exists():
            return []
        raise AuditError(f"missing regular event log: {event_path}")
    try:
        text = _read_regular_bytes(
            event_path, "event log", maximum_bytes=MAX_EVENT_LOG_BYTES
        ).decode("utf-8")
    except UnicodeDecodeError as error:
        raise AuditError(f"could not read event log: {error.__class__.__name__}") from error
    return _parse_events_text(text)


def _pending_commit_path(workspace: Path) -> Path:
    return workspace / PENDING_COMMIT_NAME


def _pending_commit_exists(workspace: Path) -> bool:
    return os.path.lexists(_pending_commit_path(workspace))


def _assert_no_pending_commit(workspace: Path) -> None:
    if _pending_commit_exists(workspace):
        raise AuditError(
            "audit workspace has an interrupted lifecycle commit; run `audit recover` "
            "before reading or writing it"
        )


def _valid_sha256_or_none(value: object, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise AuditError(f"pending commit {label} is invalid")
    return value


def _validate_snapshot_relative_path(value: object) -> str:
    relative = _require_text(value, "pending commit snapshot path")
    if relative == WORKSPACE_METADATA_NAME:
        return relative
    parts = relative.split("/")
    if len(parts) != 2 or parts[0] != FINDINGS_DIRECTORY_NAME:
        raise AuditError("pending commit snapshot path is not allowed")
    filename = parts[1]
    if not filename.endswith(".json"):
        raise AuditError("pending commit finding path is invalid")
    finding_id = filename[: -len(".json")]
    if not FINDING_ID_PATTERN.fullmatch(finding_id):
        raise AuditError("pending commit finding path is invalid")
    return relative


def _write_pending_commit(workspace: Path, body: dict[str, object]) -> None:
    path = _pending_commit_path(workspace)
    if _pending_commit_exists(workspace):
        raise AuditError("audit workspace already has a pending lifecycle commit")
    content = json.dumps(body, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if len(content.encode("utf-8")) > MAX_PENDING_COMMIT_BYTES:
        raise AuditError(
            f"pending commit exceeds the {MAX_PENDING_COMMIT_BYTES}-byte limit"
        )
    _atomic_write_text(path, content)


def _pending_content_hash(manifest: dict[str, object]) -> str:
    bound = {key: value for key, value in manifest.items() if key != "content_sha256"}
    return hashlib.sha256(_canonical_json(bound).encode("utf-8")).hexdigest()


def _read_pending_commit(workspace: Path) -> dict[str, object] | None:
    path = _pending_commit_path(workspace)
    if not _pending_commit_exists(workspace):
        return None
    manifest = _read_json_object(
        path, "pending audit commit", maximum_bytes=MAX_PENDING_COMMIT_BYTES
    )
    schema_version = manifest.get("schema_version")
    if type(schema_version) is not int or schema_version not in {
        LEGACY_PENDING_COMMIT_SCHEMA_VERSION,
        PENDING_COMMIT_SCHEMA_VERSION,
    }:
        raise AuditError("pending audit commit schema version is not supported")
    common_keys = {
        "schema_version",
        "transaction_id",
        "snapshot_path",
        "snapshot_before_sha256",
        "snapshot_after",
        "event",
    }
    if schema_version == LEGACY_PENDING_COMMIT_SCHEMA_VERSION:
        expected_keys = common_keys
    else:
        expected_keys = common_keys | {
            "snapshot_after_sha256",
            "event_log_before_sha256",
            "event_log_after_sha256",
            "content_sha256",
        }
    if set(manifest) != expected_keys:
        raise AuditError("pending audit commit has an unexpected schema")
    _require_text(manifest.get("transaction_id"), "pending commit transaction_id")
    _validate_snapshot_relative_path(manifest.get("snapshot_path"))
    _valid_sha256_or_none(
        manifest.get("snapshot_before_sha256"), "snapshot before hash"
    )
    if not isinstance(manifest.get("snapshot_after"), dict):
        raise AuditError("pending commit snapshot after-image is invalid")
    if not isinstance(manifest.get("event"), dict):
        raise AuditError("pending commit event is invalid")
    if schema_version == PENDING_COMMIT_SCHEMA_VERSION:
        snapshot_after_hash = _valid_sha256_or_none(
            manifest.get("snapshot_after_sha256"), "snapshot after hash"
        )
        if snapshot_after_hash is None:
            raise AuditError("pending commit snapshot after hash is invalid")
        _valid_sha256_or_none(
            manifest.get("event_log_before_sha256"), "event log before hash"
        )
        event_log_after_hash = _valid_sha256_or_none(
            manifest.get("event_log_after_sha256"), "event log after hash"
        )
        if event_log_after_hash is None:
            raise AuditError("pending commit event log after hash is invalid")
        content_hash = _valid_sha256_or_none(
            manifest.get("content_sha256"), "content hash"
        )
        if content_hash is None or content_hash != _pending_content_hash(manifest):
            raise AuditError("pending commit content hash does not match its intent")
        snapshot_text = _json_snapshot_text(
            manifest["snapshot_after"], "pending commit snapshot"
        )
        if _sha256_text(snapshot_text) != snapshot_after_hash:
            raise AuditError(
                "pending commit snapshot after hash does not match its after-image"
            )
    return manifest


def _delete_pending_commit(workspace: Path) -> None:
    path = _pending_commit_path(workspace)
    if path.is_symlink() or not path.is_file():
        raise AuditError("pending audit commit is missing or is not a regular file")
    try:
        path.unlink()
    except OSError as error:
        raise AuditError(f"could not remove pending audit commit: {error}") from error
    try:
        _fsync_directory(workspace)
    except AuditError:
        # The after-images are already durable. If this unlink is lost in a crash,
        # the intent may reappear and the idempotent recovery path can remove it.
        pass


def _build_event_update(
    workspace: Path,
    *,
    event_type: str,
    actor: str,
    payload: dict[str, object],
    allow_missing: bool = False,
) -> tuple[dict[str, object], list[dict[str, object]], str | None, str]:
    """Build and bound a prospective event-log update without writing it."""

    event_log_before = _optional_regular_text(
        workspace / EVENT_LOG_NAME,
        "event log",
        maximum_bytes=MAX_EVENT_LOG_BYTES,
    )
    if event_log_before is None:
        if not allow_missing:
            raise AuditError(f"missing regular event log: {workspace / EVENT_LOG_NAME}")
        events: list[dict[str, object]] = []
    else:
        if allow_missing:
            raise AuditError("pending bind requires the event log to be absent")
        events = _parse_events_text(event_log_before)
    if len(events) >= MAX_EVENTS:
        raise AuditError(f"event log has reached the {MAX_EVENTS}-event limit")
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
    updated_events = [*events, event]
    event_log_text = _event_log_text(updated_events)
    return event, updated_events, event_log_before, event_log_text


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


def _assert_workspace_project_separation(
    workspace: Path, lifecycle: dict[str, object]
) -> Path:
    """Revalidate the bound Git root and require both roots to remain non-nested."""

    current_workspace = _existing_directory(workspace, "audit workspace")
    project = lifecycle.get("project")
    if not isinstance(project, dict):
        raise AuditError("audit lifecycle project is invalid")
    stored_root_text = _require_text(project.get("root"), "project root")
    stored_root = _existing_directory(stored_root_text, "bound Git project")
    canonical_root_text = _run_git(stored_root, "rev-parse", "--show-toplevel")
    canonical_root = _existing_directory(canonical_root_text, "bound Git project root")
    if str(canonical_root) != stored_root_text:
        raise AuditError("stored project root does not match the current canonical Git root")
    if _is_within(current_workspace, canonical_root) or _is_within(
        canonical_root, current_workspace
    ):
        raise AuditError("audit workspace must remain outside the bound Git project")
    return canonical_root


def _validate_public_workspace(
    workspace_value: str | Path, *, allow_pending: bool = False
) -> tuple[Path, dict[str, object]]:
    workspace = _existing_directory(workspace_value, "audit workspace")
    if not allow_pending:
        _assert_no_pending_commit(workspace)
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
        contract = _read_regular_bytes(
            contract_path,
            "public research contract",
            maximum_bytes=MAX_AUDIT_FILE_BYTES,
        ).decode("utf-8")
    except UnicodeDecodeError as error:
        raise AuditError(f"could not read public research contract: {error.__class__.__name__}") from error
    if LEGACY_CONTRACT_DECISION_PATTERN.search(contract):
        raise AuditError(
            "G0 research contract uses legacy duplicate decision fields; remove the "
            "Status and final Human gate decision fields, then record the authoritative "
            "decision with `audit gate record`"
        )
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
    projection_mode = lifecycle.get("event_projection_mode")
    if projection_mode not in (None, LIFECYCLE_PROJECTION_MODE):
        raise AuditError("audit lifecycle event projection mode is not recognized")
    _content_binding(lifecycle)

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


def _load_bound_workspace(
    workspace_value: str | Path, *, allow_pending: bool = False
) -> tuple[Path, dict[str, object], dict[str, object]]:
    workspace, metadata = _validate_public_workspace(
        workspace_value, allow_pending=allow_pending
    )
    lifecycle = _lifecycle_from_metadata(metadata)
    _assert_workspace_project_separation(workspace, lifecycle)
    return workspace, metadata, lifecycle


@_serialized_workspace_read(0)
def validate_bound_workspace_separation(
    workspace_value: str | Path,
) -> dict[str, str]:
    """Validate and expose the canonical roots for a bound public workspace."""

    workspace, metadata = _validate_public_workspace(workspace_value)
    lifecycle = _lifecycle_from_metadata(metadata)
    project_root = _assert_workspace_project_separation(workspace, lifecycle)
    return {"workspace": str(workspace), "project_root": str(project_root)}


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


def _is_content_evidence(item: object) -> bool:
    return (
        isinstance(item, dict)
        and item.get("record_type") == _audit_evidence.CONTENT_EVIDENCE_RECORD_TYPE
    )


def _validate_evidence_item(
    item: object, finding_id: str, seen_ids: set[str]
) -> bool:
    """Validate one legacy or content-bound entry; return True for content."""

    if not isinstance(item, dict):
        raise AuditError(f"finding {finding_id} evidence entries must be objects")
    if _is_content_evidence(item):
        record = _content_call(_audit_evidence.validate_content_evidence_record, item)
        evidence_id = record["id"]
        if not isinstance(evidence_id, str) or not FINDING_ID_PATTERN.fullmatch(evidence_id):
            raise AuditError(f"finding {finding_id} evidence id is invalid")
        if evidence_id in seen_ids:
            raise AuditError(
                f"finding {finding_id} contains duplicate evidence id: {evidence_id}"
            )
        seen_ids.add(evidence_id)
        return True
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
    return False


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
    normalized_case = None
    if "case_ref" in finding:
        normalized_case = _binding_call(validate_case_ref, finding["case_ref"])
        if normalized_case["case_id"] != baseline_snapshot.get("id"):
            raise AuditError("finding case_ref must match its baseline snapshot id")
    evidence = finding.get("evidence")
    if not isinstance(evidence, list):
        raise AuditError("finding evidence must be a list")
    seen_ids: set[str] = set()
    for item in evidence:
        content_entry = _validate_evidence_item(item, finding_id, seen_ids)
        if normalized_case is None and content_entry:
            raise AuditError("content evidence requires a content-bound finding")
        if (
            normalized_case is not None
            and content_entry
            and item.get("case_ref") != normalized_case
        ):
            raise AuditError("content evidence case_ref must match its finding case_ref")
    return finding


def _load_finding(workspace: Path, finding_id: str) -> dict[str, object]:
    path = _finding_path(workspace, finding_id)
    return _validate_finding(_read_json_object(path, "finding"), expected_id=finding_id)


def _load_findings(workspace: Path) -> list[dict[str, object]]:
    directory = _validated_findings_directory(workspace)
    names: list[str] = []
    try:
        with os.scandir(directory) as entries:
            for entry in entries:
                if len(names) >= MAX_FINDINGS:
                    raise AuditError(
                        f"findings directory exceeds the {MAX_FINDINGS}-finding limit"
                    )
                names.append(entry.name)
    except AuditError:
        raise
    except OSError as error:
        raise AuditError(
            f"could not enumerate findings directory: {error.__class__.__name__}"
        ) from error
    findings: list[dict[str, object]] = []
    total_evidence = 0
    for name in sorted(names):
        path = directory / name
        if path.name == ISOLATED_DIRECTORY_NAME:
            raise AuditError("findings directory contains an isolated-material path")
        if path.is_symlink() or not path.is_file() or path.suffix != ".json":
            raise AuditError(f"findings directory contains an unexpected entry: {path.name}")
        finding_id = path.stem
        finding = _validate_finding(
            _read_json_object(path, "finding"), expected_id=finding_id
        )
        evidence = finding.get("evidence")
        if not isinstance(evidence, list) or len(evidence) > MAX_EVIDENCE_PER_FINDING:
            raise AuditError(
                f"finding {finding_id} exceeds the {MAX_EVIDENCE_PER_FINDING}-evidence limit"
            )
        total_evidence += len(evidence)
        if total_evidence > MAX_TOTAL_EVIDENCE:
            raise AuditError(
                f"findings exceed the {MAX_TOTAL_EVIDENCE}-evidence aggregate limit"
            )
        findings.append(finding)
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


def _finding_matches_current_case(
    finding: dict[str, object], lifecycle: dict[str, object]
) -> bool:
    binding = _content_binding(lifecycle)
    return (
        binding is not None
        and "case_ref" in finding
        and finding.get("case_ref") == binding["case_ref"]
    )


def _expected_current_case_ref(
    lifecycle: dict[str, object], contract_bytes: bytes, events: list[dict[str, object]]
) -> dict[str, str]:
    baseline = lifecycle.get("baseline")
    if not isinstance(baseline, dict):
        raise AuditError("audit lifecycle baseline is invalid")
    manifest = _content_call(
        _audit_evidence.build_audit_case_manifest,
        _audit_lineage_subject_ref(events),
        _require_text(baseline.get("id"), "baseline id"),
        _require_text(baseline.get("head"), "baseline head"),
        contract_bytes,
    )
    return _binding_call(case_ref, manifest)


def _verify_content_layer(
    workspace: Path,
    lifecycle: dict[str, object],
    findings: list[dict[str, object]],
    contract_bytes: bytes,
    events: list[dict[str, object]],
) -> dict[str, object]:
    """Verify content-bound records without making an evidence-sufficiency claim."""

    binding = _content_binding(lifecycle)
    content_findings = [finding for finding in findings if "case_ref" in finding]
    if binding is None:
        if content_findings:
            raise AuditError("content-bound findings require lifecycle content_binding")
        return {
            "evidence_profile": REFERENCE_ONLY_PROFILE,
            "content_binding_state": "absent",
            "current_case_ref": None,
            "content_finding_count": 0,
            "content_evidence_count": 0,
            "content_store": None,
        }

    active_case = binding["case_ref"]
    if not isinstance(active_case, dict):
        raise AuditError("audit lifecycle content binding case_ref is invalid")
    subject = _audit_lineage_subject_ref(events)
    if active_case.get("subject_id") != subject["id"]:
        raise AuditError("content binding subject_id does not match the audit lineage")

    historical_cases: dict[str, dict[str, str]] = {}
    approved_case_claims: list[tuple[dict[str, str], dict[str, object]]] = []

    def retain_case(value: object) -> None:
        reference = _binding_call(validate_case_ref, value)
        digest = reference["case_sha256"]
        previous = historical_cases.get(digest)
        if previous is not None and previous != reference:
            raise AuditError("contradictory historical CaseRefs share one digest")
        historical_cases.setdefault(digest, reference)

    for event in events:
        payload = event.get("payload")
        projection = (
            payload.get("lifecycle_projection") if isinstance(payload, dict) else None
        )
        if not isinstance(projection, dict) or "content_binding" not in projection:
            continue
        projected_binding = _content_binding(projection)
        if projected_binding is not None:
            projected_case = projected_binding["case_ref"]
            retain_case(projected_case)
            projected_gate = projection.get("g0_gate")
            if (
                isinstance(projected_gate, dict)
                and projected_gate.get("status") == "approved"
            ):
                approved_case_claims.append((projected_case, projection))
    records: list[object] = []
    for finding in content_findings:
        finding_case = finding.get("case_ref")
        if not isinstance(finding_case, dict):
            raise AuditError("content-bound finding case_ref is invalid")
        if finding_case.get("subject_id") != subject["id"]:
            raise AuditError("finding case_ref subject_id does not match the audit lineage")
        retain_case(finding_case)
        evidence = finding.get("evidence")
        if not isinstance(evidence, list):
            raise AuditError("content-bound finding evidence is invalid")
        records.extend(item for item in evidence if _is_content_evidence(item))

    store = _content_call(
        _audit_evidence.verify_content_store,
        workspace,
        binding,
        records,
        historical_case_refs=historical_cases.values(),
    )
    manifest_cache: dict[str, dict[str, object]] = {}
    for projected_case, projection in approved_case_claims:
        digest = projected_case["case_sha256"]
        manifest = manifest_cache.get(digest)
        if manifest is None:
            manifest = _content_call(
                _audit_evidence._manifest_object,
                workspace.joinpath(
                    *_audit_evidence.CASE_STORE_PARTS,
                    f"{digest}.json",
                ),
                digest,
            )
            manifest_cache[digest] = manifest
        baseline = projection.get("baseline")
        gate = projection.get("g0_gate")
        revision = manifest.get("source_revision")
        artifacts = manifest.get("artifacts")
        if (
            not isinstance(baseline, dict)
            or not isinstance(gate, dict)
            or not isinstance(revision, dict)
            or not isinstance(artifacts, list)
            or len(artifacts) != 1
            or not isinstance(artifacts[0], dict)
        ):
            raise AuditError("approved content binding projection is incomplete")
        head = baseline.get("head")
        expected_scheme = (
            "git-sha1"
            if isinstance(head, str) and len(head) == 40
            else "git-sha256"
        )
        if (
            manifest.get("subject") != subject
            or manifest.get("case_id") != baseline.get("id")
            or revision != {"scheme": expected_scheme, "value": head}
            or artifacts[0].get("sha256") != gate.get("contract_sha256")
            or artifacts[0].get("executable") is not False
        ):
            raise AuditError(
                "content binding does not match its projected baseline and G0 gate"
            )
    expected_case = _expected_current_case_ref(lifecycle, contract_bytes, events)
    gate = lifecycle.get("g0_gate")
    if not isinstance(gate, dict):
        raise AuditError("audit lifecycle G0 gate is invalid")
    contract_sha256 = hashlib.sha256(contract_bytes).hexdigest()
    binding_current = (
        active_case == expected_case
        and gate.get("contract_sha256") == contract_sha256
    )
    if (
        gate.get("status") == "approved"
        and gate.get("contract_sha256") == contract_sha256
        and active_case != expected_case
    ):
        raise AuditError(
            "approved G0 content binding does not match its baseline, HEAD, and contract bytes"
        )
    return {
        "evidence_profile": CONTENT_BOUND_PROFILE,
        "content_binding_state": "current" if binding_current else "stale",
        "current_case_ref": copy.deepcopy(active_case),
        "content_finding_count": len(content_findings),
        "content_evidence_count": len(records),
        "content_store": copy.deepcopy(store),
    }


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


def _lifecycle_event_payload(metadata: dict[str, object]) -> dict[str, object]:
    """Build the only authoritative payload shape for a new lifecycle event."""

    lifecycle = _lifecycle_from_metadata(metadata)
    if lifecycle.get("event_projection_mode") != LIFECYCLE_PROJECTION_MODE:
        raise AuditError("new lifecycle events require a full lifecycle projection")
    return {
        "metadata_sha256": _metadata_hash(metadata),
        "lifecycle_projection": copy.deepcopy(lifecycle),
    }


def _validated_lifecycle_projection(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise AuditError("workspace lifecycle event projection must be an object")
    projection = _lifecycle_from_metadata(
        {"schema_version": SCHEMA_VERSION, "audit_lifecycle": value}
    )
    if projection.get("event_projection_mode") != LIFECYCLE_PROJECTION_MODE:
        raise AuditError("workspace lifecycle event projection mode is invalid")
    return projection


def _validate_projection_transition(
    previous: dict[str, object] | None,
    current: dict[str, object],
    event_type: str,
) -> None:
    """Validate projected lifecycle changes after the first projection anchor."""

    gate = current.get("g0_gate")
    current_binding = _content_binding(current)
    if event_type == "workspace_bound":
        if previous is not None:
            raise AuditError("workspace_bound cannot replace an existing lifecycle projection")
        if not isinstance(gate, dict) or gate.get("status") != "draft":
            raise AuditError("workspace_bound lifecycle projection must start with G0 draft")
        if current_binding is not None:
            raise AuditError("workspace_bound must not activate content binding")
        return
    if previous is None:
        # A legacy v2 chain becomes strict at its first projected lifecycle event.
        if event_type == "baseline_replaced" and (
            not isinstance(gate, dict) or gate.get("status") != "draft"
        ):
            raise AuditError(
                "baseline_replaced lifecycle projection must reset G0 to draft"
            )
        if event_type == "baseline_replaced" and current_binding is not None:
            raise AuditError(
                "a first projected baseline_replaced event cannot introduce content binding"
            )
        if current_binding is not None:
            if (
                event_type != "g0_gate_set"
                or not isinstance(gate, dict)
                or gate.get("status") != "approved"
            ):
                raise AuditError("content binding may first appear only in an approved G0 event")
            current_case = current_binding["case_ref"]
            baseline = current.get("baseline")
            if (
                not isinstance(current_case, dict)
                or not isinstance(baseline, dict)
                or current_case.get("case_id") != baseline.get("id")
            ):
                raise AuditError(
                    "approved G0 content binding does not match the current project case"
                )
        return
    previous_binding = _content_binding(previous)
    if previous_binding is not None and current_binding is None:
        raise AuditError("content binding must not disappear from lifecycle projection")
    if event_type == "g0_gate_set":
        prior_fixed = {
            key: value
            for key, value in previous.items()
            if key not in {"g0_gate", "content_binding"}
        }
        current_fixed = {
            key: value
            for key, value in current.items()
            if key not in {"g0_gate", "content_binding"}
        }
        if current_fixed != prior_fixed:
            raise AuditError(
                "g0_gate_set lifecycle projection may change only the G0 gate and content binding"
            )
        status = gate.get("status") if isinstance(gate, dict) else None
        if status != "approved" and current_binding != previous_binding:
            raise AuditError("draft or blocked G0 events must preserve content binding")
        if current_binding != previous_binding:
            if status != "approved" or current_binding is None:
                raise AuditError("content binding may rotate only in an approved G0 event")
            current_case = current_binding["case_ref"]
            baseline = current.get("baseline")
            if (
                not isinstance(current_case, dict)
                or not isinstance(baseline, dict)
                or current_case.get("case_id") != baseline.get("id")
            ):
                raise AuditError(
                    "approved G0 content binding does not match the current project case"
                )
            if (
                previous_binding is not None
                and current_case.get("subject_id")
                != previous_binding["case_ref"].get("subject_id")
            ):
                raise AuditError("content binding subject_id must remain stable")
        return
    if event_type == "baseline_replaced":
        prior_fixed = {
            key: value
            for key, value in previous.items()
            if key not in {"baseline", "g0_gate"}
        }
        current_fixed = {
            key: value
            for key, value in current.items()
            if key not in {"baseline", "g0_gate"}
        }
        if current_fixed != prior_fixed:
            raise AuditError(
                "baseline_replaced lifecycle projection may change only baseline and G0 gate"
            )
        prior_baseline = previous.get("baseline")
        current_baseline = current.get("baseline")
        if (
            not isinstance(prior_baseline, dict)
            or not isinstance(current_baseline, dict)
            or current_baseline.get("id") == prior_baseline.get("id")
        ):
            raise AuditError("baseline_replaced lifecycle projection requires a new baseline id")
        if not isinstance(gate, dict) or gate.get("status") != "draft":
            raise AuditError("baseline_replaced lifecycle projection must reset G0 to draft")
        return
    raise AuditError(f"unsupported lifecycle projection event: {event_type}")


def _verify_metadata_event_hash(
    metadata: dict[str, object], events: list[dict[str, object]]
) -> None:
    """Tie metadata to legacy hashes or to a strictly replayable projection chain."""

    lifecycle = _lifecycle_from_metadata(metadata)
    projection_mode = lifecycle.get("event_projection_mode")
    projection_started = False
    previous_projection: dict[str, object] | None = None
    latest_projection: dict[str, object] | None = None
    latest_hash: str | None = None
    for event in events:
        event_type = event.get("event_type")
        payload = event.get("payload")
        if not isinstance(payload, dict):
            raise AuditError("workspace lifecycle event payload is invalid")
        has_projection = "lifecycle_projection" in payload
        if event_type not in LIFECYCLE_EVENT_TYPES:
            if has_projection:
                raise AuditError("non-lifecycle event must not contain a lifecycle projection")
            continue
        recorded_hash = payload.get("metadata_sha256")
        if not isinstance(recorded_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", recorded_hash):
            raise AuditError("workspace lifecycle event has an invalid metadata_sha256")
        latest_hash = recorded_hash
        if not has_projection:
            if projection_started:
                raise AuditError(
                    "lifecycle event is missing the required full lifecycle projection"
                )
            continue
        if set(payload) != {"metadata_sha256", "lifecycle_projection"}:
            raise AuditError("projected lifecycle event payload has an unexpected schema")
        projection = _validated_lifecycle_projection(payload["lifecycle_projection"])
        projected_metadata = copy.deepcopy(metadata)
        projected_metadata["audit_lifecycle"] = copy.deepcopy(projection)
        if _metadata_hash(projected_metadata) != recorded_hash:
            raise AuditError(
                "lifecycle projection does not match its recorded metadata snapshot"
            )
        _validate_projection_transition(previous_projection, projection, str(event_type))
        projection_started = True
        previous_projection = projection
        latest_projection = projection
    if latest_hash is None:
        raise AuditError("event log has no workspace metadata snapshot")
    if _metadata_hash(metadata) != latest_hash:
        raise AuditError("workspace metadata hash does not match its latest lifecycle event")
    if projection_mode == LIFECYCLE_PROJECTION_MODE:
        if latest_projection is None:
            raise AuditError("audit lifecycle requires a full lifecycle event projection")
        if latest_projection != lifecycle:
            raise AuditError(
                "latest lifecycle event projection does not match current metadata"
            )


def _verify_event_semantics(
    findings: list[dict[str, object]], events: list[dict[str, object]]
) -> None:
    """Replay the small public lifecycle state machine for internal consistency."""

    if not events or events[0].get("event_type") != "workspace_bound":
        raise AuditError("event history must start with exactly one workspace_bound event")
    statuses: dict[str, str] = {}
    evidence_ids: dict[str, set[str]] = {}
    finding_cases: dict[str, object | None] = {}
    evidence_claims: dict[str, dict[str, tuple[str, object | None]]] = {}
    qualifying_content: dict[str, bool] = {}
    projected_binding: dict[str, object] | None = None
    projected_gate_status: object = None
    projected_baseline_id: object = None

    def case_is_event_current(reference: object) -> bool:
        if projected_binding is None:
            return False
        active_case = projected_binding.get("case_ref")
        return (
            isinstance(active_case, dict)
            and reference == active_case
            and projected_gate_status == "approved"
            and active_case.get("case_id") == projected_baseline_id
        )

    for index, event in enumerate(events):
        event_type = event.get("event_type")
        payload = event.get("payload")
        if not isinstance(payload, dict):
            raise AuditError("event payload is invalid")
        if event_type in LIFECYCLE_EVENT_TYPES:
            if event_type == "workspace_bound" and index != 0:
                raise AuditError("workspace_bound may appear only as the first event")
            projection_value = payload.get("lifecycle_projection")
            if projection_value is not None:
                projection = _validated_lifecycle_projection(projection_value)
                projected_binding = _content_binding(projection)
                gate = projection.get("g0_gate")
                baseline = projection.get("baseline")
                if not isinstance(gate, dict) or not isinstance(baseline, dict):
                    raise AuditError("lifecycle event projection is incomplete")
                projected_gate_status = gate.get("status")
                projected_baseline_id = baseline.get("id")
            continue
        if event_type == "finding_created":
            finding_id = payload.get("finding_id")
            if not isinstance(finding_id, str) or finding_id in statuses:
                raise AuditError("finding_created has a missing or duplicate finding_id")
            if payload.get("status") != "open":
                raise AuditError("finding_created must begin with open status")
            statuses[finding_id] = "open"
            evidence_ids[finding_id] = set()
            if "case_ref" in payload:
                finding_case = _binding_call(
                    validate_case_ref, payload["case_ref"]
                )
                if not case_is_event_current(finding_case):
                    raise AuditError(
                        "content finding creation requires the event-time approved audit case"
                    )
                finding_cases[finding_id] = finding_case
            else:
                finding_cases[finding_id] = None
            evidence_claims[finding_id] = {}
            qualifying_content[finding_id] = False
        elif event_type == "finding_evidence_added":
            finding_id = payload.get("finding_id")
            evidence_id = payload.get("evidence_id")
            evidence_kind = payload.get("kind")
            if not isinstance(finding_id, str) or finding_id not in statuses:
                raise AuditError("evidence event references an unknown finding")
            if not isinstance(evidence_id, str) or evidence_id in evidence_ids[finding_id]:
                raise AuditError("evidence event has a missing or duplicate evidence_id")
            if evidence_kind not in EVIDENCE_KINDS:
                raise AuditError("evidence event has an invalid kind")
            finding_case = finding_cases[finding_id]
            if finding_case is not None and not case_is_event_current(finding_case):
                raise AuditError(
                    "case-bound evidence requires the event-time approved audit case"
                )
            evidence_ids[finding_id].add(evidence_id)
            if "evidence_ref" in payload:
                if finding_case is None:
                    raise AuditError(
                        "content evidence event requires a content-bound finding"
                    )
                evidence_reference = payload["evidence_ref"]
                if evidence_kind in CONTENT_TERMINAL_KINDS:
                    qualifying_content[finding_id] = True
            else:
                evidence_reference = None
            evidence_claims[finding_id][evidence_id] = (
                str(evidence_kind),
                evidence_reference,
            )
        elif event_type == "finding_status_changed":
            finding_id = payload.get("finding_id")
            before = payload.get("from_status")
            after = payload.get("to_status")
            if not isinstance(finding_id, str) or finding_id not in statuses:
                raise AuditError("status event references an unknown finding")
            if before != statuses[finding_id] or after not in FINDING_TRANSITIONS.get(str(before), set()):
                raise AuditError("status event violates the finding lifecycle")
            finding_case = finding_cases[finding_id]
            if finding_case is not None and after in EVIDENCE_GATED_STATUSES:
                if not case_is_event_current(finding_case):
                    raise AuditError(
                        "case-bound terminal status requires the event-time approved audit case"
                    )
                if not qualifying_content[finding_id]:
                    raise AuditError(
                        "case-bound terminal status requires prior qualifying content evidence"
                    )
            statuses[finding_id] = str(after)
        else:
            raise AuditError(f"event history contains an unknown event type: {event_type}")
    actual_statuses = {str(finding["id"]): str(finding["status"]) for finding in findings}
    if actual_statuses != statuses:
        raise AuditError("finding statuses do not match replayed event history")
    actual_cases = {
        str(finding["id"]): copy.deepcopy(finding.get("case_ref"))
        for finding in findings
    }
    if actual_cases != finding_cases:
        raise AuditError("finding case_refs do not match replayed event history")
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
    findings_by_id = {str(finding["id"]): finding for finding in findings}
    for finding_id, claims_by_id in evidence_claims.items():
        finding = findings_by_id[finding_id]
        evidence = finding.get("evidence")
        if not isinstance(evidence, list):
            raise AuditError("finding evidence is invalid")
        records_by_id = {
            str(item["id"]): item
            for item in evidence
            if isinstance(item, dict) and "id" in item
        }
        for evidence_id, (recorded_kind, reference) in claims_by_id.items():
            record = records_by_id[evidence_id]
            if record.get("kind") != recorded_kind:
                raise AuditError("evidence event kind does not match its inline record")
            if reference is None:
                if _is_content_evidence(record):
                    raise AuditError("content evidence event is missing evidence_ref")
                continue
            if not _is_content_evidence(record):
                raise AuditError("evidence_ref must bind a content evidence record")
            _content_call(
                _audit_evidence.verify_content_evidence_record_ref,
                record,
                reference,
            )


def _snapshot_target(workspace: Path, relative: str) -> Path:
    if relative == WORKSPACE_METADATA_NAME:
        return workspace / relative
    directory = _validated_findings_directory(workspace)
    return directory / relative.split("/", 1)[1]


def _verify_prospective_commit(
    workspace: Path,
    snapshot_path: str,
    snapshot: dict[str, object],
    events: list[dict[str, object]],
    *,
    binding: bool,
) -> dict[str, object]:
    if snapshot_path == WORKSPACE_METADATA_NAME:
        metadata = snapshot
    else:
        _, metadata = _validate_public_workspace(workspace, allow_pending=True)
    lifecycle = _lifecycle_from_metadata(metadata)
    _assert_workspace_project_separation(workspace, lifecycle)
    findings = [] if binding else _load_findings(workspace)
    if snapshot_path != WORKSPACE_METADATA_NAME:
        finding_id = Path(snapshot_path).stem
        candidate = _validate_finding(snapshot, expected_id=finding_id)
        by_id = {str(item["id"]): item for item in findings}
        by_id[finding_id] = candidate
        findings = list(by_id.values())
    _verify_metadata_event_hash(metadata, events)
    _verify_finding_event_hashes(findings, events)
    _verify_event_semantics(findings, events)
    _verify_content_layer(
        workspace,
        lifecycle,
        findings,
        _research_contract_bytes(workspace),
        events,
    )
    return lifecycle


def _ensure_empty_findings_directory(workspace: Path) -> None:
    directory = workspace / FINDINGS_DIRECTORY_NAME
    try:
        directory.lstat()
    except FileNotFoundError:
        try:
            directory.mkdir()
            _fsync_directory(workspace)
        except OSError as error:
            raise AuditError(f"could not create findings directory: {error}") from error
        return
    if directory.is_symlink() or not directory.is_dir():
        raise AuditError("pending bind findings path is not a regular directory")
    try:
        with os.scandir(directory) as entries:
            if next(entries, None) is not None:
                raise AuditError("pending bind findings directory is not empty")
    except AuditError:
        raise
    except OSError as error:
        raise AuditError(f"could not inspect pending bind findings directory: {error}") from error


def _commit_lifecycle_change(
    workspace: Path,
    *,
    snapshot_relative_path: str,
    snapshot_payload: dict[str, object],
    event_type: str,
    actor: str,
    event_payload: dict[str, object],
    binding: bool = False,
) -> dict[str, object]:
    """Durably commit one snapshot plus one event with explicit recovery intent."""

    _assert_no_pending_commit(workspace)
    snapshot_relative_path = _validate_snapshot_relative_path(snapshot_relative_path)
    if event_type in LIFECYCLE_EVENT_TYPES:
        if snapshot_relative_path != WORKSPACE_METADATA_NAME:
            raise AuditError("lifecycle events must commit the workspace metadata snapshot")
        expected_payload = _lifecycle_event_payload(snapshot_payload)
        if event_payload != expected_payload:
            raise AuditError(
                "lifecycle event payload does not match its prospective metadata projection"
            )
    snapshot_label = (
        "audit workspace metadata"
        if snapshot_relative_path == WORKSPACE_METADATA_NAME
        else "finding"
    )
    snapshot_text = _json_snapshot_text(snapshot_payload, snapshot_label)
    event, events, event_log_before, event_log_text = _build_event_update(
        workspace,
        event_type=event_type,
        actor=actor,
        payload=event_payload,
        allow_missing=binding,
    )
    prospective_lifecycle = _verify_prospective_commit(
        workspace,
        snapshot_relative_path,
        snapshot_payload,
        events,
        binding=binding,
    )

    if binding:
        snapshot_path = workspace / WORKSPACE_METADATA_NAME
    else:
        snapshot_path = _snapshot_target(workspace, snapshot_relative_path)
    snapshot_before = _optional_regular_text(
        snapshot_path,
        snapshot_label,
        maximum_bytes=MAX_AUDIT_FILE_BYTES,
    )
    if snapshot_relative_path == WORKSPACE_METADATA_NAME and snapshot_before is None:
        raise AuditError("audit workspace metadata disappeared before commit")
    if event_type == "finding_created" and snapshot_before is not None:
        raise AuditError(f"finding already exists: {Path(snapshot_relative_path).stem}")
    if event_type in {"finding_evidence_added", "finding_status_changed"} and snapshot_before is None:
        raise AuditError("finding disappeared before lifecycle commit")
    pending_body: dict[str, object] = {
        "schema_version": PENDING_COMMIT_SCHEMA_VERSION,
        "transaction_id": str(uuid.uuid4()),
        "snapshot_path": snapshot_relative_path,
        "snapshot_before_sha256": (
            _sha256_text(snapshot_before) if snapshot_before is not None else None
        ),
        "snapshot_after": snapshot_payload,
        "snapshot_after_sha256": _sha256_text(snapshot_text),
        "event_log_before_sha256": (
            _sha256_text(event_log_before) if event_log_before is not None else None
        ),
        "event_log_after_sha256": _sha256_text(event_log_text),
        "event": event,
    }
    pending_body["content_sha256"] = _pending_content_hash(pending_body)
    try:
        _assert_workspace_project_separation(workspace, prospective_lifecycle)
        _write_pending_commit(workspace, pending_body)
        if binding:
            _ensure_empty_findings_directory(workspace)
        _atomic_write_text(snapshot_path, snapshot_text)
        _atomic_write_text(workspace / EVENT_LOG_NAME, event_log_text)
        _verified_audit_snapshot(workspace, allow_pending=True)
        _delete_pending_commit(workspace)
    except AuditError as error:
        if not _pending_commit_exists(workspace):
            raise
        raise AuditError(
            "audit lifecycle commit was interrupted; run `audit recover` before "
            f"continuing: {error}"
        ) from error
    return copy.deepcopy(event)


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
        "event_projection_mode": LIFECYCLE_PROJECTION_MODE,
        "project": {"root": project_snapshot["project_root"]},
        "baseline": baseline,
        "g0_gate": gate,
        "findings_directory": FINDINGS_DIRECTORY_NAME,
        "event_log": EVENT_LOG_NAME,
    }
    upgraded_lifecycle = upgraded["audit_lifecycle"]
    if not isinstance(upgraded_lifecycle, dict):
        raise AuditError("audit lifecycle is not writable")
    _assert_workspace_project_separation(workspace_path, upgraded_lifecycle)

    _commit_lifecycle_change(
        workspace_path,
        snapshot_relative_path=WORKSPACE_METADATA_NAME,
        snapshot_payload=upgraded,
        event_type="workspace_bound",
        actor=actor,
        event_payload=_lifecycle_event_payload(upgraded),
        binding=True,
    )
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
    (
        workspace_path,
        metadata,
        lifecycle,
        _,
        _,
        _,
    ) = _verified_audit_snapshot(workspace)
    contract_bytes = _research_contract_bytes(workspace_path)
    if canonical_status == "approved":
        _assert_research_contract_complete(workspace_path)
        baseline = lifecycle.get("baseline")
        project = lifecycle.get("project")
        if not isinstance(baseline, dict) or not isinstance(project, dict):
            raise AuditError("audit lifecycle baseline is invalid")
        current = _git_snapshot(
            _require_text(project.get("root"), "project root"),
            require_clean=True,
        )
        if current["head"] != baseline.get("head") or current["branch"] != baseline.get("branch"):
            raise AuditError(
                "project revision drift detected; use explicit rebaseline before G0 approval"
            )
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
        "contract_sha256": hashlib.sha256(contract_bytes).hexdigest(),
    }
    updated_lifecycle["g0_gate"] = gate
    if canonical_status == "approved":
        baseline = lifecycle["baseline"]
        if not isinstance(baseline, dict):
            raise AuditError("audit lifecycle baseline is invalid")
        events = _read_events(workspace_path, allow_missing=False)
        manifest = _content_call(
            _audit_evidence.build_audit_case_manifest,
            _audit_lineage_subject_ref(events),
            _require_text(baseline.get("id"), "baseline id"),
            _require_text(baseline.get("head"), "baseline head"),
            contract_bytes,
        )
        new_binding = _content_call(
            _audit_evidence.store_audit_case,
            workspace_path,
            manifest,
            contract_bytes,
        )
        previous_binding = _content_binding(lifecycle)
        if (
            previous_binding is not None
            and previous_binding["case_ref"].get("subject_id")
            != new_binding["case_ref"].get("subject_id")
        ):
            raise AuditError("content binding subject_id must remain stable")
        updated_lifecycle["content_binding"] = new_binding
    updated_lifecycle["event_projection_mode"] = LIFECYCLE_PROJECTION_MODE
    _commit_lifecycle_change(
        workspace_path,
        snapshot_relative_path=WORKSPACE_METADATA_NAME,
        snapshot_payload=updated,
        event_type="g0_gate_set",
        actor=actor,
        event_payload=_lifecycle_event_payload(updated),
    )
    return copy.deepcopy(gate)


@_serialized_workspace_read(0)
def assess_g0_gate(workspace: str | Path) -> dict[str, object]:
    """Assess declared G0 structure and decision freshness without mutating it."""

    workspace_path, _, lifecycle, _, _, _ = _verified_audit_snapshot(workspace)
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
        "g0_prerequisites_met": ready,
        "limitation": (
            "This is a declared human decision and structural check, not identity "
            "authentication or scientific approval."
        ),
    }
    return report


@_serialized_workspace_read(0)
def preflight(workspace: str | Path) -> dict[str, object]:
    """Require a clean, unchanged baseline and an approved G0 gate before work."""

    (
        workspace_path,
        _,
        lifecycle,
        _,
        current_contract_hash,
        _,
    ) = _verified_audit_snapshot(workspace)
    gate = lifecycle["g0_gate"]
    baseline = lifecycle["baseline"]
    project = lifecycle["project"]
    if not isinstance(gate, dict) or gate.get("status") != "approved":
        raise AuditError("G0 gate must be approved before preflight can pass")
    if not isinstance(baseline, dict) or not isinstance(project, dict):
        raise AuditError("audit lifecycle baseline is invalid")
    _assert_research_contract_complete(workspace_path)
    expected_contract_hash = gate.get("contract_sha256")
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
    workspace_path, metadata, lifecycle, _, _, _ = _verified_audit_snapshot(workspace)
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
    updated_lifecycle["event_projection_mode"] = LIFECYCLE_PROJECTION_MODE
    _commit_lifecycle_change(
        workspace_path,
        snapshot_relative_path=WORKSPACE_METADATA_NAME,
        snapshot_payload=updated,
        event_type="baseline_replaced",
        actor=actor,
        event_payload=_lifecycle_event_payload(updated),
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

    (
        workspace_path,
        _,
        lifecycle,
        existing_findings,
        contract_sha256,
        _,
    ) = _verified_audit_snapshot(workspace)
    _preflight_from_snapshot(workspace_path, lifecycle, contract_sha256)
    finding_id = _require_text(finding_id, "finding_id")
    path = _finding_path(workspace_path, finding_id)
    if path.is_symlink() or path.exists():
        raise AuditError(f"finding already exists: {finding_id}")
    if len(existing_findings) >= MAX_FINDINGS:
        raise AuditError(f"findings would exceed the {MAX_FINDINGS}-finding limit")
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
    binding = _content_binding(lifecycle)
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
    if binding is not None:
        finding["case_ref"] = copy.deepcopy(binding["case_ref"])
    event_payload: dict[str, object] = {
        "finding_id": finding_id,
        "layer": layer,
        "competency": competency,
        "severity": severity,
        "status": "open",
        "finding_sha256": _finding_hash(finding),
    }
    if binding is not None:
        event_payload["case_ref"] = copy.deepcopy(binding["case_ref"])
    _commit_lifecycle_change(
        workspace_path,
        snapshot_relative_path=f"{FINDINGS_DIRECTORY_NAME}/{path.name}",
        snapshot_payload=finding,
        event_type="finding_created",
        actor=finding["actor"],
        event_payload=event_payload,
    )
    return copy.deepcopy(finding)


@_serialized_workspace_read(0)
def list_findings(workspace: str | Path) -> list[dict[str, object]]:
    """Return schema-validated findings in stable filename order."""

    _, _, _, findings, _, _ = _verified_audit_snapshot(workspace)
    return copy.deepcopy(findings)


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

    (
        workspace_path,
        _,
        lifecycle,
        existing_findings,
        contract_sha256,
        _,
    ) = _verified_audit_snapshot(workspace)
    _preflight_from_snapshot(workspace_path, lifecycle, contract_sha256)
    finding = _load_finding(workspace_path, finding_id)
    if not _finding_matches_current_baseline(finding, lifecycle):
        raise AuditError(
            "evidence must not be attached to a finding from an older baseline; "
            "create a new finding ID for the current baseline"
        )
    if "case_ref" in finding and not _finding_matches_current_case(finding, lifecycle):
        raise AuditError(
            "reference evidence must not be attached to a finding from an older audit case"
        )
    evidence_id = _require_text(evidence_id, "evidence_id")
    if not FINDING_ID_PATTERN.fullmatch(evidence_id):
        raise AuditError("evidence_id may contain only letters, digits, dot, underscore, and hyphen")
    evidence = finding["evidence"]
    if not isinstance(evidence, list):
        raise AuditError("finding evidence is invalid")
    if len(evidence) >= MAX_EVIDENCE_PER_FINDING:
        raise AuditError(
            f"finding {finding_id} would exceed the "
            f"{MAX_EVIDENCE_PER_FINDING}-evidence limit"
        )
    total_evidence = sum(len(item["evidence"]) for item in existing_findings)
    if total_evidence >= MAX_TOTAL_EVIDENCE:
        raise AuditError(
            f"findings would exceed the {MAX_TOTAL_EVIDENCE}-evidence aggregate limit"
        )
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
    finding_path = _finding_path(workspace_path, finding_id)
    _commit_lifecycle_change(
        workspace_path,
        snapshot_relative_path=f"{FINDINGS_DIRECTORY_NAME}/{finding_path.name}",
        snapshot_payload=finding,
        event_type="finding_evidence_added",
        actor=entry["actor"],
        event_payload={
            "finding_id": finding_id,
            "evidence_id": evidence_id,
            "kind": entry["kind"],
            "finding_sha256": _finding_hash(finding),
        },
    )
    return copy.deepcopy(finding)


@_serialized_workspace_mutation(0)
def import_content_evidence(
    workspace: str | Path,
    finding_id: str,
    *,
    evidence_id: str,
    evidence_type: str,
    kind: str,
    source_kind: str,
    source_path: str | Path,
    source_ref: str | None,
    summary: str,
    actor: str,
    artifact_role: str | None = None,
    environment_scope: str | None = None,
    declared_command: str | None = None,
    exit_code: int | None = None,
) -> dict[str, object]:
    """Import one explicit file as content-bound evidence without executing it."""

    (
        workspace_path,
        _,
        lifecycle,
        existing_findings,
        contract_sha256,
        _,
    ) = _verified_audit_snapshot(workspace)
    binding = _content_binding(lifecycle)
    if binding is None:
        raise AuditError("content evidence import requires an approved content binding")
    _preflight_from_snapshot(workspace_path, lifecycle, contract_sha256)
    finding = _load_finding(workspace_path, finding_id)
    if not _finding_matches_current_baseline(finding, lifecycle):
        raise AuditError(
            "content evidence must not be attached to a finding from an older baseline"
        )
    if not _finding_matches_current_case(finding, lifecycle):
        raise AuditError(
            "content evidence must not be attached to a finding from an older audit case"
        )

    evidence_id = _require_text(evidence_id, "evidence_id")
    if not FINDING_ID_PATTERN.fullmatch(evidence_id):
        raise AuditError(
            "evidence_id may contain only letters, digits, dot, underscore, and hyphen"
        )
    evidence = finding.get("evidence")
    if not isinstance(evidence, list):
        raise AuditError("finding evidence is invalid")
    if len(evidence) >= MAX_EVIDENCE_PER_FINDING:
        raise AuditError(
            f"finding {finding_id} would exceed the "
            f"{MAX_EVIDENCE_PER_FINDING}-evidence limit"
        )
    if sum(len(item["evidence"]) for item in existing_findings) >= MAX_TOTAL_EVIDENCE:
        raise AuditError(
            f"findings would exceed the {MAX_TOTAL_EVIDENCE}-evidence aggregate limit"
        )
    content_records = [
        item
        for existing in existing_findings
        for item in existing["evidence"]
        if _is_content_evidence(item)
    ]
    if len(content_records) >= _audit_evidence.MAX_EVIDENCE_RECORDS:
        raise AuditError("content evidence record limit has been reached")
    if any(
        isinstance(item, dict) and item.get("id") == evidence_id
        for item in content_records
    ):
        raise AuditError(f"content evidence id already exists: {evidence_id}")

    try:
        source_value = os.fspath(source_path)
    except TypeError as error:
        raise AuditError("source_path must be a filesystem path") from error
    if not isinstance(source_value, str):
        raise AuditError("source_path must be a text filesystem path")
    canonical_source_kind = _require_text(source_kind, "source_kind")
    if canonical_source_kind == "project-relative":
        if source_ref is not None:
            raise AuditError("project-relative evidence must not declare an external source_ref")
        project = lifecycle.get("project")
        if not isinstance(project, dict):
            raise AuditError("audit lifecycle project is invalid")
        source = _content_call(
            _audit_evidence.read_project_source,
            _require_text(project.get("root"), "project root"),
            source_value,
        )
    elif canonical_source_kind == "external":
        logical_ref = _require_text(source_ref, "source_ref")
        source = _content_call(
            _audit_evidence.read_external_source,
            source_value,
            logical_ref,
        )
    else:
        raise AuditError("source_kind must be project-relative or external")

    logical_path = source.source.get("path", source.source.get("ref"))
    if not isinstance(logical_path, str):
        raise AuditError("content evidence source has no logical path")
    artifact = _content_call(
        _audit_evidence.store_evidence_blob,
        workspace_path,
        logical_path,
        source.data,
        executable=source.executable,
    )
    entry = _content_call(
        _audit_evidence.build_content_evidence_record,
        evidence_id=evidence_id,
        evidence_type=evidence_type,
        kind=kind,
        case=binding["case_ref"],
        artifact=artifact,
        source=source.source,
        summary=summary,
        actor=actor,
        recorded_at=_utc_now(),
        artifact_role=artifact_role,
        environment_scope=environment_scope,
        declared_command=declared_command,
        exit_code=exit_code,
    )
    evidence_reference = _content_call(
        _audit_evidence.content_evidence_record_ref,
        entry,
    )
    evidence.append(entry)
    finding["actor"] = entry["actor"]
    finding["updated_at"] = entry["recorded_at"]
    finding_path = _finding_path(workspace_path, finding_id)
    _commit_lifecycle_change(
        workspace_path,
        snapshot_relative_path=f"{FINDINGS_DIRECTORY_NAME}/{finding_path.name}",
        snapshot_payload=finding,
        event_type="finding_evidence_added",
        actor=str(entry["actor"]),
        event_payload={
            "finding_id": finding_id,
            "evidence_id": evidence_id,
            "kind": entry["kind"],
            "evidence_ref": evidence_reference,
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
    reviewer can triage a changing project. The serialized ``verified`` and
    ``closed`` labels are declared lifecycle states: entering them requires
    recorded evidence, the current baseline snapshot, and a clean, approved
    preflight, but does not establish independent or scientific verification.
    """

    (
        workspace_path,
        _,
        lifecycle,
        _,
        contract_sha256,
        _,
    ) = _verified_audit_snapshot(workspace)
    finding = _load_finding(workspace_path, finding_id)
    actor = _require_text(actor, "actor")
    rationale = _require_text(rationale, "rationale")
    current_status = finding.get("status")
    if not isinstance(current_status, str) or new_status not in FINDING_TRANSITIONS.get(current_status, set()):
        raise AuditError(f"illegal finding transition: {current_status} -> {new_status}")
    if new_status in EVIDENCE_GATED_STATUSES:
        binding = _content_binding(lifecycle)
        if binding is None:
            raise AuditError(
                f"{new_status} requires an approved content-bound audit case"
            )
        evidence = finding.get("evidence")
        qualifying = [
            item
            for item in evidence
            if _is_content_evidence(item)
            and isinstance(item, dict)
            and item.get("case_ref") == binding["case_ref"]
            and item.get("kind") in CONTENT_TERMINAL_KINDS
        ] if isinstance(evidence, list) else []
        if not qualifying:
            raise AuditError(
                f"{new_status} requires observed, derived, or reproduced "
                "content-bound evidence for the current case"
            )
        if not _finding_matches_current_baseline(finding, lifecycle):
            raise AuditError(
                f"{new_status} requires a finding created against the current baseline; "
                "create a new finding ID after rebaseline"
            )
        if not _finding_matches_current_case(finding, lifecycle):
            raise AuditError(
                f"{new_status} requires a finding bound to the current audit case"
            )
        _preflight_from_snapshot(workspace_path, lifecycle, contract_sha256)
    finding["status"] = new_status
    finding["actor"] = actor
    finding["updated_at"] = _utc_now()
    finding_path = _finding_path(workspace_path, finding_id)
    _commit_lifecycle_change(
        workspace_path,
        snapshot_relative_path=f"{FINDINGS_DIRECTORY_NAME}/{finding_path.name}",
        snapshot_payload=finding,
        event_type="finding_status_changed",
        actor=actor,
        event_payload={
            "finding_id": finding_id,
            "from_status": current_status,
            "to_status": new_status,
            "rationale": rationale,
            "finding_sha256": _finding_hash(finding),
        },
    )
    return copy.deepcopy(finding)


def _verified_audit_snapshot(
    workspace: str | Path,
    *,
    allow_pending: bool = False,
) -> tuple[
    Path,
    dict[str, object],
    dict[str, object],
    list[dict[str, object]],
    str,
    dict[str, object],
]:
    """Load once, verify once, and return the exact state used by report projection."""

    workspace_path, metadata, lifecycle = _load_bound_workspace(
        workspace, allow_pending=allow_pending
    )
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
    contract_bytes = _research_contract_bytes(workspace_path)
    contract_sha256 = hashlib.sha256(contract_bytes).hexdigest()
    content_verification = _verify_content_layer(
        workspace_path,
        lifecycle,
        findings,
        contract_bytes,
        events,
    )
    verification = {
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
        **content_verification,
    }
    return (
        workspace_path,
        metadata,
        lifecycle,
        findings,
        contract_sha256,
        verification,
    )


@_serialized_workspace_read(0)
def verify_audit_workspace(workspace: str | Path) -> dict[str, object]:
    """Verify public metadata and local hash-chain consistency only.

    This check detects inconsistencies between current finding snapshots and
    their logged lifecycle hashes. It is not a scientific, legal, or deployment
    correctness determination.
    """

    return copy.deepcopy(_verified_audit_snapshot(workspace)[-1])


def _restore_after_image(
    path: Path,
    before_hash: str | None,
    after_text: str,
    label: str,
    maximum_bytes: int,
) -> None:
    current = _optional_regular_text(path, label, maximum_bytes=maximum_bytes)
    current_hash = _sha256_text(current) if current is not None else None
    after_hash = _sha256_text(after_text)
    if current_hash not in {before_hash, after_hash}:
        raise AuditError(
            f"pending commit cannot recover {label}: current content is neither "
            "the recorded before-image nor after-image"
        )
    if current_hash != after_hash:
        _atomic_write_text(path, after_text)


@_serialized_workspace_mutation(0, allow_pending=True)
def recover_audit(workspace: str | Path) -> dict[str, object]:
    """Idempotently roll a durable pending lifecycle commit forward."""

    workspace_path = _existing_directory(workspace, "audit workspace")
    manifest = _read_pending_commit(workspace_path)
    if manifest is None:
        verification = _verified_audit_snapshot(workspace_path)[-1]
        return {
            "ok": True,
            "status": "clean",
            "recovered": False,
            "verification": copy.deepcopy(verification),
        }

    snapshot_relative_path = _validate_snapshot_relative_path(
        manifest["snapshot_path"]
    )
    snapshot_payload = manifest["snapshot_after"]
    event = manifest["event"]
    if not isinstance(snapshot_payload, dict) or not isinstance(event, dict):
        raise AuditError("pending commit after-images are invalid")
    snapshot_after = _json_snapshot_text(snapshot_payload, "pending commit snapshot")
    binding = event.get("event_type") == "workspace_bound"
    current_event_text = _optional_regular_text(
        workspace_path / EVENT_LOG_NAME,
        "event log",
        maximum_bytes=MAX_EVENT_LOG_BYTES,
    )
    current_event_hash = (
        _sha256_text(current_event_text) if current_event_text is not None else None
    )
    if current_event_text is None:
        if not binding:
            raise AuditError(f"missing regular event log: {workspace_path / EVENT_LOG_NAME}")
        current_events: list[dict[str, object]] = []
    else:
        if (
            manifest.get("schema_version") == LEGACY_PENDING_COMMIT_SCHEMA_VERSION
            and binding
            and current_event_text == ""
        ):
            raise AuditError(
                "legacy pending bind cannot treat a zero-byte event log as a missing file"
            )
        current_events = _parse_events_text(current_event_text)
    if manifest.get("schema_version") == PENDING_COMMIT_SCHEMA_VERSION:
        event_before_hash = _valid_sha256_or_none(
            manifest.get("event_log_before_sha256"), "event log before hash"
        )
        event_after_hash = _valid_sha256_or_none(
            manifest.get("event_log_after_sha256"), "event log after hash"
        )
        if current_event_hash not in {event_before_hash, event_after_hash}:
            raise AuditError(
                "pending commit cannot recover event log: current content is neither "
                "the recorded before-image nor after-image"
            )
    sequence = event.get("seq")
    if type(sequence) is not int or sequence < 1:
        raise AuditError("pending commit event sequence is invalid")
    if len(current_events) == sequence - 1:
        events = [*current_events, event]
        event_write_required = True
    elif current_events and len(current_events) == sequence and current_events[-1] == event:
        events = current_events
        event_write_required = False
    else:
        raise AuditError("pending commit does not extend the current event log")
    event_log_after = _event_log_text(events)
    if (
        manifest.get("schema_version") == PENDING_COMMIT_SCHEMA_VERSION
        and _sha256_text(event_log_after) != manifest.get("event_log_after_sha256")
    ):
        raise AuditError(
            "pending commit event log after hash does not match its reconstructed after-image"
        )
    if binding and snapshot_relative_path != WORKSPACE_METADATA_NAME:
        raise AuditError("pending commit binding target is invalid")
    prospective_lifecycle = _verify_prospective_commit(
        workspace_path,
        snapshot_relative_path,
        snapshot_payload,
        events,
        binding=binding,
    )

    if binding:
        snapshot_path = workspace_path / WORKSPACE_METADATA_NAME
    else:
        snapshot_path = _snapshot_target(workspace_path, snapshot_relative_path)
    try:
        _assert_workspace_project_separation(workspace_path, prospective_lifecycle)
        if binding:
            _ensure_empty_findings_directory(workspace_path)
        _restore_after_image(
            snapshot_path,
            _valid_sha256_or_none(
                manifest["snapshot_before_sha256"], "snapshot before hash"
            ),
            snapshot_after,
            "snapshot",
            MAX_AUDIT_FILE_BYTES,
        )
        if event_write_required:
            _atomic_write_text(workspace_path / EVENT_LOG_NAME, event_log_after)
        verification = _verified_audit_snapshot(workspace_path, allow_pending=True)[-1]
        _delete_pending_commit(workspace_path)
    except AuditError as error:
        raise AuditError(
            "audit recovery remains incomplete; preserve the pending commit and run "
            f"`audit recover` again after resolving the write failure: {error}"
        ) from error
    return {
        "ok": True,
        "status": "recovered",
        "recovered": True,
        "transaction_id": manifest["transaction_id"],
        "event_hash": event["event_hash"],
        "verification": copy.deepcopy(verification),
    }


def _preflight_from_snapshot(
    workspace_path: Path,
    lifecycle: dict[str, object],
    contract_sha256: str,
) -> dict[str, object]:
    gate = lifecycle["g0_gate"]
    baseline = lifecycle["baseline"]
    project = lifecycle["project"]
    if not isinstance(gate, dict) or gate.get("status") != "approved":
        raise AuditError("G0 gate must be approved before preflight can pass")
    if not isinstance(baseline, dict) or not isinstance(project, dict):
        raise AuditError("audit lifecycle baseline is invalid")
    _assert_research_contract_complete(workspace_path)
    if contract_sha256 != gate.get("contract_sha256"):
        raise AuditError(
            "G0 research contract changed after the recorded decision; record a new gate decision"
        )
    binding = _content_binding(lifecycle)
    if binding is not None:
        expected_case = _expected_current_case_ref(
            lifecycle,
            _research_contract_bytes(workspace_path),
            _read_events(workspace_path, allow_missing=False),
        )
        if binding["case_ref"] != expected_case:
            raise AuditError(
                "content binding is stale; record an approved G0 decision for the current baseline"
            )
    current = _git_snapshot(
        _require_text(project.get("root"), "project root"), require_clean=True
    )
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


def _build_report_data_locked(workspace: str | Path) -> dict[str, object]:
    """Return report-ready data without creating or modifying any file."""

    (
        workspace_path,
        _,
        lifecycle,
        findings,
        contract_sha256,
        verification,
    ) = _verified_audit_snapshot(workspace)
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
        case_current = (
            verification["content_binding_state"] == "current"
            and _finding_matches_current_case(finding, lifecycle)
        )
        report_finding["baseline_current"] = baseline_current
        report_finding["baseline_state"] = "current" if baseline_current else "stale"
        report_finding["case_current"] = case_current
        report_finding["case_state"] = (
            "legacy"
            if "case_ref" not in finding
            else ("current" if case_current else "stale")
        )
        report_findings.append(report_finding)
    try:
        preflight_result: dict[str, object] | None = _preflight_from_snapshot(
            workspace_path, lifecycle, contract_sha256
        )
        preflight_issue: str | None = None
    except AuditError as error:
        preflight_result = None
        preflight_issue = str(error)
    stale_finding_count = sum(
        1 for finding in report_findings if not finding["baseline_current"]
    )
    stale_case_finding_count = sum(
        1 for finding in report_findings if finding["case_state"] == "stale"
    )
    report_status = (
        "preflight-current"
        if (
            preflight_result is not None
            and stale_finding_count == 0
            and stale_case_finding_count == 0
        )
        else "preflight-not-current"
    )
    report: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "validator_scope": "local_hash_chain_lifecycle_integrity_only",
        "report_status": report_status,
        "limitations": [
            "Local hash-chain consistency is not external immutability or identity authentication.",
            "The verified and closed finding values are declared lifecycle labels, not independent verification or scientific approval.",
            "Recorded evidence and human declarations are not automatically judged for scientific correctness.",
            (
                "Content hashes bind retained bytes, not source authenticity, truth, "
                "sufficiency, or independent reproduction."
            ),
            "No audited-project code is executed and no network resource is fetched by this report builder.",
        ],
        "preflight": preflight_result,
        "preflight_issue": preflight_issue,
        "verification": verification,
        "evidence_profile": verification["evidence_profile"],
        "content_binding_state": verification["content_binding_state"],
        "current_case_ref": copy.deepcopy(verification["current_case_ref"]),
        "content_store": copy.deepcopy(verification["content_store"]),
        "project": copy.deepcopy(lifecycle["project"]),
        "baseline": copy.deepcopy(lifecycle["baseline"]),
        "g0_gate": copy.deepcopy(lifecycle["g0_gate"]),
        "summary": {
            "finding_count": len(findings),
            "stale_finding_count": stale_finding_count,
            "stale_case_finding_count": stale_case_finding_count,
            "content_finding_count": verification["content_finding_count"],
            "content_evidence_count": verification["content_evidence_count"],
            "by_status": by_status,
            "by_layer": by_layer,
            "by_competency": by_competency,
            "by_severity": by_severity,
        },
        "findings": report_findings,
    }
    return report


@_serialized_workspace_read(0)
def build_report_data(workspace: str | Path) -> dict[str, object]:
    """Return one report projection while holding a shared workspace lock."""

    return _build_report_data_locked(workspace)


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


@_serialized_workspace_read(0)
def render_report_markdown(workspace: str | Path) -> str:
    """Render a Markdown view of :func:`build_report_data` without writing it."""

    report = _build_report_data_locked(workspace)
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
        f"> Report status: **{str(report.get('report_status')).upper()}**. This status describes preflight and current-record state only; it does not declare scientific correctness, legal compliance, or deployment readiness.",
        "",
        "## Bound project",
        "",
        f"- Root: {_markdown_code(project.get('root'))}",
        f"- Baseline ID: {_markdown_code(baseline.get('id'))}",
        f"- Baseline HEAD: {_markdown_code(baseline.get('head'))}",
        f"- Baseline branch: {_markdown_code(baseline.get('branch'))}",
        f"- G0 declared gate: **{_markdown_text(gate.get('status'))}** — reviewer: {_markdown_text(gate.get('reviewer'))}",
        f"- Preflight issue: {_markdown_text(report.get('preflight_issue') or 'None recorded')}",
        "",
        "## Finding summary",
        "",
        f"- Total findings: {summary.get('finding_count')}",
        f"- Findings from an older baseline: {summary.get('stale_finding_count')}",
        f"- By declared lifecycle state: {summary.get('by_status')}",
        f"- By severity: {summary.get('by_severity')}",
        "",
        "## Findings",
        "",
        "| ID | Layer | Competency | Severity | Declared lifecycle state | Baseline | Title |",
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
            reference: object = item.get("reference")
            if _is_content_evidence(item):
                artifact = item.get("artifact_ref")
                if not isinstance(artifact, dict):
                    raise AuditError("report content evidence artifact_ref is invalid")
                reference = (
                    f"{artifact.get('path')} · sha256:{artifact.get('sha256')}"
                )
            lines.append(
                "  - {id} [{kind}] — {summary} ({reference})".format(
                    id=_markdown_cell(item.get("id")),
                    kind=_markdown_cell(item.get("kind")),
                    summary=_markdown_cell(item.get("summary")),
                    reference=_markdown_code(reference),
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
