from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import importlib
import importlib.util
import json
import math
import re
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

from tests.research_audit_training_v2.helpers import V2, run_python


LEVEL = V2 / "level_2_pipeline_integrity"
CANDIDATES = LEVEL / "candidates"
ISOLATED = LEVEL / "DO_NOT_OPEN_UNTIL_FINISHED"
ARTIFACTS = (
    "split_manifest.json",
    "batch_manifest.json",
    "epoch_metrics.json",
    "evaluation_records.json",
    "selected_checkpoint.json",
    "event_log.jsonl",
    "summary.json",
)
RULES = {
    "L2_SPLIT_ENTITY_ISOLATION",
    "L2_JOINT_PERMUTATION",
    "L2_METRIC_POPULATION",
    "L2_PROTECTED_SELECTION",
}


def load_package_module(package_dir: Path, submodule: str):
    package_name = f"level2_test_{package_dir.name}_{uuid.uuid4().hex}"
    init_path = package_dir / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        package_name,
        init_path,
        submodule_search_locations=[str(package_dir)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load package {package_dir}")
    package = importlib.util.module_from_spec(spec)
    sys.modules[package_name] = package
    try:
        spec.loader.exec_module(package)
        return importlib.import_module(f"{package_name}.{submodule}")
    except BaseException:
        for name in tuple(sys.modules):
            if name == package_name or name.startswith(f"{package_name}."):
                sys.modules.pop(name, None)
        raise


def load_standalone(path: Path):
    module_name = f"level2_hidden_{path.stem}_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(module_name, None)
        raise
    return module


def item_vector(item: int) -> list[float]:
    return [item / 17.0, (item % 3) / 2.0, (item % 5) / 4.0, (item % 7) / 6.0]


def mean_vector(vectors: list[list[float]]) -> list[float]:
    return [sum(vector[index] for vector in vectors) / len(vectors) for index in range(4)]


def derive_features(prefix: list[int]) -> tuple[list[float], list[float]]:
    vectors = [item_vector(item) for item in prefix]
    return mean_vector(vectors), mean_vector(vectors[-2:])


def vector_hash(vector: list[float]) -> str:
    payload = json.dumps(vector, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def event_rows(output_dir: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in (output_dir / "event_log.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]


def aggregate(records: list[dict[str, object]]) -> dict[str, float]:
    size = len(records)
    return {
        name: sum(float(record[name]) for record in records) / size
        for name in ("hr", "mrr", "ndcg")
    }


def independent_failures(output_dir: Path) -> tuple[str, ...]:
    failures: list[str] = []
    split = read_json(output_dir / "split_manifest.json")
    examples = split["examples"]

    session_splits: dict[str, set[str]] = defaultdict(set)
    for example in examples:
        session_splits[example["session_id"]].add(example["split"])
    if any(len(splits) != 1 for splits in session_splits.values()):
        failures.append("L2_SPLIT_ENTITY_ISOLATION")

    canonical = Counter(
        (
            example["sample_id"],
            example["target"],
            example["long_hash"],
            example["short_hash"],
        )
        for example in examples
        if example["split"] == "train"
    )
    batches = read_json(output_dir / "batch_manifest.json")["epochs"]
    joint_ok = len(batches) == 3
    for epoch in batches:
        actual = Counter(
            (row["sample_id"], row["target"], row["long_hash"], row["short_hash"])
            for batch in epoch["batches"]
            for row in batch["rows"]
        )
        joint_ok = joint_ok and actual == canonical
    if not joint_ok:
        failures.append("L2_JOINT_PERMUTATION")

    by_role = {
        role: {example["sample_id"] for example in examples if example["split"] == role}
        for role in ("validation", "test")
    }
    evaluations = read_json(output_dir / "evaluation_records.json")["evaluations"]
    metric_ok = True
    for evaluation in evaluations:
        records = evaluation["records"]
        expected_ids = by_role[evaluation["role"]]
        metric_ok = metric_ok and evaluation["population_size"] == len(expected_ids)
        metric_ok = metric_ok and Counter(row["sample_id"] for row in records) == Counter(expected_ids)
        for row in records:
            ranked = row["ranked_items"]
            expected_rank = ranked.index(row["target"]) + 1 if row["target"] in ranked else None
            expected_hr = 1.0 if expected_rank is not None else 0.0
            expected_mrr = 1.0 / expected_rank if expected_rank is not None else 0.0
            expected_ndcg = 1.0 / math.log2(expected_rank + 1) if expected_rank is not None else 0.0
            metric_ok = metric_ok and row["rank"] == expected_rank
            metric_ok = metric_ok and math.isclose(row["hr"], expected_hr, abs_tol=1e-12)
            metric_ok = metric_ok and math.isclose(row["mrr"], expected_mrr, abs_tol=1e-12)
            metric_ok = metric_ok and math.isclose(row["ndcg"], expected_ndcg, abs_tol=1e-12)
        if records:
            recomputed = aggregate(records)
            metric_ok = metric_ok and all(
                math.isclose(evaluation["aggregate"][name], recomputed[name], abs_tol=1e-12)
                for name in recomputed
            )
    summary = read_json(output_dir / "summary.json")
    final = next((entry for entry in evaluations if entry["evaluation_id"] == summary["final_evaluation_id"]), None)
    metric_ok = metric_ok and final is not None
    if final is not None:
        metric_ok = metric_ok and all(
            math.isclose(summary["metrics"][name], final["aggregate"][name], abs_tol=1e-12)
            for name in ("hr", "mrr", "ndcg")
        )
    if not metric_ok:
        failures.append("L2_METRIC_POPULATION")

    selected = read_json(output_dir / "selected_checkpoint.json")
    events = event_rows(output_dir)
    selection_events = [row for row in events if row["event"] == "checkpoint_selected"]
    protected_events = [
        row
        for row in events
        if row["event"] == "evaluation_completed" and row["role"] == "test"
    ]
    selection_ok = (
        selected["evidence_role"] == "validation"
        and len(selection_events) == 1
        and selection_events[0]["evidence_role"] == "validation"
        and len(protected_events) == 1
        and protected_events[0]["sequence"] > selection_events[0]["sequence"]
    )
    if not selection_ok:
        failures.append("L2_PROTECTED_SELECTION")
    return tuple(failures)


class Level2Tests(unittest.TestCase):
    def test_public_smoke_accepts_all_candidates_without_ranking_output(self) -> None:
        result = run_python("level_2_pipeline_integrity/run_smoke.py", cwd=V2)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.splitlines(), [f"{letter}: PASS" for letter in "ABCDE"])
        self.assertNotRegex(result.stdout, r"metric|loss|score|best|rank|correct|fault|trusted")

    def test_public_artifacts_share_schema_and_use_prefix_only_features(self) -> None:
        schemas = []
        result_keys = []
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for letter in "ABCDE":
                pipeline = load_package_module(CANDIDATES / letter, "pipeline")
                output_dir = root / letter
                result = pipeline.run_pipeline(output_dir)
                result_keys.append(set(result))
                self.assertTrue(all((output_dir / name).is_file() for name in ARTIFACTS), letter)

                artifacts = {
                    name: event_rows(output_dir) if name.endswith(".jsonl") else read_json(output_dir / name)
                    for name in ARTIFACTS
                }
                schemas.append(
                    {
                        name: tuple(sorted(value)) if isinstance(value, dict) else tuple(sorted(value[0]))
                        for name, value in artifacts.items()
                    }
                )
                split = artifacts["split_manifest.json"]
                self.assertEqual(split["candidate_item_ids"], list(range(1, 18)))
                for example in split["examples"]:
                    long_feature, short_feature = derive_features(example["prefix"])
                    self.assertEqual(example["long_embedding"], long_feature, letter)
                    self.assertEqual(example["short_embedding"], short_feature, letter)
                    self.assertEqual(example["long_hash"], vector_hash(long_feature), letter)
                    self.assertEqual(example["short_hash"], vector_hash(short_feature), letter)

                epochs = artifacts["epoch_metrics.json"]["epochs"]
                self.assertEqual([row["epoch"] for row in epochs], [1, 2, 3])
                self.assertEqual(len({row["checkpoint_id"] for row in epochs}), 3)
                for row in epochs:
                    self.assertTrue((output_dir / row["checkpoint_path"]).is_file(), letter)
                    self.assertTrue(math.isfinite(row["train_loss"]), letter)
                summary = artifacts["summary.json"]
                for value in summary["metrics"].values():
                    self.assertTrue(math.isfinite(value) and 0.0 <= value <= 1.0, letter)

        self.assertTrue(all(keys == result_keys[0] for keys in result_keys))
        self.assertTrue(all(schema == schemas[0] for schema in schemas))

    def test_hidden_probes_match_independent_artifact_recomputation(self) -> None:
        probes = load_standalone(ISOLATED / "pipeline_probes.py")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report = probes.classify_all(root)
            self.assertEqual(set(report), set("ABCDE"))
            self.assertEqual(sorted(len(failures) for failures in report.values()), [0, 1, 1, 1, 1])
            self.assertEqual({rule for failures in report.values() for rule in failures}, RULES)
            for letter, failures in report.items():
                self.assertEqual(failures, independent_failures(root / letter), letter)

    def test_hidden_manifest_records_cross_artifact_single_fault_evidence(self) -> None:
        manifest = read_json(ISOLATED / "answer_manifest.json")
        entries = manifest["candidates"]
        trusted = manifest["trusted_candidate"]
        self.assertEqual(set(entries), set("ABCDE"))
        self.assertEqual(entries[trusted]["status"], "trusted")
        faulty = {letter: entry for letter, entry in entries.items() if entry["status"] == "faulty"}
        self.assertEqual(len(faulty), 4)
        self.assertEqual({entry["failed_rule"] for entry in faulty.values()}, RULES)
        for letter, entry in faulty.items():
            source = CANDIDATES / letter / entry["source_file"]
            text = source.read_text(encoding="utf-8")
            self.assertEqual(text.count(entry["mutation_span"]), 1, letter)
            self.assertGreaterEqual(len(set(entry["evidence_artifacts"])), 2, letter)
            self.assertTrue(entry["repair_expression"], letter)

    def test_public_materials_do_not_encode_answer_mapping(self) -> None:
        mapping_pattern = re.compile(
            r"(?i:trusted|correct|fault(?:y)?|split|shuffle|metric|protected)"
            r"[^\n]{0,40}\b[A-E]\b|\b[A-E]\b[^\n]{0,40}"
            r"(?i:trusted|correct|fault(?:y)?|split|shuffle|metric|protected)"
        )
        for path in (LEVEL / "README.md", LEVEL / "FROZEN_PIPELINE_SPEC.md", LEVEL / "ANSWER_SHEET.md"):
            self.assertIsNone(mapping_pattern.search(path.read_text(encoding="utf-8")), str(path))


if __name__ == "__main__":
    unittest.main()
