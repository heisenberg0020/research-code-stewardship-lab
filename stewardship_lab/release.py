"""Honest Open Demo export and boundary-preserving blind-package assembly.

The module is intentionally local-first and standard-library only.  It copies
bytes, verifies explicit manifests, and records package boundaries.  It does not
provide access control, prove novelty, execute private graders, or certify
scientific or educational validity.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import stat
import subprocess
import sys
import tempfile
from typing import Iterable
import unicodedata


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
OPEN_DEMO_SOURCE = REPOSITORY_ROOT / "LLM4SBR_research_audit_training_v2"
ASSET_DIRECTORY = (
    REPOSITORY_ROOT / "skills" / "research-code-audit-training" / "assets"
)
STATIC_VALIDATOR = (
    REPOSITORY_ROOT
    / "skills"
    / "research-code-audit-training"
    / "scripts"
    / "validate_training_package.py"
)
PUBLIC_CHECK_RUNNER = OPEN_DEMO_SOURCE / "run_all_public_checks.py"
REVOCATION_TEMPLATE = ASSET_DIRECTORY / "revocation-notice-template.md"
ACCESS_LOG_TEMPLATE = ASSET_DIRECTORY / "access-log-template.md"

ISOLATED_DIRECTORY_NAME = "DO_NOT_OPEN_UNTIL_FINISHED"
SCHEMA_VERSION = 1
MAX_MANIFEST_BYTES = 2_000_000
MAX_FILE_BYTES = 32_000_000
MAX_TOTAL_BYTES = 256_000_000
MAX_FILES = 10_000
MAX_PACKAGE_FILES = MAX_FILES + 32
MAX_PACKAGE_TOTAL_BYTES = MAX_TOTAL_BYTES + 64_000_000
MAX_JSON_NESTING = 100

ROLES = ("challenge", "evaluator", "maintainer")
ROLE_SENSITIVITY = {
    "challenge": "public",
    "evaluator": "controlled-evaluator",
    "maintainer": "controlled-maintainer",
}
APPROVAL_GATES = (
    "provenance",
    "license",
    "design",
    "leakage",
    "release-preparation",
)
OPERATIONAL_GATES_REMAINING = (
    "independent controlled storage and least-privilege placement",
    "access logging and submission-channel review",
    "independent evaluator execution and repeatability review",
    "complete Git-history and human leakage review",
    "human release sign-off and leakage/withdrawal drill",
)
TEXT_SUFFIXES = {
    ".c",
    ".cc",
    ".cfg",
    ".conf",
    ".cpp",
    ".css",
    ".csv",
    ".h",
    ".hpp",
    ".html",
    ".ini",
    ".ipynb",
    ".java",
    ".jl",
    ".js",
    ".json",
    ".jsonl",
    ".md",
    ".m",
    ".py",
    ".r",
    ".rs",
    ".rst",
    ".sh",
    ".sql",
    ".tex",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
OPEN_DEMO_SKIPPED_NAMES = {
    ISOLATED_DIRECTORY_NAME.casefold(),
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".ds_store",
}
GENERATED_PACKAGE_NAMES = {
    "package_manifest.json",
    "checksums.sha256",
    "release_boundary.md",
    "verify_package.py",
    "leakage_scan.json",
    "blind_source.json",
    "revocation_notice_template.md",
    "access_log_template.md",
}
ROLE_GENERATED_FILES = {
    "challenge": {
        "RELEASE_BOUNDARY.md",
        "verify_package.py",
        "LEAKAGE_SCAN.json",
        "PACKAGE_MANIFEST.json",
        "CHECKSUMS.sha256",
    },
    "evaluator": {
        "RELEASE_BOUNDARY.md",
        "verify_package.py",
        "PACKAGE_MANIFEST.json",
        "CHECKSUMS.sha256",
    },
    "maintainer": {
        "RELEASE_BOUNDARY.md",
        "verify_package.py",
        "BLIND_SOURCE.json",
        "REVOCATION_NOTICE_TEMPLATE.md",
        "ACCESS_LOG_TEMPLATE.md",
        "PACKAGE_MANIFEST.json",
        "CHECKSUMS.sha256",
    },
}
OPEN_DEMO_NON_SOURCE_FILES = {
    "LICENSE",
    "DOCUMENTATION_LICENSE.md",
    "THIRD_PARTY_NOTICES.md",
    "docs/CASE_RELEASE_MODEL.md",
    "docs/CASE_RELEASE_MODEL_EN.md",
    "RELEASE_BOUNDARY.md",
    "VALIDATION_RECORD.json",
    "REVOCATION_NOTICE_TEMPLATE.md",
    "verify_package.py",
    "PACKAGE_MANIFEST.json",
    "CHECKSUMS.sha256",
}

ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$")
SEMVER_PATTERN = re.compile(
    r"^(?:0|[1-9][0-9]*)[.](?:0|[1-9][0-9]*)[.](?:0|[1-9][0-9]*)"
    r"(?:-(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:[.](?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*))*)?"
    r"(?:[+][0-9A-Za-z-]+(?:[.][0-9A-Za-z-]+)*)?$"
)
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
ZERO_SHA256 = "0" * 64
GIT_REVISION = re.compile(r"^[0-9a-f]{40,64}$")
UTC_TIMESTAMP_PATTERN = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:[.][0-9]+)?Z$"
)
FORBIDDEN_CHALLENGE_PATH = re.compile(
    r"(?:^|[-_.])(?:answers?|answer[-_]?(?:map|manifest|key)|solutions?|"
    r"private[-_]?probes?|hidden[-_]?probes?|grader|evaluation[-_]?labels?|"
    r"mutation[-_]?ledger|evaluator|maintainer)(?:$|[-_.])",
    re.IGNORECASE,
)
FORBIDDEN_CHALLENGE_TEXT = re.compile(
    r"\b(?:trusted[\s_-]+candidate|correct[\s_-]+candidate|"
    r"expected[\s_-]+answer|answer[\s_-]+mapping|answer[\s_-]+manifest|"
    r"private[\s_-]+probe|hidden[\s_-]+probe|evaluation[\s_-]+label|"
    r"mutation[\s_-]+ledger|repair[\s_-]+span|hidden[\s_-]+rule[\s_-]+id)"
    r"\b[\"']?\s*(?:\])?\s*(?:=|:|\bis\b)",
    re.IGNORECASE,
)
FORBIDDEN_CHALLENGE_IMPORT = re.compile(
    r"(?:^|\n)\s*(?:from|import)\s+(?:evaluator|maintainer)(?:\b|\.)|"
    r"(?:\.\./)+(?:evaluator|maintainer)(?:/|\\)",
    re.IGNORECASE,
)
FORBIDDEN_CHALLENGE_PATH_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".env",
    "credentials",
    "credentials.json",
    "id_ed25519",
    "id_rsa",
}
FORBIDDEN_CHALLENGE_SECRET_SUFFIXES = {".key", ".p12", ".pem", ".pfx"}
CHALLENGE_LEAKAGE_LIMIT = (
    "A passing pattern scan is not proof that no answer signal, private data, "
    "or unfair cue remains. An isolated Challenge verifier cannot know private "
    "values such as the scoring digest; trusted staging verification and "
    "independent human review are still required."
)

BLIND_TOP_LEVEL_KEYS = {
    "schema_version",
    "manifest_type",
    "release_id",
    "case_id",
    "case_version",
    "release_mode",
    "created_at",
    "novelty_attestation",
    "source_bindings",
    "package_files",
    "licenses",
    "scoring",
    "isolation",
    "validation",
    "withdrawal",
    "claims_not_made",
    "human_approvals",
}


class ReleaseError(RuntimeError):
    """A release operation was invalid, unsafe, or unverifiable."""


@dataclass(frozen=True)
class FileBlob:
    """One frozen regular file read through a pinned descriptor."""

    path: str
    data: bytes
    sha256: str
    size: int
    executable: bool


@dataclass(frozen=True)
class OwnedOutput:
    """A newly created output directory that can be cleaned up by identity."""

    path: Path
    device: int
    inode: int
    descriptor: int
    parent_descriptor: int


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _packager_sha256() -> str:
    data = _read_regular_path(
        Path(__file__),
        label="trusted release packager",
        maximum_bytes=MAX_MANIFEST_BYTES,
    )
    return _sha256_bytes(data)


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _require_schema_version(value: object, *, field: str) -> None:
    """Require the exact integer schema version; JSON booleans are not integers."""

    if type(value) is not int or value != SCHEMA_VERSION:
        raise ReleaseError(f"unsupported {field} schema version")


def _normalized_path(value: Path | str) -> Path:
    try:
        return Path(os.path.abspath(os.fspath(Path(value).expanduser())))
    except (OSError, RuntimeError, TypeError, ValueError) as error:
        raise ReleaseError(f"invalid local path: {error}") from error


def _casefold_parts(path: Path) -> tuple[str, ...]:
    return tuple(unicodedata.normalize("NFC", part).casefold() for part in path.parts)


def _is_within(child: Path, parent: Path) -> bool:
    child_parts = _casefold_parts(child)
    parent_parts = _casefold_parts(parent)
    return (
        len(child_parts) >= len(parent_parts)
        and child_parts[: len(parent_parts)] == parent_parts
    )


def _has_isolated_component(path: Path | PurePosixPath) -> bool:
    isolated = ISOLATED_DIRECTORY_NAME.casefold()
    return any(part.casefold() == isolated for part in path.parts)


def _directory_open_flags() -> int:
    return os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)


def _file_open_flags() -> int:
    return os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)


def _open_directory_chain(path: Path) -> int:
    if not path.is_absolute():
        raise ReleaseError("internal path error: expected an absolute directory")
    try:
        descriptor = os.open(path.anchor, _directory_open_flags())
    except OSError as error:
        raise ReleaseError(f"could not open directory root safely: {error}") from error
    try:
        for component in path.parts[1:]:
            next_descriptor = os.open(
                component, _directory_open_flags(), dir_fd=descriptor
            )
            os.close(descriptor)
            descriptor = next_descriptor
        metadata = os.fstat(descriptor)
        if not stat.S_ISDIR(metadata.st_mode):
            raise ReleaseError(f"not a real directory: {path}")
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _validate_relative_path(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ReleaseError(f"{field} must be a non-empty POSIX relative path")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ReleaseError(f"{field} contains invalid Unicode") from error
    if value != unicodedata.normalize("NFC", value):
        raise ReleaseError(f"{field} must use NFC-normalized Unicode")
    if value.casefold().startswith("replace:") or "{{" in value or "}}" in value:
        raise ReleaseError(f"{field} still contains a template placeholder")
    if "\\" in value or "\n" in value or "\r" in value or "\x00" in value:
        raise ReleaseError(f"{field} contains an unsafe path character")
    relative = PurePosixPath(value)
    if (
        relative.is_absolute()
        or not relative.parts
        or any(part in {"", ".", ".."} for part in relative.parts)
        or _has_isolated_component(relative)
    ):
        raise ReleaseError(f"{field} must stay inside its package root")
    normalized = relative.as_posix()
    if normalized != value:
        raise ReleaseError(f"{field} must be a normalized POSIX relative path")
    return normalized


def _validate_text(
    value: object, *, field: str, maximum: int = 20_000
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReleaseError(f"{field} must be non-empty text")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ReleaseError(f"{field} contains invalid Unicode") from error
    if value != value.strip():
        raise ReleaseError(f"{field} must not have leading or trailing whitespace")
    if value != unicodedata.normalize("NFC", value):
        raise ReleaseError(f"{field} must use NFC-normalized Unicode")
    if len(value) > maximum:
        raise ReleaseError(f"{field} is too long")
    if value.casefold().startswith("replace:") or "{{" in value or "}}" in value:
        raise ReleaseError(f"{field} still contains a template placeholder")
    forbidden_controls = {
        "\x00",
        "\x1b",
        "\u202a",
        "\u202b",
        "\u202d",
        "\u202e",
        "\u2066",
        "\u2067",
        "\u2068",
        "\u2069",
    }
    if any(character in value for character in forbidden_controls):
        raise ReleaseError(f"{field} contains unsupported control characters")
    return value


def _validate_id(value: object, *, field: str) -> str:
    text = _validate_text(value, field=field, maximum=200)
    if text.casefold().startswith(("replace-", "your-")):
        raise ReleaseError(f"{field} still contains a template placeholder")
    if not ID_PATTERN.fullmatch(text):
        raise ReleaseError(f"{field} is not a valid stable identifier")
    return text


def _validate_timestamp(value: object, *, field: str) -> str:
    text = _validate_text(value, field=field, maximum=100)
    if text == "1970-01-01T00:00:00Z":
        raise ReleaseError(f"{field} still contains a template timestamp")
    if not UTC_TIMESTAMP_PATTERN.fullmatch(text):
        raise ReleaseError(f"{field} must be a UTC RFC3339 timestamp")
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as error:
        raise ReleaseError(f"{field} must be a UTC RFC3339 timestamp") from error
    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ReleaseError(f"{field} must use UTC")
    return text


def _expect_exact_keys(
    value: object, expected: set[str], *, field: str
) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ReleaseError(f"{field} must be an object")
    try:
        actual = set(value)
    except TypeError as error:
        raise ReleaseError(f"{field} contains an invalid key") from error
    missing = expected - actual
    extra = actual - expected
    if missing:
        raise ReleaseError(f"{field} is missing fields: {sorted(missing)}")
    if extra:
        raise ReleaseError(f"{field} has unexpected fields: {sorted(extra)}")
    return value


def _expect_text_list(
    value: object, *, field: str, allow_empty: bool = False
) -> list[str]:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise ReleaseError(f"{field} must be a non-empty list of text")
    result = [
        _validate_text(item, field=f"{field}[{index}]")
        for index, item in enumerate(value)
    ]
    if len(set(result)) != len(result):
        raise ReleaseError(f"{field} contains duplicate values")
    return result


def _strict_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ReleaseError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ReleaseError(f"non-finite JSON value is not allowed: {value}")


def _reject_float(value: str) -> None:
    raise ReleaseError(f"floating-point JSON value is not allowed: {value}")


def _reject_excessive_json_nesting(text: str) -> None:
    depth = 0
    in_string = False
    escaped = False
    for character in text:
        if in_string:
            if escaped:
                escaped = False
            elif ord(character) == 92:
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character in "[{":
            depth += 1
            if depth > MAX_JSON_NESTING:
                raise ReleaseError(
                    f"invalid JSON: nesting exceeds {MAX_JSON_NESTING} levels"
                )
        elif character in "]}":
            depth = max(0, depth - 1)


def _strict_json_bytes(
    data: bytes, *, field: str, maximum_bytes: int = MAX_MANIFEST_BYTES
) -> dict[str, object]:
    if len(data) > maximum_bytes:
        raise ReleaseError(f"{field} exceeds the {maximum_bytes}-byte limit")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ReleaseError(f"{field} must be valid UTF-8 JSON") from error
    try:
        _reject_excessive_json_nesting(text)
        value = json.loads(
            text,
            object_pairs_hook=_strict_object,
            parse_constant=_reject_constant,
            parse_float=_reject_float,
        )
    except ReleaseError:
        raise
    except (json.JSONDecodeError, UnicodeError, RecursionError, ValueError) as error:
        raise ReleaseError(f"invalid {field}: {error}") from error
    if not isinstance(value, dict):
        raise ReleaseError(f"{field} must contain one JSON object")
    return value


def _read_regular_file_at(
    directory_descriptor: int,
    name: str,
    *,
    label: str,
    maximum_bytes: int,
    expected: os.stat_result | None = None,
) -> bytes:
    descriptor: int | None = None
    try:
        descriptor = os.open(name, _file_open_flags(), dir_fd=directory_descriptor)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ReleaseError(f"{label} must be a regular file")
        if expected is not None and (
            before.st_dev,
            before.st_ino,
            before.st_size,
            stat.S_IMODE(before.st_mode),
        ) != (
            expected.st_dev,
            expected.st_ino,
            expected.st_size,
            stat.S_IMODE(expected.st_mode),
        ):
            raise ReleaseError(f"{label} changed while the source tree was frozen")
        if before.st_size > maximum_bytes:
            raise ReleaseError(f"{label} exceeds the {maximum_bytes}-byte limit")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(65_536, maximum_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > maximum_bytes:
                raise ReleaseError(f"{label} exceeds the {maximum_bytes}-byte limit")
        after = os.fstat(descriptor)
        if (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            stat.S_IMODE(before.st_mode),
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            stat.S_IMODE(after.st_mode),
        ):
            raise ReleaseError(f"{label} changed while it was being read")
        return b"".join(chunks)
    except ReleaseError:
        raise
    except OSError as error:
        raise ReleaseError(f"could not read {label} safely: {error}") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _read_regular_path(
    path_value: Path | str, *, label: str, maximum_bytes: int
) -> bytes:
    path = _normalized_path(path_value)
    if _has_isolated_component(path):
        raise ReleaseError(f"refusing to read protected instructor material as {label}")
    try:
        if path.is_symlink():
            raise ReleaseError(f"{label} must not be a symlink")
        canonical = path.resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as error:
        raise ReleaseError(f"could not resolve {label}: {error}") from error
    if _has_isolated_component(canonical):
        raise ReleaseError(f"refusing to read protected instructor material as {label}")
    parent_descriptor = _open_directory_chain(canonical.parent)
    try:
        return _read_regular_file_at(
            parent_descriptor,
            canonical.name,
            label=label,
            maximum_bytes=maximum_bytes,
        )
    finally:
        os.close(parent_descriptor)


def _collect_directory(
    root_value: Path | str,
    *,
    label: str,
    skip_names: set[str] | None = None,
    reject_isolated: bool = True,
    maximum_files: int = MAX_FILES,
    maximum_total_bytes: int = MAX_TOTAL_BYTES,
) -> tuple[dict[str, FileBlob], list[str]]:
    """Freeze a regular-file tree without following any source symlink."""

    root = _normalized_path(root_value)
    if _has_isolated_component(root) and reject_isolated:
        raise ReleaseError(f"{label} cannot use protected instructor material")
    try:
        if root.is_symlink():
            raise ReleaseError(f"{label} must be a real directory, not a symlink")
        canonical = root.resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as error:
        raise ReleaseError(f"could not resolve {label}: {error}") from error
    if _has_isolated_component(canonical) and reject_isolated:
        raise ReleaseError(f"{label} cannot use protected instructor material")
    if not canonical.is_dir():
        raise ReleaseError(f"{label} must be a directory")
    root_descriptor = _open_directory_chain(canonical)
    skipped: list[str] = []
    files: dict[str, FileBlob] = {}
    collision_keys: dict[str, str] = {}
    total_bytes = 0
    normalized_skips = {name.casefold() for name in (skip_names or set())}

    def walk(directory_descriptor: int, prefix: tuple[str, ...]) -> None:
        nonlocal total_bytes
        try:
            names = sorted(os.listdir(directory_descriptor))
        except OSError as error:
            raise ReleaseError(f"could not list {label} safely: {error}") from error
        local_names: dict[str, str] = {}
        for name in names:
            if name != unicodedata.normalize("NFC", name):
                raise ReleaseError(f"{label} contains a non-NFC path name")
            folded_name = name.casefold()
            if folded_name in local_names:
                raise ReleaseError(
                    f"{label} has a case-insensitive path collision"
                )
            local_names[folded_name] = name
            relative_parts = prefix + (name,)
            relative = PurePosixPath(*relative_parts).as_posix()
            if folded_name in normalized_skips:
                skipped.append(relative)
                continue
            if name in {".", ".."} or "/" in name or "\\" in name:
                raise ReleaseError(f"{label} contains an unsafe path name")
            if reject_isolated and folded_name == ISOLATED_DIRECTORY_NAME.casefold():
                raise ReleaseError(f"{label} contains protected instructor material")
            collision_key = unicodedata.normalize("NFC", relative).casefold()
            if collision_key in collision_keys:
                raise ReleaseError(
                    f"{label} has a normalized path collision"
                )
            collision_keys[collision_key] = relative
            try:
                metadata = os.stat(
                    name,
                    dir_fd=directory_descriptor,
                    follow_symlinks=False,
                )
            except OSError as error:
                raise ReleaseError(f"could not inspect {label} safely: {error}") from error
            if stat.S_ISLNK(metadata.st_mode):
                raise ReleaseError(f"{label} contains a symlink: {relative}")
            if stat.S_ISDIR(metadata.st_mode):
                child_descriptor = os.open(
                    name, _directory_open_flags(), dir_fd=directory_descriptor
                )
                try:
                    walk(child_descriptor, relative_parts)
                finally:
                    os.close(child_descriptor)
                continue
            if not stat.S_ISREG(metadata.st_mode):
                raise ReleaseError(
                    f"{label} contains a non-regular filesystem object: {relative}"
                )
            if len(files) >= maximum_files:
                raise ReleaseError(f"{label} exceeds the {maximum_files}-file limit")
            data = _read_regular_file_at(
                directory_descriptor,
                name,
                label=f"{label} file {relative}",
                maximum_bytes=MAX_FILE_BYTES,
                expected=metadata,
            )
            total_bytes += len(data)
            if total_bytes > maximum_total_bytes:
                raise ReleaseError(
                    f"{label} exceeds the {maximum_total_bytes}-byte aggregate limit"
                )
            files[relative] = FileBlob(
                path=relative,
                data=data,
                sha256=_sha256_bytes(data),
                size=len(data),
                executable=bool(metadata.st_mode & 0o111),
            )

    try:
        walk(root_descriptor, ())
    except OSError as error:
        raise ReleaseError(f"could not traverse {label} safely: {error}") from error
    finally:
        os.close(root_descriptor)
    return files, skipped


def _file_records(files: dict[str, bytes]) -> list[dict[str, object]]:
    return [
        {
            "path": path,
            "sha256": _sha256_bytes(files[path]),
            "size": len(files[path]),
        }
        for path in sorted(files)
    ]


def _root_digest(records: Iterable[dict[str, object]]) -> str:
    normalized = []
    for record in records:
        normalized_record = {
            "path": record["path"],
            "sha256": record["sha256"],
            "size": record["size"],
        }
        if "executable" in record:
            normalized_record["executable"] = record["executable"]
        normalized.append(normalized_record)
    normalized.sort(key=lambda item: str(item["path"]))
    canonical = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return _sha256_bytes(canonical)


def _checksums(files: dict[str, bytes]) -> bytes:
    return "".join(
        f"{_sha256_bytes(files[path])}  {path}\n" for path in sorted(files)
    ).encode("utf-8")


def _standalone_verifier() -> bytes:
    return b'''#!/usr/bin/env python3
"""Verify this one package without reading any sibling package."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import unicodedata

