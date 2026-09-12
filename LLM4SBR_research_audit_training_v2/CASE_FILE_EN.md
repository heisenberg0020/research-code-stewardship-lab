# LLM4SBR Research Audit v2 — Case File

[中文](CASE_FILE.md) · [Course hub](README.md) · [Release model](../docs/CASE_RELEASE_MODEL_EN.md)

| Field | Current record |
| --- | --- |
| Case ID | `rcsl/llm4sbr-research-audit-v2` |
| Release state | `current · Open Demo` |
| Version authority | The repository Git commit; record the exact commit when exporting audit evidence |
| Maintenance owner | This repository's maintainers |
| Learning purpose | Evidence-based human judgment from algorithm semantics through agent governance |

## Research object and provenance

- Paper: [LLM4SBR: A Lightweight and Effective Framework for Integrating Large Language Models in Session-based Recommendation](https://arxiv.org/abs/2402.13840)
- Official implementation: [tsinghua-fib-lab/LLM4SBR](https://github.com/tsinghua-fib-lab/LLM4SBR)
- This case does not redistribute the paper PDF, upstream source, or original datasets. See [`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md) for third-party boundaries.
- Training candidates, deterministic small fixtures, validators, and instructions are independent educational artifacts. They are not claims about defects in the authors' implementation.

## G0 research-contract summary

- **Permitted claim:** the case can train recognition of contract deviations in runnable research artifacts and assess the evidence chain a learner submits.
- **Prohibited extrapolation:** public checks do not prove the paper's conclusions, reproduce its empirical results, measure real production security, or produce a confidential blind-assessment score.
- **Runtime boundary:** public checks use local, small, deterministic material and require no network, full training, original data, or GPU.
- **Human-reserved decisions:** interpretation of paper–code conflicts, experimental fairness, risk acceptance, final claims, and release.
- **Stop conditions:** uncertain provenance or licensing, exposed protected material, learner-facing output that reveals teaching judgments, or a material upstream protocol change.

## Coverage

| Level | First failed contract | Public evidence form |
| --- | --- | --- |
| L1 | Formula, operator, index, loss, or gradient semantics | Candidate implementations, paper map, minimal smoke path |
| L2 | Data identity, split, state, checkpoint, or evaluation flow | Multi-file pipelines, frozen specification, run artifacts |
| L3 | Comparison design, evidence population, statistical rule, or claim scope | Planned/observed runs, aggregate, structured claim |
| L4 | Authorization, approval, budget, record, or protected-evidence boundary | Frozen protocol, events, approvals, resource and report ledgers |

The current case does not yet include a full unfamiliar-project capstone, real supply-chain review, production deployment lifecycle, or access-controlled evaluation service.

## Public validation

Run from the repository root:

```bash
python skills/research-code-audit-training/scripts/validate_training_package.py \
  LLM4SBR_research_audit_training_v2
python LLM4SBR_research_audit_training_v2/run_all_public_checks.py
```

The expected four `LEVEL n: PASS` lines mean only that this version satisfies the public validators' package contract. They do not expose teaching judgments or replace human audit.

## Release and isolation boundary

Instructor-oriented material for this case lives in the same public Git repository, so its separation is **honor isolation**, not access control. The case is appropriate for teaching demonstrations, workflow practice, and regression tests; it must not be described as a secure Blind Challenge. True blinding requires a separate public Challenge Package, controlled Evaluator Package, and controlled Maintainer Record.

## Review triggers

Mark this Case File `awaiting review` before revising, superseding, or withdrawing it if any of the following occurs:

- a material change to the paper, official implementation, or relevant data protocol;
- an unfair cue, exposed teaching judgment, or second primary defect is found;
- a dependency, runtime environment, or public interface changes;
- provenance, license, security, privacy, or ethics boundaries change; or
- the public validators no longer reproduce their stated package contract reliably.
