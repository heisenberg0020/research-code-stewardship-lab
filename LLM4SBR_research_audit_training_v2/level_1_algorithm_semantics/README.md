# Level 1: Algorithm Semantics

Audit five runnable implementations against the mathematical contract in
`PAPER_MAP.md`. Every implementation completes the same smoke test, so runtime
success alone is not evidence of semantic fidelity.

## Student workflow

1. Read the paper map and inspect all candidate modules.
2. Design minimal counterexamples for normalization, padded attention,
   auxiliary-gradient flow, and the recommendation objective.
3. Run `conda run -n ml python level_1_algorithm_semantics/run_smoke.py` from
   the v2 package root.
4. Record one selection and an evidence chain in `ANSWER_SHEET.md` before
   opening the isolated materials.

Your evidence should distinguish a scalar value from its gradient path and a
ranking-preserving transformation from a loss-preserving transformation.
