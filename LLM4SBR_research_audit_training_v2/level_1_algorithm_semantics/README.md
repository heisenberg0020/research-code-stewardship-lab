# Level 1 · Algorithm Semantics

> **Question:** does a runnable implementation still mean what the paper's equations mean?

Audit five runnable candidates against the mathematical contract in [PAPER_MAP.md](PAPER_MAP.md).
Every candidate completes the same smoke test, so a successful run is **not** evidence of semantic fidelity.

## What you will practice

- Translate paper statements into executable invariants.
- Separate a scalar value from its gradient path.
- Separate a ranking-preserving transformation from a loss-preserving one.
- Build a minimal counterexample rather than relying on a visually plausible implementation.

## Start here

From the `LLM4SBR_research_audit_training_v2/` directory:

```bash
python level_1_algorithm_semantics/run_smoke.py
```

You should see a passing public smoke check. That confirms only that the candidates are runnable; it does not reveal which candidate is trustworthy.

## Learner workflow

1. Read [PAPER_MAP.md](PAPER_MAP.md) before opening the candidates. Turn each listed claim into a checkable invariant.
2. Inspect implementations `A.py` through `E.py`. Keep separate notes for each one.
3. Design small counterexamples for normalization, padded attention, auxiliary-gradient flow, and the recommendation objective.
4. Record your selection and causal evidence in [ANSWER_SHEET.md](ANSWER_SHEET.md).
5. Submit your audit before consulting any instructor-only material.

## Completion standard

Your answer should identify one trustworthy implementation and explain, with exact evidence, why every rejected alternative violates an invariant. An implementation that produces the same-looking scores can still be wrong if its gradient path or objective changes.

**Next:** [Level 2 · Pipeline Integrity](../level_2_pipeline_integrity/README.md)
