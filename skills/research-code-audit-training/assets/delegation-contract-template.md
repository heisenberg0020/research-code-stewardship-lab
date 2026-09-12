# Human–Agent Delegation Contract

Define this contract before delegating a consequential research task. Replace
every double-braced prompt. The human owner remains responsible for approvals
and scientific claims even when an agent performs the work.

## Task boundary

- Delegation ID: {{stable ID}}
- Goal and expected deliverable: {{goal and deliverable}}
- Human owner: {{name and role}}
- Agent or automation identity: {{agent identity and version}}
- Input revisions: {{paper, code, data, and configuration revisions}}
- Explicit non-goals: {{non-goals}}

## Allowed action surface

- Permitted files, systems, tools, and commands: {{allowlist}}
- Permitted network or external services: {{network allowlist or None}}
- Read-only or protected resources: {{protected resources}}
- Forbidden actions and disclosures: {{denylist}}
- Time, compute, cost, and retry budget: {{budgets}}

## Contracts and evidence

- Invariants that must remain true: {{contract IDs and invariants}}
- Checks the agent must run: {{bounded validation commands or procedures}}
- Evidence the agent must return: {{diffs, logs, manifests, tests, and unknowns}}
- Success and failure criteria: {{observable criteria}}

## Human checkpoints

- Actions requiring approval before execution: {{approval gates}}
- Reviewer for each gate: {{reviewers}}
- Conditions that require stop and escalation: {{stop conditions}}
- Rollback or recovery procedure: {{recovery plan}}

## Completion decision

- Agent-reported outcome and limitations: {{outcome and limitations}}
- Human verification performed: {{independent checks}}
- Decision (`accept`, `revise`, `reject`, or `investigate`): {{decision}}
- Decision evidence and sign-off: {{evidence, owner, and date}}
