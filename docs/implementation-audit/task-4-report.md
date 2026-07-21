# Task 4 Level 2 Implementation Report

## Status

DONE

## TDD evidence

### RED

The behavior tests were written before Level 2 production files and run with:

```text
conda run -n ml python -m unittest tests.research_audit_training_v2.test_20_level2_pipeline -v
```

Exact RED summary:

```text
test_hidden_manifest_records_cross_artifact_single_fault_evidence ... ERROR
test_hidden_probes_match_independent_artifact_recomputation ... ERROR
test_public_artifacts_share_schema_and_use_prefix_only_features ... ERROR
test_public_materials_do_not_encode_answer_mapping ... ERROR
test_public_smoke_accepts_all_candidates_without_ranking_output ... FAIL
Ran 5 tests in 2.038s
FAILED (failures=1, errors=4)
```

The failures were the intended missing-feature failures: candidate packages,
public runner, frozen specification, hidden probes, and answer manifest did not
exist.

### Focused GREEN

The same command after implementation produced:

```text
test_hidden_manifest_records_cross_artifact_single_fault_evidence ... ok
test_hidden_probes_match_independent_artifact_recomputation ... ok
test_public_artifacts_share_schema_and_use_prefix_only_features ... ok
test_public_materials_do_not_encode_answer_mapping ... ok
test_public_smoke_accepts_all_candidates_without_ranking_output ... ok
Ran 5 tests in 5.646s
OK
```

Direct public smoke output was clean:

```text
A: PASS
B: PASS
C: PASS
D: PASS
E: PASS
```

The hidden result has failure-count shape `[0, 1, 1, 1, 1]` and covers exactly
the four required Level 2 rule IDs. The authoritative letter is intentionally
omitted from this report.

### Fresh combined verification

Command:

```text
conda run -n ml python -m unittest tests.research_audit_training_v2.test_00_package_contract tests.research_audit_training_v2.test_05_shared_contracts tests.research_audit_training_v2.test_10_level1_algorithm tests.research_audit_training_v2.test_20_level2_pipeline -v
```

Result:

```text
Ran 32 tests in 64.386s
OK
```

## Files

Created:

- `tests/research_audit_training_v2/test_20_level2_pipeline.py`
- `LLM4SBR_research_audit_training_v2/level_2_pipeline_integrity/_runtime.py`
- `LLM4SBR_research_audit_training_v2/level_2_pipeline_integrity/FROZEN_PIPELINE_SPEC.md`
- `LLM4SBR_research_audit_training_v2/level_2_pipeline_integrity/run_smoke.py`
- For each candidate module: `candidates/<letter>/__init__.py`
- For each candidate module: `candidates/<letter>/data.py`
- For each candidate module: `candidates/<letter>/trainer.py`
- For each candidate module: `candidates/<letter>/metrics.py`
- For each candidate module: `candidates/<letter>/pipeline.py`
- `LLM4SBR_research_audit_training_v2/level_2_pipeline_integrity/DO_NOT_OPEN_UNTIL_FINISHED/pipeline_probes.py`
- `LLM4SBR_research_audit_training_v2/level_2_pipeline_integrity/DO_NOT_OPEN_UNTIL_FINISHED/answer_manifest.json`
- `LLM4SBR_research_audit_training_v2/level_2_pipeline_integrity/DO_NOT_OPEN_UNTIL_FINISHED/ANSWER_KEY.md`

Updated:

- `LLM4SBR_research_audit_training_v2/level_2_pipeline_integrity/README.md`
- `LLM4SBR_research_audit_training_v2/level_2_pipeline_integrity/ANSWER_SHEET.md`

## Self-review

- Every candidate is a five-module package and exports
  `run_pipeline(output_dir: Path) -> dict[str, object]`.
- Every run trains a CPU PyTorch model for three epochs, consumes both long and
  short prefix-derived features, saves three checkpoints, and writes all seven
  required artifacts with a common schema.
- Feature construction reads only the visible prefix. Public tests independently
  recompute the four-dimensional item formula, long/short aggregation, and
  hashes for every example from every candidate.
- The common split semantics assign time-ordered raw sessions 1–9, 10–12, and
  13–15 before prefix expansion. The isolated split mutation changes only the
  raw-session-versus-expanded-prefix decision.
- Batch artifacts serialize the actual rows consumed during training. The
  isolated joint-permutation mutation changes only the feature-row index while
  identity, prefix, and target continue to follow the permutation.
- Evaluation loss always uses the full population. The isolated reporting
  mutation changes only the rows retained for per-example metrics; all ordinary
  runs still emit finite bounded summaries.
- Selection uses full-population cross entropy with earliest-epoch tie breaking.
  The isolated boundary mutation changes only the selection role; generic event
  logging truthfully exposes every protected evaluation.
- Hidden probes execute each pipeline once and derive findings exclusively from
  artifact relationships. The test suite independently reimplements all four
  checks and matches the hidden classification candidate by candidate.
- Each manifest fault records one unique source span, a repair expression, a
  causal chain, and at least two evidence artifacts/files. Candidate package
  file counts are identical; comments and line counts do not single out the
  trusted implementation.
- Dynamic package loading registers packages in `sys.modules` before execution.
- Public stdout contains no metric ranking, and public materials contain no
  answer mapping. Package leak tests pass.
- Frozen legacy hashes pass. No protected source, old training material, or PDF
  was modified. No network, dependency installation, or Git operation was used.

## Concerns

None known.
