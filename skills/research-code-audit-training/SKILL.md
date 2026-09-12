---
name: research-code-audit-training
description: Design and generate test-driven research-code audit training and stewardship workspaces from a paper and source repository. Use when Codex must establish a research contract, map claims to code, create four-level blind exercises with subtle runnable faults, train human triage and agent oversight, manage audit evidence, or build an end-to-end stewardship capstone; includes public/hidden separation, scientific-validity dossiers, governance timelines, review, and correction.
---

# Research Code Audit Training

Build training that teaches the human responsibilities left after coding agents can implement and operate most of a research codebase: own the specification, preserve experimental boundaries, demand evidence, and authorize scientific claims.

## Read the required guidance

Read these references before designing:

- [stewardship-competencies.md](references/stewardship-competencies.md) for the G0 gate, cross-level human capabilities, maturity stages, role routes, and capstone.
- [four-level-framework.md](references/four-level-framework.md) for level boundaries and fault families.
- [quality-gates.md](references/quality-gates.md) for mutation, anti-leakage, review, and correction criteria.
- [artifact-contracts.md](references/artifact-contracts.md) for the output tree and machine-auditable schemas.
- [level3-level4-implementation-lessons.md](references/level3-level4-implementation-lessons.md) before implementing scientific dossiers or governance timelines.

Read [domain-adaptation.md](references/domain-adaptation.md) when the paper is not session-based recommendation or uses unusual units such as patients, graphs, environments, trajectories, or temporal panels.

## Establish inputs and authority

Require a paper and its source repository. Locate them locally when possible; ask only for genuinely missing inputs. Treat existing source, data, paper files, and prior exercises as protected. Record their hashes or Git status before writing.

Complete [research-contract-template.md](assets/research-contract-template.md) and establish:

1. the research question, construct or estimand, target population, decision, allowed claim, and non-goals;
2. paper claims, equations, algorithms, datasets, splits, metrics, baselines, and ablations;
3. source entry points, configuration flow, data lineage, training state, evaluation, and reporting;
4. source revisions, data rights, licenses, privacy, safety, fairness, ethics, and affected stakeholders;
5. human-only decisions, agent permissions, approvals, protected evidence, stop conditions, and budgets;
6. the available offline environment, bounded smoke-test budget, output directory, and paths that must remain unchanged.

Treat this as the G0 gate. Mark the work `blocked` rather than inventing a value when an unresolved choice changes the research meaning, authorization, or affected population. A human owner must approve the contract before consequential implementation or experiment actions.

Do not download large models or datasets, run full training, alter original materials, or infer permission to change the research protocol.

## Create and approve the design specification first

Write a design specification before candidate code. Use [design-spec-template.md](assets/design-spec-template.md). Include:

- the paper-to-code map;
- frozen experimental protocol;
- deterministic substitute data or tiny fixtures;
- exactly four level definitions;
- candidate interfaces and public/hidden checks;
- proposed fault families without assigning public candidate letters;
- anti-leakage rules and acceptance tests;
- release mode, package boundaries, case version, and review triggers;
- resource and environment constraints.

For every proposed task, name its primary cross-level human capability and target maturity stage. Keep G0 as a prerequisite gate and the capstone as an integrative assessment; do not disguise them as extra singleton-fault levels.

Stop for user approval if the proposed faults, scientific protocol, or source interpretation would materially determine the exercise. Do not start mutation implementation before approval.

## Follow the TDD implementation sequence

Maintain a progress ledger. Implement one task at a time:

1. Freeze protected-file hashes and write package-contract tests.
2. Write shared deterministic fixtures, reference metrics, and strict schema readers.
3. Implement Level 1 after witnessing its focused tests fail for missing behavior.
4. Review and correct Level 1 before starting Level 2.
5. Repeat RED → minimal implementation → GREEN → independent review for Levels 2–4.
6. Add root public runners and an external hidden verifier.
7. Run focused, combined, reproducibility, leakage, import, network, and protected-file tests.

Never write production candidates before observing the intended failing tests. A RED caused only by syntax errors or a broken test harness is invalid; correct the test and rerun RED.

## Generate each blind level

Create five comparable candidates per level: one fully trustworthy candidate and four candidates with exactly one primary fault each. Assign trusted letters privately, vary them across levels, and avoid a visible sequence.

All five candidates must:

- share the same public interface and artifact schema;
- import, compile, and complete the bounded smoke path;
- emit finite, plausible outputs;
- have comparable file counts, comments, naming, line counts, and code quality;
- pass public checks that establish operability but not scientific correctness.

Classify a fault by the first contract it breaks, not by downstream impact. Keep one primary finding per faulty candidate.

### Level 1 — algorithm semantics

Mutate one parameter, constant, operator, index, reduction, or gradient expression. Preserve shapes, forward/backward execution, and usually the same broad output behavior. Prove faults with mathematical invariants, minimal tensors, finite differences, or gradient checks.

Do not use compilation failures, obvious branch swaps, missing modules, or errors discoverable by a single mechanical diff. Add harmless equivalent variants and decoy markers so the trustworthy candidate is not the textual center and local majority voting cannot reconstruct it.

### Level 2 — pipeline integrity

Create complete multi-file pipelines. Target identity isolation, joint permutation, feature/label alignment, population denominators, checkpoint state, recovery, or protected-evaluation order. Require evidence across at least two files or artifacts. Preserve training completion, checkpoints, event logs, and plausible metrics.

