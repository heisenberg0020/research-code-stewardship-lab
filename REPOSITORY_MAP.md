# Repository map

This public repository provides a research-code stewardship training system built around the LLM4SBR case study. The paper and original implementation remain available from their official sources and are not redistributed here. The root `README.md` is the approved general overview of modern coding-agent capability boundaries and the human role in research-code construction.

## Contents

- [LLM4SBR paper](https://arxiv.org/abs/2402.13840): the official paper used as the scientific specification.
- [Original LLM4SBR repository](https://github.com/tsinghua-fib-lab/LLM4SBR): the official implementation source.
- `LLM4SBR_code_judgement_training/`: the earlier local algorithm-code judgement exercise.
- `LLM4SBR_research_audit_training_v2/`: the four-level training package.
- `tests/research_audit_training_v2/`: package, shared-contract, Level 1, and Level 2 acceptance tests.
- `docs/superpowers/specs/`: approved four-level design specification.
- `docs/superpowers/plans/`: test-driven implementation plan.
- `docs/implementation-audit/`: RED/GREEN evidence, review decisions, corrections, and task reports.
- `skills/research-code-audit-training/`: reusable Codex Skill for generating equivalent exercises from another paper and source repository.

## Current implementation status

- Level 1 algorithm semantics: implemented and reviewed.
- Level 2 pipeline integrity: implemented and regression-tested.
- Level 3 scientific validity: implemented as five structured, recomputable experiment dossiers with hidden scientific-policy probes.
- Level 4 agent experiment governance: implemented as five closed approval/event/ledger/report timelines with hidden governance probes.

All four levels have focused tests, isolated answer manifests, public checks, and external hidden verification.

## Answer isolation

Directories named `DO_NOT_OPEN_UNTIL_FINISHED/` contain instructor-only mappings and hidden probes. Learners should work only from public materials until they have submitted their audit.

## Licensing and provenance

Original software authored by this repository's maintainers is licensed under Apache-2.0, and original documentation is licensed under CC BY 4.0. These grants exclude the LLM4SBR paper, authors' source code, datasets, and all other third-party materials. See `LICENSE`, `DOCUMENTATION_LICENSE.md`, and `THIRD_PARTY_NOTICES.md`.
