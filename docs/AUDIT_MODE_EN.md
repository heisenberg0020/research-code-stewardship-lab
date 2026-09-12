# Mode Audit: a real research-audit loop

> **Status: implemented canonical CLI.** Mode Audit manages a local evidence lifecycle for one clean Git project. It does not execute project code, use the network, modify the target project, or produce a scientific verdict.

[中文](AUDIT_MODE.md) · [Dual-mode roadmap](DUAL_MODE_ROADMAP_EN.md) · [G0 and competency model](COMPETENCY_MODEL_EN.md)

## Non-negotiable boundaries

- An audit binds to a **specific Git `HEAD` commit**, not an approximate current directory state.
- `PROJECT` must be a clean Git worktree; `WORKSPACE` must live outside the project directory, and the `init` output path must not exist.
- By default, RCSL reads only the target project and Git metadata. All new records are written only to `WORKSPACE`.
- G0 is a **declarative research contract** completed, reviewed, and recorded by a human. `--actor` and `--reviewer` are local traceability labels, **not** identity authentication, signatures, or access control.
- Running code, using the network, accessing additional/protected material, changing source, or using a larger budget requires another explicitly authorized tool flow. Mode Audit never performs those actions implicitly.

Confirm the project state first:

```bash
PROJECT="/absolute/path/to/clean-git-project"
git -C "$PROJECT" status --porcelain   # must produce no output
git -C "$PROJECT" rev-parse --verify HEAD
```

## Lifecycle and local artifacts

```text
clean Git commit + G0 draft
→ completed contract + named approved gate
→ preflight
→ findings / evidence / reasoned transitions
→ local verify + rendered review report
```

`audit init` creates these public templates and sets the G0 gate to `draft`:

| Local artifact | Purpose |
| --- | --- |
| `research-contract-template.md` | G0: scope, provenance/rights, permitted claims, authority, budget, and stop conditions |
| `evidence-passport-template.md` | One finding’s location, contract, evidence chain, causal impact, and limit |
| `triage-card-template.md` | Signal, blast radius, minimum decisive evidence, and next safe action |
| `delegation-contract-template.md` | What an agent may/may not do, acceptance criteria, budget, and human checkpoints |
| Local snapshots, event ledger, and report | Updated current metadata/finding snapshots, appended lifecycle events, and a readable handoff result |

## Exact CLI reference

Below, `rcsl` denotes the CLI (for example, run `python scripts/rcsl.py` from the repository root).

| Command | Purpose and key prerequisite | What it does not mean |
| --- | --- | --- |
| `rcsl train overview`; `rcsl train doctor`; `rcsl train start --level 1..4`; `rcsl train validate` | Mode Train curriculum navigation, environment diagnosis, per-level entry, and public checks | Training a model or issuing a scientific verdict |
| `rcsl audit init --project PROJECT --output WORKSPACE --level 1..4 --actor ACTOR [--reason TEXT]` | Rejects dirty/non-Git projects and in-project workspaces; binds clean `HEAD`; creates G0 `draft` | Authenticating an actor, executing the project, approving G0, or accepting any conclusion |
| `rcsl audit status WORKSPACE [--json]` | Reads binding, G0, finding, ledger, and preflight summary | Validating scientific correctness |
| `rcsl audit lint WORKSPACE` | Reports complete only when **all four templates** have required headings and no unresolved `{{...}}` | Approving G0 or deciding a finding holds |
| `rcsl audit gate check WORKSPACE [--json]` | Checks research-contract completeness and whether its current bytes match the recorded gate | Granting authority or authenticating a reviewer |
| `rcsl audit gate record WORKSPACE --decision draft\|approved\|blocked --reviewer REVIEWER --rationale TEXT [--actor ACTOR]` | Records a named human G0 decision; reviewer label is used when `--actor` is absent | Verifying identity, rationale truthfulness, or scientific conclusion |
| `rcsl audit preflight WORKSPACE [--json]` | Requires a **complete research contract + `approved` gate for current bytes + clean, non-drifted `HEAD` + consistent ledger** | Executing code, using the network, or proving research correctness |
| `rcsl audit rebaseline WORKSPACE --actor ACTOR --reason TEXT` | Explicitly binds a new clean `HEAD`; resets G0 to `draft` and marks old findings stale | Migrating old evidence to the new commit or closing old findings |
| `rcsl audit finding add WORKSPACE --id ID --title TEXT --layer L1\|L2\|L3\|L4\|cross-cutting --competency C1..C7 --severity critical\|high\|medium\|low\|info --claim TEXT --first-contract TEXT --actor ACTOR` | Records an `open` finding on a current baseline that passed preflight | Proving the claim is true |
| `rcsl audit finding list WORKSPACE [--json]` | Shows current finding snapshots | Reassessing their scientific sufficiency |
| `rcsl audit finding transition WORKSPACE --finding ID --to open\|triaged\|accepted\|mitigated\|verified\|closed\|dismissed\|blocked --actor ACTOR --rationale TEXT` | Appends a legal, reasoned lifecycle transition | Erasing prior records or automatically calling a repair trustworthy |
| `rcsl audit evidence add WORKSPACE --finding ID --id ID --kind asserted\|observed\|derived\|reproduced\|contradicted --reference TEXT --summary TEXT --actor ACTOR` | Appends typed evidence on a current baseline that passed preflight | Proving evidence sufficient, independent, or unbiased |
| `rcsl audit verify WORKSPACE [--json]` | Checks local metadata, snapshots, and hash-chain consistency | Verifying remote history, identity, or scientific conclusion |
| `rcsl audit report build WORKSPACE --output PATH [--format markdown\|json]` | Creates one non-existing Markdown/JSON review record directly in the workspace root (Markdown by default); refuses subdirectories, external paths, and filenames matching `.rcsl-write.lock`, `audit-workspace.json`, `audit-events.jsonl`, or any of the four templates case-insensitively | Creating a scientific PASS or release approval |

