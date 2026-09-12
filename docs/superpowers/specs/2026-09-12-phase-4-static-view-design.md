# Phase 4A Offline Static View Design

**Status:** implementation specification

**Scope:** a replaceable, completely offline, static, read-only projection of
verified Open Demo metadata and optional local Audit/Training evidence.

**Authoritative sources:** Open Demo bundles, Audit workspaces, and Training
workspaces remain authoritative. The generated view is a disposable snapshot,
not a third operating mode and not a writable system of record.

## Decision and permanent boundary

Phase 4A reduces navigation cost without creating a web service. It emits one
local HTML page and one local stylesheet. It has no JavaScript, CDN, server,
font, image, request API, telemetry, login, upload, or network fallback. The
page must open directly from disk and remain useful while the machine is
offline.

The input boundary is deliberately narrower than the Phase 3 release model:

- at least one **verified Open Demo bundle** is required;
- one existing Mode Audit workspace is optional;
- one existing Mode Train workspace is optional and is consumed only through
  the stable redacted-status projection;
- a Blind staging root and every Challenge, Evaluator, or Maintainer role
  package are refused before their payload tree is walked; and
- `assembled-awaiting-controlled-placement` is not a release status accepted by
  this viewer.

This phase never makes controlled Blind material easier to browse. Supporting a
controlled package would need a separate threat model after Phase 3B access,
placement, review, and withdrawal controls exist.

“Read-only” describes viewer behavior: there are no editing or mutation
controls, and source state is never changed. Generated files use owner-writable
local modes so that the owner can remove the disposable directory. Checksums
detect later edits; they are not filesystem immutability, signatures, or
tamper-proof history.

## Frozen CLI

```bash
python scripts/rcsl.py view build \
  --open-demo /absolute/path/to/open-demo \
  [--open-demo /absolute/path/to/another-open-demo] \
  [--audit-workspace /absolute/path/to/audit-workspace] \
  [--training-workspace /absolute/path/to/training-workspace] \
  --output /absolute/path/to/new-static-view

python scripts/rcsl.py view verify \
  /absolute/path/to/static-view [--json]
```

`--open-demo` is repeatable and required at least once. The Audit and Training
arguments are each optional and singular in Phase 4A. `--output` must name a
nonexistent directory whose immediate parent already exists. It must be outside
the public RCSL repository and non-overlapping with every input: output may not
contain an input, and no input may contain output.

`view build` exits successfully only after it has applied the same complete
validation rules used by `view verify` to the newly created root through its
still-owned directory descriptor. On a partial-write or verification failure it
does not recursively remove the new tree, because a child may have been replaced
concurrently. An unverified partial directory may therefore remain for explicit
human inspection and safe cleanup; a replacement path is never deleted.

`view verify` reads only the retained view. It does not revisit source paths,
which are intentionally not stored, and therefore cannot prove that a view is
still synchronized with a subsequently changed source. Rebuild into a new
directory after any source change.

## Input admission and frozen projections

All user paths are normalized lexically and checked for the protected
`DO_NOT_OPEN_UNTIL_FINISHED` component before any filesystem read. Each domain
adapter produces one in-memory snapshot under its own pinned/frozen read and
consistency gates; after the adapter returns, the View layer processes only
that projection and does not reopen a source path to obtain more fields. Open
Demo manifest, validation, and registry data all come from one frozen checksum
tree. Audit and Training rely on their domain adapters' existing snapshot
consistency checks. This phase does not claim that one file descriptor remains
open across the separate domain APIs.

### Open Demo

Every Open Demo is reverified with the repository-side trusted Phase 3
verifier. Verification covers the exact package root, manifest and checksum
inventories, retained bytes, source-tree binding, release boundary, validation
record, and the trusted package verifier bytes. Package code is read as inert
data and is never imported or executed.

Input-shape checks occur before a general package walk:

1. a root with `CONTROL_MANIFEST.json`, a controlled-readiness marker, or the
   fixed Blind-staging directory shape is refused before descending;
