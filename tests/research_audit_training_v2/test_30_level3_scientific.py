from __future__ import annotations

import csv
import importlib.util
import json
import math
import statistics
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
V2 = ROOT / "LLM4SBR_research_audit_training_v2"
LEVEL = V2 / "level_3_scientific_validity"
DOSSIERS = LEVEL / "dossiers"
HIDDEN = LEVEL / "DO_NOT_OPEN_UNTIL_FINISHED"
FILES = {
    "experiment_config.json",
    "planned_runs.csv",
    "runs.csv",
    "aggregate.csv",
    "claim.json",
    "claim.md",
}


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("level3_module", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class Level3Tests(unittest.TestCase):
    def test_public_validator_accepts_every_dossier_without_ranking(self) -> None:
        result = subprocess.run(
            [sys.executable, str(LEVEL / "validate_evidence_schema.py")],
            cwd=V2,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.splitlines(), [f"{letter}: PASS" for letter in "ABCDE"])

    def test_all_dossiers_share_files_and_have_recomputable_aggregates(self) -> None:
        for letter in "ABCDE":
            dossier = DOSSIERS / letter
            self.assertEqual({p.name for p in dossier.iterdir() if p.is_file()}, FILES)
            run_rows = rows(dossier / "runs.csv")
            aggregate_rows = rows(dossier / "aggregate.csv")
            for aggregate in aggregate_rows:
                values = [
                    float(row["metric_value"])
                    for row in run_rows
                    if row["method"] == aggregate["method"] and row["included"] == "true"
                ]
                self.assertEqual(int(aggregate["n"]), len(values))
                self.assertTrue(math.isclose(float(aggregate["mean"]), statistics.fmean(values), abs_tol=1e-12))
                self.assertTrue(
                    math.isclose(float(aggregate["sample_std"]), statistics.stdev(values), abs_tol=1e-12)
                )

    def test_claims_reference_existing_included_evidence(self) -> None:
        for letter in "ABCDE":
            dossier = DOSSIERS / letter
            claim = json.loads((dossier / "claim.json").read_text(encoding="utf-8"))
            included = {row["run_id"] for row in rows(dossier / "runs.csv") if row["included"] == "true"}
            self.assertTrue(set(claim["evidence_run_ids"]).issubset(included))
            self.assertIn(claim["claim_id"], (dossier / "claim.md").read_text(encoding="utf-8"))

    def test_hidden_audit_finds_one_trusted_and_four_single_faults(self) -> None:
        probes = load_module(HIDDEN / "scientific_probes.py")
        report = probes.classify_all(DOSSIERS)
        self.assertEqual(set(report), set("ABCDE"))
        self.assertEqual(sorted(len(value) for value in report.values()), [0, 1, 1, 1, 1])
        self.assertEqual(
            {rule for findings in report.values() for rule in findings},
            {
                "L3_BUDGET_FAIRNESS",
                "L3_INFORMATION_CONDITION",
                "L3_SELECTIVE_REPORTING",
                "L3_EXPERIMENTAL_UNIT",
            },
        )

    def test_hidden_audit_is_content_based_and_unexpected_errors_propagate(self) -> None:
        probes = load_module(HIDDEN / "scientific_probes.py")
        original = probes.load_json

        def explode(_path: Path):
            raise RuntimeError("infrastructure failure")

        probes.load_json = explode
        try:
            with self.assertRaisesRegex(RuntimeError, "infrastructure failure"):
                probes.classify_dossier(DOSSIERS / "A")
        finally:
            probes.load_json = original

    def test_answer_mapping_is_isolated(self) -> None:
        public_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in LEVEL.rglob("*")
            if path.is_file() and HIDDEN not in path.parents and path.suffix in {".py", ".md", ".json", ".csv"}
        )
        self.assertNotIn("trusted_candidate", public_text)
        manifest = json.loads((HIDDEN / "answer_manifest.json").read_text(encoding="utf-8"))
        self.assertIn(manifest["trusted_candidate"], "ABCDE")
        self.assertEqual(set(manifest["candidates"]), set("ABCDE"))


if __name__ == "__main__":
    unittest.main()
