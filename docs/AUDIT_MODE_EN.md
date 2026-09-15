# Mode Audit: a real research-audit loop

> **Status: `implemented` + `internally verified`, not `field validated`.** Mode Audit manages a local evidence lifecycle for one clean Git project. It does not execute project code, use the network, modify the target project, or produce a scientific verdict.

[中文](AUDIT_MODE.md) · [Dual-mode roadmap](DUAL_MODE_ROADMAP_EN.md) · [G0 and competency model](COMPETENCY_MODEL_EN.md)

## Non-negotiable boundaries

- An audit binds to a **specific Git `HEAD` commit**. An approved G0 also retains the research-contract bytes and case manifest from that decision; it is not an approximate current directory state.
- `PROJECT` must be a clean Git worktree; `WORKSPACE` must live outside the project directory, the `init` output path must not exist, and its immediate parent directory must already exist and be accessible.
- By default, RCSL reads only the target project and Git metadata. `evidence import` reads only one project or external file you explicitly select. All new records are written only to `WORKSPACE`.
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
→ completed contract + named approved gate + content-bound case
→ preflight
→ findings / explicit file-byte imports / reasoned transitions
→ local verify + rendered review report
```

`audit init` creates these public templates and sets the G0 gate to `draft`. Initialization pins descriptors for the resolved parent and new workspace, writes relative to them with no-follow and exclusive-create semantics, and rechecks the new directory's device/inode identity before finishing. A path replaced or redirected during creation therefore fails closed without overwriting same-named files in the redirect target.

| Local artifact | Purpose |
| --- | --- |
| `research-contract-template.md` | G0: scope, provenance/rights, permitted claims, authority, budget, and stop conditions |
| `evidence-passport-template.md` | One finding’s location, contract, evidence chain, causal impact, and limit |
| `triage-card-template.md` | Signal, blast radius, minimum decisive evidence, and next safe action |
| `delegation-contract-template.md` | What an agent may/may not do, acceptance criteria, budget, and human checkpoints |
| Local snapshots, event ledger, and report | Updated current metadata/finding snapshots, appended lifecycle events, and a readable handoff result |
| Content-addressed case/evidence store | Research-contract bytes at G0 approval and explicitly imported single-file bytes; old cases remain available for local digest checks |

## Exact CLI reference

Below, `rcsl` denotes the CLI (for example, run `python scripts/rcsl.py` from the repository root).

| Command | Purpose and key prerequisite | What it does not mean |
| --- | --- | --- |
| `rcsl train overview`; `rcsl train doctor`; `rcsl train start --level 1..4`; `rcsl train validate` | Mode Train curriculum navigation, environment diagnosis, per-level entry, and public checks | Training a model or issuing a scientific verdict |
| `rcsl audit init --project PROJECT --output WORKSPACE --level 1..4 --actor ACTOR [--reason TEXT]` | Requires an existing immediate parent; rejects dirty/non-Git projects, in-project workspaces, and existing outputs; writes exclusively through pinned parent/workspace descriptors, binds clean `HEAD`, and creates G0 `draft` | Authenticating an actor, executing the project, approving G0, or accepting any conclusion |
| `rcsl audit status WORKSPACE [--json]` | Reads binding, G0, findings, retained local records, and preflight summary; JSON distinguishes `evidence_profile` and `content_binding_state` | Validating scientific correctness |
| `rcsl audit lint WORKSPACE` | Reports complete only when **all four templates** have required headings and no unresolved `{{...}}` | Approving G0 or deciding a finding holds |
| `rcsl audit gate check WORKSPACE [--json]` | Checks research-contract completeness and whether its current bytes match the recorded gate | Granting authority or authenticating a reviewer |
| `rcsl audit gate record WORKSPACE --decision draft\|approved\|blocked --reviewer REVIEWER --rationale TEXT [--actor ACTOR]` | Records a named human G0 decision; `approved` also stores the current contract bytes, Git `HEAD`, and content-bound CaseRef; reviewer label is used when `--actor` is absent | Verifying identity, rationale truthfulness, or scientific conclusion |
| `rcsl audit preflight WORKSPACE [--json]` | Requires a **complete research contract + `approved` gate for current bytes + clean, non-drifted `HEAD` + consistent retained local records** | Executing code, using the network, or proving research correctness |
| `rcsl audit rebaseline WORKSPACE --actor ACTOR --reason TEXT` | Explicitly binds a new clean `HEAD`; resets G0 to `draft` and marks old findings stale | Migrating old evidence to the new commit or closing old findings |
| `rcsl audit finding add WORKSPACE --id ID --title TEXT --layer L1\|L2\|L3\|L4\|cross-cutting --competency C1..C7 --severity critical\|high\|medium\|low\|info --claim TEXT --first-contract TEXT --actor ACTOR` | Records an `open` finding on a current baseline that passed preflight | Proving the claim is true |
| `rcsl audit finding list WORKSPACE [--json]` | Shows current finding snapshots; JSON `case_state` distinguishes current/stale/legacy | Reassessing their scientific sufficiency |
| `rcsl audit finding transition WORKSPACE --finding ID --to open\|triaged\|accepted\|mitigated\|verified\|closed\|dismissed\|blocked --actor ACTOR --rationale TEXT` | Appends a legal, reasoned declared lifecycle transition; new `verified` / `closed` states also require prior `observed` / `derived` / `reproduced` content evidence for the current case | Erasing prior records, independently verifying a repair, or automatically calling it trustworthy |
| `rcsl audit evidence add WORKSPACE --finding ID --id ID --kind asserted\|observed\|derived\|reproduced\|contradicted --reference TEXT --summary TEXT --actor ACTOR` | Stores a text reference and summary for triage and old-record compatibility; it does **not** retain the referenced bytes or satisfy the new terminal content-evidence gate | Proving cited content, sufficiency, independence, or lack of bias |
| `rcsl audit evidence import WORKSPACE --finding ID --id ID --type artifact\|command-result\|environment --kind asserted\|observed\|derived\|reproduced\|contradicted --source-kind project-relative\|external --source-path PATH [--source-ref REF] --summary TEXT --actor ACTOR` | Retains the bytes and digest of **one** explicit regular file, linked to the current CaseRef, ArtifactRef, and RecordRef; see type-specific flags below | Executing commands, authenticating provenance, or judging scientific correctness |
| `rcsl audit verify WORKSPACE [--json]` | Checks consistency of retained local metadata, snapshots, event/RecordRefs, cases, and imported-byte digests | Verifying remote history, identity, original provenance, or scientific conclusion |
| `rcsl audit recover WORKSPACE [--json]` | Explicitly finishes one interrupted commit recorded by `.rcsl-audit-pending.json`, then verifies it; with no pending intent it only verifies and reports clean | Rolling history back, selectively dropping an event, or repairing unknown tampering |
| `rcsl audit report build WORKSPACE --output PATH [--format markdown\|json]` | Exclusive-creates one non-existing Markdown/JSON review record directly in the workspace root (Markdown by default), with mode `0600` on POSIX; pins and rechecks workspace identity and refuses symlinks, subdirectories, external paths, and filenames matching `.rcsl-write.lock`, `.rcsl-audit-pending.json`, `audit-workspace.json`, `audit-events.jsonl`, or any of the four templates case-insensitively | Creating a scientific PASS, signature, or release approval |

### G0, lint, and preflight are different

1. After `init`, G0 is always `draft`.
2. `lint` is `COMPLETE` only after all four templates are completed; it remains a structural check.
3. `gate record --decision approved` is recordable only after `research-contract-template.md` is complete, and binds the decision to the current contract bytes.
4. `preflight` requires a **complete research contract plus current approved gate**, and also a clean non-drifted target `HEAD` and consistent retained local records. It does not require every finding to be scientifically decided.
5. `finding add`, `evidence add`, and `evidence import` require a current baseline and preflight. A new transition into the declared `verified` state (and therefore later `closed`) requires `observed`, `derived`, or `reproduced` **content evidence** for the current case. Text references, `asserted`, and `contradicted` do not satisfy this gate. It does not judge sufficiency, independence, or correctness.

### Importing content evidence: source, type, and human responsibility

For `--source-kind project-relative`, `--source-path` is one path relative to the target-project root (for example, `config/split.yaml`); do **not** add `--source-ref`. It reads an explicit regular file under the anchored project root, but does **not** check whether Git tracks that file or establish that its bytes belong to the recorded `HEAD`. For `--source-kind external`, `--source-path` is an absolute path to one file and `--source-ref` is required as a POSIX-relative logical label (for example, `runs/2026-09-16/split-check.txt`). That label is **not** authenticated provenance, nor is the machine's absolute path a source identity. Both modes require the final selected file to be a regular non-symlink file; neither searches recursively, executes a file, or uses the network. Project-relative parent components must also be non-symlink directories. An external parent-path alias may be resolved once at selection before descriptor anchoring; this is not a promise that no parent-path symlink was ever traversed. Protected directories are never read. Check authorization, licensing, privacy, and whether copying the bytes into the audit workspace is appropriate **before** importing.

Each `--type` requires its own flags: `artifact` uses `--artifact-role TEXT`; `environment` uses `--environment-scope TEXT`; `command-result` uses `--declared-command TEXT --exit-code INT`. The command and exit code are your declarations about a command run **outside this tool**. RCSL never executes it or proves the retained output came from it. `--kind` describes the evidence's reasoning role, not its file type. Use `--summary` to distinguish observed facts, unchecked inferences, and the next human review.

```bash
# Select an actual file you are authorized to review; do not copy the sample path as fact.
rcsl audit evidence import "$WORKSPACE" --finding F-001 --id E-001 \
  --type artifact --artifact-role split-config --kind observed \
  --source-kind project-relative --source-path config/split.yaml \
  --summary 'Retain these config bytes; split outcomes still need human recomputation.' \
  --actor researcher

