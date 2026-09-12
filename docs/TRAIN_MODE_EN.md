# RCSL Mode Train: Local Progress and Human Review

[中文](TRAIN_MODE.md) · [Course hub](../LLM4SBR_research_audit_training_v2/README.md) · [Competency model](COMPETENCY_MODEL_EN.md) · [Mode Audit](AUDIT_MODE_EN.md)

Mode Train uses the public LLM4SBR Open Demo to practice research-code audit. It keeps the L1–L4 Evidence Passports, cross-layer capstone, retries, and human feedback in a learner-owned local workspace. The core workflow uses only the Python standard library and can be paused and resumed offline after creation.

> **Important boundary:** automated checks assess Markdown structure only. They do not read instructor material, judge meaning, scientific correctness, or maturity, or authenticate a learner or reviewer. The current public case uses honor isolation; it is not a security-isolated Blind Challenge.

## 1. Create an external learning workspace

Run from the repository root:

```bash
python scripts/rcsl.py train progress init \
  --output /absolute/path/to/my-rcsl-progress \
  --learner "your declared label"
```

`--output` must be a nonexistent directory outside this repository and outside every `DO_NOT_OPEN_UNTIL_FINISHED` path. The command refuses to overwrite an existing path or follow a workspace symlink.

The new workspace contains:

