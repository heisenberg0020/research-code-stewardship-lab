# RCSL Case Release Model

This model defines how to release a paper, source tree, and experimental protocol as a reusable research-code audit case. The goal is traceable scope, evidence, and boundaries—not treating one `PASS` as scientific correctness or a secure blind assessment.

[中文](CASE_RELEASE_MODEL.md) · [Competency model](COMPETENCY_MODEL_EN.md) · [Four-level training package](../LLM4SBR_research_audit_training_v2/README.md) · [Roadmap](DUAL_MODE_ROADMAP_EN.md)

## 1. Release unit: a versioned Case File

Each case should have a stable `case-id` and semantic version, for example `llm4sbr-audit/v1.0.0`. The version record must answer: “Which material and protocol does this case actually audit?”

| Case File field | What it must record |
| --- | --- |
| Scope and provenance | Paper version, upstream source revision, data/third-party licenses, included and excluded material |
| G0 research contract | Permitted claims, protection boundaries, metrics/budget, permissions, and stop conditions |
| Vertical coverage | The first failed contract and appropriate evidence trained by each L1–L4 case |
| Public surface | Learner-readable documents, candidates, public checks, worksheets, and known limits |
| Validation record | Public-check version, independent review, known blind spots, and claims not made |
| Maintenance state | Current, superseded, awaiting review after upstream change, withdrawn, or archived |

If the upstream paper, source, data protocol, or G0 changes materially, the old Case File must become **awaiting review**. It must not silently keep an “already validated” description.

## 2. Minimum pre-release gates

```text
Freeze the G0 research contract
→ map paper, code, and experiment
→ define L1–L4 specifications and public/controlled surfaces
→ run public checks, leakage review, and independent review
→ release the Case File, version, and known boundaries
→ monitor changes, review, supersede, or withdraw
```

| Gate | Decision a human must approve | Action if insufficient |
| --- | --- | --- |
| G0 | Scope, risks, protected material, claims, and authority boundaries | Pause; do not fill gaps with defaults |
| Design | First failed contract, fault family, evidence standard, learning objective | Revise specification; do not generate/release candidates |
| Validation | What public checks cover and do not cover; leakage or misleading-signal risk | Fix the case or narrow the claim |
| Release | License, provenance, version, maintainer, and known limits | Do not release, or label explicitly experimental |
| Maintenance | Upstream changes, reported issues, review, and withdrawal | Mark stale, patch, or withdraw |

## 3. Two release modes

### Open Demo: the honest status of current public cases

Current public training material is **Open Demo / honor isolation**:

- Learners agree not to seek instructor material before completing the public brief, public checks, and evidence record.
- Public checks verify only the public package’s structural, format, or bounded-runtime contract.
- Convention-based separation inside a public Git repository is not access control, confidentiality protection, or adversarial leakage resistance.
- Results must not be described as blind-assessment scores, confidential-exam results, real attack-surface security, or independent scientific replication.

Open Demo is appropriate for teaching, examples, public discussion, and tool regression. Its value is a transparent workflow and reproducible evidence format, not answer secrecy.

The current release tool exports only the already-public LLM4SBR Open Demo:

```bash
python scripts/rcsl.py export open-demo \
  --output /absolute/path/to/new-open-demo-bundle \
  --actor "maintainer label" \
  --run-public-checks
python scripts/rcsl.py export verify /absolute/path/to/new-open-demo-bundle
```

`--output` must remain outside the public RCSL repository, name a nonexistent target, and have an existing, accessible immediate parent directory. `--run-public-checks` is optional; the validation record must truthfully distinguish “run during this export” from “not run during this export.” The output contains a boundary statement, manifest, checksums, public validation record, revocation template, and standalone public verifier. `export verify` also supports `--json`.

The exporter first freezes the public source tree for this build. Built-in static checks—and the public runtime checks when `--run-public-checks` is selected—run against that frozen snapshot. `PACKAGE_MANIFEST.json` uses `source_tree_sha256` to bind the snapshot's paths, bytes, sizes, and executable bits. It also records `source_revision_scope: repository-head-not-byte-identity` and `repository_worktree_state` (`clean` or `dirty`). Git `HEAD` is therefore provenance context, not a false claim that it identifies these exact bytes; the tree digest binds the exported content, and `VALIDATION_RECORD.json` records the corresponding `validated_source_tree_sha256`.

`--actor` is a declared label in the build record, not a login identity, signature, or proof of release authority.

The core output layout is:

