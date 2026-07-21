from __future__ import annotations
import csv, importlib.util, json, subprocess, sys, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2];V2=ROOT/"LLM4SBR_research_audit_training_v2";LEVEL=V2/"level_4_agent_experiment_governance";RUNS=LEVEL/"runs";HIDDEN=LEVEL/"DO_NOT_OPEN_UNTIL_FINISHED"
FILES={"protocol.json","agent_events.jsonl","approvals.jsonl","run_ledger.csv","report_manifest.json"}
def module(path):
    spec=importlib.util.spec_from_file_location("l4",path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def csvrows(path):
    with path.open(encoding="utf-8",newline="") as h:return list(csv.DictReader(h))
def jsonlines(path):return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

class Level4Tests(unittest.TestCase):
    def test_public_validator_accepts_all_runs(self):
        result=subprocess.run([sys.executable,str(LEVEL/"validate_ledger_schema.py")],cwd=V2,text=True,capture_output=True,check=False)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr);self.assertEqual(result.stdout.splitlines(),[f"{x}: PASS" for x in "ABCDE"])
    def test_all_runs_share_schema_and_nullable_fields_are_preserved(self):
        for letter in "ABCDE":
            root=RUNS/letter;self.assertEqual({p.name for p in root.iterdir() if p.is_file()},FILES)
            events=jsonlines(root/"agent_events.jsonl");ledger=csvrows(root/"run_ledger.csv")
            self.assertTrue(all({"event_id","timestamp","actor","action_type","scope","run_id","approval_id","evidence_refs","decision_basis","details"}<=set(e) for e in events))
            self.assertTrue(any(e["run_id"] is None for e in events));self.assertTrue(all("terminal_event_id" in r and "claim_id" in r for r in ledger))
    def test_hidden_audit_finds_one_trusted_and_four_single_faults(self):
        probes=module(HIDDEN/"governance_probes.py");report=probes.classify_all(RUNS)
        self.assertEqual(sorted(len(v) for v in report.values()),[0,1,1,1,1]);self.assertEqual({x for v in report.values() for x in v},{"L4_UNAPPROVED_DATA_PROTOCOL","L4_RESOURCE_SCOPE","L4_RECORD_INTEGRITY","L4_PROTECTED_EVIDENCE_ADAPTATION"})
    def test_manifest_rebuild_is_independent_of_report(self):
        probes=module(HIDDEN/"governance_probes.py");mismatches=0
        for letter in "ABCDE":
            root=RUNS/letter;expected=probes.rebuild_manifest(csvrows(root/"run_ledger.csv"));actual=json.loads((root/"report_manifest.json").read_text())
            mismatches+=expected!=actual
        self.assertEqual(mismatches,1)
    def test_posthoc_reporting_is_not_adaptation(self):
        probes=module(HIDDEN/"governance_probes.py")
        events=[{"event_id":"p","timestamp":"2026-01-01T00:00:00Z","actor":"agent","action_type":"evaluate_protected_final","scope":"test","run_id":"r","approval_id":None,"evidence_refs":[],"decision_basis":"FINAL","details":{}},{"event_id":"q","timestamp":"2026-01-01T00:01:00Z","actor":"agent","action_type":"report_result","scope":"report","run_id":None,"approval_id":None,"evidence_refs":["p"],"decision_basis":"POST_HOC","details":{}}]
        self.assertFalse(probes.protected_adaptation(events,{"adaptive_action_types":["change_hyperparameter"]}))
    def test_unexpected_loader_errors_propagate(self):
        probes=module(HIDDEN/"governance_probes.py");original=probes.load_json
        probes.load_json=lambda _p:(_ for _ in ()).throw(RuntimeError("infrastructure failure"))
        try:
            with self.assertRaisesRegex(RuntimeError,"infrastructure failure"):probes.classify_run(RUNS/"A")
        finally:probes.load_json=original
    def test_answer_mapping_is_isolated(self):
        public="\n".join(p.read_text(encoding="utf-8") for p in LEVEL.rglob("*") if p.is_file() and HIDDEN not in p.parents and p.suffix in {".py",".md",".json",".jsonl",".csv"})
        self.assertNotIn("trusted_candidate",public);manifest=json.loads((HIDDEN/"answer_manifest.json").read_text());self.assertEqual(set(manifest["candidates"]),set("ABCDE"))
if __name__=="__main__":unittest.main()
