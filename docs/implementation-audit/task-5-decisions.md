# Task 5 Controller Decisions

No dossier-letter mapping is assigned here. The mapping belongs only in the isolated answer manifest.

## Machine-auditable study contract

- Study: `l3-fixed-study-v1`; dataset: `synthetic-sbr-final-v1`; metric: `NDCG@10`.
- Normal information condition gives both methods candidate set `catalog-8-v1` and features `session_history_v1,item_id_v1`.
- Normal search protocol gives both methods four approved validation trials and the same budget unit/value.
- Normal final evaluation contains four paired blocks `P01`–`P04`, one baseline and one proposed observation per block.
- `planned_runs` remains the source of expected run completeness even when a candidate omits or excludes a result.
- Hidden policy checks only structured JSON/CSV fields; Markdown is explanatory and may not be the sole evidence for a finding.

## Normal values

Baseline values by pair: `0.400,0.420,0.410,0.430`.

Proposed values by pair: `0.440,0.455,0.445,0.460`.

Paired mean difference is `0.035`, exceeding the frozen practical threshold `0.020`. `aggregate.csv` uses sample standard deviation and descriptive `mean ± std`, rounded to 12 decimals; this interval is never used as a significance test.

The trusted claim is limited to the frozen dataset, candidate population and protocol. `claim.json` identifies the claim, threshold and all evidence run IDs; `claim.md` cites the same Claim-ID.

## Single primary faults

- Budget fairness changes only structured per-method approved trial IDs/max trials/budget from equal to 2 versus 4.
- Information condition changes only the proposed method feature set by adding `catalog_text_embedding_v1`.
- Selective reporting keeps the complete planned matrix but marks selected proposed runs included and low runs excluded with an exclusion code absent from the predeclared exclusion list; its aggregate remains arithmetically correct for the declared included rows.
- Experimental-unit fault expands each pair/method into three correlated checkpoint snapshots and declares checkpoint observations as units; its aggregate remains arithmetically correct, while the frozen review standard requires one final observation per pair/method.

Every public dossier remains schema-valid and internally recomputable. Hidden findings cite concrete keys/run IDs and never rely on marginal-interval overlap.
