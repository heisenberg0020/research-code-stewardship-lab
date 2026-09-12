# Progression

Read the [Case File](CASE_FILE_EN.md) first so the G0 scope, provenance, permitted
claims, and validation limits are explicit. Then work through the four levels in
numerical order and finish with the cross-layer capstone. Learner-facing materials
are separated from post-completion material by convention; this public layout is
honor isolation, not access control.

1. **Level 1 — Algorithm semantics:** prove local tensor, loss, mask, and gradient semantics.
2. **Level 2 — Pipeline integrity:** reconstruct identity, permutation, metric, and checkpoint lineage.
3. **Level 3 — Scientific validity:** audit comparison fairness, reporting completeness, and experimental units.
4. **Level 4 — Agent governance:** audit approvals, budgets, records, and protected-evidence use.
5. **Capstone — Cross-layer incident:** triage interacting signals, preserve evidence, bound delegation and claims, and communicate the current decision.

Advance only after recording exact locations, violated contracts, competing
hypotheses, causal effects, minimal counterexamples, claim boundaries, and safe
responses—not merely a candidate letter.

## Resumable local route

Create a learner-owned workspace outside this repository:

```bash
python scripts/rcsl.py train progress init \
  --output /absolute/path/to/my-rcsl-progress \
  --learner "your declared label"
```

For each target (`L1`, `L2`, `L3`, `L4`, then `capstone`):

```bash
python scripts/rcsl.py train progress check /absolute/path/to/my-rcsl-progress --target L1
python scripts/rcsl.py train progress submit /absolute/path/to/my-rcsl-progress --target L1
python scripts/rcsl.py train progress status /absolute/path/to/my-rcsl-progress
```

`check` establishes structural completeness only. `submit` freezes an immutable
attempt and waits for a named human review. A new submission is a retry and keeps
the earlier attempt and review history. Recognize / Prove / Direct / Steward are
human observations from the copied `RUBRIC.md`, not an automatic maturity score.

The capstone brief is public and synthetic. It has no answer mapping, and structural
completion cannot pass it. A named human must record the final capstone review.
See [Mode Train](../docs/TRAIN_MODE_EN.md) for the complete command and trust boundary.
