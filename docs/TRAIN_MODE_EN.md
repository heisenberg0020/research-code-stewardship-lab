# RCSL Mode Train: Local Progress and Human Review

[中文](TRAIN_MODE.md) · [Course hub](../LLM4SBR_research_audit_training_v2/README.md) · [Competency model](COMPETENCY_MODEL_EN.md) · [Mode Audit](AUDIT_MODE_EN.md)

Mode Train uses the public LLM4SBR Open Demo to practice research-code audit. It keeps the L1–L4 Evidence Passports, cross-layer capstone, retries, and human feedback in a learner-owned local workspace. The core workflow uses only the Python standard library and can be paused and resumed offline after creation.

This version freezes what the learner can actually see in an explicit case manifest: new workspaces currently include 122 public Open Demo inputs, each with exact bytes, size, and SHA-256 digest. It does not traverse or read instructor or post-completion material. Later verification uses the workspace's retained manifest and bytes, not a newer live source-file list; adding case files to the repository does not rewrite an old attempt. Attempts, rubric, and human reviews refer to this content-bound case. Repository `HEAD` is limited provenance, not case identity. Only synthetic automated testing has occurred, not a real learner–independent reviewer pilot, so the assurance ceiling remains `internally verified`.

> **Important boundary:** worksheet checks assess Markdown structure only; case and packet verification check retained bytes and references only. They do not read instructor material, judge meaning, scientific correctness, or maturity, or authenticate a learner or reviewer. The current public case uses honor isolation; it is not a security-isolated Blind Challenge.

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
├── case/
│   ├── LLM4SBR_research_audit_training_v2/...
│   └── skills/research-code-audit-training/assets/...
└── worksheets/
    ├── L1.md
    ├── L2.md
    ├── L3.md
    ├── L4.md
    └── capstone.md
