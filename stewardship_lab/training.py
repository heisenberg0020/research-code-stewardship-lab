"""Local-first progress records for the public RCSL training curriculum.

This module deliberately performs structural checks only. It never opens isolated
instructor material, executes a candidate, or infers scientific correctness.
"""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
from typing import Iterator
import unicodedata
import uuid


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TRAINING_PACKAGE = REPOSITORY_ROOT / "LLM4SBR_research_audit_training_v2"
ASSET_DIRECTORY = REPOSITORY_ROOT / "skills" / "research-code-audit-training" / "assets"
PROGRESS_FILENAME = "progress.json"
LOCK_FILENAME = ".rcsl-progress.lock"
ISOLATED_DIRECTORY_NAME = "DO_NOT_OPEN_UNTIL_FINISHED"
WORKSPACE_TYPE = "rcsl-training-progress"
SCHEMA_VERSION = 1
CASE_ID = "rcsl/llm4sbr-research-audit-v2"
EXPOSURE_STATE = "open-demo-honor-isolation"
VALIDATOR_SCOPE = "structure-only; semantic and scientific assessment not performed"
MAX_WORKSHEET_BYTES = 1_000_000
MAX_PROGRESS_BYTES = 32_000_000
MAX_ATTEMPTS_PER_TARGET = 100
MAX_REVIEWS_PER_TARGET = 1_000
MAX_JSON_NESTING = 100

BANDS = ("Recognize", "Prove", "Direct", "Steward")
RATING_VALUES = ("not-observed", "partial", "demonstrated", "cannot-assess")
REVIEW_DECISIONS = ("pass", "revise", "blocked")

PASSPORT_HEADINGS = (
    "1. Decision identity and uncertainty",
    "2. First broken contract",
    "3. Evidence chain",
    "4. Why the artifact remains plausible",
    "5. Causal effect and claim boundary",
    "6. Delegation and human checkpoints",
    "7. Safe response and regression evidence",
    "8. Stakeholder communication",
)
CAPSTONE_HEADINGS = (
    "1. G0 stop and containment decision",
    "2. Incident triage and blast radius",
    "3. L1–L4 first-break map",
    "4. Evidence preservation and competing hypotheses",
    "5. Human–Agent delegation",
    "6. Claim and release boundary",
    "7. Remediation and prevention verification",
    "8. Stakeholder update",
    "9. Human sign-off",
)
TARGET_DEFINITIONS = {
    "L1": {"title": "Algorithm semantics", "headings": PASSPORT_HEADINGS},
    "L2": {"title": "Pipeline integrity", "headings": PASSPORT_HEADINGS},
    "L3": {"title": "Scientific validity", "headings": PASSPORT_HEADINGS},
    "L4": {"title": "Agent experiment governance", "headings": PASSPORT_HEADINGS},
    "capstone": {"title": "Cross-layer research incident", "headings": CAPSTONE_HEADINGS},
}
TARGETS = tuple(TARGET_DEFINITIONS)

RESOURCE_SOURCES = {
    "RUBRIC.md": ASSET_DIRECTORY / "maturity-rubric.md",
    "CAPSTONE_BRIEF.md": TRAINING_PACKAGE / "CAPSTONE_BRIEF.md",
}
PASSPORT_TEMPLATE = ASSET_DIRECTORY / "learner-evidence-passport-template.md"
CAPSTONE_TEMPLATE = ASSET_DIRECTORY / "capstone-response-template.md"

