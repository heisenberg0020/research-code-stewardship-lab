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
MAX_JSON_NODES = 100_000
MAX_JSON_STRING_BYTES = 1_000_000
MAX_CANONICAL_JSON_BYTES = 16_000_000
MAX_ARTIFACT_PATH_BYTES = 4_096
MAX_ARTIFACT_PATH_PART_BYTES = 255
MAX_ARTIFACTS = 10_000
MIN_JSON_INTEGER = -(2**63)
MAX_JSON_INTEGER = 2**63 - 1
RECORD_BINDING_DOMAIN = "rcsl-record-binding"
RECORD_BINDING_SCHEMA_VERSION = 1

_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
_GIT_SHA1_PATTERN = re.compile(r"[0-9a-f]{40}\Z")
_GIT_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
_WINDOWS_FORBIDDEN_CHARACTERS = frozenset('<>:"|?*')
_WINDOWS_RESERVED_STEMS = frozenset(
    {
        "aux",
        "clock$",
        "con",
        "conin$",
        "conout$",
        "nul",
        "prn",
        *(f"com{suffix}" for suffix in "123456789¹²³"),
        *(f"lpt{suffix}" for suffix in "123456789¹²³"),
    }
)


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
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise BindingError(f"{field} must contain Unicode scalar values")
    try:
        encoded = value.encode("utf-8")
    except UnicodeError as error:
        raise BindingError(f"{field} must be valid UTF-8 text") from error
    if len(encoded) > MAX_JSON_STRING_BYTES:
        raise BindingError(
            f"{field} exceeds the {MAX_JSON_STRING_BYTES}-byte string limit"
        )
    return value


def _consume_json_node(state: list[int], *, field: str) -> None:
    state[0] += 1
    if state[0] > MAX_JSON_NODES:
        raise BindingError(f"{field} exceeds the {MAX_JSON_NODES}-node JSON limit")


def _validate_json_value(
    value: object, *, field: str, depth: int = 0, state: list[int] | None = None
) -> None:
    if state is None:
        state = [0]
    _consume_json_node(state, field=field)
    if depth > MAX_JSON_NESTING:
        raise BindingError(f"{field} exceeds the JSON nesting limit")
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, int):
        if value < MIN_JSON_INTEGER or value > MAX_JSON_INTEGER:
            raise BindingError(f"{field} integer must fit in signed 64 bits")
        return
    if isinstance(value, float):
        raise BindingError(f"{field} must not contain floating-point numbers")
    if isinstance(value, str):
        _require_canonical_string(value, field=field)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(
                item,
                field=f"{field}[{index}]",
                depth=depth + 1,
                state=state,
            )
        return
    if isinstance(value, dict):
        for index, (key, item) in enumerate(value.items()):
            _consume_json_node(state, field=f"{field} key")
            _require_canonical_string(key, field=f"{field} key")
            _validate_json_value(
                item,
                field=f"{field}[{index}]",
                depth=depth + 1,
                state=state,
            )
        return
    raise BindingError(f"{field} contains a non-JSON value: {type(value).__name__}")


