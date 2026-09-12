# Level 2 · Pipeline Integrity

> **Question:** do data, splits, training, evaluation, and checkpointing still form one trustworthy experiment?

Audit the candidates as a connected system. Each one completes the same deterministic three-epoch run and writes the same artifact family; successful execution does **not** establish trustworthy lineage.

## What you will practice

- Trace stable sample identities across split, batch, evaluation, checkpoint, and event artifacts.
- Recompute audit invariants from serialized evidence instead of trusting logs.
- Recognize how a locally reasonable data or checkpoint decision can invalidate an entire comparison.

## Start here

From the `LLM4SBR_research_audit_training_v2/` directory:

```bash
python level_2_pipeline_integrity/run_smoke.py
```

You should see a passing public smoke check. It establishes operability, not the integrity of any candidate's experiment lineage.

## Learner workflow

1. Read [FROZEN_PIPELINE_SPEC.md](FROZEN_PIPELINE_SPEC.md) before inspecting implementations.
2. Run the public smoke command and identify the artifacts it creates or verifies.
3. Trace sample identities through split, batching, evaluation, checkpoint selection, and event records.
4. Recompute the four audit invariants from the serialized evidence.
5. Record a selection and causal argument in [ANSWER_SHEET.md](ANSWER_SHEET.md), then submit it before consulting instructor-only material.

## Completion standard

Your audit should explain how the selected candidate preserves the frozen experiment contract, and why each rejected candidate breaks that contract even if it emits the expected artifacts.

**Previous:** [Level 1 · Algorithm Semantics](../level_1_algorithm_semantics/README.md)<br />
**Next:** [Level 3 · Scientific Validity](../level_3_scientific_validity/README.md)