2. a root whose small, bounded `PACKAGE_MANIFEST.json` declares
   `rcsl-role-package` is refused as a role package; and
3. only `rcsl-open-demo-package` proceeds to full Open Demo verification; the
   same pinned root then rechecks the classified manifest bytes and forbidden
   root markers before any directory descent.

These early checks prevent a FIFO or other hostile object deeper in an
obviously private-package fixture from being opened merely to discover that the
input type was forbidden.

After successful verification, the Case Registry receives only this allowlist:

| Field | Source |
| --- | --- |
| `case_id`, `case_version` | Open Demo manifest |
| `release_mode`, `release_state`, `exposure_state` | Open Demo manifest |
| `source_revision`, `source_revision_scope`, `repository_worktree_state` | Open Demo manifest |
| `source_tree_sha256` | Open Demo manifest |
| `package_manifest_sha256`, `package_checksums_sha256`, `package_file_count` | trusted verification result |
| `licenses` (`scope`, `terms`, `notice` only) | Open Demo manifest |
| `known_limitations`, `claims_not_made` | Open Demo manifest |
| `static_validation`, `public_runtime_checks` | the two verified validation-record outcomes |
| `scientific_correctness`, `measurement_validity` | Open Demo manifest; both remain `not_assessed` |

The projection excludes `created_at`, `declared_actor`, `actor_authentication`,
validation environment/commands/output digests, raw file inventory, arbitrary
package payload, reviewer data, and every controlled scoring, evaluator,
maintainer, whole-release, or private-source digest. License notice paths are
displayed as inert text and never turned into links.

Two inputs with the same manifest digest are refused as duplicates. If one
`(case_id, case_version)` maps to different `source_tree_sha256` values, build
fails as a version collision rather than presenting ambiguous provenance.

### Audit evidence projection

The trusted source adapter calls `audit.build_report_data` and projects its
returned in-memory snapshot; it never copies an Audit workspace file into the
view. The evidence record retains only:

- `schema_version`, record type, validator scope, and `report_status`;
- Git baseline `head`, branch, and capture time, plus the local ledger's
  `event_count` and `last_event_hash`;
- the derived `preflight_state` and, for every finding, the Boolean
  `baseline_current` consistency flag;
- G0 status and the current contract SHA-256 binding;
- finding counts grouped by status, layer, competency, and severity;
- for every finding: ID, title, layer, competency, severity, claim, first broken
  contract, lifecycle status, timestamps, baseline state, and evidence;
- for every evidence item: ID, kind, reference, summary, and recorded time; and
- up to 100 bounded source-report limitations, followed by three fixed
  projection limitations, plus an explicit
  `scientific_correctness: not_assessed` boundary.

The projection omits the Audit workspace path, project root,
baseline/gate/finding/evidence actors, reviewer, rationale, full contract,
templates, event payloads, and any other source field. Before retaining
free-form title, claim, broken-contract, reference, or summary text, literal
occurrences of the trusted adapter's known workspace and project-root strings
and their file-URI forms are replaced, longest first, with
`[local-path-redacted]`. An evidence `reference` that is absolute, a file URI,
or contains a known root becomes `[local-reference-redacted]`. The replacement
is deterministic and does not claim to find aliases, secrets, names, or paths
the author typed in another spelling.

Audit free text can still contain confidential research information or personal
data. For that reason, adding an Audit input always classifies the whole output
as `local-sensitive-not-deployable`, even after field reduction and known-root
replacement.

The v1 Audit record has exactly this shape (the count maps contain every value
from the authoritative Audit vocabularies):

