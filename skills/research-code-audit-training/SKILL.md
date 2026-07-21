---
name: research-code-audit-training
description: Generate a test-driven four-level blind research-code audit training package from a paper and its source repository. Use when Codex must turn paper formulas, implementation code, experiment pipelines, scientific evidence, or agent-run records into exercises with one trustworthy candidate and four subtle runnable faults per level; includes specification design, paper-to-code mapping, semantic mutations, hidden probes, leakage resistance, scientific-validity dossiers, governance timelines, review, and correction.
---

# Research Code Audit Training

Build training that teaches the human responsibilities left after coding agents can implement and operate most of a research codebase: own the specification, preserve experimental boundaries, demand evidence, and authorize scientific claims.

## Read the required guidance

Read these references before designing:

- [four-level-framework.md](references/four-level-framework.md) for level boundaries and fault families.
- [quality-gates.md](references/quality-gates.md) for mutation, anti-leakage, review, and correction criteria.
- [artifact-contracts.md](references/artifact-contracts.md) for the output tree and machine-auditable schemas.
- [level3-level4-implementation-lessons.md](references/level3-level4-implementation-lessons.md) before implementing scientific dossiers or governance timelines.

Read [domain-adaptation.md](references/domain-adaptation.md) when the paper is not session-based recommendation or uses unusual units such as patients, graphs, environments, trajectories, or temporal panels.

## Establish inputs and authority

Require a paper and its source repository. Locate them locally when possible; ask only for genuinely missing inputs. Treat existing source, data, paper files, and prior exercises as protected. Record their hashes or Git status before writing.

Establish:

1. paper claims, equations, algorithms, datasets, splits, metrics, baselines, and ablations;
2. source entry points, configuration flow, data lineage, training state, evaluation, and reporting;
3. the available offline environment and a bounded smoke-test budget;
4. the output directory and paths that must remain unchanged.

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
- resource and environment constraints.

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

Do not claim the package is complete from static validation alone.