def canonical_json_bytes(value: object) -> bytes:
    """Return one deterministic UTF-8 JSON representation.

    Floating-point values are refused so semantically surprising encodings such
    as NaN, infinity, and negative zero cannot enter an identity digest.
    """

    try:
        _validate_json_value(value, field="value")
        encoder = json.JSONEncoder(
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        output = bytearray()
        for chunk in encoder.iterencode(value):
            encoded = chunk.encode("utf-8")
            if len(output) + len(encoded) > MAX_CANONICAL_JSON_BYTES:
                raise BindingError(
                    "canonical JSON exceeds the "
                    f"{MAX_CANONICAL_JSON_BYTES}-byte limit"
                )
            output.extend(encoded)
        return bytes(output)
    except BindingError:
        raise
    except (RecursionError, RuntimeError, TypeError, UnicodeError, ValueError) as error:
        raise BindingError(f"value cannot be encoded as canonical JSON: {error}") from error


def sha256_json(value: object) -> str:
    """Return the SHA-256 digest of :func:`canonical_json_bytes`."""

    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _validate_artifact_path(value: object) -> str:
    path = _require_canonical_string(value, field="artifact path")
    if len(path.encode("utf-8")) > MAX_ARTIFACT_PATH_BYTES:
        raise BindingError(
            f"artifact path exceeds the {MAX_ARTIFACT_PATH_BYTES}-byte limit"
        )
    if (
        not path
        or "\\" in path
        or any(character in _WINDOWS_FORBIDDEN_CHARACTERS for character in path)
        or any(unicodedata.category(character) in {"Cc", "Cs"} for character in path)
    ):
        raise BindingError("artifact path must be a non-empty canonical POSIX path")
    parsed = PurePosixPath(path)
    if not parsed.parts or parsed.is_absolute() or str(parsed) != path:
        raise BindingError("artifact path must be a canonical relative POSIX path")
    if any(part in ("", ".", "..") for part in parsed.parts):
        raise BindingError("artifact path must not contain empty, dot, or parent parts")
    for part in parsed.parts:
        if len(part.encode("utf-8")) > MAX_ARTIFACT_PATH_PART_BYTES:
            raise BindingError(
                "artifact path part exceeds the "
                f"{MAX_ARTIFACT_PATH_PART_BYTES}-byte limit"
            )
        if part.endswith((".", " ")):
            raise BindingError("artifact path parts must not end with a dot or space")
        windows_stem = part.split(".", 1)[0].rstrip(" ").casefold()
        if windows_stem in _WINDOWS_RESERVED_STEMS:
            raise BindingError("artifact path must not use a Windows reserved device name")
    isolated = ISOLATED_DIRECTORY_NAME.casefold()
    if any(part.casefold() == isolated for part in parsed.parts):
        raise BindingError("artifact path must not reference isolated material")
    return path


def _artifact_path_collision_key(path: str) -> str:
    return "/".join(
        unicodedata.normalize("NFC", part.casefold())
        for part in PurePosixPath(path).parts
    )


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
    if (
        isinstance(size, bool)
        or not isinstance(size, int)
        or size < 0
        or size > MAX_JSON_INTEGER
    ):
        raise BindingError("artifact size must be an integer from 0 through 2^63 - 1")
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
        collision_key = _artifact_path_collision_key(item["path"])
        if collision_key in seen:
            raise BindingError("case manifest contains colliding artifact paths")
        seen.add(collision_key)
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


def _require_record_type(value: object) -> str:
    if value not in RECORD_TYPES:
        raise BindingError(f"record type must be one of: {', '.join(RECORD_TYPES)}")
    return cast(str, value)


def _record_binding_envelope(
    record_type: object,
    record_id: object,
    record: object,
    case: object,
) -> dict[str, object]:
    normalized_type = _require_record_type(record_type)
    normalized_id = _require_id(record_id, field="record id")
    normalized_case = validate_case_ref(case)
    if not isinstance(record, dict):
        raise BindingError("record must be an object")
    if "id" not in record:
        raise BindingError("record must contain id")
    internal_id = _require_id(record["id"], field="record.id")
    if internal_id != normalized_id:
        raise BindingError("record.id must match record id")
    if "case_ref" not in record:
        raise BindingError("record must contain case_ref")
    internal_case = validate_case_ref(record["case_ref"])
    if internal_case != normalized_case:
        raise BindingError("record.case_ref must match case ref")
    return {
        "schema_version": RECORD_BINDING_SCHEMA_VERSION,
        "domain": RECORD_BINDING_DOMAIN,
        "record_type": normalized_type,
        "record_id": normalized_id,
        "case_sha256": normalized_case["case_sha256"],
        "record": record,
    }


def record_ref(
    record_type: str,
    record_id: str,
    record: object,
    case: Mapping[str, object],
) -> RecordRef:
    """Bind one canonical object record to its declared ID and exact case."""

    envelope = _record_binding_envelope(record_type, record_id, record, case)
    return {
        "record_type": cast(str, envelope["record_type"]),
        "record_id": cast(str, envelope["record_id"]),
        "record_sha256": sha256_json(envelope),
        "case_sha256": cast(str, envelope["case_sha256"]),
    }


def validate_record_ref(value: object) -> RecordRef:
    """Validate the shape of a reference without claiming its record is present."""

    record = _require_exact_keys(
        value,
        {"record_type", "record_id", "record_sha256", "case_sha256"},
        field="record ref",
    )
    return {
        "record_type": _require_record_type(record["record_type"]),
        "record_id": _require_id(record["record_id"], field="record id"),
        "record_sha256": _require_sha256(
            record["record_sha256"], field="record sha256"
        ),
        "case_sha256": _require_sha256(
            record["case_sha256"], field="case sha256"
        ),
    }


def verify_record_ref(
    value: object, record: object, case: Mapping[str, object]
) -> RecordRef:
    """Verify a reference against the exact canonical record and case it names."""

    reference = validate_record_ref(value)
    normalized_case = validate_case_ref(case)
    if reference["case_sha256"] != normalized_case["case_sha256"]:
        raise BindingError("record ref case sha256 does not match case ref")
    expected = record_ref(
        reference["record_type"],
        reference["record_id"],
        record,
        normalized_case,
    )
    if expected != reference:
        raise BindingError("record ref digest does not match record binding")
    return reference


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
    "sha256_json",
    "source_revision",
    "subject_ref",
    "validate_artifact_ref",
    "validate_case_manifest",
    "validate_case_ref",
    "validate_record_ref",
    "validate_source_revision",
    "validate_subject_ref",
    "verify_record_ref",
)