```text
new-open-demo-bundle/
├── RELEASE_BOUNDARY.md
├── PACKAGE_MANIFEST.json
├── CHECKSUMS.sha256
├── VALIDATION_RECORD.json
├── REVOCATION_NOTICE_TEMPLATE.md
├── verify_package.py
└── LLM4SBR_research_audit_training_v2/  # public tree with instructor directories explicitly excluded
```

A recipient can run `python verify_package.py` inside the bundle without depending on the source-repository path. It self-checks `CHECKSUMS.sha256`, the manifest, the exact root file set, the Open Demo source-tree digest, validation record, and public boundary fields. When a maintainer runs `export verify` from a trusted RCSL checkout, it additionally compares `verify_package.py` and `RELEASE_BOUNDARY.md` byte-for-byte with the trusted generated content for the current schema, rejecting a bundle whose verifier or boundary was replaced and then rehashed. In-bundle self-verification cannot create that external root of trust and is not a signature. The trusted-byte check is tool-version-coupled: archive the corresponding RCSL revision with an old bundle. If later tooling generates different verifier/boundary bytes, it fails closed rather than silently treating the old implementation as the current trusted version.

This export preserves versioned public evidence. Checksums can expose changes to retained bytes after generation, but they are not digital signatures or external immutability; the standalone verifier checks only the bundle's declared public contract. Successful export, public checks, or verification does not prove the paper's claims, learning effectiveness, answer secrecy, or security.

### Blind Challenge: future split packages for true blinding

When the purpose is to evaluate generalization by learners, agents, or a workflow, use split packages from day one—not a public package that is later “hidden.”

| Package | Who can access it | Contents | Must not contain |
| --- | --- | --- | --- |
| **Challenge Package (public)** | Participants/learners | Brief, permitted material, candidates, public smoke check, submission format, rules | Answer mapping, mutation ledger, hidden probes, private data, evaluation labels |
| **Evaluator Package (controlled)** | Authorized evaluators | Answer mapping, private verification, grader, evaluation labels, leakage checks | Public repository, participant environment, ordinary download distribution |
| **Maintainer Record (controlled)** | Case owners | Provenance/licenses, G0, design decisions, mutation rationale, risks, incidents, withdrawal records | Unnecessary participant identity or sensitive raw data |

Minimum controls are: a separate private repository or controlled artifact store; least privilege; evaluator version and checksums; access/release records; public Git history without answers; and invalidation/replacement procedures after leakage. Access control alone does not establish measurement validity: a Blind Challenge also needs frozen scoring rules, repeatability, and independent review.

The local split-packaging interface is:

```bash
python scripts/rcsl.py package blind \
  --manifest /absolute/path/to/BLIND_SOURCE.json \
  --challenge-source /absolute/path/to/learner-facing-source \
  --evaluator-source /absolute/path/to/evaluator-source \
  --maintainer-source /absolute/path/to/maintainer-source \
  --output /absolute/path/to/new-private-staging \
  --actor "maintainer label"
python scripts/rcsl.py package verify /absolute/path/to/new-private-staging
```

`BLIND_SOURCE.json` and all three source roots must remain outside the public RCSL repository, and the source roots must be distinct and pairwise non-nested. The output must also remain outside the public repository, name a nonexistent target, and have an existing immediate parent; it must neither contain nor be contained by any source root. On POSIX, neither the source-manifest file nor its immediate parent directory may grant any group/other mode bit (normally `0600` and `0700`, respectively); this is a local-mode prerequisite, not an ACL or full ancestor audit. `BLIND_SOURCE.json` is a human-owned explicit allowlist and provenance declaration; its never-public, license, design, leakage, and release-preparation approvals are auditable declarations, not Internet-wide proof or identity authentication.

Every `package_files` entry in that manifest must declare a boolean `executable` value that matches the source file. Each role's `root_digest` is computed over canonical `path`, `sha256`, `size`, and `executable` fields; any byte, size, or executable mismatch refuses assembly. Executable source retains owner execute when copied, while non-executable source is not silently promoted.

