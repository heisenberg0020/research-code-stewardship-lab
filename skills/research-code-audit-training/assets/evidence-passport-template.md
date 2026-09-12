# Audit Evidence Passport

Use one passport for one material finding or trust decision. Replace every
double-braced prompt. A completed form records an argument; it does not by
itself prove that the argument is scientifically correct.

## Decision identity

- Audit and finding ID: {{stable audit ID and finding ID}}
- Artifact revision: {{commit, dataset version, run ID, or manifest hash}}
- Reviewer and date: {{reviewer, role, and YYYY-MM-DD}}
- Audit level (`L1`, `L2`, `L3`, `L4`, or `cross-cutting`): {{level}}
- Primary stewardship capability (`C1`–`C7`): {{capability ID and name}}
- Target maturity (`Recognize`, `Prove`, `Direct`, or `Steward`): {{maturity}}
- Decision (`accept`, `reject`, `block`, or `needs-evidence`): {{decision}}

## Claim and first broken contract

- Claim being evaluated: {{precise claim}}
- First broken contract or invariant: {{contract ID and plain-language rule}}
- Why this is the first break rather than a downstream symptom: {{boundary reasoning}}

## Evidence chain

- Exact source locations: {{file, line, key, event, run, or record IDs}}
- Independent evidence or recomputation: {{method and result}}
- Minimal counterexample or reproduction: {{smallest falsifying procedure}}
- Why the artifact can still run or look plausible: {{plausibility explanation}}

## Causal assessment

- Immediate effect: {{direct effect}}
- Downstream claim impact: {{impact on evidence or decision}}
- Direction and magnitude: {{supported direction and magnitude, or Unknown with reason}}
- Competing explanation checked: {{alternative and result}}

## Response

- Smallest safe repair or governance action: {{repair or action}}
- Regression or acceptance evidence required: {{tests, reruns, or approvals}}
- Residual risk and unresolved evidence: {{remaining uncertainty}}
- Confidence and basis: {{confidence with justification}}
- Human owner decision and sign-off: {{owner, decision, and date}}