```json
{
  "schema_version": 1,
  "evidence_type": "rcsl-audit-evidence-view",
  "privacy_classification": "local-sensitive-not-deployable",
  "validator_scope": "local_hash_chain_lifecycle_integrity_only",
  "report_status": "draft|review-ready",
  "preflight_state": "ready|not-ready",
  "scientific_correctness": "not_assessed",
  "baseline": {"head": "...", "branch": null, "captured_at": "..."},
  "g0_gate": {"status": "draft|approved|blocked", "contract_sha256": "..."},
  "integrity": {"event_count": 0, "last_event_hash": "..."},
  "summary": {
    "finding_count": 0,
    "stale_finding_count": 0,
    "by_status": {},
    "by_layer": {},
    "by_competency": {},
    "by_severity": {}
  },
  "findings": [],
  "limitations": ["at least one source or fixed limitation"]
}
```

Every finding has exactly `id`, `title`, `layer`, `competency`, `severity`,
`claim`, `first_broken_contract`, `status`, `created_at`, `updated_at`,
`baseline_state`, `baseline_current`, and `evidence`. Every evidence item has
exactly `id`, `kind`, `reference`, `summary`, and `recorded_at`.

`report_status: review-ready` is equivalent to a ready preflight with zero
stale findings. A preflight can still be `ready` while the report remains
`draft` when one or more findings belong to an older baseline; the view must
retain that legitimate state rather than reject or upgrade it.

### Training evidence projection

Training is consumed through a public `training.get_redacted_status` helper,
which is the single stable adapter shared with the existing redacted export.
It first strictly verifies the workspace and then returns an in-memory record
with this allowlist:

- case ID/revision, exposure state, validator scope, overall state, next
  recommended target, scientific-correctness state, and human-only maturity
  boundary;
- for each of `L1`, `L2`, `L3`, `L4`, and `capstone`: attempt, structure,
  human-review, semantic, maturity, scientific, current-draft, and retry/count
  states; latest attempt ID/digest; disagreement values; historical review
  count; and evidence-gap count;
- active declared reviews reduced to review ID, deterministic
  `reviewer-<n>` alias, decision, the four declared ratings, and a Boolean
  `gap_recorded`; and
- the redaction privacy note and export boundary.

The retained evidence schema names the review array `declared_reviews` and its
pseudonymous field `reviewer_alias`; it contains no generic `reviewer` or
`actor` key. It excludes learner label, editable worksheets, submitted
worksheet snapshots, attempt notes, operations, raw reviewer labels, rationale,
strengths, gap text, and answer/evaluator mappings. The attempt digest remains
as a local binding and may itself be linkable to source material, so adding a
Training input also makes the output `local-sensitive-not-deployable`.

Pseudonymization and field omission are not anonymization or publication
approval. The adapter never reads, imports, or copies isolated instructor
material.

The v1 Training record has exactly `schema_version`, `evidence_type`,
`privacy_classification`, `case_id`, `case_revision`, `exposure_state`,
`validator_scope`, `overall_state`, `next_recommended_target`,
`scientific_correctness`, `maturity_assessment`, `targets`, `privacy_note`, and
`export_boundary`. Each target has exactly `attempt_state`, `structure_state`,
`human_review_state`, `maturity_assessment`, `semantic_assessment`,
`scientific_correctness`, `attempt_count`, `latest_attempt_id`,
`latest_attempt_sha256`, `draft_changes_since_submission`,
`current_draft_state`, `declared_reviews`, `rating_disagreements`,
`historical_review_count`, and `evidence_gap_count`. Each declared review has
exactly `review_id`, `reviewer_alias`, `decision`, `ratings`, and
`gap_recorded`.

## Exact output boundary

```text
static-view/
├── index.html
├── style.css
├── VIEW_BOUNDARY.md
├── VIEW_MANIFEST.json
├── CHECKSUMS.sha256
└── data/
    ├── CASE_REGISTRY.json
    └── evidence/
        ├── audit-<64-lowercase-hex-digest>.json       # optional
        └── training-<64-lowercase-hex-digest>.json    # optional
```

The three directories are always present, even when `data/evidence/` is empty.
No other directory or file is permitted. Evidence filenames use the SHA-256 of
their own canonical JSON bytes, so neither source path nor identity appears in
a filename. A filename collision with nonidentical bytes fails closed.

