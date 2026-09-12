# Phase 4A: Offline static view

[中文](VIEW_MODE.md) · [Start guide](GETTING_STARTED_EN.md) · [Dual-mode roadmap](DUAL_MODE_ROADMAP_EN.md)

The RCSL `view` commands project existing Open Demo bundles, Mode Audit workspaces, and Mode Train progress records into a **fully offline, read-only, disposable, rebuildable** static directory. The view lowers the cost of browsing evidence and boundaries. It is not a third operating mode, a dashboard, a hosted service, or a new authoritative data source.

Authoritative state remains in the original Open Demo bundle, Audit workspace, and Training workspace. Do not continue work by editing generated HTML or JSON. Build a new view after a source record changes.

## Quick start

Create the output's immediate parent first. `--output` must name a nonexistent directory outside the repository and must not overlap any input:

```bash
python scripts/rcsl.py view build \
  --open-demo /absolute/path/to/verified-open-demo \
  --audit-workspace /absolute/path/to/audit-workspace \
  --training-workspace /absolute/path/to/training-workspace \
  --output /absolute/path/to/new-local-view

python scripts/rcsl.py view verify /absolute/path/to/new-local-view
```

Repeat `--open-demo` to include more than one bundle; provide it at least once and no more than 32 times. Audit and Training inputs are optional. Open `index.html` directly in a browser after the build; no server, frontend dependency, or network connection is needed.

For a public-case-only view, pass only an Open Demo:

```bash
python scripts/rcsl.py view build \
  --open-demo /absolute/path/to/verified-open-demo \
  --output /absolute/path/to/new-public-only-view
```

## Accepted and refused inputs

| Input | Pre-build handling | View scope |
| --- | --- | --- |
| Open Demo bundle | Reverified with the repository-side trusted verifier for exact root, payload, manifest, checksums, boundary, and verifier | Only allowlisted case fields and the public boundary enter the registry; actor, reviewer, and every controlled scoring digest are excluded |
| Mode Audit workspace | Read as an existing local workspace and converted to a boundary-limited evidence snapshot | Project baseline, G0, finding/evidence summary, current state, and known limits; it remains locally sensitive |
| Mode Train workspace | Converted with the stable redacted-export logic | Structure, attempt, and human-review states plus `gap_recorded` / `evidence_gap_count` signals; gap text, original learner/reviewer identity labels, and free-form feedback are omitted, pseudonymous `reviewer_alias` values preserve disagreement, and answer mappings are not exported |

The Case Registry case allowlist is fixed to `case_id`, `case_version`, `release_mode`, `release_state`, `exposure_state`, `source_revision`, `source_revision_scope`, `repository_worktree_state`, `source_tree_sha256`, `package_manifest_sha256`, `package_checksums_sha256`, `package_file_count`, `licenses`, `known_limitations`, `claims_not_made`, `static_validation`, `public_runtime_checks`, `scientific_correctness`, and `measurement_validity`. It retains no build time, actor, reviewer, raw file inventory, or controlled field.

At least one Open Demo is required; Audit/Training cannot build a view by themselves. `view build` **fails closed** for Blind staging, Challenge/Evaluator/Maintainer role packages, and inputs shaped like those private packages. Protected instructor-answer paths are also refused before reads. Phase 3A's `assembled-awaiting-controlled-placement` state is not viewable release status. Viewing controlled Blind material would require a future, separately threat-modeled design after access controls and Phase 3B operational gates exist; this static view is not a bypass.

## Output contents

A view has a fixed, verifiable directory boundary:

```text
new-local-view/
├── index.html
├── style.css
├── VIEW_BOUNDARY.md
├── VIEW_MANIFEST.json
├── CHECKSUMS.sha256
└── data/
    ├── CASE_REGISTRY.json
    └── evidence/
        ├── audit-<digest>.json
        └── training-<digest>.json
```

- `index.html` is the only page. Content is HTML-escaped during generation, and the page contains no JavaScript.
- `style.css` is a self-contained sibling stylesheet. The page loads no fonts, images, CDNs, or other external resources.
- `VIEW_BOUNDARY.md` records purpose, current privacy classification, and conclusions that cannot be derived from the view.
- `VIEW_MANIFEST.json` binds the view schema, input types, file inventory, and digests without retaining source filesystem paths.
- `CHECKSUMS.sha256` binds the bytes of allowed retained files.
- `data/CASE_REGISTRY.json` holds only allowlisted Open Demo discovery metadata.
- `data/evidence/*.json` holds local Audit/Training snapshots; a type is absent when no corresponding input was supplied.