```text
my-rcsl-progress/
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

- `worksheets/*.md` are editable drafts.
- `RUBRIC.md` and `CAPSTONE_BRIEF.md` are fixed reference files; changing them invalidates workspace verification.
- `progress.json` is the authoritative record. It contains frozen submission snapshots, human-review history, and local operation-deduplication records. Do not edit it by hand.

## 2. Complete and check an Evidence Passport

The recommended order is L1, L2, L3, L4, then the capstone; the CLI does not replace learning judgment with automatic unlock rules. Read the corresponding public brief and frozen contract, then edit the matching workspace worksheet. For example, after completing L1, run:

```bash
python scripts/rcsl.py train progress check \
  /absolute/path/to/my-rcsl-progress --target L1
```

The target is `L1`, `L2`, `L3`, `L4`, or `capstone`. `check` reports missing sections, empty sections, and unresolved template prompts. It exits `0` for structurally complete and `1` for incomplete. Even when it reports `COMPLETE`, semantic assessment, scientific correctness, and maturity remain `NOT PERFORMED` / `NOT ASSESSED`.

For machine-readable output:

```bash
python scripts/rcsl.py train progress check \
  /absolute/path/to/my-rcsl-progress --target L1 --json
```

## 3. Freeze a submission and retry

Once the worksheet is structurally complete, freeze its exact bytes as an immutable attempt:

```bash
python scripts/rcsl.py train progress submit \
  /absolute/path/to/my-rcsl-progress \
  --target L1 \
  --note "first evidence-chain attempt"
```

Submission returns an attempt ID such as `L1-A001` and a SHA-256 digest, but its state is only `AWAITING HUMAN REVIEW`. Later edits do not rewrite that snapshot. A second submission creates `L1-A002` with `retry_of` pointing to the previous attempt. The new attempt keeps the history but does not inherit an active human conclusion from the previous attempt.

Scripts or uncertain retries may supply a stable `--operation-id`:

```bash
python scripts/rcsl.py train progress submit \
  /absolute/path/to/my-rcsl-progress \
  --target L1 \
  --note "first evidence-chain attempt" \
  --operation-id submit-l1-v1
```

The same operation ID with exactly the same operation content returns the original result. Reusing it for different content is refused.

## 4. Record a named human review

The reviewer should inspect the frozen attempt and `RUBRIC.md`, then record a declared human judgment:

```bash
python scripts/rcsl.py train progress review \
  /absolute/path/to/my-rcsl-progress \
  --target L1 \
  --attempt latest \
  --reviewer "reviewer label" \
  --decision revise \
  --recognize demonstrated \
  --prove partial \
  --direct cannot-assess \
  --steward cannot-assess \
  --rationale "The first break is identified, but causal proof is incomplete." \
  --strengths "Precise location and a plausible competing hypothesis." \
  --gaps "Add an independent recomputation and bound the claim impact."
```

Each band observation is `not-observed`, `partial`, `demonstrated`, or `cannot-assess`; the decision is `pass`, `revise`, or `blocked`. The CLI checks record consistency only:

- An L1–L4 `pass` must declare Recognize and Prove as `demonstrated`.
- A capstone `pass` must declare Recognize, Prove, Direct, and Steward as `demonstrated`.
- Neither rule proves that the judgment is true or sufficient. The capstone still passes only after actual human review.

One attempt may retain records from multiple reviewers. The system does not average disagreement: conflicting current decisions appear as `review-disagreement` for human explanation or adjudication. A later record from the same reviewer becomes that reviewer's current record; earlier records remain in history.

## 5. Inspect, pause, and resume

```bash
python scripts/rcsl.py train progress status \
  /absolute/path/to/my-rcsl-progress
```

`status` keeps these meanings separate for every target:

| Dimension | Meaning |
| --- | --- |
| `attempt` | Whether a frozen submission exists |
| `structure` | Whether the current editable worksheet is structurally complete |
| `human-review` | Whether the latest attempt awaits review, needs revision, is blocked, is human-passed, or has disagreement |
| `draft_changes_since_submission` | Whether the current draft differs from the latest frozen attempt (JSON output) |
| `evidence_gaps` | Gaps explicitly recorded by current human reviews |

Close the workspace at any time and continue with `status`, `check`, `submit`, or `review`. `status` exits successfully for a valid but incomplete workspace because incomplete learning is not a file error. Add `--json` for the stable machine-readable summary.

The overall state becomes `human-reviewed-complete` only when the latest attempt for every one of the five targets is `human-passed` and there are no unsubmitted edits made after a reviewed attempt. If such edits exist, the state explicitly becomes `human-reviewed-complete-with-unsubmitted-draft`; the human conclusion remains bound to the older attempt digest. Neither state is scientific certification.

## 6. Complete the cross-layer capstone

After L1–L4, read `CAPSTONE_BRIEF.md` in the workspace and respond to the public synthetic research incident in `worksheets/capstone.md`. The response covers a G0 stop/continue decision, blast radius, L1–L4 first-failed contracts, evidence preservation and competing hypotheses, Human–Agent delegation, claim/release boundaries, remediation verification, stakeholder communication, and human sign-off.

The capstone uses the same check and submission flow:

```bash
python scripts/rcsl.py train progress check \
  /absolute/path/to/my-rcsl-progress --target capstone
python scripts/rcsl.py train progress submit \
  /absolute/path/to/my-rcsl-progress --target capstone
```

Structural completeness does not pass the capstone. A named human must separately record `pass`, with all four maturity-band observations explicitly declared `demonstrated`.

## 7. Export a shareable summary

The output must remain inside the workspace, its parent must already exist, and it must not overwrite an existing or reserved file:

```bash
python scripts/rcsl.py train progress export \
  /absolute/path/to/my-rcsl-progress \
  --output /absolute/path/to/my-rcsl-progress/progress-report.md \
  --format markdown
```

`--format` is `markdown` or `json`. The export omits the learner label, worksheet snapshots, and free-form feedback/gap text that may contain identity data; it retains only whether a gap was recorded. Reviewer labels become aliases such as `reviewer-1`. Structure state, the latest submission digest, current human decisions, and maturity observations remain. Full feedback stays local in `progress.json` and `status --json`. The export is a readable record, not a certificate, signature, or scientific `PASS`.

## Record and trust boundaries

- `progress.json` is atomically replaced in one write, with a local exclusive lock to prevent concurrent writers. If a lock is left behind unexpectedly, first confirm that no writer is active and then follow the error guidance.
- Workspace loading strictly checks the schema, fixed-resource digests, frozen-snapshot digests, attempt/review references, and declared consistency. It refuses an invalid record.
- These are local consistency controls, not externally immutable storage. Anyone able to write the workspace can still replace the complete history.
- `--learner` and `--reviewer` are declared labels, not login identities, digital signatures, or authority proofs.
- `train validate` checks the repository's public training package. `train progress check` checks one workspace worksheet. Neither judges scientific correctness.
