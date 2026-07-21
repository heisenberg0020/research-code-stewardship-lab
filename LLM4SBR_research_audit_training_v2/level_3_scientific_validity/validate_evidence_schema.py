from __future__ import annotations
import csv, json, math, statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REQUIRED = {"experiment_config.json","planned_runs.csv","runs.csv","aggregate.csv","claim.json","claim.md"}

def load_json(path):
    value=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value,dict): raise ValueError(f"{path.name}: expected object")
    return value

def load_csv(path):
    with path.open(encoding="utf-8",newline="") as handle: return list(csv.DictReader(handle))

def validate_dossier(path):
    if {p.name for p in path.iterdir() if p.is_file()} != REQUIRED: raise ValueError(f"{path.name}: file contract")
    config=load_json(path/"experiment_config.json")
    if not {"study_id","dataset_id","metric","methods","analysis","practical_threshold"} <= set(config): raise ValueError(f"{path.name}: config")
    planned,runs,aggregates=load_csv(path/"planned_runs.csv"),load_csv(path/"runs.csv"),load_csv(path/"aggregate.csv")
    if {r["run_id"] for r in planned}!={r["run_id"] for r in runs}: raise ValueError(f"{path.name}: planned runs")
    included={r["run_id"] for r in runs if r["included"]=="true"}
    for aggregate in aggregates:
        values=[float(r["metric_value"]) for r in runs if r["method"]==aggregate["method"] and r["included"]=="true"]
        if int(aggregate["n"])!=len(values) or not math.isclose(float(aggregate["mean"]),statistics.fmean(values),abs_tol=1e-12) or not math.isclose(float(aggregate["sample_std"]),statistics.stdev(values),abs_tol=1e-12): raise ValueError(f"{path.name}: aggregate")
    claim=load_json(path/"claim.json")
    if not set(claim["evidence_run_ids"])<=included or str(claim["claim_id"]) not in (path/"claim.md").read_text(encoding="utf-8"): raise ValueError(f"{path.name}: claim")

if __name__=="__main__":
    for letter in "ABCDE": validate_dossier(ROOT/"dossiers"/letter); print(f"{letter}: PASS")
