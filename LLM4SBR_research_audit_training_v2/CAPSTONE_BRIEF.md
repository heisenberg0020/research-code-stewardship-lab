# Cross-layer Research Incident Capstone

This is a public, synthetic Open Demo brief. It is not L5, not a verified blind
exam, and not a scientific certification. It contains no evaluator mapping. Use it
only after practicing the four first-broken-contract layers.

## Situation

A research team is preparing a result for release. A scheduled rerun completed and
produced plausible figures, but the headline metric moved unexpectedly. The run
dashboard shows no crash. During the same period:

- a low-level numerical helper was refactored;
- a data-cache refresh and sample-order change were recorded;
- one comparison run used a different resource envelope after an interruption;
- an Agent performed several approved tasks and one action whose approval record
  is unclear;
- a draft abstract already contains a broad claim based on the affected result.

These are observations and leads, not diagnoses. More than one contract may have
failed, and a later-layer symptom must not be used to conceal an earlier break.

## Frozen public artifact packet

The following small, synthetic artifacts are the complete learner-visible packet
for this incident. Their IDs are fixture labels, **not** content hashes or proof
that the events happened in a real project. Cite a path plus an exact line, JSON
key, or row/event ID in your worksheet. Preserve the original bytes before making
an edit or running a check; put any derived evidence in your own workspace.

| Artifact | What it can help you inspect | What it cannot prove by itself |
| --- | --- | --- |
| [`change.diff`](capstone_artifacts/change.diff) | Two review excerpts from the numerical and cache-order changes | The full implementation, numerical behavior, or label lineage |
| [`run_config.json`](capstone_artifacts/run_config.json) | Frozen comparison plan and declared per-run settings | That the settings were actually used at runtime |
| [`run_ledger.csv`](capstone_artifacts/run_ledger.csv) | Terminal runs, reported metrics, resource totals, and evidence-bundle IDs | Raw metric rows, independent experimental units, or complete compute accounting |
| [`agent_events.csv`](capstone_artifacts/agent_events.csv) | Ordered Agent actions and their declared approval references | Authenticity, a complete audit trail, or authorization from a missing reference alone |
| [`approvals.csv`](capstone_artifacts/approvals.csv) | Declared approval decisions, scope, timing, and limits | Whether an unlinked action was actually covered by an approval |
| [`claim_note.md`](capstone_artifacts/claim_note.md) | A draft claim, its cited run IDs, and proposed release artifact | A signed publication decision or a scientifically valid conclusion |

The packet deliberately omits the full source tree, raw sample/label alignment,
per-example evaluation rows, command/environment capture, and an authenticated
approval system. Those absences are evidence gaps to identify and request, not
permission to invent a diagnosis. The same fixture can support several competing
hypotheses. A numerical refactor, cache ordering, resource-envelope drift,
governance linkage, and claim scope require separate checks and human decisions.

## Your role

You are the named research-code steward for this bounded incident. Do not assume
that a successful run, a polished figure, or an Agent explanation is sufficient
evidence. Work from the public artifacts you have or explicitly mark what remains
unknown. Do not access instructor-material directories.

## Required response

Use `worksheets/capstone.md` to produce one reviewable response that includes:

1. an immediate G0 stop/continue and evidence-preservation decision;
2. a triage of affected, possibly affected, and currently unaffected scope;
3. a per-finding L1–L4 first-broken-contract map;
4. competing hypotheses, independent checks, negative evidence, and remaining
   unknowns, each tied to packet IDs or precise artifact locations;
5. bounded Human–Agent delegation with permissions, budgets, acceptance, stop, and escalation rules;
6. retain/narrow/withdraw/block decisions for material claims and release artifacts;
7. remediation, regression evidence, rebaseline, prevention, owners, and revisit conditions;
8. a concise stakeholder update that does not overstate current evidence.

## Review boundary

The public CLI can report whether all required sections were completed and can
freeze the exact submission bytes. A fixture ID in an answer is a human citation,
not proof that its declared event happened. The CLI cannot decide which hypothesis
is true, whether the blast radius is sufficient, whether the claim is valid, or
whether the learner demonstrated a maturity band. The capstone passes only through
an explicit record from a named human reviewer, whose label is declared rather
than authenticated.
