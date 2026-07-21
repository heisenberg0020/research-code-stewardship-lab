# Task 3 Level 1 Implementation Report

## Status

DONE

## TDD evidence

### RED

Command:

```text
conda run -n ml python -m unittest tests.research_audit_training_v2.test_10_level1_algorithm -v
```

The first run exited 1. It demonstrated the expected missing-feature failures:
`run_smoke.py` was absent, `probes.py` was absent, and the manifest and paper map
were absent. One direct detach-property assertion initially expected an unused
gradient (`None`); the actual residual retains a cancelling recommendation path
and correctly produces a zero tensor. After correcting that test assertion, a
second RED run had both direct mathematical property tests passing while the
remaining one failure and four errors were all caused by the missing Level 1
implementation files.

### GREEN

Task 3 command result:

```text
Ran 7 tests in 52.679s
OK
```

The public smoke output was re-run directly after warning cleanup:

```text
A: PASS
B: PASS
C: PASS
D: PASS
E: PASS
```

The hidden behavior report has failure-count shape `[0, 1, 1, 1, 1]` and its
four singleton failures cover exactly `L1_BATCH_INVARIANCE`, `L1_PADDING`,
`L1_AUX_GRAD`, and `L1_LOGIT_CE`. The trusted candidate letter is intentionally
omitted from this report.

### Fresh combined verification

Command:

```text
conda run -n ml python -m unittest tests.research_audit_training_v2.test_00_package_contract tests.research_audit_training_v2.test_05_shared_contracts tests.research_audit_training_v2.test_10_level1_algorithm -v
```

Result:

```text
Ran 25 tests in 52.383s
OK
```

This includes 7 package-contract tests, 11 shared-contract regression tests,
and 7 Level 1 tests.

## Files

Created:

- `tests/research_audit_training_v2/test_10_level1_algorithm.py`
- `LLM4SBR_research_audit_training_v2/level_1_algorithm_semantics/PAPER_MAP.md`
- `LLM4SBR_research_audit_training_v2/level_1_algorithm_semantics/run_smoke.py`
- `LLM4SBR_research_audit_training_v2/level_1_algorithm_semantics/candidates/A.py`
- `LLM4SBR_research_audit_training_v2/level_1_algorithm_semantics/candidates/B.py`
- `LLM4SBR_research_audit_training_v2/level_1_algorithm_semantics/candidates/C.py`
- `LLM4SBR_research_audit_training_v2/level_1_algorithm_semantics/candidates/D.py`
- `LLM4SBR_research_audit_training_v2/level_1_algorithm_semantics/candidates/E.py`
- `LLM4SBR_research_audit_training_v2/level_1_algorithm_semantics/DO_NOT_OPEN_UNTIL_FINISHED/probes.py`
- `LLM4SBR_research_audit_training_v2/level_1_algorithm_semantics/DO_NOT_OPEN_UNTIL_FINISHED/answer_manifest.json`
- `LLM4SBR_research_audit_training_v2/level_1_algorithm_semantics/DO_NOT_OPEN_UNTIL_FINISHED/ANSWER_KEY.md`

Updated:

- `LLM4SBR_research_audit_training_v2/level_1_algorithm_semantics/README.md`
- `LLM4SBR_research_audit_training_v2/level_1_algorithm_semantics/ANSWER_SHEET.md`

## Self-review

- All five modules export the required interface and complete import, forward,
  finite-loss validation, backward, finite-gradient validation, and one Adam
  step under seed `20260711`.
- Every faulty candidate changes only its designated semantic expression. Query
  normalization leaves item-row normalization intact; padding changes only the
  pre-softmax fill; detach affects only total-loss construction while the raw
  auxiliary is returned; and the CE mutation affects only the function input
  while model logits remain raw.
- Each probe is isolated according to the controller decision: batch probing
  calls localization directly, padding fixes attention parameters, auxiliary
  probing differentiates the residual against text projection, and CE probing
  compares both scalar and input gradients.
- The manifest records one unique source span and repair for each faulty module.
  Tests apply each repair to a temporary copy and confirm all four probes pass.
- Five distinct textual forms exist at every semantic site and at the harmless
  style-rotation site. Token/AST distance checks confirm the trusted module is
  not the unique text center, and it is not the shortest candidate.
- Dynamic loaders register modules in `sys.modules` before `exec_module`.
- Public documentation and the answer sheet contain no answer mapping; package
  leak checks pass. Only isolated materials contain the authoritative mapping.
- Frozen legacy hashes pass. No old source, old training asset, or PDF was
  changed. No network, dependency installation, or Git operation was used.

## Concerns

None known.

## Review follow-up: infrastructure, local-marker resistance, target dtype

### Focused RED evidence

Tests were added before implementation for all three review findings, then run
together with:

```text
conda run -n ml python -m unittest tests.research_audit_training_v2.test_10_level1_algorithm.Level1Tests.test_hidden_probe_infrastructure_errors_are_not_misclassified tests.research_audit_training_v2.test_10_level1_algorithm.Level1Tests.test_semantic_sites_have_no_textual_majority_and_trusted_is_not_text_center tests.research_audit_training_v2.test_10_level1_algorithm.Level1Tests.test_recommendation_losses_accept_integer_valued_floating_targets -v
```

Exact RED summary:

```text
test_hidden_probe_infrastructure_errors_are_not_misclassified ... FAIL
test_semantic_sites_have_no_textual_majority_and_trusted_is_not_text_center ... FAIL
test_recommendation_losses_accept_integer_valued_floating_targets ... ERROR
Ran 3 tests in 0.045s
FAILED (failures=2, errors=1)
```

The observed causes matched the review findings: the dummy `RuntimeError` was
not propagated; the first marker audit found zero `0 if` query snippets; and a
candidate passed a Double target vector to cross entropy after subtracting a
floating one tensor.

### Focused GREEN evidence

After the minimal implementation changes, the identical command produced:

```text
test_hidden_probe_infrastructure_errors_are_not_misclassified ... ok
test_semantic_sites_have_no_textual_majority_and_trusted_is_not_text_center ... ok
test_recommendation_losses_accept_integer_valued_floating_targets ... ok
Ran 3 tests in 48.809s
OK
```

The four marker predicates now each occur in exactly two of the five recorded
semantic snippets. All snippets remain distinct. The extra appearances are
semantically harmless, while every faulty module retains exactly one true
semantic mutation.

### Full Level 1 and combined GREEN evidence

Focused Level 1 command:

```text
conda run -n ml python -m unittest tests.research_audit_training_v2.test_10_level1_algorithm -v
Ran 9 tests in 54.733s
OK
```

This revalidated the `[0, 1, 1, 1, 1]` classification shape and all four
temporary one-expression repairs after removing the blanket probe exception
handler and updating manifest spans/snippets.

Fresh combined command:

```text
conda run -n ml python -m unittest tests.research_audit_training_v2.test_00_package_contract tests.research_audit_training_v2.test_05_shared_contracts tests.research_audit_training_v2.test_10_level1_algorithm -v
Ran 27 tests in 52.926s
OK
```

No protected file changed, the student-side leak checks remain green, and the
authoritative letter remains confined to isolated material.
