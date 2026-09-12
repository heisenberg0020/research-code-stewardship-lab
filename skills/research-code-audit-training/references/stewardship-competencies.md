# Research-code stewardship competency model

## Why this model exists

The four levels classify the **first research contract broken by an artifact**.
They do not, by themselves, describe every capability a modern programmer or
research owner needs. Use two independent axes:

1. the vertical evidence boundary: `G0 → L1 → L2 → L3 → L4 → capstone`;
2. the horizontal human capability used to investigate, decide, delegate, and
   communicate across those boundaries.

Do not turn every horizontal capability into another numbered level. A level
answers “where did trust first fail?” A competency answers “what must the human
be able to do about it?”

## Vertical evidence boundaries

### G0 — Research contract and legitimacy gate

Freeze the question, construct or estimand, target population, allowed claim,
success and stop conditions, source revisions, data rights, licenses, affected
stakeholders, privacy/ethics constraints, protected evidence, budgets, and
human-only decisions before implementation or audit. Block work when a missing
choice would materially change the research meaning or authorization.

G0 is a gate, not a fifth candidate-selection exercise. A technically correct
system cannot repair an illegitimate question, an unlicensed dataset, or an
undefined decision target.

### L1–L4 — First broken contract

- **L1 Algorithm semantics:** formula, tensor, index, loss, or gradient meaning.
- **L2 Pipeline integrity:** identity, lineage, split, state, checkpoint, or
  evaluation flow.
- **L3 Scientific validity:** comparison design, evidence population, inference,
  or claim scope.
- **L4 Agent experiment governance:** authorization, approval, budget, record,
  stopping, or protected-evidence boundary.

Classify a finding at the earliest broken contract even when its consequences
propagate through later levels.

### Capstone — Artifact and lifecycle stewardship

After L1–L4, require the learner to audit a changed or unfamiliar project from
G0 through a release decision. The capstone should include reproducibility on a
clean environment, dependency and provenance review, maintainability and
handoff, incident correction, claim calibration, and a durable evidence bundle.
Use an optional delivery/lifecycle level only for projects that actually deploy
or operate a service; do not force production concerns into every paper exercise.

## Seven cross-level human capabilities

| Capability | Observable human performance | Evidence to require |
| --- | --- | --- |
| Research mandate and judgment | Defines what is being measured, why it matters, what would change a decision, and what cannot be inferred | Approved research contract, assumptions, allowed-claim boundary |
| Rapid triage and localization | Separates cause from symptom, identifies the first failing contract, and chooses the cheapest discriminating check | Triage card, competing hypotheses, minimal reproduction |
| Delegation and agent assurance | Decomposes work, sets permissions and stop gates, and verifies rather than merely accepts an agent report | Delegation contract, checkpoints, independent verification |
| Architecture and maintainability | Preserves explicit interfaces, change boundaries, recovery paths, and transferability to another maintainer | Architecture decision, change-impact map, clean handoff test |
| Security, privacy, and ethics | Models abuse and supply-chain risk, protects secrets and people, and establishes lawful/ethical data use | Threat/data-rights review, dependency provenance, approval record |
| Incident response and correction | Contains damage, preserves evidence, rolls back safely, explains root cause, and prevents recurrence | Incident timeline, causal analysis, corrective tests, correction notice |
| Evidence communication | Connects claims to exact evidence, marks uncertainty, calibrates language, and records accountable decisions | Evidence passport, limitations, reviewer sign-off |

Each exercise need not score all seven equally. It must state which capabilities
are primary, which are secondary, and which are explicitly out of scope.

## Four maturity stages

Assess each capability independently:

1. **Recognize** — identifies a suspicious pattern and the relevant contract.
2. **Prove** — produces a minimal, reproducible evidence chain and rules out a
   plausible alternative.
3. **Direct** — designs checks, delegates bounded work, sets stop conditions, and
   makes an evidence-based accept/block/request-evidence decision.
4. **Steward** — builds durable controls, handles incidents and change over time,
   communicates limitations, and transfers ownership without losing provenance.

Do not infer maturity from a single multiple-choice answer. Require artifacts
and decisions appropriate to the stage.

## Role routes

- **Audit practitioner:** emphasize triage, proof, false-positive control, and
  evidence communication across L1–L4.
- **Research owner:** emphasize G0, scientific judgment, delegation, approvals,
  risk acceptance, and claim sign-off.
- **System maintainer:** emphasize architecture, dependency provenance,
  reproducibility, incident response, lifecycle change, and handoff.

All routes share the same contract vocabulary, so evidence can be handed from
one role to another without translating the meaning of a finding.

## Applying the model to package design

Before generating candidates:

1. complete the research contract template;
2. name the primary capability and target maturity for every task;
3. freeze the first-broken-contract boundary and acceptance evidence;
4. define what an agent may execute and what a human must decide;
5. specify how findings will be captured in evidence passports;
6. include at least one rapid-triage exercise and one cross-level capstone in a
   full curriculum, without weakening the singleton-fault rule inside L1–L4.

Structural completeness is not substantive correctness. A validator may check
that required fields and links exist, but only a qualified reviewer can decide
whether the research question, evidence, ethics, or claim is sound.
