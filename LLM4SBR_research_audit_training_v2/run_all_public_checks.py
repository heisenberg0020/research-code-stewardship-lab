from __future__ import annotations
import subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
CHECKS=(ROOT/"level_1_algorithm_semantics/run_smoke.py",ROOT/"level_2_pipeline_integrity/run_smoke.py",ROOT/"level_3_scientific_validity/validate_evidence_schema.py",ROOT/"level_4_agent_experiment_governance/validate_ledger_schema.py")
def main():
    for index,path in enumerate(CHECKS,1):
        result=subprocess.run([sys.executable,str(path)],cwd=ROOT,text=True,capture_output=True,check=False)
        if result.returncode:
            sys.stderr.write(result.stdout+result.stderr);return result.returncode
        print(f"LEVEL {index}: PASS")
    return 0
if __name__=="__main__":raise SystemExit(main())
