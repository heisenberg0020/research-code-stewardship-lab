# RCSL Dual-Mode Roadmap

**Goal:** let RCSL support both repeatable capability training (**Mode Train**) and bounded real research audits (**Mode Audit**) without presenting an automated structural check as scientific judgment or repackaging an already public case as an “unseen” blind task.

[中文](DUAL_MODE_ROADMAP.md) · [Competency model](COMPETENCY_MODEL_EN.md) · [Case release model](CASE_RELEASE_MODEL_EN.md)

## Invariants

1. **Local first:** CLI plus Markdown/JSON are the authoritative interface; any future UI is only an optional view of the same model.
2. **Standard-library first:** core navigation, templates, schemas, and package checks use the Python standard library by default; heavy runtimes remain optional.
3. **Original projects are read-only:** audit commands do not modify papers, source, data, or existing results by default; new artifacts write only to a user-specified output directory.
4. **Human final decision:** an agent may gather, run bounded checks, and draft; a human freezes G0, approves authority, interprets evidence, permits claims, and closes incidents.
5. **Structure is not science:** `PASS` only means that a given version passed a structural, format, or bounded-runtime contract. It does not prove paper fidelity, experimental fairness, security, or a true conclusion.

## Two modes and one common kernel

| Item | Mode Train | Mode Audit |
| --- | --- | --- |
| Purpose | Practice finding research errors that run but should not be trusted in prepared cases | Form an auditable judgment about papers, source, experiments, and agent actions within user-authorized scope |
| Inputs | Versioned case, public brief, learner worksheet, public checks | User-supplied research contract, read-only sources, permitted scope, output directory, approval rules |
| Outputs | Evidence Passport, progress record, capstone deliverable | Research Contract, Triage Card, Evidence Passport, named G0 gate decision, local lifecycle ledger, and review report |
| Human role | Reason independently within the rules, retain evidence, accept or request feedback | Freeze G0, set authority and risk boundaries, approve runs and final conclusion |
| Does not promise | A real blind assessment or automatic grading equal to scientific correctness | An unattended audit, automatic publication, or automatic changes to the original project |

Both modes reuse the same **common kernel**:

```text
G0 Research Contract / Case Manifest
→ Triage Card + Delegation Contract
→ Evidence Passport (location · contract · command/artifact · causal effect · boundary)
→ named G0 gate decision + local lifecycle ledger
→ rendered Markdown/JSON review report with project baseline, G0, finding/evidence summary, and known limits
```

The vertical axis always classifies by the **first failed contract**: L1 semantics, L2 pipeline, L3 scientific validity, or L4 agent governance. The seven accountable capabilities and four maturity bands are defined in the [competency model](COMPETENCY_MODEL_EN.md).

## Priority overview

| Phase | Status | Priority | Main risk |
| --- | --- | --- | --- |
| Phase 0: current baseline | **Complete** | P0 | A public case is mistaken for a blind task or scientific certification |
| Phase 1: explicit Train/Audit and real closed loop | **Completed this turn** | P0 | Unauthorized default writes/execution, or tool output mistaken for a conclusion |
| Phase 2: learner progress, scoring, and capstone | Planned | P1 | Mechanical scoring, answer leakage, overstated learning gains |
| Phase 3: Demo export and Blind Challenge split packages | Planned | P2 | Pseudo-blinding, missing access control, licensing and measurement-validity failures |
| Phase 4: optional UI/registry/integrations | Optional | P3 | Premature platform work, privacy/lock-in, CLI/UI semantic drift |

---

## Phase 0: current baseline (complete)

**Purpose:** provide an honest, runnable public training starting point.

| Item | Content |
| --- | --- |
| Existing deliverables | L1–L4 training package; G0/competency/release-model documents; source-blind paper-study protocol; public navigation, environment diagnosis, and public-check entry points; CI and public validation record |
| Acceptance criteria | Public Level 1–4 checks run in a supported environment; documentation explains first failed contract, answer-isolation boundary, and limits of `public PASS`; public entry points do not depend on instructor material |
| Non-goals | Calling LLM4SBR or any currently public case an unseen task, confidential exam, production security audit, or proof of paper reproduction |
| Dependencies | Existing training package, Python environment, public sources, and human maintenance |
| Exit condition | **Already met.** Later features must preserve these boundaries rather than weaken transparency for a smoother experience |

## Phase 1: explicit Train/Audit commands and real audit closed loop (completed this turn)

**Purpose:** let users know from the first command whether they are training or auditing a real project, and give Audit a full loop from G0 to a human decision.

| Item | Content |
| --- | --- |
| Concrete deliverables | Explicit command families: `rcsl train overview`, `rcsl train doctor`, `rcsl train start --level 1..4`, and `rcsl train validate`; plus `rcsl audit init`, `status`, `lint`, `gate check`, `gate record`, `preflight`, `rebaseline`, `finding add/list/transition`, `evidence add`, `verify`, and `report build`. The four local templates are `research-contract-template.md`, `evidence-passport-template.md`, `triage-card-template.md`, and `delegation-contract-template.md`; an audit workspace outside the project is written only through `--output`; a temporary clean-Git E2E test |
| Closed loop | `audit init` binds a clean `HEAD` and creates G0 `draft` → a human completes the research contract and remaining templates → `audit lint` → `audit gate record --decision approved` → `audit preflight` → findings/evidence with reasoned transitions → `audit verify` and a local Markdown/JSON review report |
| Acceptance criteria | A temporary Git fixture completes “init → complete templates/lint → G0 approve/preflight → finding/evidence → legal `verified`/`closed` transition → verify/report”; a test confirms that fixture's target `HEAD`, worktree status, and tracked file remain unchanged; Audit never executes the project, uses the network, or reads isolated answers by default; lint, verify, and report state clearly that they are not scientific judgments |
| Non-goals | Letting an agent define the question, run arbitrary scripts, repair the original project directly, approve release automatically, or give an unsupported correctness verdict |
| Dependencies | Stable CLI schema, public templates, project-read-only/external-workspace policy, local hash-chain lifecycle, temporary Git E2E test, and human-review rules |
| Exit condition | **Met.** The standard-library CLI has completed the stated loop in a fresh temporary clean-Git directory; tests confirm that fixture's target `HEAD`, worktree status, and tracked file remain unchanged, and docs state every command’s authority and boundary |

