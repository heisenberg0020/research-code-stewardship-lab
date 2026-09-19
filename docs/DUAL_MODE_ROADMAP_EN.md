# Research Code Stewardship Lab: Roadmap after scope closure

[中文](DUAL_MODE_ROADMAP.md) · [Project charter](PROJECT_CHARTER_EN.md) · [Competency model](COMPETENCY_MODEL_EN.md) · [Case release model](CASE_RELEASE_MODEL_EN.md)

## Goal and boundary

RCSL retains only two core user outcomes:

- **Mode Audit** helps an accountable owner audit real research code and preserve traceable evidence and human decisions.
- **Mode Train** develops the human ability to recognize, prove, and handle research-code risks in the coding-agent era.

`export` and `package` are case-release utilities, not a third mode. Presentation, hosting, and other integrations will be reconsidered only after the core workflows have completed real pilots.

## Anti-drift rule

This section summarizes the [project charter](PROJECT_CHARTER_EN.md) for the roadmap. If a phase plan conflicts with the charter, the charter governs.

The repository began as a four-level audit-training project. It later deliberately added a second outcome: helping an owner audit real research code and manage its evidence. That intentional dual-mode expansion is not a mandate to become a general security, publishing, or presentation platform.

A new capability may enter the core only when it directly improves at least one of these user loops:

1. an audit owner can locate, preserve, review, or hand off evidence and human decisions for a real project more accurately; or
2. a learner and an independent reviewer can complete judgment, proof, feedback, and retry against the same frozen material.

More tests, filesystem defenses, pages, registries, integrations, or “platform feel” are not sufficient reasons unless they remove an observed blocker in one of those loops. General authorization, defense against a malicious same-privilege local process, remote operations, and hosted services require a separately owned deployment boundary.

## Status terms must remain distinct

| Status | Meaning | It does not establish |
| --- | --- | --- |
| `implemented` | The corresponding code, command, or document exists | Correct design, usability, or safety |
| `internally verified` | Automated tests and controlled synthetic scenarios pass | Successful use by real projects or learners |
| `field validated` | External real users completed an end-to-end task in a real setting, with retained observations | Production-grade security, recovery, or operations |
| `production ready` | Threat model, identity and access, recovery, migration, monitoring, governance, and maintenance ownership are closed | Guarantees outside the declared deployment boundary |

The roadmap no longer uses an unqualified “complete.” Every milestone must identify which status it has reached.

## Honest current baseline

| Work surface | Implemented | Internally verified | Field validated | Production ready | Current judgment |
| --- | --- | --- | --- | --- | --- |
| Four-level public training case | Yes | Yes | No | No | Usable as an experimental public curriculum; no learning-effectiveness claim |
| Phase 1 Audit lifecycle | Yes | Yes | No | No | Alpha; core boundaries and recovery still need closure |
| Phase 2 Training progress | Yes | Yes | No | No | Experimental; reviewer-object and case-version binding remain incomplete |
| Phase 3A local release/packaging | Yes | Yes | No | No | Verifies local file and package contracts only |
| Phase 3B controlled Blind operation | No | No | No | No | Depends on a real private case, people, and infrastructure; stop expanding local code |
| Phase 4 presentation, registry, and hosting | No | Not applicable | No | No | Pruned from the active product and deferred |

Passing tests supports only `internally verified`. It does not prove scientific correctness, learning gains, successful independent audit, or production safety.

## Phase 1: close Audit core risks first

**Current status:** `implemented` and `internally verified`; not `field validated`.

Retained essentials are clean-Git baselines, external workspaces, G0, finding/evidence lifecycle, the local event chain, preflight, rebaseline, verification, and human-review reports.

Risks that must close first:

1. Revalidate on every read and write that the workspace remains outside the target project; initialization-only checking is insufficient.
2. Give G0 one authoritative decision source so template text and machine state cannot contradict each other.
3. Make multi-file mutation atomic or provide an explicit and tested recovery procedure.
4. Enforce size and capacity limits before writing so a successful mutation cannot create an unverifiable workspace.
5. Status words now use scoped terms such as `g0-prerequisites-met`, `preflight-passed`, `local-records-consistent`, and `preflight-current`, avoiding confusion between process state and audit completion.

**Next exit gate:** regression tests cover every item above and a fresh temporary project completes a failure-recovery scenario. This still raises only internal confidence.

## Phase 2: ensure humans review the frozen object

