# Phase 3 Release Packaging Design

**Status:** implementation-aligned specification

**Schema authority:** `stewardship_lab/release.py::_validate_blind_manifest`

**Scope:** export the current public teaching case honestly, and assemble a
future never-public case into three locally staged role packages.

Packaging can establish file selection, source-byte consistency, package
separation, and retained-byte integrity. It cannot establish confidentiality,
participant identity, scientific correctness, measurement validity, learning
effectiveness, or operational access control.

## Permanent release boundary

The current `LLM4SBR_research_audit_training_v2` case has existed in public Git
history. Removing files, moving the case, encrypting an archive, or rebuilding a
smaller distribution cannot make it unseen. Every export of that case is
permanently an **Open Demo** with honor isolation, never a Blind Challenge.

A real Blind Challenge must begin as a new case outside public repository
history. Its Challenge, Evaluator, and Maintainer materials must be separated
before any participant receives the Challenge Package. The Phase 3 packager
creates a local staging layout only. Success means:

```text
assembled-awaiting-controlled-placement
```

It does not mean `blind-ready`, deployed, confidential, fair, or scientifically
correct.

## Frozen CLI

### Open Demo

```bash
python scripts/rcsl.py export open-demo \
  --output /absolute/path/to/new-open-demo \
  --actor "declared builder label" \
  [--run-public-checks]

python scripts/rcsl.py export verify \
  /absolute/path/to/open-demo [--json]
```

This command has no caller-selectable source or input record. It always exports
the repository's current `LLM4SBR_research_audit_training_v2` case. `--actor` is
a declared label and is not authenticated. The static public-surface validator
always runs. `--run-public-checks` additionally runs the known Level 1–4 public
runtime check runner before writing the bundle.

### Blind Challenge staging

```bash
python scripts/rcsl.py package blind \
  --manifest /absolute/private/path/blind-source.json \
  --challenge-source /absolute/private/path/challenge-source \
  --evaluator-source /absolute/private/path/evaluator-source \
  --maintainer-source /absolute/private/path/maintainer-source \
  --output /absolute/private/path/new-staging-root \
  --actor "declared builder label"

python scripts/rcsl.py package verify \
  /absolute/private/path/staging-root [--json]
```

The Blind source manifest and all three source roots must be outside the public
RCSL repository and outside protected instructor-material paths. The three
source roots must be pairwise distinct and non-nested. The output must be new,
outside the public repository, and non-overlapping with every source root. On
POSIX, the source-manifest file and its immediate parent directory must grant no
group/other permission bits (normally `0600` for the file and `0700` for its
parent). This is a local-mode prerequisite, not an ACL or full ancestor-path
audit.

`package verify` is maintainer-side verification. It reads the private staging
root and therefore must never be exposed as a participant/public verification
workflow. Each role package also contains a standalone verifier that reads only
that package.

## File-selection contract

### Fixed Open Demo selection

Open Demo is not manifest-driven. Its frozen selection policy is:

1. Traverse the fixed `LLM4SBR_research_audit_training_v2` root without
   following symlinks.
2. Exclude any path component matching one of these names case-insensitively:

   ```text
   DO_NOT_OPEN_UNTIL_FINISHED
   __pycache__
   .pytest_cache
   .mypy_cache
   .ruff_cache
   .ds_store
   ```

3. Require the expected honor-isolation directory name to have been observed
   and skipped.
4. Add only these repository support files:

   ```text
   LICENSE
   DOCUMENTATION_LICENSE.md
   THIRD_PARTY_NOTICES.md
   docs/CASE_RELEASE_MODEL.md
   docs/CASE_RELEASE_MODEL_EN.md
   ```

5. Freeze the selected case bytes and executable-state bits into a private
   temporary snapshot, then run the static validator and any requested public
   runtime checks against that snapshot rather than the mutable working tree.
6. Generate the boundary, validation, revocation-template, manifest, checksum,
   and standalone-verifier files described below.

The exporter never reads bytes from the excluded
`DO_NOT_OPEN_UNTIL_FINISHED` tree, never traverses into it, and never imports
anything from it. The frozen validation snapshot contains no isolated-tree
entry. Its digest covers each selected relative path, SHA-256 digest, size, and
executable boolean.