### G0, lint, and preflight are different

1. After `init`, G0 is always `draft`.
2. `lint` is `COMPLETE` only after all four templates are completed; it remains a structural check.
3. `gate record --decision approved` is recordable only after `research-contract-template.md` is complete, and binds the decision to the current contract bytes.
4. `preflight` requires a **complete research contract plus current approved gate**, and also a clean non-drifted target `HEAD` and a consistent ledger. It does not require every finding to be scientifically decided.
5. `finding add` and `evidence add` require preflight. Entering `verified` (and therefore later `closed`) requires evidence, a current baseline, and passing preflight.

## Minimum copyable E2E flow

This block creates an empty temporary Git fixture and completes the record lifecycle. It does not run the audited project or use the network, and it is not a real scientific audit. For a real project, a human must complete all four templates honestly rather than use the synthetic values below.

```bash
# Run from the RCSL repository root. The temporary directory is retained for inspection.
rcsl() { python scripts/rcsl.py "$@"; }
ROOT="$(mktemp -d "${TMPDIR:-/tmp}/rcsl-audit-e2e.XXXXXX")"
PROJECT="$ROOT/project"
WORKSPACE="$ROOT/workspace"

mkdir "$PROJECT"
git -C "$PROJECT" init -q
printf '# RCSL audit E2E fixture\n' > "$PROJECT/README.md"
git -C "$PROJECT" add README.md
git -C "$PROJECT" -c user.name='RCSL E2E' -c user.email='rcsl-e2e@example.invalid' \
  commit -qm 'initial fixture'

rcsl audit init --project "$PROJECT" --output "$WORKSPACE" --level 2 \
  --actor 'E2E Auditor' --reason 'Temporary clean Git lifecycle test.'

# Fill public templates only for this temporary E2E fixture. Real audits need real human content.
WORKSPACE="$WORKSPACE" python - <<'PY'
import os
import re
from pathlib import Path

workspace = Path(os.environ["WORKSPACE"])
for path in workspace.glob("*-template.md"):
    text = path.read_text(encoding="utf-8")
    path.write_text(
        re.sub(r"\{\{[^{}\n]+\}\}", "Synthetic bounded fixture value", text),
        encoding="utf-8",
    )
PY

rcsl audit lint "$WORKSPACE"
rcsl audit gate record "$WORKSPACE" --decision approved \
  --reviewer 'E2E Research Owner' --actor 'E2E Auditor' \
  --rationale 'Completed temporary contract reviewed for the bounded fixture.'
rcsl audit gate check "$WORKSPACE" --json
rcsl audit preflight "$WORKSPACE" --json

rcsl audit finding add "$WORKSPACE" --id F-001 \
  --title 'Checkpoint lineage requires review' --layer L2 --competency C2 \
  --severity medium \
  --claim 'The reported model may not match the declared checkpoint lineage.' \
  --first-contract 'Each reported run must identify the evaluated checkpoint.' \
  --actor 'E2E Auditor'
rcsl audit evidence add "$WORKSPACE" --finding F-001 --id E-001 --kind observed \
  --reference 'README.md@HEAD' \
  --summary 'The temporary fixture records an observation for lifecycle testing.' \
  --actor 'E2E Auditor'

rcsl audit finding transition "$WORKSPACE" --finding F-001 --to triaged \
  --actor 'E2E Auditor' --rationale 'Signal has been scoped.'
rcsl audit finding transition "$WORKSPACE" --finding F-001 --to accepted \
  --actor 'E2E Auditor' --rationale 'The bounded finding is accepted for mitigation.'
rcsl audit finding transition "$WORKSPACE" --finding F-001 --to mitigated \
  --actor 'E2E Auditor' --rationale 'Mitigation record is ready for verification.'
rcsl audit preflight "$WORKSPACE"
rcsl audit finding transition "$WORKSPACE" --finding F-001 --to verified \
  --actor 'E2E Research Owner' --rationale 'Evidence exists and the current baseline passes preflight.'
rcsl audit finding transition "$WORKSPACE" --finding F-001 --to closed \
  --actor 'E2E Research Owner' --rationale 'Verified temporary finding formally closed.'

rcsl audit verify "$WORKSPACE" --json
rcsl audit finding list "$WORKSPACE" --json
rcsl audit report build "$WORKSPACE" --output "$WORKSPACE/review.md" --format markdown
rcsl audit status "$WORKSPACE" --json
echo "Inspect the temporary workspace: $WORKSPACE"
```

