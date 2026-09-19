"""Content-bound audit cases and explicit-file evidence stored in a local CAS.
Lifecycle owns locking; this module never executes, captures, walks, fetches, or GC's.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Iterable, Mapping, cast

from .bindings import (
    ArtifactRef,
    BindingError,
    CaseManifest,
    CaseRef,
    RecordRef,
    SubjectRef,
    artifact_ref,
    build_case_manifest,
    canonical_json_bytes,
    case_ref,
    case_sha256,
    record_ref,
    source_revision,
    validate_artifact_ref,
    validate_case_manifest,
    validate_case_ref,
    validate_record_ref,
    validate_subject_ref,
)

CONTENT_BINDING_SCHEMA_VERSION = 1
CONTENT_BINDING_TYPE = "rcsl-audit-content-binding"
CONTENT_EVIDENCE_RECORD_TYPE = "rcsl-content-evidence"
EVIDENCE_TYPES = ("artifact", "command-result", "environment")
EVIDENCE_KINDS = ("asserted", "observed", "derived", "reproduced", "contradicted")
CONTRACT_ARTIFACT_PATH = "research-contract-template.md"
CASE_STORE_PARTS, BLOB_STORE_PARTS = (
    ("case-manifests", "sha256"),
    ("evidence", "blobs", "sha256"),
)
STAGING_PARTS = (".content-staging",)
ISOLATED_DIRECTORY_NAME = "DO_NOT_OPEN_UNTIL_FINISHED"
MAX_CONTENT_BYTES, MAX_CAS_OBJECTS, MAX_EVIDENCE_RECORDS = 16_000_000, 10_000, 10_000
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_UTC_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")


class AuditEvidenceError(RuntimeError):
    pass


@dataclass(frozen=True)
class SourceSnapshot:
    source: dict[str, str]
    data: bytes
    executable: bool


def _binding(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except BindingError as error:
        raise AuditEvidenceError(str(error)) from error


def _exact(value: object, keys: set[str], label: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise AuditEvidenceError(f"{label} must be an object with string keys")
    if set(value) != keys:
        missing = sorted(keys - set(value))
        unknown = sorted(set(value) - keys)
        if missing:
            raise AuditEvidenceError(
                f"{label} has missing fields: {', '.join(missing)}"
            )
        if unknown:
            raise AuditEvidenceError(
                f"{label} has unknown fields: {', '.join(unknown)}"
            )
    return value


def _text(value: object, label: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AuditEvidenceError(f"{label} must be a non-empty string")
    try:
        encoded = value.encode("utf-8")
    except UnicodeError as error:
        raise AuditEvidenceError(f"{label} must be valid UTF-8") from error
    if len(encoded) > limit:
        raise AuditEvidenceError(f"{label} exceeds the {limit}-byte limit")
    return value


def _timestamp(value: object) -> str:
    result = _text(value, "recorded_at", 32)
    if not _UTC_TIMESTAMP.fullmatch(result):
        raise AuditEvidenceError("recorded_at must use UTC form YYYY-MM-DDTHH:MM:SSZ")
    try:
        datetime.strptime(result, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as error:
        raise AuditEvidenceError("recorded_at is not a valid UTC timestamp") from error
    return result


def _reject_isolated(path: Path, label: str) -> None:
    isolated = ISOLATED_DIRECTORY_NAME.casefold()
    if any(part.casefold() == isolated for part in path.parts):
        raise AuditEvidenceError(f"{label} must not reference isolated material")


def _directory(value: str | Path, label: str) -> Path:
    try:
        path = Path(os.path.abspath(os.fspath(value)))
    except (TypeError, ValueError) as error:
        raise AuditEvidenceError(f"{label} is not a valid path") from error
    _reject_isolated(path, label)
    try:
        metadata = path.lstat()
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise AuditEvidenceError(f"{label} must be an existing directory") from error
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise AuditEvidenceError(f"{label} must be an existing directory")
    _reject_isolated(resolved, label)
    return resolved


def _identity(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


_READ_FLAGS = (
    os.O_RDONLY
    | getattr(os, "O_NOFOLLOW", 0)
    | getattr(os, "O_NONBLOCK", 0)
    | getattr(os, "O_CLOEXEC", 0)
)
_DIRECTORY_FLAGS = (
    os.O_RDONLY
    | getattr(os, "O_DIRECTORY", 0)
    | getattr(os, "O_NOFOLLOW", 0)
    | getattr(os, "O_CLOEXEC", 0)
)


def _absolute_path(value: str | Path, label: str) -> Path:
    try:
        path = Path(os.path.abspath(os.fspath(value)))
    except (TypeError, ValueError) as error:
        raise AuditEvidenceError(f"{label} is not a valid path") from error
    _reject_isolated(path, label)
    return path


def _directory_object_id(value: os.stat_result) -> tuple[int, int]:
    return value.st_dev, value.st_ino


def _open_child_directory(parent: int, name: str, label: str) -> int:
    """Select one directory entry, then retain it by descriptor."""
    descriptor = None
    try:
        expected = os.stat(name, dir_fd=parent, follow_symlinks=False)
        if stat.S_ISLNK(expected.st_mode) or not stat.S_ISDIR(expected.st_mode):
            raise AuditEvidenceError(f"{label} must be a non-symlink directory")
        descriptor = os.open(name, _DIRECTORY_FLAGS, dir_fd=parent)
        opened = os.fstat(descriptor)
        if not stat.S_ISDIR(opened.st_mode) or _directory_object_id(
            opened
        ) != _directory_object_id(expected):
            raise AuditEvidenceError(f"{label} changed before it could be anchored")
        result, descriptor = descriptor, None
        return result
    except AuditEvidenceError:
        raise
    except OSError as error:
        raise AuditEvidenceError(
            f"could not anchor {label}: {error.__class__.__name__}"
        ) from error
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _open_canonical_directory(path: Path, label: str) -> int:
    """Open an absolute, canonical directory path one component at a time."""
    descriptor = None
    try:
        descriptor = os.open(path.anchor, _DIRECTORY_FLAGS)
        for part in path.parts[1:]:
            next_descriptor = _open_child_directory(descriptor, part, label)
            os.close(descriptor)
            descriptor = next_descriptor
        result, descriptor = descriptor, None
        return result
    except AuditEvidenceError:
        raise
    except OSError as error:
        raise AuditEvidenceError(
            f"could not anchor {label}: {error.__class__.__name__}"
        ) from error
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _open_resolved_parent(path: Path, label: str) -> int:
    """Resolve aliases once, then anchor the selected parent by descriptors."""
    try:
        parent = path.parent.resolve(strict=True)
    except OSError as error:
        raise AuditEvidenceError(f"{label} parent does not exist") from error
    _reject_isolated(parent, label)
    return _open_canonical_directory(parent, f"{label} parent")


def _open_explicit_directory(path: Path, label: str) -> int:
    if path == Path(path.anchor):
        return _open_canonical_directory(path, label)
    parent = _open_resolved_parent(path, label)
    try:
        return _open_child_directory(parent, path.name, label)
    finally:
        os.close(parent)


def _consume(
    descriptor: int, expected: os.stat_result, label: str, *, private: bool = False
) -> tuple[bytes, os.stat_result]:
    if stat.S_ISLNK(expected.st_mode) or not stat.S_ISREG(expected.st_mode):
        raise AuditEvidenceError(f"{label} must be a regular, non-symlink file")
    if private and stat.S_IMODE(expected.st_mode) != 0o600:
        raise AuditEvidenceError(f"{label} must have mode 0o600")
    if expected.st_size > MAX_CONTENT_BYTES:
        raise AuditEvidenceError(f"{label} exceeds the {MAX_CONTENT_BYTES}-byte limit")
    before = os.fstat(descriptor)
    if not stat.S_ISREG(before.st_mode) or _identity(before) != _identity(expected):
        raise AuditEvidenceError(f"{label} changed before it could be read")
    chunks, total = [], 0
    while True:
        chunk = os.read(descriptor, min(65_536, MAX_CONTENT_BYTES + 1 - total))
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if total > MAX_CONTENT_BYTES:
            raise AuditEvidenceError(
                f"{label} exceeds the {MAX_CONTENT_BYTES}-byte limit"
            )
    after = os.fstat(descriptor)
    if _identity(after) != _identity(before):
        raise AuditEvidenceError(f"{label} changed while it was being read")
    return b"".join(chunks), after


def _read(
    path: Path, label: str, *, private: bool = False
) -> tuple[bytes, os.stat_result]:
    descriptor = None
    try:
        expected = path.lstat()
        if stat.S_ISLNK(expected.st_mode) or not stat.S_ISREG(expected.st_mode):
            raise AuditEvidenceError(f"{label} must be a regular, non-symlink file")
        descriptor = os.open(path, _READ_FLAGS)
        return _consume(descriptor, expected, label, private=private)
    except AuditEvidenceError:
        raise
    except OSError as error:
        raise AuditEvidenceError(
            f"could not read {label}: {error.__class__.__name__}"
        ) from error
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _logical_path(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise AuditEvidenceError(f"{label} must be a string")
    return cast(str, _binding(artifact_ref, value, b"")["path"])


def _source(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        raise AuditEvidenceError("source must be an object")
    kind = value.get("kind")
    if kind == "project-relative":
        source = _exact(value, {"kind", "path"}, "source")
        return {"kind": kind, "path": _logical_path(source["path"], "source path")}
    if kind == "external":
        source = _exact(value, {"kind", "ref"}, "source")
        return {"kind": kind, "ref": _logical_path(source["ref"], "source ref")}
    raise AuditEvidenceError("source kind must be project-relative or external")


def read_project_source(project_root: str | Path, relative_path: str) -> SourceSnapshot:
    """Read one explicit file from the successfully anchored project root."""
    logical = _logical_path(relative_path, "project-relative source path")
    root = _absolute_path(project_root, "project root")
    parts = logical.split("/")
    directory_descriptor = file_descriptor = None
    try:
        directory_descriptor = _open_explicit_directory(root, "project root")
        for part in parts[:-1]:
            try:
                next_descriptor = _open_child_directory(
                    directory_descriptor, part, "source parent"
                )
            except AuditEvidenceError as error:
                raise AuditEvidenceError(
                    "source parents must be non-symlink directories"
                ) from error
            os.close(directory_descriptor)
            directory_descriptor = next_descriptor
        expected = os.stat(
            parts[-1], dir_fd=directory_descriptor, follow_symlinks=False
        )
        if stat.S_ISLNK(expected.st_mode) or not stat.S_ISREG(expected.st_mode):
            raise AuditEvidenceError(
                "project-relative source must be a regular, non-symlink file"
            )
        file_descriptor = os.open(parts[-1], _READ_FLAGS, dir_fd=directory_descriptor)
        data, metadata = _consume(file_descriptor, expected, "project-relative source")
    except AuditEvidenceError:
        raise
    except OSError as error:
        raise AuditEvidenceError(
            f"could not read project-relative source: {error.__class__.__name__}"
        ) from error
    finally:
        if file_descriptor is not None:
            os.close(file_descriptor)
        if directory_descriptor is not None:
            os.close(directory_descriptor)
    return SourceSnapshot(
        {"kind": "project-relative", "path": logical},
        data,
        bool(metadata.st_mode & 0o111),
    )


def read_external_source(source_path: str | Path, source_ref: str) -> SourceSnapshot:
    """Read one external file selected from a successfully anchored parent."""
    logical = _logical_path(source_ref, "external source ref")
    path = _absolute_path(source_path, "external source")
    directory_descriptor = file_descriptor = None
    try:
        directory_descriptor = _open_resolved_parent(path, "external source")
        expected = os.stat(
            path.name, dir_fd=directory_descriptor, follow_symlinks=False
        )
        if stat.S_ISLNK(expected.st_mode) or not stat.S_ISREG(expected.st_mode):
            raise AuditEvidenceError(
                "external source must be a regular, non-symlink file"
            )
        file_descriptor = os.open(path.name, _READ_FLAGS, dir_fd=directory_descriptor)
        data, metadata = _consume(file_descriptor, expected, "external source")
    except AuditEvidenceError:
        raise
    except OSError as error:
        raise AuditEvidenceError(
            f"could not read external source: {error.__class__.__name__}"
        ) from error
    finally:
        if file_descriptor is not None:
            os.close(file_descriptor)
        if directory_descriptor is not None:
            os.close(directory_descriptor)
    return SourceSnapshot(
        {"kind": "external", "ref": logical}, data, bool(metadata.st_mode & 0o111)
    )


def _audit_manifest(value: object) -> CaseManifest:
    manifest = _binding(validate_case_manifest, value)
    if manifest["subject"]["kind"] != "git-project":
        raise AuditEvidenceError("audit case subject kind must be git-project")
    if manifest["source_revision"] is None:
        raise AuditEvidenceError("audit case must bind a Git source revision")
    artifacts = manifest["artifacts"]
    if len(artifacts) != 1 or artifacts[0]["path"] != CONTRACT_ARTIFACT_PATH:
        raise AuditEvidenceError(
            f"audit case must bind exactly {CONTRACT_ARTIFACT_PATH}"
        )
    if artifacts[0]["size"] > MAX_CONTENT_BYTES:
        raise AuditEvidenceError("research contract exceeds the content byte limit")
    return manifest


def build_audit_case_manifest(
    subject: Mapping[str, object],
    baseline_id: str,
    git_head: str,
    contract_bytes: bytes,
) -> CaseManifest:
    """Bind a stable Git subject, baseline ID, HEAD, and exact contract bytes."""
    if not isinstance(contract_bytes, bytes):
        raise AuditEvidenceError("research contract content must be bytes")
    if len(contract_bytes) > MAX_CONTENT_BYTES:
        raise AuditEvidenceError("research contract exceeds the content byte limit")
    normalized: SubjectRef = _binding(validate_subject_ref, subject)
    if normalized["kind"] != "git-project":
        raise AuditEvidenceError("audit case subject kind must be git-project")
    scheme = "git-sha1" if len(git_head) == 40 else "git-sha256"
    revision = _binding(source_revision, scheme, git_head)
    contract = _binding(artifact_ref, CONTRACT_ARTIFACT_PATH, contract_bytes)
    return _audit_manifest(
        _binding(
            build_case_manifest,
            normalized,
            baseline_id,
            [contract],
            source_revision_value=revision,
        )
    )


def validate_content_binding(value: object) -> dict[str, object]:
    record = _exact(
        value, {"schema_version", "binding_type", "case_ref"}, "content binding"
    )
    if type(record["schema_version"]) is not int or record["schema_version"] != 1:
        raise AuditEvidenceError("content binding schema version is not supported")
    if record["binding_type"] != CONTENT_BINDING_TYPE:
        raise AuditEvidenceError("content binding type is not supported")
    return {
        "schema_version": 1,
        "binding_type": CONTENT_BINDING_TYPE,
        "case_ref": _binding(validate_case_ref, record["case_ref"]),
    }


def _fsync_directory(path: Path) -> None:
    descriptor = None
    try:
        descriptor = os.open(path, _DIRECTORY_FLAGS)
        os.fsync(descriptor)
    except OSError as error:
        raise AuditEvidenceError("could not make CAS directory durable") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _store_directory(workspace: Path, parts: tuple[str, ...]) -> Path:
    current = workspace
    for part in parts:
        candidate = current / part
        created = False
        try:
            candidate.mkdir(mode=0o700)
            created = True
        except FileExistsError:
            pass
        except OSError as error:
            raise AuditEvidenceError("could not create CAS directory") from error
        try:
            metadata = candidate.lstat()
        except OSError as error:
            raise AuditEvidenceError("could not inspect CAS directory") from error
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise AuditEvidenceError("CAS path components must be regular directories")
        if metadata.st_mode & 0o022:
            raise AuditEvidenceError(
                "CAS directories must not be group- or world-writable"
            )
        if created:
            _fsync_directory(current)
        current = candidate
    return current


def _verify_bytes(path: Path, expected: bytes, label: str) -> None:
    actual, _ = _read(path, label, private=True)
    if actual != expected:
        raise AuditEvidenceError(f"existing {label} does not match its content address")


def _require_store_capacity(directory: Path, target: Path) -> None:
    """Refuse a new object before it would make this store unverifiable."""
    if os.path.lexists(target):
        return
    count = 0
    try:
        with os.scandir(directory) as entries:
            for _entry in entries:
                count += 1
                if count >= MAX_CAS_OBJECTS:
                    raise AuditEvidenceError("CAS object limit reached")
    except AuditEvidenceError:
        raise
    except OSError as error:
        raise AuditEvidenceError("could not enumerate CAS store") from error


def _put(path: Path, data: bytes, label: str, staging: Path) -> None:
    if os.path.lexists(path):
        _verify_bytes(path, data, label)
        return
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=staging
        )
    except OSError as error:
        raise AuditEvidenceError(f"could not stage {label}") from error
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        offset = 0
        while offset < len(data):
            written = os.write(descriptor, data[offset : offset + 65_536])
            if written <= 0:
                raise AuditEvidenceError("could not complete CAS object write")
            offset += written
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        try:
            os.link(temporary, path, follow_symlinks=False)
        except FileExistsError:
            pass
        temporary.unlink()
        _fsync_directory(path.parent)
        _verify_bytes(path, data, label)
    except AuditEvidenceError:
        raise
    except OSError as error:
        raise AuditEvidenceError(f"could not store {label}") from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if os.path.lexists(temporary):
            temporary.unlink(missing_ok=True)


def store_audit_case(
    workspace: str | Path, manifest: object, contract_bytes: bytes
) -> dict[str, object]:
    """Add the contract blob and its canonical manifest without overwriting CAS."""
    if not isinstance(contract_bytes, bytes):
        raise AuditEvidenceError("research contract content must be bytes")
    normalized = _audit_manifest(manifest)
    expected_contract = _binding(artifact_ref, CONTRACT_ARTIFACT_PATH, contract_bytes)
    if normalized["artifacts"] != [expected_contract]:
        raise AuditEvidenceError(
            "research contract bytes do not match the case manifest"
        )
    workspace_path = _directory(workspace, "audit workspace")
    staging = _store_directory(workspace_path, STAGING_PARTS)
    blob_store = _store_directory(workspace_path, BLOB_STORE_PARTS)
    manifest_bytes = _binding(canonical_json_bytes, normalized)
    manifest_store = _store_directory(workspace_path, CASE_STORE_PARTS)
    blob_path = blob_store / expected_contract["sha256"]
    manifest_path = manifest_store / f"{_binding(case_sha256, normalized)}.json"
    _require_store_capacity(blob_store, blob_path)
    _require_store_capacity(manifest_store, manifest_path)
    _put(
        blob_path,
        contract_bytes,
        "contract blob",
        staging,
    )
    _put(
        manifest_path,
        manifest_bytes,
        "case manifest",
        staging,
    )
    return {
        "schema_version": CONTENT_BINDING_SCHEMA_VERSION,
        "binding_type": CONTENT_BINDING_TYPE,
        "case_ref": _binding(case_ref, normalized),
    }


def store_evidence_blob(
    workspace: str | Path,
    logical_path: str,
    data: bytes,
    *,
    executable: bool = False,
) -> ArtifactRef:
    """Store caller-provided bytes without executing or interpreting them."""
    if not isinstance(data, bytes):
        raise AuditEvidenceError("evidence blob content must be bytes")
    if len(data) > MAX_CONTENT_BYTES:
        raise AuditEvidenceError("evidence blob exceeds the content byte limit")
    reference: ArtifactRef = _binding(
        artifact_ref, logical_path, data, executable=executable
    )
    workspace_path = _directory(workspace, "audit workspace")
    directory = _store_directory(workspace_path, BLOB_STORE_PARTS)
    staging = _store_directory(workspace_path, STAGING_PARTS)
    target = directory / reference["sha256"]
    _require_store_capacity(directory, target)
    _put(target, data, "evidence blob", staging)
    return reference


def build_content_evidence_record(
    *,
    evidence_id: str,
    evidence_type: str,
    kind: str,
    case: Mapping[str, object],
    artifact: Mapping[str, object],
    source: Mapping[str, object],
    summary: str,
    actor: str,
    recorded_at: str,
    artifact_role: str | None = None,
    environment_scope: str | None = None,
    declared_command: str | None = None,
    exit_code: int | None = None,
) -> dict[str, object]:
    record = {
        "schema_version": 1,
        "record_type": CONTENT_EVIDENCE_RECORD_TYPE,
        "id": evidence_id,
        "evidence_type": evidence_type,
        "kind": kind,
        "case_ref": dict(case),
        "artifact_ref": dict(artifact),
        "source": dict(source),
        "summary": summary,
        "actor": actor,
        "recorded_at": recorded_at,
    }
    if declared_command is not None:
        record["declared_command"] = declared_command
    if exit_code is not None:
        record["exit_code"] = exit_code
    if artifact_role is not None:
        record["artifact_role"] = artifact_role
    if environment_scope is not None:
        record["environment_scope"] = environment_scope
    return validate_content_evidence_record(record)


def validate_content_evidence_record(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise AuditEvidenceError("content evidence record must be an object")
    evidence_type = value.get("evidence_type")
    if evidence_type not in EVIDENCE_TYPES:
        raise AuditEvidenceError("evidence_type is not supported")
    keys = {
        "schema_version",
        "record_type",
        "id",
        "evidence_type",
        "kind",
        "case_ref",
        "artifact_ref",
        "source",
        "summary",
        "actor",
        "recorded_at",
    }
    if evidence_type == "artifact":
        keys.add("artifact_role")
    elif evidence_type == "environment":
        keys.add("environment_scope")
    else:
        keys |= {"declared_command", "exit_code"}
    record = _exact(value, keys, "content evidence record")
    if type(record["schema_version"]) is not int or record["schema_version"] != 1:
        raise AuditEvidenceError("content evidence schema version is not supported")
    if record["record_type"] != CONTENT_EVIDENCE_RECORD_TYPE:
        raise AuditEvidenceError("content evidence record type is not supported")
    if record["kind"] not in EVIDENCE_KINDS:
        raise AuditEvidenceError("evidence kind is not supported")
    normalized_case: CaseRef = _binding(validate_case_ref, record["case_ref"])
    normalized_artifact: ArtifactRef = _binding(
        validate_artifact_ref, record["artifact_ref"]
    )
    if normalized_artifact["size"] > MAX_CONTENT_BYTES:
        raise AuditEvidenceError("evidence artifact exceeds the content byte limit")
    normalized_source = _source(record["source"])
    logical_source = normalized_source.get("path", normalized_source.get("ref"))
    if normalized_artifact["path"] != logical_source:
        raise AuditEvidenceError("artifact_ref.path must equal the logical source path")
    normalized = {
        "schema_version": 1,
        "record_type": CONTENT_EVIDENCE_RECORD_TYPE,
        "id": _text(record["id"], "evidence id", 128),
        "evidence_type": evidence_type,
        "kind": record["kind"],
        "case_ref": normalized_case,
        "artifact_ref": normalized_artifact,
        "source": normalized_source,
        "summary": _text(record["summary"], "summary", 64_000),
        "actor": _text(record["actor"], "actor", 1_024),
        "recorded_at": _timestamp(record["recorded_at"]),
    }
    if evidence_type == "artifact":
        normalized["artifact_role"] = _text(
            record["artifact_role"], "artifact_role", 128
        )
    elif evidence_type == "environment":
        normalized["environment_scope"] = _text(
            record["environment_scope"], "environment_scope", 256
        )
    else:
        normalized["declared_command"] = _text(
            record["declared_command"], "declared_command", 64_000
        )
        exit_code = record["exit_code"]
        if (
            isinstance(exit_code, bool)
            or not isinstance(exit_code, int)
            or not -(2**31) <= exit_code < 2**31
        ):
            raise AuditEvidenceError("exit_code must be a signed 32-bit integer")
        normalized["exit_code"] = exit_code
    _binding(record_ref, "evidence", normalized["id"], normalized, normalized_case)
    if normalized != value:
        raise AuditEvidenceError("content evidence record is not canonical")
    return normalized


def content_evidence_record_ref(value: object) -> RecordRef:
    """Build the RecordRef that the lifecycle event must retain."""
    record = validate_content_evidence_record(value)
    return _binding(record_ref, "evidence", record["id"], record, record["case_ref"])


def verify_content_evidence_record_ref(value: object, reference: object) -> RecordRef:
    """Verify an inline record against the RecordRef retained by lifecycle."""
    record = validate_content_evidence_record(value)
    supplied: RecordRef = _binding(validate_record_ref, reference)
    if supplied["record_type"] != "evidence":
        raise AuditEvidenceError(
            "content evidence RecordRef must use record_type evidence"
        )
    expected = content_evidence_record_ref(record)
    if supplied != expected:
        raise AuditEvidenceError(
            "content evidence RecordRef does not bind the inline record"
        )
    return supplied


def _manifest_object(path: Path, digest: str) -> CaseManifest:
    data, _ = _read(path, "case manifest CAS object", private=True)
    try:
        parsed = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AuditEvidenceError(
            "case manifest CAS object is not UTF-8 JSON"
        ) from error
    manifest = _audit_manifest(parsed)
    if data != _binding(canonical_json_bytes, manifest):
        raise AuditEvidenceError("case manifest CAS object is not canonical JSON")
    if _binding(case_sha256, manifest) != digest:
        raise AuditEvidenceError("case manifest does not match its content address")
    return manifest


def _blob_object(path: Path, digest: str) -> int:
    data, _ = _read(path, "blob CAS object", private=True)
    if hashlib.sha256(data).hexdigest() != digest:
        raise AuditEvidenceError("blob does not match its content address")
    return len(data)


def _store_names(workspace: Path, parts: tuple[str, ...]) -> tuple[Path, list[str]]:
    directory = workspace.joinpath(*parts)
    try:
        metadata = directory.lstat()
    except OSError as error:
        raise AuditEvidenceError("required CAS directory is missing") from error
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise AuditEvidenceError("CAS store must be a regular directory")
    names = []
    try:
        with os.scandir(directory) as entries:
            for entry in entries:
                if len(names) >= MAX_CAS_OBJECTS:
                    raise AuditEvidenceError("CAS object limit exceeded")
                names.append(entry.name)
    except OSError as error:
        raise AuditEvidenceError("could not enumerate CAS store") from error
    return directory, sorted(names)


def verify_content_store(
    workspace: str | Path,
    content_binding: object,
    evidence_records: Iterable[object],
    *,
    historical_case_refs: Iterable[object] = (),
) -> dict[str, int]:
    """Verify current and historical cases, all blobs, and count valid orphans."""
    workspace_path = _directory(workspace, "audit workspace")
    binding = validate_content_binding(content_binding)
    active_case = cast(CaseRef, binding["case_ref"])
    active_subject_id = active_case["subject_id"]
    refs: dict[str, CaseRef] = {}

    def remember_case(value: object) -> None:
        reference: CaseRef = _binding(validate_case_ref, value)
        if reference["subject_id"] != active_subject_id:
            raise AuditEvidenceError(
                "CaseRef subject_id must match the active content binding"
            )
        previous = refs.get(reference["case_sha256"])
        if previous is not None and previous != reference:
            raise AuditEvidenceError("contradictory CaseRefs share one digest")
        refs[reference["case_sha256"]] = reference

    remember_case(binding["case_ref"])
    for index, value in enumerate(historical_case_refs):
        if index >= MAX_CAS_OBJECTS:
            raise AuditEvidenceError("historical CaseRef limit exceeded")
        remember_case(value)
    records, ids = [], set()
    for value in evidence_records:
        if len(records) >= MAX_EVIDENCE_RECORDS:
            raise AuditEvidenceError("content evidence record limit exceeded")
        record = validate_content_evidence_record(value)
        if record["id"] in ids:
            raise AuditEvidenceError(f"duplicate evidence id: {record['id']}")
        ids.add(record["id"])
        remember_case(record["case_ref"])
        records.append(record)
    case_directory, case_names = _store_names(workspace_path, CASE_STORE_PARTS)
    manifests: dict[str, CaseManifest] = {}
    for name in case_names:
        digest = name[:-5] if name.endswith(".json") else ""
        if not _SHA256.fullmatch(digest):
            raise AuditEvidenceError(f"case manifest store has illegal entry: {name}")
        manifests[digest] = _manifest_object(case_directory / name, digest)
    for digest, reference in refs.items():
        manifest = manifests.get(digest)
        if manifest is None or _binding(case_ref, manifest) != reference:
            raise AuditEvidenceError("CaseRef has no matching case manifest")
    blob_directory, blob_names = _store_names(workspace_path, BLOB_STORE_PARTS)
    blob_sizes: dict[str, int] = {}
    for name in blob_names:
        if not _SHA256.fullmatch(name):
            raise AuditEvidenceError(f"blob store has illegal entry: {name}")
        blob_sizes[name] = _blob_object(blob_directory / name, name)
    referenced_blobs = set()
    for digest, manifest in manifests.items():
        artifact = manifest["artifacts"][0]
        if blob_sizes.get(artifact["sha256"]) != artifact["size"]:
            raise AuditEvidenceError("case ArtifactRef has no matching blob")
        if digest in refs:
            referenced_blobs.add(artifact["sha256"])
    for record in records:
        artifact = cast(ArtifactRef, record["artifact_ref"])
        if blob_sizes.get(artifact["sha256"]) != artifact["size"]:
            raise AuditEvidenceError("evidence ArtifactRef has no matching blob")
        referenced_blobs.add(artifact["sha256"])
    return {
        "referenced_case_manifests": len(refs),
        "referenced_evidence_blobs": len(referenced_blobs),
        "orphan_case_manifests": len(set(manifests) - set(refs)),
        "orphan_evidence_blobs": len(set(blob_sizes) - referenced_blobs),
    }


__all__ = (
    "AuditEvidenceError",
    "SourceSnapshot",
    "build_audit_case_manifest",
    "build_content_evidence_record",
    "content_evidence_record_ref",
    "read_external_source",
    "read_project_source",
    "store_audit_case",
    "store_evidence_blob",
    "validate_content_binding",
    "validate_content_evidence_record",
    "verify_content_evidence_record_ref",
    "verify_content_store",
)
