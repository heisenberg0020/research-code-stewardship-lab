# Level 3 · Scientific Validity

> **Question:** even if the calculations are correct, does the evidence justify the scientific claim?

Audit `dossiers/A` through `dossiers/E` against [REVIEW_CRITERIA.md](REVIEW_CRITERIA.md). Every dossier is schema-valid and arithmetically recomputable. The task is to determine whether its comparison, evidence chain, and stated claim are scientifically supportable.

## What you will practice

- Separate arithmetic correctness from a fair experimental comparison.
- Identify the strongest claim that the available evidence can actually support.
- Cite structured keys and run identifiers instead of relying on a narrative summary.

## Start here

From the `LLM4SBR_research_audit_training_v2/` directory:

```bash
python level_3_scientific_validity/validate_evidence_schema.py
```

This public check validates parsing and schema shape only. It does **not** tell you whether a dossier's scientific claim is valid.

## Learner workflow

1. Read [REVIEW_CRITERIA.md](REVIEW_CRITERIA.md) and turn each criterion into a review question.
2. Inspect `dossiers/A` through `dossiers/E`; recompute the stated quantities where appropriate.
3. Compare each dossier's evaluation population, baseline, intervention, and claim boundary against the frozen criteria.
4. Record the trustworthy dossier in [ANSWER_SHEET.md](ANSWER_SHEET.md). For every rejection, cite exact keys or run IDs, the violated criterion, why the arithmetic can still be valid, the strongest supportable claim, and the minimum revision.
5. Submit your audit before consulting instructor-only material.

## Completion standard

The final selection must be supported by an auditable evidence chain. “The numbers add up” is insufficient when the comparison is unfair, the evidence is incomplete, or the claim is broader than the experiment supports.

**Previous:** [Level 2 · Pipeline Integrity](../level_2_pipeline_integrity/README.md)<br />
**Next:** [Level 4 · Agent Experiment Governance](../level_4_agent_experiment_governance/README.md)
