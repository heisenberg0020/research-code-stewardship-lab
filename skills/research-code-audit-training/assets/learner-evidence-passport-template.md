# Evidence Passport — [[TARGET_ID]]

**Exercise:** [[TARGET_TITLE]]

Replace every double-braced prompt. This worksheet records your auditable
argument. A structural check cannot determine whether the argument is true,
scientifically sufficient, or evidence of a maturity band.

## 1. Decision identity and uncertainty

- Learner recommendation: {{accept, reject, block, narrow, or needs-evidence}}
- Artifact revision or run identity: {{commit, manifest, dataset, run, or record ID}}
- What is directly observed: {{facts separated from interpretation}}
- What remains unknown: {{unknowns and the evidence needed to resolve them}}

## 2. First broken contract

- Earliest failed contract or invariant: {{precise contract and boundary}}
- Why this is the first break rather than a downstream symptom: {{boundary reasoning}}
- Competing explanation: {{credible alternative hypothesis}}

## 3. Evidence chain

- Exact source locations: {{file, line, key, event, run, or record IDs}}
- Minimal reproduction or audit procedure: {{bounded repeatable procedure}}
- Independent evidence or recomputation: {{second evidence path and result}}
- Negative or inconclusive evidence retained: {{result that did not support the hypothesis}}

## 4. Why the artifact remains plausible

{{Explain how the code, pipeline, result, or Agent record can still run, look normal,
or produce persuasive output despite the suspected failure.}}

## 5. Causal effect and claim boundary

- Immediate effect: {{direct causal effect}}
- Affected and possibly affected artifacts or runs: {{bounded blast radius}}
- Direction and magnitude: {{supported estimate, or Unknown with reason}}
- Permitted claim now: {{claim that remains supportable}}
- Claim that must be narrowed, withdrawn, or blocked: {{unsupported boundary}}

## 6. Delegation and human checkpoints

- Human-only judgment retained: {{decision the human owner must make}}
- Agent task and allowed scope: {{bounded delegated task and allowed paths or data}}
- Acceptance, stop, and escalation conditions: {{observable conditions}}
- Independent review of Agent output: {{how a human will verify the result}}

## 7. Safe response and regression evidence

- Immediate containment: {{smallest safe stop, isolation, or preservation action}}
- Durable repair or governance action: {{change proposed after evidence review}}
- Regression or revalidation evidence: {{tests, reruns, comparisons, or approvals}}
- Residual risk, owner, and revisit condition: {{named declared owner and trigger}}

## 8. Stakeholder communication

{{Write a short update that separates confirmed facts, impact, uncertainty, current
decision, owner, and next checkpoint without overstating the evidence.}}