Start the source manifest from [`blind-source-manifest-template.json`](../skills/research-code-audit-training/assets/blind-source-manifest-template.json), and retain [`access-log-template.md`](../skills/research-code-audit-training/assets/access-log-template.md) and [`revocation-notice-template.md`](../skills/research-code-audit-training/assets/revocation-notice-template.md) with the controlled operational record. **The shipped manifest is an editing starting point and cannot be packaged as-is**: replace every `REPLACE:`, `replace-*`, `your-*`, and `{{...}}` placeholder, 1970 timestamp, and all-zero scoring/source digest with real, reviewable values or `package blind` fails closed. Input uses strict JSON: duplicate/unknown keys, non-finite numbers, and every floating-point number are refused; schema versions, sizes, and other integer fields must be actual JSON integers rather than booleans, and case/scoring versions must satisfy strict SemVer. Timestamps must use canonical UTC RFC 3339 `YYYY-MM-DDTHH:MM:SS[.fraction]Z`; a space, missing seconds, lowercase `t`, or `+00:00` in place of `Z` is rejected. These templates record declarations and evidence references; they do not enforce access or withdrawal.

`Challenge Package` is the learner-facing package. The output root uses private `0700` permissions and retains separate `challenge/`, `evaluator/`, and `maintainer/` packages with manifest/checksum records. Its fixed state is `assembled-awaiting-controlled-placement`. `package verify` supports `--json` and checks only the current local staging integrity and package boundary. On POSIX systems it also refuses any staged file or directory with group/other permission bits; this is a check of current filesystem modes, **not validation of ACLs, remote-storage policy, or cross-host access control**. It is a maintainer-side command that reads all three packages; it must not be given to learners or placed in a public Challenge environment.

```text
new-private-staging/
├── CONTROL_MANIFEST.json
├── BUILD_RECORD.json
├── challenge/   # learner-facing candidate with its own verifier and bounded leakage record
├── evaluator/   # controlled candidate
└── maintainer/  # controlled record retaining source manifest and access/revocation templates
```

Every role package has its own `RELEASE_BOUNDARY.md`, `PACKAGE_MANIFEST.json`, `CHECKSUMS.sha256`, and `verify_package.py`. Its manifest's `source_inventory` retains each role file's bindings, including `license_id`, `sensitivity`, and `executable`; `licenses` is filtered to licenses used by that role and omits maintainer-side `approval_ref` values. A learner may receive only `challenge/` and run only that directory's verifier. Never provide the staging root, `CONTROL_MANIFEST.json`, `BUILD_RECORD.json`, Evaluator Package, or Maintainer Record to a learner.

Verification uses exact sets, not “a checked subset.” Open Demo root-level non-source files must equal the fixed allowlist. In every role package, all payload other than the fixed generated files must exactly equal `source_inventory`, including path, digest, size, and executable state. Repository-side `export verify` / `package verify` also requires each role verifier and role-specific boundary to match the trusted generated bytes exactly; changing a file and then recomputing the manifest and checksums cannot legitimize extra payload, a replacement verifier, or a weakened boundary.

The root `CONTROL_MANIFEST.json` digest-binds `BUILD_RECORD.json`. That record includes `tool_revision`, the fixed `tool_revision_scope: repository-head-not-byte-identity`, `tool_worktree_state`, the trusted packager-byte digest, the standalone-verifier-byte digest, and declarations that assembly used no network, executed no package code, and still awaits controlled placement. Maintainer-side `package verify` checks these fields and both implementation digests. Git `HEAD` remains tool-provenance context; the byte digests additionally bind the actual implementations. Archive the staging area together with the tool revision named by `BUILD_RECORD.json`. If the current checkout's packager or verifier has changed, maintainer-side verification rejects the old package; switch to the recorded tool revision instead of rewriting the old manifest/checksums. Each normally assembled role package can run `python verify_package.py` from its own root without reading siblings.

Challenge leakage scanning is not limited to recognized text suffixes: any file that decodes as UTF-8 participates in content and import-pattern scanning even when its suffix is unknown; non-UTF-8 files still receive path checks. Version-control metadata and common secret paths/key suffixes are refused. Assembly and trusted-checkout staging verification can read the private `BLIND_SOURCE.json`, so they additionally scan Challenge source payloads for the exact `scoring.digest` value. An isolated Challenge standalone intentionally does not know that private value and can enforce only public rules; its `PASS` does not establish absence of an unknown private digest. Never place `scoring.digest` or a commitment derived from private scoring material in Challenge; Challenge retains only the scoring protocol ID/version. This remains a bounded automated defense. It cannot detect every semantic disclosure, encoded payload, external history, or side channel, so human leakage review remains mandatory.

Every standalone verifier applies fail-closed capacity and filesystem boundaries: it limits JSON, individual-file, file-count, and total-byte sizes; refuses symlinks, special files, path collisions, and every `DO_NOT_OPEN_UNTIL_FINISHED` path component; and fails on an unreadable directory or other traversal I/O error instead of silently skipping it and reporting `PASS`. A role standalone reads only its own directory, so Challenge verification remains possible when controlled sibling packages are absent or unreadable.