On POSIX, the builder requests and the verifier requires exact mode `0700` for
the root, `data/`, and `data/evidence/`, and exact mode `0600` for every file.
Files are therefore readable only by the owner under ordinary mode-bit
semantics. This check does not inspect all ancestor permissions, ACLs, extended
attributes, backups, disk encryption, processes running as the same user, or
later copies.

### `data/CASE_REGISTRY.json`

The registry is strict JSON with no unknown fields:

```json
{
  "schema_version": 1,
  "registry_type": "rcsl-open-demo-case-registry",
  "projection_scope": "verified-open-demo-metadata-only",
  "scientific_correctness": "not_assessed",
  "cases": []
}
```

`cases` contains the exact Open Demo projection above, sorted by `case_id`,
`case_version`, and `package_manifest_sha256`. It never
contains an Audit or Training record and has no schema branch for a Blind case
in Phase 4A.

Each case object has exactly `case_id`, `case_version`, `release_mode`,
`release_state`, `exposure_state`, `source_revision`, `source_revision_scope`,
`repository_worktree_state`, `source_tree_sha256`,
`package_manifest_sha256`, `package_checksums_sha256`, `package_file_count`,
`licenses`, `known_limitations`, `claims_not_made`, `static_validation`,
`public_runtime_checks`, `scientific_correctness`, and `measurement_validity`.

### Evidence JSON

Each optional source produces one canonical record under `data/evidence/`:

```json
{
  "schema_version": 1,
  "evidence_type": "rcsl-audit-evidence-view",
  "scientific_correctness": "not_assessed",
  "...": "the fixed Audit projection defined above"
}
```

or:

```json
{
  "schema_version": 1,
  "evidence_type": "rcsl-training-status-view",
  "scientific_correctness": "not_assessed",
  "...": "the fixed Training projection defined above"
}
```

Verifier code owns an exact key/type schema for both variants. It rejects
unknown or missing fields, JSON duplicate keys, Boolean substitutes for integer
fields, floats, `NaN`/infinities, excessive nesting, invalid digests, unexpected
target names, and vocabulary outside the authoritative Train/Audit constants.

### `VIEW_MANIFEST.json`

The manifest has exactly these top-level keys:

```json
{
  "schema_version": 1,
  "manifest_type": "rcsl-static-view",
  "view_mode": "offline-static-snapshot",
  "privacy_classification": "open-demo-only-offline",
  "deployment_policy": "offline-open-demo-snapshot-only",
  "network_access": "not_used",
  "code_execution": "not_performed",
  "scientific_correctness": "not_assessed",
  "case_count": 1,
  "evidence_kinds": [],
  "evidence": [],
  "files": [],
  "limitations": []
}
```

When Audit or Training evidence is present,
`privacy_classification` is `local-sensitive-not-deployable` and
`deployment_policy` is `do-not-deploy-local-sensitive-data`.
`evidence_kinds` is the sorted subset of
`["audit", "training"]`. `evidence` binds every evidence kind, relative path,
and file digest. It contains no source filesystem path. `files` contains the
sorted exact `{path, sha256, size}` inventory of every retained payload except
`VIEW_MANIFEST.json` and `CHECKSUMS.sha256`; it therefore covers HTML, CSS,
boundary, registry, and evidence bytes.

`network_access: not_used` and `code_execution: not_performed` describe this
trusted builder path only. Reading files and asking the Audit adapter to inspect
Git metadata are not execution of audited or packaged code. These strings are
not sandbox or operating-system attestations.

### `CHECKSUMS.sha256` and trusted verification

`CHECKSUMS.sha256` has one sorted lowercase SHA-256 record for every retained
file except itself, including `VIEW_MANIFEST.json`. The file set in checksums,
the manifest inventory, and the exact allowed tree must agree; a self-consistent
superset is rejected.