ROOT = Path(__file__).resolve().parent
LINE = re.compile(r"^([0-9a-f]{64})  (.+)$")
HEX = re.compile(r"^[0-9a-f]{64}$")
ZERO = "0" * 64
GIT_REVISION = re.compile(r"^[0-9a-f]{40,64}$")
UTC_TIMESTAMP = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:[.][0-9]+)?Z$"
)
ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$")
SEMVER = re.compile(
    r"^(?:0|[1-9][0-9]*)[.](?:0|[1-9][0-9]*)[.](?:0|[1-9][0-9]*)"
    r"(?:-(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:[.](?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*))*)?"
    r"(?:[+][0-9A-Za-z-]+(?:[.][0-9A-Za-z-]+)*)?$"
)
OPEN_KEYS = {
    "schema_version", "manifest_type", "release_mode", "release_state",
    "exposure_state", "case_id", "case_version", "source_revision",
    "source_revision_scope", "repository_worktree_state", "source_tree_sha256",
    "created_at", "declared_actor", "actor_authentication", "files", "licenses",
    "known_limitations", "claims_not_made", "scientific_correctness",
    "measurement_validity", "validation_record", "revocation_template",
}
ROLE_COMMON_KEYS = {
    "schema_version", "manifest_type", "package_role", "distribution_state",
    "release_id", "case_id", "case_version", "created_at", "files",
    "source_inventory", "licenses", "boundary", "claims_not_made",
    "scientific_correctness",
}
ROLE_EXTRA_KEYS = {
    "challenge": {"scoring_reference"},
    "evaluator": {"source_manifest_sha256", "challenge_manifest_sha256", "scoring_reference"},
    "maintainer": {"source_manifest_sha256", "challenge_manifest_sha256", "evaluator_manifest_sha256"},
}
ROLE_GENERATED = {
    "challenge": {"RELEASE_BOUNDARY.md", "verify_package.py", "LEAKAGE_SCAN.json", "PACKAGE_MANIFEST.json"},
    "evaluator": {"RELEASE_BOUNDARY.md", "verify_package.py", "PACKAGE_MANIFEST.json"},
    "maintainer": {"RELEASE_BOUNDARY.md", "verify_package.py", "BLIND_SOURCE.json", "REVOCATION_NOTICE_TEMPLATE.md", "ACCESS_LOG_TEMPLATE.md", "PACKAGE_MANIFEST.json"},
}
OPEN_NON_SOURCE = {
    "LICENSE",
    "DOCUMENTATION_LICENSE.md",
    "THIRD_PARTY_NOTICES.md",
    "docs/CASE_RELEASE_MODEL.md",
    "docs/CASE_RELEASE_MODEL_EN.md",
    "RELEASE_BOUNDARY.md",
    "VALIDATION_RECORD.json",
    "REVOCATION_NOTICE_TEMPLATE.md",
    "verify_package.py",
    "PACKAGE_MANIFEST.json",
}
MAX_JSON_BYTES = 2_000_000
MAX_FILE_BYTES = 32_000_000
MAX_PACKAGE_FILES = 10_032
MAX_PACKAGE_TOTAL_BYTES = 320_000_000
ISOLATED_NAME = "do_not_open_until_finished"
TEXT_SUFFIXES = {
    ".c", ".cc", ".cfg", ".conf", ".cpp", ".css", ".csv", ".h", ".hpp",
    ".html", ".ini", ".ipynb", ".java", ".jl", ".js", ".json", ".jsonl",
    ".md", ".m", ".py", ".r", ".rs", ".rst", ".sh", ".sql", ".tex",
    ".toml", ".ts", ".tsx", ".txt", ".xml", ".yaml", ".yml",
}
TEXT_NAMES = {"dockerfile", "makefile", "procfile", "rakefile"}
FORBIDDEN_PATH_NAMES = {
    ".git", ".hg", ".svn", ".env", "credentials", "credentials.json",
    "id_ed25519", "id_rsa",
}
FORBIDDEN_SECRET_SUFFIXES = {".key", ".p12", ".pem", ".pfx"}
FORBIDDEN_PATH = re.compile(
    r"(?:^|[-_.])(?:answers?|answer[-_]?(?:map|manifest|key)|solutions?|"
    r"private[-_]?(?:probes?)|hidden[-_]?(?:probes?)|grader|"
    r"evaluation[-_]?(?:labels?)|mutation[-_]?(?:ledger)|evaluator|maintainer)"
    r"(?:$|[-_.])", re.IGNORECASE
)
FORBIDDEN_TEXT = re.compile(
    r"\\b(?:trusted[\\s_-]+candidate|correct[\\s_-]+candidate|"
    r"expected[\\s_-]+answer|answer[\\s_-]+mapping|answer[\\s_-]+manifest|"
    r"private[\\s_-]+probe|hidden[\\s_-]+probe|evaluation[\\s_-]+label|"
    r"mutation[\\s_-]+ledger|repair[\\s_-]+span|hidden[\\s_-]+rule[\\s_-]+id)"
    r"\\b[\\"']?\\s*(?:\\])?\\s*(?:=|:|\\bis\\b)", re.IGNORECASE
)
FORBIDDEN_IMPORT = re.compile(
    r"(?:^|\\n)\\s*(?:from|import)\\s+(?:evaluator|maintainer)(?:\\b|\\.)|"
    r"(?:\\.\\./)+(?:evaluator|maintainer)(?:/|\\\\)", re.IGNORECASE
)
LEAKAGE_LIMIT = (
    "A passing pattern scan is not proof that no answer signal, private data, "
    "or unfair cue remains. An isolated Challenge verifier cannot know private "
    "values such as the scoring digest; trusted staging verification and "
    "independent human review are still required."
)

def fail(message):
    print(f"PACKAGE INTEGRITY: FAIL ({message})", file=sys.stderr)
    return 1

def walk_error(error):
    raise error

def safe_relative(value):
    if not isinstance(value, str):
        return False
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    if (value != unicodedata.normalize("NFC", value) or
            value.casefold().startswith("replace:") or
            "{{" in value or "}}" in value or
            "\\\\" in value or "\\n" in value or "\\r" in value or
            any(ord(character) == 0 for character in value)):
        return False
    path = PurePosixPath(value)
    return (bool(path.parts) and not path.is_absolute() and
            all(p not in {"", ".", ".."} and p.casefold() != ISOLATED_NAME for p in path.parts))

def text(value, maximum=20_000):
    if not isinstance(value, str) or not value or value != value.strip():
        return False
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    if (value != unicodedata.normalize("NFC", value) or len(value) > maximum or
            value.casefold().startswith("replace:") or
            "{{" in value or "}}" in value):
        return False
    forbidden = {0, 27, 0x202A, 0x202B, 0x202D, 0x202E, 0x2066, 0x2067, 0x2068, 0x2069}
    return not any(ord(character) in forbidden for character in value)

def stable_id(value):
    return (text(value, 200) and
            not value.casefold().startswith(("replace-", "your-")) and
            bool(ID.fullmatch(value)))

def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result

def strict_json(path):
    data = path.read_bytes()
    if len(data) > MAX_JSON_BYTES:
        raise ValueError("JSON file too large")
    source = data.decode("utf-8")
    depth = 0
    in_string = False
    escaped = False
    for character in source:
        if in_string:
            if escaped:
                escaped = False
            elif ord(character) == 92:
                escaped = True
            elif character == '"':
                in_string = False
        elif character == '"':
            in_string = True
        elif character in "[{":
            depth += 1
            if depth > 100:
                raise ValueError("JSON nesting too deep")
        elif character in "]}":
            depth = max(0, depth - 1)
    value = json.loads(
        source,
        object_pairs_hook=strict_object,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError("non-finite JSON")),
        parse_float=lambda value: (_ for _ in ()).throw(ValueError("floating-point JSON")),
    )
    if not isinstance(value, dict):
        raise ValueError("JSON root must be an object")
    return value

def utc_timestamp(value):
    if (not text(value, 100) or value == "1970-01-01T00:00:00Z" or
            not UTC_TIMESTAMP.fullmatch(value)):
        return False
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    return parsed.utcoffset() == timezone.utc.utcoffset(parsed)

def text_list(value):
    return isinstance(value, list) and bool(value) and all(text(item) for item in value) and len(set(value)) == len(value)

