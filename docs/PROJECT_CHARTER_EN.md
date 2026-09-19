# RCSL Project Charter: Human Judgment, Evidence, and Responsibility

[中文](PROJECT_CHARTER.md) · [Competency model](COMPETENCY_MODEL_EN.md) · [Converged roadmap](DUAL_MODE_ROADMAP_EN.md)

## Why we exist

Research Code Stewardship Lab does not exist to help a person or an Agent produce runnable code faster. It exists to train and support human judgment: whether an implementation remains faithful to the research question, whether an experiment is fair, whether evidence supports a claim, and whether an Agent stayed within approved boundaries.

The repository later deliberately formed two core loops without changing that center of responsibility:

1. **Mode Audit** helps a research owner audit real research code and preserve reviewable evidence and human decisions.
2. **Mode Train** lets a learner and an independent reviewer practice recognizing, proving, handling, and communicating risk against the same frozen material.

Release tooling, packaging, pages, registries, hosting, and integrations may only support those loops. They must not become a third product axis.

## Enduring credo

> **Runnable is not trustworthy. Agents may execute; humans must judge. Claims must return to evidence, and status language must not exceed its assurance. Close the loop before building the platform; pilot before expanding; prune before adding.**

1. **Humans retain final responsibility.** Agents may search, implement, check, and organize. A named human must decide research scope, risk acceptance, evidence sufficiency, publication, and when to stop.
2. **Research fidelity outranks superficial executability.** Passing tests, successful execution, or internally consistent records do not replace judgment about algorithm semantics, pipeline integrity, scientific validity, or Agent governance.
3. **Evidence precedes status.** A finding, review, or decision must bind the case, artifact, or attempt the reviewer actually saw. A free-text reference must never masquerade as content evidence.
4. **The reviewed object must be shared and frozen.** Learners, reviewers, and audit owners must be able to establish that they are discussing the same version, bytes, and human decision.
5. **Automation states only its real boundary.** Structure checks, a local hash chain, preflight, and declared `verified` / `closed` states must not be described as scientific proof, identity authentication, or independent reproduction.
6. **L1–L4 locate failure layers; they are not the whole human capability model.** G0, research judgment, rapid triage, delegation and Agent assurance, architecture stewardship, security/privacy/ethics, incident response, and evidence communication complete the framework. The system does not automatically score those judgments.
7. **Default to least authority and least exposure.** Work locally, accept explicit inputs, and require clear authorization. Do not implicitly execute a project, use the network, open protected material, or collect data unrelated to the current decision.
8. **Real use precedes product expansion.** Synthetic tests support only `internally verified`. Without a real project, real people, observation notes, and failure cases, the project cannot claim `field validated` or justify new surfaces merely for “platform feel.”
9. **Complexity must repay a user.** Every schema layer, lock, release contract, or defense must remove an observed core blocker. General authentication, hosting, remote operations, and defense against a malicious same-privilege process require a separate deployment boundary and owner.
10. **Deletability is a design requirement.** Every capability must state non-goals, exit conditions, and maintenance ownership. If it stops serving a core loop, freeze, extract, or remove it rather than sustaining it with more compatibility layers.

## Anti-drift gate before any work begins

Every issue, plan, pull request, or Agent task must first answer:

1. Which core user does it directly serve: an Audit owner, or a Training learner/reviewer?
2. Which observed blocker does it remove, and what is the evidence?
3. How does it strengthen rather than replace human judgment, review, or responsibility?
4. Which real objects and bytes does it bind, and which parts remain declarations?
5. What is the smallest deliverable slice, and what is explicitly out of scope?
6. Can success establish only `implemented`, `internally verified`, `field validated`, or `production ready`, and why?
7. If a pilot shows no value, when is it frozen or removed, and who maintains it?

If questions 1–5 do not have clear answers, the work must not enter the core. More tests, pages, registries, integrations, generic abstractions, or defense layers are not sufficient reasons by themselves.

## Current long-term sequence

1. Close Audit gaps in G0, workspace boundaries, failure recovery, and honest status language.
2. Bind Audit cases and evidence to real Git revisions, contracts, and artifact bytes.
3. Bind Training cases, attempts, rubrics, and reviewer packets to the same frozen material.
4. Complete one real Audit that a second person can independently review.
5. Complete one real learner–independent-reviewer pilot.
6. Use blockers observed in those pilots—and only those blockers—to decide whether Phase 3B or Phase 4 should resume.

Until both kinds of real pilot are complete, Phase 3A is maintenance-only; Phase 3B, presentation, dashboards, registries, and hosting remain frozen.

## Stop conditions

Stop implementation and re-examine direction when any of the following is true:

- the capability does not directly improve either core loop;
- an automated status begins replacing human judgment about evidence sufficiency or scientific claims;
- supporting-module complexity again exceeds the core workflow it serves;
- a remote service, authentication layer, database, UI, or generic plugin system is introduced for a hypothetical future need;
- synthetic tests are used to claim real training effectiveness, real audit success, or production security; or
- work would read, distribute, or infer protected material without new explicit authorization and ownership.

This charter outranks phase numbering and existing roadmaps. The route may change; human judgment, reviewable evidence, and final responsibility may not.