The trusted verifier also reparses registry/evidence with their exact schemas,
recomputes evidence filenames and manifest bindings, regenerates `index.html`
from the retained canonical JSON, and byte-compares the expected HTML,
`style.css`, and `VIEW_BOUNDARY.md`. Rehashing a malicious HTML page therefore
does not make it valid. There is no generated standalone verifier in Phase 4A;
verification depends on a trusted RCSL checkout. Even a trusted verification
establishes internal view integrity and the current rendering contract, not the
authenticity or continuing existence of original inputs. Checksums can be
rewritten by anyone able to rewrite the directory.

## Static rendering and XSS contract

`index.html` embeds all display content at build time. It does not use
`fetch`, XHR, WebSocket, dynamic import, a service worker, or client-side JSON
loading. The only local resource reference is the fixed literal `style.css`.
The retained JSON files exist for inspection and verification, not as browser
dependencies.

The fixed page head includes a restrictive meta Content Security Policy whose
effective intent is:

```text
default-src 'none'; style-src 'self'; img-src 'none'; font-src 'none';
script-src 'none'; connect-src 'none'; object-src 'none'; base-uri 'none';
form-action 'none'
```

No source-provided value is placed into a tag name, attribute name, URL,
`style`, `class`, or element ID. Input projection rejects NUL, escape, and bidi
override/isolate controls; Audit free text additionally removes other Unicode
control characters except newline and tab and is normalized to NFC. Every
retained dynamic scalar then becomes a text node by applying
`html.escape(value, quote=True)` exactly once and concatenating only the escaped
result into fixed markup.

Source Markdown is never interpreted. Strings resembling `<script>`, closing
tags, event handlers, Markdown links, `javascript:` URLs, CSS, or HTML entities
remain visible text. Evidence references are not clickable. The
stylesheet is constant, contains no `@import`, `url(...)`, embedded font, or
generated data, and is byte-compared during verification.

The boundary notice is visible near the start of the page, not hidden in a
footer. Semantic headings, lists/tables, visible focus indicators, sufficient
contrast, and a useful narrow-screen layout are part of the static template,
but visual styling never changes any source state or claim.

## Determinism

For the same trusted implementation and the same verified source snapshot,
build output bytes are identical regardless of output path or CLI input order.
The builder therefore records no build timestamp, source absolute path, process
ID, hostname, random identifier, authenticated actor, or filesystem metadata in
payload bytes.

All JSON uses UTF-8, sorted object keys, two-space indentation, `allow_nan=False`,
and one trailing newline. Registries, evidence bindings, file inventories, and
checksum lines use defined stable sort keys. HTML is regenerated from those
canonical in-memory projections in the same order. The view records source
timestamps only where they are already part of an allowed Audit/Training field;
it never invents a new time.

The builder validates and pins the output parent before reading inputs, but does
not create the named output directory until every projection and payload byte
is ready. It then creates the owned output through that pinned parent, writes
every file exclusively through pinned directory descriptors, flushes
files/directories, validates the owned namespace identities, and runs full
retained-view verification before success.

## Resource and filesystem limits

The implementation defines finite constants and fails before retaining output
when any is exceeded. Phase 4A uses the Phase 3 limits while verifying each Open
Demo and additionally caps:

- 32 Open Demo inputs, plus at most one Audit and one Training input;
- 128 immediate root entries during Open Demo type preclassification;
- 64 immediate Audit-workspace root entries and 48 MB of bounded Audit input
  bytes before projection;
- 10,000 findings, 10,000 evidence items per finding, and 50,000 Audit
  evidence items in aggregate;
- 200,000 UTF-8 bytes for one projected text scalar;
- 12 MB for one parsed/canonical projected JSON document;
- 16 MB for one retained output file;
- 16 retained files, 18 total retained namespace entries including the two
  fixed directories, and 48 MB of retained bytes; and
- JSON nesting at 100 levels.

File, JSON, tree, and scalar limits are checked on encoded bytes. The trusted
source adapters retain their own stricter limits where applicable. The builder
processes inputs in a bounded sequence and drops full package payload snapshots
after extracting an allowlisted Open Demo entry.

