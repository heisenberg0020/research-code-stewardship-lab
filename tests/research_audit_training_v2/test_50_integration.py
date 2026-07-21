from __future__ import annotations
import json, subprocess, sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];V2=ROOT/"LLM4SBR_research_audit_training_v2";TESTS=ROOT/"tests/research_audit_training_v2"
LEVELS=("level_1_algorithm_semantics","level_2_pipeline_integrity","level_3_scientific_validity","level_4_agent_experiment_governance")
class IntegrationTests(unittest.TestCase):
    def run_script(self,path):return subprocess.run([sys.executable,str(path)],cwd=V2,text=True,capture_output=True,check=False)
    def test_root_public_runner_is_deterministic_and_neutral(self):
        first=self.run_script(V2/"run_all_public_checks.py");second=self.run_script(V2/"run_all_public_checks.py")
        self.assertEqual(first.returncode,0,first.stdout+first.stderr);self.assertEqual(first.stdout,second.stdout)
        self.assertEqual(first.stdout.splitlines(),[f"LEVEL {i}: PASS" for i in range(1,5)])
    def test_public_package_verifier_does_not_reference_hidden_answers(self):
        path=V2/"verify_package.py";text=path.read_text(encoding="utf-8")
        self.assertNotIn("DO_NOT_OPEN_UNTIL_FINISHED",text);result=self.run_script(path);self.assertEqual(result.returncode,0,result.stdout+result.stderr)
    def test_external_hidden_verifier_passes_without_printing_mappings(self):
        result=subprocess.run([sys.executable,str(TESTS/"run_hidden_verification.py")],cwd=ROOT,text=True,capture_output=True,check=False)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr);self.assertEqual(result.stdout.splitlines(),[f"LEVEL {i}: PASS" for i in range(1,5)])
    def test_four_trusted_letters_are_distinct_and_isolated(self):
        letters=[]
        for level in LEVELS:
            manifest=json.loads((V2/level/"DO_NOT_OPEN_UNTIL_FINISHED/answer_manifest.json").read_text())
            letters.append(manifest["trusted_candidate"])
        self.assertEqual(len(set(letters)),4)
        public="\n".join(p.read_text(encoding="utf-8") for p in V2.rglob("*") if p.is_file() and "DO_NOT_OPEN_UNTIL_FINISHED" not in p.parts and p.suffix in {".py",".md",".json",".csv",".jsonl"})
        self.assertNotIn("trusted_candidate",public)
    def test_training_package_has_no_network_imports(self):
        forbidden=("import requests","from requests","import urllib","from urllib","import socket","from socket")
        for path in V2.rglob("*.py"):
            self.assertFalse(any(token in path.read_text(encoding="utf-8") for token in forbidden),str(path))
    def test_generated_csv_files_use_repository_lf_endings(self):
        for path in (V2/"level_3_scientific_validity").rglob("*.csv"):
            self.assertNotIn(b"\r\n",path.read_bytes(),str(path))
        for path in (V2/"level_4_agent_experiment_governance").rglob("*.csv"):
            self.assertNotIn(b"\r\n",path.read_bytes(),str(path))
if __name__=="__main__":unittest.main()