def tree_digest(records):
    encoded = json.dumps(
        sorted(records, key=lambda item: item["path"]),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

def main():
    checksum_path = ROOT / "CHECKSUMS.sha256"
    try:
        if checksum_path.is_symlink() or not checksum_path.is_file():
            return fail("missing checksum file")
        checksum_size = checksum_path.stat().st_size
        if checksum_size > MAX_FILE_BYTES:
            return fail("checksum file too large")
        expected = {}
        for raw in checksum_path.read_text(encoding="utf-8").splitlines():
            match = LINE.fullmatch(raw)
            if not match or not safe_relative(match.group(2)):
                return fail("malformed checksum record")
            key = unicodedata.normalize("NFC", match.group(2)).casefold()
            if key in expected:
                return fail("duplicate checksum path")
            expected[key] = (match.group(2), match.group(1))
        actual = {}
        file_count = 1
        total_bytes = checksum_size
        for base, directories, filenames in os.walk(
            ROOT, followlinks=False, onerror=walk_error
        ):
            base_path = Path(base)
            for name in list(directories):
                path = base_path / name
                if name != unicodedata.normalize("NFC", name):
                    return fail("non-NFC directory name")
                if name.casefold() == ISOLATED_NAME:
                    return fail("protected instructor-material directory")
                if path.is_symlink():
                    return fail("symlink directory")
            for name in filenames:
                path = base_path / name
                relative = path.relative_to(ROOT).as_posix()
                if relative == "CHECKSUMS.sha256":
                    continue
                metadata = path.lstat()
                if not stat.S_ISREG(metadata.st_mode) or path.is_symlink():
                    return fail("non-regular file")
                file_count += 1
                total_bytes += metadata.st_size
                if metadata.st_size > MAX_FILE_BYTES:
                    return fail("package file too large")
                if file_count > MAX_PACKAGE_FILES or total_bytes > MAX_PACKAGE_TOTAL_BYTES:
                    return fail("package capacity exceeded")
                key = unicodedata.normalize("NFC", relative).casefold()
                if key in actual:
                    return fail("path collision")
                actual[key] = relative
        if set(actual) != set(expected):
            return fail("file set differs from checksums")
        for key, relative in actual.items():
            if expected[key][0] != relative:
                return fail("checksum path case differs from retained path")
            digest = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
            if digest != expected[key][1]:
                return fail("digest mismatch")
        manifest = strict_json(ROOT / "PACKAGE_MANIFEST.json")
        if manifest.get("scientific_correctness") != "not_assessed":
            return fail("invalid trust boundary")
        manifest_type = manifest.get("manifest_type")
        if manifest_type == "rcsl-open-demo-package":
            required_open = {
                "release_boundary.md",
                "validation_record.json",
                "revocation_notice_template.md",
                "verify_package.py",
                "package_manifest.json",
            }
            if not required_open.issubset(actual):
                return fail("missing Open Demo boundary artifact")
            source_prefix = "llm4sbr_research_audit_training_v2/"
            non_source = {
                key for key in actual if not key.startswith(source_prefix)
            }
            expected_non_source = {
                path.casefold(): path for path in OPEN_NON_SOURCE
            }
            if (
                non_source != set(expected_non_source)
                or any(actual[key] != expected_non_source[key] for key in non_source)
                or not any(
                key.startswith(source_prefix) for key in actual
                )
            ):
                return fail("unbound Open Demo non-source file")
            if (set(manifest) != OPEN_KEYS or type(manifest.get("schema_version")) is not int or
                    manifest.get("schema_version") != 1 or
                    manifest.get("release_mode") != "open-demo" or
                    manifest.get("release_state") != "open-demo-artifact" or
                    manifest.get("exposure_state") != "historically-public-honor-isolation" or
                    manifest.get("source_revision_scope") != "repository-head-not-byte-identity" or
                    not isinstance(manifest.get("repository_worktree_state"), str) or
                    manifest.get("repository_worktree_state") not in {"clean", "dirty"} or
                    manifest.get("actor_authentication") != "not_performed" or
                    manifest.get("measurement_validity") != "not_assessed" or
                    manifest.get("validation_record") != "VALIDATION_RECORD.json" or
                    manifest.get("revocation_template") != "REVOCATION_NOTICE_TEMPLATE.md" or
                    not isinstance(manifest.get("source_revision"), str) or
                    not GIT_REVISION.fullmatch(manifest["source_revision"]) or
                    not isinstance(manifest.get("source_tree_sha256"), str) or
                    not HEX.fullmatch(manifest["source_tree_sha256"]) or
                    not stable_id(manifest.get("case_id")) or
                    not isinstance(manifest.get("case_version"), str) or
                    len(manifest["case_version"]) > 100 or
                    not SEMVER.fullmatch(manifest["case_version"]) or
                    not utc_timestamp(manifest.get("created_at")) or
                    not text(manifest.get("declared_actor")) or
                    not text_list(manifest.get("known_limitations")) or
                    not text_list(manifest.get("claims_not_made")) or
                    not any("unseen" in item.casefold() for item in manifest["claims_not_made"])):
                return fail("invalid Open Demo boundary")
            licenses = manifest.get("licenses")
            if not isinstance(licenses, list) or not licenses:
                return fail("invalid Open Demo licenses")
            for license_record in licenses:
                if (not isinstance(license_record, dict) or
                        set(license_record) != {"scope", "terms", "notice"} or
                        not text(license_record.get("scope")) or
                        not text(license_record.get("terms")) or
                        not isinstance(license_record.get("notice"), str) or
                        not safe_relative(license_record["notice"]) or
                        unicodedata.normalize("NFC", license_record["notice"]).casefold() not in actual or
                        actual[unicodedata.normalize("NFC", license_record["notice"]).casefold()] != license_record["notice"]):
                    return fail("invalid Open Demo license record")
            try:
                validation = strict_json(ROOT / manifest["validation_record"])
            except (OSError, UnicodeError, ValueError, TypeError):
                return fail("invalid Open Demo validation record")
            if (not isinstance(validation, dict) or
                    set(validation) != {"schema_version", "record_type", "validated_source_tree_sha256", "environment", "records", "scientific_correctness", "measurement_validity"} or
                    type(validation.get("schema_version")) is not int or
                    validation.get("schema_version") != 1 or
                    validation.get("record_type") != "rcsl-open-demo-validation" or
                    validation.get("validated_source_tree_sha256") != manifest["source_tree_sha256"] or
                    validation.get("scientific_correctness") != "not_assessed" or
                    validation.get("measurement_validity") != "not_assessed"):
                return fail("invalid Open Demo validation binding")
            environment = validation.get("environment")
            if (not isinstance(environment, dict) or
                    set(environment) != {"python", "platform"} or
                    not text(environment.get("python")) or
                    not text(environment.get("platform"))):
                return fail("invalid Open Demo validation environment")
            validation_records = validation.get("records")
            expected_names = ("static-public-surface", "level-1-through-4-public-checks")
            record_keys = {"name", "command", "started_at", "outcome", "exit_code", "stdout_sha256", "stderr_sha256", "scope"}
            if not isinstance(validation_records, list) or len(validation_records) != 2:
                return fail("invalid Open Demo validation records")
            for index, validation_record in enumerate(validation_records):
                if (not isinstance(validation_record, dict) or
                        set(validation_record) != record_keys or
                        validation_record.get("name") != expected_names[index] or
                        not text(validation_record.get("command")) or
                        not text(validation_record.get("scope"))):
                    return fail("invalid Open Demo validation record")
                outcome = validation_record.get("outcome")
                if (not isinstance(outcome, str) or
                        (index == 0 and outcome != "passed") or
                        (index == 1 and outcome not in {"passed", "not-run"})):
                    return fail("invalid Open Demo validation outcome")
                if outcome == "passed":
                    if (not utc_timestamp(validation_record.get("started_at")) or
                            type(validation_record.get("exit_code")) is not int or validation_record["exit_code"] != 0 or
                            not isinstance(validation_record.get("stdout_sha256"), str) or not HEX.fullmatch(validation_record["stdout_sha256"]) or
                            not isinstance(validation_record.get("stderr_sha256"), str) or not HEX.fullmatch(validation_record["stderr_sha256"])):
                        return fail("invalid passing validation evidence")
                elif any(validation_record.get(field) is not None for field in ("started_at", "exit_code", "stdout_sha256", "stderr_sha256")):
                    return fail("invented not-run validation evidence")
        elif manifest_type == "rcsl-role-package":
            role = manifest.get("package_role")
            expected_distribution = "learner-facing-candidate" if role == "challenge" else "controlled-candidate"
            if (not isinstance(role, str) or role not in ROLE_EXTRA_KEYS or
                    set(manifest) != ROLE_COMMON_KEYS | ROLE_EXTRA_KEYS[role] or
                    type(manifest.get("schema_version")) is not int or manifest.get("schema_version") != 1 or
                    manifest.get("distribution_state") != expected_distribution or
                    manifest.get("boundary") != "assembled-awaiting-controlled-placement" or
                    not stable_id(manifest.get("release_id")) or
                    not stable_id(manifest.get("case_id")) or
                    not isinstance(manifest.get("case_version"), str) or len(manifest["case_version"]) > 100 or not SEMVER.fullmatch(manifest["case_version"]) or
                    not utc_timestamp(manifest.get("created_at")) or
                    not text_list(manifest.get("claims_not_made"))):
                return fail("invalid role-package boundary")
            for digest_field in ("source_manifest_sha256", "challenge_manifest_sha256", "evaluator_manifest_sha256"):
                if digest_field in manifest and (not isinstance(manifest[digest_field], str) or not HEX.fullmatch(manifest[digest_field]) or manifest[digest_field] == ZERO):
                    return fail("invalid controlled binding")
            scoring = manifest.get("scoring_reference")
            if role == "challenge":
                if (not isinstance(scoring, dict) or set(scoring) != {"protocol_id", "version"} or
                        not stable_id(scoring.get("protocol_id")) or
                        not isinstance(scoring.get("version"), str) or len(scoring["version"]) > 100 or not SEMVER.fullmatch(scoring["version"])):
                    return fail("invalid challenge scoring reference")
            elif role == "evaluator":
                scoring_keys = {"protocol_id", "version", "digest", "automatic_scope", "human_gate", "independent_reviewer_ref"}
                if (not isinstance(scoring, dict) or set(scoring) != scoring_keys or
                        not stable_id(scoring.get("protocol_id")) or
                        not isinstance(scoring.get("version"), str) or len(scoring["version"]) > 100 or not SEMVER.fullmatch(scoring["version"]) or
                        not isinstance(scoring.get("digest"), str) or not HEX.fullmatch(scoring["digest"]) or scoring["digest"] == ZERO or
                        not all(text(scoring.get(key)) for key in ("automatic_scope", "human_gate", "independent_reviewer_ref"))):
                    return fail("invalid evaluator scoring reference")
        else:
            return fail("unsupported manifest type")
        records = manifest.get("files")
        if not isinstance(records, list):
            return fail("invalid manifest file inventory")
        recorded = {}
        for record in records:
            if not isinstance(record, dict) or set(record) != {"path", "sha256", "size"}:
                return fail("invalid manifest file record")
            relative = record.get("path")
            digest = record.get("sha256")
            size = record.get("size")
            if (not isinstance(relative, str) or not safe_relative(relative) or
                    not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest) or
                    isinstance(size, bool) or not isinstance(size, int) or size < 0):
                return fail("invalid manifest file record")
            key = unicodedata.normalize("NFC", relative).casefold()
            if key in recorded:
                return fail("duplicate manifest path")
            recorded[key] = (relative, digest, size)
        payload = set(actual) - {"package_manifest.json"}
        if set(recorded) != payload:
            return fail("manifest file set differs from payload")
        for key, (relative, digest, size) in recorded.items():
            if actual[key] != relative:
                return fail("manifest path case differs from retained path")
            path = ROOT / actual[key]
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest or path.stat().st_size != size:
                return fail("manifest file record mismatch")
        if manifest_type == "rcsl-open-demo-package":
            prefix = "LLM4SBR_research_audit_training_v2/"
            source_records = [
                {
                    "path": relative[len(prefix):],
                    "sha256": digest,
                    "size": size,
                    "executable": bool(
                        (
                            ROOT
                            / actual[
                                unicodedata.normalize("NFC", relative).casefold()
                            ]
                        ).stat().st_mode
                        & 0o111
                    ),
                }
                for relative, digest, size in recorded.values()
                if relative.startswith(prefix)
            ]
            if not source_records or tree_digest(source_records) != manifest["source_tree_sha256"]:
                return fail("Open Demo source tree digest mismatch")
        else:
            role = manifest["package_role"]
            sensitivity = {
                "challenge": "public",
                "evaluator": "controlled-evaluator",
                "maintainer": "controlled-maintainer",
            }[role]
            inventory = manifest.get("source_inventory")
            if not isinstance(inventory, list) or not inventory:
                return fail("invalid source inventory")
            inventory_paths = set()
            inventory_originals = set()
            used_licenses = set()
            for entry in inventory:
                if (not isinstance(entry, dict) or
                        set(entry) != {"path", "sha256", "size", "executable", "role", "license_id", "sensitivity"} or
                        not isinstance(entry.get("path"), str) or not safe_relative(entry["path"]) or
                        not isinstance(entry.get("sha256"), str) or not HEX.fullmatch(entry["sha256"]) or
                        isinstance(entry.get("size"), bool) or not isinstance(entry.get("size"), int) or entry["size"] < 0 or
                        not isinstance(entry.get("executable"), bool) or
                        entry.get("role") != role or entry.get("sensitivity") != sensitivity or
                        not stable_id(entry.get("license_id"))):
                    return fail("invalid source inventory record")
                key = unicodedata.normalize("NFC", entry["path"]).casefold()
                if key in inventory_paths or key not in recorded:
                    return fail("invalid source inventory path")
                inventory_paths.add(key)
                inventory_originals.add(entry["path"])
                used_licenses.add(entry["license_id"])
                relative, digest, size = recorded[key]
                executable = bool((ROOT / actual[key]).stat().st_mode & 0o111)
                if (relative != entry["path"] or digest != entry["sha256"] or
                        size != entry["size"] or executable != entry["executable"]):
                    return fail("source inventory record mismatch")
            generated_originals = ROLE_GENERATED[role]
            generated = {path.casefold() for path in generated_originals}
            if (not generated.issubset(actual) or
                    any(actual[path.casefold()] != path for path in generated_originals) or
                    set(actual) - generated != inventory_paths):
                return fail("role package contains an unbound payload file")
            licenses = manifest.get("licenses")
            if not isinstance(licenses, list) or not licenses:
                return fail("invalid role license inventory")
            license_ids = set()
            for license_record in licenses:
                if (not isinstance(license_record, dict) or
                        set(license_record) != {"id", "terms", "redistribution", "notice_path"} or
                        not stable_id(license_record.get("id")) or
                        not text(license_record.get("terms")) or
                        not isinstance(license_record.get("redistribution"), str) or
                        license_record.get("redistribution") not in {"allowed", "restricted", "review-required"} or
                        not isinstance(license_record.get("notice_path"), str) or not safe_relative(license_record["notice_path"]) or
                        license_record["notice_path"] not in inventory_originals or
                        (role == "challenge" and license_record["redistribution"] != "allowed")):
                    return fail("invalid role license record")
                if license_record["id"] in license_ids:
                    return fail("duplicate role license id")
                license_ids.add(license_record["id"])
            if license_ids != used_licenses:
                return fail("role license inventory mismatch")
            if role == "challenge":
                leakage_key = "leakage_scan.json"
                if leakage_key not in actual:
                    return fail("missing Challenge Package leakage record")
                leakage = strict_json(ROOT / actual[leakage_key])
                text_files = 0
                binary_files = 0
                for entry in inventory:
                    relative = PurePosixPath(entry["path"])
                    for part in relative.parts:
                        folded = part.casefold()
                        if (FORBIDDEN_PATH.search(part) or
                                folded in FORBIDDEN_PATH_NAMES or
                                PurePosixPath(part).suffix.casefold() in FORBIDDEN_SECRET_SUFFIXES):
                            return fail("Challenge Package failed bounded leakage path rule")
                    data = (ROOT / actual[unicodedata.normalize("NFC", entry["path"]).casefold()]).read_bytes()
                    declared_text = (
                        relative.suffix.casefold() in TEXT_SUFFIXES or
                        relative.name.casefold() in TEXT_NAMES
                    )
                    try:
                        source_text = data.decode("utf-8")
                    except UnicodeDecodeError:
                        if declared_text:
                            return fail("invalid UTF-8 in text-classified challenge file")
                        binary_files += 1
                        continue
                    text_files += 1
                    if FORBIDDEN_TEXT.search(source_text) or FORBIDDEN_IMPORT.search(source_text):
                        return fail("Challenge Package failed bounded leakage text rule")
                expected_leakage = {
                    "schema_version": 1,
                    "scan_type": "bounded-pattern-and-path-scan",
                    "status": "passed",
                    "text_files_scanned": text_files,
                    "binary_files_path_only": binary_files,
                    "known_limit": LEAKAGE_LIMIT,
                    "scientific_correctness": "not_assessed",
                }
                if (type(leakage.get("schema_version")) is not int or
                        type(leakage.get("text_files_scanned")) is not int or
                        type(leakage.get("binary_files_path_only")) is not int or
                        leakage != expected_leakage):
                    return fail("invalid Challenge Package leakage record")
    except (OSError, UnicodeError, ValueError, KeyError) as error:
        return fail(type(error).__name__)
    print("PACKAGE INTEGRITY: PASS")
    print("Checksums verify retained bytes only; they do not certify correctness or confidentiality.")
    print("This isolated verifier cannot test absence of unknown private values; run trusted staging verification before release.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
'''


def _finalize_package(
    files: dict[str, bytes], manifest: dict[str, object]
) -> tuple[dict[str, bytes], str, str]:
    for path in files:
        _validate_relative_path(path, field="generated package path")
        if path.casefold() in {"package_manifest.json", "checksums.sha256"}:
            raise ReleaseError(f"source collides with generated control file: {path}")
    manifest_bytes = _json_bytes(manifest)
    complete = dict(files)
    complete["PACKAGE_MANIFEST.json"] = manifest_bytes
    checksums = _checksums(complete)
    complete["CHECKSUMS.sha256"] = checksums
    return complete, _sha256_bytes(manifest_bytes), _sha256_bytes(checksums)


def _validate_new_output(output_value: Path | str) -> Path:
    output = _normalized_path(output_value)
    if _has_isolated_component(output):
        raise ReleaseError("release output cannot enter protected instructor material")
    if not output.name or output.name in {".", ".."}:
        raise ReleaseError("release output must name a new directory")
    try:
        parent = output.parent.resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as error:
        raise ReleaseError(f"release output parent is unavailable: {error}") from error
    if not parent.is_dir():
        raise ReleaseError("release output parent must be an existing directory")
    canonical_output = parent / output.name
    if _has_isolated_component(canonical_output):
        raise ReleaseError("release output cannot enter protected instructor material")
    if _is_within(canonical_output, REPOSITORY_ROOT.resolve()):
        raise ReleaseError("release outputs must stay outside the public RCSL repository")
    if os.path.lexists(canonical_output):
        raise ReleaseError(f"refusing to overwrite existing output: {canonical_output}")
    return canonical_output


def _create_owned_output(output: Path) -> OwnedOutput:
    parent_descriptor = _open_directory_chain(output.parent)
    descriptor: int | None = None
    created = False
    try:
        os.mkdir(output.name, 0o700, dir_fd=parent_descriptor)
        created = True
        metadata = os.stat(
            output.name, dir_fd=parent_descriptor, follow_symlinks=False
        )
        descriptor = os.open(
            output.name, _directory_open_flags(), dir_fd=parent_descriptor
        )
        opened = os.fstat(descriptor)
    except FileExistsError as error:
        os.close(parent_descriptor)
        raise ReleaseError(f"refusing to overwrite existing output: {output}") from error
    except (OSError, ReleaseError) as error:
        if descriptor is not None:
            os.close(descriptor)
        if created:
            try:
                os.rmdir(output.name, dir_fd=parent_descriptor)
            except OSError:
                pass
        os.close(parent_descriptor)
        raise ReleaseError(f"could not create release output: {error}") from error
    if not stat.S_ISDIR(metadata.st_mode):
        os.close(descriptor)
        os.close(parent_descriptor)
        raise ReleaseError("new release output is not a real directory")
    if (metadata.st_dev, metadata.st_ino) != (opened.st_dev, opened.st_ino):
        os.close(descriptor)
        os.close(parent_descriptor)
        raise ReleaseError("new release output identity changed during creation")
    return OwnedOutput(
        output,
        metadata.st_dev,
        metadata.st_ino,
        descriptor,
        parent_descriptor,
    )


def _assert_owned_output_identity(owned: OwnedOutput) -> None:
    try:
        current = owned.path.lstat()
        opened = os.fstat(owned.descriptor)
        parent_entry = os.stat(
            owned.path.name,
            dir_fd=owned.parent_descriptor,
            follow_symlinks=False,
        )
    except OSError as error:
        raise ReleaseError("release output identity is no longer available") from error
    if (
        not stat.S_ISDIR(current.st_mode)
        or owned.path.is_symlink()
        or (current.st_dev, current.st_ino) != (owned.device, owned.inode)
        or (opened.st_dev, opened.st_ino) != (owned.device, owned.inode)
        or (parent_entry.st_dev, parent_entry.st_ino)
        != (owned.device, owned.inode)
    ):
        raise ReleaseError("release output identity changed during assembly")


def _close_owned_output(owned: OwnedOutput) -> None:
    for descriptor in (owned.descriptor, owned.parent_descriptor):
        try:
            os.close(descriptor)
        except OSError:
            pass


def _cleanup_owned_output(owned: OwnedOutput) -> None:
    def clear(directory_descriptor: int) -> None:
        try:
            names = os.listdir(directory_descriptor)
        except OSError:
            return
        for name in names:
            try:
                metadata = os.stat(
                    name, dir_fd=directory_descriptor, follow_symlinks=False
                )
                if stat.S_ISDIR(metadata.st_mode):
                    child_descriptor = os.open(
                        name,
                        _directory_open_flags(),
                        dir_fd=directory_descriptor,
                    )
                    try:
                        clear(child_descriptor)
                    finally:
                        os.close(child_descriptor)
                    os.rmdir(name, dir_fd=directory_descriptor)
                else:
                    os.unlink(name, dir_fd=directory_descriptor)
            except OSError:
                continue

    try:
        opened = os.fstat(owned.descriptor)
    except OSError:
        return
    if (opened.st_dev, opened.st_ino) != (owned.device, owned.inode):
        return
    clear(owned.descriptor)
    try:
        current = os.stat(
            owned.path.name,
            dir_fd=owned.parent_descriptor,
            follow_symlinks=False,
        )
        if (
            stat.S_ISDIR(current.st_mode)
            and (current.st_dev, current.st_ino) == (owned.device, owned.inode)
        ):
            os.rmdir(owned.path.name, dir_fd=owned.parent_descriptor)
    except OSError:
        pass


def _write_file(path: Path, data: bytes, *, executable: bool = False) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor: int | None = None
    try:
        descriptor = os.open(
            path,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0),
            0o700 if executable else 0o600,
        )
        handle = os.fdopen(descriptor, "wb")
        descriptor = None
        with handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as error:
        raise ReleaseError(f"refusing to overwrite package file: {path.name}") from error
    except OSError as error:
        raise ReleaseError(f"could not write package file safely: {error}") from error
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass


def _open_or_create_directory_at(parent_descriptor: int, name: str) -> int:
    try:
        os.mkdir(name, 0o700, dir_fd=parent_descriptor)
    except FileExistsError:
        pass
    try:
        descriptor = os.open(name, _directory_open_flags(), dir_fd=parent_descriptor)
        metadata = os.fstat(descriptor)
    except OSError as error:
        raise ReleaseError(f"could not create package directory safely: {error}") from error
    if not stat.S_ISDIR(metadata.st_mode):
        os.close(descriptor)
        raise ReleaseError("package path component is not a real directory")
    return descriptor


def _write_file_at(
    root_descriptor: int,
    relative: str,
    data: bytes,
    *,
    executable: bool = False,
) -> None:
    safe = _validate_relative_path(relative, field="output file path")
    parts = PurePosixPath(safe).parts
    parent_descriptor = os.dup(root_descriptor)
    descriptor: int | None = None
    try:
        for component in parts[:-1]:
            child_descriptor = _open_or_create_directory_at(
                parent_descriptor, component
            )
            os.close(parent_descriptor)
            parent_descriptor = child_descriptor
        descriptor = os.open(
            parts[-1],
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0),
            0o700 if executable else 0o600,
            dir_fd=parent_descriptor,
        )
        handle = os.fdopen(descriptor, "wb")
        descriptor = None
        with handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as error:
        raise ReleaseError(f"refusing to overwrite package file: {safe}") from error
    except OSError as error:
        raise ReleaseError(f"could not write package file safely: {error}") from error
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        os.close(parent_descriptor)


def _write_tree_at(
    root_descriptor: int,
    files: dict[str, bytes],
    *,
    executable_paths: set[str] | None = None,
) -> None:
    collision_keys: set[str] = set()
    executable_paths = executable_paths or set()
    for relative in sorted(files):
        safe = _validate_relative_path(relative, field="output file path")
        key = safe.casefold()
        if key in collision_keys:
            raise ReleaseError("generated output contains a case-insensitive collision")
        collision_keys.add(key)
        _write_file_at(
            root_descriptor,
            safe,
            files[relative],
            executable=safe == "verify_package.py" or safe in executable_paths,
        )


def _write_tree(
    root: Path,
    files: dict[str, bytes],
    *,
    executable_paths: set[str] | None = None,
) -> None:
    collision_keys: set[str] = set()
    executable_paths = executable_paths or set()
    for relative in sorted(files):
        safe = _validate_relative_path(relative, field="output file path")
        key = safe.casefold()
        if key in collision_keys:
            raise ReleaseError("generated output contains a case-insensitive collision")
        collision_keys.add(key)
        _write_file(
            root / Path(*PurePosixPath(safe).parts),
            files[relative],
            executable=safe == "verify_package.py" or safe in executable_paths,
        )


def _read_public_asset(path: Path, *, label: str) -> bytes:
    if not _is_within(path.resolve(), REPOSITORY_ROOT.resolve()):
        raise ReleaseError(f"{label} escaped the RCSL repository")
    return _read_regular_path(path, label=label, maximum_bytes=MAX_FILE_BYTES)


def _git_revision() -> str:
    result = subprocess.run(
        ("git", "-C", str(REPOSITORY_ROOT), "rev-parse", "HEAD"),
        capture_output=True,
        text=True,
        check=False,
    )
    revision = result.stdout.strip()
    if result.returncode != 0 or not GIT_REVISION.fullmatch(revision):
        raise ReleaseError("could not resolve the RCSL source revision")
    return revision


def _git_worktree_state() -> str:
    result = subprocess.run(
        (
            "git",
            "-C",
            str(REPOSITORY_ROOT),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ),
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise ReleaseError("could not determine the RCSL worktree state")
    return "clean" if not result.stdout.strip() else "dirty"


def _command_record(
    *, name: str, argv: list[str], display_command: str, scope: str
) -> dict[str, object]:
    started = _utc_now()
    try:
        result = subprocess.run(
            argv,
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            check=False,
            timeout=180,
        )
        return {
            "name": name,
            "command": display_command,
            "started_at": started,
            "outcome": "passed" if result.returncode == 0 else "failed",
            "exit_code": result.returncode,
            "stdout_sha256": _sha256_bytes(result.stdout),
            "stderr_sha256": _sha256_bytes(result.stderr),
            "scope": scope,
        }
    except (OSError, subprocess.TimeoutExpired) as error:
        return {
            "name": name,
            "command": display_command,
            "started_at": started,
            "outcome": "failed-to-run",
            "exit_code": None,
            "stdout_sha256": None,
            "stderr_sha256": None,
            "scope": scope,
            "error_type": type(error).__name__,
        }


def _open_demo_validation(
    snapshot: Path,
    *,
    run_public_checks: bool,
    source_tree_sha256: str,
) -> dict[str, object]:
    static = _command_record(
        name="static-public-surface",
        argv=[
            sys.executable,
            str(STATIC_VALIDATOR),
            "--public-export",
            str(snapshot),
        ],
        display_command=(
            "python skills/research-code-audit-training/scripts/"
            "validate_training_package.py --public-export <frozen-export-snapshot>"
        ),
        scope=(
            "Frozen exported package structure, instructor-directory absence, and "
            "learner-visible leakage patterns only."
        ),
    )
    if static["outcome"] != "passed":
        raise ReleaseError("Open Demo static validation did not pass; no bundle was written")
    if run_public_checks:
        runtime = _command_record(
            name="level-1-through-4-public-checks",
            argv=[sys.executable, str(snapshot / PUBLIC_CHECK_RUNNER.name)],
            display_command=(
                "python <frozen-export-snapshot>/run_all_public_checks.py"
            ),
            scope=(
                "Learner-visible deterministic runtime contracts only; no scientific "
                "or maturity judgment."
            ),
        )
        if runtime["outcome"] != "passed":
            raise ReleaseError(
                "Open Demo public runtime checks did not pass; no bundle was written"
            )
    else:
        runtime = {
            "name": "level-1-through-4-public-checks",
            "command": (
                "python LLM4SBR_research_audit_training_v2/"
                "run_all_public_checks.py"
            ),
            "started_at": None,
            "outcome": "not-run",
            "exit_code": None,
            "stdout_sha256": None,
            "stderr_sha256": None,
            "scope": (
                "Optional heavy-runtime check; run with --run-public-checks before a "
                "release claim."
            ),
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "rcsl-open-demo-validation",
        "validated_source_tree_sha256": source_tree_sha256,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "records": [static, runtime],
        "scientific_correctness": "not_assessed",
        "measurement_validity": "not_assessed",
    }


def _open_demo_boundary() -> bytes:
    return b"""# Open Demo release boundary

This bundle is a historically public teaching artifact with honor isolation.  The
exporter omitted instructor-oriented directories from distribution, but omission,
compression, relocation, or encryption cannot make a previously public case unseen.

Checksums establish byte integrity for this generated bundle only.  Static and
runtime checks cover documented package contracts only; they do not prove the paper,
scientific claims, learning impact, security, confidentiality, or reviewer identity.
The bundle must never be described as a controlled Blind Challenge.
"""


def export_open_demo(
    output_value: Path | str,
    *,
    actor: str,
    run_public_checks: bool = False,
) -> Path:
    """Export the current historically public case without instructor material."""

    actor_label = _validate_text(actor, field="actor label", maximum=200)
    output = _validate_new_output(output_value)
    source_files, skipped = _collect_directory(
        OPEN_DEMO_SOURCE,
        label="current Open Demo source",
        skip_names=OPEN_DEMO_SKIPPED_NAMES,
        reject_isolated=False,
    )
    if not any(
        PurePosixPath(path).name.casefold() == ISOLATED_DIRECTORY_NAME.casefold()
        for path in skipped
    ):
        raise ReleaseError(
            "Open Demo source did not expose the expected honor-isolation boundary"
        )
    source_tree_sha256 = _root_digest(
        {
            "path": path,
            "sha256": blob.sha256,
            "size": blob.size,
            "executable": blob.executable,
        }
        for path, blob in source_files.items()
    )
    with tempfile.TemporaryDirectory(prefix="rcsl-open-demo-validation-") as temporary:
        snapshot = Path(temporary) / OPEN_DEMO_SOURCE.name
        snapshot.mkdir(mode=0o700)
        _write_tree(
            snapshot,
            {path: blob.data for path, blob in source_files.items()},
            executable_paths={
                path for path, blob in source_files.items() if blob.executable
            },
        )
        validation = _open_demo_validation(
            snapshot,
            run_public_checks=run_public_checks,
            source_tree_sha256=source_tree_sha256,
        )
    source_revision = _git_revision()
    worktree_state = _git_worktree_state()
    files: dict[str, bytes] = {
        f"{OPEN_DEMO_SOURCE.name}/{path}": blob.data
        for path, blob in source_files.items()
    }
    support_files = {
        "LICENSE": REPOSITORY_ROOT / "LICENSE",
        "DOCUMENTATION_LICENSE.md": REPOSITORY_ROOT / "DOCUMENTATION_LICENSE.md",
        "THIRD_PARTY_NOTICES.md": REPOSITORY_ROOT / "THIRD_PARTY_NOTICES.md",
        "docs/CASE_RELEASE_MODEL.md": REPOSITORY_ROOT
        / "docs"
        / "CASE_RELEASE_MODEL.md",
        "docs/CASE_RELEASE_MODEL_EN.md": REPOSITORY_ROOT
        / "docs"
        / "CASE_RELEASE_MODEL_EN.md",
    }
    for relative, source in support_files.items():
        files[relative] = _read_public_asset(source, label=f"Open Demo support file {relative}")
    files["RELEASE_BOUNDARY.md"] = _open_demo_boundary()
    files["VALIDATION_RECORD.json"] = _json_bytes(validation)
    files["REVOCATION_NOTICE_TEMPLATE.md"] = _read_public_asset(
        REVOCATION_TEMPLATE, label="revocation notice template"
    )
    files["verify_package.py"] = _standalone_verifier()

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "manifest_type": "rcsl-open-demo-package",
        "release_mode": "open-demo",
        "release_state": "open-demo-artifact",
        "exposure_state": "historically-public-honor-isolation",
        "case_id": "rcsl/llm4sbr-research-audit-v2",
        "case_version": "2.0.0",
        "source_revision": source_revision,
        "source_revision_scope": "repository-head-not-byte-identity",
        "repository_worktree_state": worktree_state,
        "source_tree_sha256": source_tree_sha256,
        "created_at": _utc_now(),
        "declared_actor": actor_label,
        "actor_authentication": "not_performed",
        "files": _file_records(files),
        "licenses": [
            {
                "scope": "RCSL-authored software",
                "terms": "Apache-2.0",
                "notice": "LICENSE",
            },
            {
                "scope": "RCSL-authored documentation",
                "terms": "CC-BY-4.0",
                "notice": "DOCUMENTATION_LICENSE.md",
            },
            {
                "scope": "third-party exclusions and provenance",
                "terms": "See notice",
                "notice": "THIRD_PARTY_NOTICES.md",
            },
        ],
        "known_limitations": [
            "Instructor material was historically present in public Git history.",
            "Pattern-based leakage checks are incomplete and are not a confidentiality proof.",
            "Checksums prove retained-byte consistency only.",
            "Public checks do not establish scientific correctness or learning impact.",
            "Git HEAD alone does not identify dirty-worktree bytes; source_tree_sha256 binds the exported case snapshot.",
        ],
        "claims_not_made": [
            "unseen or confidential assessment",
            "access control",
            "scientific replication",
            "measurement validity",
            "authenticated reviewer identity",
        ],
        "scientific_correctness": "not_assessed",
        "measurement_validity": "not_assessed",
        "validation_record": "VALIDATION_RECORD.json",
        "revocation_template": "REVOCATION_NOTICE_TEMPLATE.md",
    }
    package, _, _ = _finalize_package(files, manifest)
    owned = _create_owned_output(output)
    try:
        _write_tree_at(
            owned.descriptor,
            package,
            executable_paths={
                f"{OPEN_DEMO_SOURCE.name}/{path}"
                for path, blob in source_files.items()
                if blob.executable
            },
        )
        os.fsync(owned.descriptor)
        _assert_owned_output_identity(owned)
        verify_export(output)
        _assert_owned_output_identity(owned)
    except BaseException:
        _cleanup_owned_output(owned)
        _close_owned_output(owned)
        raise
    _close_owned_output(owned)
    return output


def _load_blind_manifest(path_value: Path | str) -> tuple[dict[str, object], bytes]:
    path = _normalized_path(path_value)
    if _has_isolated_component(path):
        raise ReleaseError("refusing a protected instructor-material manifest path")
    try:
        if path.is_symlink():
            raise ReleaseError("blind source manifest must not be a symlink")
        canonical = path.resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as error:
        raise ReleaseError(f"could not resolve blind source manifest: {error}") from error
    if _has_isolated_component(canonical):
        raise ReleaseError("refusing a protected instructor-material manifest path")
    if _is_within(canonical, REPOSITORY_ROOT.resolve()):
        raise ReleaseError(
            "blind source manifest must stay outside the public RCSL repository"
        )
    if os.name == "posix":
        try:
            if stat.S_IMODE(canonical.stat().st_mode) & 0o077:
                raise ReleaseError(
                    "blind source manifest must not grant group or other permissions"
                )
            if stat.S_IMODE(canonical.parent.stat().st_mode) & 0o077:
                raise ReleaseError(
                    "blind source manifest parent must not grant group or other permissions"
                )
        except OSError as error:
            raise ReleaseError(
                f"could not validate blind source manifest permissions: {error}"
            ) from error
    data = _read_regular_path(
        path,
        label="blind source manifest",
        maximum_bytes=MAX_MANIFEST_BYTES,
    )
    manifest = _strict_json_bytes(data, field="blind source manifest")
    return _validate_blind_manifest(manifest), data


def _validate_blind_manifest(manifest: dict[str, object]) -> dict[str, object]:
    manifest = _expect_exact_keys(
        manifest, BLIND_TOP_LEVEL_KEYS, field="blind source manifest"
    )
    _require_schema_version(manifest["schema_version"], field="blind source")
    if manifest["manifest_type"] != "rcsl-blind-source":
        raise ReleaseError("manifest_type must be rcsl-blind-source")
    if manifest["release_mode"] != "blind-challenge":
        raise ReleaseError("release_mode must be blind-challenge")
    _validate_id(manifest["release_id"], field="release_id")
    _validate_id(manifest["case_id"], field="case_id")
    version = _validate_text(manifest["case_version"], field="case_version", maximum=100)
    if not SEMVER_PATTERN.fullmatch(version):
        raise ReleaseError("case_version must be semantic version text")
    _validate_timestamp(manifest["created_at"], field="created_at")

    novelty = _expect_exact_keys(
        manifest["novelty_attestation"],
        {"state", "reviewer", "reviewed_at", "evidence_refs"},
        field="novelty_attestation",
    )
    if novelty["state"] != "human-declared-never-public":
        raise ReleaseError(
            "blind packaging requires a human-declared never-public source"
        )
    _validate_text(novelty["reviewer"], field="novelty_attestation.reviewer")
    _validate_timestamp(
        novelty["reviewed_at"], field="novelty_attestation.reviewed_at"
    )
    _expect_text_list(
        novelty["evidence_refs"], field="novelty_attestation.evidence_refs"
    )

    bindings = _expect_exact_keys(
        manifest["source_bindings"], set(ROLES), field="source_bindings"
    )
    for role in ROLES:
        binding = _expect_exact_keys(
            bindings[role],
            {"revision", "revision_type", "clean_state", "root_digest"},
            field=f"source_bindings.{role}",
        )
        _validate_text(binding["revision"], field=f"source_bindings.{role}.revision")
        if not isinstance(binding["revision_type"], str) or binding[
            "revision_type"
        ] not in {"git", "content-digest"}:
            raise ReleaseError(
                f"source_bindings.{role}.revision_type must be git or content-digest"
            )
        if binding["clean_state"] != "human-declared-clean":
            raise ReleaseError(
                f"source_bindings.{role}.clean_state must be human-declared-clean"
            )
        if not isinstance(binding["root_digest"], str) or not HEX_SHA256.fullmatch(
            binding["root_digest"]
        ):
            raise ReleaseError(f"source_bindings.{role}.root_digest is invalid")

    package_files = _expect_exact_keys(
        manifest["package_files"], set(ROLES), field="package_files"
    )
    known_licenses: set[str] = set()
    licenses = manifest["licenses"]
    if not isinstance(licenses, list) or not licenses:
        raise ReleaseError("licenses must be a non-empty list")
    license_records: dict[str, dict[str, object]] = {}
    for index, raw_license in enumerate(licenses):
        field = f"licenses[{index}]"
        license_record = _expect_exact_keys(
            raw_license,
            {"id", "terms", "redistribution", "notice_path", "approval_ref"},
            field=field,
        )
        license_id = _validate_id(license_record["id"], field=f"{field}.id")
        if license_id in known_licenses:
            raise ReleaseError(f"duplicate license id: {license_id}")
        known_licenses.add(license_id)
        _validate_text(license_record["terms"], field=f"{field}.terms")
        if not isinstance(license_record["redistribution"], str) or license_record[
            "redistribution"
        ] not in {
            "allowed",
            "restricted",
            "review-required",
        }:
            raise ReleaseError(f"{field}.redistribution is invalid")
        _validate_relative_path(
            license_record["notice_path"], field=f"{field}.notice_path"
        )
        _validate_text(license_record["approval_ref"], field=f"{field}.approval_ref")
        license_records[license_id] = license_record

    for role in ROLES:
        entries = package_files[role]
        if not isinstance(entries, list) or not entries:
            raise ReleaseError(f"package_files.{role} must be a non-empty list")
        paths: set[str] = set()
        collision_keys: set[str] = set()
        for index, raw_entry in enumerate(entries):
            field = f"package_files.{role}[{index}]"
            entry = _expect_exact_keys(
                raw_entry,
                {
                    "path",
                    "sha256",
                    "size",
                    "executable",
                    "role",
                    "license_id",
                    "sensitivity",
                },
                field=field,
            )
            path = _validate_relative_path(entry["path"], field=f"{field}.path")
            collision = path.casefold()
            if path in paths or collision in collision_keys:
                raise ReleaseError(f"package_files.{role} has a path collision")
            paths.add(path)
            collision_keys.add(collision)
            if path.casefold() in GENERATED_PACKAGE_NAMES:
                raise ReleaseError(f"{field}.path collides with a generated control file")
            if not isinstance(entry["sha256"], str) or not HEX_SHA256.fullmatch(
                entry["sha256"]
            ):
                raise ReleaseError(f"{field}.sha256 is invalid")
            if (
                isinstance(entry["size"], bool)
                or not isinstance(entry["size"], int)
                or entry["size"] < 0
                or entry["size"] > MAX_FILE_BYTES
            ):
                raise ReleaseError(f"{field}.size is invalid")
            if not isinstance(entry["executable"], bool):
                raise ReleaseError(f"{field}.executable must be true or false")
            if entry["role"] != role:
                raise ReleaseError(f"{field}.role must be {role}")
            if entry["sensitivity"] != ROLE_SENSITIVITY[role]:
                raise ReleaseError(
                    f"{field}.sensitivity must be {ROLE_SENSITIVITY[role]}"
                )
            entry_license_id = _validate_id(
                entry["license_id"], field=f"{field}.license_id"
            )
            if entry_license_id not in known_licenses:
                raise ReleaseError(f"{field}.license_id is unknown")
            if (
                role == "challenge"
                and license_records[entry_license_id]["redistribution"]
                != "allowed"
            ):
                raise ReleaseError(
                    "every Challenge Package file needs redistribution=allowed"
                )
        for license_id in {str(entry["license_id"]) for entry in entries}:
            notice = str(license_records[license_id]["notice_path"])
            if notice not in paths:
                raise ReleaseError(
                    f"package_files.{role} is missing license notice {notice}"
                )

    scoring = _expect_exact_keys(
        manifest["scoring"],
        {
            "protocol_id",
            "version",
            "digest",
            "automatic_scope",
            "human_gate",
            "independent_reviewer_ref",
        },
        field="scoring",
    )
    _validate_id(scoring["protocol_id"], field="scoring.protocol_id")
    scoring_version = _validate_text(
        scoring["version"], field="scoring.version", maximum=100
    )
    if not SEMVER_PATTERN.fullmatch(scoring_version):
        raise ReleaseError("scoring.version must be semantic version text")
    if not isinstance(scoring["digest"], str) or not HEX_SHA256.fullmatch(
        scoring["digest"]
    ) or scoring["digest"] == ZERO_SHA256:
        raise ReleaseError("scoring.digest is invalid")
    for key in ("automatic_scope", "human_gate", "independent_reviewer_ref"):
        _validate_text(scoring[key], field=f"scoring.{key}")

    isolation = _expect_exact_keys(
        manifest["isolation"],
        {
            "challenge_audience",
            "evaluator_audience",
            "maintainer_audience",
            "access_plan_ref",
            "submission_channel_ref",
        },
        field="isolation",
    )
    for key in isolation:
        _validate_text(isolation[key], field=f"isolation.{key}")

    validation = _expect_exact_keys(
        manifest["validation"],
        {
            "public_record_refs",
            "controlled_record_refs",
            "leakage_review_ref",
            "repeatability_review_ref",
        },
        field="validation",
    )
    _expect_text_list(
        validation["public_record_refs"],
        field="validation.public_record_refs",
        allow_empty=True,
    )
    _expect_text_list(
        validation["controlled_record_refs"],
        field="validation.controlled_record_refs",
    )
    _validate_text(
        validation["leakage_review_ref"], field="validation.leakage_review_ref"
    )
    _validate_text(
        validation["repeatability_review_ref"],
        field="validation.repeatability_review_ref",
    )

    withdrawal = _expect_exact_keys(
        manifest["withdrawal"],
        {"owner_label", "contact_or_process_ref", "triggers", "procedure_ref"},
        field="withdrawal",
    )
    _validate_text(withdrawal["owner_label"], field="withdrawal.owner_label")
    _validate_text(
        withdrawal["contact_or_process_ref"],
        field="withdrawal.contact_or_process_ref",
    )
    _expect_text_list(withdrawal["triggers"], field="withdrawal.triggers")
    _validate_text(withdrawal["procedure_ref"], field="withdrawal.procedure_ref")
    _expect_text_list(manifest["claims_not_made"], field="claims_not_made")

    approvals = manifest["human_approvals"]
    if not isinstance(approvals, list):
        raise ReleaseError("human_approvals must be a list")
    approval_gates: set[str] = set()
    for index, raw_approval in enumerate(approvals):
        field = f"human_approvals[{index}]"
        approval = _expect_exact_keys(
            raw_approval,
            {"gate", "reviewer", "reviewed_at", "rationale", "evidence_refs"},
            field=field,
        )
        gate = _validate_text(approval["gate"], field=f"{field}.gate")
        if gate not in APPROVAL_GATES or gate in approval_gates:
            raise ReleaseError(f"{field}.gate is missing, duplicate, or unsupported")
        approval_gates.add(gate)
        _validate_text(approval["reviewer"], field=f"{field}.reviewer")
        _validate_timestamp(approval["reviewed_at"], field=f"{field}.reviewed_at")
        _validate_text(approval["rationale"], field=f"{field}.rationale")
        _expect_text_list(
            approval["evidence_refs"], field=f"{field}.evidence_refs"
        )
    if approval_gates != set(APPROVAL_GATES):
        raise ReleaseError(
            f"human_approvals must contain exactly these gates: {list(APPROVAL_GATES)}"
        )
    return deepcopy(manifest)


def _validate_blind_source_root(path_value: Path | str, *, role: str) -> Path:
    path = _normalized_path(path_value)
    if _has_isolated_component(path):
        raise ReleaseError(f"{role} source cannot use a protected-path convention")
    try:
        if path.is_symlink():
            raise ReleaseError(f"{role} source must not be a symlink")
        canonical = path.resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as error:
        raise ReleaseError(f"could not resolve {role} source: {error}") from error
    if not canonical.is_dir():
        raise ReleaseError(f"{role} source must be a real directory")
    if _has_isolated_component(canonical):
        raise ReleaseError(f"{role} source cannot use a protected-path convention")
    if _is_within(canonical, REPOSITORY_ROOT.resolve()):
        raise ReleaseError(
            "a historically public RCSL path is not eligible as a blind source"
        )
    return canonical


def _entry_records(entries: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        {
            "path": entry["path"],
            "sha256": entry["sha256"],
            "size": entry["size"],
            "executable": entry["executable"],
        }
        for entry in entries
    ]


def _validate_and_freeze_role(
    root: Path,
    role: str,
    manifest: dict[str, object],
) -> tuple[dict[str, bytes], dict[str, object], set[str]]:
    collected, _ = _collect_directory(
        root,
        label=f"{role} source",
        reject_isolated=True,
    )
    entries = manifest["package_files"][role]
    expected = {str(entry["path"]): entry for entry in entries}
    if set(collected) != set(expected):
        raise ReleaseError(
            f"{role} source file set does not match its explicit allowlist"
        )
    for path, blob in collected.items():
        entry = expected[path]
        if (
            entry["sha256"] != blob.sha256
            or entry["size"] != blob.size
            or entry["executable"] != blob.executable
        ):
            raise ReleaseError(f"{role} source bytes do not match the frozen manifest")
    records = _entry_records(entries)
    expected_root = manifest["source_bindings"][role]["root_digest"]
    if _root_digest(records) != expected_root:
        raise ReleaseError(f"{role} root digest does not match the explicit allowlist")
    return (
        {path: blob.data for path, blob in collected.items()},
        {
            "file_count": len(collected),
            "byte_count": sum(blob.size for blob in collected.values()),
            "root_digest": expected_root,
        },
        {path for path, blob in collected.items() if blob.executable},
    )


def _challenge_private_values(manifest: dict[str, object]) -> tuple[bytes, ...]:
    """Return controlled values that must never occur in Challenge payload bytes."""

    scoring = manifest["scoring"]
    if not isinstance(scoring, dict):  # Already validated; keep the helper fail closed.
        raise ReleaseError("invalid private scoring record")
    digest = scoring.get("digest")
    if not isinstance(digest, str) or not HEX_SHA256.fullmatch(digest):
        raise ReleaseError("invalid private scoring digest")
    values = [digest.encode("ascii")]
    licenses = manifest.get("licenses")
    if not isinstance(licenses, list):  # Already validated; keep this fail closed.
        raise ReleaseError("invalid private license records")
    for license_record in licenses:
        if not isinstance(license_record, dict):
            raise ReleaseError("invalid private license record")
        approval_ref = license_record.get("approval_ref")
        if not isinstance(approval_ref, str):
            raise ReleaseError("invalid private license approval reference")
        values.append(approval_ref.encode("utf-8"))
    unique: dict[bytes, bytes] = {}
    for value in values:
        unique.setdefault(value.lower(), value)
    return tuple(unique.values())


def _scan_challenge(
    files: dict[str, bytes], *, private_values: Iterable[bytes] = ()
) -> dict[str, object]:
    normalized_private_values: tuple[bytes, ...] = tuple(private_values)
    for value in normalized_private_values:
        if not isinstance(value, bytes) or not value:
            raise ReleaseError("invalid private Challenge comparison value")
    text_files = 0
    binary_files = 0
    for path, data in files.items():
        relative = PurePosixPath(path)
        if any(
            FORBIDDEN_CHALLENGE_PATH.search(part)
            or part.casefold() in FORBIDDEN_CHALLENGE_PATH_NAMES
            or PurePosixPath(part).suffix.casefold()
            in FORBIDDEN_CHALLENGE_SECRET_SUFFIXES
            for part in relative.parts
        ):
            raise ReleaseError(
                "Challenge Package failed bounded leakage rule path-forbidden"
            )
        folded_data = data.lower()
        if any(value.lower() in folded_data for value in normalized_private_values):
            raise ReleaseError(
                "Challenge Package failed bounded leakage rule exact-sensitive-value"
            )
        declared_text = (
            relative.suffix.casefold() in TEXT_SUFFIXES
            or relative.name.casefold()
            in {"dockerfile", "makefile", "procfile", "rakefile"}
        )
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as error:
            if declared_text:
                raise ReleaseError(
                    "a text-classified Challenge Package file is not valid UTF-8"
                ) from error
            binary_files += 1
            continue
        text_files += 1
        if FORBIDDEN_CHALLENGE_TEXT.search(text):
            raise ReleaseError(
                "Challenge Package failed bounded leakage rule schema-answer-field"
            )
        if FORBIDDEN_CHALLENGE_IMPORT.search(text):
            raise ReleaseError(
                "Challenge Package failed bounded leakage rule controlled-import"
            )
    return {
        "schema_version": SCHEMA_VERSION,
        "scan_type": "bounded-pattern-and-path-scan",
        "status": "passed",
        "text_files_scanned": text_files,
        "binary_files_path_only": binary_files,
        "known_limit": CHALLENGE_LEAKAGE_LIMIT,
        "scientific_correctness": "not_assessed",
    }


def _role_license_records(
    manifest: dict[str, object], role: str
) -> list[dict[str, object]]:
    used = {
        str(entry["license_id"]) for entry in manifest["package_files"][role]
    }
    return [
        {
            "id": license_record["id"],
            "terms": license_record["terms"],
            "redistribution": license_record["redistribution"],
            "notice_path": license_record["notice_path"],
        }
        for license_record in manifest["licenses"]
        if str(license_record["id"]) in used
    ]


def _validate_challenge_metadata(manifest: dict[str, object]) -> None:
    learner_metadata = {
        "release_id": manifest["release_id"],
        "case_id": manifest["case_id"],
        "case_version": manifest["case_version"],
        "scoring_reference": {
            "protocol_id": manifest["scoring"]["protocol_id"],
            "version": manifest["scoring"]["version"],
        },
        "licenses": _role_license_records(manifest, "challenge"),
    }
    text = _json_bytes(learner_metadata).decode("utf-8")
    if FORBIDDEN_CHALLENGE_TEXT.search(text) or FORBIDDEN_CHALLENGE_IMPORT.search(text):
        raise ReleaseError(
            "Challenge Package failed bounded leakage rule learner-metadata"
        )


def _role_boundary(role: str) -> bytes:
    if role == "challenge":
        text = """# Challenge Package boundary

This is the learner-facing package candidate.  Its manifest binds only its own
files and an opaque scoring protocol ID/version.  It contains no controlled-package
digest.  A limited leakage scan passed, but independent human review and controlled
placement are still required.  Its isolated verifier cannot know private values
such as the scoring digest; run trusted staging verification before release.
Package integrity is not confidentiality, novelty, fairness, scientific correctness,
or a maturity verdict.
"""
    elif role == "evaluator":
        text = """# Evaluator Package boundary

This package is controlled evaluation material.  Keep it outside participant
environments and ordinary public distribution.  The packager does not execute its
grader or establish scoring validity.  Independent operation, access control,
repeatability review, and human release approval remain mandatory.
"""
    else:
        text = """# Maintainer Record boundary

This controlled record retains provenance, design, risk, package bindings, access
and withdrawal material.  It is not a participant package.  Declared people and
approvals are labels, not authenticated signatures, and local assembly is not a
controlled release.
"""
    return text.encode("utf-8")


def _build_role_package(
    *,
    role: str,
    source_files: dict[str, bytes],
    manifest: dict[str, object],
    source_manifest_data: bytes,
    leakage_scan: dict[str, object],
    challenge_manifest_sha256: str | None = None,
    evaluator_manifest_sha256: str | None = None,
) -> tuple[dict[str, bytes], str, str]:
    files = dict(source_files)
    files["RELEASE_BOUNDARY.md"] = _role_boundary(role)
    files["verify_package.py"] = _standalone_verifier()
    source_inventory = deepcopy(manifest["package_files"][role])
    licenses = _role_license_records(manifest, role)
    if role == "challenge":
        files["LEAKAGE_SCAN.json"] = _json_bytes(leakage_scan)
        role_manifest: dict[str, object] = {
            "schema_version": SCHEMA_VERSION,
            "manifest_type": "rcsl-role-package",
            "package_role": role,
            "distribution_state": "learner-facing-candidate",
            "release_id": manifest["release_id"],
            "case_id": manifest["case_id"],
            "case_version": manifest["case_version"],
            "created_at": manifest["created_at"],
            "scoring_reference": {
                "protocol_id": manifest["scoring"]["protocol_id"],
                "version": manifest["scoring"]["version"],
            },
            "source_inventory": source_inventory,
            "licenses": licenses,
            "files": _file_records(files),
            "boundary": "assembled-awaiting-controlled-placement",
            "claims_not_made": [
                "confidentiality",
                "verified novelty",
                "measurement validity",
                "scientific correctness",
            ],
            "scientific_correctness": "not_assessed",
        }
    elif role == "evaluator":
        if challenge_manifest_sha256 is None:
            raise ReleaseError("internal package order error")
        role_manifest = {
            "schema_version": SCHEMA_VERSION,
            "manifest_type": "rcsl-role-package",
            "package_role": role,
            "distribution_state": "controlled-candidate",
            "release_id": manifest["release_id"],
            "case_id": manifest["case_id"],
            "case_version": manifest["case_version"],
            "created_at": manifest["created_at"],
            "source_manifest_sha256": _sha256_bytes(source_manifest_data),
            "challenge_manifest_sha256": challenge_manifest_sha256,
            "scoring_reference": deepcopy(manifest["scoring"]),
            "source_inventory": source_inventory,
            "licenses": licenses,
            "files": _file_records(files),
            "boundary": "assembled-awaiting-controlled-placement",
            "claims_not_made": deepcopy(manifest["claims_not_made"]),
            "scientific_correctness": "not_assessed",
        }
    else:
        if challenge_manifest_sha256 is None or evaluator_manifest_sha256 is None:
            raise ReleaseError("internal package order error")
        files["BLIND_SOURCE.json"] = source_manifest_data
        files["REVOCATION_NOTICE_TEMPLATE.md"] = _read_public_asset(
            REVOCATION_TEMPLATE, label="revocation notice template"
        )
        files["ACCESS_LOG_TEMPLATE.md"] = _read_public_asset(
            ACCESS_LOG_TEMPLATE, label="access log template"
        )
        role_manifest = {
            "schema_version": SCHEMA_VERSION,
            "manifest_type": "rcsl-role-package",
            "package_role": role,
            "distribution_state": "controlled-candidate",
            "release_id": manifest["release_id"],
            "case_id": manifest["case_id"],
            "case_version": manifest["case_version"],
            "created_at": manifest["created_at"],
            "source_manifest_sha256": _sha256_bytes(source_manifest_data),
            "challenge_manifest_sha256": challenge_manifest_sha256,
            "evaluator_manifest_sha256": evaluator_manifest_sha256,
            "source_inventory": source_inventory,
            "licenses": licenses,
            "files": _file_records(files),
            "boundary": "assembled-awaiting-controlled-placement",
            "claims_not_made": deepcopy(manifest["claims_not_made"]),
            "scientific_correctness": "not_assessed",
        }
    return _finalize_package(files, role_manifest)


def package_blind(
    manifest_value: Path | str,
    *,
    challenge_source: Path | str,
    evaluator_source: Path | str,
    maintainer_source: Path | str,
    output: Path | str,
    actor: str,
) -> Path:
    """Assemble three local package candidates from an explicit never-public plan."""

    actor_label = _validate_text(actor, field="actor label", maximum=200)
    manifest, source_manifest_data = _load_blind_manifest(manifest_value)
    roots = {
        "challenge": _validate_blind_source_root(
            challenge_source, role="challenge"
        ),
        "evaluator": _validate_blind_source_root(
            evaluator_source, role="evaluator"
        ),
        "maintainer": _validate_blind_source_root(
            maintainer_source, role="maintainer"
        ),
    }
    for index, role in enumerate(ROLES):
        for other in ROLES[index + 1 :]:
            if _is_within(roots[role], roots[other]) or _is_within(
                roots[other], roots[role]
            ):
                raise ReleaseError("blind source roots must be distinct and non-nested")
    output_path = _validate_new_output(output)
    for root in roots.values():
        if _is_within(output_path, root) or _is_within(root, output_path):
            raise ReleaseError("blind source and output paths must not overlap")

    frozen: dict[str, dict[str, bytes]] = {}
    frozen_executables: dict[str, set[str]] = {}
    source_summaries: dict[str, dict[str, object]] = {}
    for role in ROLES:
        (
            frozen[role],
            source_summaries[role],
            frozen_executables[role],
        ) = _validate_and_freeze_role(roots[role], role, manifest)
    leakage_scan = _scan_challenge(
        frozen["challenge"],
        private_values=_challenge_private_values(manifest),
    )
    _validate_challenge_metadata(manifest)

    challenge_package, challenge_manifest_digest, challenge_checksums_digest = (
        _build_role_package(
            role="challenge",
            source_files=frozen["challenge"],
            manifest=manifest,
            source_manifest_data=source_manifest_data,
            leakage_scan=leakage_scan,
        )
    )
    evaluator_package, evaluator_manifest_digest, evaluator_checksums_digest = (
        _build_role_package(
            role="evaluator",
            source_files=frozen["evaluator"],
            manifest=manifest,
            source_manifest_data=source_manifest_data,
            leakage_scan=leakage_scan,
            challenge_manifest_sha256=challenge_manifest_digest,
        )
    )
    maintainer_package, maintainer_manifest_digest, maintainer_checksums_digest = (
        _build_role_package(
            role="maintainer",
            source_files=frozen["maintainer"],
            manifest=manifest,
            source_manifest_data=source_manifest_data,
            leakage_scan=leakage_scan,
            challenge_manifest_sha256=challenge_manifest_digest,
            evaluator_manifest_sha256=evaluator_manifest_digest,
        )
    )
    packages = {
        "challenge": challenge_package,
        "evaluator": evaluator_package,
        "maintainer": maintainer_package,
    }
    digests = {
        "challenge": {
            "manifest_sha256": challenge_manifest_digest,
            "checksums_sha256": challenge_checksums_digest,
        },
        "evaluator": {
            "manifest_sha256": evaluator_manifest_digest,
            "checksums_sha256": evaluator_checksums_digest,
        },
        "maintainer": {
            "manifest_sha256": maintainer_manifest_digest,
            "checksums_sha256": maintainer_checksums_digest,
        },
    }
    build_record = {
        "schema_version": SCHEMA_VERSION,
        "record_type": "rcsl-local-blind-assembly",
        "built_at": _utc_now(),
        "declared_actor": actor_label,
        "actor_authentication": "not_performed",
        "tool_revision": _git_revision(),
        "tool_revision_scope": "repository-head-not-byte-identity",
        "tool_worktree_state": _git_worktree_state(),
        "packager_sha256": _packager_sha256(),
        "verifier_sha256": _sha256_bytes(_standalone_verifier()),
        "network_used": False,
        "package_code_executed": False,
        "assembly_state": "assembled-awaiting-controlled-placement",
    }
    build_record_data = _json_bytes(build_record)
    control_manifest = {
        "schema_version": SCHEMA_VERSION,
        "manifest_type": "rcsl-blind-staging",
        "release_id": manifest["release_id"],
        "case_id": manifest["case_id"],
        "case_version": manifest["case_version"],
        "assembly_state": "assembled-awaiting-controlled-placement",
        "source_manifest_sha256": _sha256_bytes(source_manifest_data),
        "build_record_sha256": _sha256_bytes(build_record_data),
        "packages": digests,
        "source_summaries": source_summaries,
        "operational_gates_remaining": list(OPERATIONAL_GATES_REMAINING),
        "scientific_correctness": "not_assessed",
        "measurement_validity": "not_assessed",
    }

    owned = _create_owned_output(output_path)
    try:
        for role in ROLES:
            role_descriptor = _open_or_create_directory_at(owned.descriptor, role)
            try:
                _write_tree_at(
                    role_descriptor,
                    packages[role],
                    executable_paths=frozen_executables[role],
                )
                os.fsync(role_descriptor)
            finally:
                os.close(role_descriptor)
        _write_file_at(
            owned.descriptor,
            "CONTROL_MANIFEST.json",
            _json_bytes(control_manifest),
        )
        _write_file_at(
            owned.descriptor, "BUILD_RECORD.json", build_record_data
        )
        os.fsync(owned.descriptor)
        _assert_owned_output_identity(owned)
        verify_blind_staging(output_path)
        _assert_owned_output_identity(owned)
    except BaseException:
        _cleanup_owned_output(owned)
        _close_owned_output(owned)
        raise
    _close_owned_output(owned)
    return output_path


def _parse_checksums(data: bytes) -> dict[str, str]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ReleaseError("CHECKSUMS.sha256 must be UTF-8") from error
    result: dict[str, str] = {}
    collision_keys: set[str] = set()
    for index, line in enumerate(text.splitlines()):
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if match is None:
            raise ReleaseError(f"malformed checksum record at line {index + 1}")
        path = _validate_relative_path(
            match.group(2), field=f"checksum line {index + 1} path"
        )
        collision = path.casefold()
        if collision in collision_keys:
            raise ReleaseError("checksums contain a duplicate or colliding path")
        collision_keys.add(collision)
        result[path] = match.group(1)
    if not result:
        raise ReleaseError("checksums file is empty")
    return result


def _verify_checksum_tree(root: Path) -> dict[str, object]:
    files, _ = _collect_directory(
        root,
        label="release package",
        reject_isolated=True,
        maximum_files=MAX_PACKAGE_FILES,
        maximum_total_bytes=MAX_PACKAGE_TOTAL_BYTES,
    )
    if "CHECKSUMS.sha256" not in files or "PACKAGE_MANIFEST.json" not in files:
        raise ReleaseError("release package is missing manifest or checksums")
    expected = _parse_checksums(files["CHECKSUMS.sha256"].data)
    actual_paths = set(files) - {"CHECKSUMS.sha256"}
    if set(expected) != actual_paths:
        raise ReleaseError("release package file set differs from checksums")
    for path, digest in expected.items():
        if files[path].sha256 != digest:
            raise ReleaseError("release package checksum mismatch")
    manifest = _strict_json_bytes(
        files["PACKAGE_MANIFEST.json"].data, field="package manifest"
    )
    if manifest.get("scientific_correctness") != "not_assessed":
        raise ReleaseError("package manifest crossed the scientific trust boundary")
    records = manifest.get("files")
    if not isinstance(records, list):
        raise ReleaseError("package manifest files must be a list")
    recorded: dict[str, dict[str, object]] = {}
    recorded_collisions: set[str] = set()
    for index, raw_record in enumerate(records):
        record = _expect_exact_keys(
            raw_record,
            {"path", "sha256", "size"},
            field=f"package manifest files[{index}]",
        )
        path = _validate_relative_path(
            record["path"], field=f"package manifest files[{index}].path"
        )
        collision = path.casefold()
        if path in recorded or collision in recorded_collisions:
            raise ReleaseError("package manifest files contain a path collision")
        if not isinstance(record["sha256"], str) or not HEX_SHA256.fullmatch(
            record["sha256"]
        ):
            raise ReleaseError("package manifest contains an invalid digest")
        if isinstance(record["size"], bool) or not isinstance(record["size"], int):
            raise ReleaseError("package manifest contains an invalid size")
        recorded[path] = record
        recorded_collisions.add(collision)
    payload_paths = actual_paths - {"PACKAGE_MANIFEST.json"}
    if set(recorded) != payload_paths:
        raise ReleaseError("package manifest file set differs from retained payload")
    for path, record in recorded.items():
        if files[path].sha256 != record["sha256"] or files[path].size != record["size"]:
            raise ReleaseError("package manifest file record mismatch")
    return {
        "integrity_status": "pass",
        "manifest_type": manifest.get("manifest_type"),
        "package_role": manifest.get("package_role"),
        "manifest_sha256": files["PACKAGE_MANIFEST.json"].sha256,
        "checksums_sha256": files["CHECKSUMS.sha256"].sha256,
        "file_count": len(actual_paths),
        "scientific_correctness": "not_assessed",
        "_manifest": manifest,
        "_files": files,
    }


def _validate_open_demo_manifest(manifest: dict[str, object]) -> None:
    expected_keys = {
        "schema_version",
        "manifest_type",
        "release_mode",
        "release_state",
        "exposure_state",
        "case_id",
        "case_version",
        "source_revision",
        "source_revision_scope",
        "repository_worktree_state",
        "source_tree_sha256",
        "created_at",
        "declared_actor",
        "actor_authentication",
        "files",
        "licenses",
        "known_limitations",
        "claims_not_made",
        "scientific_correctness",
        "measurement_validity",
        "validation_record",
        "revocation_template",
    }
    _expect_exact_keys(manifest, expected_keys, field="Open Demo package manifest")
    _require_schema_version(
        manifest["schema_version"], field="Open Demo package"
    )
    if (
        manifest["manifest_type"] != "rcsl-open-demo-package"
        or manifest["release_mode"] != "open-demo"
        or manifest["release_state"] != "open-demo-artifact"
        or manifest["exposure_state"] != "historically-public-honor-isolation"
        or manifest["actor_authentication"] != "not_performed"
        or manifest["scientific_correctness"] != "not_assessed"
        or manifest["measurement_validity"] != "not_assessed"
        or manifest["validation_record"] != "VALIDATION_RECORD.json"
        or manifest["revocation_template"] != "REVOCATION_NOTICE_TEMPLATE.md"
        or manifest["source_revision_scope"] != "repository-head-not-byte-identity"
        or not isinstance(manifest["repository_worktree_state"], str)
        or manifest["repository_worktree_state"] not in {"clean", "dirty"}
    ):
        raise ReleaseError("Open Demo package boundary is invalid")
    _validate_id(manifest["case_id"], field="Open Demo case_id")
    version = _validate_text(
        manifest["case_version"], field="Open Demo case_version", maximum=100
    )
    if not SEMVER_PATTERN.fullmatch(version):
        raise ReleaseError("Open Demo case_version is invalid")
    if not isinstance(manifest["source_revision"], str) or not GIT_REVISION.fullmatch(
        manifest["source_revision"]
    ):
        raise ReleaseError("Open Demo source revision is invalid")
    if not isinstance(manifest["source_tree_sha256"], str) or not HEX_SHA256.fullmatch(
        manifest["source_tree_sha256"]
    ):
        raise ReleaseError("Open Demo source tree digest is invalid")
    _validate_timestamp(manifest["created_at"], field="Open Demo created_at")
    _validate_text(manifest["declared_actor"], field="Open Demo declared_actor")
    _expect_text_list(manifest["known_limitations"], field="Open Demo known_limitations")
    claims = _expect_text_list(manifest["claims_not_made"], field="Open Demo claims_not_made")
    if not any("unseen" in claim.casefold() for claim in claims):
        raise ReleaseError("Open Demo manifest must disclaim unseen assessment")
    licenses = manifest["licenses"]
    if not isinstance(licenses, list) or not licenses:
        raise ReleaseError("Open Demo licenses must be a non-empty list")
    for index, raw_license in enumerate(licenses):
        license_record = _expect_exact_keys(
            raw_license,
            {"scope", "terms", "notice"},
            field=f"Open Demo licenses[{index}]",
        )
        _validate_text(license_record["scope"], field=f"Open Demo licenses[{index}].scope")
        _validate_text(license_record["terms"], field=f"Open Demo licenses[{index}].terms")
        _validate_relative_path(
            license_record["notice"], field=f"Open Demo licenses[{index}].notice"
        )


def _validate_open_demo_record(
    manifest: dict[str, object], files: dict[str, FileBlob]
) -> None:
    source_prefix = f"{OPEN_DEMO_SOURCE.name}/"
    non_source_paths = {
        path for path in files if not path.startswith(source_prefix)
    }
    if non_source_paths != OPEN_DEMO_NON_SOURCE_FILES:
        raise ReleaseError("Open Demo package contains an unbound non-source file")
    required = {
        "VALIDATION_RECORD.json",
        "REVOCATION_NOTICE_TEMPLATE.md",
        "RELEASE_BOUNDARY.md",
        "verify_package.py",
    }
    if not required.issubset(files):
        raise ReleaseError("Open Demo package is missing a release-boundary artifact")
    if files["verify_package.py"].data != _standalone_verifier():
        raise ReleaseError("Open Demo verifier does not match the trusted verifier")
    if files["RELEASE_BOUNDARY.md"].data != _open_demo_boundary():
        raise ReleaseError("Open Demo release boundary does not match schema version 1")
    for index, raw_license in enumerate(manifest["licenses"]):
        notice = str(raw_license["notice"])
        if notice not in files:
            raise ReleaseError(f"Open Demo license notice {index} is not retained")
    prefix = source_prefix
    source_records = [
        {
            "path": path.removeprefix(prefix),
            "sha256": blob.sha256,
            "size": blob.size,
            "executable": blob.executable,
        }
        for path, blob in files.items()
        if path.startswith(prefix)
    ]
    if not source_records or _root_digest(source_records) != manifest["source_tree_sha256"]:
        raise ReleaseError("Open Demo source tree digest does not bind retained bytes")
    validation = _strict_json_bytes(
        files["VALIDATION_RECORD.json"].data, field="Open Demo validation record"
    )
    _expect_exact_keys(
        validation,
        {
            "schema_version",
            "record_type",
            "validated_source_tree_sha256",
            "environment",
            "records",
            "scientific_correctness",
            "measurement_validity",
        },
        field="Open Demo validation record",
    )
    _require_schema_version(
        validation["schema_version"], field="Open Demo validation record"
    )
    if (
        validation["record_type"] != "rcsl-open-demo-validation"
        or validation["validated_source_tree_sha256"]
        != manifest["source_tree_sha256"]
        or validation["scientific_correctness"] != "not_assessed"
        or validation["measurement_validity"] != "not_assessed"
    ):
        raise ReleaseError("Open Demo validation binding is invalid")
    environment = _expect_exact_keys(
        validation["environment"], {"python", "platform"}, field="validation environment"
    )
    _validate_text(environment["python"], field="validation environment.python")
    _validate_text(environment["platform"], field="validation environment.platform")
    records = validation["records"]
    if not isinstance(records, list) or len(records) != 2:
        raise ReleaseError("Open Demo validation must contain exactly two records")
    expected_names = (
        "static-public-surface",
        "level-1-through-4-public-checks",
    )
    for index, raw_record in enumerate(records):
        record = _expect_exact_keys(
            raw_record,
            {
                "name",
                "command",
                "started_at",
                "outcome",
                "exit_code",
                "stdout_sha256",
                "stderr_sha256",
                "scope",
            },
            field=f"Open Demo validation records[{index}]",
        )
        if record["name"] != expected_names[index]:
            raise ReleaseError("Open Demo validation record order is invalid")
        _validate_text(record["command"], field=f"validation records[{index}].command")
        _validate_text(record["scope"], field=f"validation records[{index}].scope")
        if not isinstance(record["outcome"], str):
            raise ReleaseError("Open Demo validation outcome must be text")
        if index == 0 and record["outcome"] != "passed":
            raise ReleaseError("Open Demo static validation record is not passing")
        if index == 1 and record["outcome"] not in {"passed", "not-run"}:
            raise ReleaseError("Open Demo runtime validation record is invalid")
        if record["outcome"] == "passed":
            _validate_timestamp(
                record["started_at"], field=f"validation records[{index}].started_at"
            )
            if type(record["exit_code"]) is not int or record["exit_code"] != 0:
                raise ReleaseError("Open Demo passing validation has an invalid exit code")
            for digest_field in ("stdout_sha256", "stderr_sha256"):
                if not isinstance(record[digest_field], str) or not HEX_SHA256.fullmatch(
                    record[digest_field]
                ):
                    raise ReleaseError("Open Demo validation output digest is invalid")
        elif any(
            record[field] is not None
            for field in ("started_at", "exit_code", "stdout_sha256", "stderr_sha256")
        ):
            raise ReleaseError("Open Demo not-run validation contains invented evidence")


def _validate_blind_staging_root(root: Path) -> None:
    expected = set(ROLES) | {"CONTROL_MANIFEST.json", "BUILD_RECORD.json"}
    descriptor = _open_directory_chain(root)
    try:
        names = os.listdir(descriptor)
        folded: set[str] = set()
        for name in names:
            if name != unicodedata.normalize("NFC", name):
                raise ReleaseError("blind staging contains a non-NFC root entry")
            key = name.casefold()
            if key in folded:
                raise ReleaseError("blind staging contains a root path collision")
            folded.add(key)
        if set(names) != expected:
            raise ReleaseError("blind staging root contains missing or unbound entries")
        for name in names:
            metadata = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            if name in ROLES:
                if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
                    raise ReleaseError("blind staging role entry must be a real directory")
            elif not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
                raise ReleaseError("blind staging control entry must be a regular file")
    except ReleaseError:
        raise
    except OSError as error:
        raise ReleaseError(f"could not inspect blind staging root safely: {error}") from error
    finally:
        os.close(descriptor)


def _validate_private_staging_permissions(root: Path) -> None:
    """Require POSIX staging bytes to stay inaccessible to group/other users."""

    if os.name != "posix":
        return
    root_descriptor = _open_directory_chain(root)

    def walk(directory_descriptor: int) -> None:
        metadata = os.fstat(directory_descriptor)
        if stat.S_IMODE(metadata.st_mode) & 0o077:
            raise ReleaseError("blind staging permissions expose controlled material")
        for name in os.listdir(directory_descriptor):
            child = os.stat(name, dir_fd=directory_descriptor, follow_symlinks=False)
            if stat.S_IMODE(child.st_mode) & 0o077:
                raise ReleaseError("blind staging permissions expose controlled material")
            if stat.S_ISDIR(child.st_mode):
                child_descriptor = os.open(
                    name, _directory_open_flags(), dir_fd=directory_descriptor
                )
                try:
                    walk(child_descriptor)
                finally:
                    os.close(child_descriptor)

    try:
        walk(root_descriptor)
    except ReleaseError:
        raise
    except OSError as error:
        raise ReleaseError(
            f"could not validate blind staging permissions: {error}"
        ) from error
    finally:
        os.close(root_descriptor)


def _validate_role_manifest(
    manifest: dict[str, object],
    *,
    role: str,
    control: dict[str, object] | None = None,
    source_manifest: dict[str, object] | None = None,
) -> None:
    common = {
        "schema_version",
        "manifest_type",
        "package_role",
        "distribution_state",
        "release_id",
        "case_id",
        "case_version",
        "created_at",
        "files",
        "source_inventory",
        "licenses",
        "boundary",
        "claims_not_made",
        "scientific_correctness",
    }
    expected = set(common)
    if role == "challenge":
        expected.add("scoring_reference")
    elif role == "evaluator":
        expected.update(
            {"source_manifest_sha256", "challenge_manifest_sha256", "scoring_reference"}
        )
    else:
        expected.update(
            {
                "source_manifest_sha256",
                "challenge_manifest_sha256",
                "evaluator_manifest_sha256",
            }
        )
    _expect_exact_keys(manifest, expected, field=f"{role} package manifest")
    expected_distribution = (
        "learner-facing-candidate" if role == "challenge" else "controlled-candidate"
    )
    _require_schema_version(
        manifest["schema_version"], field=f"{role} package"
    )
    if (
        manifest["manifest_type"] != "rcsl-role-package"
        or manifest["package_role"] != role
        or manifest["distribution_state"] != expected_distribution
        or manifest["boundary"] != "assembled-awaiting-controlled-placement"
        or manifest["scientific_correctness"] != "not_assessed"
    ):
        raise ReleaseError(f"{role} package boundary is invalid")
    _validate_id(manifest["release_id"], field=f"{role} release_id")
    _validate_id(manifest["case_id"], field=f"{role} case_id")
    version = _validate_text(
        manifest["case_version"], field=f"{role} case_version", maximum=100
    )
    if not SEMVER_PATTERN.fullmatch(version):
        raise ReleaseError(f"{role} case_version is invalid")
    _validate_timestamp(manifest["created_at"], field=f"{role} created_at")
    _expect_text_list(manifest["claims_not_made"], field=f"{role} claims_not_made")
    inventory = manifest["source_inventory"]
    if not isinstance(inventory, list) or not inventory:
        raise ReleaseError(f"{role} source_inventory must be a non-empty list")
    inventory_paths: set[str] = set()
    inventory_collisions: set[str] = set()
    used_licenses: set[str] = set()
    for index, raw_entry in enumerate(inventory):
        field = f"{role} source_inventory[{index}]"
        entry = _expect_exact_keys(
            raw_entry,
            {
                "path",
                "sha256",
                "size",
                "executable",
                "role",
                "license_id",
                "sensitivity",
            },
            field=field,
        )
        path = _validate_relative_path(entry["path"], field=f"{field}.path")
        collision = path.casefold()
        if path in inventory_paths or collision in inventory_collisions:
            raise ReleaseError(f"{role} source_inventory contains a path collision")
        inventory_paths.add(path)
        inventory_collisions.add(collision)
        if not isinstance(entry["sha256"], str) or not HEX_SHA256.fullmatch(
            entry["sha256"]
        ):
            raise ReleaseError(f"{field}.sha256 is invalid")
        if (
            isinstance(entry["size"], bool)
            or not isinstance(entry["size"], int)
            or entry["size"] < 0
            or not isinstance(entry["executable"], bool)
            or entry["role"] != role
            or entry["sensitivity"] != ROLE_SENSITIVITY[role]
        ):
            raise ReleaseError(f"{field} has an invalid role, size, mode, or sensitivity")
        used_licenses.add(_validate_id(entry["license_id"], field=f"{field}.license_id"))
    licenses = manifest["licenses"]
    if not isinstance(licenses, list) or not licenses:
        raise ReleaseError(f"{role} licenses must be a non-empty list")
    license_ids: set[str] = set()
    for index, raw_license in enumerate(licenses):
        field = f"{role} licenses[{index}]"
        license_record = _expect_exact_keys(
            raw_license,
            {"id", "terms", "redistribution", "notice_path"},
            field=field,
        )
        license_id = _validate_id(license_record["id"], field=f"{field}.id")
        if license_id in license_ids:
            raise ReleaseError(f"{role} licenses contain a duplicate id")
        license_ids.add(license_id)
        _validate_text(license_record["terms"], field=f"{field}.terms")
        if not isinstance(license_record["redistribution"], str) or license_record[
            "redistribution"
        ] not in {"allowed", "restricted", "review-required"}:
            raise ReleaseError(f"{field}.redistribution is invalid")
        notice = _validate_relative_path(
            license_record["notice_path"], field=f"{field}.notice_path"
        )
        if notice not in inventory_paths:
            raise ReleaseError(f"{role} license notice is not in source_inventory")
        if role == "challenge" and license_record["redistribution"] != "allowed":
            raise ReleaseError("Challenge Package contains a non-redistributable license")
    if license_ids != used_licenses:
        raise ReleaseError(f"{role} license inventory does not match source files")
    if role == "challenge":
        scoring = _expect_exact_keys(
            manifest["scoring_reference"],
            {"protocol_id", "version"},
            field="challenge scoring_reference",
        )
        _validate_id(scoring["protocol_id"], field="challenge scoring protocol_id")
        version = _validate_text(
            scoring["version"], field="challenge scoring version", maximum=100
        )
        if not SEMVER_PATTERN.fullmatch(version):
            raise ReleaseError("challenge scoring version is invalid")
    elif role == "evaluator":
        scoring = _expect_exact_keys(
            manifest["scoring_reference"],
            {
                "protocol_id",
                "version",
                "digest",
                "automatic_scope",
                "human_gate",
                "independent_reviewer_ref",
            },
            field="evaluator scoring_reference",
        )
        _validate_id(scoring["protocol_id"], field="evaluator scoring protocol_id")
        version = _validate_text(
            scoring["version"], field="evaluator scoring version", maximum=100
        )
        if not SEMVER_PATTERN.fullmatch(version):
            raise ReleaseError("evaluator scoring version is invalid")
        if not isinstance(scoring["digest"], str) or not HEX_SHA256.fullmatch(
            scoring["digest"]
        ) or scoring["digest"] == ZERO_SHA256:
            raise ReleaseError("evaluator scoring digest is invalid")
        for key in ("automatic_scope", "human_gate", "independent_reviewer_ref"):
            _validate_text(scoring[key], field=f"evaluator scoring {key}")
    for key in (
        "source_manifest_sha256",
        "challenge_manifest_sha256",
        "evaluator_manifest_sha256",
    ):
        if key in manifest and (
            not isinstance(manifest[key], str)
            or not HEX_SHA256.fullmatch(manifest[key])
            or manifest[key] == ZERO_SHA256
        ):
            raise ReleaseError(f"{role} package {key} is invalid")
    if control is not None and source_manifest is not None:
        for key in ("release_id", "case_id", "case_version"):
            if manifest[key] != control[key] or manifest[key] != source_manifest[key]:
                raise ReleaseError(f"{role} package identity binding is invalid")
        if manifest["created_at"] != source_manifest["created_at"]:
            raise ReleaseError(f"{role} package creation binding is invalid")
        if manifest["source_inventory"] != source_manifest["package_files"][role]:
            raise ReleaseError(f"{role} source inventory binding is invalid")
        if manifest["licenses"] != _role_license_records(source_manifest, role):
            raise ReleaseError(f"{role} license inventory binding is invalid")


def _validate_role_payload_inventory(
    manifest: dict[str, object],
    files: dict[str, FileBlob],
    *,
    role: str,
) -> None:
    generated = ROLE_GENERATED_FILES[role]
    actual_paths = set(files)
    if not generated.issubset(actual_paths):
        raise ReleaseError(f"{role} package is missing a generated boundary artifact")
    if files["verify_package.py"].data != _standalone_verifier():
        raise ReleaseError(f"{role} verifier does not match the trusted verifier")
    if files["RELEASE_BOUNDARY.md"].data != _role_boundary(role):
        raise ReleaseError(f"{role} release boundary does not match schema version 1")
    inventory = {
        str(entry["path"]): entry for entry in manifest["source_inventory"]
    }
    if actual_paths - generated != set(inventory):
        raise ReleaseError(f"{role} package contains an unbound payload file")
    for path, entry in inventory.items():
        blob = files[path]
        if (
            blob.sha256 != entry["sha256"]
            or blob.size != entry["size"]
            or blob.executable != entry["executable"]
        ):
            raise ReleaseError(f"{role} retained source inventory is invalid")


def _validate_challenge_leakage_record(
    manifest: dict[str, object],
    files: dict[str, FileBlob],
    *,
    private_values: Iterable[bytes] = (),
) -> None:
    leakage_blob = files.get("LEAKAGE_SCAN.json")
    if leakage_blob is None:
        raise ReleaseError("Challenge Package is missing its bounded leakage record")
    source_paths = [str(entry["path"]) for entry in manifest["source_inventory"]]
    source_files = {path: files[path].data for path in source_paths}
    expected = _scan_challenge(source_files, private_values=private_values)
    retained = _strict_json_bytes(
        leakage_blob.data, field="Challenge Package leakage record"
    )
    if (
        type(retained.get("schema_version")) is not int
        or type(retained.get("text_files_scanned")) is not int
        or type(retained.get("binary_files_path_only")) is not int
        or retained != expected
    ):
        raise ReleaseError(
            "Challenge Package leakage record does not match a fresh bounded scan"
        )


def _public_release_result(result: dict[str, object]) -> dict[str, object]:
    result.pop("_manifest", None)
    result.pop("_files", None)
    return result


def verify_export(bundle_value: Path | str) -> dict[str, object]:
    """Verify retained bytes for an Open Demo bundle or one role package."""

    bundle = _normalized_path(bundle_value)
    if _has_isolated_component(bundle):
        raise ReleaseError("refusing to verify a protected instructor-material path")
    try:
        if bundle.is_symlink():
            raise ReleaseError("release bundle must not be a symlink")
        canonical = bundle.resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as error:
        raise ReleaseError(f"could not resolve release bundle: {error}") from error
    if _has_isolated_component(canonical):
        raise ReleaseError("refusing to verify a protected instructor-material path")
    result = _verify_checksum_tree(canonical)
    manifest_type = result["manifest_type"]
    if not isinstance(manifest_type, str) or manifest_type not in {
        "rcsl-open-demo-package",
        "rcsl-role-package",
    }:
        raise ReleaseError("unsupported release package manifest type")
    manifest = result["_manifest"]
    if manifest_type == "rcsl-open-demo-package":
        _validate_open_demo_manifest(manifest)
        _validate_open_demo_record(manifest, result["_files"])
    else:
        role = result["package_role"]
        if not isinstance(role, str) or role not in ROLES:
            raise ReleaseError("unsupported role-package identity")
        _validate_role_manifest(manifest, role=role)
        _validate_role_payload_inventory(
            manifest, result["_files"], role=role
        )
        if role == "challenge":
            _validate_challenge_leakage_record(manifest, result["_files"])
    return _public_release_result(result)


def verify_blind_staging(staging_value: Path | str) -> dict[str, object]:
    """Verify all three local candidates and their private control bindings."""

    staging = _normalized_path(staging_value)
    if _has_isolated_component(staging):
        raise ReleaseError("refusing a protected instructor-material staging path")
    try:
        if staging.is_symlink():
            raise ReleaseError("blind staging must not be a symlink")
        canonical = staging.resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as error:
        raise ReleaseError(f"could not resolve blind staging: {error}") from error
    if _has_isolated_component(canonical):
        raise ReleaseError("refusing a protected instructor-material staging path")
    _validate_blind_staging_root(canonical)
    _validate_private_staging_permissions(canonical)
    control_data = _read_regular_path(
        canonical / "CONTROL_MANIFEST.json",
        label="blind staging control manifest",
        maximum_bytes=MAX_MANIFEST_BYTES,
    )
    control = _strict_json_bytes(control_data, field="blind staging control manifest")
    expected_control_keys = {
        "schema_version",
        "manifest_type",
        "release_id",
        "case_id",
        "case_version",
        "assembly_state",
        "source_manifest_sha256",
        "build_record_sha256",
        "packages",
        "source_summaries",
        "operational_gates_remaining",
        "scientific_correctness",
        "measurement_validity",
    }
    _expect_exact_keys(control, expected_control_keys, field="blind staging control manifest")
    _require_schema_version(
        control["schema_version"], field="blind staging control manifest"
    )
    if (
        control["manifest_type"] != "rcsl-blind-staging"
        or control["assembly_state"] != "assembled-awaiting-controlled-placement"
        or control["scientific_correctness"] != "not_assessed"
        or control["measurement_validity"] != "not_assessed"
    ):
        raise ReleaseError("blind staging control boundary is invalid")
    for key in ("release_id", "case_id"):
        _validate_id(control[key], field=f"blind staging {key}")
    version = _validate_text(
        control["case_version"], field="blind staging case_version", maximum=100
    )
    if not SEMVER_PATTERN.fullmatch(version):
        raise ReleaseError("blind staging case_version is invalid")
    for field in ("source_manifest_sha256", "build_record_sha256"):
        if not isinstance(control[field], str) or not HEX_SHA256.fullmatch(control[field]):
            raise ReleaseError(f"blind staging {field} is invalid")
    _expect_text_list(
        control["operational_gates_remaining"],
        field="blind staging operational_gates_remaining",
    )
    if control["operational_gates_remaining"] != list(OPERATIONAL_GATES_REMAINING):
        raise ReleaseError("blind staging operational gates are incomplete")
    build_record_data = _read_regular_path(
        canonical / "BUILD_RECORD.json",
        label="blind staging build record",
        maximum_bytes=MAX_MANIFEST_BYTES,
    )
    if _sha256_bytes(build_record_data) != control["build_record_sha256"]:
        raise ReleaseError("blind staging build record digest mismatch")
    build_record = _strict_json_bytes(build_record_data, field="blind staging build record")
    _expect_exact_keys(
        build_record,
        {
            "schema_version",
            "record_type",
            "built_at",
            "declared_actor",
            "actor_authentication",
            "tool_revision",
            "tool_revision_scope",
            "tool_worktree_state",
            "packager_sha256",
            "verifier_sha256",
            "network_used",
            "package_code_executed",
            "assembly_state",
        },
        field="blind staging build record",
    )
    _require_schema_version(
        build_record["schema_version"], field="blind staging build record"
    )
    if (
        build_record["record_type"] != "rcsl-local-blind-assembly"
        or build_record["actor_authentication"] != "not_performed"
        or build_record["tool_revision_scope"]
        != "repository-head-not-byte-identity"
        or not isinstance(build_record["tool_worktree_state"], str)
        or build_record["tool_worktree_state"] not in {"clean", "dirty"}
        or build_record["network_used"] is not False
        or build_record["package_code_executed"] is not False
        or build_record["assembly_state"] != control["assembly_state"]
    ):
        raise ReleaseError("blind staging build record boundary is invalid")
    _validate_timestamp(build_record["built_at"], field="blind staging built_at")
    _validate_text(build_record["declared_actor"], field="blind staging declared_actor")
    if not isinstance(build_record["tool_revision"], str) or not GIT_REVISION.fullmatch(
        build_record["tool_revision"]
    ):
        raise ReleaseError("blind staging tool revision is invalid")
    if (
        not isinstance(build_record["packager_sha256"], str)
        or not HEX_SHA256.fullmatch(build_record["packager_sha256"])
        or build_record["packager_sha256"] != _packager_sha256()
    ):
        raise ReleaseError("blind staging packager digest is invalid")
    expected_verifier_sha256 = _sha256_bytes(_standalone_verifier())
    if (
        not isinstance(build_record["verifier_sha256"], str)
        or not HEX_SHA256.fullmatch(build_record["verifier_sha256"])
        or build_record["verifier_sha256"] != expected_verifier_sha256
    ):
        raise ReleaseError("blind staging verifier digest is invalid")
    packages = _expect_exact_keys(
        control["packages"], set(ROLES), field="blind staging packages"
    )
    role_results: dict[str, dict[str, object]] = {}
    role_manifests: dict[str, dict[str, object]] = {}
    role_files: dict[str, dict[str, FileBlob]] = {}
    for role in ROLES:
        role_root = canonical / role
        result = _verify_checksum_tree(role_root)
        if result["package_role"] != role:
            raise ReleaseError("blind staging package role does not match its directory")
        binding = _expect_exact_keys(
            packages[role],
            {"manifest_sha256", "checksums_sha256"},
            field=f"blind staging packages.{role}",
        )
        if (
            binding["manifest_sha256"] != result["manifest_sha256"]
            or binding["checksums_sha256"] != result["checksums_sha256"]
        ):
            raise ReleaseError("blind staging package binding mismatch")
        role_manifests[role] = result["_manifest"]
        role_files[role] = result["_files"]
        role_results[role] = _public_release_result(result)

    source_manifest_blob = role_files["maintainer"].get("BLIND_SOURCE.json")
    if source_manifest_blob is None:
        raise ReleaseError("Maintainer Record is missing the frozen source manifest")
    if source_manifest_blob.sha256 != control["source_manifest_sha256"]:
        raise ReleaseError("blind staging source manifest digest mismatch")
    source_manifest = _validate_blind_manifest(
        _strict_json_bytes(source_manifest_blob.data, field="retained blind source manifest")
    )
    for key in ("release_id", "case_id", "case_version"):
        if source_manifest[key] != control[key]:
            raise ReleaseError("blind staging source identity binding is invalid")

    summaries = _expect_exact_keys(
        control["source_summaries"], set(ROLES), field="blind staging source_summaries"
    )
    for role in ROLES:
        summary = _expect_exact_keys(
            summaries[role],
            {"file_count", "byte_count", "root_digest"},
            field=f"blind staging source_summaries.{role}",
        )
        entries = source_manifest["package_files"][role]
        if (
            isinstance(summary["file_count"], bool)
            or not isinstance(summary["file_count"], int)
            or isinstance(summary["byte_count"], bool)
            or not isinstance(summary["byte_count"], int)
            or summary["file_count"] != len(entries)
            or summary["byte_count"] != sum(int(entry["size"]) for entry in entries)
            or summary["root_digest"]
            != source_manifest["source_bindings"][role]["root_digest"]
        ):
            raise ReleaseError("blind staging source summary binding is invalid")

    for role in ROLES:
        _validate_role_manifest(
            role_manifests[role],
            role=role,
            control=control,
            source_manifest=source_manifest,
        )
        _validate_role_payload_inventory(
            role_manifests[role], role_files[role], role=role
        )

    challenge_manifest_digest = packages["challenge"]["manifest_sha256"]
    evaluator_manifest_digest = packages["evaluator"]["manifest_sha256"]
    source_manifest_digest = control["source_manifest_sha256"]
    challenge_scoring = _expect_exact_keys(
        role_manifests["challenge"]["scoring_reference"],
        {"protocol_id", "version"},
        field="challenge scoring_reference",
    )
    if challenge_scoring != {
        "protocol_id": source_manifest["scoring"]["protocol_id"],
        "version": source_manifest["scoring"]["version"],
    }:
        raise ReleaseError("Challenge Package scoring reference is invalid")
    evaluator_manifest = role_manifests["evaluator"]
    if (
        evaluator_manifest["source_manifest_sha256"] != source_manifest_digest
        or evaluator_manifest["challenge_manifest_sha256"]
        != challenge_manifest_digest
        or evaluator_manifest["scoring_reference"] != source_manifest["scoring"]
    ):
        raise ReleaseError("Evaluator Package controlled binding is invalid")
    maintainer_manifest = role_manifests["maintainer"]
    if (
        maintainer_manifest["source_manifest_sha256"] != source_manifest_digest
        or maintainer_manifest["challenge_manifest_sha256"]
        != challenge_manifest_digest
        or maintainer_manifest["evaluator_manifest_sha256"]
        != evaluator_manifest_digest
    ):
        raise ReleaseError("Maintainer Record controlled binding is invalid")

    _validate_challenge_leakage_record(
        role_manifests["challenge"],
        role_files["challenge"],
        private_values=_challenge_private_values(source_manifest),
    )

    challenge_manifest_data = _read_regular_path(
        canonical / "challenge" / "PACKAGE_MANIFEST.json",
        label="Challenge Package manifest",
        maximum_bytes=MAX_MANIFEST_BYTES,
    )
    challenge_manifest = _strict_json_bytes(
        challenge_manifest_data, field="Challenge Package manifest"
    )
    forbidden_public_fields = {
        "source_manifest_sha256",
        "challenge_manifest_sha256",
        "evaluator_manifest_sha256",
        "scoring_digest",
    }
    if not forbidden_public_fields.isdisjoint(challenge_manifest):
        raise ReleaseError("Challenge Package exposes a controlled binding")
    controlled_digests = {
        str(source_manifest_digest).encode("ascii"),
        str(evaluator_manifest_digest).encode("ascii"),
        str(packages["maintainer"]["manifest_sha256"]).encode("ascii"),
    }
    if any(
        digest in blob.data
        for digest in controlled_digests
        for blob in role_files["challenge"].values()
    ):
        raise ReleaseError("Challenge Package exposes a controlled package digest")
    return {
        "integrity_status": "pass",
        "assembly_state": control["assembly_state"],
        "release_id": control["release_id"],
        "packages": role_results,
        "operational_release": "not_approved",
        "scientific_correctness": "not_assessed",
        "measurement_validity": "not_assessed",
    }


__all__ = (
    "APPROVAL_GATES",
    "ReleaseError",
    "ROLES",
    "export_open_demo",
    "package_blind",
    "verify_blind_staging",
    "verify_export",
)
