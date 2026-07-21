from __future__ import annotations
import subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
LEVELS=("level_1_algorithm_semantics","level_2_pipeline_integrity","level_3_scientific_validity","level_4_agent_experiment_governance")
def main():
    for name in ("README.md","FRAMEWORK_OVERVIEW.md","PROGRESSION.md","run_all_public_checks.py"):
        if not (ROOT/name).is_file():raise SystemExit(f"missing {name}")
    for level in LEVELS:
        if not (ROOT/level/"README.md").is_file() or not (ROOT/level/"ANSWER_SHEET.md").is_file():raise SystemExit(f"incomplete {level}")
    result=subprocess.run([sys.executable,str(ROOT/"run_all_public_checks.py")],cwd=ROOT,text=True,check=False)
    return result.returncode
if __name__=="__main__":raise SystemExit(main())