**Current status:** `implemented` and `internally verified`; not `field validated`.

Retained essentials are external learning workspaces, structural checks, immutable attempts, multiple reviewer records, retry relationships, the four-band human rubric, capstone, and redacted export.

Closure targets:

1. Provide `attempt show` or a reviewer packet so a reviewer sees the exact frozen response bound by the system.
2. Content-bind the complete learner-visible case instead of recording only repository `HEAD`.
3. Merge competing answer surfaces and make the workspace worksheet the sole submit-able entry.
4. Give the capstone inspectable diffs, logs, configurations, approvals, or ledger artifacts rather than only a narrative.
5. Preserve the human-judgment boundary; structural checks must not infer correctness or maturity.

**Next exit gate:** an independent reviewer can accurately assess a named attempt using only the reviewer packet, and any case-material change explicitly invalidates the case binding.

## Phase 3: retain release contracts and stop simulating operations

### 3A local tooling

**Current status:** `implemented` and `internally verified`.

Retain Open Demo export, strict manifests and checksums, local three-role staging, and standalone verification. They establish only consistency between retained bytes and declared package contracts. They provide no ACL, authenticated identity, confidentiality, independent evaluation, or scientific conclusion.

### 3B controlled operation

**Current status:** not `implemented`, and further local code must not be presented as operational completion.

Resume only when all external prerequisites exist: a new never-public case, separate private storage, least privilege, access records, frozen scoring, an independent evaluator, controlled execution, human leakage review, named release sign-off, and a withdrawal drill.

Experimental readiness work must not enter the core baseline unless it directly serves a confirmed real pilot.

## Phase 4: pruned and deferred

The earlier offline presentation prototype passed internal contract tests, but it had no evidence of real user demand and could place material without a shared subject/case binding on the same page. It added substantial duplicate schema, filesystem hardening, and maintenance cost without closing the Audit or Training journey.

The active product therefore contains no presentation, Registry, Dashboard, or hosted layer. Git history retains the design process. Reopening this work requires all of the following:

1. a stable shared subject/case/artifact identity model;
2. at least one real Audit pilot and one real Training pilot;
3. user research showing that presentation or collaboration is an actual blocker; and
4. named ownership for privacy, permissions, accessibility, deployment, and maintenance.

## New execution order

Work no longer advances by adding more phases. It advances by closing user journeys and risks:

1. **Prune and freeze the baseline:** remove the old training tree, legacy top-level aliases, and unvalidated presentation surface; keep documentation, CLI, tests, and CI aligned.
2. **Audit Core Closure:** close Phase 1 workspace-boundary, single-source G0, transactional recovery, and pre-write capacity issues.
3. **Unify identity and evidence:** define `subject → case → artifact → evidence → decision → review`, content-address every record, and support schema migration.
4. **Acquire Audit evidence:** import evidence with digests, commands, exit status, environment, and provenance instead of retaining only free-text references.
5. **Close the Training reviewer flow:** deliver reviewer packets, a complete case manifest, and an artifact-rich capstone.
6. **Run a real public Audit pilot:** audit one public research repository, have a second person review from exported material alone, and record completion time, blockers, and attribution errors.
7. **Run a real learner/reviewer pilot:** observe whether users can localize, prove, and communicate faults; never infer learning gains from a single completion.
8. **Conditionally resume Phase 3B:** begin only when a real private case, independent people, and infrastructure exist.
9. **Re-evaluate Phase 4:** design the smallest presentation surface only from navigation or collaboration problems observed in pilots.

No step advances automatically to `field validated` or `production ready` because its test count increased.

## Decision gates before the next step

| Decision | Required question |
| --- | --- |
| Change the Audit schema | Can an old workspace be recognized, migrated, or explicitly rejected? How is failure recovered? |
| Record evidence | Is it bound to real artifact bytes, generation method, environment, and responsible party rather than only prose? |
| Record a human review | Did the reviewer see the exact frozen object being signed? Is identity merely a label or an authenticated principal? |
| Claim field validity | Is there a real project, real participants, retained observation, and documented failure cases? |
| Release a Blind Challenge | Do never-public provenance, private storage, least privilege, independent evaluation, and a withdrawal drill actually exist? |
| Build UI or hosting | Is the core schema stable? Do pilots show this is the most important blocker? Who owns privacy, security, and operations? |

The next meaningful milestone is not another feature. It is one real Audit that a second person can independently review.