Verification requires exact roots rather than accepting any self-consistent
superset. Every retained file except `CHECKSUMS.sha256` must be represented in
the checksum inventory and every retained payload except
`PACKAGE_MANIFEST.json` must be represented in the manifest. The Open Demo's
root-level non-source files must equal the fixed support/generated allowlist;
all other payload must be rooted under the fixed LLM4SBR directory. The
repository-side verifier also compares `verify_package.py` and
`RELEASE_BOUNDARY.md` byte-for-byte with the trusted generated content for
schema version 1. The standalone verifier checks the same structure and
boundary fields but cannot establish an external authenticity root for its own
bytes.

### Explicit Blind allowlists

Blind packaging is manifest-driven. `package_files.challenge`,
`package_files.evaluator`, and `package_files.maintainer` are the three explicit
file allowlists. For each role, the source directory's complete regular-file set
must exactly equal its declared list. Undeclared files, missing files, symlinks,
special files, hash drift, size drift, executable-state drift, normalization
collisions, and generated control-file name collisions fail closed.

## Open Demo output contract

```text
open-demo/
├── CHECKSUMS.sha256
├── PACKAGE_MANIFEST.json
├── RELEASE_BOUNDARY.md
├── REVOCATION_NOTICE_TEMPLATE.md
├── VALIDATION_RECORD.json
├── verify_package.py
├── LICENSE
├── DOCUMENTATION_LICENSE.md
├── THIRD_PARTY_NOTICES.md
├── docs/
│   ├── CASE_RELEASE_MODEL.md
│   └── CASE_RELEASE_MODEL_EN.md
└── LLM4SBR_research_audit_training_v2/
    └── <fixed public surface with excluded names omitted>
```

`RELEASE_BOUNDARY.md` must say that instructor-oriented material was omitted
from this distribution but may remain discoverable in public history. Neither
the boundary nor the manifest may describe the bundle as blind or unseen.

### Generated Open Demo manifest

`PACKAGE_MANIFEST.json` is generated by the exporter and contains these
fields:

```json
{
  "schema_version": 1,
  "manifest_type": "rcsl-open-demo-package",
  "release_mode": "open-demo",
  "release_state": "open-demo-artifact",
  "exposure_state": "historically-public-honor-isolation",
  "case_id": "rcsl/llm4sbr-research-audit-v2",
  "case_version": "2.0.0",
  "source_revision": "<repository Git revision>",
  "source_revision_scope": "repository-head-not-byte-identity",
  "repository_worktree_state": "clean|dirty",
  "source_tree_sha256": "<digest of frozen case inventory>",
  "created_at": "<UTC build time>",
  "declared_actor": "<caller-supplied label>",
  "actor_authentication": "not_performed",
  "files": [
    {"path": "...", "sha256": "...", "size": 123}
  ],
  "licenses": [
    {"scope": "...", "terms": "...", "notice": "..."}
  ],
  "known_limitations": ["..."],
  "claims_not_made": ["..."],
  "scientific_correctness": "not_assessed",
  "measurement_validity": "not_assessed",
  "validation_record": "VALIDATION_RECORD.json",
  "revocation_template": "REVOCATION_NOTICE_TEMPLATE.md"
}
```

`source_revision` names repository HEAD, while `source_revision_scope` states
explicitly that HEAD is not the byte identity of a possibly dirty working tree.
`repository_worktree_state` records whether tracked or untracked worktree
changes existed. `source_tree_sha256` binds the actual fixed-source snapshot,
including executable state, and is recomputed from retained export bytes during
verification.

The public manifest contains only hashes of files included in the Open Demo. It
contains no Evaluator or Maintainer inventory, path, size, content digest, or
whole-package digest.

### Generated Open Demo validation record

The exporter generates `VALIDATION_RECORD.json`; it does not import a caller's
verdict. Its contract is:

```json
{
  "schema_version": 1,
  "record_type": "rcsl-open-demo-validation",
  "validated_source_tree_sha256": "<same digest as the package manifest>",
  "environment": {
    "python": "...",
    "platform": "..."
  },
  "records": [
    {
      "name": "...",
      "command": "...",
      "started_at": "... or null",
      "outcome": "passed|failed|failed-to-run|not-run",
      "exit_code": "<integer or null>",
      "stdout_sha256": "<digest or null>",
      "stderr_sha256": "<digest or null>",
      "scope": "..."
    }
  ],
  "scientific_correctness": "not_assessed",
  "measurement_validity": "not_assessed"
}
```

There are exactly two logical records: the always-run static public-surface
validator and the optional public runtime checks. Both operate on the same
frozen snapshot bound by `validated_source_tree_sha256`; the latter must equal
the package manifest's `source_tree_sha256`. A failed required run aborts before
a bundle is retained. Output bytes are represented only by digests; raw stdout
and stderr are not included. A passing public check proves only its documented
learner-visible contract, not a correct paper, valid experiment, programmer
maturity, confidentiality, or learning outcome.

## Blind source manifest contract

`_validate_blind_manifest` is the executable authority. It rejects missing and
unknown fields at every object boundary. The top-level object contains exactly:

```json
{
  "schema_version": 1,
  "manifest_type": "rcsl-blind-source",
  "release_id": "...",
  "case_id": "...",
  "case_version": "1.0.0",
  "release_mode": "blind-challenge",
  "created_at": "2026-09-12T00:00:00Z",
  "novelty_attestation": {},
  "source_bindings": {},
  "package_files": {},
  "licenses": [],
  "scoring": {},
  "isolation": {},
  "validation": {},
  "withdrawal": {},
  "claims_not_made": [],
  "human_approvals": []
}
```

The source-manifest parser accepts one UTF-8 JSON object only. It rejects
duplicate keys, unknown keys at each schema boundary, non-finite numbers, and
all floating-point numbers (including finite values such as `0.0`). Integer
fields reject JSON booleans. `case_version` and `scoring.version` must satisfy
strict SemVer 2.0 syntax, including no leading zero in a numeric identifier.
UTC timestamp fields use canonical RFC 3339
`YYYY-MM-DDTHH:MM:SS[.fraction]Z`: spaces, missing seconds, lowercase `t`, and a
`+00:00` suffix in place of `Z` are rejected. IDs and digests are validated
independently of any human claim attached to them.

### Novelty attestation

```json
{
  "state": "human-declared-never-public",
  "reviewer": "...",
  "reviewed_at": "2026-09-12T00:00:00Z",
  "evidence_refs": ["..."]
}
```

Only `human-declared-never-public` is accepted. The reviewer and evidence list
are mandatory. This is a human declaration, not an Internet-wide proof. A case
whose state is unknown or previously public, a source within the public RCSL
repository, or a source using the protected-path convention is ineligible.

### Three source bindings

`source_bindings` is an object with exactly `challenge`, `evaluator`, and
`maintainer`. Each value contains exactly:

```json
{
  "revision": "...",
  "revision_type": "git|content-digest",
  "clean_state": "human-declared-clean",
  "root_digest": "<64 lowercase hexadecimal characters>"
}
```

`root_digest` is computed from the sorted canonical records containing each
allowlisted path, SHA-256 digest, size, and executable boolean. Changing only a
file's executable state therefore changes or invalidates the role binding. A
declared clean state does not prove novelty, authorship, licensing, or
correctness.

### Three package file allowlists

`package_files` is an object with exactly `challenge`, `evaluator`, and
`maintainer`; each value is a non-empty list. Every entry contains exactly:

```json
{
  "path": "relative/posix/path",
  "sha256": "<64 lowercase hexadecimal characters>",
  "size": 123,
  "executable": false,
  "role": "challenge|evaluator|maintainer",
  "license_id": "...",
  "sensitivity": "public|controlled-evaluator|controlled-maintainer"
}
```

`executable` is a required JSON boolean. The entry's `role` must equal the
containing list. Sensitivity is fixed by role:

| Role | Required sensitivity |
| --- | --- |
| `challenge` | `public` |
| `evaluator` | `controlled-evaluator` |
| `maintainer` | `controlled-maintainer` |