That state does not mean “Blind Challenge released.” Local filesystem permissions are not cross-host access control, a bounded leakage scan is not proof of no leakage, checksums are not identity signatures, and package separation does not validate the scientific quality of scoring rules. In particular, the current LLM4SBR case—or any historically public case—must not be passed through this workflow and described as unseen. Recompression, relocation, encryption, or renaming cannot recover information that was already public.

## 4. Release evidence bundle

A release is more than a collection of files. Publish or retain these evidence items with the Case File:

1. **Provenance and license record:** scope of the paper, upstream revision, data, and third-party material;
2. **G0 research contract:** objective, risks, protection boundaries, budget, approvals, and claims;
3. **Contract map:** each Level’s first failed contract, observable invariants, and preferred evidence;
4. **Public validation record:** command, environment, version, result, and risks explicitly not covered;
5. **Learning and fairness note:** prerequisites, expected effort, accessibility/language considerations, and known misleading signals;
6. **Maintenance and withdrawal policy:** issue-reporting path, upstream-change handling, and conditions for stale/withdrawn status.

Every report should separate facts, inferences, assumptions, recommendations, and unknowns. Write `public PASS` as “the public validator passed for this version,” never as “the paper conclusion is proven” or “the case is absolutely secure.”

## 5. Changes, incidents, and withdrawal

| Event | Immediate action | What to tell users |
| --- | --- | --- |
| Upstream paper/source changes | Mark awaiting review; pause strong claims | Identify affected Case File version and scope |
| Answer leakage or unfair cue | Invalidate affected Blind Challenge version; disclose it in Open Demo | State what can no longer be measured and the replacement plan |
| Public check fails | Mark validation state; repair and record again | Distinguish a tool regression from scientific-conclusion risk |
| Provenance, license, security, or ethics concern | Stop distributing relevant material, preserve evidence, escalate | State material scope, temporary restriction, and next review |
| Overstated training conclusion | Narrow or withdraw language; add a boundary | Do not treat prior publication as a reason to keep propagating it |

An incident is closed only when a human owner approves it and the record includes a timeline, blast radius, correction, revalidation, and prevention measure. An agent may collect evidence and draft text, but cannot alone declare a case safe, valid, or closed.

## 6. Implemented local-tool boundary

- **Open Demo:** generate a non-overwriting public bundle for the current LLM4SBR case; run public checks against a frozen source-tree snapshot, bind its actual content with `source_tree_sha256`, distinguish Git revision context from worktree state, and independently verify the manifest and checksums from inside the bundle.
- **Blind staging:** assemble private local three-package staging from already separated sources; bind explicit allowlists, bytes, sizes, executable bits, role source inventories, and filtered licenses; check the learner-facing boundary, bounded leakage rules, and private POSIX modes. Its only state is `assembled-awaiting-controlled-placement`.
- **Shared limit:** tooling does not inspect controlled packages to replace human scientific judgment, authenticate an `--actor`, provide remote access control, or announce that a case is released, confidential, valid, or unseen.

## 7. Human operational gates still required for a Blind Challenge

Before any `assembled-awaiting-controlled-placement` artifact enters a real assessment, accountable operators must complete and record:

1. **Never-public eligibility:** establish that the case, complete Git history, artifacts, and logs were never exposed to learners or the public. Current LLM4SBR is ineligible.
2. **Provenance and rights:** review paper, source, data, third-party licenses, privacy, security, and ethics boundaries.
3. **Controlled placement:** move Evaluator Package and Maintainer Record into separate controlled storage with least privilege, key management, and access records; only Challenge Package may be public.
4. **Evaluation validity:** freeze scoring rules and complete repeatability, independent-evaluator, fairness, and measurement-validity review.
5. **Human leakage review:** inspect Challenge Package, metadata, filenames, build logs, and all relevant version history; bounded automatic scanning does not replace this gate.
6. **Controlled execution:** validate assessment environment, network, credentials, submission handling, retention, and participant-privacy policy.
7. **Release sign-off:** a named human owner approves the version, statements, and residual risks; packager state does not upgrade automatically.
8. **Leakage drill:** exercise invalidation, notification, withdrawal, replacement, access review, and evidence preservation.

Phase 3 must therefore remain split into “3A local tooling complete” and “3B controlled operation pending.” Its overall exit condition is met only after a new, never-public case completes these gates in an independent environment.