HEADING_PATTERN = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)
HTML_COMMENT_PATTERN = re.compile(r"<!--.*?(?:-->|\Z)", re.DOTALL)
RAW_HTML_BLOCK_PATTERN = re.compile(
    r"<(pre|script|style)\b[^>]*>.*?(?:</\1\s*>|\Z)",
    re.IGNORECASE | re.DOTALL,
)
PLACEHOLDER_PATTERN = re.compile(
    r"\{\{.*?\}\}|\[TODO\]|\[填写\]|待填写|^\s*(?:TODO|TBD)\s*$",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")

TOP_LEVEL_KEYS = {
    "schema_version",
    "workspace_type",
    "validator_scope",
    "case_id",
    "case_revision",
    "learner_label",
    "exposure_state",
    "created_at",
    "updated_at",
    "resources",
    "targets",
    "operations",
}
TARGET_KEYS = {"worksheet", "attempts", "reviews"}
ATTEMPT_KEYS = {
    "id",
    "created_at",
    "retry_of",
    "note",
    "worksheet_sha256",
    "worksheet_snapshot",
    "structure_assessment",
}
REVIEW_KEYS = {
    "id",
    "attempt_id",
    "attempt_sha256",
    "reviewer",
    "created_at",
    "decision",
    "ratings",
    "rationale",
    "strengths",
    "gaps",
}
OPERATION_KEYS = {"id", "kind", "target", "payload_sha256", "result_id"}
ASSESSMENT_KEYS = {
    "target",
    "structure_status",
    "required_sections",
    "present_sections",
    "missing_sections",
    "empty_sections",
    "placeholder_count",
    "semantic_assessment",
    "scientific_correctness",
    "maturity_assessment",
}


class TrainingError(RuntimeError):
    """A refused or invalid training-progress operation."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _normalized_path(value: Path | str) -> Path:
    return Path(os.path.abspath(os.fspath(Path(value).expanduser())))


def _has_isolated_component(path: Path) -> bool:
    isolated = ISOLATED_DIRECTORY_NAME.casefold()
    return any(part.casefold() == isolated for part in path.parts)


def _casefold_parts(path: Path) -> tuple[str, ...]:
    return tuple(part.casefold() for part in path.parts)


def _is_within(child: Path, parent: Path) -> bool:
    child_parts = _casefold_parts(child)
    parent_parts = _casefold_parts(parent)
    return len(child_parts) >= len(parent_parts) and child_parts[: len(parent_parts)] == parent_parts


def _resolved_without_reading_target(path: Path) -> Path:
    try:
        return path.resolve(strict=False)
    except (OSError, RuntimeError) as error:
        raise TrainingError(f"could not resolve path safely: {error}") from error


def _validate_workspace_location(value: Path | str, *, creating: bool) -> Path:
    workspace = _normalized_path(value)
    if _has_isolated_component(workspace):
        raise TrainingError("refusing an isolated instructor-material path")
    if not creating and workspace.is_symlink():
        raise TrainingError("training workspace must be a real directory, not a symlink")
    canonical = _resolved_without_reading_target(workspace)
    if _has_isolated_component(canonical):
        raise TrainingError("refusing a path that resolves into isolated instructor material")
    repository = REPOSITORY_ROOT.resolve()
    if _is_within(canonical, repository):
        raise TrainingError("training workspace must be outside the RCSL repository")
    return workspace


def _require_regular_file(path: Path, *, label: str, within: Path | None = None) -> None:
    try:
        metadata = path.lstat()
    except FileNotFoundError as error:
        raise TrainingError(f"missing {label}: {path}") from error
    if not stat.S_ISREG(metadata.st_mode) or path.is_symlink():
        raise TrainingError(f"{label} must be a regular file, not a symlink: {path}")
    if within is not None:
        canonical = _resolved_without_reading_target(path)
        if not _is_within(canonical, within.resolve()):
            raise TrainingError(f"{label} resolves outside the training workspace")
        if _has_isolated_component(canonical):
            raise TrainingError(f"{label} resolves into isolated instructor material")


def _directory_open_flags() -> int:
    return os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)


def _file_open_flags() -> int:
    return os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)


def _open_directory_chain(path: Path) -> int:
    """Open an absolute directory one non-symlink component at a time."""

    if not path.is_absolute():
        raise TrainingError("internal path safety error: expected an absolute directory")
    descriptor = os.open(path.anchor, _directory_open_flags())
    try:
        for component in path.parts[1:]:
            next_descriptor = os.open(component, _directory_open_flags(), dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        metadata = os.fstat(descriptor)
        if not stat.S_ISDIR(metadata.st_mode):
            raise TrainingError(f"training workspace is not a real directory: {path}")
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _validate_relative_file_path(relative_value: str, *, label: str) -> Path:
    relative = Path(relative_value)
    if (
        relative.is_absolute()
        or not relative.parts
        or any(part in {"", ".", ".."} for part in relative.parts)
        or _has_isolated_component(relative)
    ):
        raise TrainingError(f"{label} has an unsafe workspace-relative path")
    return relative


def _read_from_directory_fd(
    root_descriptor: int,
    relative_value: str,
    *,
    label: str,
    maximum_bytes: int,
) -> bytes:
    """Read one relative regular file beneath an already verified directory fd."""

    relative = _validate_relative_file_path(relative_value, label=label)
    directory_descriptor: int | None = os.dup(root_descriptor)
    file_descriptor: int | None = None
    try:
        for component in relative.parts[:-1]:
            next_descriptor = os.open(
                component, _directory_open_flags(), dir_fd=directory_descriptor
            )
            os.close(directory_descriptor)
            directory_descriptor = next_descriptor
        file_descriptor = os.open(
            relative.parts[-1], _file_open_flags(), dir_fd=directory_descriptor
        )
        metadata = os.fstat(file_descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise TrainingError(f"{label} must be a regular file, not a symlink")
        if metadata.st_size > maximum_bytes:
            raise TrainingError(f"{label} exceeds the {maximum_bytes}-byte local safety limit")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(file_descriptor, min(65_536, maximum_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > maximum_bytes:
                raise TrainingError(f"{label} exceeds the {maximum_bytes}-byte local safety limit")
        return b"".join(chunks)
    except TrainingError:
        raise
    except OSError as error:
        raise TrainingError(
            f"{label} must be a readable regular file reached without symlinks: {error}"
        ) from error
    finally:
        if file_descriptor is not None:
            os.close(file_descriptor)
        if directory_descriptor is not None:
            os.close(directory_descriptor)


def _open_verified_root(
    root: Path,
    *,
    allow_repository_root: bool = False,
) -> int:
    try:
        canonical_root = root.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise TrainingError(f"could not resolve training workspace safely: {error}") from error
    if _has_isolated_component(canonical_root) or (
        not allow_repository_root
        and _is_within(canonical_root, REPOSITORY_ROOT.resolve())
    ):
        raise TrainingError("training workspace crossed a protected path boundary")
    try:
        return _open_directory_chain(canonical_root)
    except TrainingError:
        raise
    except OSError as error:
        raise TrainingError(f"could not open training workspace safely: {error}") from error


def _read_workspace_bytes(
    workspace: Path,
    relative_value: str,
    *,
    label: str,
    maximum_bytes: int,
    allow_repository_root: bool = False,
) -> bytes:
    """Read a workspace file through dir fds without following symlinks."""

    root_descriptor = _open_verified_root(
        workspace, allow_repository_root=allow_repository_root
    )
    try:
        return _read_from_directory_fd(
            root_descriptor,
            relative_value,
            label=label,
            maximum_bytes=maximum_bytes,
        )
    finally:
        os.close(root_descriptor)


def _read_text_from_directory_fd(
    root_descriptor: int,
    relative_value: str,
    *,
    label: str,
    maximum_bytes: int,
) -> str:
    data = _read_from_directory_fd(
        root_descriptor,
        relative_value,
        label=label,
        maximum_bytes=maximum_bytes,
    )
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise TrainingError(f"{label} must be valid UTF-8") from error


def _read_workspace_text(
    workspace: Path,
    relative_value: str,
    *,
    label: str,
    maximum_bytes: int,
    allow_repository_root: bool = False,
) -> str:
    data = _read_workspace_bytes(
        workspace,
        relative_value,
        label=label,
        maximum_bytes=maximum_bytes,
        allow_repository_root=allow_repository_root,
    )
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise TrainingError(f"{label} must be valid UTF-8") from error


def _validate_label(value: str, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TrainingError(f"{field} must be a non-empty declared label")
    if len(value) > 200 or any(ord(character) < 32 for character in value):
        raise TrainingError(f"{field} contains unsupported control characters or is too long")
    return value.strip()


def _validate_text(value: str, *, field: str, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise TrainingError(f"{field} must be text")
    cleaned = value.strip()
    if not allow_empty and not cleaned:
        raise TrainingError(f"{field} must not be empty")
    if len(value) > 20_000:
        raise TrainingError(f"{field} is too long")
    forbidden_controls = {"\x00", "\x1b", "\u202a", "\u202b", "\u202d", "\u202e", "\u2066", "\u2067", "\u2068", "\u2069"}
    if any(character in value for character in forbidden_controls):
        raise TrainingError(f"{field} contains unsupported control characters")
    return cleaned if not allow_empty else value.strip()


def _validate_id(value: str, *, field: str) -> str:
    if not isinstance(value, str) or not ID_PATTERN.fullmatch(value):
        raise TrainingError(f"{field} must match {ID_PATTERN.pattern}")
    return value


def _validate_timestamp(value: object, *, field: str) -> None:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise TrainingError(f"{field} must be a UTC RFC3339 timestamp")
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise TrainingError(f"{field} must be a UTC RFC3339 timestamp") from error


def _strict_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise TrainingError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise TrainingError(f"non-finite JSON value is not allowed: {value}")


def _reject_excessive_json_nesting(text: str) -> None:
    """Bound parser work consistently across Python JSON implementations."""

    depth = 0
    in_string = False
    escaped = False
    for character in text:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character in "[{":
            depth += 1
            if depth > MAX_JSON_NESTING:
                raise TrainingError(
                    f"invalid progress JSON: nesting exceeds {MAX_JSON_NESTING} levels"
                )
        elif character in "]}":
            depth = max(0, depth - 1)


def _strict_json_loads(text: str) -> dict[str, object]:
    try:
        _reject_excessive_json_nesting(text)
        value = json.loads(
            text,
            object_pairs_hook=_strict_object,
            parse_constant=_reject_constant,
        )
    except TrainingError:
        raise
    except (json.JSONDecodeError, UnicodeError, RecursionError, ValueError) as error:
        raise TrainingError(f"invalid progress JSON: {error}") from error
    if not isinstance(value, dict):
        raise TrainingError("progress JSON must contain one object")
    return value


def _expect_exact_keys(value: object, expected: set[str], *, field: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TrainingError(f"{field} must be an object")
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        details = []
        if missing:
            details.append(f"missing fields {missing}")
        if extra:
            details.append(f"unexpected fields {extra}")
        raise TrainingError(f"{field}: {'; '.join(details)}")
    return value


def _expect_string_list(value: object, *, field: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise TrainingError(f"{field} must be a list of strings")
    return value


def _visible_markdown(content: str) -> str:
    """Remove HTML comments and fenced code before structural heading checks."""

    uncommented = HTML_COMMENT_PATTERN.sub("", content)
    uncommented = RAW_HTML_BLOCK_PATTERN.sub("", uncommented)
    visible: list[str] = []
    fence_character: str | None = None
    fence_length = 0
    for line in uncommented.splitlines(keepends=True):
        stripped = line.lstrip()
        fence_match = re.match(r"(`{3,}|~{3,})", stripped)
        if fence_character is None and fence_match:
            marker = fence_match.group(1)
            fence_character = marker[0]
            fence_length = len(marker)
            visible.append("\n" if line.endswith(("\n", "\r")) else "")
            continue
        if fence_character is not None:
            closing = re.match(rf"{re.escape(fence_character)}{{{fence_length},}}\s*$", stripped)
            if closing:
                fence_character = None
                fence_length = 0
            visible.append("\n" if line.endswith(("\n", "\r")) else "")
            continue
        visible.append(line)
    return "".join(visible)


def _headings(content: str) -> list[str]:
    return [
        match.group(1).strip().rstrip("#").strip()
        for match in HEADING_PATTERN.finditer(content)
    ]


def _section_body(content: str, heading: str) -> str:
    pattern = re.compile(
        rf"^#{{1,6}}\s+{re.escape(heading)}\s*$\n(.*?)(?=^#{{1,6}}\s+|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(content)
    return match.group(1).strip() if match else ""


def _assess_text(target: str, content: str) -> dict[str, object]:
    if target not in TARGET_DEFINITIONS:
        raise TrainingError(f"unknown training target: {target}")
    required = list(TARGET_DEFINITIONS[target]["headings"])
    visible_content = _visible_markdown(content)
    present_source = _headings(visible_content)
    present = [heading for heading in required if heading in present_source]
    missing = [heading for heading in required if heading not in present_source]
    empty = [heading for heading in present if not _section_body(visible_content, heading)]
    placeholder_count = len(PLACEHOLDER_PATTERN.findall(content))
    complete = not missing and not empty and placeholder_count == 0
    return {
        "target": target,
        "structure_status": "complete" if complete else "incomplete",
        "required_sections": required,
        "present_sections": present,
        "missing_sections": missing,
        "empty_sections": empty,
        "placeholder_count": placeholder_count,
        "semantic_assessment": "not_performed",
        "scientific_correctness": "not_assessed",
        "maturity_assessment": "not_performed",
    }


def _case_revision() -> str:
    result = subprocess.run(
        ("git", "-C", str(REPOSITORY_ROOT), "rev-parse", "HEAD"),
        capture_output=True,
        text=True,
        check=False,
    )
    revision = result.stdout.strip()
    return revision if result.returncode == 0 and revision else "unavailable-local-source-revision"


def _workspace_readme() -> str:
    return """# RCSL Local Training Workspace

This directory belongs to the learner. It is intentionally outside the RCSL source
repository. Edit the Markdown files in `worksheets/`, then use the `train progress`
commands to check structure, freeze attempts, record named human reviews, resume,
and export a redacted summary.

Automatic checks assess structure only. They do not inspect instructor material,
judge an answer, verify scientific correctness, authenticate a reviewer, or grant a
maturity band. This public case uses honor isolation and is not a verified blind
challenge. `progress.json` has local integrity checks but is not tamper-proof.
"""


def _write_new_file(path: Path, data: bytes, *, mode: int = 0o600) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        handle = os.fdopen(descriptor, "wb")
        descriptor = -1
        with handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


def _write_new_file_from_directory_fd(
    root_descriptor: int,
    relative_value: str,
    data: bytes,
    *,
    label: str,
    mode: int = 0o600,
) -> None:
    """Create one file beneath a pinned root without following parent symlinks."""

    relative = _validate_relative_file_path(relative_value, label=label)
    directory_descriptor: int | None = os.dup(root_descriptor)
    file_descriptor: int | None = None
    created_identity: tuple[int, int] | None = None
    completed = False
    try:
        for component in relative.parts[:-1]:
            next_descriptor = os.open(
                component, _directory_open_flags(), dir_fd=directory_descriptor
            )
            os.close(directory_descriptor)
            directory_descriptor = next_descriptor
        file_descriptor = os.open(
            relative.parts[-1],
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0),
            mode,
            dir_fd=directory_descriptor,
        )
        metadata = os.fstat(file_descriptor)
        created_identity = (metadata.st_dev, metadata.st_ino)
        with os.fdopen(file_descriptor, "wb") as handle:
            file_descriptor = None
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.fsync(directory_descriptor)
        completed = True
    except FileExistsError as error:
        raise TrainingError(f"refusing to overwrite existing {label}") from error
    except OSError as error:
        raise TrainingError(f"could not safely create {label}: {error}") from error
    finally:
        if file_descriptor is not None:
            try:
                os.close(file_descriptor)
            except OSError:
                pass
            file_descriptor = None
        if (
            not completed
            and created_identity is not None
            and directory_descriptor is not None
        ):
            try:
                current = os.stat(
                    relative.parts[-1],
                    dir_fd=directory_descriptor,
                    follow_symlinks=False,
                )
                if (current.st_dev, current.st_ino) == created_identity:
                    os.unlink(relative.parts[-1], dir_fd=directory_descriptor)
            except OSError:
                pass
        if directory_descriptor is not None:
            os.close(directory_descriptor)


def _atomic_write_progress(
    workspace_descriptor: int, progress: dict[str, object]
) -> None:
    try:
        destination_metadata = os.stat(
            PROGRESS_FILENAME,
            dir_fd=workspace_descriptor,
            follow_symlinks=False,
        )
    except OSError as error:
        raise TrainingError(f"could not verify {PROGRESS_FILENAME}: {error}") from error
    if not stat.S_ISREG(destination_metadata.st_mode):
        raise TrainingError(f"{PROGRESS_FILENAME} must remain a regular file")
    data = (
        json.dumps(progress, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode("utf-8")
    if len(data) > MAX_PROGRESS_BYTES:
        raise TrainingError(
            f"progress record exceeds the {MAX_PROGRESS_BYTES}-byte local safety limit"
        )
    temporary = f".{PROGRESS_FILENAME}.tmp-{uuid.uuid4().hex}"
    descriptor: int | None = None
    temporary_identity: tuple[int, int] | None = None
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
            dir_fd=workspace_descriptor,
        )
        temporary_metadata = os.fstat(descriptor)
        temporary_identity = (temporary_metadata.st_dev, temporary_metadata.st_ino)
        handle = os.fdopen(descriptor, "wb")
        descriptor = None
        with handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(
            temporary,
            PROGRESS_FILENAME,
            src_dir_fd=workspace_descriptor,
            dst_dir_fd=workspace_descriptor,
        )
        try:
            os.fsync(workspace_descriptor)
        except OSError:
            # The namespace update is already visible and the new file data was
            # synced. Reporting a refusal here would invite a duplicate retry,
            # especially when the caller used an automatically generated operation
            # ID. Treat the committed replace as authoritative.
            pass
    except OSError as error:
        raise TrainingError(f"could not atomically update {PROGRESS_FILENAME}: {error}") from error
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        if temporary_identity is not None:
            try:
                current = os.stat(
                    temporary,
                    dir_fd=workspace_descriptor,
                    follow_symlinks=False,
                )
                if (current.st_dev, current.st_ino) == temporary_identity:
                    os.unlink(temporary, dir_fd=workspace_descriptor)
            except FileNotFoundError:
                pass
            except OSError:
                # Preserve the original write error. A uniquely named leftover file
                # is harmless and can be inspected rather than masking the refusal.
                pass


@contextmanager
def _exclusive_lock(workspace: Path) -> Iterator[int]:
    workspace_descriptor = _open_verified_root(workspace)
    token = uuid.uuid4().hex
    lock_identity: tuple[int, int] | None = None
    descriptor: int | None = None
    operation_succeeded = False
    cleanup_error: OSError | None = None
    try:
        try:
            descriptor = os.open(
                LOCK_FILENAME,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
                dir_fd=workspace_descriptor,
            )
        except FileExistsError as error:
            raise TrainingError(
                f"training workspace is busy; inspect and remove {LOCK_FILENAME} only after confirming no writer is active"
            ) from error
        except OSError as error:
            raise TrainingError(f"could not create the training workspace lock: {error}") from error
        try:
            try:
                metadata = os.fstat(descriptor)
                lock_identity = (metadata.st_dev, metadata.st_ino)
                payload = (
                    json.dumps(
                        {"token": token, "pid": os.getpid(), "created_at": _utc_now()}
                    )
                    + "\n"
                ).encode("utf-8")
                offset = 0
                while offset < len(payload):
                    written = os.write(descriptor, payload[offset:])
                    if written <= 0:
                        raise OSError("lock write made no progress")
                    offset += written
                os.fsync(descriptor)
                os.fsync(workspace_descriptor)
            except OSError as error:
                raise TrainingError(
                    f"could not establish the training workspace lock: {error}"
                ) from error

            yield workspace_descriptor
            operation_succeeded = True
        finally:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError as error:
                    cleanup_error = error
            try:
                current = os.stat(
                    LOCK_FILENAME,
                    dir_fd=workspace_descriptor,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                current = None
            except OSError as error:
                current = None
                cleanup_error = cleanup_error or error
            if (
                current is not None
                and lock_identity is not None
                and (current.st_dev, current.st_ino) == lock_identity
            ):
                try:
                    os.unlink(LOCK_FILENAME, dir_fd=workspace_descriptor)
                    os.fsync(workspace_descriptor)
                except OSError as error:
                    cleanup_error = cleanup_error or error
            if operation_succeeded and cleanup_error is not None:
                raise TrainingError(
                    f"operation completed but the training workspace lock could not be cleaned up: {cleanup_error}"
                ) from cleanup_error
    finally:
        try:
            os.close(workspace_descriptor)
        except OSError:
            # Never replace a more useful operation or lock-cleanup exception.
            pass


def initialize_workspace(output: Path | str, *, learner_label: str) -> dict[str, object]:
    """Create a new external progress workspace from public assets only."""

    learner = _validate_label(learner_label, field="learner label")
    workspace = _validate_workspace_location(output, creating=True)
    if os.path.lexists(workspace):
        raise TrainingError(f"output already exists; refusing to overwrite: {workspace}")

    sources = dict(RESOURCE_SOURCES)
    sources["learner-evidence-passport-template.md"] = PASSPORT_TEMPLATE
    sources["capstone-response-template.md"] = CAPSTONE_TEMPLATE
    source_data: dict[str, bytes] = {}
    for label, source in sources.items():
        if _has_isolated_component(source):
            raise TrainingError("public training source unexpectedly enters isolated material")
        try:
            relative_source = source.relative_to(REPOSITORY_ROOT).as_posix()
        except ValueError as error:
            raise TrainingError("public training source is outside the RCSL repository") from error
        source_data[label] = _read_workspace_bytes(
            REPOSITORY_ROOT,
            relative_source,
            label=f"public source asset {label}",
            maximum_bytes=MAX_WORKSHEET_BYTES,
            allow_repository_root=True,
        )

    workspace.parent.mkdir(parents=True, exist_ok=True)
    workspace.mkdir(mode=0o700)
    try:
        worksheets = workspace / "worksheets"
        worksheets.mkdir(mode=0o700)
        _write_new_file(workspace / "README.md", _workspace_readme().encode("utf-8"))

        resources: dict[str, str] = {}
        for destination_name in RESOURCE_SOURCES:
            data = source_data[destination_name]
            _write_new_file(workspace / destination_name, data)
            resources[destination_name] = _sha256_bytes(data)

        try:
            passport_template = source_data["learner-evidence-passport-template.md"].decode("utf-8")
            capstone_template = source_data["capstone-response-template.md"].decode("utf-8")
        except UnicodeDecodeError as error:
            raise TrainingError("public training templates must be valid UTF-8") from error
        targets: dict[str, object] = {}
        for target, definition in TARGET_DEFINITIONS.items():
            if target == "capstone":
                content = capstone_template
            else:
                content = passport_template.replace("[[TARGET_ID]]", target).replace(
                    "[[TARGET_TITLE]]", str(definition["title"])
                )
            relative_path = f"worksheets/{target}.md"
            _write_new_file(workspace / relative_path, content.encode("utf-8"))
            targets[target] = {"worksheet": relative_path, "attempts": [], "reviews": []}

        timestamp = _utc_now()
        progress: dict[str, object] = {
            "schema_version": SCHEMA_VERSION,
            "workspace_type": WORKSPACE_TYPE,
            "validator_scope": VALIDATOR_SCOPE,
            "case_id": CASE_ID,
            "case_revision": _case_revision(),
            "learner_label": learner,
            "exposure_state": EXPOSURE_STATE,
            "created_at": timestamp,
            "updated_at": timestamp,
            "resources": resources,
            "targets": targets,
            "operations": [],
        }
        data = (
            json.dumps(progress, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"
        ).encode("utf-8")
        _write_new_file(workspace / PROGRESS_FILENAME, data)
        return deepcopy(progress)
    except BaseException:
        shutil.rmtree(workspace)
        raise


def _validate_assessment(value: object, *, target: str, snapshot: str, field: str) -> None:
    assessment = _expect_exact_keys(value, ASSESSMENT_KEYS, field=field)
    _expect_string_list(assessment["required_sections"], field=f"{field}.required_sections")
    _expect_string_list(assessment["present_sections"], field=f"{field}.present_sections")
    _expect_string_list(assessment["missing_sections"], field=f"{field}.missing_sections")
    _expect_string_list(assessment["empty_sections"], field=f"{field}.empty_sections")
    if isinstance(assessment["placeholder_count"], bool) or not isinstance(assessment["placeholder_count"], int):
        raise TrainingError(f"{field}.placeholder_count must be an integer")
    expected = _assess_text(target, snapshot)
    if assessment != expected:
        raise TrainingError(f"{field} does not match the frozen worksheet snapshot")


def _validate_progress(
    progress: dict[str, object],
    workspace: Path,
    *,
    workspace_descriptor: int | None = None,
) -> None:
    def read_bytes(relative: str, *, label: str, maximum_bytes: int) -> bytes:
        if workspace_descriptor is None:
            return _read_workspace_bytes(
                workspace, relative, label=label, maximum_bytes=maximum_bytes
            )
        return _read_from_directory_fd(
            workspace_descriptor, relative, label=label, maximum_bytes=maximum_bytes
        )

    def read_text(relative: str, *, label: str, maximum_bytes: int) -> str:
        if workspace_descriptor is None:
            return _read_workspace_text(
                workspace, relative, label=label, maximum_bytes=maximum_bytes
            )
        return _read_text_from_directory_fd(
            workspace_descriptor, relative, label=label, maximum_bytes=maximum_bytes
        )

    _expect_exact_keys(progress, TOP_LEVEL_KEYS, field="progress")
    if type(progress["schema_version"]) is not int or progress["schema_version"] != SCHEMA_VERSION:
        raise TrainingError(f"unsupported progress schema version: {progress['schema_version']!r}")
    if progress["workspace_type"] != WORKSPACE_TYPE:
        raise TrainingError("not an RCSL training-progress workspace")
    if progress["validator_scope"] != VALIDATOR_SCOPE:
        raise TrainingError("validator scope has changed or is invalid")
    if progress["case_id"] != CASE_ID:
        raise TrainingError("training case ID has changed or is invalid")
    _validate_text(progress["case_revision"], field="case revision")
    _validate_label(progress["learner_label"], field="learner label")
    if progress["exposure_state"] != EXPOSURE_STATE:
        raise TrainingError("public training exposure state must remain honor isolation")
    _validate_timestamp(progress["created_at"], field="created_at")
    _validate_timestamp(progress["updated_at"], field="updated_at")

    resources = _expect_exact_keys(progress["resources"], set(RESOURCE_SOURCES), field="resources")
    for filename in RESOURCE_SOURCES:
        digest = resources[filename]
        if not isinstance(digest, str) or not HEX_SHA256.fullmatch(digest):
            raise TrainingError(f"resources.{filename} must be a SHA-256 digest")
        data = read_bytes(
            filename,
            label=f"fixed resource {filename}",
            maximum_bytes=MAX_WORKSHEET_BYTES,
        )
        if _sha256_bytes(data) != digest:
            raise TrainingError(f"fixed resource digest mismatch: {filename}")

    targets = _expect_exact_keys(progress["targets"], set(TARGETS), field="targets")
    known_attempts: dict[str, set[str]] = {}
    known_reviews: dict[str, set[str]] = {}
    attempt_records: dict[tuple[str, str], dict[str, object]] = {}
    review_records: dict[tuple[str, str], dict[str, object]] = {}
    for target in TARGETS:
        target_record = _expect_exact_keys(targets[target], TARGET_KEYS, field=f"targets.{target}")
        expected_worksheet = f"worksheets/{target}.md"
        if target_record["worksheet"] != expected_worksheet:
            raise TrainingError(f"targets.{target}.worksheet must be {expected_worksheet}")
        read_text(
            expected_worksheet,
            label=f"{target} worksheet",
            maximum_bytes=MAX_WORKSHEET_BYTES,
        )

        attempts = target_record["attempts"]
        reviews = target_record["reviews"]
        if not isinstance(attempts, list) or not isinstance(reviews, list):
            raise TrainingError(f"targets.{target} attempts and reviews must be lists")
        if len(attempts) > MAX_ATTEMPTS_PER_TARGET:
            raise TrainingError(
                f"targets.{target} exceeds the {MAX_ATTEMPTS_PER_TARGET}-attempt safety limit"
            )
        if len(reviews) > MAX_REVIEWS_PER_TARGET:
            raise TrainingError(
                f"targets.{target} exceeds the {MAX_REVIEWS_PER_TARGET}-review safety limit"
            )
        attempt_ids: set[str] = set()
        previous_attempt: str | None = None
        for index, raw_attempt in enumerate(attempts, start=1):
            field = f"targets.{target}.attempts[{index - 1}]"
            attempt = _expect_exact_keys(raw_attempt, ATTEMPT_KEYS, field=field)
            expected_id = f"{target.upper()}-A{index:03d}"
            if attempt["id"] != expected_id:
                raise TrainingError(f"{field}.id must be {expected_id}")
            _validate_timestamp(attempt["created_at"], field=f"{field}.created_at")
            if attempt["retry_of"] != previous_attempt:
                raise TrainingError(f"{field}.retry_of must reference the previous attempt")
            _validate_text(attempt["note"], field=f"{field}.note", allow_empty=True)
            snapshot = attempt["worksheet_snapshot"]
            digest = attempt["worksheet_sha256"]
            if not isinstance(snapshot, str) or not isinstance(digest, str) or not HEX_SHA256.fullmatch(digest):
                raise TrainingError(f"{field} has an invalid worksheet snapshot or digest")
            if _sha256_text(snapshot) != digest:
                raise TrainingError(f"{field} worksheet digest mismatch")
            if len(snapshot.encode("utf-8")) > MAX_WORKSHEET_BYTES:
                raise TrainingError(f"{field} worksheet snapshot exceeds the local safety limit")
            _validate_assessment(attempt["structure_assessment"], target=target, snapshot=snapshot, field=f"{field}.structure_assessment")
            if attempt["structure_assessment"]["structure_status"] != "complete":
                raise TrainingError(f"{field} contains a structurally incomplete submission")
            attempt_ids.add(expected_id)
            attempt_records[(target, expected_id)] = attempt
            previous_attempt = expected_id
        known_attempts[target] = attempt_ids

        review_ids: set[str] = set()
        for index, raw_review in enumerate(reviews, start=1):
            field = f"targets.{target}.reviews[{index - 1}]"
            review = _expect_exact_keys(raw_review, REVIEW_KEYS, field=field)
            expected_id = f"{target.upper()}-R{index:03d}"
            if review["id"] != expected_id:
                raise TrainingError(f"{field}.id must be {expected_id}")
            if not isinstance(review["attempt_id"], str) or review["attempt_id"] not in attempt_ids:
                raise TrainingError(f"{field}.attempt_id references an unknown attempt")
            attempt = next(item for item in attempts if item["id"] == review["attempt_id"])
            if (
                not isinstance(review["attempt_sha256"], str)
                or not HEX_SHA256.fullmatch(review["attempt_sha256"])
                or review["attempt_sha256"] != attempt["worksheet_sha256"]
            ):
                raise TrainingError(f"{field}.attempt_sha256 does not match the frozen attempt digest")
            _validate_label(review["reviewer"], field=f"{field}.reviewer")
            _validate_timestamp(review["created_at"], field=f"{field}.created_at")
            if review["decision"] not in REVIEW_DECISIONS:
                raise TrainingError(f"{field}.decision is invalid")
            ratings = _expect_exact_keys(review["ratings"], set(BANDS), field=f"{field}.ratings")
            if any(ratings[band] not in RATING_VALUES for band in BANDS):
                raise TrainingError(f"{field}.ratings contains an invalid observation")
            for name in ("rationale", "strengths", "gaps"):
                _validate_text(review[name], field=f"{field}.{name}")
            _validate_pass_consistency(target, str(review["decision"]), ratings)
            review_ids.add(expected_id)
            review_records[(target, expected_id)] = review
        known_reviews[target] = review_ids

    operations = progress["operations"]
    if not isinstance(operations, list):
        raise TrainingError("operations must be a list")
    maximum_operations = len(TARGETS) * (
        MAX_ATTEMPTS_PER_TARGET + MAX_REVIEWS_PER_TARGET
    )
    if len(operations) > maximum_operations:
        raise TrainingError("operations exceeds the local history safety limit")
    operation_ids: set[str] = set()
    mapped_results: set[tuple[str, str, str]] = set()
    for index, raw_operation in enumerate(operations):
        field = f"operations[{index}]"
        operation = _expect_exact_keys(raw_operation, OPERATION_KEYS, field=field)
        operation_id = _validate_id(operation["id"], field=f"{field}.id")
        if operation_id in operation_ids:
            raise TrainingError(f"duplicate operation ID: {operation_id}")
        operation_ids.add(operation_id)
        if not isinstance(operation["kind"], str) or operation["kind"] not in ("submit", "review"):
            raise TrainingError(f"{field}.kind is invalid")
        if not isinstance(operation["target"], str) or operation["target"] not in TARGETS:
            raise TrainingError(f"{field}.target is invalid")
        digest = operation["payload_sha256"]
        if not isinstance(digest, str) or not HEX_SHA256.fullmatch(digest):
            raise TrainingError(f"{field}.payload_sha256 is invalid")
        known_results = known_attempts[operation["target"]] if operation["kind"] == "submit" else known_reviews[operation["target"]]
        if not isinstance(operation["result_id"], str) or operation["result_id"] not in known_results:
            raise TrainingError(f"{field}.result_id references an unknown result")
        result_key = (str(operation["kind"]), str(operation["target"]), str(operation["result_id"]))
        if result_key in mapped_results:
            raise TrainingError(f"{field}.result_id is mapped by more than one operation")
        mapped_results.add(result_key)

        if operation["kind"] == "submit":
            attempt = attempt_records[(operation["target"], operation["result_id"])]
            expected_payload = {
                "kind": "submit",
                "target": operation["target"],
                "note": attempt["note"],
                "worksheet_sha256": attempt["worksheet_sha256"],
            }
        else:
            review = review_records[(operation["target"], operation["result_id"])]
            expected_payload = {
                "kind": "review",
                "target": operation["target"],
                "attempt_id": review["attempt_id"],
                "attempt_sha256": review["attempt_sha256"],
                "reviewer": review["reviewer"],
                "decision": review["decision"],
                "ratings": review["ratings"],
                "rationale": review["rationale"],
                "strengths": review["strengths"],
                "gaps": review["gaps"],
            }
        if operation["payload_sha256"] != _payload_digest(expected_payload):
            raise TrainingError(f"{field}.payload_sha256 does not match its recorded result")

    expected_results = {
        ("submit", target, result_id)
        for target, result_ids in known_attempts.items()
        for result_id in result_ids
    } | {
        ("review", target, result_id)
        for target, result_ids in known_reviews.items()
        for result_id in result_ids
    }
    if mapped_results != expected_results:
        raise TrainingError("every attempt and review must have exactly one operation record")


def _load_progress_from_descriptor(
    workspace: Path, workspace_descriptor: int
) -> dict[str, object]:
    text = _read_text_from_directory_fd(
        workspace_descriptor,
        PROGRESS_FILENAME,
        label=PROGRESS_FILENAME,
        maximum_bytes=MAX_PROGRESS_BYTES,
    )
    progress = _strict_json_loads(text)
    _validate_progress(
        progress, workspace, workspace_descriptor=workspace_descriptor
    )
    return progress


def load_progress(workspace_value: Path | str) -> dict[str, object]:
    """Load and strictly verify one local training workspace."""

    workspace = _validate_workspace_location(workspace_value, creating=False)
    workspace_descriptor = _open_verified_root(workspace)
    try:
        return _load_progress_from_descriptor(workspace, workspace_descriptor)
    finally:
        os.close(workspace_descriptor)


def _worksheet_relative(progress: dict[str, object], target: str) -> str:
    if target not in TARGETS:
        raise TrainingError(f"unknown training target: {target}")
    relative = progress["targets"][target]["worksheet"]
    if not isinstance(relative, str):
        raise TrainingError(f"{target} worksheet path must be text")
    return relative


def check_worksheet(workspace_value: Path | str, target: str) -> dict[str, object]:
    """Check public worksheet structure without assessing its meaning."""

    workspace = _validate_workspace_location(workspace_value, creating=False)
    workspace_descriptor = _open_verified_root(workspace)
    try:
        progress = _load_progress_from_descriptor(workspace, workspace_descriptor)
        relative = _worksheet_relative(progress, target)
        content = _read_text_from_directory_fd(
            workspace_descriptor,
            relative,
            label=f"{target} worksheet",
            maximum_bytes=MAX_WORKSHEET_BYTES,
        )
        return _assess_text(target, content)
    finally:
        os.close(workspace_descriptor)


def _payload_digest(payload: dict[str, object]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return _sha256_text(serialized)


def _existing_operation(
    progress: dict[str, object], operation_id: str, payload_sha256: str
) -> dict[str, object] | None:
    for operation in progress["operations"]:
        if operation["id"] != operation_id:
            continue
        if operation["payload_sha256"] != payload_sha256:
            raise TrainingError("operation ID was already used with a different payload")
        return operation
    return None


def _find_result(progress: dict[str, object], operation: dict[str, object]) -> dict[str, object]:
    collection = "attempts" if operation["kind"] == "submit" else "reviews"
    for item in progress["targets"][operation["target"]][collection]:
        if item["id"] == operation["result_id"]:
            return deepcopy(item)
    raise TrainingError("operation result is missing from verified progress history")


def submit_attempt(
    workspace_value: Path | str,
    target: str,
    *,
    note: str = "",
    operation_id: str | None = None,
) -> dict[str, object]:
    """Freeze a structurally complete worksheet as an immutable embedded attempt."""

    workspace = _validate_workspace_location(workspace_value, creating=False)
    normalized_note = _validate_text(note, field="learner note", allow_empty=True)
    operation = _validate_id(operation_id or f"op-{uuid.uuid4().hex}", field="operation ID")
    with _exclusive_lock(workspace) as workspace_descriptor:
        progress = _load_progress_from_descriptor(workspace, workspace_descriptor)
        relative = _worksheet_relative(progress, target)
        snapshot = _read_text_from_directory_fd(
            workspace_descriptor,
            relative,
            label=f"{target} worksheet",
            maximum_bytes=MAX_WORKSHEET_BYTES,
        )
        assessment = _assess_text(target, snapshot)
        if assessment["structure_status"] != "complete":
            raise TrainingError(
                f"{target} worksheet is structurally incomplete; run train progress check first"
            )
        payload_sha256 = _payload_digest(
            {
                "kind": "submit",
                "target": target,
                "note": normalized_note,
                "worksheet_sha256": _sha256_text(snapshot),
            }
        )
        existing = _existing_operation(progress, operation, payload_sha256)
        if existing is not None:
            return _find_result(progress, existing)

        target_record = progress["targets"][target]
        attempts = target_record["attempts"]
        attempt_id = f"{target.upper()}-A{len(attempts) + 1:03d}"
        attempt = {
            "id": attempt_id,
            "created_at": _utc_now(),
            "retry_of": attempts[-1]["id"] if attempts else None,
            "note": normalized_note,
            "worksheet_sha256": _sha256_text(snapshot),
            "worksheet_snapshot": snapshot,
            "structure_assessment": assessment,
        }
        attempts.append(attempt)
        progress["operations"].append(
            {
                "id": operation,
                "kind": "submit",
                "target": target,
                "payload_sha256": payload_sha256,
                "result_id": attempt_id,
            }
        )
        progress["updated_at"] = _utc_now()
        _validate_progress(
            progress, workspace, workspace_descriptor=workspace_descriptor
        )
        _atomic_write_progress(workspace_descriptor, progress)
        return deepcopy(attempt)


def _validate_pass_consistency(target: str, decision: str, ratings: dict[str, object]) -> None:
    if decision != "pass":
        return
    if target == "capstone":
        if any(ratings.get(band) != "demonstrated" for band in BANDS):
            raise TrainingError("a capstone pass must declare all four maturity bands demonstrated")
    elif ratings.get("Recognize") != "demonstrated" or ratings.get("Prove") != "demonstrated":
        raise TrainingError("a level pass must declare Recognize and Prove demonstrated")


def record_review(
    workspace_value: Path | str,
    target: str,
    *,
    reviewer: str,
    decision: str,
    ratings: dict[str, str],
    rationale: str,
    strengths: str,
    gaps: str,
    attempt_id: str = "latest",
    operation_id: str | None = None,
) -> dict[str, object]:
    """Append one declared human review; never calculate a rating automatically."""

    workspace = _validate_workspace_location(workspace_value, creating=False)
    reviewer_label = _validate_label(reviewer, field="reviewer label")
    if decision not in REVIEW_DECISIONS:
        raise TrainingError(f"review decision must be one of {REVIEW_DECISIONS}")
    ratings = _expect_exact_keys(ratings, set(BANDS), field="ratings")
    if any(value not in RATING_VALUES for value in ratings.values()):
        raise TrainingError(f"rating observations must be one of {RATING_VALUES}")
    _validate_pass_consistency(target, decision, ratings)
    rationale_text = _validate_text(rationale, field="review rationale")
    strengths_text = _validate_text(strengths, field="review strengths")
    gaps_text = _validate_text(gaps, field="review gaps")
    operation = _validate_id(operation_id or f"op-{uuid.uuid4().hex}", field="operation ID")

    with _exclusive_lock(workspace) as workspace_descriptor:
        progress = _load_progress_from_descriptor(workspace, workspace_descriptor)
        if target not in TARGETS:
            raise TrainingError(f"unknown training target: {target}")
        target_record = progress["targets"][target]
        attempts = target_record["attempts"]
        if not attempts:
            raise TrainingError(f"{target} has no submitted attempt to review")
        selected_id = attempts[-1]["id"] if attempt_id == "latest" else attempt_id
        selected = next((item for item in attempts if item["id"] == selected_id), None)
        if selected is None:
            raise TrainingError(f"unknown submitted attempt for {target}: {selected_id}")

        payload_sha256 = _payload_digest(
            {
                "kind": "review",
                "target": target,
                "attempt_id": selected_id,
                "attempt_sha256": selected["worksheet_sha256"],
                "reviewer": reviewer_label,
                "decision": decision,
                "ratings": ratings,
                "rationale": rationale_text,
                "strengths": strengths_text,
                "gaps": gaps_text,
            }
        )
        existing = _existing_operation(progress, operation, payload_sha256)
        if existing is not None:
            return _find_result(progress, existing)

        reviews = target_record["reviews"]
        review_id = f"{target.upper()}-R{len(reviews) + 1:03d}"
        review = {
            "id": review_id,
            "attempt_id": selected_id,
            "attempt_sha256": selected["worksheet_sha256"],
            "reviewer": reviewer_label,
            "created_at": _utc_now(),
            "decision": decision,
            "ratings": dict(ratings),
            "rationale": rationale_text,
            "strengths": strengths_text,
            "gaps": gaps_text,
        }
        reviews.append(review)
        progress["operations"].append(
            {
                "id": operation,
                "kind": "review",
                "target": target,
                "payload_sha256": payload_sha256,
                "result_id": review_id,
            }
        )
        progress["updated_at"] = _utc_now()
        _validate_progress(
            progress, workspace, workspace_descriptor=workspace_descriptor
        )
        _atomic_write_progress(workspace_descriptor, progress)
        return deepcopy(review)


def _active_reviews(target_record: dict[str, object]) -> list[dict[str, object]]:
    attempts = target_record["attempts"]
    if not attempts:
        return []
    latest_attempt_id = attempts[-1]["id"]
    by_reviewer: dict[str, dict[str, object]] = {}
    for review in target_record["reviews"]:
        if review["attempt_id"] == latest_attempt_id:
            by_reviewer[review["reviewer"]] = review
    return list(by_reviewer.values())


def _human_review_state(target_record: dict[str, object]) -> str:
    if not target_record["attempts"]:
        return "not-reviewed"
    active = _active_reviews(target_record)
    if not active:
        return "awaiting-human-review"
    decisions = {review["decision"] for review in active}
    if decisions == {"pass"}:
        return "human-passed"
    if len(decisions) > 1:
        return "review-disagreement"
    if decisions == {"blocked"}:
        return "human-blocked"
    return "needs-revision"


def _status_from_descriptor(
    workspace: Path, workspace_descriptor: int
) -> dict[str, object]:
    progress = _load_progress_from_descriptor(workspace, workspace_descriptor)
    targets: dict[str, object] = {}
    all_human_passed = True
    has_unsubmitted_draft = False
    next_target: str | None = None
    for target in TARGETS:
        target_record = progress["targets"][target]
        relative = _worksheet_relative(progress, target)
        worksheet_content = _read_text_from_directory_fd(
            workspace_descriptor,
            relative,
            label=f"{target} worksheet",
            maximum_bytes=MAX_WORKSHEET_BYTES,
        )
        assessment = _assess_text(target, worksheet_content)
        attempts = target_record["attempts"]
        latest = attempts[-1] if attempts else None
        active = _active_reviews(target_record)
        human_state = _human_review_state(target_record)
        draft_changed = bool(
            latest and _sha256_text(worksheet_content) != latest["worksheet_sha256"]
        )
        if draft_changed:
            has_unsubmitted_draft = True
        if human_state != "human-passed":
            all_human_passed = False
            if next_target is None:
                next_target = target
        elif draft_changed and next_target is None:
            next_target = target
        active_summary = [
            {
                "review_id": review["id"],
                "reviewer": review["reviewer"],
                "decision": review["decision"],
                "ratings": deepcopy(review["ratings"]),
                "gaps": review["gaps"],
            }
            for review in active
        ]
        rating_disagreements = {
            band: sorted({str(review["ratings"][band]) for review in active})
            for band in BANDS
            if len({str(review["ratings"][band]) for review in active}) > 1
        }
        targets[target] = {
            "attempt_state": "submitted" if latest else "not-submitted",
            "structure_state": assessment["structure_status"],
            "human_review_state": human_state,
            "maturity_assessment": "human-only",
            "semantic_assessment": "not_performed",
            "scientific_correctness": "not_assessed",
            "attempt_count": len(attempts),
            "latest_attempt_id": latest["id"] if latest else None,
            "latest_attempt_sha256": latest["worksheet_sha256"] if latest else None,
            "draft_changes_since_submission": draft_changed,
            "current_draft_state": (
                "changed-unsubmitted"
                if draft_changed
                else "matches-latest-submission"
                if latest
                else "not-submitted"
            ),
            "active_reviews": active_summary,
            "rating_disagreements": rating_disagreements,
            "historical_review_count": len(target_record["reviews"]) - len(active),
            "evidence_gaps": [review["gaps"] for review in active],
        }
    if all_human_passed and has_unsubmitted_draft:
        overall_state = "human-reviewed-complete-with-unsubmitted-draft"
    elif all_human_passed:
        overall_state = "human-reviewed-complete"
    else:
        overall_state = "in-progress"
    return {
        "workspace_type": WORKSPACE_TYPE,
        "case_id": progress["case_id"],
        "case_revision": progress["case_revision"],
        "exposure_state": progress["exposure_state"],
        "validator_scope": progress["validator_scope"],
        "overall_state": overall_state,
        "next_recommended_target": next_target,
        "scientific_correctness": "not_assessed",
        "maturity_assessment": "human-only",
        "targets": targets,
    }


def get_status(workspace_value: Path | str) -> dict[str, object]:
    """Build a resumable view without collapsing distinct meanings into one score."""

    workspace = _validate_workspace_location(workspace_value, creating=False)
    workspace_descriptor = _open_verified_root(workspace)
    try:
        return _status_from_descriptor(workspace, workspace_descriptor)
    finally:
        os.close(workspace_descriptor)


def _redacted_status(status: dict[str, object]) -> dict[str, object]:
    redacted = deepcopy(status)
    reviewer_aliases: dict[str, str] = {}
    for target in TARGETS:
        target_record = redacted["targets"][target]
        raw_gaps = target_record.pop("evidence_gaps")
        target_record["evidence_gap_count"] = len(raw_gaps)
        for review in target_record["active_reviews"]:
            label = review["reviewer"]
            if label not in reviewer_aliases:
                reviewer_aliases[label] = f"reviewer-{len(reviewer_aliases) + 1}"
            review["reviewer"] = reviewer_aliases[label]
            review["gap_recorded"] = bool(review.pop("gaps"))
    redacted["privacy_note"] = (
        "Learner labels and free-form review text are omitted; reviewer labels are pseudonymized."
    )
    redacted["export_boundary"] = (
        "No worksheet snapshots are exported. Structure and declared human reviews are not scientific certification."
    )
    return redacted


def _safe_markdown(value: object) -> str:
    text = str(value)
    text = "".join(
        character
        for character in text
        if character in "\n\t" or (unicodedata.category(character) != "Cc" and character not in "\u202a\u202b\u202d\u202e\u2066\u2067\u2068\u2069")
    )
    text = html.escape(text, quote=True)
    return re.sub(r"([\\`*_{}\[\]()#+.!|>])", r"\\\1", text)


def _render_markdown(status: dict[str, object]) -> str:
    lines = [
        "# RCSL Training Progress Export",
        "",
        f"- Case: `{_safe_markdown(status['case_id'])}`",
        f"- Case revision: `{_safe_markdown(status['case_revision'])}`",
        f"- Exposure: `{_safe_markdown(status['exposure_state'])}`",
        f"- Overall state: `{_safe_markdown(status['overall_state'])}`",
        f"- Scientific correctness: `{_safe_markdown(status['scientific_correctness'])}`",
        "",
        _safe_markdown(status["export_boundary"]),
        "",
    ]
    for target in TARGETS:
        record = status["targets"][target]
        lines.extend(
            [
                f"## {_safe_markdown(target)}",
                "",
                f"- Attempt: `{_safe_markdown(record['attempt_state'])}`",
                f"- Structure: `{_safe_markdown(record['structure_state'])}`",
                f"- Human review: `{_safe_markdown(record['human_review_state'])}`",
                f"- Current draft: `{_safe_markdown(record['current_draft_state'])}`",
                f"- Reviewed attempt digest: `{_safe_markdown(record['latest_attempt_sha256'])}`",
                f"- Semantic assessment: `{_safe_markdown(record['semantic_assessment'])}`",
                f"- Maturity assessment: `{_safe_markdown(record['maturity_assessment'])}`",
            ]
        )
        if record["active_reviews"]:
            lines.extend(["", "Active declared human reviews:"])
            for review in record["active_reviews"]:
                ratings = ", ".join(
                    f"{band}={review['ratings'][band]}" for band in BANDS
                )
                lines.append(
                    f"- {_safe_markdown(review['reviewer'])}: "
                    f"`{_safe_markdown(review['decision'])}`; {_safe_markdown(ratings)}; "
                    f"gap-recorded: `{_safe_markdown(review['gap_recorded'])}`"
                )
        if record["rating_disagreements"]:
            differences = ", ".join(
                f"{band}={values}"
                for band, values in record["rating_disagreements"].items()
            )
            lines.append(f"- Rating disagreement: {_safe_markdown(differences)}")
        lines.append("")
    lines.extend(
        [
            "---",
            "",
            _safe_markdown(status["privacy_note"]),
            "This export contains declared records, not an authenticated signature or scientific PASS.",
            "",
        ]
    )
    return "\n".join(lines)


def export_progress(
    workspace_value: Path | str,
    output_value: Path | str,
    *,
    format_name: str,
) -> Path:
    """Create a non-overwriting, redacted progress report inside the workspace."""

    workspace = _validate_workspace_location(workspace_value, creating=False)
    if format_name not in {"markdown", "json"}:
        raise TrainingError("export format must be markdown or json")
    output = _normalized_path(output_value)
    if _has_isolated_component(output):
        raise TrainingError("refusing to export into isolated instructor material")
    if not _is_within(output, workspace) or len(output.parts) <= len(workspace.parts):
        raise TrainingError("progress export must remain inside the training workspace")
    relative_output = Path(*output.parts[len(workspace.parts) :])
    _validate_relative_file_path(relative_output.as_posix(), label="progress export")
    if output.name.casefold() in {
        PROGRESS_FILENAME.casefold(),
        LOCK_FILENAME.casefold(),
        "readme.md",
        "rubric.md",
        "capstone_brief.md",
    }:
        raise TrainingError("refusing to overwrite a reserved training-workspace file")
    workspace_descriptor = _open_verified_root(workspace)
    try:
        status = _redacted_status(
            _status_from_descriptor(workspace, workspace_descriptor)
        )
        if format_name == "json":
            content = (
                json.dumps(
                    status,
                    indent=2,
                    sort_keys=True,
                    ensure_ascii=False,
                    allow_nan=False,
                )
                + "\n"
            )
        else:
            content = _render_markdown(status)
        _write_new_file_from_directory_fd(
            workspace_descriptor,
            relative_output.as_posix(),
            content.encode("utf-8"),
            label=f"progress export {relative_output.as_posix()}",
        )
    finally:
        os.close(workspace_descriptor)
    return output
