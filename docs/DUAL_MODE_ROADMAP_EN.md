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
| Phase 2: learner progress, human rubric, and capstone | **Complete** | P1 | Mechanical scoring, answer leakage, overstated learning gains |
| Phase 3: Demo export and Blind Challenge split packages | **3A local tooling complete; 3B controlled operation pending** | P2 | Pseudo-blinding, missing access control, licensing and measurement-validity failures |
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
| Acceptance criteria | A temporary Git fixture completes “init → complete templates/lint → G0 approve/preflight → finding/evidence → legal `verified`/`closed` transition → verify/report.” `audit init` requires an existing immediate parent and exclusive writes through pinned parent/new-directory descriptors; `report build` pins workspace identity, refuses overwrite, and emits `0600` on POSIX. Path-replacement tests prove neither writes into a redirect target. Tests also preserve target `HEAD`, worktree state, and tracked bytes; Audit executes no project code, uses no network, reads no isolated answers by default, and issues no scientific verdict |
| Non-goals | Letting an agent define the question, run arbitrary scripts, repair the original project directly, approve release automatically, or give an unsupported correctness verdict |
| Dependencies | Stable CLI schema, public templates, project-read-only/external-workspace policy, local hash-chain lifecycle, temporary Git E2E test, and human-review rules |
| Exit condition | **Met.** The standard-library CLI has completed the stated loop in a fresh temporary clean-Git directory; tests confirm that fixture's target `HEAD`, worktree status, and tracked file remain unchanged, and docs state every command’s authority and boundary |

**Risk control:** Audit commands only read the target project or record local audit material; preflight does not grant execution authority. With incomplete G0 or no current `approved` gate, the tool refuses the next action or returns `needs-human-decision`, rather than guessing.

## Phase 2: learner progress, human rubric, and cross-level capstone (complete)

**Purpose:** turn “ran an exercise” into observable capability growth without treating a guessed answer or automated score as research judgment.

| Item | Content |
| --- | --- |
| Concrete deliverables | `train progress init/status/check/submit/review/export`; a learner workspace outside the repository with one atomically updated `progress.json`; L1–L4 Evidence Passport and capstone worksheets; a human Recognize / Prove / Direct / Steward rubric; immutable submission snapshots, retry links, multi-reviewer feedback, and redacted Markdown/JSON export |
| Implemented loop | `progress init` → edit a worksheet → `check` structure → `submit` a frozen attempt → `review` with a named human judgment → retry from explicit evidence gaps → resume offline with `status` → create a non-overwriting redacted `export`. The editable draft, latest frozen attempt, and history remain distinct |
| Acceptance criteria | Progress pauses and resumes offline; status separates worksheet structure, attempt state, human review, and unassessed scientific correctness; reviewer differences are not averaged; the capstone requires G0, triage, delegation, blast radius, claim boundary, remediation, and stakeholder communication; the public workflow neither reads nor exports answer mappings |
| Non-goals | Global leaderboard, judging research ability from a candidate letter, claiming learning impact from one completion, or putting hidden answers in a client-side scorer |
| Dependencies | Phase 1 common artifacts and schemas; versioned human rubric; public synthetic incident; answer-isolation and review design; standard-library atomic writes and a local exclusive lock |
| Exit condition | **Met.** A learner can complete, pause, resume, and export an evidence record locally; the system retains each reviewer's rubric observations, decision, and gap explanation so humans can explain disagreement; the capstone passes only through an explicit named human `pass` with all four observations declared `demonstrated` |

**Risk control:** the CLI checks sections, content, and unresolved prompts only; it never infers meaning, scientific correctness, or maturity. Digests and atomic replacement in `progress.json` provide local consistency, not identity authentication or external immutability. The current case remains `open-demo-honor-isolation`. Do not claim the curriculum improves real research quality without preregistered evidence. See the [Mode Train guide](TRAIN_MODE_EN.md) for exact commands.

## Phase 3: Open Demo export and true Blind Challenge split packages (partially complete)

**Purpose:** support honest public teaching releases and establish proper package boundaries for a future controlled blind assessment.

| Item | Content |
| --- | --- |
| Phase 3A: local tooling (complete) | `export open-demo --output NEW_DIR --actor LABEL [--run-public-checks]` creates a self-verifiable frozen snapshot of the current LLM4SBR Open Demo; `export verify BUNDLE [--json]` checks its exact root/payload and byte-compares the trusted verifier/boundary from a trusted checkout. `package blind --manifest ... --challenge-source ... --evaluator-source ... --maintainer-source ... --output NEW_PRIVATE_STAGING --actor LABEL` creates private `0700` staging; `package verify STAGING [--json]` checks all three packages, exact source inventories, executable bits, BUILD_RECORD, bounded leakage rules, and private POSIX modes |
| 3A acceptance criteria | Open Demo and Blind outputs remain outside public Git, name nonexistent targets, and have existing immediate parents. The Blind manifest and three sources also remain outside public Git; the sources are distinct and pairwise non-nested, and the Blind output neither contains nor is contained by any source. On POSIX, the manifest/immediate parent have no group/other permission bits. Strict JSON rejects floats, duplicate/unknown fields, and Boolean integer substitutes; versions use strict SemVer, timestamps use canonical UTC RFC 3339 `YYYY-MM-DDTHH:MM:SS[.fraction]Z`, and template placeholders fail closed. Each role's non-generated payload exactly equals `source_inventory`; BUILD_RECORD binds tool-revision scope/worktree state and packager/verifier digests. After normal assembly, all three roles pass standalone verification from their own roots without reading siblings, and fail closed on capacity, unreadable directories, symlinks/special files, and protected paths. Repository-side trust verification is coupled to the corresponding tool revision, so an old package must be checked with its recorded tool version after trusted bytes change. Challenge excludes controlled mappings/digests/metadata; staging stays `assembled-awaiting-controlled-placement`, and mode checks never masquerade as ACLs |
| Phase 3B: controlled operation (pending) | Provide separate private evaluator/maintainer storage, least privilege, access records, frozen scoring rules, license review, independent evaluator, controlled execution, human leakage review, named release sign-off, and a leakage invalidation/withdrawal drill for a new never-public case |
| Non-goals | Calling current LLM4SBR or any already public case an “unseen” blind task after recompressing, encrypting, or moving directories; treating a local packager as access control, confidentiality, or measurement-validity proof |
| Dependencies | 3A is covered by standard-library local tooling and synthetic tests; 3B still depends on independent private evaluation storage, least privilege, access records, frozen scoring rules, license review, independent evaluator, and leakage-invalidation process |
| Overall exit condition | **Not met.** A newly created, never-public case must complete split packaging, human leakage review, independent grading, and a leakage drill in a controlled environment; current public LLM4SBR remains explicitly Open Demo |

**Key fact:** a historically public task does not become unseen by repackaging it. A true Blind Challenge needs a new, never-public case and operational capacity to protect it; local packaging and `package verify` can enforce file, digest, exact-package, and current POSIX-mode contracts only. They cannot validate ACLs, recover leaked information, or replace human operational gates. Completing Phase 3A local tooling does not change the fact that Phase 3B—and Phase 3 overall—remain incomplete. See the [case release model](CASE_RELEASE_MODEL_EN.md).

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
