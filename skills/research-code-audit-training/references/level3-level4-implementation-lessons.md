# Level 3 and Level 4 implementation lessons

## Level 3: separate arithmetic validity from scientific validity

Use four linked evidence layers:

1. `planned_runs.csv` defines every expected unit, pair, method, and observation role.
2. `runs.csv` records every observed result plus inclusion and exclusion decisions.
3. `aggregate.csv` is exactly recomputable from declared included rows.
4. `claim.json` states scope, threshold, paired effect, and exact evidence run IDs; prose repeats its claim ID.

The public validator checks schema, planned/observed identity, arithmetic, and claim references. It deliberately does not decide fairness or scientific validity.

Freeze a complete comparison signature for each method: approved trial IDs, maximum trials, budget unit and value, candidate population, features, and preprocessing. Equality of only one budget number is insufficient.

Treat the independent unit as an explicit field and independently count observations per `(pair_id, method)`. A seed, epoch, checkpoint, crop, or window is not automatically an independent scientific unit. Do not use marginal confidence-interval overlap as a significance rule.

For selective reporting, keep the planned matrix complete. Record exclusions explicitly and compare their codes with the predeclared set. Keep the aggregate mathematically correct for included rows so the intended fault remains reporting policy rather than arithmetic corruption.

## Level 4: audit explicit evidence flow

Use stable protocol clause IDs and five structured artifacts:

- frozen protocol;
- ordered agent events;
- approval decisions;
- complete run ledger;
- report manifest.

Every event carries `event_id`, timestamp, action type, scope, nullable run/approval IDs, evidence references, decision basis, and details. Validators must distinguish a missing field from a present, schema-allowed null or blank.

Flag an approval violation only when an explicit approval conflicts by status, decision time, exact scope, or limits. Absence alone is not positive proof unless the closed protocol explicitly makes approval mandatory and completeness is established.

Recompute cumulative runs and resource use from the ledger. Locate the first terminal event crossing the approved boundary. Rebuild report manifests from the complete ledger; never validate a report against itself. A retained failed run with `reported=false` is still a reporting-integrity violation.

Identify protected-evidence misuse through explicit graph flow: a protected evaluation event ID appears in `evidence_refs` of a later action classified as adaptive. `report_result` and `discuss_result` are post-hoc actions and must not be false positives.

## Singleton-fault discipline

Keep each candidate's schema valid and all ordinary calculations consistent. The candidate should violate one primary policy only. Audit all other policies before accepting the fixture; otherwise a budget candidate may accidentally become an information-condition or record-integrity candidate too.

Unexpected parse, import, or execution errors are infrastructure failures. Propagate them instead of converting them into domain findings.
