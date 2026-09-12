# RCSL Case Release Model

This model defines how to release a paper, source tree, and experimental protocol as a reusable research-code audit case. The goal is traceable scope, evidence, and boundaries—not treating one `PASS` as scientific correctness or a secure blind assessment.

[中文](CASE_RELEASE_MODEL.md) · [Competency model](COMPETENCY_MODEL_EN.md) · [Four-level training package](../LLM4SBR_research_audit_training_v2/README.md)

## 1. Release unit: a versioned Case File

Each case should have a stable `case-id` and semantic version, for example `llm4sbr-audit/v1.0.0`. The version record must answer: “Which material and protocol does this case actually audit?”

| Case File field | What it must record |
| --- | --- |
| Scope and provenance | Paper version, upstream source revision, data/third-party licenses, included and excluded material |
| G0 research contract | Permitted claims, protection boundaries, metrics/budget, permissions, and stop conditions |
| Vertical coverage | The first failed contract and appropriate evidence trained by each L1–L4 case |
| Public surface | Learner-readable documents, candidates, public checks, worksheets, and known limits |
| Validation record | Public-check version, independent review, known blind spots, and claims not made |
| Maintenance state | Current, superseded, awaiting review after upstream change, withdrawn, or archived |

If the upstream paper, source, data protocol, or G0 changes materially, the old Case File must become **awaiting review**. It must not silently keep an “already validated” description.

## 2. Minimum pre-release gates

```text
Freeze the G0 research contract
→ map paper, code, and experiment
→ define L1–L4 specifications and public/controlled surfaces
→ run public checks, leakage review, and independent review
→ release the Case File, version, and known boundaries
→ monitor changes, review, supersede, or withdraw
```

| Gate | Decision a human must approve | Action if insufficient |
| --- | --- | --- |
| G0 | Scope, risks, protected material, claims, and authority boundaries | Pause; do not fill gaps with defaults |
| Design | First failed contract, fault family, evidence standard, learning objective | Revise specification; do not generate/release candidates |
| Validation | What public checks cover and do not cover; leakage or misleading-signal risk | Fix the case or narrow the claim |
| Release | License, provenance, version, maintainer, and known limits | Do not release, or label explicitly experimental |
| Maintenance | Upstream changes, reported issues, review, and withdrawal | Mark stale, patch, or withdraw |

## 3. Two release modes

### Open Demo: the honest status of current public cases

Current public training material is **Open Demo / honor isolation**:

- Learners agree not to seek instructor material before completing the public brief, public checks, and evidence record.
- Public checks verify only the public package’s structural, format, or bounded-runtime contract.
- Convention-based separation inside a public Git repository is not access control, confidentiality protection, or adversarial leakage resistance.
- Results must not be described as blind-assessment scores, confidential-exam results, real attack-surface security, or independent scientific replication.

Open Demo is appropriate for teaching, examples, public discussion, and tool regression. Its value is a transparent workflow and reproducible evidence format, not answer secrecy.

### Blind Challenge: future split packages for true blinding

When the purpose is to evaluate generalization by learners, agents, or a workflow, use split packages from day one—not a public package that is later “hidden.”

| Package | Who can access it | Contents | Must not contain |
| --- | --- | --- | --- |
| **Challenge Package (public)** | Participants/learners | Brief, permitted material, candidates, public smoke check, submission format, rules | Answer mapping, mutation ledger, hidden probes, private data, evaluation labels |
| **Evaluator Package (controlled)** | Authorized evaluators | Answer mapping, private verification, grader, evaluation labels, leakage checks | Public repository, participant environment, ordinary download distribution |
| **Maintainer Record (controlled)** | Case owners | Provenance/licenses, G0, design decisions, mutation rationale, risks, incidents, withdrawal records | Unnecessary participant identity or sensitive raw data |

Minimum controls are: a separate private repository or controlled artifact store; least privilege; evaluator version and checksums; access/release records; public Git history without answers; and invalidation/replacement procedures after leakage. Access control alone does not establish measurement validity: a Blind Challenge also needs frozen scoring rules, repeatability, and independent review.

## 4. Release evidence bundle

A release is more than a collection of files. Publish or retain these evidence items with the Case File:

1. **Provenance and license record:** scope of the paper, upstream revision, data, and third-party material;
2. **G0 research contract:** objective, risks, protection boundaries, budget, approvals, and claims;
3. **Contract map:** each Level’s first failed contract, observable invariants, and preferred evidence;
4. **Public validation record:** command, environment, version, result, and risks explicitly not covered;
5. **Learning and fairness note:** prerequisites, expected effort, accessibility/language considerations, and known misleading signals;
6. **Maintenance and withdrawal policy:** issue-reporting path, upstream-change handling, and conditions for stale/withdrawn status.

Every report should separate facts, inferences, assumptions, recommendations, and unknowns. Write `public PASS` as “the public validator passed for this version,” never as “the paper conclusion is proven” or “the case is absolutely secure.”

## 5. Changes, incidents, and withdrawal

| Event | Immediate action | What to tell users |
| --- | --- | --- |
| Upstream paper/source changes | Mark awaiting review; pause strong claims | Identify affected Case File version and scope |
| Answer leakage or unfair cue | Invalidate affected Blind Challenge version; disclose it in Open Demo | State what can no longer be measured and the replacement plan |
| Public check fails | Mark validation state; repair and record again | Distinguish a tool regression from scientific-conclusion risk |
| Provenance, license, security, or ethics concern | Stop distributing relevant material, preserve evidence, escalate | State material scope, temporary restriction, and next review |
| Overstated training conclusion | Narrow or withdraw language; add a boundary | Do not treat prior publication as a reason to keep propagating it |

An incident is closed only when a human owner approves it and the record includes a timeline, blast radius, correction, revalidation, and prevention measure. An agent may collect evidence and draft text, but cannot alone declare a case safe, valid, or closed.

## 6. Smallest useful next steps

1. Create a brief `CASE_FILE.md` for the current LLM4SBR case, stating Open Demo status, provenance, version, public validation, and known boundaries.
2. Preserve commands, environments, and results with every release, rather than only the word “passed.”
3. Add a public issue template requiring a minimal reproduction, material license, and impact statement.
4. Do not claim or publish a Blind Challenge until there is an independent evaluator environment, frozen scoring rules, and maintenance capacity.
