# Phase 2 Learning Progress Design

**Status:** implementation specification
**Scope:** local-first learner progress, immutable attempts, human rubric reviews,
and one cross-layer capstone for Mode Train.

## Problem and boundary

The existing curriculum can launch and validate the four public exercises, but it
cannot preserve a learner's work across sessions or distinguish a structurally
complete answer from a human judgment. Phase 2 adds that lifecycle without reading
or copying anything inside `DO_NOT_OPEN_UNTIL_FINISHED`.

The new tooling makes four deliberately separate statements:

1. `attempt_state`: whether a worksheet has been submitted.
2. `structure_state`: whether required public sections are present and no template
   prompt remains.
3. `human_review_state`: the declared decisions of named human reviewers.
4. `exposure_state`: `open-demo-honor-isolation`; never `blind` or
   `verified-unseen` for this public case.

No automatic command judges scientific correctness, grants a maturity level, or
verifies identity. A human `pass` is a declared review bound to immutable attempt
bytes, not certification that a paper or result is correct.

## Authoritative storage

Each learner uses a new directory outside this repository and outside any case or
isolated instructor-material directory:

```text
learning-workspace/
├── README.md
├── RUBRIC.md
├── CAPSTONE_BRIEF.md
├── progress.json
└── worksheets/
    ├── L1.md
    ├── L2.md
    ├── L3.md
    ├── L4.md
    └── capstone.md
```

`progress.json` is the single authoritative mutable file. Every mutation takes an
exclusive lock and replaces this file atomically. It embeds the exact submitted
worksheet text plus SHA-256, so a crash cannot leave an attempt snapshot and an
event ledger disagreeing. Fixed workspace resources record their source hashes and
are checked on every load. Local integrity is not tamper-proofing: anyone who can
rewrite the directory can rewrite its history.

Workspace and public-source files are opened one path component at a time through
directory file descriptors with no-follow flags, then checked as regular files
before their bytes are read. This closes the validation/read symlink race at the
isolation boundary. UTF-8, worksheet size, progress size, and history-count limits
fail closed with a training error rather than a traceback or unbounded load.

The document has these top-level fields:

```json
{
  "schema_version": 1,
  "workspace_type": "rcsl-training-progress",
  "case_id": "rcsl/llm4sbr-research-audit-v2",
  "case_revision": "<source Git revision>",
  "learner_label": "<declared label>",
  "exposure_state": "open-demo-honor-isolation",
  "validator_scope": "structure-only; semantic and scientific assessment not performed",
  "created_at": "<UTC timestamp>",
  "updated_at": "<UTC timestamp>",
  "resources": {"RUBRIC.md": "<sha256>", "CAPSTONE_BRIEF.md": "<sha256>"},
  "targets": {
    "L1": {"worksheet": "worksheets/L1.md", "attempts": [], "reviews": []},
    "L2": {"worksheet": "worksheets/L2.md", "attempts": [], "reviews": []},
    "L3": {"worksheet": "worksheets/L3.md", "attempts": [], "reviews": []},
    "L4": {"worksheet": "worksheets/L4.md", "attempts": [], "reviews": []},
    "capstone": {"worksheet": "worksheets/capstone.md", "attempts": [], "reviews": []}
  },
  "operations": []
}
```

An attempt is append-only and contains a sequential ID, timestamp, optional learner
note, predecessor ID for a retry, worksheet SHA-256, exact worksheet snapshot, and a
structure assessment. A review is append-only and contains a sequential ID, target
attempt ID and digest, reviewer label, decision, four band observations, rationale,
strengths, gaps, and timestamp. Loading fails closed if schema, IDs, references,
hashes, known paths, or fixed resource bytes disagree.

Each mutation also records a caller-supplied or generated operation ID and a payload
digest. Replaying the same ID with the same payload returns the original result;
reusing it for different bytes is refused. This lets a caller safely retry after a
lost response without creating a duplicate attempt or review.

## Worksheet contract

