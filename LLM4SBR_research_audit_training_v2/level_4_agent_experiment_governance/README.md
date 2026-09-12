# Level 4 · Agent Experiment Governance

> **Question:** did the agent have the authority to take each action, regardless of how good the metric looked?

Audit `runs/A` through `runs/E` against [FROZEN_PROTOCOL.md](FROZEN_PROTOCOL.md). This level treats a research run as a governed sequence of approvals, actions, budgets, evidence, and ledger entries—not merely a final score.

## What you will practice

- Separate metric quality from authorization.
- Reconstruct an approval and evidence chain from an event/ledger timeline.
- Identify the minimum compliant stop or repair action when a protocol boundary is crossed.

## Start here

From the `LLM4SBR_research_audit_training_v2/` directory:

```bash
python level_4_agent_experiment_governance/validate_ledger_schema.py
```

This neutral public check verifies only that the ledger can be parsed. It does **not** decide whether the actions were authorized.

## Learner workflow

1. Read [FROZEN_PROTOCOL.md](FROZEN_PROTOCOL.md) before inspecting the runs.
2. Inspect `runs/A` through `runs/E` as complete timelines: events, approvals, budgets, evidence flow, and ledger entries.
3. For every action, establish the authorizing clause and approval ID—or identify the exact missing or expired authorization.
4. Record the trustworthy run in [ANSWER_SHEET.md](ANSWER_SHEET.md). For every rejection, cite event IDs, approval IDs, protocol clauses, ledger rows, evidence flow, and the minimum compliant stop or repair action.
5. Submit your audit before consulting instructor-only material.

## Completion standard

The selected run must satisfy the frozen protocol end to end. A better metric cannot retrospectively authorize an unapproved data access, spend, model change, or claim.

**Previous:** [Level 3 · Scientific Validity](../level_3_scientific_validity/README.md)<br />
**Course hub:** [LLM4SBR Research Audit Training v2](../README.md)