Paths must be Unicode NFC, relative, normalized POSIX paths. Absolute paths,
backslashes, newline/carriage-return/NUL characters, empty/dot/dot-dot
components, protected instructor-material components, and collisions after
normalization plus casefolding are refused.

### Licenses

`licenses` is a non-empty list. Each entry contains exactly:

```json
{
  "id": "...",
  "terms": "SPDX identifier or exact terms reference",
  "redistribution": "allowed|restricted|review-required",
  "notice_path": "relative/notice/path",
  "approval_ref": "non-empty evidence reference"
}
```

Every file refers to a known license ID. For every license used by a role, that
role's allowlist must contain the license's `notice_path`. Every Challenge file
must use a license whose `redistribution` is exactly `allowed`. Structural
acceptance records a declared basis; it is not legal advice or a licensing
determination.

### Scoring

`scoring` contains exactly:

```json
{
  "protocol_id": "...",
  "version": "...",
  "digest": "<64 lowercase hexadecimal characters>",
  "automatic_scope": "...",
  "human_gate": "...",
  "independent_reviewer_ref": "..."
}
```

The Challenge manifest exposes only `protocol_id` and `version`. The scoring
digest and remaining controlled scoring declarations appear only in controlled
outputs. Automated scoring scope must not be represented as a scientific,
educational, or maturity verdict.

### Isolation

`isolation` contains exactly:

```json
{
  "challenge_audience": "...",
  "evaluator_audience": "...",
  "maintainer_audience": "...",
  "access_plan_ref": "...",
  "submission_channel_ref": "..."
}
```

These are mandatory operational declarations, not credentials and not evidence
that access control was deployed.

### Validation references

`validation` contains exactly:

```json
{
  "public_record_refs": [],
  "controlled_record_refs": ["..."],
  "leakage_review_ref": "...",
  "repeatability_review_ref": "..."
}
```

The public reference list may be empty. The controlled reference list must be
non-empty. References are not executed or interpreted by the Blind packager;
they remain declarations for human and controlled operational review.

### Withdrawal

`withdrawal` contains exactly:

```json
{
  "owner_label": "...",
  "contact_or_process_ref": "...",
  "triggers": ["..."],
  "procedure_ref": "..."
}
```

Every value is required, and `triggers` must be non-empty. The local packager
does not perform notification, revocation, or replacement.

### Human approvals

`human_approvals` is a list containing exactly one record for each gate:

```text
provenance
license
design
leakage
release-preparation
```

Each record contains exactly:

```json
{
  "gate": "provenance|license|design|leakage|release-preparation",
  "reviewer": "...",
  "reviewed_at": "2026-09-12T00:00:00Z",
  "rationale": "...",
  "evidence_refs": ["..."]
}
```

Duplicate, missing, or unsupported gates fail. The reviewer, rationale, and
evidence list are mandatory. These records are named human declarations, not
authenticated signatures and not proof that the cited work was performed.

### Template fail-closed rule

The shipped Blind source manifest template is a scaffold, not an assemblable
release declaration. `package blind` must reject it before creating output until
all operator-owned values are replaced. At minimum it refuses:

- text or path placeholders beginning with `REPLACE:` and identifier
  placeholders beginning with `replace-` or `your-`, plus unresolved
  `{{...}}` markers;
- the sentinel timestamp `1970-01-01T00:00:00Z` in any validated timestamp
  field; and
- a `scoring.digest` consisting of 64 zeroes.

Replacing syntax alone is insufficient: every resulting value must still pass
the exact ID, semantic-version, timestamp, path, digest, evidence, license, and
human-gate rules. Template rejection is not a novelty, rights, or approval
assessment.

## Three-package output contract

```text
private-staging/
├── CONTROL_MANIFEST.json
├── BUILD_RECORD.json
├── challenge/
│   ├── CHECKSUMS.sha256
│   ├── LEAKAGE_SCAN.json
│   ├── PACKAGE_MANIFEST.json
│   ├── RELEASE_BOUNDARY.md
│   ├── verify_package.py
│   └── <challenge allowlist>
├── evaluator/
│   ├── CHECKSUMS.sha256
│   ├── PACKAGE_MANIFEST.json
│   ├── RELEASE_BOUNDARY.md
│   ├── verify_package.py
│   └── <evaluator allowlist>
└── maintainer/
    ├── ACCESS_LOG_TEMPLATE.md
    ├── BLIND_SOURCE.json
    ├── CHECKSUMS.sha256
    ├── PACKAGE_MANIFEST.json
    ├── RELEASE_BOUNDARY.md
    ├── REVOCATION_NOTICE_TEMPLATE.md
    ├── verify_package.py
    └── <maintainer allowlist>
```

