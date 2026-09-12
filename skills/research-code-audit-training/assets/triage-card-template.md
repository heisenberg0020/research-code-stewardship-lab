# Rapid Triage Card

Use this card to turn an anomaly into a bounded investigation before asking an
agent to change code. Replace every double-braced prompt.

## Signal and impact

- Incident or anomaly ID: {{stable ID}}
- Observed signal and first timestamp: {{observation and time}}
- Affected artifact, run, or claim: {{scope}}
- Potential severity and blast radius: {{severity and affected decisions}}
- Immediate containment already taken: {{containment or None with reason}}

## First-contract localization

- Earliest plausible boundary (`G0`, `L1`, `L2`, `L3`, `L4`, or cross-cutting): {{boundary}}
- Evidence for that boundary: {{specific evidence}}
- Downstream symptoms not to confuse with the cause: {{symptoms}}

## Competing hypotheses

| Hypothesis | Cheapest discriminating check | Result | Keep / reject |
| --- | --- | --- | --- |
| {{hypothesis}} | {{check}} | {{result}} | {{disposition}} |

## Bounded investigation

- Minimal reproduction or independent recomputation: {{procedure}}
- Logs, revisions, identities, and configuration frozen: {{evidence references}}
- Changes deliberately avoided during diagnosis: {{protected state}}
- Time and compute budget: {{limits}}

## Decision

- Current classification: {{cause, unresolved ambiguity, or false alarm}}
- Next action and owner: {{action and owner}}
- Stop, rollback, or escalation trigger: {{trigger}}
- Evidence required before resuming: {{required evidence}}
- Human reviewer and date: {{reviewer and date}}
