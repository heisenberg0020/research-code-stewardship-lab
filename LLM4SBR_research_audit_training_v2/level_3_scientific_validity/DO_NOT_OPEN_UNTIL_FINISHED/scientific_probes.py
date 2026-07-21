from __future__ import annotations
import csv,json
from pathlib import Path

def load_json(path):
    value=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value,dict): raise ValueError(path)
    return value
def load_csv(path):
    with path.open(encoding="utf-8",newline="") as handle:return list(csv.DictReader(handle))
def classify_dossier(path):
    config,runs=load_json(path/"experiment_config.json"),load_csv(path/"runs.csv"); findings=[]
    baseline,proposed=config["methods"]["baseline"],config["methods"]["proposed"]
    signature=lambda m:(tuple(m["approved_trial_ids"]),int(m["max_trials"]),m["budget"]["unit"],float(m["budget"]["value"]))
    if signature(baseline)!=signature(proposed):findings.append("L3_BUDGET_FAIRNESS")
    if baseline["candidate_set"]!=proposed["candidate_set"] or set(baseline["features"])!=set(proposed["features"]):findings.append("L3_INFORMATION_CONDITION")
    allowed=set(config["predeclared_exclusion_codes"])
    if any(r["included"]=="false" and r["exclusion_code"] not in allowed for r in runs):findings.append("L3_SELECTIVE_REPORTING")
    counts={}
    for r in runs:counts[(r["pair_id"],r["method"])]=counts.get((r["pair_id"],r["method"]),0)+1
    analysis=config["analysis"]
    if analysis["experimental_unit"]!="paired_block" or int(analysis["final_observations_per_pair_method"])!=1 or any(v!=1 for v in counts.values()):findings.append("L3_EXPERIMENTAL_UNIT")
    return tuple(findings)
def classify_all(dossiers=None):
    root=dossiers or Path(__file__).resolve().parents[1]/"dossiers"
    return {p.name:classify_dossier(p) for p in sorted(root.iterdir()) if p.is_dir()}
