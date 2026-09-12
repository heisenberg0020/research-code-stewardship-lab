# G0 Research Contract

Replace every double-braced prompt below. If evidence is unavailable, write
`Unknown — reason; person responsible for resolving it` instead of guessing.
This contract is a decision gate: work may begin only after the named human
owner accepts the unresolved risks.

## Identity and decision

- Project or audit: {{project name}}
- Contract version or commit: {{version or revision}}
- Human owner: {{name and role}}
- Review date: {{YYYY-MM-DD}}
- Decision this work will inform: {{decision}}

## Research mandate

- Research question: {{question}}
- Construct, estimand, or evidence target: {{what is actually being measured or proved}}
- Target population and operating context: {{population and context}}
- Strongest claim permitted if the success criteria are met: {{allowed claim}}
- Explicitly out of scope: {{non-goals}}

## Success, failure, and stopping

- Success criteria: {{observable criteria}}
- Failure criteria: {{observable failure conditions}}
- Stop or escalation conditions: {{conditions that require a human decision}}
- Protected evaluation boundary: {{data or evidence that cannot guide adaptation}}

## Sources, rights, and legitimacy

- Paper or specification source: {{source and revision}}
- Code source: {{repository and commit}}
- Data provenance and permission: {{origin, consent, license, and access basis}}
- Software and model licenses: {{license compatibility}}
- Privacy, safety, fairness, or ethics review: {{review status and constraints}}
- Intended users and people who could be affected: {{stakeholders}}

## Human authority and delegation

- Decisions reserved for the human owner: {{human-only decisions}}
- Actions an agent may perform without another approval: {{permitted actions}}
- Actions requiring explicit approval: {{approval gates}}
- Forbidden actions, paths, services, and disclosures: {{prohibited actions}}
- Time, compute, cost, and network budget: {{resource limits}}

## Assumptions and unknowns

| Assumption or unknown | Evidence available | Consequence if false | Owner / next check |
| --- | --- | --- | --- |
| {{item}} | {{evidence}} | {{consequence}} | {{owner and check}} |

## Human gate decision

This contract records the evidence and constraints a named human needs for the
gate. It does not store the final gate outcome. Record the authoritative
`draft`, `approved`, or `blocked` decision only with `audit gate record`; do not
duplicate it here.

- Decision questions requiring human judgment: {{decision questions}}
- Unresolved risks to present at the gate: {{risks requiring a decision}}
