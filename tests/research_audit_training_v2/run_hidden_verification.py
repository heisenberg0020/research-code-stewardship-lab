from __future__ import annotations
import importlib.util,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];V2=ROOT/"LLM4SBR_research_audit_training_v2"
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
def valid(report,rules):return sorted(len(v) for v in report.values())==[0,1,1,1,1] and {x for v in report.values() for x in v}==rules
def main():
    hidden="DO_NOT_OPEN_UNTIL_FINISHED"
    p1=load(V2/"level_1_algorithm_semantics"/hidden/"probes.py","p1")
    if not valid(p1.classify_all(),{"L1_BATCH_INVARIANCE","L1_PADDING","L1_AUX_GRAD","L1_LOGIT_CE"}):return 1
    print("LEVEL 1: PASS")
    p2=load(V2/"level_2_pipeline_integrity"/hidden/"pipeline_probes.py","p2")
    with tempfile.TemporaryDirectory() as tmp:report=p2.classify_all(Path(tmp))
    if not valid(report,{"L2_SPLIT_ENTITY_ISOLATION","L2_JOINT_PERMUTATION","L2_METRIC_POPULATION","L2_PROTECTED_SELECTION"}):return 1
    print("LEVEL 2: PASS")
    p3=load(V2/"level_3_scientific_validity"/hidden/"scientific_probes.py","p3")
    if not valid(p3.classify_all(),{"L3_BUDGET_FAIRNESS","L3_INFORMATION_CONDITION","L3_SELECTIVE_REPORTING","L3_EXPERIMENTAL_UNIT"}):return 1
    print("LEVEL 3: PASS")
    p4=load(V2/"level_4_agent_experiment_governance"/hidden/"governance_probes.py","p4")
    if not valid(p4.classify_all(),{"L4_UNAPPROVED_DATA_PROTOCOL","L4_RESOURCE_SCOPE","L4_RECORD_INTEGRITY","L4_PROTECTED_EVIDENCE_ADAPTATION"}):return 1
    print("LEVEL 4: PASS");return 0
if __name__=="__main__":raise SystemExit(main())