### Level 3 — scientific validity

Create structured experiment dossiers. Treat the planned-run matrix as the authoritative expected population and preserve separate planned, observed, aggregate, and claim layers. Freeze paired/block identity, one final observation per method and unit, information condition, complete tuning-budget signatures, predeclared exclusions, practical threshold, and allowed claim scope.

Target tuning-budget fairness, information-condition parity, selective exclusion, experimental units, pairing, uncertainty, or claim scope. Make every aggregate arithmetically correct for its declared included rows even when the scientific design is wrong. Link structured claims to exact evidence run IDs and repeat the same claim ID in prose. Hidden checks must use JSON/CSV evidence, never prose or marginal interval overlap alone.

### Level 4 — experiment governance

Create a machine-readable frozen protocol with stable clause IDs plus closed event, approval, resource, run-ledger, and report timelines. Give every event evidence references and details; distinguish required values from schema-declared JSON null or CSV blank fields.

Target explicit approval conflicts, resource overrun, record suppression, or protected-evidence adaptation. Prove approval faults positively through status, timing, scope, or limits rather than treating an absent optional approval ID as proof. Recompute resource use and reports from the complete ledger. A poor result is not itself a violation. Post-hoc reporting and discussion of protected evidence are allowed; only explicit flow into a later adaptive action is prohibited.

## Separate public and hidden surfaces

Keep student-visible materials, public smoke tests, and answer sheets outside isolated answer directories. Keep authoritative mappings, rule IDs, repair spans, causal chains, and probes under `DO_NOT_OPEN_UNTIL_FINISHED/` or an equivalent protected directory.

Call a same-repository layout with readable instructor files an **Open Demo with honor isolation**, not a secure blind assessment. For a real Blind Challenge, generate separate learner, instructor, and public-CI packages; publish only the learner and public-CI artifacts, and keep instructor mappings and probes behind actual access control.

Generate a learner-visible `CASE_FILE.md` using [artifact-contracts.md](references/artifact-contracts.md). Record source revisions, G0 scope, release mode, validation claims, known limitations, owner, and review triggers. Mark a case stale when a material source or protocol revision changes; do not silently carry forward an earlier validation claim.

The public package verifier must never import hidden answers. Put the whole-package hidden verifier outside the student package. Public stdout may print only neutral PASS/FAIL operability results, never metrics rankings or diagnostic rule names.

Hidden probes must derive findings from behavior and artifacts. Never swallow broad exceptions and translate infrastructure failure into a scientific rule. Let unexpected exceptions fail verification.

Require one content-based classifier per Level 3/4 candidate. Test that injected loader failures propagate and that public validators accept all five candidates without revealing rule names or result rankings.

## Require evidence-rich answers

Use [answer-sheet-template.md](assets/answer-sheet-template.md). Require the learner to provide:

- the unique trustworthy candidate;
- precise location or structured evidence for every rejection;
- the paper equation, protocol clause, or scientific rule violated;
- why the candidate still runs and appears plausible;
- a minimal counterexample or reproducible audit;
- expected causal impact, with direction marked unknown when unsupported;
- the smallest safe repair or governance response.

Grade evidence and reasoning, not letter selection alone.

## Train stewardship across the levels

Use the four levels to locate the first broken contract, then require the human capabilities described in [stewardship-competencies.md](references/stewardship-competencies.md). Use:

- [triage-card-template.md](assets/triage-card-template.md) to localize an anomaly and compare hypotheses before mutation or repair;
- [delegation-contract-template.md](assets/delegation-contract-template.md) before an agent receives a consequential task;
- [evidence-passport-template.md](assets/evidence-passport-template.md) for each material finding or trust decision.

Automated linting may establish only that required evidence fields are present. It must never label a research question legitimate, a finding correct, or a scientific claim approved. Require a named human owner to make those decisions.

For a complete curriculum, add a capstone on an unfamiliar or changed revision. It should cross G0 and L1–L4, reproduce the public artifact in a clean environment, review provenance and lifecycle risks, respond to an injected incident, and end with a calibrated release or claim decision plus a durable evidence bundle.

## Review and correct adversarially

After each level, inspect all public and hidden surfaces using [quality-gates.md](references/quality-gates.md). When a review finds a defect:

1. add a focused test that fails on the defect;
2. record the exact RED evidence;
3. make the smallest correction;
4. rerun focused and combined tests;
5. update manifests, repair spans, and reports without exposing mappings;
6. obtain an independent review when available.

Reject a level if the trusted candidate has a second bug, a faulty candidate has multiple primary faults, an error can be guessed from style or metrics, a probe depends on candidate names, or public materials reveal the mapping.

## Validate and hand off

Run the bundled static validator:

```bash
python scripts/validate_training_package.py /absolute/path/to/training-package
```

Then run the package's real focused and full test commands twice. Confirm protected hashes remain unchanged and normalize temporary paths/timestamps before comparing reproducibility.

Run `git diff --check` when using Git. Make deterministic artifact generators emit repository-standard LF line endings so generated CSV/JSON does not introduce platform-only diffs.

Hand off:

- the approved design specification;
- the self-contained training folder;
- public commands and learning order;
- isolated answer materials;
- RED/GREEN evidence and independent-review findings;
- limitations, untested assumptions, and environment requirements.
- the approved G0 research contract, delegation boundaries, evidence passports, and capstone decision when those artifacts are in scope.

Do not claim the package is complete from static validation alone.
