# LLM4SBR Research Audit v2 — Case File

[中文](CASE_FILE.md) · [Course hub](README.md) · [Release model](../docs/CASE_RELEASE_MODEL_EN.md)

| Field | Current record |
| --- | --- |
| Case ID | `rcsl/llm4sbr-research-audit-v2` |
| Release state | `current · Open Demo · historically-public` |
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
| Capstone | Triage, delegation, blast radius, and release judgment when signals cross layers | Public synthetic incident brief, cross-layer response, named human review |

The current case includes a public synthetic cross-layer capstone, but not an unfamiliar private-project capstone, real supply-chain review, production deployment lifecycle, or access-controlled evaluation service. It must not be described as confidential or unseen.

## Local learning progress and human review

`python scripts/rcsl.py train progress ...` creates a learner-owned workspace outside the repository and retains L1–L4 and capstone worksheets, immutable submission snapshots, retry relationships, human feedback, and redacted exports. Automated `check` verifies required sections, nonempty content, and resolved template prompts only; it does not judge meaning, scientific correctness, or maturity.

Recognize / Prove / Direct / Steward observations can be declared only by a named human reviewer. A human L1–L4 `pass` requires the reviewer to record Recognize and Prove as `demonstrated`; a human capstone `pass` requires all four bands as `demonstrated`. The CLI validates declared consistency only, not the judgment itself. See the [Mode Train guide](../docs/TRAIN_MODE_EN.md).

## Public validation

Run from the repository root:

```bash
python skills/research-code-audit-training/scripts/validate_training_package.py \
  LLM4SBR_research_audit_training_v2
python LLM4SBR_research_audit_training_v2/run_all_public_checks.py
```

The expected four `LEVEL n: PASS` lines mean only that this version satisfies the public validators' package contract. They do not expose teaching judgments or replace human audit. Likewise, `structure=complete` in a learning workspace is not a semantic, scientific, or maturity pass.

## Release and isolation boundary

Instructor-oriented material for this case lives in the same public Git repository, so its separation is **honor isolation**, not access control. The case is appropriate for teaching demonstrations, workflow practice, and regression tests; it must not be described as a secure Blind Challenge. True blinding requires a separate public Challenge Package, controlled Evaluator Package, and controlled Maintainer Record.

This case and its related Git history are already public, so they do not satisfy never-public eligibility. Recompression, relocation, encryption, renaming, or invoking split packaging cannot make the case unseen. It may only use Open Demo export:

```bash
python scripts/rcsl.py export open-demo \
  --output /absolute/path/to/new-open-demo-bundle \
  --actor "maintainer label" \
  --run-public-checks
python scripts/rcsl.py export verify /absolute/path/to/new-open-demo-bundle
```

The export creates a boundary statement, manifest, checksums, validation record, revocation template, and standalone public verifier. `--run-public-checks` may be omitted, but the record must truthfully say whether checks were run during this export. Export first freezes the selected public source tree and runs checks against that snapshot; `source_tree_sha256` binds its actual paths, bytes, sizes, and executable bits, while `source_revision_scope` and `repository_worktree_state` record the limited meaning of the Git revision and the source worktree's `clean`/`dirty` state. The bundled verifier checks the exact root file set, manifest/payload, and boundary fields; `export verify` from a trusted RCSL checkout additionally byte-compares the verifier and boundary generated by that tool version. Archive the corresponding RCSL revision with an old bundle; newer tooling fails closed if those trusted bytes have changed. Successful export or verification only means that the retained public bundle satisfies its local release contract. A checksum is not a signature, and the public verifier does not establish scientific correctness, learning effectiveness, or answer secrecy.

`package blind` applies only to a different, new, never-public case whose three source classes were separated from creation. Its output state is still only `assembled-awaiting-controlled-placement`; controlled storage, least privilege, human leakage review, independent evaluation, named release sign-off, and a leakage-withdrawal drill remain required. See the [case release model](../docs/CASE_RELEASE_MODEL_EN.md).

## Review triggers

Mark this Case File `awaiting review` before revising, superseding, or withdrawing it if any of the following occurs:

- a material change to the paper, official implementation, or relevant data protocol;
- an unfair cue, exposed teaching judgment, or second primary defect is found;
- a dependency, runtime environment, or public interface changes;
- provenance, license, security, privacy, or ethics boundaries change; or
- the public validators no longer reproduce their stated package contract reliably.
