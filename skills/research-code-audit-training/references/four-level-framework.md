# Four-level framework

## Boundary rule

Assign the level by the first broken contract:

| Level | First broken contract | Human capability trained | Preferred evidence |
|---|---|---|---|
| 1 | Formula/operator semantics | Translate paper mathematics into tensor and gradient semantics | Property test, minimal tensor, gradient probe |
| 2 | Automated data/state/evaluation flow | Trace identity, lineage, lifecycle, and evaluation boundaries | Cross-artifact lineage and independent recomputation |
| 3 | Comparison design/evidence/claim | Judge fairness, statistical units, completeness, and claim scope | Config comparison, ledger reconstruction, frozen analysis rule |
| 4 | Authorization/process governance | Enforce approval, budget, stop, record, and protected-evidence boundaries | Event timeline, approval chain, ledger and report audit |

Downstream consequences may cross levels. Keep the primary fault at the first broken contract.

## Level 1 fault families

- Wrong normalization or aggregation dimension while shapes remain valid.
- Padding or invalid positions receive probability mass.
- Probabilities are passed to a loss expecting logits, or scores use the wrong scale/sign.
- A `.detach()`, in-place operation, frozen parameter, or optimizer omission breaks an update path.
- Legal but semantically wrong indices, labels, temporal positions, or special tokens.
- Training/evaluation state or scaling changes mathematical meaning.

Quality bar: a very small source mutation with high scientific impact; finite forward/backward; not visually obvious; proven locally without long training.

## Level 2 fault families

- Split after expansion, augmentation, or windowing so the parent entity leaks across splits.
- Shuffle only some aligned modalities or labels.
- Cache, resume, scheduler, or checkpoint state belongs to the wrong run or epoch.
- Misses, failures, or empty cases disappear from metric denominators.
- Test/protected evaluation selects checkpoints or hyperparameters.
- Padding/item-ID offsets or candidate filtering drift across components.

Quality bar: requires following identity or state across multiple components; all candidates complete a realistic bounded pipeline.

## Level 3 fault families

- Unequal tuning trials, compute, early stopping, or engineering attention.
- Different features, candidate sets, external data, preprocessing, or oracle information.
- Planned runs exist but unfavorable runs are excluded under undeclared rules.
- Correlated checkpoints, epochs, crops, windows, or seeds are treated as independent scientific units.
- Pairing is broken or uncertainty/claims exceed the frozen analysis plan.
- A descriptive improvement is presented as stable, general, causal, or practically meaningful without support.

Quality bar: files are schema-valid and arithmetic can be correct. The flaw is scientific, not a broken CSV.

## Level 4 fault families

- A rejected, pending, late, wrong-scope, or limit-insufficient approval is followed by the action.
- Runs or compute exceed approved limits.
- Failed, cancelled, or negative runs are omitted from the report.
- Protected evidence explicitly flows into later adaptive development.
- An agent continues when a frozen protocol says stop and request approval.

Quality bar: use positive timeline evidence. Do not infer a violation merely because an optional approval ID is absent. Distinguish allowed post-hoc description from adaptation.

## Human-role mapping

The four levels train the modern programmer as:

1. mathematical implementation auditor;
2. data and lifecycle architect;
3. scientific evidence and claim reviewer;
4. experiment owner and agent-governance approver.

Agent execution bandwidth does not transfer final responsibility for problem definition, protected-data boundaries, fairness, or publication claims.
