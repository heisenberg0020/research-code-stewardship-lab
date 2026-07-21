# Level 2: Pipeline Integrity

Audit data splitting, batching, evaluation, and checkpoint selection as one
connected system. Each candidate completes the same deterministic three-epoch
run and writes the same artifact family; successful execution alone does not
establish trustworthy lineage.

## Student workflow

1. Read `FROZEN_PIPELINE_SPEC.md` before inspecting implementations.
2. Run the public smoke command from the v2 package root.
3. Trace stable sample identities across split, batch, evaluation, checkpoint,
   and event artifacts.
4. Recompute the four audit invariants from serialized evidence.
5. Record a selection and causal evidence in `ANSWER_SHEET.md` before opening
   isolated materials.
