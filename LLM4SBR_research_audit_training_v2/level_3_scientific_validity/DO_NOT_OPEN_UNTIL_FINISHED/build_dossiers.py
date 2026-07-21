from __future__ import annotations
import csv,json,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE={"P01":.400,"P02":.420,"P03":.410,"P04":.430}; PROP={"P01":.440,"P02":.455,"P03":.445,"P04":.460}
def wjson(path,value):path.write_text(json.dumps(value,indent=2,sort_keys=True)+"\n",encoding="utf-8")
def wcsv(path,rows):
    with path.open("w",encoding="utf-8",newline="") as h:w=csv.DictWriter(h,fieldnames=list(rows[0]),lineterminator="\n");w.writeheader();w.writerows(rows)
def config(letter):
    trials=["T01","T02","T03","T04"]
    methods={m:{"candidate_set":"catalog-8-v1","features":["session_history_v1","item_id_v1"],"approved_trial_ids":trials,"max_trials":4,"budget":{"unit":"validation_trials","value":4}} for m in ("baseline","proposed")}
    if letter=="A":methods["baseline"].update(approved_trial_ids=trials[:2],max_trials=2,budget={"unit":"validation_trials","value":2})
    if letter=="C":methods["proposed"]["features"].append("catalog_text_embedding_v1")
    analysis={"experimental_unit":"paired_block","pairing_key":"pair_id","final_observations_per_pair_method":1}
    if letter=="E":analysis.update(experimental_unit="checkpoint_snapshot",final_observations_per_pair_method=3)
    return {"study_id":"l3-fixed-study-v1","dataset_id":"synthetic-sbr-final-v1","metric":"NDCG@10","candidate_population":"catalog-8-v1","practical_threshold":.020,"predeclared_exclusion_codes":["INFRASTRUCTURE_FAILURE_BEFORE_METRIC"],"methods":methods,"analysis":analysis}
def build(letter):
    target=ROOT/"dossiers"/letter;target.mkdir(parents=True,exist_ok=True);cfg=config(letter);wjson(target/"experiment_config.json",cfg)
    runs=[];offsets=(-.002,0,.002) if letter=="E" else (0,)
    for pair in BASE:
      for method,center in (("baseline",BASE[pair]),("proposed",PROP[pair])):
       for i,offset in enumerate(offsets,1):
        include=not(letter=="D" and method=="proposed" and pair in {"P01","P03"})
        runs.append({"run_id":f"{pair}-{method}-C{i}","pair_id":pair,"method":method,"observation_role":"final","checkpoint_id":f"checkpoint-{i}","metric_value":f"{center+offset:.12f}","included":str(include).lower(),"exclusion_code":"" if include else "POSTHOC_LOW_SCORE"})
    planned=[{k:r[k] for k in ("run_id","pair_id","method","observation_role")} for r in runs];wcsv(target/"planned_runs.csv",planned);wcsv(target/"runs.csv",runs)
    ag=[]
    for method in ("baseline","proposed"):
      values=[float(r["metric_value"]) for r in runs if r["method"]==method and r["included"]=="true"]
      ag.append({"method":method,"n":len(values),"mean":f"{statistics.fmean(values):.12f}","sample_std":f"{statistics.stdev(values):.12f}","unit":cfg["analysis"]["experimental_unit"]})
    wcsv(target/"aggregate.csv",ag);included=[r["run_id"] for r in runs if r["included"]=="true"]
    deltas=[]
    for pair in BASE:
      p=[float(r["metric_value"]) for r in runs if r["pair_id"]==pair and r["method"]=="proposed" and r["included"]=="true"];b=[float(r["metric_value"]) for r in runs if r["pair_id"]==pair and r["method"]=="baseline" and r["included"]=="true"]
      if p and b:deltas.append(statistics.fmean(p)-statistics.fmean(b))
    cid=f"claim-l3-{letter.lower()}";wjson(target/"claim.json",{"claim_id":cid,"scope":"synthetic-sbr-final-v1/catalog-8-v1/frozen-protocol-only","metric":"NDCG@10","threshold":.020,"mean_paired_delta":round(statistics.fmean(deltas),12),"evidence_run_ids":included});(target/"claim.md").write_text(f"# Scientific claim\n\nClaim-ID: `{cid}`\n\nUnder the declared frozen study and candidate population, the paired mean difference exceeds the practical threshold.\n",encoding="utf-8")
if __name__=="__main__":
    for letter in "ABCDE":build(letter)