Every role `PACKAGE_MANIFEST.json` contains the common fields
`schema_version`, `manifest_type`, `package_role`, `distribution_state`,
`release_id`, `case_id`, `case_version`, `created_at`, `files`,
`source_inventory`, `licenses`, `boundary`, `claims_not_made`, and
`scientific_correctness`. `source_inventory` is the exact role-specific
`package_files` list from the frozen source manifest, including each source
file's executable boolean. `files` separately binds all retained role payload
and generated support files by path, hash, and size. Verification requires the
entire role payload outside the fixed generated-file set to equal
`source_inventory` exactly; rehashing a newly injected file into `files` and
`CHECKSUMS.sha256` remains invalid.

Each role manifest includes only licenses actually used by that role. Its
license records contain exactly `id`, `terms`, `redistribution`, and
`notice_path`. The source-only `approval_ref` is deliberately removed from
every role manifest; it remains available to maintainers in the retained
`BLIND_SOURCE.json` and is not exposed through Challenge metadata.

Role-specific manifest fields are:

- Challenge: `scoring_reference` with only protocol ID and semantic version.
- Evaluator: source-manifest digest, Challenge-manifest digest, and the full
  controlled scoring reference.
- Maintainer: source-manifest, Challenge-manifest, and Evaluator-manifest
  digests.

The staging root is created with private local permissions where supported. Its
three children remain co-located, so this layout is explicitly **not an access-
control boundary**. Publishing, synchronizing, or granting participants access
to the entire staging root is a release incident.

### Challenge Package

The Challenge Package contains only learner-facing source files, generated
boundary/integrity files, a bounded leakage-scan record, release/case identity,
and the opaque scoring protocol ID/version.

It must contain no:

- Evaluator or Maintainer file name, path, size, inventory, content digest, or
  whole-package digest;
- source manifest or source-manifest digest;
- answer mapping, correct candidate, hidden probe, grader, expected result,
  repair span, or private scoring digest;
- builder actor, build host, runtime build timestamp, credential, access token,
  or controlled directory location.

Even a digest of a small answer mapping can enable enumeration. Phase 3
therefore does not use a controlled digest as a public commitment.

### Evaluator Package

The Evaluator Package is controlled. Its manifest binds its own files, the
source manifest digest, the exact Challenge manifest digest, and the full
scoring object. It does not include Maintainer package inventory or digest.
Evaluator code is packaged but never executed by `package blind`.

### Maintainer Record

The Maintainer package is controlled. It retains the exact source manifest,
its own files, the Challenge manifest digest, the Evaluator manifest digest,
revocation material, and an access-log template. The private root
`CONTROL_MANIFEST.json` binds all three role manifests and checksum files.
It also binds `BUILD_RECORD.json` by SHA-256. `BUILD_RECORD.json` separately
records the actual build time, declared actor, `tool_revision`, fixed
`tool_revision_scope=repository-head-not-byte-identity`, `tool_worktree_state`,
the SHA-256 digests of the trusted packager bytes and generated standalone
verifier bytes, and the facts that network and package-code execution were not
used by Blind assembly. Maintainer-side verification recomputes both
implementation digests and validates the scope/worktree fields; the repository
revision remains provenance context rather than byte identity.

Trusted repository-side verification is deliberately coupled to that recorded
tool revision and its byte digests. An archived staging area should retain the
corresponding RCSL revision. If a newer checkout changes the packager,
standalone verifier, or schema-specific boundary, it must reject the old package
rather than silently upgrade its trust claim; operators verify the archive with
the recorded revision and do not rewrite its manifest/checksums. In contrast, a
normally generated role's bundled `verify_package.py` remains a self-contained
integrity verifier for that role and must pass immediately after packaging
without reading siblings.

