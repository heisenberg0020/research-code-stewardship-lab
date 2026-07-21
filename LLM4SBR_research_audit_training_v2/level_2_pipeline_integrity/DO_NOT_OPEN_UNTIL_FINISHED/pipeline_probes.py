from __future__ import annotations

from collections import Counter, defaultdict
import importlib
import importlib.util
import json
import math
from pathlib import Path
import sys


LEVEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LEVEL.parents[1]))
RULES = (
    "L2_SPLIT_ENTITY_ISOLATION",
    "L2_JOINT_PERMUTATION",
    "L2_METRIC_POPULATION",
    "L2_PROTECTED_SELECTION",
)


def _load_pipeline(letter: str):
    package_dir = LEVEL / "candidates" / letter
    package_name = f"level2_probe_{letter}_{id(package_dir)}"
    spec = importlib.util.spec_from_file_location(
        package_name,
        package_dir / "__init__.py",
        submodule_search_locations=[str(package_dir)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {package_dir}")
    package = importlib.util.module_from_spec(spec)
    sys.modules[package_name] = package
    try:
        spec.loader.exec_module(package)
        return importlib.import_module(f"{package_name}.pipeline")
    except BaseException:
        for name in tuple(sys.modules):
            if name == package_name or name.startswith(f"{package_name}."):
                sys.modules.pop(name, None)
        raise


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _events(output_dir: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in (output_dir / "event_log.jsonl").read_text(encoding="utf-8").splitlines() if line]


def _split_isolated(split: dict[str, object]) -> bool:
    session_splits: dict[str, set[str]] = defaultdict(set)
    for example in split["examples"]:
        session_splits[example["session_id"]].add(example["split"])
    return all(len(splits) == 1 for splits in session_splits.values())


def _joint_permutation(split: dict[str, object], batches: dict[str, object]) -> bool:
    expected = Counter(
        (row["sample_id"], row["target"], row["long_hash"], row["short_hash"])
        for row in split["examples"] if row["split"] == "train"
    )
    epochs = batches["epochs"]
    return len(epochs) == 3 and all(
        Counter(
            (row["sample_id"], row["target"], row["long_hash"], row["short_hash"])
            for batch in epoch["batches"] for row in batch["rows"]
        ) == expected
        for epoch in epochs
    )


def _metric_population(split: dict[str, object], artifact: dict[str, object], summary: dict[str, object]) -> bool:
    role_ids = {
        role: {row["sample_id"] for row in split["examples"] if row["split"] == role}
        for role in ("validation", "test")
    }
    evaluations = artifact["evaluations"]
    valid = True
    for evaluation in evaluations:
        records = evaluation["records"]
        expected_ids = role_ids[evaluation["role"]]
        valid = valid and evaluation["population_size"] == len(expected_ids)
        valid = valid and Counter(row["sample_id"] for row in records) == Counter(expected_ids)
        for row in records:
            ranked = row["ranked_items"]
            rank = ranked.index(row["target"]) + 1 if row["target"] in ranked else None
            expected = {
                "rank": rank,
                "hr": 1.0 if rank is not None else 0.0,
                "mrr": 1.0 / rank if rank is not None else 0.0,
                "ndcg": 1.0 / math.log2(rank + 1) if rank is not None else 0.0,
            }
            valid = valid and row["rank"] == expected["rank"]
            valid = valid and all(math.isclose(float(row[name]), expected[name], abs_tol=1e-12) for name in ("hr", "mrr", "ndcg"))
        if records:
            for name in ("hr", "mrr", "ndcg"):
                recomputed = sum(float(row[name]) for row in records) / len(records)
                valid = valid and math.isclose(evaluation["aggregate"][name], recomputed, abs_tol=1e-12)
    final = next((row for row in evaluations if row["evaluation_id"] == summary["final_evaluation_id"]), None)
    return valid and final is not None and all(
        math.isclose(summary["metrics"][name], final["aggregate"][name], abs_tol=1e-12)
        for name in ("hr", "mrr", "ndcg")
    )


def _protected_selection(selected: dict[str, object], events: list[dict[str, object]]) -> bool:
    selection_events = [event for event in events if event["event"] == "checkpoint_selected"]
    protected = [event for event in events if event["event"] == "evaluation_completed" and event["role"] == "test"]
    return (
        selected["evidence_role"] == "validation"
        and len(selection_events) == 1
        and selection_events[0]["evidence_role"] == "validation"
        and len(protected) == 1
        and protected[0]["sequence"] > selection_events[0]["sequence"]
    )


def classify_artifacts(output_dir: Path) -> tuple[str, ...]:
    split = _read(output_dir / "split_manifest.json")
    batches = _read(output_dir / "batch_manifest.json")
    evaluations = _read(output_dir / "evaluation_records.json")
    selected = _read(output_dir / "selected_checkpoint.json")
    summary = _read(output_dir / "summary.json")
    checks = (
        (RULES[0], _split_isolated(split)),
        (RULES[1], _joint_permutation(split, batches)),
        (RULES[2], _metric_population(split, evaluations, summary)),
        (RULES[3], _protected_selection(selected, _events(output_dir))),
    )
    return tuple(rule for rule, passed in checks if not passed)


def classify_all(temp_root: Path) -> dict[str, tuple[str, ...]]:
    temp_root = Path(temp_root)
    report = {}
    for letter in "ABCDE":
        output_dir = temp_root / letter
        _load_pipeline(letter).run_pipeline(output_dir)
        report[letter] = classify_artifacts(output_dir)
    return report
