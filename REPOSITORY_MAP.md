# Repository map

This public repository has two explicit operating modes built on one stewardship model. **Mode Train** develops human research-code judgment with the LLM4SBR Open Demo. **Mode Audit** binds an external workspace to a real project's clean Git `HEAD` and records G0, findings, evidence, lifecycle events, and a human-review report. The paper and original implementation remain available from their official sources and are not redistributed here.

Canonical entry points are `python scripts/rcsl.py train ...` and `python scripts/rcsl.py audit ...`. Case maintainers additionally use `python scripts/rcsl.py export ...` and `python scripts/rcsl.py package ...` for release artifacts. These explicit namespaces are the complete active CLI surface; legacy top-level aliases and the unvalidated static-view surface have been pruned.

## Contents

- [LLM4SBR paper](https://arxiv.org/abs/2402.13840): the official paper used as the scientific specification.
- [Original LLM4SBR repository](https://github.com/tsinghua-fib-lab/LLM4SBR): the official implementation source.
- `docs/GETTING_STARTED.md`: Chinese task-oriented start guide for learners, auditors, reviewers, maintainers, and research owners.
- `docs/GETTING_STARTED_EN.md`: English version of the task-oriented start guide.
- `docs/TRAIN_MODE.md`: Chinese command and trust-boundary guide for resumable learning progress, human review, retries, capstone, and export.
- `docs/TRAIN_MODE_EN.md`: English version of the Mode Train progress guide.
- `docs/AUDIT_MODE.md`: Chinese command and boundary guide for the real-project audit lifecycle.
- `docs/AUDIT_MODE_EN.md`: English version of the Mode Audit guide.
- `docs/DUAL_MODE_ROADMAP.md`: Chinese phased implementation plan for the shared Train/Audit system.
- `docs/DUAL_MODE_ROADMAP_EN.md`: English version of the dual-mode roadmap.
- `docs/COMPETENCY_MODEL.md`: Chinese G0 + L1–L4 + seven cross-level capabilities and maturity model.
- `docs/COMPETENCY_MODEL_EN.md`: English version of the competency model.
- `docs/CASE_RELEASE_MODEL.md`: Chinese Open Demo export, Blind staging, package-role, verification, and remaining operational-gate guide.
- `docs/CASE_RELEASE_MODEL_EN.md`: English version of the case release model and tooling guide.
- `docs/images/research-code-stewardship-banner.svg`: the repository’s self-contained Paper → Code → Evidence → Governance banner.
- `requirements.txt`: learner-facing runtime dependency list for local public checks.
- `scripts/rcsl.py`: unified CLI. `train overview|doctor|start|validate` covers course navigation and public checks; `train progress init|status|check|submit|review|export` covers local learning records; `audit init|status|lint|gate|preflight|rebaseline|finding|evidence|verify|report` covers the real-project lifecycle; `export open-demo|verify` and `package blind|verify` cover local release artifacts.
- `stewardship_lab/audit.py`: standard-library audit core for clean-Git binding, G0 gates, structured findings/evidence, allowed state transitions, baseline drift, local hash-chain verification, and report data/rendering.
- `stewardship_lab/training.py`: standard-library training-progress core for external workspaces, structural worksheet checks, immutable attempt snapshots, named human reviews, retries, local consistency verification, and redacted exports.
- `stewardship_lab/release.py`: standard-library release core for frozen-snapshot Open Demo export; exact root/payload and trusted verifier/boundary checks; source-tree/revision/worktree-state binding; strict no-float JSON and SemVer; and private three-package Blind staging with external private manifest/source prerequisites, executable-aware inventories, role-filtered licenses, build-record implementation digests, bounded leakage/path refusal, standalone capacity/traversal fail-closed behavior, and POSIX-mode checks.
- `stewardship_lab/__init__.py`: public package boundary for the stewardship cores.
- `LLM4SBR_research_audit_training_v2/`: the four-level training package and its course hub.
  - `CASE_FILE.md` / `CASE_FILE_EN.md`: versioned scope, provenance, G0 boundary, Open Demo status, and review triggers for the current case.
  - `CAPSTONE_BRIEF.md`: public synthetic cross-layer incident brief; contains no evaluator mapping and requires human review.
- `tests/research_audit_training_v2/`: package, shared-contract, Level 1, and Level 2 acceptance tests.
- `tests/test_audit_lifecycle.py`: synthetic clean-Git lifecycle tests, including dirty-project refusal, G0/preflight, drift/rebaseline, findings/evidence/transitions, tamper detection, and reports.
- `tests/test_training_progress.py`: external-workspace tests for initialization, structure-only checks, immutable retries, human-review consistency/disagreement, tamper and symlink refusal, offline resume, and redacted export.
- `tests/test_release_packaging.py`: Open Demo and synthetic Blind-staging tests for frozen-snapshot validation, exact root/payload binding, trusted verifier/boundary replacement refusal, strict JSON/SemVer, external/private source-manifest prerequisites, executable-aware allowlists/root digests, role inventories/license filtering, build-record bindings, UTF-8 leakage and VCS/secret-path refusal, standalone capacity/unreadable/protected-path failure, POSIX private modes, tamper detection, fail-closed template placeholders, and non-overwriting race behavior.
- `docs/superpowers/specs/`: approved four-level design specification.
- `docs/superpowers/plans/`: test-driven implementation plan.
- `docs/implementation-audit/`: RED/GREEN evidence, review decisions, corrections, and task reports.
- `skills/research-code-audit-training/`: reusable Codex Skill for generating equivalent exercises and stewardship evidence from another paper and source repository.
  - `assets/research-contract-template.md`: G0 question, legitimacy, authority, and stopping gate.
  - `assets/triage-card-template.md`: rapid localization and bounded investigation record.
  - `assets/delegation-contract-template.md`: human–Agent authority and evidence contract.
  - `assets/evidence-passport-template.md`: one finding or trust decision with its complete evidence chain.
  - `assets/learner-evidence-passport-template.md`: L1–L4 worksheet used by a local progress workspace.
  - `assets/capstone-response-template.md`: cross-layer incident response worksheet.
  - `assets/maturity-rubric.md`: versioned human Recognize / Prove / Direct / Steward observation rubric.
  - `assets/blind-source-manifest-template.json`: human-declared, three-role source manifest for a new never-public case.
  - `assets/access-log-template.md`: declared controlled-access activity record; it is not an authentication or access-control mechanism.
  - `assets/revocation-notice-template.md`: quarantine, withdrawal, supersession, notification, and replacement record.
  - `references/stewardship-competencies.md`: portable two-axis competency model for the Skill.

## Mode map

```text
Mode Train
  train overview / doctor / start / validate
  ├─ LLM4SBR_research_audit_training_v2/  learner-visible Open Demo
  └─ train progress init → check → submit → human review → retry/status → export
     └─ external learner workspace: worksheets/ + RUBRIC.md + CAPSTONE_BRIEF.md + progress.json

Mode Audit
  audit init → status/lint → gate check/record → preflight
             → finding add/list/transition + evidence add
             → verify → report build
             └─ rebaseline when the clean target HEAD changes
  └─ external workspace: templates + audit-workspace.json + findings/ + audit-events.jsonl

Case release
  export open-demo → frozen public snapshot + boundary + manifest + checksums
                   → source-tree/revision/worktree record + validation record
                   → revocation template + standalone public verifier
  export verify    → exact root/payload + trusted verifier/boundary bytes

  package blind    → external private sources/manifest + strict JSON/SemVer
                   → executable-aware exact allowlists + BUILD_RECORD tool bindings
                   → private 0700 staging in assembled-awaiting-controlled-placement state
                   ├─ challenge/   participant-safe learner-facing package
                   ├─ evaluator/   controlled evaluation package
                   └─ maintainer/  controlled provenance/governance record
  package verify   → maintainer-side verification of all three staged packages
                   → exact role payloads + trusted verifier/boundary bytes
                   → role inventories/licenses + bounded leakage + POSIX private modes (not ACLs)
  role self-check  → each role runs only its own verify_package.py
                   → bounded capacity/traversal; no sibling package required

Shared governance
  docs/COMPETENCY_MODEL*.md + docs/CASE_RELEASE_MODEL*.md
  skills/research-code-audit-training/
```

Mode Audit does **not execute target-project code, use the network, or modify the target project by default**. `audit init` requires an already-existing parent and creates the new workspace through pinned directory descriptors and exclusive writes; `audit report build` pins workspace identity, refuses overwrite, and writes `0600` on POSIX. These are local fail-closed controls, not access control. Actor/reviewer values are unauthenticated labels, and the hash chain checks internal consistency only for retained local records; every scoped state—including `current`, `ledger-consistent`, and `review-ready`—is not a scientific PASS.

## Current implementation status

Status terms follow the [roadmap](docs/DUAL_MODE_ROADMAP_EN.md): `implemented` means the artifact exists, `internally verified` means controlled tests pass, `field validated` requires observed real use, and `production ready` additionally requires operational, security, recovery, and governance closure. The current core has not reached either of the last two states.

- Level 1 algorithm semantics: implemented and reviewed.
- Level 2 pipeline integrity: implemented and regression-tested.
- Level 3 scientific validity: implemented as five structured, recomputable experiment dossiers with hidden scientific-policy probes.
- Level 4 agent experiment governance: implemented as five closed approval/event/ledger/report timelines with hidden governance probes.
- Explicit Mode Train namespace: implemented and internally verified; legacy aliases have been removed.
- Mode Train progress lifecycle: implemented with an external resumable `progress.json`, separate structure/attempt/human-review states, immutable attempt snapshots, retry history, reviewer disagreement, explicit evidence gaps, a public synthetic capstone, and redacted Markdown/JSON export.
- Capstone pass gate: implemented as a named human record; structural completeness cannot pass it, and the CLI does not generate a maturity or scientific verdict.
- Real-project Mode Audit lifecycle: implemented for clean Git binding, draft/approved/blocked G0, status/lint/preflight, rebaseline, structured findings and evidence, constrained transitions, local integrity verification, and non-overwriting Markdown/JSON reports.
- Phase 3A local release tooling: implemented for the current historically public LLM4SBR Open Demo and for runtime-generated synthetic, never-public three-package staging. Verification enforces exact roots/payloads and trusted generated boundaries; Blind manifests/sources stay outside the public repository, strict no-float JSON, canonical UTC RFC 3339 timestamps, strict SemVer, and placeholder rules fail closed. Build records bind tool-revision scope/worktree state and packager/verifier bytes; every normally assembled role passes its own sibling-independent standalone verifier, which bounds capacity and fails on traversal errors or protected paths. POSIX private modes are checked locally. Repository-side trust is version-coupled, so archived artifacts must retain and use their corresponding tool revision if trusted bytes change. These establish manifest/checksum/package contracts only; they do not establish ACLs or confidentiality.
- Phase 3B controlled Blind operation: not implemented. No current RCSL case is asserted to be an operational Blind Challenge; independent private placement, least privilege, access records, frozen scoring, independent evaluation, human leakage review, release sign-off, and a leakage drill remain external human gates.
- Phase 4 presentation/registry work: deferred and pruned from the active product after review. A historical prototype passed internal contract tests, but it had no field-validated demand and did not bind displayed cases to audit/training subjects strongly enough. Reconsider this layer only after the shared case identity model and real pilots are complete.

All four levels have focused tests, isolated answer manifests, public checks, and external hidden verification.

## Answer isolation and release mode

Directories named `DO_NOT_OPEN_UNTIL_FINISHED/` contain instructor-oriented mappings and probes. In this public repository they provide **honor isolation only**, not access control; the current case is permanently an Open Demo because it and its history are already public. Learners should work only from public materials until they have submitted their audit. A new Blind candidate must separate Challenge, Evaluator, and Maintainer sources before any learner release. Local `package blind` output is only `assembled-awaiting-controlled-placement`; see `docs/CASE_RELEASE_MODEL.md` for the operational controls still required.

## Licensing and provenance

Original software authored by this repository's maintainers is licensed under Apache-2.0, and original documentation is licensed under CC BY 4.0. These grants exclude the LLM4SBR paper, authors' source code, datasets, and all other third-party materials. See `LICENSE`, `DOCUMENTATION_LICENSE.md`, and `THIRD_PARTY_NOTICES.md`.
