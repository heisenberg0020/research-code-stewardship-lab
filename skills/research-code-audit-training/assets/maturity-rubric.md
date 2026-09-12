# Human Audit Maturity Rubric v1

This rubric helps named human reviewers explain observable differences in a frozen
training attempt. It is not an automatic score, a global rank, an identity check,
or certification that a research claim is true.

For each band, record exactly one observation:

- `not-observed`: the frozen attempt does not show the behavior.
- `partial`: some relevant behavior is visible, but material evidence is missing.
- `demonstrated`: the reviewer finds the behavior observable for this bounded task.
- `cannot-assess`: available evidence does not support a responsible judgment.

Two reviewers' records remain separate. Do not average disagreements. Explain them
at criterion level and request evidence or an explicit adjudication when needed.

## Recognize

- **R1:** Notices a material anomaly without relying only on a label or metric size.
- **R2:** Locates the first broken contract and separates it from downstream symptoms.
- **R3:** Separates facts, inferences, hypotheses, and unknowns; keeps a competing explanation.
- **R4:** Recognizes when risk requires a stop, isolation, preservation, or escalation decision.

## Prove

- **P1:** Binds the argument to exact revisions, locations, runs, events, or records.
- **P2:** Supplies a minimal, repeatable counterexample or audit procedure.
- **P3:** Uses independent recomputation or a second evidence path, not an Agent summary alone.
- **P4:** Tests alternatives and calibrates causal direction, magnitude, and uncertainty.

For this rubric, Prove means a reviewable argument for a frozen task. It does not
mean that an entire paper has been proved correct.

## Direct

- **D1:** Decomposes work into bounded Human–Agent delegation contracts.
- **D2:** Defines allowed scope, permissions, budget, acceptance, stop, and escalation conditions.
- **D3:** Independently checks Agent artifacts and retains negative or uncertain outcomes.
- **D4:** Prioritizes checks by risk and information value without silently expanding scope.

## Steward

- **S1:** Makes a named accept, block, narrow, withdraw, or release decision.
- **S2:** Specifies durable repair, regression evidence, rebaseline, and prevention controls.
- **S3:** Preserves incident evidence and communicates separately to technical and other stakeholders.
- **S4:** Leaves transferable provenance, residual risk, ownership, and revisit conditions.

## Review-record consistency

A declared `pass` for L1–L4 must mark Recognize and Prove as `demonstrated`. A
declared capstone `pass` must mark all four bands as `demonstrated`. The CLI checks
only this internal consistency; it does not produce or verify the judgment.
