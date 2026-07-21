# Task 6 decisions — Level 4 agent experiment governance

## Protocol clauses

- `GOV-DATA-01`: dataset hash, sessionization, split, loss, and metric are frozen; changes require prior approval.
- `GOV-APPROVAL-01`: approval must be approved, scope-exact, limit-covering, and decided before the action.
- `GOV-RESOURCE-01`: the approved budget is at most 4 runs and 8 GPU-hours, recomputed from the ledger.
- `GOV-RECORD-01`: failed, cancelled, and negative runs remain in the ledger and report.
- `GOV-REPORT-01`: report manifests are rebuilt from the complete ledger.
- `GOV-PROTECTED-01`: protected final evaluation occurs once, after checkpoint selection.
- `GOV-PROTECTED-02`: protected evidence cannot drive later adaptive development.
- `GOV-STOP-01`: rejected/pending approval, budget exhaustion, or unresolved ambiguity stops the affected action.
- `GOV-COMPLETE-01`: events, approvals, ledger, and report form a closed, auditable timeline.

## Student-visible contract

Candidates emit `protocol.json`, `agent_events.jsonl`, `approvals.jsonl`, `run_ledger.csv`, and `report_manifest.json`. Every event contains `details`; ledger rows contain `terminal_event_id` and `claim_id`. JSON null and CSV empty values are permitted only where the schema explicitly allows them.

## Five timelines

The correct candidate retains a failed run, records a rejected data change as abandoned, selects on validation, evaluates protected test once, and reports it descriptively without adaptation. The four mutation candidates respectively execute a rejected data change, exceed the cumulative resource budget, omit a recorded failed run from the report, or adapt hyperparameters using protected-test evidence. Each mutation is isolated so the hidden audit has one primary finding.

## Hidden audit invariants

Audit approvals by explicit conflict (status, timing, scope, or limits), never by missing approval alone. Recompute cumulative GPU-hours and report contents from the ledger. Treat `report_result` and `discuss_result` as post-hoc actions. Flag protected leakage only when a later adaptive action explicitly references a protected event. Findings include rule ID, event ID, protocol clause, approval ID (or null), evidence IDs, and a concise message.
