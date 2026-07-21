# Task 2 Report: Shared deterministic data, metrics, and schemas

## TDD evidence

### RED

Command:

```bash
conda run -n ml python -m unittest tests.research_audit_training_v2.test_05_shared_contracts -v
```

Result: expected import failure before production code existed.

```text
ModuleNotFoundError: No module named 'LLM4SBR_research_audit_training_v2.shared'
Ran 1 test in 0.000s
FAILED (errors=1)
```

### GREEN

Command:

```bash
conda run -n ml python -m unittest tests.research_audit_training_v2.test_05_shared_contracts -v
```

Result: all eight shared-contract tests passed with no warnings.

```text
Ran 8 tests in 0.006s
OK
```

## Files created

- `tests/research_audit_training_v2/test_05_shared_contracts.py`
- `LLM4SBR_research_audit_training_v2/shared/__init__.py`
- `LLM4SBR_research_audit_training_v2/shared/synthetic_sbr.py`
- `LLM4SBR_research_audit_training_v2/shared/metrics_reference.py`
- `LLM4SBR_research_audit_training_v2/shared/schemas.py`

## Self-audit

- `raw_sessions()` is a fixed, timestamp-ordered tuple of 15 frozen sessions.  It includes sequence lengths 3 through 7, repeated non-padding items, and 17 distinct non-padding item IDs; ID 0 never occurs.
- `prefix_examples()` carries the original session ID and embeddings, and each target is the next item following its exact stored prefix.
- `algorithm_batch()` constructs six compact-core tensors from a new PyTorch generator seeded with `8675309` on every call.
- Reference metrics emit one frozen `MetricRow` for every input target. Misses are explicit zero rows and aggregation divides by the supplied row population.
- JSON, JSONL, and CSV loaders use only the standard library. Parse and required-field failures include the input filename; JSONL failures also include the source line.
- No files in `LLM4SBR-main/`, `LLM4SBR_code_judgement_training/`, or the PDF were modified. Task 1 tests were not changed.

## Review-fix TDD evidence

### RED

Command:

```bash
conda run -n ml python -m unittest tests.research_audit_training_v2.test_05_shared_contracts -v
```

Result: three newly added contract tests failed for their intended pre-fix behaviours.

```text
FAIL: test_raw_item_vocabulary_matches_algorithm_batch_universe
AssertionError: 13 != 16

FAIL: test_jsonl_materializes_generator_required_keys_for_every_record
AssertionError: ValueError not raised

FAIL: test_required_values_reject_empty_and_whitespace_strings
AssertionError: ValueError not raised

Ran 11 tests in 0.014s
FAILED (failures=3)
```

### GREEN

Command:

```bash
conda run -n ml python -m unittest tests.research_audit_training_v2.test_05_shared_contracts -v
```

Result: all shared-contract tests passed with no warnings.

```text
Ran 11 tests in 0.005s
OK
```

### Review-fix self-audit

- The shared item universe is now IDs 1 through 17: `n_items` is 18 and `item_text` has 17 rows, while every algorithm target remains valid.
- `load_jsonl()` snapshots `required_keys` before iterating records, so a generator validates every JSONL object rather than only the first.
- `require_keys()` now treats `None`, `""`, and whitespace-only strings as missing; CSV row errors retain the filename and physical line number.