All traversals use sorted names and directory descriptors. Symlinks and special
objects (FIFO, socket, block/character device) at an expected input or output
position fail closed before an open that could block. Names must be NFC,
relative output paths must not be absolute or contain empty/`.`/`..` segments,
and case-insensitive path collisions are rejected. Protected components are
skipped-before-read only where an existing trusted Open Demo policy explicitly
requires that behavior; otherwise their presence is a refusal.

Output creation extends the Phase 3 owned-output discipline: existing targets
are never overwritten; the parent is pinned before input verification and must
retain the same path identity through creation; the newly created root remains
pinned; files use `O_EXCL` and `O_NOFOLLOW`; and every directory transition
verifies a directory. Failure handling never recursively deletes a partially
built tree because an attacker could replace a child after it was checked. A
failed, non-authoritative partial directory may therefore remain for explicit
human cleanup. Tests that replace either the root or a child must leave every
replacement and sentinel untouched.

## Implementation map

- `stewardship_lab/view.py` owns View errors, strict schemas, projections,
  canonical serialization, static rendering, build, and verification. It
  freezes one Open Demo checksum tree and applies the trusted release manifest,
  boundary, validation-record, and retained-byte validators to that same
  snapshot; Blind verifiers remain separate.
- `stewardship_lab/training.py` exposes `get_redacted_status`; both the existing
  Training export and the viewer use the same redaction implementation.
- `stewardship_lab/audit.py` remains the authority for one internally consistent,
  validated report snapshot; the View layer only reduces and root-redacts that
  returned in-memory snapshot.
- `stewardship_lab/__init__.py` exports the public View entry points.
- `scripts/rcsl.py` adds the frozen `view build` and `view verify` command family.
- `tests/test_static_view.py` owns the Phase 4A behavioral/security matrix, and
  the public workflow runs it alongside existing Train/Audit/Release tests.

No frontend build system, package manager, template engine, Markdown renderer,
browser automation dependency, database, socket listener, or hosted service is
introduced.

## Build and verification algorithm

`view build` performs these ordered gates:

1. parse counts and lexically reject protected input/output paths;
2. identify obvious Blind staging and role-package inputs from bounded control
   files, before any forbidden payload walk;
3. pin, reverify, and project each Open Demo; reject duplicates and version
   collisions;
4. pin and project optional Audit and Training workspaces through their domain
   validators; apply the fixed reduction/redaction contracts;
5. validate all projected schemas, types, vocabularies, sizes, and cross-record
   counts in memory;
6. canonicalize evidence, derive content-addressed filenames, create the sorted
   registry, and render fixed HTML/CSS/boundary bytes;
7. build the manifest and checksum inventories without nondeterministic build
   metadata;
8. exclusively create the private owned output tree and write bytes through
   pinned descriptors;
9. recheck output identity, freeze and verify the complete retained tree through
   the still-owned root descriptor, recheck the frozen identities and bytes, and
   then close descriptors; and
10. on failure, preserve any unverified partial tree for explicit safe handling
   and report a bounded View error without recursively deleting children.

`view verify` performs the inverse structural proof:

1. reject a protected, symlinked, non-directory, wrong-mode, over-limit, or
   path-colliding view root;
2. freeze the exact regular-file tree and exact directory set without following
   links or opening special objects;
3. verify checksums, then strict manifest schema and payload inventory;
4. verify privacy classification, deployment policy, evidence kinds/counts,
   registry case count, evidence filenames/bindings, and all explicit
   `not_assessed`/no-execution/no-network states;
5. parse and validate exact registry and evidence projections;
6. regenerate and byte-compare the HTML and fixed resources; and
7. return only a bounded summary: integrity status, privacy classification,
   scientific-correctness state, case count, evidence kinds, file count,
   network-access state, and code-execution state.

Neither algorithm imports source Python, executes the packaged public-check
runner or audited-project code, evaluates JavaScript, starts a browser/server,
contacts a URL, changes an Audit/Training workspace, or reads controlled answer
material.

## Required test matrix