L1–L4 use one learner Evidence Passport template. The target identifier and title
are filled during workspace creation; the learner replaces all remaining
double-braced prompts. The stable required sections are:

1. Decision identity and uncertainty
2. First broken contract
3. Evidence chain
4. Why the artifact remains plausible
5. Causal effect and claim boundary
6. Delegation and human checkpoints
7. Safe response and regression evidence
8. Stakeholder communication

The capstone worksheet has nine required sections covering G0 containment, triage
and blast radius, an L1–L4 first-break map, competing hypotheses, bounded Human–Agent
delegation, claim/release boundary, remediation, stakeholder communication, and
human sign-off. Structural checks report missing sections and template prompts only.
They always emit `semantic_assessment: not_performed`,
`scientific_correctness: not_assessed`, and
`maturity_assessment: not_performed`.

## Human rubric

The stable bands are Recognize, Prove, Direct, and Steward. A reviewer records one
of `not-observed`, `partial`, `demonstrated`, or `cannot-assess` for each band and
explains the judgment. There is no average, percentage, leaderboard, or automatic
band inference.

To prevent internally contradictory records, the CLI accepts a `pass` declaration
for L1–L4 only when Recognize and Prove are declared `demonstrated`; a capstone
`pass` requires all four bands declared `demonstrated`. This validates the review
record's internal consistency, not whether its judgment is true.

Every reviewer history is preserved. For the latest attempt, the latest review from
each reviewer is active. Mixed active decisions become `review-disagreement`; they
are not averaged or silently overwritten. A retry creates a new attempt linked to
the prior attempt; prior reviews stay historical and the new attempt begins
`awaiting-human-review`.

## CLI

Existing `train overview`, `doctor`, `start`, and `validate` remain unchanged. New
commands are grouped under `train progress`:

```text
rcsl train progress init --output DIR --learner LABEL
rcsl train progress check DIR --target L1|L2|L3|L4|capstone [--json]
rcsl train progress submit DIR --target ... [--note TEXT]
rcsl train progress review DIR --target ... --reviewer LABEL --decision ...
  --recognize ... --prove ... --direct ... --steward ...
  --rationale TEXT --strengths TEXT --gaps TEXT [--attempt latest|ID]
rcsl train progress status DIR [--json]
rcsl train progress export DIR --output FILE --format markdown|json
```

`check` exits 0 only when the current worksheet is structurally complete and 1 when
it is incomplete. `status` exits 0 for any valid workspace regardless of completion.
`submit` refuses incomplete worksheets. `review` refuses unknown or altered
attempts. `export` is non-overwriting, remains inside the workspace, excludes full
worksheet snapshots, learner labels, and free-form review text, pseudonymizes
reviewer labels, and exposes whether gaps and reviewer disagreement were recorded.
Fenced code and HTML comments cannot satisfy a required worksheet heading or body.

A human decision remains bound to its frozen attempt digest. If the learner edits a
worksheet after that attempt was reviewed, status and export show
`changed-unsubmitted`; an otherwise complete workspace becomes
`human-reviewed-complete-with-unsubmitted-draft` until the new bytes are submitted
and reviewed.

## Capstone

The public capstone is a synthetic cross-layer incident brief, not L5 and not a
multiple-choice question. It asks the learner to respond to observable symptoms,
preserve evidence, determine first broken contracts across possible L1–L4 layers,
constrain Agent work, bound affected and possibly affected claims, and communicate a
decision. It contains no evaluator answer mapping or private probes. Public tooling
can check its response structure; only a named human review can pass it.

## Verification and non-goals

Tests must cover offline restart, atomic locked writes, immutable retry history,
hash/schema tamper detection, symlink and isolated-path refusal, two-reviewer
disagreement, redacted non-overwriting export, CLI exit codes, and the guarantee
that public checks never inspect instructor-material contents. The existing public
package validator remains the leak boundary.

This phase does not provide secure identity, anti-cheat controls, a verified blind
exam, automatic scientific judgment, hosted synchronization, or evidence that the
course improves real-world research quality.
