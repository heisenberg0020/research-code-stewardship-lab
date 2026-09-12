# Repository map

This public repository has two explicit operating modes built on one stewardship model. **Mode Train** develops human research-code judgment with the LLM4SBR Open Demo. **Mode Audit** binds an external workspace to a real project's clean Git `HEAD` and records G0, findings, evidence, lifecycle events, and a human-review report. The paper and original implementation remain available from their official sources and are not redistributed here.

Canonical entry points are `python scripts/rcsl.py train ...` and `python scripts/rcsl.py audit ...`. Legacy top-level commands remain compatibility aliases.

## Contents

- [LLM4SBR paper](https://arxiv.org/abs/2402.13840): the official paper used as the scientific specification.
- [Original LLM4SBR repository](https://github.com/tsinghua-fib-lab/LLM4SBR): the official implementation source.
- `docs/GETTING_STARTED.md`: Chinese task-oriented start guide for learners, auditors, reviewers, maintainers, and research owners.
- `docs/GETTING_STARTED_EN.md`: English version of the task-oriented start guide.
- `docs/AUDIT_MODE.md`: Chinese command and boundary guide for the real-project audit lifecycle.
- `docs/AUDIT_MODE_EN.md`: English version of the Mode Audit guide.
- `docs/DUAL_MODE_ROADMAP.md`: Chinese phased implementation plan for the shared Train/Audit system.
- `docs/DUAL_MODE_ROADMAP_EN.md`: English version of the dual-mode roadmap.
- `docs/COMPETENCY_MODEL.md`: Chinese G0 + L1–L4 + seven cross-level capabilities and maturity model.
- `docs/COMPETENCY_MODEL_EN.md`: English version of the competency model.
- `docs/CASE_RELEASE_MODEL.md`: Chinese Open Demo and access-controlled Blind Challenge release model.
- `docs/CASE_RELEASE_MODEL_EN.md`: English version of the case release model.
- `docs/images/research-code-stewardship-banner.svg`: the repository’s self-contained Paper → Code → Evidence → Governance banner.
- `requirements.txt`: learner-facing runtime dependency list for local public checks.
- `scripts/rcsl.py`: unified public-only CLI. `train overview|doctor|start|validate` covers the curriculum; `audit init|status|lint|gate|preflight|rebaseline|finding|evidence|verify|report` covers the real-project lifecycle.
- `stewardship_lab/audit.py`: standard-library audit core for clean-Git binding, G0 gates, structured findings/evidence, allowed state transitions, baseline drift, local hash-chain verification, and report data/rendering.
- `stewardship_lab/__init__.py`: public package boundary for the audit core.
- `LLM4SBR_code_judgement_training/`: the earlier local algorithm-code judgement exercise.
- `LLM4SBR_research_audit_training_v2/`: the four-level training package and its course hub.
  - `CASE_FILE.md` / `CASE_FILE_EN.md`: versioned scope, provenance, G0 boundary, Open Demo status, and review triggers for the current case.
- `tests/research_audit_training_v2/`: package, shared-contract, Level 1, and Level 2 acceptance tests.
- `tests/test_audit_lifecycle.py`: synthetic clean-Git lifecycle tests, including dirty-project refusal, G0/preflight, drift/rebaseline, findings/evidence/transitions, tamper detection, and reports.
- `docs/superpowers/specs/`: approved four-level design specification.
- `docs/superpowers/plans/`: test-driven implementation plan.
- `docs/implementation-audit/`: RED/GREEN evidence, review decisions, corrections, and task reports.
- `skills/research-code-audit-training/`: reusable Codex Skill for generating equivalent exercises and stewardship evidence from another paper and source repository.
  - `assets/research-contract-template.md`: G0 question, legitimacy, authority, and stopping gate.
  - `assets/triage-card-template.md`: rapid localization and bounded investigation record.
  - `assets/delegation-contract-template.md`: human–Agent authority and evidence contract.
  - `assets/evidence-passport-template.md`: one finding or trust decision with its complete evidence chain.
  - `references/stewardship-competencies.md`: portable two-axis competency model for the Skill.

## Mode map

```text
Mode Train
  train overview / doctor / start / validate
  └─ LLM4SBR_research_audit_training_v2/  learner-visible Open Demo

Mode Audit
  audit init → status/lint → gate check/record → preflight
             → finding add/list/transition + evidence add
             → verify → report build
             └─ rebaseline when the clean target HEAD changes
  └─ external workspace: templates + audit-workspace.json + findings/ + audit-events.jsonl

Shared governance
  docs/COMPETENCY_MODEL*.md + docs/CASE_RELEASE_MODEL*.md
  skills/research-code-audit-training/
```

Mode Audit does **not execute target-project code, use the network, or modify the target project by default**. Actor/reviewer values are unauthenticated labels. Its hash chain checks internal consistency only for retained local records; it is not access control, external immutability, or identity authentication. Every scoped state—including `current`, `ledger-consistent`, and `review-ready`—is not a scientific PASS.

## Current implementation status

- Level 1 algorithm semantics: implemented and reviewed.
- Level 2 pipeline integrity: implemented and regression-tested.
- Level 3 scientific validity: implemented as five structured, recomputable experiment dossiers with hidden scientific-policy probes.
- Level 4 agent experiment governance: implemented as five closed approval/event/ledger/report timelines with hidden governance probes.
- Explicit Mode Train namespace and compatibility aliases: implemented.
- Real-project Mode Audit lifecycle: implemented for clean Git binding, draft/approved/blocked G0, status/lint/preflight, rebaseline, structured findings and evidence, constrained transitions, local integrity verification, and non-overwriting Markdown/JSON reports.

All four levels have focused tests, isolated answer manifests, public checks, and external hidden verification.

## Answer isolation and release mode

Directories named `DO_NOT_OPEN_UNTIL_FINISHED/` contain instructor-oriented mappings and probes. In this public repository they provide **honor isolation only**, not access control; the current case is an Open Demo. Learners should work only from public materials until they have submitted their audit. See `docs/CASE_RELEASE_MODEL.md` for the separate packages required by a genuinely blind challenge.

## Licensing and provenance

Original software authored by this repository's maintainers is licensed under Apache-2.0, and original documentation is licensed under CC BY 4.0. These grants exclude the LLM4SBR paper, authors' source code, datasets, and all other third-party materials. See `LICENSE`, `DOCUMENTATION_LICENSE.md`, and `THIRD_PARTY_NOTICES.md`.
