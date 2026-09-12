"""Small, deterministic identity bindings shared by audit and training.

This module owns value validation and content digests only.  It deliberately does
not read or write files, acquire locks, manage lifecycle state, authenticate
labels, or decide whether evidence is sufficient.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import PurePosixPath
import re
from typing import Iterable, Mapping, TypedDict, cast
import unicodedata


SCHEMA_VERSION = 1
MANIFEST_TYPE = "rcsl-case"
ISOLATED_DIRECTORY_NAME = "DO_NOT_OPEN_UNTIL_FINISHED"
SUBJECT_KINDS = ("git-project", "training-case")
SOURCE_REVISION_SCHEMES = ("git-sha1", "git-sha256")
RECORD_TYPES = ("attempt", "evidence", "finding", "review")
MAX_JSON_NESTING = 100
MAX_ARTIFACTS = 100_000

_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
_GIT_SHA1_PATTERN = re.compile(r"[0-9a-f]{40}\Z")
_GIT_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
_WINDOWS_DRIVE_PATTERN = re.compile(r"[A-Za-z]:\Z")


class BindingError(ValueError):
    """Raised when an identity value is ambiguous or not canonical."""


class SubjectRef(TypedDict):
    id: str
    kind: str


class ArtifactRef(TypedDict):
    path: str
    sha256: str
    size: int
    executable: bool


class SourceRevision(TypedDict):
    scheme: str
    value: str


class CaseManifest(TypedDict):
    schema_version: int
    manifest_type: str
    subject: SubjectRef
    case_id: str
    source_revision: SourceRevision | None
    artifacts: list[ArtifactRef]


class CaseRef(TypedDict):
    subject_id: str
    case_id: str
    case_sha256: str


class RecordRef(TypedDict):
    record_type: str
    record_id: str
    record_sha256: str
    case_sha256: str


def _require_exact_keys(
    value: object, expected: set[str], *, field: str
) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise BindingError(f"{field} must be an object")
    if any(not isinstance(key, str) for key in value):
        raise BindingError(f"{field} keys must be strings")
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        details: list[str] = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if unknown:
            details.append("unknown " + ", ".join(unknown))
        raise BindingError(f"{field} has invalid fields: {'; '.join(details)}")
    return value


def _require_id(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not _ID_PATTERN.fullmatch(value):
        raise BindingError(
            f"{field} must be 1-128 ASCII letters, digits, dot, underscore, colon, "
            "slash, or hyphen and must start with a letter or digit"
        )
    return value


def _require_sha256(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not _SHA256_PATTERN.fullmatch(value):
        raise BindingError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _require_canonical_string(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise BindingError(f"{field} must be a string")
    if unicodedata.normalize("NFC", value) != value:
        raise BindingError(f"{field} must use NFC Unicode normalization")
    return value


def _validate_json_value(value: object, *, field: str, depth: int = 0) -> None:
    if depth > MAX_JSON_NESTING:
        raise BindingError(f"{field} exceeds the JSON nesting limit")
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        raise BindingError(f"{field} must not contain floating-point numbers")
    if isinstance(value, str):
        _require_canonical_string(value, field=field)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, field=f"{field}[{index}]", depth=depth + 1)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            canonical_key = _require_canonical_string(key, field=f"{field} key")
            _validate_json_value(
                item, field=f"{field}.{canonical_key}", depth=depth + 1
            )
        return
    raise BindingError(f"{field} contains a non-JSON value: {type(value).__name__}")


def canonical_json_bytes(value: object) -> bytes:
    """Return one deterministic UTF-8 JSON representation.

    Floating-point values are refused so semantically surprising encodings such
    as NaN, infinity, and negative zero cannot enter an identity digest.
    """

    _validate_json_value(value, field="value")
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_json(value: object) -> str:
    """Return the SHA-256 digest of :func:`canonical_json_bytes`."""

    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _validate_artifact_path(value: object) -> str:
    path = _require_canonical_string(value, field="artifact path")
    if not path or "\\" in path or any(ord(character) < 32 for character in path):
        raise BindingError("artifact path must be a non-empty canonical POSIX path")
    parsed = PurePosixPath(path)
    if not parsed.parts or parsed.is_absolute() or str(parsed) != path:
        raise BindingError("artifact path must be a canonical relative POSIX path")
    if any(part in ("", ".", "..") for part in parsed.parts):
        raise BindingError("artifact path must not contain empty, dot, or parent parts")
    if parsed.parts and _WINDOWS_DRIVE_PATTERN.fullmatch(parsed.parts[0]):
        raise BindingError("artifact path must not contain a Windows drive prefix")
    isolated = ISOLATED_DIRECTORY_NAME.casefold()
    if any(part.casefold() == isolated for part in parsed.parts):
        raise BindingError("artifact path must not reference isolated material")
    return path


def subject_ref(subject_id: str, kind: str) -> SubjectRef:
    """Build a logical subject label; this is not an authenticated identity."""

    return validate_subject_ref({"id": subject_id, "kind": kind})


def validate_subject_ref(value: object) -> SubjectRef:
    record = _require_exact_keys(value, {"id", "kind"}, field="subject ref")
    subject_id = _require_id(record["id"], field="subject id")
    kind = record["kind"]
    if kind not in SUBJECT_KINDS:
        raise BindingError(f"subject kind must be one of: {', '.join(SUBJECT_KINDS)}")
    return {"id": subject_id, "kind": cast(str, kind)}


def artifact_ref(path: str, data: bytes, *, executable: bool = False) -> ArtifactRef:
    """Build an artifact identity from caller-supplied bytes without filesystem I/O."""

    if not isinstance(data, bytes):
        raise BindingError("artifact data must be bytes")
    if not isinstance(executable, bool):
        raise BindingError("artifact executable must be a boolean")
    return {
        "path": _validate_artifact_path(path),
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": len(data),
        "executable": executable,
    }


def validate_artifact_ref(value: object) -> ArtifactRef:
    record = _require_exact_keys(
        value, {"path", "sha256", "size", "executable"}, field="artifact ref"
    )
    size = record["size"]
    if isinstance(size, bool) or not isinstance(size, int) or size < 0:
        raise BindingError("artifact size must be a non-negative integer")
    executable = record["executable"]
    if not isinstance(executable, bool):
        raise BindingError("artifact executable must be a boolean")
    return {
        "path": _validate_artifact_path(record["path"]),
        "sha256": _require_sha256(record["sha256"], field="artifact sha256"),
        "size": size,
        "executable": executable,
    }


def source_revision(scheme: str, value: str) -> SourceRevision:
    """Build a Git source revision used as case provenance."""

    return validate_source_revision({"scheme": scheme, "value": value})


def validate_source_revision(value: object) -> SourceRevision:
    record = _require_exact_keys(
        value, {"scheme", "value"}, field="source revision"
    )
    scheme = record["scheme"]
    revision = record["value"]
    if scheme not in SOURCE_REVISION_SCHEMES:
        raise BindingError(
            "source revision scheme must be one of: "
            + ", ".join(SOURCE_REVISION_SCHEMES)
        )
    pattern = _GIT_SHA1_PATTERN if scheme == "git-sha1" else _GIT_SHA256_PATTERN
    if not isinstance(revision, str) or not pattern.fullmatch(revision):
        expected = 40 if scheme == "git-sha1" else 64
        raise BindingError(
            f"source revision value must be {expected} lowercase hexadecimal characters"
        )
    return {"scheme": cast(str, scheme), "value": revision}


def build_case_manifest(
    subject: Mapping[str, object],
    case_id: str,
    artifacts: Iterable[Mapping[str, object]],
    *,
    source_revision_value: Mapping[str, object] | None = None,
) -> CaseManifest:
    """Build a canonical case manifest sorted by artifact path."""

    normalized_subject = validate_subject_ref(subject)
    normalized_artifacts: list[ArtifactRef] = []
    for item in artifacts:
        if len(normalized_artifacts) >= MAX_ARTIFACTS:
            raise BindingError(f"case manifest exceeds the {MAX_ARTIFACTS}-artifact limit")
        normalized_artifacts.append(validate_artifact_ref(item))
    if not normalized_artifacts:
        raise BindingError("case manifest must contain at least one artifact")
    normalized_artifacts.sort(key=lambda item: item["path"])
    seen: set[str] = set()
    for item in normalized_artifacts:
        folded = item["path"].casefold()
        if folded in seen:
            raise BindingError("case manifest contains colliding artifact paths")
        seen.add(folded)
    revision = (
        None
        if source_revision_value is None
        else validate_source_revision(source_revision_value)
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "manifest_type": MANIFEST_TYPE,
        "subject": normalized_subject,
        "case_id": _require_id(case_id, field="case id"),
        "source_revision": revision,
        "artifacts": normalized_artifacts,
    }


def validate_case_manifest(value: object) -> CaseManifest:
    record = _require_exact_keys(
        value,
        {
            "schema_version",
            "manifest_type",
            "subject",
            "case_id",
            "source_revision",
            "artifacts",
        },
        field="case manifest",
    )
    if type(record["schema_version"]) is not int or record["schema_version"] != SCHEMA_VERSION:
        raise BindingError("case manifest schema version is not supported")
    if record["manifest_type"] != MANIFEST_TYPE:
        raise BindingError("case manifest type is not supported")
    artifacts = record["artifacts"]
    if not isinstance(artifacts, list):
        raise BindingError("case manifest artifacts must be a list")
    revision = record["source_revision"]
    normalized = build_case_manifest(
        validate_subject_ref(record["subject"]),
        _require_id(record["case_id"], field="case id"),
        artifacts,
        source_revision_value=(
            None if revision is None else validate_source_revision(revision)
        ),
    )
    if normalized["artifacts"] != artifacts:
        raise BindingError("case manifest artifacts must use canonical path order")
    return normalized


def case_sha256(manifest: object) -> str:
    """Return the identity digest of a validated case manifest."""

    return sha256_json(validate_case_manifest(manifest))


def case_ref(manifest: object) -> CaseRef:
    """Build the small reference embedded by audit and training records."""

    normalized = validate_case_manifest(manifest)
    return {
        "subject_id": normalized["subject"]["id"],
        "case_id": normalized["case_id"],
        "case_sha256": sha256_json(normalized),
    }


def validate_case_ref(value: object) -> CaseRef:
    record = _require_exact_keys(
        value, {"subject_id", "case_id", "case_sha256"}, field="case ref"
    )
    return {
        "subject_id": _require_id(record["subject_id"], field="subject id"),
        "case_id": _require_id(record["case_id"], field="case id"),
        "case_sha256": _require_sha256(
            record["case_sha256"], field="case sha256"
        ),
    }


def record_sha256(record: object) -> str:
    """Return a digest for a caller-owned evidence, attempt, finding, or review."""

    return sha256_json(record)


def record_ref(
    record_type: str,
    record_id: str,
    record: object,
    case: Mapping[str, object],
) -> RecordRef:
    """Bind one immutable caller-owned record to an exact case digest."""

    normalized_case = validate_case_ref(case)
    return validate_record_ref(
        {
            "record_type": record_type,
            "record_id": record_id,
            "record_sha256": record_sha256(record),
            "case_sha256": normalized_case["case_sha256"],
        }
    )


def validate_record_ref(value: object) -> RecordRef:
    record = _require_exact_keys(
        value,
        {"record_type", "record_id", "record_sha256", "case_sha256"},
        field="record ref",
    )
    record_type_value = record["record_type"]
    if record_type_value not in RECORD_TYPES:
        raise BindingError(f"record type must be one of: {', '.join(RECORD_TYPES)}")
    return {
        "record_type": cast(str, record_type_value),
        "record_id": _require_id(record["record_id"], field="record id"),
        "record_sha256": _require_sha256(
            record["record_sha256"], field="record sha256"
        ),
        "case_sha256": _require_sha256(
            record["case_sha256"], field="case sha256"
        ),
    }


__all__ = (
    "ArtifactRef",
    "BindingError",
    "CaseManifest",
    "CaseRef",
    "RecordRef",
    "SourceRevision",
    "SubjectRef",
    "artifact_ref",
    "build_case_manifest",
    "canonical_json_bytes",
    "case_ref",
    "case_sha256",
    "record_ref",
    "record_sha256",
    "sha256_json",
    "source_revision",
    "subject_ref",
    "validate_artifact_ref",
    "validate_case_manifest",
    "validate_case_ref",
    "validate_record_ref",
    "validate_source_revision",
    "validate_subject_ref",
)
