"""Build and verify a no-JavaScript, offline RCSL evidence snapshot.

The view is a projection, never a new source of truth.  Open Demo inputs must
first pass the trusted release verifier.  Optional audit and training inputs are
read through their own validators and projected onto an explicit allowlist.
Blind staging and every role package are deliberately out of scope.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import html
from itertools import islice
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
from typing import Iterable
import unicodedata

from . import audit as audit_core
from . import release as release_core
from . import training as training_core


SCHEMA_VERSION = 1
MANIFEST_TYPE = "rcsl-static-view"
VIEW_MODE = "offline-static-snapshot"
OPEN_PRIVACY_CLASSIFICATION = "open-demo-only-offline"
LOCAL_PRIVACY_CLASSIFICATION = "local-sensitive-not-deployable"
SCIENTIFIC_CORRECTNESS = "not_assessed"
NETWORK_ACCESS = "not_used"
CODE_EXECUTION = "not_performed"
PROTECTED_DIRECTORY_NAME = "DO_NOT_OPEN_UNTIL_FINISHED"

MAX_OPEN_DEMOS = 32
MAX_VIEW_FILES = 16
MAX_VIEW_FILE_BYTES = 16_000_000
MAX_VIEW_TOTAL_BYTES = 48_000_000
MAX_PROJECTED_JSON_BYTES = 12_000_000
MAX_TEXT_LENGTH = 200_000
MAX_FINDINGS = 10_000
MAX_EVIDENCE_PER_FINDING = 10_000
MAX_AUDIT_EVIDENCE = 50_000
MAX_RELEASE_ROOT_ENTRIES = 128
MAX_VIEW_ENTRIES = MAX_VIEW_FILES + 2
MAX_AUDIT_ROOT_ENTRIES = 64
MAX_AUDIT_INPUT_BYTES = MAX_VIEW_TOTAL_BYTES

BASE_PAYLOAD_PATHS = {
    "VIEW_BOUNDARY.md",
    "data/CASE_REGISTRY.json",
    "index.html",
    "style.css",
}
CONTROL_PATHS = {"VIEW_MANIFEST.json", "CHECKSUMS.sha256"}
EXPECTED_DIRECTORIES = {"data", "data/evidence"}
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
GIT_REVISION = re.compile(r"^[0-9a-f]{40,64}$")
SEMVER = release_core.SEMVER_PATTERN
WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:[\\/]")
REVIEWER_ALIAS = re.compile(r"^reviewer-[1-9][0-9]*$")
FORBIDDEN_RELEASE_ROOT_MARKERS = {
    "challenge",
    "evaluator",
    "maintainer",
    "control_manifest.json",
    "build_record.json",
    "readiness-workspace.json",
}

FORBIDDEN_PROJECTION_KEYS = {
    "actor",
    "actor_authentication",
    "declared_actor",
    "learner_label",
    "reviewer",
    "workspace",
    "project_root",
    "worksheet_snapshot",
    "trusted_candidate",
    "correct_candidate",
    "expected_answer",
    "hidden_rule_id",
    "repair_span",
    "private_probe",
}

VIEW_LIMITATIONS = [
    "This snapshot verifies retained bytes and an allowlisted projection only.",
    "It does not establish scientific correctness, measurement validity, reviewer identity, or external immutability.",
    "No package or audited-project code is executed and no network resource is fetched by the view builder.",
    "Audit and training projections can still contain locally sensitive research context and must not be deployed.",
]
TRAINING_PRIVACY_NOTE = (
    "Learner labels and free-form review text are omitted; reviewer labels are "
    "pseudonymized."
)
TRAINING_EXPORT_BOUNDARY = (
    "No worksheet snapshots are exported. Structure and declared human reviews "
    "are not scientific certification."
)


class ViewError(RuntimeError):
    """A static-view operation was unsafe, invalid, or unverifiable."""


@dataclass(frozen=True)
class _FrozenView:
    root: Path
    descriptor: int
    device: int
    inode: int
    files: dict[str, release_core.FileBlob]
    directories: set[str]
    identities: dict[str, tuple[int, int, int, int, int]]


@dataclass(frozen=True)
class _PinnedOutputParent:
    path: Path
    descriptor: int
    device: int
    inode: int


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _json_bytes(value: object) -> bytes:
    try:
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
    except (TypeError, ValueError, UnicodeError) as error:
        raise ViewError(f"could not serialize the static-view projection: {error}") from error


def _has_protected_component(path: Path | PurePosixPath) -> bool:
    protected = PROTECTED_DIRECTORY_NAME.casefold()
    return any(part.casefold() == protected for part in path.parts)


def _normalized_path(value: Path | str) -> Path:
    try:
        return Path(os.path.abspath(os.fspath(Path(value).expanduser())))
    except (OSError, RuntimeError, TypeError, ValueError) as error:
        raise ViewError(f"invalid local path: {error}") from error


def _resolve_directory(value: Path | str, *, label: str) -> Path:
    path = _normalized_path(value)
    if _has_protected_component(path):
        raise ViewError(f"{label} cannot enter protected instructor material")
    try:
        if path.is_symlink():
            raise ViewError(f"{label} must not be a symlink")
        canonical = path.resolve(strict=True)
    except ViewError:
        raise
    except (OSError, RuntimeError, ValueError) as error:
        raise ViewError(f"could not resolve {label}: {error}") from error
    if _has_protected_component(canonical):
        raise ViewError(f"{label} cannot enter protected instructor material")
    if not canonical.is_dir():
        raise ViewError(f"{label} must be an existing directory")
    return canonical


def _is_within(child: Path, parent: Path) -> bool:
    child_parts = tuple(
        unicodedata.normalize("NFC", part).casefold() for part in child.parts
    )
    parent_parts = tuple(
        unicodedata.normalize("NFC", part).casefold() for part in parent.parts
    )
    return (
        len(child_parts) >= len(parent_parts)
        and child_parts[: len(parent_parts)] == parent_parts
    )


def _reject_overlap(output: Path, source: Path, *, label: str) -> None:
    if _is_within(output, source) or _is_within(source, output):
        raise ViewError(f"static-view output must not overlap {label}")


def _bounded_names(
    descriptor: int, *, label: str, maximum_entries: int
) -> list[str]:
    names: list[str] = []
    try:
        with os.scandir(descriptor) as entries:
            for entry in entries:
                if len(names) >= maximum_entries:
                    raise ViewError(
                        f"{label} exceeds the {maximum_entries}-entry safety limit"
                    )
                names.append(entry.name)
    except ViewError:
        raise
    except OSError as error:
        raise ViewError(f"could not inspect {label}: {error}") from error
    names.sort()
    return names


def _safe_root_names(root: Path, *, label: str) -> tuple[int, list[str]]:
    """Pin a root and list only its immediate names without descending."""

    descriptor: int | None = None
    try:
        descriptor = release_core._open_directory_chain(root)
        names = _bounded_names(
            descriptor,
            label=label,
            maximum_entries=MAX_RELEASE_ROOT_ENTRIES,
        )
    except release_core.ReleaseError as error:
        if descriptor is not None:
            os.close(descriptor)
        raise ViewError(str(error)) from error
    except OSError as error:
        if descriptor is not None:
            os.close(descriptor)
        raise ViewError(f"could not inspect {label}: {error}") from error
    except BaseException:
        if descriptor is not None:
            os.close(descriptor)
        raise
    folded: set[str] = set()
    try:
        for name in names:
            if name != unicodedata.normalize("NFC", name):
                raise ViewError(f"{label} contains a non-NFC root name")
            key = name.casefold()
            if key in folded:
                raise ViewError(f"{label} contains a case-insensitive root collision")
            folded.add(key)
            if key == PROTECTED_DIRECTORY_NAME.casefold():
                raise ViewError(f"{label} contains protected instructor material")
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor, names


def _peek_release_manifest(
    root: Path,
    *,
    descriptor: int | None = None,
    names: list[str] | None = None,
    include_data: bool = False,
) -> str | tuple[str, bytes] | None:
    """Classify a release root before any role payload can be traversed."""

    owns_descriptor = descriptor is None
    if descriptor is None:
        descriptor, names = _safe_root_names(root, label="Open Demo input")
    if names is None:
        raise ViewError("internal release classification error: root names unavailable")
    try:
        folded = {name.casefold(): name for name in names}
        if FORBIDDEN_RELEASE_ROOT_MARKERS & set(folded):
            raise ViewError("Blind staging is not a supported static-view input")
        manifest_name = folded.get("package_manifest.json")
        if manifest_name is None:
            raise ViewError("Open Demo input is missing PACKAGE_MANIFEST.json")
        try:
            metadata = os.stat(
                manifest_name, dir_fd=descriptor, follow_symlinks=False
            )
            data = release_core._read_regular_file_at(
                descriptor,
                manifest_name,
                label="release package manifest",
                maximum_bytes=release_core.MAX_MANIFEST_BYTES,
                expected=metadata,
            )
            manifest = release_core._strict_json_bytes(
                data, field="release package manifest"
            )
        except release_core.ReleaseError as error:
            raise ViewError(str(error)) from error
        manifest_type = manifest.get("manifest_type")
        if manifest_type == "rcsl-role-package":
            role = manifest.get("package_role", "unknown")
            raise ViewError(
                f"Blind role package ({role}) is not a supported static-view input"
            )
        if manifest_type == "rcsl-blind-staging":
            raise ViewError("Blind staging is not a supported static-view input")
        if manifest_type != "rcsl-open-demo-package":
            raise ViewError(f"unsupported release input type: {manifest_type}")
        return (manifest_type, data) if include_data else manifest_type
    finally:
        if owns_descriptor:
            os.close(descriptor)


def _verified_open_demo(bundle_value: Path | str) -> tuple[Path, dict[str, object], dict[str, release_core.FileBlob], dict[str, object]]:
    bundle = _resolve_directory(bundle_value, label="Open Demo input")
    descriptor, names = _safe_root_names(bundle, label="Open Demo input")
    try:
        opened = os.fstat(descriptor)
        peeked = _peek_release_manifest(
            bundle,
            descriptor=descriptor,
            names=names,
            include_data=True,
        )
        if not isinstance(peeked, tuple):
            raise ViewError("Open Demo manifest classification was unavailable")
        kind, classified_manifest_data = peeked
        if kind != "rcsl-open-demo-package":
            raise ViewError(f"unsupported release input type: {kind}")
        frozen = release_core._verify_checksum_tree_at(
            descriptor,
            expected_manifest=classified_manifest_data,
            forbidden_root_names=FORBIDDEN_RELEASE_ROOT_MARKERS,
        )
        manifest = frozen["_manifest"]
        files = frozen["_files"]
        if not isinstance(manifest, dict) or not isinstance(files, dict):
            raise ViewError("trusted Open Demo verifier returned an invalid snapshot")
        release_core._validate_open_demo_manifest(manifest)
        release_core._validate_open_demo_record(manifest, files)
        current = bundle.lstat()
        if (
            bundle.is_symlink()
            or not stat.S_ISDIR(current.st_mode)
            or (current.st_dev, current.st_ino) != (opened.st_dev, opened.st_ino)
        ):
            raise ViewError("Open Demo input identity changed during verification")
    except release_core.ReleaseError as error:
        raise ViewError(f"Open Demo verification failed: {error}") from error
    except OSError as error:
        raise ViewError(f"Open Demo verification failed safely: {error}") from error
    finally:
        os.close(descriptor)
    if frozen.get("manifest_type") != "rcsl-open-demo-package":
        raise ViewError("Blind role packages are not supported by the static viewer")
    public_result = {
        key: deepcopy(frozen[key])
        for key in (
            "integrity_status",
            "manifest_type",
            "manifest_sha256",
            "checksums_sha256",
            "file_count",
            "scientific_correctness",
        )
    }
    return bundle, manifest, files, public_result


def _require_object(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ViewError(f"{field} must be an object")
    return value


def _expect_exact_keys(value: object, expected: set[str], *, field: str) -> dict[str, object]:
    record = _require_object(value, field=field)
    actual = set(record)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        details = []
        if missing:
            details.append(f"missing {missing}")
        if extra:
            details.append(f"unexpected {extra}")
        raise ViewError(f"{field} has an invalid schema ({'; '.join(details)})")
    return record


def _require_text(
    value: object,
    *,
    field: str,
    allow_empty: bool = False,
    maximum: int = MAX_TEXT_LENGTH,
) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ViewError(f"{field} must be {'text' if allow_empty else 'non-empty text'}")
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ViewError(f"{field} must be valid Unicode") from error
    if len(encoded) > maximum:
        raise ViewError(f"{field} exceeds the {maximum}-byte UTF-8 limit")
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
        raise ViewError(f"{field} contains an unsupported control character")
    return value


def _require_bool(value: object, *, field: str) -> bool:
    if type(value) is not bool:
        raise ViewError(f"{field} must be a boolean")
    return value


def _require_nonnegative_int(value: object, *, field: str) -> int:
    if type(value) is not int or value < 0:
        raise ViewError(f"{field} must be a non-negative integer")
    return value


def _require_digest(value: object, *, field: str, git: bool = False) -> str:
    if not isinstance(value, str) or not (GIT_REVISION if git else HEX_SHA256).fullmatch(value):
        raise ViewError(f"{field} must be a valid {'Git revision' if git else 'SHA-256 digest'}")
    return value


def _sanitize_text(value: object, *, field: str, roots: Iterable[str] = ()) -> str:
    text = _require_text(value, field=field)
    for root in sorted({item for item in roots if len(item) > 1}, key=len, reverse=True):
        try:
            uri = Path(root).as_uri()
        except (OSError, ValueError):
            uri = None
        if uri is not None:
            text = text.replace(uri, "[local-path-redacted]")
        text = text.replace(root, "[local-path-redacted]")
    text = text.replace(PROTECTED_DIRECTORY_NAME, "[protected-name-redacted]")
    text = text.replace(PROTECTED_DIRECTORY_NAME.casefold(), "[protected-name-redacted]")
    cleaned = "".join(
        character
        for character in text
        if character in "\n\t" or unicodedata.category(character) != "Cc"
    )
    return unicodedata.normalize("NFC", cleaned)


def _safe_reference(value: object, *, roots: Iterable[str]) -> str:
    original = _require_text(value, field="audit evidence reference")
    candidate = original.strip()
    if (
        candidate != original
        or any(character in original for character in "\r\n\t")
        or os.path.isabs(candidate)
        or WINDOWS_ABSOLUTE.match(candidate)
        or candidate.startswith("\\\\")
        or candidate.casefold().startswith("file:")
        or any(root and root in candidate for root in roots)
    ):
        return "[local-reference-redacted]"
    return _sanitize_text(original, field="audit evidence reference", roots=roots)


def _forbid_projection_keys(value: object, *, field: str = "projection") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if not isinstance(key, str):
                raise ViewError(f"{field} contains a non-text key")
            folded = key.casefold()
            if (
                folded in FORBIDDEN_PROJECTION_KEYS
                or "private" in folded
                or folded == "answer"
                or folded == "answers"
            ):
                raise ViewError(f"{field} crossed the identity or answer-data boundary")
            _forbid_projection_keys(nested, field=f"{field}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _forbid_projection_keys(nested, field=f"{field}[{index}]")
    elif isinstance(value, float):
        raise ViewError(f"{field} contains unsupported floating-point data")


def _open_case_record(
    manifest: dict[str, object],
    files: dict[str, release_core.FileBlob],
    verification: dict[str, object],
) -> dict[str, object]:
    validation_blob = files.get("VALIDATION_RECORD.json")
    if validation_blob is None:
        raise ViewError("verified Open Demo is missing its validation record")
    try:
        validation = release_core._strict_json_bytes(
            validation_blob.data, field="Open Demo validation record"
        )
    except release_core.ReleaseError as error:
        raise ViewError(str(error)) from error
    records = validation.get("records")
    if not isinstance(records, list) or len(records) != 2:
        raise ViewError("verified Open Demo validation record is invalid")
    outcomes: dict[str, str] = {}
    for index, record_value in enumerate(records):
        record = _require_object(record_value, field=f"Open Demo validation record {index}")
        name = _require_text(record.get("name"), field="Open Demo validation name")
        outcome = _require_text(record.get("outcome"), field="Open Demo validation outcome")
        outcomes[name] = outcome
    record = {
        "case_id": _require_text(manifest.get("case_id"), field="Open Demo case_id"),
        "case_version": _require_text(manifest.get("case_version"), field="Open Demo case_version"),
        "release_mode": _require_text(manifest.get("release_mode"), field="Open Demo release_mode"),
        "exposure_state": _require_text(manifest.get("exposure_state"), field="Open Demo exposure_state"),
        "release_state": _require_text(manifest.get("release_state"), field="Open Demo release_state"),
        "source_revision": _require_digest(
            manifest.get("source_revision"), field="Open Demo source_revision", git=True
        ),
        "source_revision_scope": _require_text(
            manifest.get("source_revision_scope"), field="Open Demo source_revision_scope"
        ),
        "repository_worktree_state": _require_text(
            manifest.get("repository_worktree_state"), field="Open Demo repository_worktree_state"
        ),
        "source_tree_sha256": _require_digest(
            manifest.get("source_tree_sha256"), field="Open Demo source_tree_sha256"
        ),
        "package_manifest_sha256": _require_digest(
            verification.get("manifest_sha256"), field="Open Demo manifest digest"
        ),
        "package_checksums_sha256": _require_digest(
            verification.get("checksums_sha256"), field="Open Demo checksums digest"
        ),
        "package_file_count": _require_nonnegative_int(
            verification.get("file_count"), field="Open Demo package file_count"
        ),
        "licenses": deepcopy(manifest.get("licenses")),
        "known_limitations": deepcopy(manifest.get("known_limitations")),
        "claims_not_made": deepcopy(manifest.get("claims_not_made")),
        "static_validation": outcomes.get("static-public-surface"),
        "public_runtime_checks": outcomes.get("level-1-through-4-public-checks"),
        "scientific_correctness": SCIENTIFIC_CORRECTNESS,
        "measurement_validity": "not_assessed",
    }
    _validate_case_record(record, field="Open Demo projection")
    return record


def _preflight_audit_workspace_limits(root: Path) -> None:
    """Bound the legacy audit adapter before it materializes its report."""

    descriptor: int | None = None
    findings_descriptor: int | None = None
    total_bytes = 0
    total_evidence = 0

    def consume(data: bytes, *, label: str) -> bytes:
        nonlocal total_bytes
        total_bytes += len(data)
        if total_bytes > MAX_AUDIT_INPUT_BYTES:
            raise ViewError(
                f"audit workspace exceeds the {MAX_AUDIT_INPUT_BYTES}-byte input limit"
            )
        return data

    def read_regular(
        directory: int, name: str, *, label: str, maximum: int
    ) -> bytes:
        try:
            metadata = os.stat(name, dir_fd=directory, follow_symlinks=False)
            return consume(
                release_core._read_regular_file_at(
                    directory,
                    name,
                    label=label,
                    maximum_bytes=maximum,
                    expected=metadata,
                ),
                label=label,
            )
        except release_core.ReleaseError as error:
            raise ViewError(str(error)) from error
        except OSError as error:
            raise ViewError(f"could not inspect {label}: {error}") from error

    def text_bytes(value: object) -> int:
        if isinstance(value, str):
            return len(value.encode("utf-8"))
        if isinstance(value, dict):
            return sum(text_bytes(key) + text_bytes(item) for key, item in value.items())
        if isinstance(value, list):
            return sum(text_bytes(item) for item in value)
        return 0

    try:
        descriptor = release_core._open_directory_chain(root)
        names = _bounded_names(
            descriptor,
            label="audit workspace root",
            maximum_entries=MAX_AUDIT_ROOT_ENTRIES,
        )
        folded: set[str] = set()
        for name in names:
            key = unicodedata.normalize("NFC", name).casefold()
            if name != unicodedata.normalize("NFC", name) or key in folded:
                raise ViewError("audit workspace root contains an unsafe name collision")
            if key == PROTECTED_DIRECTORY_NAME.casefold():
                raise ViewError("audit workspace contains protected instructor material")
            folded.add(key)
        # Empty directories are used by adapter-isolation tests. The real audit
        # validator will reject them; there is no legacy input to bound here.
        if audit_core.WORKSPACE_METADATA_NAME not in names:
            return
        known_root_files = {
            audit_core.WORKSPACE_METADATA_NAME,
            audit_core.EVENT_LOG_NAME,
            *audit_core.PUBLIC_TEMPLATE_FILENAMES,
        }
        for name in sorted(known_root_files & set(names)):
            read_regular(
                descriptor,
                name,
                label=f"audit input {name}",
                maximum=min(MAX_PROJECTED_JSON_BYTES, MAX_AUDIT_INPUT_BYTES - total_bytes),
            )
        if audit_core.FINDINGS_DIRECTORY_NAME not in names:
            return
        metadata = os.stat(
            audit_core.FINDINGS_DIRECTORY_NAME,
            dir_fd=descriptor,
            follow_symlinks=False,
        )
        if not stat.S_ISDIR(metadata.st_mode):
            raise ViewError("audit findings entry must be a regular directory")
        findings_descriptor = os.open(
            audit_core.FINDINGS_DIRECTORY_NAME,
            release_core._directory_open_flags(),
            dir_fd=descriptor,
        )
        opened = os.fstat(findings_descriptor)
        if (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino):
            raise ViewError("audit findings directory identity changed during preflight")
        finding_names = _bounded_names(
            findings_descriptor,
            label="audit findings directory",
            maximum_entries=MAX_FINDINGS + 1,
        )
        if len(finding_names) > MAX_FINDINGS:
            raise ViewError(f"audit findings exceed the {MAX_FINDINGS}-finding limit")
        projected_text = 0
        for name in finding_names:
            if not name.endswith(".json"):
                raise ViewError("audit findings directory contains an unexpected entry")
            data = read_regular(
                findings_descriptor,
                name,
                label=f"audit finding {name}",
                maximum=min(MAX_PROJECTED_JSON_BYTES, MAX_AUDIT_INPUT_BYTES - total_bytes),
            )
            try:
                finding = release_core._strict_json_bytes(
                    data,
                    field=f"audit finding {name}",
                    maximum_bytes=MAX_PROJECTED_JSON_BYTES,
                )
            except release_core.ReleaseError as error:
                raise ViewError(str(error)) from error
            evidence = finding.get("evidence")
            if not isinstance(evidence, list) or len(evidence) > MAX_EVIDENCE_PER_FINDING:
                raise ViewError(f"audit finding {name} evidence list is outside limits")
            total_evidence += len(evidence)
            if total_evidence > MAX_AUDIT_EVIDENCE:
                raise ViewError(
                    f"audit workspace exceeds the {MAX_AUDIT_EVIDENCE}-evidence limit"
                )
            projected_text += text_bytes(finding)
            if projected_text > MAX_PROJECTED_JSON_BYTES:
                raise ViewError("audit workspace exceeds the projected UTF-8 budget")
        after = os.fstat(findings_descriptor)
        if (after.st_dev, after.st_ino) != (metadata.st_dev, metadata.st_ino):
            raise ViewError("audit findings directory identity changed during preflight")
    except release_core.ReleaseError as error:
        raise ViewError(str(error)) from error
    finally:
        if findings_descriptor is not None:
            os.close(findings_descriptor)
        if descriptor is not None:
            os.close(descriptor)


def _project_audit(report_value: object) -> dict[str, object]:
    report = _require_object(report_value, field="audit report")
    verification = _require_object(report.get("verification"), field="audit verification")
    project = report.get("project")
    if not isinstance(project, dict):
        project = verification.get("project")
    project = _require_object(project, field="audit project")
    roots = {
        value
        for value in (verification.get("workspace"), project.get("root"))
        if isinstance(value, str) and value
    }
    projected_text_bytes = 0

    def consume(text: str) -> str:
        nonlocal projected_text_bytes
        projected_text_bytes += len(text.encode("utf-8"))
        if projected_text_bytes > MAX_PROJECTED_JSON_BYTES:
            raise ViewError("audit projection exceeds the cumulative UTF-8 budget")
        return text

    def sanitize(value: object, *, field: str) -> str:
        return consume(_sanitize_text(value, field=field, roots=roots))

    def reference(value: object) -> str:
        return consume(_safe_reference(value, roots=roots))
    baseline = _require_object(report.get("baseline"), field="audit baseline")
    gate = _require_object(report.get("g0_gate"), field="audit G0 gate")
    summary = _require_object(report.get("summary"), field="audit summary")
    source_limitations = report.get("limitations")
    if not isinstance(source_limitations, list) or not source_limitations or len(source_limitations) > 100:
        raise ViewError("audit report limitations must be a bounded, non-empty list")
    limitations = [
        sanitize(item, field=f"audit limitation {index}")
        for index, item in enumerate(source_limitations)
    ]
    limitations.extend(
        [
            "This is a local redacted projection of integrity-checked declarations, not scientific certification.",
            "People, workstation paths, project roots, and raw lifecycle events are omitted.",
            "Evidence references that identify an absolute local path are redacted.",
        ]
    )
    for fixed_limitation in limitations[len(source_limitations) :]:
        consume(fixed_limitation)
    limitations = list(dict.fromkeys(limitations))
    preflight = report.get("preflight")
    preflight_state = (
        "ready"
        if isinstance(preflight, dict) and preflight.get("ok") is True
        else "not-ready"
    )
    findings_value = report.get("findings")
    if not isinstance(findings_value, list) or len(findings_value) > MAX_FINDINGS:
        raise ViewError(f"audit findings must be a list of at most {MAX_FINDINGS} entries")

    findings: list[dict[str, object]] = []
    total_evidence = 0
    for finding_index, finding_value in enumerate(findings_value):
        source = _require_object(finding_value, field=f"audit finding {finding_index}")
        evidence_value = source.get("evidence")
        if not isinstance(evidence_value, list) or len(evidence_value) > MAX_EVIDENCE_PER_FINDING:
            raise ViewError(
                f"audit finding {finding_index} evidence must contain at most "
                f"{MAX_EVIDENCE_PER_FINDING} entries"
            )
        total_evidence += len(evidence_value)
        if total_evidence > MAX_AUDIT_EVIDENCE:
            raise ViewError(
                f"audit projection exceeds the {MAX_AUDIT_EVIDENCE}-evidence limit"
            )
        evidence: list[dict[str, object]] = []
        for evidence_index, evidence_value_item in enumerate(evidence_value):
            item = _require_object(
                evidence_value_item,
                field=f"audit finding {finding_index} evidence {evidence_index}",
            )
            evidence.append(
                {
                    "id": sanitize(item.get("id"), field="audit evidence id"),
                    "kind": sanitize(item.get("kind"), field="audit evidence kind"),
                    "reference": reference(item.get("reference")),
                    "summary": sanitize(item.get("summary"), field="audit evidence summary"),
                    "recorded_at": sanitize(item.get("recorded_at"), field="audit evidence recorded_at"),
                }
            )
        findings.append(
            {
                "id": sanitize(source.get("id"), field="audit finding id"),
                "title": sanitize(source.get("title"), field="audit finding title"),
                "layer": sanitize(source.get("layer"), field="audit finding layer"),
                "competency": sanitize(source.get("competency"), field="audit finding competency"),
                "severity": sanitize(source.get("severity"), field="audit finding severity"),
                "claim": sanitize(source.get("claim"), field="audit finding claim"),
                "first_broken_contract": sanitize(
                    source.get("first_broken_contract"),
                    field="audit finding first_broken_contract",
                ),
                "status": sanitize(source.get("status"), field="audit finding status"),
                "created_at": sanitize(source.get("created_at"), field="audit finding created_at"),
                "updated_at": sanitize(source.get("updated_at"), field="audit finding updated_at"),
                "baseline_state": sanitize(source.get("baseline_state"), field="audit finding baseline_state"),
                "baseline_current": _require_bool(
                    source.get("baseline_current"),
                    field="audit finding baseline_current",
                ),
                "evidence": evidence,
            }
        )

    def counts(source_value: object, keys: Iterable[str], field: str) -> dict[str, int]:
        source_counts = _require_object(source_value, field=field)
        return {
            key: _require_nonnegative_int(
                source_counts.get(key, 0), field=f"{field}.{key}"
            )
            for key in keys
        }

    projection = {
        "schema_version": SCHEMA_VERSION,
        "evidence_type": "rcsl-audit-evidence-view",
        "privacy_classification": LOCAL_PRIVACY_CLASSIFICATION,
        "validator_scope": "local_hash_chain_lifecycle_integrity_only",
        "report_status": _require_text(report.get("report_status"), field="audit report_status"),
        "preflight_state": preflight_state,
        "scientific_correctness": SCIENTIFIC_CORRECTNESS,
        "baseline": {
            "head": _require_digest(baseline.get("head"), field="audit baseline head", git=True),
            "branch": (
                None
                if baseline.get("branch") is None
                else sanitize(baseline.get("branch"), field="audit baseline branch")
            ),
            "captured_at": sanitize(
                baseline.get("captured_at"), field="audit baseline captured_at"
            ),
        },
        "g0_gate": {
            "status": sanitize(gate.get("status"), field="audit G0 status"),
            "contract_sha256": _require_digest(
                gate.get("contract_sha256"), field="audit G0 contract digest"
            ),
        },
        "integrity": {
            "event_count": _require_nonnegative_int(
                verification.get("event_count"), field="audit event_count"
            ),
            "last_event_hash": _require_digest(
                verification.get("last_event_hash"), field="audit last event hash"
            ),
        },
        "summary": {
            "finding_count": _require_nonnegative_int(
                summary.get("finding_count"), field="audit finding_count"
            ),
            "stale_finding_count": _require_nonnegative_int(
                summary.get("stale_finding_count"), field="audit stale_finding_count"
            ),
            "by_status": counts(summary.get("by_status"), audit_core.FINDING_STATUSES, "audit by_status"),
            "by_layer": counts(summary.get("by_layer"), audit_core.LAYERS, "audit by_layer"),
            "by_competency": counts(
                summary.get("by_competency"), audit_core.COMPETENCIES, "audit by_competency"
            ),
            "by_severity": counts(summary.get("by_severity"), audit_core.SEVERITIES, "audit by_severity"),
        },
        "findings": findings,
        "limitations": limitations,
    }
    if projection["summary"]["finding_count"] != len(findings):
        raise ViewError("audit finding_count does not match projected findings")
    _forbid_projection_keys(projection, field="audit projection")
    _validate_audit_projection(projection)
    return projection


def _project_training(status_value: object) -> dict[str, object]:
    status = _require_object(status_value, field="training status")
    targets_source = _require_object(status.get("targets"), field="training targets")
    targets: dict[str, object] = {}
    for target in training_core.TARGETS:
        source = _require_object(targets_source.get(target), field=f"training target {target}")
        reviews_value = source.get("active_reviews")
        if not isinstance(reviews_value, list):
            raise ViewError(f"training target {target} reviews must be a list")
        declared_reviews: list[dict[str, object]] = []
        for index, review_value in enumerate(reviews_value):
            review = _require_object(
                review_value, field=f"training target {target} review {index}"
            )
            ratings_source = _require_object(
                review.get("ratings"), field=f"training target {target} review ratings"
            )
            declared_reviews.append(
                {
                    "review_id": _require_text(
                        review.get("review_id"), field="training review id"
                    ),
                    "reviewer_alias": _require_text(
                        review.get("reviewer"), field="training reviewer alias"
                    ),
                    "decision": _require_text(
                        review.get("decision"), field="training review decision"
                    ),
                    "ratings": {
                        band: _require_text(
                            ratings_source.get(band), field=f"training rating {band}"
                        )
                        for band in training_core.BANDS
                    },
                    "gap_recorded": _require_bool(
                        review.get("gap_recorded"), field="training gap_recorded"
                    ),
                }
            )
        disagreements_source = _require_object(
            source.get("rating_disagreements"),
            field=f"training target {target} rating disagreements",
        )
        disagreements: dict[str, list[str]] = {}
        for band in training_core.BANDS:
            if band not in disagreements_source:
                continue
            values = disagreements_source[band]
            if not isinstance(values, list):
                raise ViewError(f"training disagreement {band} must be a list")
            disagreements[band] = [
                _require_text(value, field=f"training disagreement {band}")
                for value in values
            ]
        targets[target] = {
            "attempt_state": _require_text(source.get("attempt_state"), field="training attempt_state"),
            "structure_state": _require_text(source.get("structure_state"), field="training structure_state"),
            "human_review_state": _require_text(source.get("human_review_state"), field="training human_review_state"),
            "maturity_assessment": _require_text(source.get("maturity_assessment"), field="training maturity_assessment"),
            "semantic_assessment": _require_text(source.get("semantic_assessment"), field="training semantic_assessment"),
            "scientific_correctness": SCIENTIFIC_CORRECTNESS,
            "attempt_count": _require_nonnegative_int(source.get("attempt_count"), field="training attempt_count"),
            "latest_attempt_id": (
                None
                if source.get("latest_attempt_id") is None
                else _require_text(source.get("latest_attempt_id"), field="training latest_attempt_id")
            ),
            "latest_attempt_sha256": (
                None
                if source.get("latest_attempt_sha256") is None
                else _require_digest(
                    source.get("latest_attempt_sha256"), field="training latest attempt digest"
                )
            ),
            "draft_changes_since_submission": _require_bool(
                source.get("draft_changes_since_submission"), field="training draft state"
            ),
            "current_draft_state": _require_text(
                source.get("current_draft_state"), field="training current_draft_state"
            ),
            "declared_reviews": declared_reviews,
            "rating_disagreements": disagreements,
            "historical_review_count": _require_nonnegative_int(
                source.get("historical_review_count"), field="training historical_review_count"
            ),
            "evidence_gap_count": _require_nonnegative_int(
                source.get("evidence_gap_count"), field="training evidence_gap_count"
            ),
        }
    projection = {
        "schema_version": SCHEMA_VERSION,
        "evidence_type": "rcsl-training-status-view",
        "privacy_classification": LOCAL_PRIVACY_CLASSIFICATION,
        "case_id": _require_text(status.get("case_id"), field="training case_id"),
        "case_revision": _require_text(
            status.get("case_revision"), field="training case revision"
        ),
        "exposure_state": _require_text(status.get("exposure_state"), field="training exposure_state"),
        "validator_scope": _require_text(status.get("validator_scope"), field="training validator_scope"),
        "overall_state": _require_text(status.get("overall_state"), field="training overall_state"),
        "next_recommended_target": (
            None
            if status.get("next_recommended_target") is None
            else _require_text(
                status.get("next_recommended_target"), field="training next target"
            )
        ),
        "scientific_correctness": SCIENTIFIC_CORRECTNESS,
        "maturity_assessment": "human-only",
        "targets": targets,
        "privacy_note": TRAINING_PRIVACY_NOTE,
        "export_boundary": TRAINING_EXPORT_BOUNDARY,
    }
    _forbid_projection_keys(projection, field="training projection")
    _validate_training_projection(projection)
    return projection


def _file_records(files: dict[str, bytes]) -> list[dict[str, object]]:
    return [
        {
            "path": path,
            "sha256": _sha256_bytes(files[path]),
            "size": len(files[path]),
        }
        for path in sorted(files)
    ]


def _checksums(files: dict[str, bytes]) -> bytes:
    return "".join(
        f"{_sha256_bytes(files[path])}  {path}\n" for path in sorted(files)
    ).encode("utf-8")


def _boundary(privacy_classification: str) -> bytes:
    if privacy_classification == LOCAL_PRIVACY_CLASSIFICATION:
        scope = (
            "This view contains a redacted audit and/or training projection. Treat the "
            "whole directory as local-sensitive and do not deploy, publish, email, or "
            "copy it to a shared service without a separate human disclosure review."
        )
    elif privacy_classification == OPEN_PRIVACY_CLASSIFICATION:
        scope = (
            "This view contains verified Open Demo metadata only. It is an offline "
            "snapshot, not a Blind Challenge, assessment result, or release approval."
        )
    else:
        raise ViewError("static-view privacy classification is invalid")
    return (
        "# RCSL Static View Boundary\n\n"
        f"Privacy classification: `{privacy_classification}`\n\n"
        f"{scope}\n\n"
        "The builder reads declared artifacts as data. It does not execute package or "
        "audited-project code, load JavaScript, contact a network service, authenticate "
        "people, inspect protected instructor material, or establish scientific "
        "correctness. `CHECKSUMS.sha256` and `VIEW_MANIFEST.json` describe retained-byte "
        "self-consistency; an external trust anchor is still required for provenance.\n"
    ).encode("utf-8")


STYLE_CSS = b"""\
:root {
  color-scheme: light dark;
  --bg: #f5f6f3;
  --surface: #ffffff;
  --ink: #172126;
  --muted: #5d6a70;
  --line: #d6ddd9;
  --accent: #0c7280;
  --accent-soft: #dceff1;
  --warning: #8a4b08;
  --warning-soft: #fff0d7;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink); line-height: 1.55; }
main { width: min(1120px, calc(100% - 2rem)); margin: 0 auto; padding: 2rem 0 4rem; }
header { padding: 1.25rem 0 1.75rem; border-bottom: 1px solid var(--line); }
h1, h2, h3 { line-height: 1.15; text-wrap: balance; }
h1 { margin: .25rem 0 .75rem; font-family: ui-serif, Georgia, serif; font-size: clamp(2rem, 6vw, 4.5rem); }
h2 { margin-top: 2.5rem; font-size: clamp(1.4rem, 3vw, 2.1rem); }
h3 { margin: 0 0 .6rem; }
.eyebrow { color: var(--accent); font-size: .78rem; font-weight: 800; letter-spacing: .13em; text-transform: uppercase; }
.lede, .muted { color: var(--muted); }
.badge { display: inline-block; padding: .35rem .65rem; border-radius: 999px; background: var(--accent-soft); color: var(--accent); font-size: .8rem; font-weight: 750; }
.badge.sensitive { background: var(--warning-soft); color: var(--warning); }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 280px), 1fr)); gap: 1rem; }
.card { min-width: 0; padding: 1.1rem; border: 1px solid var(--line); border-radius: 1rem; background: var(--surface); box-shadow: 0 9px 28px rgba(22, 36, 42, .05); }
dl { display: grid; grid-template-columns: minmax(7rem, auto) 1fr; gap: .35rem .8rem; margin: .8rem 0 0; }
dt { color: var(--muted); font-size: .82rem; font-weight: 700; }
dd { min-width: 0; margin: 0; overflow-wrap: anywhere; }
code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: .86em; overflow-wrap: anywhere; }
details { margin-top: .75rem; padding-top: .75rem; border-top: 1px solid var(--line); }
summary { cursor: pointer; font-weight: 750; }
summary:focus-visible { outline: 3px solid var(--accent); outline-offset: 4px; }
.finding { margin-top: 1rem; padding-top: 1rem; border-top: 1px solid var(--line); }
.finding:first-of-type { border-top: 0; }
.evidence { margin: .65rem 0 0; padding-left: 1.2rem; }
.trust { padding: .7rem .85rem; border-left: 4px solid var(--warning); background: var(--warning-soft); color: var(--warning); }
footer { margin-top: 3rem; padding-top: 1rem; border-top: 1px solid var(--line); color: var(--muted); font-size: .9rem; }
@media (prefers-color-scheme: dark) {
  :root { --bg: #101719; --surface: #172126; --ink: #edf5f3; --muted: #b2c1bd; --line: #33423f; --accent: #77d0db; --accent-soft: #173d42; --warning: #ffc677; --warning-soft: #3a2b18; }
}
@media (max-width: 560px) { main { width: min(100% - 1.2rem, 1120px); } dl { grid-template-columns: 1fr; } dd { margin-bottom: .45rem; } }
"""


def _h(value: object) -> str:
    if value is None:
        return "&mdash;"
    return html.escape(str(value), quote=True)


def _dl(rows: Iterable[tuple[str, object]]) -> str:
    return "<dl>" + "".join(
        f"<dt>{_h(label)}</dt><dd><code>{_h(value)}</code></dd>"
        for label, value in rows
    ) + "</dl>"


def _render_html(
    registry: dict[str, object],
    evidence: dict[str, dict[str, object]],
    privacy_classification: str,
) -> bytes:
    cases = registry["cases"]
    case_cards = []
    for record in cases:
        case_cards.append(
            '<article class="card">'
            f"<p class=\"eyebrow\">Verified Open Demo</p><h3>{_h(record['case_id'])}</h3>"
            + _dl(
                (
                    ("Version", record["case_version"]),
                    ("Release mode", record["release_mode"]),
                    ("Exposure", record["exposure_state"]),
                    ("Revision", record["source_revision"]),
                    ("Package files", record["package_file_count"]),
                    ("Package manifest", record["package_manifest_sha256"]),
                    ("Package checksums", record["package_checksums_sha256"]),
                    ("Static validation", record["static_validation"]),
                    ("Public runtime checks", record["public_runtime_checks"]),
                    ("Scientific correctness", record["scientific_correctness"]),
                    ("Measurement validity", record["measurement_validity"]),
                )
            )
            + "<details><summary>Package notices and boundaries</summary>"
            + "<p><strong>Licenses</strong></p><ul>"
            + "".join(
                f"<li>{_h(item['scope'])}: {_h(item['terms'])} "
                f"(<code>{_h(item['notice'])}</code>)</li>"
                for item in record["licenses"]
            )
            + "</ul><p><strong>Known limitations</strong></p><ul>"
            + "".join(
                f"<li>{_h(item)}</li>" for item in record["known_limitations"]
            )
            + "</ul><p><strong>Claims not made</strong></p><ul>"
            + "".join(
                f"<li>{_h(item)}</li>" for item in record["claims_not_made"]
            )
            + "</ul></details>"
            + "</article>"
        )

    sections = [
        "<section aria-labelledby=\"cases-heading\"><h2 id=\"cases-heading\">Verified case registry</h2>"
        '<div class="grid">' + "".join(case_cards) + "</div></section>"
    ]
    if "audit" in evidence:
        audit = evidence["audit"]
        finding_html = []
        for finding in audit["findings"]:
            evidence_items = "".join(
                "<li>"
                f"<strong>{_h(item['kind'])}</strong> — {_h(item['summary'])} "
                f"<span class=\"muted\">({_h(item['reference'])})</span>"
                "</li>"
                for item in finding["evidence"]
            ) or "<li>No evidence item recorded.</li>"
            finding_html.append(
                '<article class="finding">'
                f"<h3>{_h(finding['id'])}: {_h(finding['title'])}</h3>"
                + _dl(
                    (
                        ("Layer / competency", f"{finding['layer']} / {finding['competency']}"),
                        ("Severity", finding["severity"]),
                        ("Status", finding["status"]),
                        ("Baseline", finding["baseline_state"]),
                    )
                )
                + f"<p><strong>Claim:</strong> {_h(finding['claim'])}</p>"
                f"<p><strong>First broken contract:</strong> {_h(finding['first_broken_contract'])}</p>"
                f"<details><summary>Evidence ({len(finding['evidence'])})</summary>"
                f"<ul class=\"evidence\">{evidence_items}</ul></details></article>"
            )
        summary = audit["summary"]
        sections.append(
            "<section aria-labelledby=\"audit-heading\"><h2 id=\"audit-heading\">Audit evidence</h2>"
            '<p class="trust">Local integrity-checked declarations; scientific correctness remains not_assessed.</p>'
            '<div class="card">'
            + _dl(
                (
                    ("Report state", audit["report_status"]),
                    ("Preflight", audit["preflight_state"]),
                    ("Findings", summary["finding_count"]),
                    ("Stale findings", summary["stale_finding_count"]),
                    ("Baseline head", audit["baseline"]["head"]),
                    ("G0 state", audit["g0_gate"]["status"]),
                )
            )
            + "".join(finding_html)
            + "<details><summary>Audit limitations</summary><ul>"
            + "".join(f"<li>{_h(item)}</li>" for item in audit["limitations"])
            + "</ul></details>"
            + "</div></section>"
        )
    if "training" in evidence:
        training = evidence["training"]
        target_cards = []
        for target in training_core.TARGETS:
            record = training["targets"][target]
            review_items = "".join(
                "<li>"
                f"<strong>{_h(review['reviewer_alias'])}</strong>: "
                f"{_h(review['decision'])}; "
                + ", ".join(
                    f"{_h(band)}={_h(review['ratings'][band])}"
                    for band in training_core.BANDS
                )
                + f"; gap recorded={_h(review['gap_recorded'])}</li>"
                for review in record["declared_reviews"]
            ) or "<li>No active declared review.</li>"
            disagreement_items = "".join(
                f"<li>{_h(band)}: {_h(', '.join(record['rating_disagreements'][band]))}</li>"
                for band in training_core.BANDS
                if band in record["rating_disagreements"]
            ) or "<li>No active rating disagreement.</li>"
            target_cards.append(
                '<article class="card">'
                f"<p class=\"eyebrow\">{_h(target)}</p><h3>{_h(record['human_review_state'])}</h3>"
                + _dl(
                    (
                        ("Attempt", record["attempt_state"]),
                        ("Structure", record["structure_state"]),
                        ("Current draft", record["current_draft_state"]),
                        ("Declared reviews", len(record["declared_reviews"])),
                        ("Evidence gaps", record["evidence_gap_count"]),
                        ("Scientific correctness", record["scientific_correctness"]),
                    )
                )
                + "<details><summary>Declared review evidence</summary>"
                + f"<ul class=\"evidence\">{review_items}</ul>"
                + "<p><strong>Rating disagreements</strong></p>"
                + f"<ul class=\"evidence\">{disagreement_items}</ul></details>"
                + "</article>"
            )
        sections.append(
            "<section aria-labelledby=\"training-heading\"><h2 id=\"training-heading\">Training progress</h2>"
            '<p class="trust">Human-declared progress and structural checks; no semantic or scientific certification.</p>'
            '<div class="grid">' + "".join(target_cards) + "</div></section>"
        )

    sensitive = " sensitive" if privacy_classification == LOCAL_PRIVACY_CLASSIFICATION else ""
    document = (
        "<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" content="default-src &#x27;none&#x27;; style-src &#x27;self&#x27;; font-src &#x27;none&#x27;; img-src &#x27;none&#x27;; connect-src &#x27;none&#x27;; script-src &#x27;none&#x27;; object-src &#x27;none&#x27;; frame-src &#x27;none&#x27;; base-uri &#x27;none&#x27;; form-action &#x27;none&#x27;">'
        '<meta name="referrer" content="no-referrer">'
        '<link rel="stylesheet" href="style.css">'
        "<title>RCSL Offline Evidence View</title></head><body><main>"
        "<header><p class=\"eyebrow\">Research Code Stewardship Lab</p>"
        "<h1>Offline evidence view</h1>"
        '<p class="lede">A deterministic, read-only projection of verified local records.</p>'
        f'<span class="badge{sensitive}">{_h(privacy_classification)}</span></header>'
        + "".join(sections)
        + "<footer>Integrity is not correctness. Human judgment and an external provenance trust anchor remain required.</footer>"
        "</main></body></html>\n"
    )
    return document.encode("utf-8")


def _write_view_tree(owned: release_core.OwnedOutput, files: dict[str, bytes]) -> None:
    data_descriptor = release_core._open_or_create_directory_at(owned.descriptor, "data")
    try:
        evidence_descriptor = release_core._open_or_create_directory_at(
            data_descriptor, "evidence"
        )
        os.close(evidence_descriptor)
    finally:
        os.close(data_descriptor)
    release_core._write_tree_at(owned.descriptor, files)
    os.fsync(owned.descriptor)


def _validate_and_pin_output(
    output_value: Path | str,
) -> tuple[Path, _PinnedOutputParent]:
    requested = _normalized_path(output_value)
    if _has_protected_component(requested):
        raise ViewError("static-view output cannot enter protected instructor material")
    if not requested.name or requested.name in {".", ".."}:
        raise ViewError("static-view output must name a new directory")
    try:
        parent = requested.parent.resolve(strict=True)
        descriptor = release_core._open_directory_chain(parent)
        opened = os.fstat(descriptor)
        current = parent.lstat()
    except (OSError, release_core.ReleaseError) as error:
        if "descriptor" in locals():
            os.close(descriptor)
        raise ViewError(f"could not pin static-view output parent: {error}") from error
    except ViewError:
        raise
    if (
        not stat.S_ISDIR(opened.st_mode)
        or not stat.S_ISDIR(current.st_mode)
        or parent.is_symlink()
        or (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino)
    ):
        os.close(descriptor)
        raise ViewError("static-view output parent identity is unsafe")
    output = parent / requested.name
    if _has_protected_component(output):
        os.close(descriptor)
        raise ViewError("static-view output cannot enter protected instructor material")
    if _is_within(output, release_core.REPOSITORY_ROOT.resolve()):
        os.close(descriptor)
        raise ViewError("release outputs must stay outside the public RCSL repository")
    try:
        os.stat(output.name, dir_fd=descriptor, follow_symlinks=False)
    except FileNotFoundError:
        pass
    except OSError as error:
        os.close(descriptor)
        raise ViewError(f"could not inspect static-view output target: {error}") from error
    else:
        os.close(descriptor)
        raise ViewError(f"refusing to overwrite existing output: {output}")
    return output, _PinnedOutputParent(
        path=parent,
        descriptor=descriptor,
        device=opened.st_dev,
        inode=opened.st_ino,
    )


def _assert_pinned_output_parent(pinned: _PinnedOutputParent) -> None:
    try:
        opened = os.fstat(pinned.descriptor)
        current = pinned.path.lstat()
    except OSError as error:
        raise ViewError("static-view output parent identity is no longer available") from error
    if (
        not stat.S_ISDIR(opened.st_mode)
        or not stat.S_ISDIR(current.st_mode)
        or pinned.path.is_symlink()
        or (opened.st_dev, opened.st_ino) != (pinned.device, pinned.inode)
        or (current.st_dev, current.st_ino) != (pinned.device, pinned.inode)
    ):
        raise ViewError("static-view output parent identity changed during assembly")


def _create_owned_output_from_pinned_parent(
    output: Path, pinned: _PinnedOutputParent
) -> release_core.OwnedOutput:
    _assert_pinned_output_parent(pinned)
    parent_descriptor = os.dup(pinned.descriptor)
    descriptor: int | None = None
    try:
        os.mkdir(output.name, 0o700, dir_fd=parent_descriptor)
        metadata = os.stat(
            output.name, dir_fd=parent_descriptor, follow_symlinks=False
        )
        created_identity = (metadata.st_dev, metadata.st_ino)
        descriptor = os.open(
            output.name,
            release_core._directory_open_flags(),
            dir_fd=parent_descriptor,
        )
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISDIR(metadata.st_mode)
            or created_identity != (opened.st_dev, opened.st_ino)
        ):
            raise ViewError("new static-view output identity changed during creation")
        _assert_pinned_output_parent(pinned)
        return release_core.OwnedOutput(
            output,
            metadata.st_dev,
            metadata.st_ino,
            descriptor,
            parent_descriptor,
        )
    except FileExistsError as error:
        os.close(parent_descriptor)
        raise ViewError(f"refusing to overwrite existing output: {output}") from error
    except BaseException:
        if descriptor is not None:
            os.close(descriptor)
        os.close(parent_descriptor)
        raise


def build_static_view(
    open_demo_bundles: Iterable[Path | str],
    output: Path | str,
    *,
    audit_workspace: Path | str | None = None,
    training_workspace: Path | str | None = None,
) -> Path:
    """Build one new external offline snapshot from verified, allowlisted data."""

    if isinstance(open_demo_bundles, (str, Path)):
        raise ViewError("open_demo_bundles must be an iterable of local paths")
    output_path, pinned = _validate_and_pin_output(output)
    try:
        try:
            iterator = iter(open_demo_bundles)
            bundles = list(islice(iterator, MAX_OPEN_DEMOS + 1))
        except TypeError as error:
            raise ViewError(
                "open_demo_bundles must be an iterable of local paths"
            ) from error
        if not bundles:
            raise ViewError("at least one verified Open Demo bundle is required")
        if len(bundles) > MAX_OPEN_DEMOS:
            raise ViewError(
                f"at most {MAX_OPEN_DEMOS} Open Demo bundles are supported"
            )
        return _build_static_view_pinned(
            bundles,
            output_path,
            pinned,
            audit_workspace=audit_workspace,
            training_workspace=training_workspace,
        )
    finally:
        os.close(pinned.descriptor)


def _build_static_view_pinned(
    bundles: list[Path | str],
    output_path: Path,
    pinned_parent: _PinnedOutputParent,
    *,
    audit_workspace: Path | str | None,
    training_workspace: Path | str | None,
) -> Path:

    cases: list[dict[str, object]] = []
    seen_manifests: set[str] = set()
    version_bindings: dict[tuple[str, str], str] = {}
    for index, bundle in enumerate(bundles):
        canonical, manifest, files, verification = _verified_open_demo(bundle)
        _reject_overlap(output_path, canonical, label=f"Open Demo input {index + 1}")
        digest = _require_digest(
            verification.get("manifest_sha256"), field="Open Demo manifest digest"
        )
        if digest in seen_manifests:
            raise ViewError("duplicate Open Demo bundle manifest")
        seen_manifests.add(digest)
        case = _open_case_record(manifest, files, verification)
        identity = (str(case["case_id"]), str(case["case_version"]))
        source_tree = str(case["source_tree_sha256"])
        if identity in version_bindings and version_bindings[identity] != source_tree:
            raise ViewError(
                "one Open Demo case ID and version cannot bind multiple source trees"
            )
        version_bindings[identity] = source_tree
        cases.append(case)
    cases.sort(
        key=lambda record: (
            str(record["case_id"]),
            str(record["case_version"]),
            str(record["package_manifest_sha256"]),
        )
    )
    registry = {
        "schema_version": SCHEMA_VERSION,
        "registry_type": "rcsl-open-demo-case-registry",
        "projection_scope": "verified-open-demo-metadata-only",
        "scientific_correctness": SCIENTIFIC_CORRECTNESS,
        "cases": cases,
    }
    _forbid_projection_keys(registry, field="case registry")
    _validate_registry(registry)

    evidence: dict[str, dict[str, object]] = {}
    if audit_workspace is not None:
        audit_root = _resolve_directory(audit_workspace, label="audit workspace")
        _reject_overlap(output_path, audit_root, label="audit workspace")
        try:
            _preflight_audit_workspace_limits(audit_root)
            evidence["audit"] = _project_audit(
                audit_core.build_report_data(audit_root)
            )
        except audit_core.AuditError as error:
            raise ViewError(f"audit workspace verification failed: {error}") from error
    if training_workspace is not None:
        training_root = _resolve_directory(training_workspace, label="training workspace")
        _reject_overlap(output_path, training_root, label="training workspace")
        try:
            evidence["training"] = _project_training(
                training_core.get_redacted_status(training_root)
            )
        except training_core.TrainingError as error:
            raise ViewError(f"training workspace verification failed: {error}") from error

    privacy_classification = (
        LOCAL_PRIVACY_CLASSIFICATION if evidence else OPEN_PRIVACY_CLASSIFICATION
    )
    registry_bytes = _json_bytes(registry)
    if len(registry_bytes) > MAX_PROJECTED_JSON_BYTES:
        raise ViewError("case registry exceeds the projected-data limit")
    files_to_write: dict[str, bytes] = {
        "data/CASE_REGISTRY.json": registry_bytes,
        "style.css": STYLE_CSS,
        "VIEW_BOUNDARY.md": _boundary(privacy_classification),
    }
    evidence_records: list[dict[str, object]] = []
    for kind in sorted(evidence):
        data = _json_bytes(evidence[kind])
        if len(data) > MAX_PROJECTED_JSON_BYTES:
            raise ViewError(f"{kind} projection exceeds the projected-data limit")
        digest = _sha256_bytes(data)
        relative = f"data/evidence/{kind}-{digest}.json"
        files_to_write[relative] = data
        evidence_records.append(
            {"kind": kind, "path": relative, "sha256": digest, "size": len(data)}
        )
    files_to_write["index.html"] = _render_html(
        registry, evidence, privacy_classification
    )
    if any(len(data) > MAX_VIEW_FILE_BYTES for data in files_to_write.values()):
        raise ViewError("static-view output contains an oversized file")
    if sum(len(data) for data in files_to_write.values()) > MAX_VIEW_TOTAL_BYTES:
        raise ViewError("static-view output exceeds the aggregate byte limit")

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "manifest_type": MANIFEST_TYPE,
        "view_mode": VIEW_MODE,
        "privacy_classification": privacy_classification,
        "deployment_policy": (
            "do-not-deploy-local-sensitive-data"
            if evidence
            else "offline-open-demo-snapshot-only"
        ),
        "network_access": NETWORK_ACCESS,
        "code_execution": CODE_EXECUTION,
        "scientific_correctness": SCIENTIFIC_CORRECTNESS,
        "case_count": len(cases),
        "evidence_kinds": sorted(evidence),
        "evidence": evidence_records,
        "files": _file_records(files_to_write),
        "limitations": list(VIEW_LIMITATIONS),
    }
    _validate_manifest(manifest)
    files_to_write["VIEW_MANIFEST.json"] = _json_bytes(manifest)
    files_to_write["CHECKSUMS.sha256"] = _checksums(files_to_write)

    owned: release_core.OwnedOutput | None = None
    try:
        owned = _create_owned_output_from_pinned_parent(output_path, pinned_parent)
        _write_view_tree(owned, files_to_write)
        release_core._assert_owned_output_identity(owned)
        _verify_owned_static_view(owned)
        release_core._assert_owned_output_identity(owned)
    except ViewError:
        if owned is not None:
            release_core._close_owned_output(owned)
        raise
    except release_core.ReleaseError as error:
        if owned is not None:
            release_core._close_owned_output(owned)
        raise ViewError(str(error)) from error
    except OSError as error:
        if owned is not None:
            release_core._close_owned_output(owned)
        raise ViewError(f"could not finish static-view output safely: {error}") from error
    except BaseException:
        if owned is not None:
            release_core._close_owned_output(owned)
        raise
    release_core._close_owned_output(owned)
    return output_path


def _collect_view_tree(
    root_value: Path | str,
    *,
    borrowed_descriptor: int | None = None,
    expected_identity: tuple[int, int] | None = None,
) -> _FrozenView:
    if borrowed_descriptor is None:
        root = _resolve_directory(root_value, label="static view")
        try:
            root_lstat = root.lstat()
        except OSError as error:
            raise ViewError("static-view root identity is unavailable") from error
        try:
            root_descriptor = release_core._open_directory_chain(root)
        except release_core.ReleaseError as error:
            raise ViewError(str(error)) from error
        expected_root_identity = (root_lstat.st_dev, root_lstat.st_ino)
    else:
        root = _normalized_path(root_value)
        try:
            root_descriptor = os.dup(borrowed_descriptor)
        except OSError as error:
            raise ViewError("could not duplicate the owned static-view root") from error
        expected_root_identity = expected_identity
    try:
        opened = os.fstat(root_descriptor)
    except OSError as error:
        os.close(root_descriptor)
        raise ViewError("could not pin the static-view root") from error
    if expected_root_identity is None or (
        opened.st_dev,
        opened.st_ino,
    ) != expected_root_identity:
        os.close(root_descriptor)
        raise ViewError("static-view root identity changed before verification")
    files: dict[str, release_core.FileBlob] = {}
    directories: set[str] = set()
    identities: dict[str, tuple[int, int, int, int, int]] = {}
    collision_keys: set[str] = set()
    total = 0
    total_entries = 0

    def walk(descriptor: int, prefix: tuple[str, ...]) -> None:
        nonlocal total, total_entries
        names = _bounded_names(
            descriptor,
            label="static view file limit",
            maximum_entries=MAX_VIEW_ENTRIES - total_entries,
        )
        total_entries += len(names)
        local: set[str] = set()
        for name in names:
            if name != unicodedata.normalize("NFC", name):
                raise ViewError("static view contains a non-NFC path")
            key = name.casefold()
            if key in local:
                raise ViewError("static view contains a case-insensitive path collision")
            local.add(key)
            if key == PROTECTED_DIRECTORY_NAME.casefold():
                raise ViewError("static view contains protected instructor material")
            relative = PurePosixPath(*(prefix + (name,))).as_posix()
            try:
                safe = release_core._validate_relative_path(
                    relative, field="static-view path"
                )
            except release_core.ReleaseError as error:
                raise ViewError(str(error)) from error
            collision = unicodedata.normalize("NFC", safe).casefold()
            if collision in collision_keys:
                raise ViewError("static view contains a normalized path collision")
            collision_keys.add(collision)
            try:
                metadata = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            except OSError as error:
                raise ViewError(f"could not inspect static-view path {safe}: {error}") from error
            if stat.S_ISLNK(metadata.st_mode):
                raise ViewError(f"static view contains a symlink: {safe}")
            identities[safe] = (
                metadata.st_dev,
                metadata.st_ino,
                metadata.st_size,
                metadata.st_mtime_ns,
                metadata.st_mode,
            )
            if stat.S_ISDIR(metadata.st_mode):
                if safe not in EXPECTED_DIRECTORIES:
                    raise ViewError(
                        "static-view directory inventory contains an unexpected path"
                    )
                if os.name == "posix" and stat.S_IMODE(metadata.st_mode) != 0o700:
                    raise ViewError(f"static-view directory has an invalid mode: {safe}")
                directories.add(safe)
                try:
                    child = os.open(
                        name, release_core._directory_open_flags(), dir_fd=descriptor
                    )
                except OSError as error:
                    raise ViewError(f"could not open static-view directory {safe}: {error}") from error
                child_stat = os.fstat(child)
                if (child_stat.st_dev, child_stat.st_ino) != (
                    metadata.st_dev,
                    metadata.st_ino,
                ):
                    os.close(child)
                    raise ViewError(f"static-view directory identity changed: {safe}")
                try:
                    walk(child, prefix + (name,))
                finally:
                    os.close(child)
                continue
            if not stat.S_ISREG(metadata.st_mode):
                raise ViewError(f"static view contains a special filesystem object: {safe}")
            if os.name == "posix" and stat.S_IMODE(metadata.st_mode) != 0o600:
                raise ViewError(f"static-view file has an invalid mode: {safe}")
            if len(files) >= MAX_VIEW_FILES:
                raise ViewError(f"static view exceeds the {MAX_VIEW_FILES}-file limit")
            try:
                data = release_core._read_regular_file_at(
                    descriptor,
                    name,
                    label=f"static-view file {safe}",
                    maximum_bytes=MAX_VIEW_FILE_BYTES,
                    expected=metadata,
                )
            except release_core.ReleaseError as error:
                raise ViewError(str(error)) from error
            total += len(data)
            if total > MAX_VIEW_TOTAL_BYTES:
                raise ViewError("static view exceeds the aggregate byte limit")
            files[safe] = release_core.FileBlob(
                path=safe,
                data=data,
                sha256=_sha256_bytes(data),
                size=len(data),
                executable=bool(metadata.st_mode & 0o111),
            )

    try:
        if os.name == "posix" and stat.S_IMODE(opened.st_mode) != 0o700:
            raise ViewError("static-view root has an invalid directory mode")
        walk(root_descriptor, ())
        after = os.fstat(root_descriptor)
        current = root.lstat()
        if (
            (after.st_dev, after.st_ino) != (opened.st_dev, opened.st_ino)
            or not stat.S_ISDIR(current.st_mode)
            or root.is_symlink()
            or (current.st_dev, current.st_ino) != (opened.st_dev, opened.st_ino)
        ):
            raise ViewError("static-view root identity changed during verification")
    except BaseException:
        os.close(root_descriptor)
        raise
    return _FrozenView(
        root=root,
        descriptor=root_descriptor,
        device=opened.st_dev,
        inode=opened.st_ino,
        files=files,
        directories=directories,
        identities=identities,
    )


def _assert_frozen_view_identities(snapshot: _FrozenView) -> None:
    """Rewalk the pinned tree and match every retained directory entry."""

    expected_paths = set(snapshot.identities)

    def identity(metadata: os.stat_result) -> tuple[int, int, int, int, int]:
        return (
            metadata.st_dev,
            metadata.st_ino,
            metadata.st_size,
            metadata.st_mtime_ns,
            metadata.st_mode,
        )

    def walk(descriptor: int, prefix: tuple[str, ...]) -> None:
        expected_names = {
            PurePosixPath(path).parts[len(prefix)]
            for path in expected_paths
            if PurePosixPath(path).parts[: len(prefix)] == prefix
            and len(PurePosixPath(path).parts) == len(prefix) + 1
        }
        names = _bounded_names(
            descriptor,
            label="static view identity recheck",
            maximum_entries=len(expected_names) + 1,
        )
        if set(names) != expected_names:
            raise ViewError("static-view entries changed during semantic verification")
        for name in names:
            path = PurePosixPath(*(prefix + (name,))).as_posix()
            expected = snapshot.identities.get(path)
            if expected is None:
                raise ViewError("static-view entries changed during semantic verification")
            try:
                current = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            except OSError as error:
                raise ViewError(
                    f"static-view entry identity is unavailable: {path}"
                ) from error
            if identity(current) != expected:
                raise ViewError(
                    f"static-view entry identity changed during semantic verification: {path}"
                )
            if stat.S_ISDIR(current.st_mode):
                try:
                    child = os.open(
                        name,
                        release_core._directory_open_flags(),
                        dir_fd=descriptor,
                    )
                except OSError as error:
                    raise ViewError(
                        f"static-view directory identity is unavailable: {path}"
                    ) from error
                try:
                    if identity(os.fstat(child)) != expected:
                        raise ViewError(
                            f"static-view directory identity changed during semantic verification: {path}"
                        )
                    walk(child, prefix + (name,))
                finally:
                    os.close(child)
            else:
                try:
                    data = release_core._read_regular_file_at(
                        descriptor,
                        name,
                        label=f"static-view identity recheck {path}",
                        maximum_bytes=MAX_VIEW_FILE_BYTES,
                        expected=current,
                    )
                    after = os.stat(
                        name, dir_fd=descriptor, follow_symlinks=False
                    )
                    blob = snapshot.files.get(path)
                    if (
                        identity(after) != expected
                        or blob is None
                        or data != blob.data
                        or _sha256_bytes(data) != blob.sha256
                    ):
                        raise ViewError(
                            f"static-view file identity changed during semantic verification: {path}"
                        )
                except ViewError:
                    raise
                except (OSError, release_core.ReleaseError) as error:
                    raise ViewError(
                        f"static-view file identity is unavailable: {path}"
                    ) from error

    walk(snapshot.descriptor, ())


def _parse_checksums(data: bytes) -> dict[str, str]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ViewError("CHECKSUMS.sha256 must be UTF-8") from error
    records: dict[str, str] = {}
    collisions: set[str] = set()
    for index, line in enumerate(text.splitlines()):
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if match is None:
            raise ViewError(f"malformed checksum line {index + 1}")
        try:
            path = release_core._validate_relative_path(
                match.group(2), field=f"checksum line {index + 1} path"
            )
        except release_core.ReleaseError as error:
            raise ViewError(str(error)) from error
        collision = path.casefold()
        if collision in collisions:
            raise ViewError("checksums contain a duplicate or colliding path")
        collisions.add(collision)
        records[path] = match.group(1)
    if not records:
        raise ViewError("CHECKSUMS.sha256 is empty")
    canonical = "".join(f"{records[path]}  {path}\n" for path in sorted(records))
    if canonical != text:
        raise ViewError("CHECKSUMS.sha256 is not in canonical order")
    return records


def _strict_json(data: bytes, *, field: str) -> dict[str, object]:
    try:
        return release_core._strict_json_bytes(
            data, field=field, maximum_bytes=MAX_PROJECTED_JSON_BYTES
        )
    except release_core.ReleaseError as error:
        raise ViewError(str(error)) from error


def _validate_file_record(value: object, *, field: str) -> dict[str, object]:
    record = _expect_exact_keys(value, {"path", "sha256", "size"}, field=field)
    try:
        path = release_core._validate_relative_path(record["path"], field=f"{field}.path")
    except release_core.ReleaseError as error:
        raise ViewError(str(error)) from error
    record["path"] = path
    _require_digest(record["sha256"], field=f"{field}.sha256")
    _require_nonnegative_int(record["size"], field=f"{field}.size")
    return record


def _validate_case_record(value: object, *, field: str) -> dict[str, object]:
    expected = {
        "case_id",
        "case_version",
        "release_mode",
        "exposure_state",
        "release_state",
        "source_revision",
        "source_revision_scope",
        "repository_worktree_state",
        "source_tree_sha256",
        "package_manifest_sha256",
        "package_checksums_sha256",
        "package_file_count",
        "licenses",
        "known_limitations",
        "claims_not_made",
        "static_validation",
        "public_runtime_checks",
        "scientific_correctness",
        "measurement_validity",
    }
    record = _expect_exact_keys(value, expected, field=field)
    for key in (
        "case_id",
        "release_mode",
        "exposure_state",
        "release_state",
        "source_revision_scope",
        "repository_worktree_state",
        "static_validation",
        "public_runtime_checks",
    ):
        _require_text(record[key], field=f"{field}.{key}")
    try:
        release_core._validate_id(record["case_id"], field=f"{field}.case_id")
    except release_core.ReleaseError as error:
        raise ViewError(str(error)) from error
    version = _require_text(record["case_version"], field=f"{field}.case_version")
    if not SEMVER.fullmatch(version):
        raise ViewError(f"{field}.case_version must use semantic versioning")
    _require_digest(record["source_revision"], field=f"{field}.source_revision", git=True)
    _require_digest(record["source_tree_sha256"], field=f"{field}.source_tree_sha256")
    _require_digest(record["package_manifest_sha256"], field=f"{field}.package_manifest_sha256")
    _require_digest(record["package_checksums_sha256"], field=f"{field}.package_checksums_sha256")
    package_file_count = _require_nonnegative_int(
        record["package_file_count"], field=f"{field}.package_file_count"
    )
    if package_file_count < 1:
        raise ViewError(f"{field}.package_file_count must be positive")
    licenses = record["licenses"]
    if not isinstance(licenses, list) or not licenses:
        raise ViewError(f"{field}.licenses must be a non-empty list")
    for index, license_value in enumerate(licenses):
        license_record = _expect_exact_keys(
            license_value,
            {"scope", "terms", "notice"},
            field=f"{field}.licenses[{index}]",
        )
        for key in ("scope", "terms", "notice"):
            _require_text(
                license_record[key], field=f"{field}.licenses[{index}].{key}"
            )
        try:
            release_core._validate_relative_path(
                license_record["notice"],
                field=f"{field}.licenses[{index}].notice",
            )
        except release_core.ReleaseError as error:
            raise ViewError(str(error)) from error
    for key in ("known_limitations", "claims_not_made"):
        values = record[key]
        if not isinstance(values, list) or not values:
            raise ViewError(f"{field}.{key} must be a non-empty text list")
        normalized = [
            _require_text(item, field=f"{field}.{key}[{index}]")
            for index, item in enumerate(values)
        ]
        if len(normalized) != len(set(normalized)):
            raise ViewError(f"{field}.{key} contains duplicate entries")
    if record["scientific_correctness"] != SCIENTIFIC_CORRECTNESS:
        raise ViewError(f"{field} crossed the scientific trust boundary")
    if record["measurement_validity"] != "not_assessed":
        raise ViewError(f"{field} crossed the measurement-validity boundary")
    if (
        record["release_mode"] != "open-demo"
        or record["exposure_state"] != "historically-public-honor-isolation"
        or record["release_state"] != "open-demo-artifact"
        or record["source_revision_scope"] != "repository-head-not-byte-identity"
        or record["repository_worktree_state"] not in {"clean", "dirty"}
        or record["static_validation"] != "passed"
        or record["public_runtime_checks"] not in {"passed", "not-run"}
    ):
        raise ViewError(f"{field} contains an invalid Open Demo state")
    return record


def _validate_registry(value: object) -> dict[str, object]:
    registry = _expect_exact_keys(
        value,
        {
            "schema_version",
            "registry_type",
            "projection_scope",
            "scientific_correctness",
            "cases",
        },
        field="case registry",
    )
    if type(registry["schema_version"]) is not int or registry["schema_version"] != SCHEMA_VERSION:
        raise ViewError("unsupported case registry schema version")
    if (
        registry["registry_type"] != "rcsl-open-demo-case-registry"
        or registry["projection_scope"] != "verified-open-demo-metadata-only"
        or registry["scientific_correctness"] != SCIENTIFIC_CORRECTNESS
    ):
        raise ViewError("case registry boundary is invalid")
    cases = registry["cases"]
    if not isinstance(cases, list) or not cases or len(cases) > MAX_OPEN_DEMOS:
        raise ViewError("case registry must contain a bounded, non-empty cases list")
    seen: set[str] = set()
    version_bindings: dict[tuple[str, str], str] = {}
    normalized: list[tuple[str, str, str]] = []
    for index, case in enumerate(cases):
        record = _validate_case_record(case, field=f"case registry cases[{index}]")
        digest = str(record["package_manifest_sha256"])
        if digest in seen:
            raise ViewError("case registry contains a duplicate source manifest")
        seen.add(digest)
        identity = (str(record["case_id"]), str(record["case_version"]))
        source_tree = str(record["source_tree_sha256"])
        if identity in version_bindings and version_bindings[identity] != source_tree:
            raise ViewError(
                "one case ID and version cannot bind multiple source trees"
            )
        version_bindings[identity] = source_tree
        normalized.append(
            (str(record["case_id"]), str(record["case_version"]), digest)
        )
    if normalized != sorted(normalized):
        raise ViewError("case registry is not in deterministic order")
    _forbid_projection_keys(registry, field="case registry")
    return registry


def _validate_audit_projection(value: object) -> dict[str, object]:
    audit = _expect_exact_keys(
        value,
        {
            "schema_version",
            "evidence_type",
            "privacy_classification",
            "validator_scope",
            "report_status",
            "preflight_state",
            "scientific_correctness",
            "baseline",
            "g0_gate",
            "integrity",
            "summary",
            "findings",
            "limitations",
        },
        field="audit evidence",
    )
    if type(audit["schema_version"]) is not int or audit["schema_version"] != SCHEMA_VERSION:
        raise ViewError("unsupported audit evidence schema version")
    if (
        audit["evidence_type"] != "rcsl-audit-evidence-view"
        or audit["privacy_classification"] != LOCAL_PRIVACY_CLASSIFICATION
        or audit["validator_scope"] != "local_hash_chain_lifecycle_integrity_only"
        or audit["scientific_correctness"] != SCIENTIFIC_CORRECTNESS
    ):
        raise ViewError("audit evidence boundary is invalid")
    report_status = _require_text(
        audit["report_status"], field="audit evidence report_status"
    )
    if report_status not in {"draft", "review-ready"}:
        raise ViewError("audit evidence report_status is invalid")
    preflight_state = _require_text(
        audit["preflight_state"], field="audit evidence preflight_state"
    )
    if preflight_state not in {"ready", "not-ready"}:
        raise ViewError("audit evidence preflight_state is invalid")
    baseline = _expect_exact_keys(
        audit["baseline"], {"head", "branch", "captured_at"}, field="audit evidence baseline"
    )
    _require_digest(baseline["head"], field="audit baseline head", git=True)
    if baseline["branch"] is not None:
        _require_text(baseline["branch"], field="audit baseline branch")
    try:
        release_core._validate_timestamp(
            baseline["captured_at"], field="audit baseline captured_at"
        )
    except release_core.ReleaseError as error:
        raise ViewError(str(error)) from error
    gate = _expect_exact_keys(
        audit["g0_gate"], {"status", "contract_sha256"}, field="audit evidence G0 gate"
    )
    gate_status = _require_text(gate["status"], field="audit G0 status")
    if gate_status not in audit_core.G0_STATUSES:
        raise ViewError("audit G0 status is invalid")
    if preflight_state == "ready" and gate_status != "approved":
        raise ViewError("audit ready preflight requires an approved G0 gate")
    _require_digest(gate["contract_sha256"], field="audit G0 contract digest")
    integrity = _expect_exact_keys(
        audit["integrity"], {"event_count", "last_event_hash"}, field="audit evidence integrity"
    )
    _require_nonnegative_int(integrity["event_count"], field="audit event_count")
    _require_digest(integrity["last_event_hash"], field="audit last_event_hash")
    summary = _expect_exact_keys(
        audit["summary"],
        {"finding_count", "stale_finding_count", "by_status", "by_layer", "by_competency", "by_severity"},
        field="audit evidence summary",
    )
    _require_nonnegative_int(summary["finding_count"], field="audit finding_count")
    _require_nonnegative_int(summary["stale_finding_count"], field="audit stale_finding_count")
    if summary["stale_finding_count"] > summary["finding_count"]:
        raise ViewError("audit stale finding count exceeds finding count")
    for name, keys in (
        ("by_status", audit_core.FINDING_STATUSES),
        ("by_layer", audit_core.LAYERS),
        ("by_competency", audit_core.COMPETENCIES),
        ("by_severity", audit_core.SEVERITIES),
    ):
        counts = _expect_exact_keys(summary[name], set(keys), field=f"audit summary {name}")
        for key in keys:
            _require_nonnegative_int(counts[key], field=f"audit summary {name}.{key}")
        if sum(counts.values()) != summary["finding_count"]:
            raise ViewError(f"audit summary {name} does not total finding_count")
    findings = audit["findings"]
    if not isinstance(findings, list) or len(findings) > MAX_FINDINGS:
        raise ViewError("audit findings list is invalid")
    if len(findings) != summary["finding_count"]:
        raise ViewError("audit evidence finding_count does not match findings")
    finding_keys = {
        "id", "title", "layer", "competency", "severity", "claim",
        "first_broken_contract", "status", "created_at", "updated_at",
        "baseline_state", "baseline_current", "evidence",
    }
    evidence_keys = {"id", "kind", "reference", "summary", "recorded_at"}
    seen_findings: set[str] = set()
    total_evidence = 0
    for index, finding_value in enumerate(findings):
        finding = _expect_exact_keys(finding_value, finding_keys, field=f"audit finding {index}")
        for key in finding_keys - {"evidence", "baseline_current"}:
            _require_text(finding[key], field=f"audit finding {index}.{key}")
        baseline_current = _require_bool(
            finding["baseline_current"],
            field=f"audit finding {index}.baseline_current",
        )
        finding_id = str(finding["id"])
        if not audit_core.FINDING_ID_PATTERN.fullmatch(finding_id) or finding_id in seen_findings:
            raise ViewError("audit evidence contains an invalid or duplicate finding ID")
        seen_findings.add(finding_id)
        if finding["layer"] not in audit_core.LAYERS:
            raise ViewError("audit evidence contains an invalid finding layer")
        if finding["competency"] not in audit_core.COMPETENCIES:
            raise ViewError("audit evidence contains an invalid finding competency")
        if finding["severity"] not in audit_core.SEVERITIES:
            raise ViewError("audit evidence contains an invalid finding severity")
        if finding["status"] not in audit_core.FINDING_STATUSES:
            raise ViewError("audit evidence contains an invalid finding status")
        if finding["baseline_state"] not in {"current", "stale"}:
            raise ViewError("audit evidence contains an invalid baseline state")
        if baseline_current != (finding["baseline_state"] == "current"):
            raise ViewError("audit finding baseline state is inconsistent")
        try:
            release_core._validate_timestamp(
                finding["created_at"], field=f"audit finding {index}.created_at"
            )
            release_core._validate_timestamp(
                finding["updated_at"], field=f"audit finding {index}.updated_at"
            )
        except release_core.ReleaseError as error:
            raise ViewError(str(error)) from error
        evidence = finding["evidence"]
        if not isinstance(evidence, list) or len(evidence) > MAX_EVIDENCE_PER_FINDING:
            raise ViewError(f"audit finding {index} evidence list is invalid")
        total_evidence += len(evidence)
        if total_evidence > MAX_AUDIT_EVIDENCE:
            raise ViewError(
                f"audit evidence exceeds the {MAX_AUDIT_EVIDENCE}-evidence limit"
            )
        seen_evidence: set[str] = set()
        for item_index, item_value in enumerate(evidence):
            item = _expect_exact_keys(
                item_value, evidence_keys, field=f"audit finding {index} evidence {item_index}"
            )
            for key in evidence_keys:
                text = _require_text(item[key], field=f"audit evidence {key}")
                if key == "reference":
                    candidate = text.strip()
                    if (
                        candidate != text
                        or any(character in text for character in "\r\n\t")
                        or os.path.isabs(candidate)
                        or WINDOWS_ABSOLUTE.match(candidate)
                        or candidate.startswith("\\\\")
                        or candidate.casefold().startswith("file:")
                    ):
                        raise ViewError(
                            "audit evidence contains an absolute local reference"
                        )
            evidence_id = str(item["id"])
            if (
                not audit_core.FINDING_ID_PATTERN.fullmatch(evidence_id)
                or evidence_id in seen_evidence
            ):
                raise ViewError("audit evidence contains an invalid or duplicate evidence ID")
            seen_evidence.add(evidence_id)
            if item["kind"] not in audit_core.EVIDENCE_KINDS:
                raise ViewError("audit evidence contains an invalid evidence kind")
            try:
                release_core._validate_timestamp(
                    item["recorded_at"], field="audit evidence recorded_at"
                )
            except release_core.ReleaseError as error:
                raise ViewError(str(error)) from error
    expected_summary = {
        "finding_count": len(findings),
        "stale_finding_count": sum(
            1 for finding in findings if finding["baseline_state"] == "stale"
        ),
        "by_status": {
            key: sum(1 for finding in findings if finding["status"] == key)
            for key in audit_core.FINDING_STATUSES
        },
        "by_layer": {
            key: sum(1 for finding in findings if finding["layer"] == key)
            for key in audit_core.LAYERS
        },
        "by_competency": {
            key: sum(1 for finding in findings if finding["competency"] == key)
            for key in audit_core.COMPETENCIES
        },
        "by_severity": {
            key: sum(1 for finding in findings if finding["severity"] == key)
            for key in audit_core.SEVERITIES
        },
    }
    if summary != expected_summary:
        raise ViewError("audit summary does not match retained findings")
    expected_report_status = (
        "review-ready"
        if preflight_state == "ready" and expected_summary["stale_finding_count"] == 0
        else "draft"
    )
    if report_status != expected_report_status:
        raise ViewError("audit report and preflight states are inconsistent")
    limitations = audit["limitations"]
    if not isinstance(limitations, list) or not limitations or len(limitations) > 103:
        raise ViewError("audit evidence limitations must be bounded and non-empty")
    for item in limitations:
        _require_text(item, field="audit evidence limitation")
    _forbid_projection_keys(audit, field="audit evidence")
    return audit


def _validate_training_projection(value: object) -> dict[str, object]:
    training = _expect_exact_keys(
        value,
        {
            "schema_version", "evidence_type", "privacy_classification", "case_id",
            "case_revision", "exposure_state", "validator_scope", "overall_state",
            "next_recommended_target", "scientific_correctness", "maturity_assessment",
            "targets", "privacy_note", "export_boundary",
        },
        field="training evidence",
    )
    if type(training["schema_version"]) is not int or training["schema_version"] != SCHEMA_VERSION:
        raise ViewError("unsupported training evidence schema version")
    if (
        training["evidence_type"] != "rcsl-training-status-view"
        or training["privacy_classification"] != LOCAL_PRIVACY_CLASSIFICATION
        or training["scientific_correctness"] != SCIENTIFIC_CORRECTNESS
        or training["maturity_assessment"] != "human-only"
    ):
        raise ViewError("training evidence boundary is invalid")
    for key in ("case_id", "exposure_state", "validator_scope", "overall_state", "privacy_note", "export_boundary"):
        _require_text(training[key], field=f"training evidence {key}")
    if (
        training["case_id"] != training_core.CASE_ID
        or training["exposure_state"] != training_core.EXPOSURE_STATE
        or training["validator_scope"] != training_core.VALIDATOR_SCOPE
        or training["overall_state"]
        not in {
            "in-progress",
            "human-reviewed-complete",
            "human-reviewed-complete-with-unsubmitted-draft",
        }
        or training["privacy_note"] != TRAINING_PRIVACY_NOTE
        or training["export_boundary"] != TRAINING_EXPORT_BOUNDARY
    ):
        raise ViewError("training evidence state or redaction boundary is invalid")
    try:
        training_core._validate_case_revision(
            training["case_revision"], field="training evidence case_revision"
        )
    except training_core.TrainingError as error:
        raise ViewError(str(error)) from error
    if training["next_recommended_target"] is not None:
        next_target = _require_text(
            training["next_recommended_target"], field="training next target"
        )
        if next_target not in training_core.TARGETS:
            raise ViewError("training next target is invalid")
    targets = _expect_exact_keys(
        training["targets"], set(training_core.TARGETS), field="training evidence targets"
    )
    target_keys = {
        "attempt_state", "structure_state", "human_review_state", "maturity_assessment",
        "semantic_assessment", "scientific_correctness", "attempt_count",
        "latest_attempt_id", "latest_attempt_sha256", "draft_changes_since_submission",
        "current_draft_state", "declared_reviews", "rating_disagreements",
        "historical_review_count", "evidence_gap_count",
    }
    review_keys = {"review_id", "reviewer_alias", "decision", "ratings", "gap_recorded"}
    seen_review_ids: set[str] = set()
    alias_order: list[str] = []
    expected_next_target: str | None = None
    all_human_passed = True
    has_unsubmitted_draft = False
    for target in training_core.TARGETS:
        record = _expect_exact_keys(targets[target], target_keys, field=f"training target {target}")
        for key in (
            "attempt_state", "structure_state", "human_review_state", "maturity_assessment",
            "semantic_assessment", "current_draft_state",
        ):
            _require_text(record[key], field=f"training target {target}.{key}")
        if (
            record["attempt_state"] not in {"submitted", "not-submitted"}
            or record["structure_state"] not in {"complete", "incomplete"}
            or record["human_review_state"]
            not in {
                "not-reviewed",
                "awaiting-human-review",
                "human-passed",
                "review-disagreement",
                "human-blocked",
                "needs-revision",
            }
            or record["maturity_assessment"] != "human-only"
            or record["semantic_assessment"] != "not_performed"
            or record["current_draft_state"]
            not in {
                "not-submitted",
                "matches-latest-submission",
                "changed-unsubmitted",
            }
        ):
            raise ViewError(f"training target {target} contains an invalid state")
        if record["scientific_correctness"] != SCIENTIFIC_CORRECTNESS:
            raise ViewError("training target crossed the scientific trust boundary")
        attempt_count = _require_nonnegative_int(
            record["attempt_count"], field=f"training target {target}.attempt_count"
        )
        historical_review_count = _require_nonnegative_int(
            record["historical_review_count"],
            field=f"training target {target}.historical_review_count",
        )
        evidence_gap_count = _require_nonnegative_int(
            record["evidence_gap_count"],
            field=f"training target {target}.evidence_gap_count",
        )
        draft_changed = _require_bool(
            record["draft_changes_since_submission"],
            field=f"training target {target}.draft_changes_since_submission",
        )
        if record["latest_attempt_id"] is not None:
            _require_text(record["latest_attempt_id"], field="training latest attempt ID")
        if record["latest_attempt_sha256"] is not None:
            _require_digest(record["latest_attempt_sha256"], field="training latest attempt digest")
        if (record["latest_attempt_id"] is None) != (
            record["latest_attempt_sha256"] is None
        ):
            raise ViewError("training latest attempt ID and digest must appear together")
        if (attempt_count == 0) != (record["latest_attempt_id"] is None):
            raise ViewError("training attempt count does not match latest attempt metadata")
        expected_attempt_state = "submitted" if attempt_count else "not-submitted"
        expected_draft_state = (
            "changed-unsubmitted"
            if draft_changed
            else "matches-latest-submission"
            if attempt_count
            else "not-submitted"
        )
        expected_attempt_id = (
            f"{target.upper()}-A{attempt_count:03d}" if attempt_count else None
        )
        if (
            record["attempt_state"] != expected_attempt_state
            or record["current_draft_state"] != expected_draft_state
            or record["latest_attempt_id"] != expected_attempt_id
            or (attempt_count == 0 and draft_changed)
            or attempt_count > training_core.MAX_ATTEMPTS_PER_TARGET
        ):
            raise ViewError(f"training target {target} attempt state is inconsistent")
        reviews = record["declared_reviews"]
        if not isinstance(reviews, list) or len(reviews) > training_core.MAX_REVIEWS_PER_TARGET:
            raise ViewError(f"training target {target} reviews list is invalid")
        decisions: set[str] = set()
        ratings_by_band = {band: set() for band in training_core.BANDS}
        gap_count = 0
        target_aliases: set[str] = set()
        total_review_count = historical_review_count + len(reviews)
        review_numbers: list[int] = []
        for index, review_value in enumerate(reviews):
            review = _expect_exact_keys(
                review_value, review_keys, field=f"training target {target} review {index}"
            )
            review_id = _require_text(review["review_id"], field="training review ID")
            prefix = f"{target.upper()}-R"
            suffix = review_id[len(prefix) :] if review_id.startswith(prefix) else ""
            number = int(suffix) if suffix.isdecimal() else 0
            if (
                review_id != f"{prefix}{number:03d}"
                or review_id in seen_review_ids
                or number < 1
                or number > total_review_count
            ):
                raise ViewError("training review ID is invalid or inconsistent")
            seen_review_ids.add(review_id)
            review_numbers.append(number)
            alias = _require_text(review["reviewer_alias"], field="training reviewer alias")
            if not REVIEWER_ALIAS.fullmatch(alias) or alias in target_aliases:
                raise ViewError("training reviewer alias is invalid")
            target_aliases.add(alias)
            if alias not in alias_order:
                alias_order.append(alias)
            decision = _require_text(
                review["decision"], field="training review decision"
            )
            if decision not in training_core.REVIEW_DECISIONS:
                raise ViewError("training review decision is invalid")
            decisions.add(decision)
            ratings = _expect_exact_keys(
                review["ratings"], set(training_core.BANDS), field="training review ratings"
            )
            for band in training_core.BANDS:
                rating = _require_text(
                    ratings[band], field=f"training rating {band}"
                )
                if rating not in training_core.RATING_VALUES:
                    raise ViewError(f"training rating {band} is invalid")
                ratings_by_band[band].add(rating)
            gap_recorded = _require_bool(
                review["gap_recorded"], field="training review gap_recorded"
            )
            gap_count += int(gap_recorded)
            try:
                training_core._validate_pass_consistency(
                    target, decision, review["ratings"]
                )
            except training_core.TrainingError as error:
                raise ViewError(str(error)) from error
        if review_numbers != sorted(review_numbers):
            raise ViewError(f"training target {target} reviews are not in deterministic order")
        disagreements = _require_object(
            record["rating_disagreements"], field="training rating disagreements"
        )
        if not set(disagreements).issubset(training_core.BANDS):
            raise ViewError("training rating disagreements contain an unknown band")
        for band, values in disagreements.items():
            if not isinstance(values, list):
                raise ViewError(f"training disagreement {band} must be a list")
            normalized_values = []
            for rating in values:
                normalized_rating = _require_text(
                    rating, field=f"training disagreement {band}"
                )
                if normalized_rating not in training_core.RATING_VALUES:
                    raise ViewError(f"training disagreement {band} is invalid")
                normalized_values.append(normalized_rating)
            if normalized_values != sorted(set(normalized_values)):
                raise ViewError(f"training disagreement {band} is not unique and sorted")
        expected_disagreements = {
            band: sorted(values)
            for band, values in ratings_by_band.items()
            if len(values) > 1
        }
        if disagreements != expected_disagreements:
            raise ViewError(f"training target {target} rating disagreements are inconsistent")
        expected_human_state = (
            "not-reviewed"
            if attempt_count == 0
            else "awaiting-human-review"
            if not decisions
            else "human-passed"
            if decisions == {"pass"}
            else "review-disagreement"
            if len(decisions) > 1
            else "human-blocked"
            if decisions == {"blocked"}
            else "needs-revision"
        )
        if (
            record["human_review_state"] != expected_human_state
            or evidence_gap_count != gap_count
            or total_review_count > training_core.MAX_REVIEWS_PER_TARGET
            or (attempt_count == 0 and total_review_count != 0)
        ):
            raise ViewError(f"training target {target} review state is inconsistent")
        if expected_human_state != "human-passed":
            all_human_passed = False
        if draft_changed:
            has_unsubmitted_draft = True
        if expected_next_target is None and (
            expected_human_state != "human-passed" or draft_changed
        ):
            expected_next_target = target
    expected_aliases = [f"reviewer-{index}" for index in range(1, len(alias_order) + 1)]
    if alias_order != expected_aliases:
        raise ViewError("training reviewer aliases are not in deterministic order")
    expected_overall = (
        "human-reviewed-complete-with-unsubmitted-draft"
        if all_human_passed and has_unsubmitted_draft
        else "human-reviewed-complete"
        if all_human_passed
        else "in-progress"
    )
    if (
        training["overall_state"] != expected_overall
        or training["next_recommended_target"] != expected_next_target
    ):
        raise ViewError("training overall state or next target is inconsistent")
    _forbid_projection_keys(training, field="training evidence")
    return training


def _validate_manifest(value: object) -> dict[str, object]:
    manifest = _expect_exact_keys(
        value,
        {
            "schema_version", "manifest_type", "view_mode", "privacy_classification",
            "deployment_policy", "network_access", "code_execution",
            "scientific_correctness", "case_count", "evidence_kinds", "evidence",
            "files", "limitations",
        },
        field="static-view manifest",
    )
    if type(manifest["schema_version"]) is not int or manifest["schema_version"] != SCHEMA_VERSION:
        raise ViewError("unsupported static-view manifest schema version")
    if (
        manifest["manifest_type"] != MANIFEST_TYPE
        or manifest["view_mode"] != VIEW_MODE
        or manifest["network_access"] != NETWORK_ACCESS
        or manifest["code_execution"] != CODE_EXECUTION
        or manifest["scientific_correctness"] != SCIENTIFIC_CORRECTNESS
    ):
        raise ViewError("static-view manifest boundary is invalid")
    privacy = manifest["privacy_classification"]
    if privacy not in {OPEN_PRIVACY_CLASSIFICATION, LOCAL_PRIVACY_CLASSIFICATION}:
        raise ViewError("static-view privacy classification is invalid")
    expected_policy = (
        "do-not-deploy-local-sensitive-data"
        if privacy == LOCAL_PRIVACY_CLASSIFICATION
        else "offline-open-demo-snapshot-only"
    )
    if manifest["deployment_policy"] != expected_policy:
        raise ViewError("static-view deployment policy is invalid")
    case_count = _require_nonnegative_int(manifest["case_count"], field="static-view case_count")
    if case_count < 1 or case_count > MAX_OPEN_DEMOS:
        raise ViewError("static-view case_count is outside the supported range")
    kinds = manifest["evidence_kinds"]
    if not isinstance(kinds, list):
        raise ViewError("static-view evidence_kinds is invalid")
    normalized_kinds = [
        _require_text(kind, field=f"static-view evidence_kinds[{index}]")
        for index, kind in enumerate(kinds)
    ]
    if (
        normalized_kinds != sorted(set(normalized_kinds))
        or not set(normalized_kinds).issubset({"audit", "training"})
    ):
        raise ViewError("static-view evidence_kinds is invalid")
    kinds = normalized_kinds
    evidence = manifest["evidence"]
    if not isinstance(evidence, list) or len(evidence) != len(kinds):
        raise ViewError("static-view evidence inventory is invalid")
    expected_evidence_paths: set[str] = set()
    for index, item_value in enumerate(evidence):
        item = _expect_exact_keys(
            item_value, {"kind", "path", "sha256", "size"}, field=f"static-view evidence {index}"
        )
        kind = _require_text(item["kind"], field="static-view evidence kind")
        if index >= len(kinds) or kind != kinds[index]:
            raise ViewError("static-view evidence inventory is not in deterministic order")
        digest = _require_digest(item["sha256"], field="static-view evidence digest")
        _require_nonnegative_int(item["size"], field="static-view evidence size")
        expected_path = f"data/evidence/{kind}-{digest}.json"
        if item["path"] != expected_path:
            raise ViewError("static-view evidence path is not content-addressed")
        expected_evidence_paths.add(expected_path)
    if bool(kinds) != (privacy == LOCAL_PRIVACY_CLASSIFICATION):
        raise ViewError("static-view privacy classification does not match its evidence")
    records = manifest["files"]
    if not isinstance(records, list) or not records:
        raise ViewError("static-view files inventory must be non-empty")
    paths: list[str] = []
    for index, record_value in enumerate(records):
        record = _validate_file_record(record_value, field=f"static-view files[{index}]")
        paths.append(str(record["path"]))
    if paths != sorted(paths) or len(paths) != len(set(path.casefold() for path in paths)):
        raise ViewError("static-view files inventory is not unique and sorted")
    if set(paths) != BASE_PAYLOAD_PATHS | expected_evidence_paths:
        raise ViewError("static-view files inventory differs from the exact view payload")
    limitations = manifest["limitations"]
    if limitations != VIEW_LIMITATIONS:
        raise ViewError("static-view limitations have changed")
    return manifest


def _verify_frozen_view(snapshot: _FrozenView) -> dict[str, object]:
    root = snapshot.root
    files = snapshot.files
    directories = snapshot.directories
    if directories != EXPECTED_DIRECTORIES:
        raise ViewError("static-view directory inventory differs from the exact layout")
    if "VIEW_MANIFEST.json" not in files or "CHECKSUMS.sha256" not in files:
        raise ViewError("static view is missing its manifest or checksums")
    checksums = _parse_checksums(files["CHECKSUMS.sha256"].data)
    expected_checksum_paths = set(files) - {"CHECKSUMS.sha256"}
    if set(checksums) != expected_checksum_paths:
        raise ViewError("static-view file set differs from checksums")
    for path, digest in checksums.items():
        if files[path].sha256 != digest:
            raise ViewError(f"static-view checksum mismatch: {path}")

    manifest = _strict_json(files["VIEW_MANIFEST.json"].data, field="static-view manifest")
    if files["VIEW_MANIFEST.json"].data != _json_bytes(manifest):
        raise ViewError("static-view manifest JSON is not canonical")
    _validate_manifest(manifest)
    records = {str(record["path"]): record for record in manifest["files"]}
    payload_paths = set(files) - CONTROL_PATHS
    if set(records) != payload_paths:
        raise ViewError("static-view manifest inventory differs from retained payload")
    for path, record in records.items():
        blob = files[path]
        if blob.sha256 != record["sha256"] or blob.size != record["size"]:
            raise ViewError(f"static-view manifest record mismatch: {path}")

    registry = _strict_json(
        files["data/CASE_REGISTRY.json"].data, field="static-view case registry"
    )
    if files["data/CASE_REGISTRY.json"].data != _json_bytes(registry):
        raise ViewError("static-view case registry JSON is not canonical")
    _validate_registry(registry)
    if len(registry["cases"]) != manifest["case_count"]:
        raise ViewError("static-view case_count does not match the registry")

    evidence: dict[str, dict[str, object]] = {}
    for item in manifest["evidence"]:
        kind = str(item["kind"])
        path = str(item["path"])
        blob = files[path]
        if blob.sha256 != item["sha256"] or blob.size != item["size"]:
            raise ViewError(f"static-view evidence record mismatch: {kind}")
        payload = _strict_json(blob.data, field=f"static-view {kind} evidence")
        if blob.data != _json_bytes(payload):
            raise ViewError(f"static-view {kind} evidence JSON is not canonical")
        if kind == "audit":
            _validate_audit_projection(payload)
        elif kind == "training":
            _validate_training_projection(payload)
        else:
            raise ViewError(f"unsupported static-view evidence kind: {kind}")
        evidence[kind] = payload

    privacy = str(manifest["privacy_classification"])
    if files["style.css"].data != STYLE_CSS:
        raise ViewError("static-view stylesheet does not match the trusted offline stylesheet")
    if files["VIEW_BOUNDARY.md"].data != _boundary(privacy):
        raise ViewError("static-view boundary notice does not match its classification")
    expected_html = _render_html(registry, evidence, privacy)
    if files["index.html"].data != expected_html:
        raise ViewError("static-view rendered HTML does not match the escaped projection")
    _assert_frozen_view_identities(snapshot)
    # Keep the pinned tree alive until every semantic check has completed, then
    # ensure its externally visible root was not swapped in the meantime.
    try:
        opened = os.fstat(snapshot.descriptor)
        current = root.lstat()
    except OSError as error:
        raise ViewError("static-view identity is no longer available") from error
    if (
        not stat.S_ISDIR(current.st_mode)
        or root.is_symlink()
        or (opened.st_dev, opened.st_ino) != (snapshot.device, snapshot.inode)
        or (current.st_dev, current.st_ino) != (snapshot.device, snapshot.inode)
    ):
        raise ViewError("static-view identity changed during semantic verification")
    return {
        "integrity_status": "pass",
        "manifest_type": MANIFEST_TYPE,
        "privacy_classification": privacy,
        "case_count": manifest["case_count"],
        "evidence_kinds": list(manifest["evidence_kinds"]),
        "file_count": len(files),
        "scientific_correctness": SCIENTIFIC_CORRECTNESS,
        "network_access": NETWORK_ACCESS,
        "code_execution": CODE_EXECUTION,
    }


def _verify_owned_static_view(
    owned: release_core.OwnedOutput,
) -> dict[str, object]:
    snapshot = _collect_view_tree(
        owned.path,
        borrowed_descriptor=owned.descriptor,
        expected_identity=(owned.device, owned.inode),
    )
    try:
        return _verify_frozen_view(snapshot)
    finally:
        os.close(snapshot.descriptor)


def verify_static_view(view_value: Path | str) -> dict[str, object]:
    """Verify a static view's exact schema, bytes, permissions, and boundaries."""

    snapshot = _collect_view_tree(view_value)
    try:
        return _verify_frozen_view(snapshot)
    finally:
        os.close(snapshot.descriptor)
