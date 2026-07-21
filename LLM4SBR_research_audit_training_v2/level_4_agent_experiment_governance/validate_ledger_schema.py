from __future__ import annotations
import csv,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
FILES={"protocol.json","agent_events.jsonl","approvals.jsonl","run_ledger.csv","report_manifest.json"}
EVENT_KEYS={"event_id","timestamp","actor","action_type","scope","run_id","approval_id","evidence_refs","decision_basis","details"}
APPROVAL_KEYS={"approval_id","request_event_id","decision_event_id","status","scope","limits","decided_at"}
LEDGER_KEYS={"run_id","parent_run_id","status","started_at","ended_at","actual_gpu_hours","config_hash","dataset_hash","evaluation_role","reported","terminal_event_id","claim_id"}
def obj(path):
    value=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value,dict):raise ValueError(path)
    return value
def lines(path):return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
def rows(path):
    with path.open(encoding="utf-8",newline="") as h:return list(csv.DictReader(h))
def validate(path):
    if {p.name for p in path.iterdir() if p.is_file()}!=FILES:raise ValueError(f"{path.name}: files")
    protocol=obj(path/"protocol.json");events=lines(path/"agent_events.jsonl");approvals=lines(path/"approvals.jsonl");ledger=rows(path/"run_ledger.csv");manifest=obj(path/"report_manifest.json")
    if not {"clauses","resources","frozen","adaptive_action_types","posthoc_action_types"}<=set(protocol):raise ValueError(f"{path.name}: protocol")
    if not events or any(not EVENT_KEYS<=set(e) for e in events) or [e["timestamp"] for e in events]!=sorted(e["timestamp"] for e in events):raise ValueError(f"{path.name}: events")
    if any(not APPROVAL_KEYS<=set(a) for a in approvals):raise ValueError(f"{path.name}: approvals")
    if not ledger or any(not LEDGER_KEYS<=set(r) for r in ledger):raise ValueError(f"{path.name}: ledger")
    if not {"included_run_ids","failed_run_ids","claim_ids","evidence_refs","success_count","failure_count"}<=set(manifest):raise ValueError(f"{path.name}: manifest")
if __name__=="__main__":
    for letter in "ABCDE":validate(ROOT/"runs"/letter);print(f"{letter}: PASS")