To continue with a real project at a new commit, review the change first, then:

```bash
rcsl audit rebaseline "$WORKSPACE" --actor 'Research Owner' \
  --reason 'Reviewed a deliberate upstream commit change; prior evidence stays attached to its old baseline.'
```

Rebaseline makes old findings `stale` and resets G0 to `draft`. Complete the research contract again, record a new `approved` gate, and pass preflight before adding findings or evidence for the new baseline.

## Working rules for findings and evidence

1. **Triage before asserting.** An `open` finding is a claim to audit. When evidence is insufficient, use `blocked`, `dismissed`, or retain it for later review; do not write a hypothesis as a proven violation.
2. **Classify by the first failed contract.** L1 semantics, L2 pipeline, L3 scientific validity, L4 agent governance. Effects can cross layers, but the primary classification must not double count them.
3. **One finding, one causal chain.** `claim` and `first-contract` should make location, rule, impact, and known limits clear. Evidence attaches only concrete asserted/observed/derived/reproduced/contradicted records.
4. **Record; do not hand-edit history.** The CLI refreshes current metadata/finding snapshots and appends gate, transition, evidence, and rebaseline rationale to the event ledger. Correct old conclusions through a new lifecycle action, not by editing JSON/JSONL directly.
5. **Terminal states have extra gates.** `open → triaged → accepted → mitigated → verified → closed` is one legal example path. `verified`/`closed` require evidence, a current baseline, and preflight; intermediate states cannot be skipped.

## Honest meaning of status words

| Status | It may say | It must never say |
| --- | --- | --- |
| `structure` | The four templates meet lint’s format and placeholder requirements | A finding is true or a conclusion is correct |
| `ledger` | Retained local events, metadata, and finding snapshots have internally consistent hash relationships | History was not deleted/replaced or witnessed by a trusted third party |
| `current` | The target worktree is clean and `HEAD` matches the active baseline | Code is faithful, experiment is fair, or risk-free |
| `review-ready` | Current G0, Git baseline, and ledger pass preflight, and the report has no stale finding from an older baseline; human reading can begin | `lint` completed, any finding/evidence exists, findings reached closure, evidence is sufficient, or a reviewer, PI, or independent reproduction substantively approved the conclusion |

`structure`, `ledger`, `current`, and `review-ready` describe records and process only. **They—and `audit lint` and `audit verify`—are not a scientific PASS.**

## Limits of hash chains, identity, and security

A local hash chain only makes edits, reorderings, or breaks easier to notice in **local history that is still retained**. It cannot:

- authenticate an `--actor`, `--reviewer`, timestamp, or approval source;
- prevent a local writer from deleting records, replacing a workspace, or recomputing a new chain;
- prove that remote Git history, external files, command output, or cited content was not changed; or
- provide access control, confidentiality, legal compliance, or scientific validity.

One lifecycle action updates a snapshot and appends an event; these writes are not a cross-file database transaction. If a process, disk, or machine fails partway through a multi-file update, the next `verify` fails closed and the workspace may retain `.rcsl-write.lock`. Preserve/back up the state and inspect it manually; do not “repair” history by editing JSON or recomputing hashes.

Stronger assurance needs separate controlled storage, code-host audit records, signatures, independent review, and organizational policy. Those capabilities must not be described as default CLI protections.

## When to stop and escalate

Retain the record already gathered and use `blocked`, or stop for a human decision, when:

- the research contract lacks permitted scope, data rights, budget, protection boundary, or claim limit;
- the project is dirty, not Git, or the workspace is inside it;
- work requires project execution, network use, protected material, source changes, or a larger budget;
- there is potential secret/privacy exposure, unclear licensing, protected-evaluation leakage, or a high-impact claim; or
- evidence supports only “unknown,” not a stronger finding state.

A good Mode Audit result is sometimes a pause, narrowed claim, or request for approval. It never substitutes “the project ran” for a research owner’s final decision about trust and release.