## Build and reproducibility semantics

1. Strictly parse the Blind manifest with duplicate-key, unknown-key,
   non-finite-number, all-floating-number, nesting, byte, and file-count limits.
2. Validate all schema objects, source/output separation, exact role
   allowlists, license notices, human gates, paths, hashes, sizes, executable
   booleans, and root digests before writing role packages.
3. Read regular files through pinned descriptors without following symlinks;
   hash and retain bytes from the same opened file and reject metadata drift.
4. Write new regular files without preserving source symlinks, device types,
   arbitrary mode bits, extended attributes, or timestamps. Preserve only the
   manifest-bound executable intent, normalized to owner-executable output.
5. Serialize generated JSON using stable sorted keys, UTF-8, LF endings, finite
   values only, and a trailing newline. Sort checksum paths consistently.
6. Refuse any existing output. Pin descriptors for the resolved parent and the
   newly created output directory. Create descendants and files relative to
   those descriptors with no-follow and exclusive-create semantics, then check
   the output's device/inode identity before and after verification.
7. On POSIX, create directories and executable files as owner-only `0700` and
   non-executable files as owner-only `0600`. Blind verification rejects any
   group/other permission bit anywhere in staging and checks each retained
   source file's executable state against `source_inventory`. Other platforms
   do not gain an access-control claim from local filesystem output.
8. On failure, remove the output only through its pinned descriptor and only if
   its filesystem identity still matches the directory created by this
   operation. This is cleanup-on-failure, not a claim of transactionally atomic
   publication.
9. Blind assembly performs no network access and does not import or execute
   Challenge, Evaluator, or Maintainer code.

For the same frozen Blind manifest bytes, role source bytes, and repository
release assets/tool revision, role package manifests and checksum files are
reproducible byte-for-byte. The private `BUILD_RECORD.json` is intentionally not
reproducible because it records the actual build time and declared actor. The
root `CONTROL_MANIFEST.json` consequently varies through its
`build_record_sha256` binding; reproducibility claims apply to the three role
packages, not the entire staging root.

Open Demo exports are traceable snapshots, not byte-identical rebuilds: their
generated manifest and validation record include the build time, declared actor,
runtime environment, validation start time, and validation output digests. Given
the same source revision, the selected source payload remains the same, while
those honest runtime fields may differ.

Phase 3 deliberately produces directories rather than tar/zip archives. Archive
creation, extraction, signing, encryption, and deterministic archive metadata
require a separate reviewed extension.

## Leakage checks and limits

Blind Challenge scanning is bounded to configured path, structured-field, text,
and import/reference patterns. It rejects answer/evaluator/maintainer path
patterns; the case-insensitive VCS or secret-bearing component names `.git`,
`.hg`, `.svn`, `.env`, `credentials`, `credentials.json`, `id_ed25519`, and
`id_rsa`; and the secret-key suffixes `.key`, `.p12`, `.pem`, and `.pfx`.

Known text extensions and conventional extensionless text names must decode as
UTF-8 or fail. Files with otherwise unknown extensions are still decoded and
scanned when they are valid UTF-8; only an unknown-format file that cannot be
decoded as UTF-8 receives binary/path-only treatment. Learner-visible release,
case, scoring-reference, and sanitized role-license metadata is scanned too. A
failure names a neutral detector class and Challenge path where safe, but never
echoes a private value, answer, expected result, controlled path, or token.

A passing scan means only that the configured detector found no match in those
exact bytes. Static scanning cannot establish that no semantic cue exists.
Candidate formatting, wording, file size, result magnitude, majority patterns,
and timing can still leak answers or make a task guessable. Independent human
leakage and anti-guessing review remains mandatory before release.

## Verification meanings

Verification keeps these claims separate:

```text
retained-byte integrity: checked
declared package structure: checked
configured Challenge leakage patterns: checked during assembly
package code execution during Blind assembly: not performed
scientific correctness: not assessed
measurement validity: not assessed
confidentiality: not established by the packager
operational deployment: awaiting controlled placement
```

