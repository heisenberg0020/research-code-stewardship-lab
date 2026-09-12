# Real-project audit workflow

Use this workflow when the user wants to audit and manage evidence for an
existing research-code project. Do not enter the candidate-generation workflow
unless the user separately asks to turn the project into a training case.

## Authority boundary

- Bind the audit to one clean Git worktree and one exact `HEAD` revision.
- Keep the audit workspace outside the target project.
- Treat the target project as read-only. The RCSL lifecycle CLI reads Git
  metadata but does not execute project code, use the network, or modify the
  target.
- Treat actor and reviewer names as declared labels, not authenticated
  identities or signatures.
- Stop for explicit human authorization before running project code, accessing
  external data or services, changing the project, or widening the declared
  budget or claim.
- Never inspect a directory named `DO_NOT_OPEN_UNTIL_FINISHED` while auditing a
  public training repository.

## Closed-loop sequence

From the RCSL repository root, use the canonical command family:

```bash
python scripts/rcsl.py audit init \
  --project /absolute/path/to/clean-project \
  --output /absolute/path/outside-project/audit-workspace \
  --level 2 \
  --actor "declared auditor"
```

Then follow this order:

1. Complete the four public Markdown templates. The research contract is the
   G0 gate; the other templates retain triage, delegation, and evidence context.
2. Use `audit lint WORKSPACE` for structural completeness. This is not a
   scientific assessment.
3. Use `audit gate check WORKSPACE`, then have a named human record `draft`,
   `approved`, or `blocked` with `audit gate record`. Approval is bound to the
   current research-contract bytes.
4. Use `audit preflight WORKSPACE`. It requires a consistent local ledger, the
   approved current contract, a clean worktree, and the same Git `HEAD` and
   branch as the active baseline.
5. Record findings with `audit finding add`. Supply a stable ID, L1–L4 or
   cross-cutting layer, C1–C7 competency, severity, precise claim, first broken
   contract, and actor.
6. Add typed evidence with `audit evidence add`. Use one of `asserted`,
   `observed`, `derived`, `reproduced`, or `contradicted`, plus a stable evidence
   ID, source reference, summary, and actor.
7. Move a finding only through the declared lifecycle with `audit finding
   transition`. `verified` and `closed` require evidence, a current finding
   baseline, an approved G0 contract, and successful preflight. These states
   describe recorded review, not scientific truth.
8. Use `audit verify WORKSPACE` to check retained local metadata, current
   finding snapshots, event order, and hash-chain consistency. A person with
   local write access can still replace the whole workspace and recompute a new
   chain; this is not external immutability.
9. Build a non-overwriting report directly in the workspace root with `audit
   report build`. The output must not use `.rcsl-write.lock`, workspace metadata,
   the event log, or a template filename (matched case-insensitively); nested and
   external output paths are refused. A `review-ready` report means current
   G0/baseline/ledger preflight passed and no finding is stale. It is only ready
   to begin human inspection; it does not require complete lint, any finding or
   evidence, a closed lifecycle, or scientific support.

Use `python scripts/rcsl.py audit --help` and each subcommand's `--help` for the
complete argument list.

## Change and incident rules

- If the project becomes dirty or its `HEAD`/branch changes, stop attribution to
  the old baseline. Review the change, restore the declared revision, or use
  `audit rebaseline WORKSPACE --actor ... --reason ...` on a clean worktree.
- Rebaseline creates a new baseline ID and resets G0 to `draft`. Existing
  findings remain attached to the old baseline and are reported as stale.
- Do not edit JSON snapshots or the JSONL event history by hand. A later
  mutation must refuse an inconsistent ledger rather than blessing it.
- Snapshot and event writes are not a cross-file database transaction. If an
  interrupted mutation leaves an inconsistent workspace or `.rcsl-write.lock`,
  preserve and inspect the state; do not erase the lock or recompute history
  until the interruption is understood.
- Record a hypothesis as `open` or `triaged`; do not advance it merely because
  a tool produced output. Preserve competing explanations and limitations in
  the Markdown evidence passport and the finding's claim/evidence fields.
- A blocked audit, narrowed claim, or explicit unknown can be a correct handoff.

## Meaning of automated states

- `STRUCTURE=COMPLETE`: expected fields and headings are present.
- `READY FOR DECLARED SCOPE`: the local G0, contract digest, Git baseline, and
  ledger prerequisites are current.
- `LEDGER=CONSISTENT`: the retained local snapshots and hash-linked events agree.
- `REVIEW-READY`: current G0/baseline/ledger preflight passed and no finding is
  stale, so human reading can begin; it requires neither complete lint, findings,
  evidence, nor lifecycle closure.

None of these means paper fidelity, experimental fairness, legal compliance,
security, successful reproduction, release approval, or scientific correctness.
