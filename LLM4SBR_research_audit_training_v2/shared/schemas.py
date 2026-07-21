"""Small standard-library parsers with actionable, source-named validation errors."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any


def _source_name(source: str | Path) -> str:
    return Path(source).name if isinstance(source, Path) else str(source)


def require_keys(
    record: Mapping[str, Any], required_keys: Iterable[str], source: str | Path
) -> None:
    """Ensure a mapping has each required field and name its source on failure."""

    missing = [
        key
        for key in required_keys
        if key not in record
        or record[key] is None
        or (isinstance(record[key], str) and not record[key].strip())
    ]
    if missing:
        raise ValueError(f"{_source_name(source)}: missing required keys: {', '.join(missing)}")


def load_json(path: str | Path) -> Any:
    """Load a JSON document and convert parser failures to source-named ValueErrors."""

    source = Path(path)
    try:
        with source.open(encoding="utf-8") as handle:
            return json.load(handle)
    except OSError as exc:
        raise ValueError(f"{source.name}: cannot read JSON ({exc})") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"{source.name}: invalid JSON at line {exc.lineno}: {exc.msg}") from exc


def load_jsonl(path: str | Path, required_keys: Iterable[str] = ()) -> list[dict[str, Any]]:
    """Load object-per-line JSON, reporting the file and exact invalid line."""

    source = Path(path)
    required = tuple(required_keys)
    records: list[dict[str, Any]] = []
    try:
        with source.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                try:
                    value = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"{source.name}: invalid JSONL at line {line_number}: {exc.msg}"
                    ) from exc
                if not isinstance(value, dict):
                    raise ValueError(f"{source.name}: line {line_number} must contain a JSON object")
                require_keys(value, required, f"{source.name} line {line_number}")
                records.append(value)
    except OSError as exc:
        raise ValueError(f"{source.name}: cannot read JSONL ({exc})") from exc
    return records


def load_csv(path: str | Path, required_keys: Iterable[str] = ()) -> list[dict[str, str]]:
    """Load a CSV table and validate required headers and row values."""

    source = Path(path)
    required = tuple(required_keys)
    try:
        with source.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            headers = reader.fieldnames
            if headers is None:
                raise ValueError(f"{source.name}: CSV is missing a header row")
            missing_headers = [key for key in required if key not in headers]
            if missing_headers:
                raise ValueError(
                    f"{source.name}: missing required keys: {', '.join(missing_headers)}"
                )
            rows: list[dict[str, str]] = []
            for line_number, row in enumerate(reader, start=2):
                require_keys(row, required, f"{source.name} line {line_number}")
                rows.append(dict(row))
            return rows
    except OSError as exc:
        raise ValueError(f"{source.name}: cannot read CSV ({exc})") from exc