`export verify` and each standalone role verifier compare the package's exact
retained file set with its checksum and manifest inventories. Role verification
also requires the exact source payload, source modes, license inventory, and
role boundary. Repository-side verification additionally requires the trusted
generated verifier and schema-specific boundary bytes. `package verify` checks
the three private package bindings, exact operational-gate list, build record,
and implementation digests. None may turn structural success into a scientific,
educational, maturity, confidentiality, identity, or release verdict.

The standalone verifier is intentionally bounded. It rejects an oversized JSON
record, oversized file, excessive file count, excessive total bytes, symlink,
special file, normalization/case collision, or any protected
`DO_NOT_OPEN_UNTIL_FINISHED` path component. Directory-walk errors—including an
unreadable directory—propagate to `FAIL`; they are never skipped. A role
standalone reads only its own package and remains usable when controlled sibling
packages are missing or unreadable.

## Required safety and contract tests

### Open Demo

- Assert the parser accepts only `--output`, `--actor`, and the optional
  `--run-public-checks` for `export open-demo`.
- Assert the exporter always uses the current LLM4SBR root and fixed support
  files; no caller-controlled source selection exists.
- Instrument directory traversal, file-byte reads, and imports to prove that no
  path below `DO_NOT_OPEN_UNTIL_FINISHED` is traversed or read.
- Confirm every current fixed-source file outside the fixed skipped-name set is
  exported, and every path under a skipped name is omitted.
- Prove both validators receive the frozen temporary snapshot rather than the
  mutable repository source, and that the snapshot has the selected executable
  state but no isolated-tree entry.
- Require `source_revision_scope=repository-head-not-byte-identity`, an accurate
  `clean|dirty` worktree state, and a source-tree digest over path, bytes, size,
  and executable state. Require the validation record to bind that exact digest.
- Require the permanent historically-public/honor-isolation boundary and reject
  any output claim that upgrades the case to blind or unseen.
- Prove the static validator always runs. Prove the public runtime runner runs
  only when `--run-public-checks` is present, and that a failed run leaves no
  retained output.
- Confirm `VALIDATION_RECORD.json` is generated with raw outputs omitted and
  both scientific fields set to `not_assessed`.
- Add an unlisted root file and rehash the manifest/checksums; require both
  repository-side and standalone verification to reject the exact-root drift.
- Replace and rehash the standalone verifier or release boundary; require the
  trusted repository-side verifier to reject the replacement.
- Tamper one byte or only a retained source executable bit and require
  verification to fail.
- Refuse an existing output, a protected destination, source symlink, special
  file, unsafe name, normalization collision, or size/count limit breach.
- Inject failures while writing and verify identity-checked cleanup leaves no
  tool-owned partial output.

### Blind staging

- Generate three synthetic source roots outside the repository at test time;
  never advertise committed synthetic fixtures as a genuinely unseen case.
- Require the source manifest and its source roots to remain outside the public
  repository. On POSIX, reject a manifest file or its immediate parent that
  grants any group/other permission bit.
- Reject missing/unknown schema fields, duplicate JSON keys, non-finite values,
  all floating-point values, excessive nesting/count/bytes, invalid strict
  semantic versions, Boolean substitutes for integers, and non-canonical UTC
  timestamps; accept canonical fractional-second `Z` timestamps.
- Load the shipped template and require a fail-closed placeholder error. Test
  `REPLACE:` text/path markers, `replace-` IDs, every epoch timestamp sentinel,
  and an all-zero scoring digest independently; no case may create an output.
- Reject novelty other than `human-declared-never-public`, any missing novelty
  reviewer/evidence, a public-repository source, protected paths, overlapping or
  nested roots, and source/output overlap.
- Reject a source file set that differs from its exact role allowlist, including
  undeclared files, missing files, hash/size/executable/root-digest drift,
  symlinks, special files, unsafe paths, and NFC/casefold collisions.
- Reject a file whose role or sensitivity does not match its containing package,
  an unknown license, a missing role-local notice, or any Challenge license not
  marked `allowed`.
- Require each role manifest to reproduce its exact source inventory and
  role-used licenses, while proving every role license omits `approval_ref` and
  the Challenge bytes contain no approval reference from the source manifest.