```

- `worksheets/*.md` are editable drafts.
- `case/` is the frozen copy of the public case made at initialization. Prefer this copy so a reviewer can check the version you actually used; it is not an answer directory and must not be edited. Any change to a bound case byte is rejected on validation. Later repository commits do not silently rewrite an existing workspace.
- `RUBRIC.md` and `CAPSTONE_BRIEF.md` are fixed reference files; changing them invalidates workspace verification.
- `progress.json` is the authoritative record. It contains frozen submission snapshots, human-review history, and local operation-deduplication records. Do not edit it by hand.

An old `schema_version: 1` workspace did not retain the complete public case and cannot establish the exact bytes seen at the time. This version does not silently migrate it by treating today's repository as that historical case. Keep old records as historical reference; create a new v2 workspace and resubmit when content binding is needed.

## 2. Complete and check an Evidence Passport

The recommended order is L1, L2, L3, L4, then the capstone; the CLI does not replace learning judgment with automatic unlock rules. Read the corresponding public brief and frozen contract, then edit the matching workspace worksheet. For example, after completing L1, run:

**The only submit-able answer entry point is the workspace's `worksheets/L1.md` (and equivalent files).** The course package's original `ANSWER_SHEET.md` files remain public learning templates/reference material; `train progress submit` does not read them. Do not maintain competing answers in both locations.

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

After submission, build a non-redacted packet for the chosen attempt inside the workspace, then verify it:

```bash
python scripts/rcsl.py train progress packet build \
  /absolute/path/to/my-rcsl-progress \
  --target L1 --attempt latest \
  --output /absolute/path/to/my-rcsl-progress/L1-A001-review-packet.json
python scripts/rcsl.py train progress packet verify \
  /absolute/path/to/my-rcsl-progress/L1-A001-review-packet.json
```

The packet is self-contained as a single material file: verification needs neither the original case repository nor the learner workspace, but running `verify` still requires a trusted RCSL tool/checkout. It reports the attempt ID, case-content digest, and packet SHA-256. The packet contains `attempt.worksheet_snapshot` (the exact frozen answer) and base64-encoded original bytes for all 122 case materials; base64 is an encoding, not redaction or secrecy. The reviewer should inspect the exact answer, case, and `RUBRIC.md`, decoding case materials as needed, then personally judge evidence, risk, maturity, and decision. Sharing this **non-redacted** packet with another person may disclose the learner's answer or personal information. The workspace owner must choose the recipient and sharing scope; the program sends nothing automatically. Independent byte checking is not an independent scientific judgment or proof of packet authorship.

The packet's `resource_aliases.RUBRIC.md` points to the `skills/research-code-audit-training/assets/maturity-rubric.md` artifact. Decode that item for the exact bytes of the workspace's top-level `RUBRIC.md`; the packet also aliases `CAPSTONE_BRIEF.md`.

The packet SHA-256 is a stable digest of the JSON content, **not** the raw bytes of the pretty-printed `.json` file. Do not substitute a file-level `sha256sum` result for the command's output.

`packet verify` checks consistency among retained materials, the case manifest, and the attempt reference. It does not authenticate their origin or prove that the public-input boundary was complete for teaching; the reviewer must retain a trusted boundary/tool version and judge the scope independently.

To record a declared human judgment, supply the exact packet SHA-256 printed by `verify`; replace the placeholder below:

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
  --gaps "Add an independent recomputation and bound the claim impact." \
  --packet-sha256 PACKET_SHA256_FROM_VERIFY
```

Later edits to the editable worksheet draft do not change an existing attempt's historical packet. Only a resubmission creates a new attempt with a new packet digest. Editing the frozen case materials is refused on verification rather than silently changing a packet. A mismatched digest or one from a different attempt is refused. The digest only shows which frozen packet the review record names; it cannot prove the reviewer read it. Each band observation is `not-observed`, `partial`, `demonstrated`, or `cannot-assess`; the decision is `pass`, `revise`, or `blocked`. The CLI checks record consistency only:

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

After L1–L4, read `CAPSTONE_BRIEF.md` in the workspace and respond to the public synthetic research incident in `worksheets/capstone.md`. Six frozen public artifacts are available under the workspace's `case/LLM4SBR_research_audit_training_v2/capstone_artifacts/`: `change.diff`, `run_config.json`, `run_ledger.csv`, `agent_events.csv`, `approvals.csv`, and `claim_note.md`. Cite precise paths and lines, JSON keys, or row/event IDs rather than guessing from the narrative. These are inspectable leads, not the complete source tree, raw metric rows, or authenticated approvals; request missing evidence explicitly instead of inventing it. The response covers a G0 stop/continue decision, blast radius, L1–L4 first-failed contracts, evidence preservation and competing hypotheses, Human–Agent delegation, claim/release boundaries, remediation verification, stakeholder communication, and human sign-off.

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

`--format` is `markdown` or `json`. The export omits the learner label, worksheet snapshots, and free-form feedback/gap text that may contain identity data; it retains only whether a gap was recorded. Reviewer labels become aliases such as `reviewer-1`. The case-content digest, structure state, latest submission digest, current human decisions, and maturity observations remain. Unlike a non-redacted reviewer packet, this export is a readable summary, not a certificate, signature, or scientific `PASS`. Full feedback stays local in `progress.json` and `status --json`.

### Do not confuse the two export operations

`train progress export` creates a redacted summary for one learner. The case-maintainer command `python scripts/rcsl.py export open-demo ...` creates a separate directory-level public release bundle; the formats are not interchangeable. The latter freezes the public source tree for that build, runs selected checks against the snapshot, binds the exported content with `source_tree_sha256`, and requires an exact root/payload; repository-side verification also checks the trusted verifier and boundary. None of that is a learning-progress record. The former cannot release a case, and the latter is not a personal transcript. Neither creates or certifies a Blind Challenge. The current LLM4SBR case is already public and can only remain an Open Demo. See the [case release model](CASE_RELEASE_MODEL_EN.md) for release boundaries.

## Record and trust boundaries

- `progress.json` is atomically replaced in one write, with a local exclusive lock to prevent concurrent writers. If a lock is left behind unexpectedly, first confirm that no writer is active and then follow the error guidance.
- Workspace loading strictly checks the schema, fixed-resource digests, frozen-snapshot digests, attempt/review references, and declared consistency. It refuses an invalid record.
- The case manifest is an explicit public-file list and local content binding. Packet verification checks only the retained bytes, answer, and references; it does not validate case design, authenticated authority, or scientific conclusions.
- These are local consistency controls, not externally immutable storage. Anyone able to write the workspace can still replace the complete history.
- `--learner` and `--reviewer` are declared labels, not login identities, digital signatures, or authority proofs.
- `train validate` checks the repository's public training package. `train progress check` checks one workspace worksheet. Neither judges scientific correctness.
