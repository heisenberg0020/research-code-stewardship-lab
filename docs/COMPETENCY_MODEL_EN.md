# Modern Research Programmer Competency Model

This model gives RCSL two complementary dimensions: the **vertical axis classifies the first research contract that failed**; the **horizontal axis trains how a human uses agents and evidence responsibly**. It does not turn every capability into another sequential level.

[中文](COMPETENCY_MODEL.md) · [Case release model](CASE_RELEASE_MODEL_EN.md) · [Four-level framework](../skills/research-code-audit-training/references/four-level-framework.md)

## Apply the model to your own project

From the repository root, create a local evidence workspace that does not modify the target project:

```bash
python scripts/rcsl.py init-audit --level 1 --output my-audit
```

Then complete the [G0 research contract](../skills/research-code-audit-training/assets/research-contract-template.md), [rapid triage card](../skills/research-code-audit-training/assets/triage-card-template.md), [human–agent delegation contract](../skills/research-code-audit-training/assets/delegation-contract-template.md), and [evidence passport](../skills/research-code-audit-training/assets/evidence-passport-template.md). Run `python scripts/rcsl.py status-audit my-audit` for structural progress and `python scripts/rcsl.py lint-audit my-audit` for unresolved prompts. Neither command judges scientific correctness.

## G0: research-contract gate (before every level)

G0 is not a “Level 0” exercise and does not rank candidates. It is a gate that a human research owner must pass before reading, generating, running, or comparing candidates. Freeze the following first.

| What must be frozen | Minimum deliverable |
| --- | --- |
| Research question, permitted claims, and prohibited extrapolation | A `claim charter`: question, objective, boundaries, success and stop conditions |
| Provenance and permitted scope of papers, source, data, and third-party material | Source inventory, allowed read/write paths, protected-material inventory |
| Splits, metrics, baselines, budget, and statistical unit | Auditable experimental protocol and invariants |
| What an agent may or may not do, and when it must stop for approval | Delegation contract, permission/budget matrix, escalation conditions |
| Privacy, security, ethics, and publication risk | Risk register, owner, handling, and disclosure rules |

If G0 is incomplete, the correct action is to **pause and request clarification**, not let an agent invent research facts from defaults.

## Vertical axis: classify by the first failed contract

One fault can have downstream effects at several layers, but it belongs to the first contract it breaks. The four levels therefore remain a clear, reusable evidence-depth axis rather than four isolated topics.

| Axis | First failed contract | Question a human must answer | Preferred evidence |
| --- | --- | --- | --- |
| **L1 Algorithm semantics** | Formula, operator, index, mask, loss, or gradient | Does runnable code still implement the paper’s definition? | Property test, minimal tensor, gradient probe |
| **L2 Pipeline integrity** | Data identity, state, split, evaluation, or checkpoint flow | Does this sample/state/metric lineage stay consistent? | Cross-artifact lineage, independent recomputation, event order |
| **L3 Scientific validity** | Comparison design, evidence, or claim scope | Is this comparison fair, and how strong a claim does the evidence permit? | Configuration comparison, ledger reconstruction, frozen analysis rule |
| **L4 Agent experiment governance** | Authorization, approval, budget, record, or protected evidence | Was the action authorized and traceable? | Timeline, approval chain, resource ledger, report audit |

## Horizontal axis: seven accountable capabilities

“Human responsibility” below cannot be silently delegated. An agent may assist with execution and propose options, but cannot replace final accountability.