**Risk control:** Audit commands only read the target project or record local audit material; preflight does not grant execution authority. With incomplete G0 or no current `approved` gate, the tool refuses the next action or returns `needs-human-decision`, rather than guessing.

## Phase 2: learner progress, scoring, and cross-level capstone

**Purpose:** turn “ran an exercise” into observable capability growth without treating a guessed answer or automated score as research judgment.

| Item | Content |
| --- | --- |
| Concrete deliverables | Local `progress.json` and readable progress summary; Recognize / Prove / Direct / Steward rubric; completeness checks for each Evidence Passport; cross-L1–L4 research-incident capstone; human feedback and retry record |
| Acceptance criteria | Progress resumes offline; scoring exposes evidence gaps rather than only a number; capstone requires triage, delegation, blast radius, claim boundary, and stakeholder communication; public checks do not expose answer mappings |
| Non-goals | Global leaderboard, judging research ability from a candidate letter, claiming learning impact from one completion, or putting hidden answers in a client-side scorer |
| Dependencies | Phase 1 common artifacts and schemas; clear human rubric; licensed cases/synthetic incidents; answer-isolation and review design |
| Exit condition | A learner can complete, pause, resume, and export their evidence record locally; two reviewers can explain a scoring difference with the rubric; the capstone has an explicit human pass gate |

**Risk control:** show “structural-completeness score,” “human scientific judgment,” and “still uncertain” separately. Do not claim the curriculum improves real research quality without preregistered evidence.

## Phase 3: Open Demo export and true Blind Challenge split packages

**Purpose:** support honest public teaching releases and establish proper package boundaries for a future controlled blind assessment.

| Item | Content |
| --- | --- |
| Concrete deliverables | `rcsl export open-demo` exports provenance, version, license, known limits, and public validation record; `rcsl package blind` creates a Challenge Package, controlled Evaluator Package, and controlled Maintainer Record from the outset; manifests, checksums, leakage scan, and revocation template |
| Acceptance criteria | Open Demo visibly says it is not security isolation; a synthetic fixture’s Challenge Package excludes answer mappings, private probes, and evaluation labels; Evaluator Package grades in an independent controlled environment; every package has traceable version and provenance |
| Non-goals | Calling current LLM4SBR or any already public case an “unseen” blind task after recompressing, encrypting, or moving directories; treating a local packager as access control, confidentiality, or measurement-validity proof |
| Dependencies | Independent private evaluator storage, least privilege, access records, frozen scoring rules, license review, independent evaluator, and leakage-invalidation process |
| Exit condition | A newly created, never-public case completes split packaging, leakage review, independent grading, and a leakage drill in a controlled environment; current public cases remain explicitly Open Demo |

**Key fact:** a historically public task does not become unseen by repackaging it. A true Blind Challenge needs new, never-public cases and operational capacity to protect them; a packager can enforce boundaries but cannot recover information already leaked.

## Phase 4: optional Web UI, registry, and integrations

**Purpose:** after the common kernel is stable, reduce navigation cost and improve case discovery without turning RCSL into a centralized-service dependency.

| Item | Content |
| --- | --- |
| Concrete deliverables | Optional local/static Web view; Case Registry (provenance, version, mode, license, known limits); editor/CI/learning-platform integrations; Evidence Passport viewer rendered from the same Markdown/JSON schema |
| Acceptance criteria | All Train/Audit work remains possible without Web; UI and CLI produce the same schema; no source, data, answers, or identity is uploaded by default; registry distinguishes Open Demo from controlled Blind Challenge |
| Non-goals | Forced login, uploading private research material to a central service, replacing human approval with UI, or inferring scientific correctness from integration status |
| Dependencies | Stable Phase 1 schema and CLI; privacy/security/accessibility review; clear governance, hosting, and maintenance ownership |
| Exit condition | The UI is a replaceable view layer: closing it or working offline never loses cases, evidence, or human decisions; every mode still imports/exports through the local CLI |

**Risk control:** begin with static or local views. Consider a hosted registry or third-party integration only after real cross-device collaboration demand and governance are established.

## Decision gates

| When | Question that must be answered |
| --- | --- |
| Entering Audit | Is the original project a clean Git worktree? Is the workspace outside it and nonexistent? Does G0 begin as `draft` for later human completion and review? |
| Allowing execution | Audit itself never executes the project. If code execution, network access, protected material, source changes, or more budget are needed, is there a separate explicitly authorized tool flow? |
| Forming a conclusion | Does the Evidence Passport distinguish facts, inferences, assumptions, unknowns, and permitted claims? |
| Releasing a case | Is it an Open Demo or a Blind Challenge? Does the statement honestly match the controls? |
| Adding UI/integration | Can all evidence and human decisions still be retained locally, offline, and exportably? |