# One external result file that you generated and reviewed outside RCSL.
rcsl audit evidence import "$WORKSPACE" --finding F-001 --id E-002 \
  --type command-result --kind reproduced --source-kind external \
  --source-path /absolute/path/to/split-check.txt \
  --source-ref runs/split-check.txt --declared-command 'python check_split.py' \
  --exit-code 0 --summary 'Retain these run bytes; provenance and claim need human review.' \
  --actor researcher
```

`approved` G0 retains the contract bytes from that decision. A later edit to the contract or drifting target `HEAD` invalidates preflight. `rebaseline` keeps old CaseRefs and findings readable but stale; another G0 approval creates a new case. Old evidence never automatically becomes evidence for the new case. A new `draft` without a content binding or an older workspace has `evidence_profile=reference-only`; old records remain readable, but text references cannot pass the new `verified` / `closed` gate.

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
rcsl audit evidence import "$WORKSPACE" --finding F-001 --id E-001 \
  --type artifact --artifact-role fixture-source --kind observed \
  --source-kind project-relative --source-path README.md \
  --summary 'Retain the temporary fixture README bytes for lifecycle testing only.' \
  --actor 'E2E Auditor'

rcsl audit finding transition "$WORKSPACE" --finding F-001 --to triaged \
  --actor 'E2E Auditor' --rationale 'Signal has been scoped.'
rcsl audit finding transition "$WORKSPACE" --finding F-001 --to accepted \
  --actor 'E2E Auditor' --rationale 'The bounded finding is accepted for mitigation.'
rcsl audit finding transition "$WORKSPACE" --finding F-001 --to mitigated \
  --actor 'E2E Auditor' --rationale 'Mitigation record is ready for verification.'
rcsl audit preflight "$WORKSPACE"
rcsl audit finding transition "$WORKSPACE" --finding F-001 --to verified \
  --actor 'E2E Research Owner' --rationale 'Current-case content bytes were retained and preflight passed for this fixture.'
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

Rebaseline makes old findings and the old content case `stale` and resets G0 to `draft`. Complete the research contract again, record a new `approved` gate, and pass preflight before adding findings or evidence for the new baseline. The old case manifest remains retained for digest checks but is not migrated.

## Working rules for findings and evidence

1. **Triage before asserting.** An `open` finding is a claim to audit. When evidence is insufficient, use `blocked`, `dismissed`, or retain it for later review; do not write a hypothesis as a proven violation.
2. **Classify by the first failed contract.** L1 semantics, L2 pipeline, L3 scientific validity, L4 agent governance. Effects can cross layers, but the primary classification must not double count them.
3. **One finding, one causal chain.** `claim` and `first-contract` should make location, rule, impact, and known limits clear. `evidence add` stores a text reference; `evidence import` retains an explicit file's bytes. They may coexist but offer different assurances.
4. **Record; do not hand-edit history.** The CLI refreshes current metadata/finding snapshots and appends gate, transition, evidence, and rebaseline rationale to the event ledger. Correct old conclusions through a new lifecycle action, not by editing JSON/JSONL directly.
5. **Some declared lifecycle states have a content-evidence gate.** `open → triaged → accepted → mitigated → verified → closed` is one legal example path. New `verified` / `closed` transitions require a prior imported `observed` / `derived` / `reproduced` item for the current case, current baseline, and preflight; intermediate states cannot be skipped. Old historical values remain readable and do not mean the system performed independent verification or scientific approval.

## Honest meaning of status words

| Status | It may say | It must never say |
| --- | --- | --- |
| `contract_structure=complete` | The research contract meets structural and placeholder requirements | G0 is approved, a finding is true, or a conclusion is correct |
| `g0-prerequisites-met` | The research contract is complete and its declared `approved` decision matches the current bytes | A clean Git baseline, every preflight condition, or reviewer identity authenticity |
| `local-records-consistent` | Retained local events, metadata, and finding snapshots have internally consistent hash relationships | History was not deleted/replaced or witnessed by a trusted third party |
| `evidence_profile=content-bound-v1` | A G0 case is retained; retained contract, older/newer cases, and imported-byte digests pass local content-binding checks. Inspect binding state separately for currency | Provenance is authentic, a command ran, or a research conclusion is correct |
| `evidence_profile=reference-only` | No content binding exists yet (including an initialized `draft` or older record); only text-reference semantics apply | Cited bytes are stored or references can pass a new terminal gate |
| `content_binding_state=current/stale/absent`; `case_state=current/stale/legacy` | Whether the retained CaseRef matches the current baseline/`HEAD`/contract bytes and a finding belongs to that case; an old case remains retained but stale after rebaseline | `current` means G0 is presently approved, preflight passed, evidence is sufficient, or science is trustworthy. A binding may remain `current` after a same-byte `draft`/`blocked` gate; inspect G0 status and `preflight_issue` together |
| `current` | A finding's bound baseline is the active baseline; preflight separately checks that the target worktree is clean and `HEAD` has not drifted | Code is faithful, an experiment is fair, or risk-free |
| `preflight-passed` | Current G0, Git baseline, and retained local records passed this preflight | Any finding/evidence exists, findings reached closure, or a conclusion was approved |
| `preflight-current` | Preflight passed and the report has no stale finding from an older baseline or case; this can be true with zero findings or evidence | A substantive audit is complete, evidence is sufficient, or a scientific claim may be published |
| `preflight-not-current` | Preflight did not pass, or the report still contains stale findings from an older baseline/case; inspect `preflight_issue` and the stale counts | Every local record is corrupt or a scientific conclusion is false |
| `verified` / `closed` | A new transition followed a legal path and met its prior current-case content-evidence, baseline, and preflight gates; historical labels remain readable | Evidence is true, sufficient, or independent, or the system/third party verified the repair or conclusion |

These states describe declarations, retained records, and process only. **They—and `audit lint` and `audit verify`—are not a scientific PASS.**

The CLI `status --json` / `verify --json` names the retained binding `retained_case_ref`. It still exists when `stale` and must not be treated as a currently approved case. The compatibility fields `verification.current_case_ref` and a JSON report's `current_case_ref` name that same retained binding; always interpret them alongside `content_binding_state`.

## Limits of hash chains, identity, and security

A local hash chain only makes edits, reorderings, or breaks easier to notice in **local history that is still retained**. It cannot:

- authenticate an `--actor`, `--reviewer`, timestamp, or approval source;
- prevent a local writer from deleting records, replacing a workspace, or recomputing a new chain;
- prove remote Git history, the original provenance of external files, actual execution of a declared command, or integrity of cited content; or
- provide access control, confidentiality, legal compliance, or scientific validity.

The content-bound store can recheck **retained** contract bytes, case manifests, and imported bytes. CaseRefs, ArtifactRefs, and RecordRefs bind local objects to events, but do not prove authorship, authentic provenance, scientific correctness, evidence sufficiency, or independent reproduction. Even a self-consistent digest can be replaced by a same-privilege local writer who rebuilds the namespace and history.

Import first stores bytes in the content-addressed store, then commits the finding/event. A failure or interruption in the latter step can leave a legitimate orphan blob not referenced by an event. The CLI does not automatically garbage-collect it. Especially before importing an external sensitive file, the owner should assess the authorization and local-retention risk.

Before a lifecycle action writes anything public, it validates the prospective snapshot, event count, and byte capacity. It then writes and syncs a short-lived `.rcsl-audit-pending.json` intent before replacing the snapshot and event ledger. If a process, disk, or machine fails in the middle, ordinary reads and writes fail closed and direct the operator to `rcsl audit recover WORKSPACE`. Recovery performs one deterministic roll-forward without appending the same event twice. An unknown third file state is still refused and requires preservation and human inspection. Do not “repair” history by editing JSON or recomputing hashes.

`.rcsl-write.lock` is a persistent fixed advisory-lock file, not stale state to delete. Cooperating local POSIX processes use shared/exclusive `flock`, and the operating system releases the lock when a process exits. This coordination does not cover non-POSIX environments or stop non-cooperating same-privilege writers.

Capacity prechecks, a recoverable commit intent, per-file atomic replacement and directory sync, together with pinned-directory initialization/report writes, exclusive creation, identity rechecks, and POSIX `0600`, are fail-closed defenses against half-commits, accidental overwrites, and common local path-replacement races. They are not a general transactional database, digital signature, ACL, or a boundary against a malicious local writer.

Stronger assurance needs separate controlled storage, code-host audit records, signatures, independent review, and organizational policy. Those capabilities must not be described as default CLI protections.

## When to stop and escalate

Retain the record already gathered and use `blocked`, or stop for a human decision, when:

- the research contract lacks permitted scope, data rights, budget, protection boundary, or claim limit;
- the project is dirty, not Git, or the workspace is inside it;
- work requires project execution, network use, protected material, source changes, or a larger budget;
- there is potential secret/privacy exposure, unclear licensing, protected-evaluation leakage, or a high-impact claim; or
- evidence supports only “unknown,” not a stronger finding state.

A good Mode Audit result is sometimes a pause, narrowed claim, or request for approval. It never substitutes “the project ran” for a research owner’s final decision about trust and release.
