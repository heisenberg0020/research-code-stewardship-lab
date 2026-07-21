# Level 1 Answer Key

The authoritative candidate mapping is stored in `answer_manifest.json`. The
mapping should be checked only after completing the public answer sheet.

## Audit method

The four hidden rules isolate one semantic boundary each:

- `L1_BATCH_INVARIANCE` calls intent localization directly so batch-dependent
  DirectAU uniformity cannot confound the result.
- `L1_PADDING` fixes every attention scoring parameter at zero, changes only a
  masked hidden row, and checks both the global vector and fused session.
- `L1_AUX_GRAD` differentiates the residual total-minus-recommendation scalar
  with respect to the text projection, separating auxiliary supervision from
  the recommendation branch.
- `L1_LOGIT_CE` calls the exported loss directly and compares both value and
  input gradient with raw-logit cross entropy.

Each faulty entry in the manifest includes its governing formula, exact unique
source span, one-expression repair, why the program still runs, the causal
chain, and the deterministic minimal counterexample. Applying just that repair
causes all four probes to pass for a temporary copy. The trusted entry passes
without repair.

The public smoke test is intentionally non-diagnostic: all modules import,
execute forward and backward, produce finite gradients, and complete one Adam
step. The semantic-site table also records five distinct textual forms at each
audited location plus a harmless style rotation, preventing a simple majority
or formatting heuristic from serving as the answer.