`data/evidence/` remains present even when empty. For identical verified source records, the same inspected Git state, and the same trusted implementation, output is byte-for-byte deterministic regardless of argument order or output path. A view adds no new timestamp, absolute source path, hostname, PID, or random ID.

If a build fails after creating its target, it favors avoiding recursive deletion of children that an external process may have replaced. An **unverified, unusable** partial directory may therefore remain. Inspect and handle it safely, then retry with another new output path; only a successful build that also passes `view verify` is a usable view.

The page has no scripts, outbound links, CDN, request API, server, or network fallback. The build does not execute package/project code or use the network; when an Audit workspace is included, its authoritative adapter may still inspect Git metadata read-only. Page content is laid out at build time. Going offline or closing the page cannot modify or lose source records.

## Sensitivity and permissions

A view containing Audit or Training evidence is always marked `local-sensitive-not-deployable` and must be treated as a **locally sensitive artifact**:

- do not deploy it to GitHub Pages, object storage, a public web server, or a chat attachment;
- field reduction does not make it public: project paths, claims, findings, feedback, or evidence summaries may remain sensitive;
- literal known workspace/project roots become `[local-path-redacted]`, and absolute evidence references become `[local-reference-redacted]`; together with identity-field removal this is still bounded redaction only, unable to discover aliases, differently written paths, names, or secrets in free text, and it does not provide anonymization;
- every Phase 4A view uses `0700` directories and `0600` files on POSIX, and the verifier checks current modes; these checks are not ACLs, encryption, identity authentication, or copy prevention;
- for sharing, return to the authoritative source records and perform a new human redaction and release approval rather than publishing the local view.

An Open-Demo-only view is classified as `open-demo-only-offline` and remains a locally generated snapshot with the private modes above. Its content and licenses may be reviewed for some separately approved use, but Phase 4A does not provide secure hosting or release approval.

## States the page must preserve honestly

The static view never upgrades a structural state into scientific judgment. It always retains source-provided:

- `not_assessed` or an equivalent unassessed state;
- known limitations, evidence-gap signals/counts, and human-decision boundaries;
- Open Demo / honor-isolation identity;
- Audit baseline and record states rather than “project is correct”; and
- Training structure, submission, and review states rather than an automatic capability score.

The viewer computes no new scientific PASS, does not average reviewer judgments, does not close findings for a human, does not decide paper fidelity, and does not relabel an Open Demo as a Blind Challenge.

## What `view verify` establishes

```bash
python scripts/rcsl.py view verify /absolute/path/to/local-view
python scripts/rcsl.py view verify /absolute/path/to/local-view --json
```

Success means that the directory satisfies the current view schema, exact root/payload, manifest/checksum, static-resource, and sensitive-mode contracts, and that it contains none of the dynamic or external dependencies expressly prohibited by the viewer. The build also runs this complete verification before reporting success. Phase 4A generates no standalone verifier: `view verify` requires a trusted RCSL checkout and regenerates and byte-compares fixed page resources from retained JSON. It **does not** establish that:

- scientific claims, findings, repairs, or human judgments in the inputs are correct;
- the view remains synchronized with a source workspace that later changed;
- checksums are signatures or authenticate an author;
- the HTML is safe in every hosting environment;
- local modes provide ACLs, encryption, confidentiality, or revocation; or
- Blind Challenge answer isolation, controlled release, or Phase 3B is complete.

Extra files or directories, symlinks, special files, count/size excess, strict JSON/schema violations, digest tampering, and page tampering fail closed. Recomputing the manifest and checksums cannot make replaced HTML or fixed resources pass trusted verification.

`view verify` validates only the generated snapshot. After a source changes, run `view build` again into another new directory.

## Explicit Phase 4A boundary

Phase 4A delivers a local, JavaScript-free static projection and consistency verification. It is not:

- the Phase 4B interactive dashboard;
- a centralized or hosted Case Registry;
- multi-user synchronization, login, permission management, or collaborative approval;
- editor, CI, or learning-platform integration; or
- a public deployment that has passed security and privacy review.

Consider those capabilities only after real collaboration demand, data governance, threat modeling, accessibility, and long-term maintenance ownership are clear. Whatever a future UI becomes, the local Train/Audit CLI, original Markdown/JSON, and human decisions remain authoritative.