| Area | Required tests |
| --- | --- |
| Happy paths | One Open Demo; repeated distinct Open Demos; optional Audit; optional Training; both evidence types; empty evidence directory; direct local page bytes; JSON CLI output |
| Determinism | Two builds from identical inputs at different output paths are byte-for-byte equal; reversed Open Demo argument order is equal; no time/path/host/PID appears |
| Input boundary | No Open Demo refused; malformed Open Demo refused; same manifest duplicate refused; case/version collision refused; Blind staging and controlled-readiness markers refused before deep FIFO; each role package refused before payload walk; a classified manifest removed or replaced by a directory is rejected before any descent; protected component refused before read; output/input overlap refused |
| Source integrity | Open Demo checksum, manifest, boundary, verifier, validation record, source-tree, executable-state, extra-file, and file-count/byte-limit tampering all fail |
| Audit projection | Ledger/report validation required; project/workspace roots replaced in retained free text; all actor/reviewer fields and values absent; finding/evidence kind/status preserved; stale/draft state remains visible; no original workspace mutation |
| Training projection | Uses shared redacted helper; learner and raw reviewer labels absent; worksheets/snapshots/notes/rationale/strengths/gap text absent; aliases and gap Boolean/count preserved; disagreements not averaged; no isolated-material access |
| XSS/offline | Script/tag/attribute/entity/Markdown/CSS/URL payloads display escaped; no `<script>`, event attributes, remote `href`, `src`, import, `url(`, fetch, or form; CSP and fixed stylesheet present; rehashed malicious HTML rejected |
| Output integrity | Byte tamper, missing/extra file, missing/extra directory, malformed checksum, duplicate/colliding path, bad manifest record, bad evidence filename, invalid privacy state, and rehashed unknown schema all fail |
| Filesystem safety | Existing output preserved; source/output symlink refused; FIFO/socket/device refused without blocking; parent/root/file swap races fail; cleanup never deletes a replacement; POSIX modes are exactly `0700`/`0600` |
| Resource safety | Per-scalar, JSON, HTML, count, nesting, file, and total-byte limits fail closed; Boolean-as-integer, float, duplicate JSON key, `NaN`, and invalid UTF-8 fail |
| Claims | Every page/registry/evidence/manifest keeps `not_assessed` and limitations; Open Demo is never shown as blind; integrity never becomes scientific validity, privacy approval, maturity inference, release approval, identity authentication, or source freshness |
| Regression | Existing public Train, Audit, release packaging, validators, and CLI tests remain green; test discovery never requires reading isolated instructor material |

Tests patch process/network entry points in the View layer so a successful build
demonstrates that it does not execute package code or create a network client.
Filesystem race tests use controlled hooks immediately before/after writes and
source snapshot boundaries; they assert both refusal and preservation of an
attacker-created replacement sentinel.

## Acceptance criteria and non-goals

Phase 4A is complete when a user can build the exact output above from at least
one verified Open Demo, optionally add safely reduced Audit/Training evidence,
open the page from disk with no network or JavaScript, and verify the retained
snapshot. All authoritative work remains possible through the original local
CLI and Markdown/JSON when the view directory is deleted.

Phase 4A does not provide:

- scientific, reproducibility, fairness, maturity, security, or privacy
  certification;
- source freshness, authenticated identity, signatures, external immutability,
  confidentiality, ACLs, encryption, copy prevention, or revocation;
- a Blind Challenge viewer or completion of Phase 3B;
- editing, finding transitions, reviews, approvals, or source-workspace writes;
- a hosted registry, deployment pipeline, backend, database, sync, account, or
  multi-user collaboration;
- JavaScript filters, live search, client-side scoring, analytics, or telemetry;
  or
- proof that escaped local HTML is safe to publish in every hosting context.

Any later interactive UI must consume the same versioned projections, preserve
these claim boundaries, and remain replaceable by the local CLI. Hosting or
controlled-package support is a new phase requiring separate privacy, access,
governance, and threat-model approval.