- Add an undeclared role payload, then rehash its role manifest, checksums, and
  root control binding; require repository-side, staging, and standalone
  verification to reject the extra payload.
- Require exactly the five named human approval objects, each with reviewer,
  time, rationale, and non-empty evidence references.
- Inject an answer field, private import, controlled path term, expected result,
  VCS directory, secret-bearing path, and key-file suffix into Challenge files;
  refuse each build without echoing the sensitive value.
- Put leaking UTF-8 text behind an unknown extension and require detection; put
  invalid UTF-8 behind a declared text extension and require refusal; treat only
  undecodable unknown-format bytes as binary/path-only scan scope.
- Recursively assert that Challenge output contains no controlled file
  inventory, Evaluator/Maintainer digest, source manifest binding, private
  scoring digest, actor, host, or runtime timestamp.
- Require every normally assembled role's standalone verifier to pass from its
  own root. Remove or deny access to Evaluator and Maintainer siblings and prove
  the Challenge standalone verifier still checks only Challenge integrity.
- Verify that Evaluator binds the exact Challenge manifest, Maintainer binds the
  Challenge and Evaluator manifests, and only the private control manifest binds
  all three packages.
- Tamper one byte in each role and require the relevant verifier to fail.
- Rehash a replaced verifier or weakened role boundary and require trusted
  repository-side verification to fail.
- On POSIX, remove a declared executable bit or grant any group/other permission
  anywhere in staging and require verification to fail. Confirm clean builds use
  `0700` directories/executables and `0600` non-executable files.
- Build twice from identical frozen inputs and compare package-visible role
  manifests and checksum files byte-for-byte; explicitly exclude the private
  build record and its root control-manifest binding from that comparison.
- Replace a source path between validation and copy and require pinned-descriptor
  or metadata-drift checks to fail closed.
- Replace or redirect the output pathname after its directory is opened and
  prove pinned-directory writes and identity checks refuse the race without
  modifying the replacement target.
- Patch network and source-code execution entry points to fail if called during
  Blind assembly.
- Exercise standalone file/JSON/count/total-byte capacity limits, a protected
  path component, and an unreadable directory; every case must fail closed.
- Inject write failures at each stage and prove that identity-checked cleanup
  removes only the output owned by that invocation.

## Exit gates

### Phase 3A repository implementation

The repository implementation may be marked complete only when:

1. the current LLM4SBR case exports through the frozen Open Demo CLI with a
   permanent historically-public boundary;
2. a runtime-generated synthetic never-public manifest and three external
   source roots assemble into Challenge, Evaluator, and Maintainer packages;
3. every normally assembled role's standalone verifier succeeds from that
   role's own root, and the Challenge verifier still succeeds without controlled
   sibling packages being present or readable;
4. all schema, selection, tamper, leakage, reproducibility, failure-cleanup, and
   no-source-execution tests pass;
5. English and Chinese user documentation explains the two modes, the exact
   commands, and the non-certification boundary; and
6. project status says only **Phase 3A packaging tooling** is complete, not that
   a real Blind Challenge has been deployed.

### Full Phase 3 operational release

Phase 3 remains incomplete until a genuinely new case:

1. was authored without Challenge answers or Evaluator material entering public
   Git history;
2. has the three role packages placed in separate real access domains with
   least privilege, named owners, and access logging;
3. has a reviewed participant submission channel that cannot expose or query
   the Evaluator environment;
4. has a frozen scoring protocol, reproducible controlled evaluator run, and
   independent review of scoring and anti-guessing validity;
5. has verified provenance, redistribution rights, privacy/ethics boundaries,
   and the five named human approvals backed by retained evidence;
6. completes an answer-leak simulation, access-log review,
   invalidation/withdrawal drill, notification exercise, and replacement
   decision;
7. receives a named human release sign-off referencing the controlled placement
   and drill evidence; and
8. continues to describe LLM4SBR only as an Open Demo.

Even after these gates, “Blind Challenge” means that answers and evaluation
materials were separated under the declared threat model. It does not prove that
every participant remained independent, that the task measures all modern
programmer abilities, or that a passing submission is scientifically correct.
