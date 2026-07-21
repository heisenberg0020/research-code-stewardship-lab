# Quality gates and correction playbook

## Candidate validity

- Exactly five candidates per level: one trusted and four singleton faults.
- Every public import, schema, smoke, and bounded execution succeeds.
- Every fault is causally tied to its rule and repair.
- Repairing the documented mutation makes all hidden probes pass without unrelated changes.
- Unexpected exceptions fail the harness; probes do not use blanket exception-to-rule conversion.
- Each faulty candidate has one primary fault and no accidental dtype, empty-input, device, or indexing bug.

## Anti-guessing and anti-leakage

- Trusted letters differ across levels and have no obvious sequence.
- Student files contain no mapping, rule-to-letter text, repair spans, or hidden imports.
- Public output does not rank metric values.
- Candidate file counts, APIs, comments, line counts, and formatting are comparable.
- At each Level 1 semantic site, use distinct equivalent forms and harmless decoys; no simple local marker or majority vote identifies the trusted candidate.
- The trusted implementation is not uniquely shortest or the textual/AST center.
- Hidden probes infer from behavior/artifacts, never candidate names.
- Search generated reports, progress logs, tests, and docs as well as the exercise folder for leaked mappings.

## Evidence quality

- Level 1 probes isolate one mathematical property at a time.
- Level 2 findings require identity/state evidence across at least two artifacts or files.
- Level 3 findings cite structured keys and run IDs; prose is explanatory only.
- Level 4 findings cite rule ID, event ID, protocol clause, approval ID or null, and evidence IDs.
- Impact direction is stated only when derivable; otherwise mark it unknown.

## Boundary cases learned from implementation review

- Test integer-valued floating targets when public APIs plausibly accept them; convert to an integer dtype before cross entropy.
- Distinguish a missing key from an allowed JSON null or CSV blank. Do not reuse a strict nonblank helper for nullable governance fields.
- Materialize iterables of required keys before validating multiple rows; generators otherwise validate only the first record.
- Treat empty and whitespace-only required strings as missing.
- Preserve full-population metric rows, including explicit zero-valued misses.
- Base split isolation on the raw independent entity before prefix/window expansion.
- Base checkpoint selection on validation evidence, with protected evaluation after selection and only as specified.
- Rebuild report manifests from the complete ledger, not from the report itself.
- Classify protected leakage only when protected event IDs flow into adaptive actions; reporting and discussion are not adaptive.

## TDD evidence requirements

For every task, retain:

1. command and exact RED cause;
2. focused GREEN command and test count;
3. combined regression command and test count;
4. implementation file list;
5. self-review and known concerns;
6. independent review verdict and follow-up RED/GREEN evidence.

Do not accept a RED caused by an unrelated import, syntax, or test-harness error. Do not accept GREEN without fresh execution.

## Final rejection conditions

Reject or revise the package if:

- public checks identify the answer;
- hidden probes classify infrastructure failures as scientific faults;
- any candidate has a compilation or obvious shape failure;
- any level lacks an independent reference computation;
- a trusted candidate contains a second semantic defect;
- a candidate's result magnitude exposes its role;
- original source/paper hashes changed;
- runs require undeclared network, GPU, model, or data access;
- repeated runs are nondeterministic without a documented reason.
