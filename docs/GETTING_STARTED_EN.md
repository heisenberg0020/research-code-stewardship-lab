# Start here

![Research Code Stewardship Lab: Paper → Code → Evidence → Governance](images/research-code-stewardship-banner.svg)

**Research Code Stewardship Lab** helps you decide whether runnable research code, experiments, and agent workflows still honor the paper, experimental protocol, and evidence trail behind them. It is not a code-writing speed course. It develops evidence-based research judgment for the coding-agent era.

[中文指南](GETTING_STARTED.md) · [Repository map](../REPOSITORY_MAP.md) · [Four-level course](../LLM4SBR_research_audit_training_v2/README.md)

## Choose your path

| You are a… | Start with… | You will leave with… |
| --- | --- | --- |
| **Learner** | Audit the LLM4SBR case study from Level 1 | An evidence chain: location, violated contract, counterexample, causal effect, and safe repair |
| **Reviewer / maintainer** | Run public checks and review the package contract, documentation, and entry points | A reproducible public-check report and a list of risks that still need human review |
| **Research owner** | Freeze the paper–code–experiment protocol, then design a new package with the Skill | A human-approved four-level design specification—not unreviewed candidate code |

---

## Path A: Learn the LLM4SBR case

### 1. Confirm that the public package runs

From the repository root:

```bash
python -m pip install -r requirements.txt
python scripts/rcsl.py doctor
python scripts/rcsl.py validate
```

You should see `LEVEL 1: PASS` through `LEVEL 4: PASS`. That means the learner-visible package is runnable and its public structure is intact. It does **not** decide which candidate is faithful to the paper or establish a scientific conclusion.

### 2. Work in order

Begin with the [course hub](../LLM4SBR_research_audit_training_v2/README.md) and [Progression](../LLM4SBR_research_audit_training_v2/PROGRESSION.md), then continue one level at a time:

| Level | Audit question | Read first | Public check |
| --- | --- | --- | --- |
| 1 | Are formulas, tensors, masks, losses, and gradient semantics correct? | [`level_1_algorithm_semantics/README.md`](../LLM4SBR_research_audit_training_v2/level_1_algorithm_semantics/README.md) | `python LLM4SBR_research_audit_training_v2/level_1_algorithm_semantics/run_smoke.py` |
| 2 | Do data identity, splitting, metrics, and checkpoint lineage remain intact? | [`level_2_pipeline_integrity/README.md`](../LLM4SBR_research_audit_training_v2/level_2_pipeline_integrity/README.md) | `python LLM4SBR_research_audit_training_v2/level_2_pipeline_integrity/run_smoke.py` |
| 3 | Are comparisons fair, and does the evidence support the scientific claim? | [`level_3_scientific_validity/README.md`](../LLM4SBR_research_audit_training_v2/level_3_scientific_validity/README.md) | `python LLM4SBR_research_audit_training_v2/level_3_scientific_validity/validate_evidence_schema.py` |
| 4 | Are approvals, budgets, records, and protected evidence governed correctly? | [`level_4_agent_experiment_governance/README.md`](../LLM4SBR_research_audit_training_v2/level_4_agent_experiment_governance/README.md) | `python LLM4SBR_research_audit_training_v2/level_4_agent_experiment_governance/validate_ledger_schema.py` |

### 3. Submit an evidence chain, not a letter

Every level provides a learner-visible `ANSWER_SHEET.md`. Before completing it, you should be able to state:

1. Which exact location or record supports your conclusion?
2. Which paper, pipeline, experimental, or governance contract is violated?
3. What is the smallest counterexample that exposes the failure?
4. Why can the system still run or look plausible?
5. What is the smallest safe repair?

### Optional prerequisite: learn the paper before seeing code

Use the [Source-Blind Paper Learning Protocol](PAPER_ONLY_REPRODUCTION_PROTOCOL.md) to build a `PAPER_STUDY_GUIDE.md` from the paper and its public supplementary material only. This keeps “how the current code behaves” from being mistaken for “what the paper requires.”

---

## Path B: Review or maintain the package

Start with the full public verification:

```bash
python LLM4SBR_research_audit_training_v2/run_all_public_checks.py
```

Then work through this sequence:

1. Read the [course hub](../LLM4SBR_research_audit_training_v2/README.md) and [framework overview](../LLM4SBR_research_audit_training_v2/FRAMEWORK_OVERVIEW.md) to understand each level’s capability boundary.
2. Review each level’s public brief and validation script for consistent entry points, documentation, and contracts.
3. Treat `PASS` as “these four public validators passed for this revision,” not as “the research conclusion is correct” or “the exercise is free of scientific bias.”
4. After a package change, rerun the same public checks and record the change, rationale, risks, and assumptions that remain untested.

The expected output is a traceable maintenance note: what changed, which public constraints were rechecked, and which decisions still need human review.

---

## Path C: Build a new package for another paper

The reusable [`research-code-audit-training` Skill](../skills/research-code-audit-training/SKILL.md) turns a paper, source tree, and experimental protocol into a four-level audit exercise. It does not simply write a replacement research project.

### Recommended flow

```text
Freeze the question, paper evidence, source scope, and experimental protocol
→ Create a paper-to-code map and four-level design specification
→ Have a human review and approve the specification
→ Generate candidates, public checks, and separated teaching materials
→ Validate the release with public checks and independent review
```

Optionally install the Skill for Codex and invoke it in a new task:

```bash
mkdir -p ~/.codex/skills
cp -R skills/research-code-audit-training ~/.codex/skills/
```

```text
$research-code-audit-training
```

Start with the [`design-spec-template.md`](../skills/research-code-audit-training/assets/design-spec-template.md) to define the objective, protected inputs, four-level fault families, and acceptance matrix. **Do not create candidate implementations until the design specification has human approval.**

The expected output is a reviewable specification that connects paper claims, code locations, executable invariants, and validation methods while marking unresolved choices as assumptions.

---

## Two boundaries that always apply

### 1. Answer isolation protects the learning value

Instructor materials and learner-visible materials are intentionally separated. Before you finish a level’s public brief, public checks, and evidence chain, do not search for, read, or cite material marked as instructor-only or unlocked after completion. Public verifiers should not depend on that material either.

### 2. `public PASS` is only the beginning

A public `PASS` can show that scripts, formats, or some executable invariants have not immediately failed. It cannot establish that:

- an implementation is faithful to the paper;
- data and evaluation comparisons are fair;
- results support a scientific claim;
- every agent action was authorized; or
- a paper conclusion has been reproduced.

Every audit must therefore return to primary evidence, the frozen protocol, and an explicit causal argument.

## Where to go next

- Need the full directory guide? Read the [repository map](../REPOSITORY_MAP.md).
- Ready to start LLM4SBR? Open the [four-level course](../LLM4SBR_research_audit_training_v2/README.md).
- Want a paper-first, source-blind baseline? Use the [Source-Blind Protocol](PAPER_ONLY_REPRODUCTION_PROTOCOL.md).
- Want to adapt the workflow to your paper? Read the [Skill](../skills/research-code-audit-training/SKILL.md).