| Capability | Human responsibility | What an agent may assist with under a clear contract | Evidence to retain |
| --- | --- | --- | --- |
| **C1 Research judgment** | Define the question, acceptable risk, permitted claim, and final conclusion | Align paper and code; enumerate conflicts and unknowns | Research contract, claim card |
| **C2 Rapid triage** | Decide to stop, contain, escalate, continue under constraints, or mark unknown | Reproduce symptoms, summarize logs, run bounded probes | Triage card: severity, blast radius, evidence, next safe action |
| **C3 Delegation & agent assurance** | Set permissions, budget, acceptance criteria, and escalation points; approve consequential changes | Read, implement, test, extract traces, draft reports | Delegation contract and acceptance record |
| **C4 Architecture & maintainability** | Choose boundaries, interfaces, lineage, rollback, and ownership | Scaffold modules, generate docs/tests, suggest refactors | Architecture decision record, runbook, change history |
| **C5 Security, privacy & ethics** | Decide data rights, disclosure, risk acceptance, and exception approval | Scan secrets/dependencies, identify untrusted input, generate threat hypotheses | Safety case: assets, trust zones, risks, mitigations, stop rules |
| **C6 Incident response** | Declare an incident, pause release, notify, remediate, and close it | Preserve logs, snapshot, reproduce, draft postmortem | Incident ledger, blast radius, postmortem, prevention verification |
| **C7 Evidence communication** | Decide what to say to whom, with what confidence and claim wording | Draft summaries/figures, trace citations, translate technical material | Decision memo: fact / inference / assumption / recommendation / unknown |

### A triage loop for every level

```text
Detect → Contain → Establish blast radius → Gather minimum decisive evidence
→ Delegate or escalate within explicit limits → Communicate decision and next check
```

Security, privacy, and ethics are a **stop-the-line overlay**, not a closing topic saved for L4. Even before an algorithm fault is proven, sensitive-data exposure, unclear licensing, protected-evaluation leakage, or unsafe external action should trigger the G0 escalation condition.

## Four maturity bands

Maturity describes depth within a capability; it does not create new Levels. A learner can be `Prove` at L1 but still be `Recognize` at L3.

| Band | Observable behavior | Minimum evidence |
| --- | --- | --- |
| **Recognize** | Spots a risk or failed contract in a given scope and states uncertainty | Correct source citation and checklist use |
| **Prove** | Independently constructs a minimal counterexample or reproducible evidence chain | Location, contract, command/artifact, causal effect |
| **Direct** | Splits work for agents, bounds authority, and reviews whether output meets acceptance criteria | Delegation contract, review record, escalation decision |
| **Steward** | Accepts final responsibility for risk, release, claim, and incident closure | Approve/block decision, boundary statement, stakeholder record |

## Three role tracks

Tracks are suggested practice routes. They do not replace the vertical axis or imply that the other capabilities are unimportant.

| Track | For | Recommended emphasis | Typical output |
| --- | --- | --- | --- |
| **Audit practitioner** | Graduate students, research programmers, review collaborators | G0 + L1–L4; C1, C2, C7 | One Evidence Passport per level: location, rule, counterexample, impact, repair |
| **Research systems maintainer** | People maintaining data, training, and evaluation systems | G0, L1–L2; C2, C3, C4, C5, C6 | Lineage graph, runbook, triage card, incident postmortem |
| **Research owner / agent supervisor** | PIs, senior researchers, research-engineering leads | G0, L3–L4; C1, C3, C5, C6, C7 | Research contract, approval record, claim card, decision memo |

## Downstream capstone: a cross-contract research incident

The capstone is not L5. It presents a case with multi-layer consequences: for example, a local semantic deviation (L1) causes state or split contamination (L2), a strong-looking result is overclaimed (L3), and an agent continues outside approved scope (L4).

Learners must:

1. use G0 to decide whether to stop and notify immediately;
2. use the triage loop to preserve evidence, scope impact, and arrange delegation;
3. classify each issue by its **first failed contract**;
4. produce a technical incident report and a concise stakeholder update; and
5. change the protocol, architecture, or runbook and prove that the prevention measure was rechecked.

Passing means an auditable decision and evidence trail—not the best metric or a superficially “fixed” file.

## Relation to the case release model

Current public cases, including answer-related material, are **Open Demo / honor isolation**: learners agree not to look for instructor material until completing the public task and evidence record, but convention-based separation in a public repository is **not a security boundary**. It must not be presented as a blind assessment, confidential exam, or adversarial leakage defense.

When true blinding is required, use the [Blind Challenge split-package recommendation](CASE_RELEASE_MODEL_EN.md). Keep the public package, controlled evaluator package, and maintainer record separate from the outset; do not commit answers to public Git history and try to hide them later.
