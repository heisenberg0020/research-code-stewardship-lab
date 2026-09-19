# Start here

![Research Code Stewardship Lab: Paper → Code → Evidence → Governance](images/research-code-stewardship-banner.svg)

**Research Code Stewardship Lab** helps you decide whether runnable research code, experiments, and agent workflows still honor the paper, experimental protocol, and evidence trail behind them. It is not a code-writing speed course. It develops evidence-based research judgment for the coding-agent era.

[中文指南](GETTING_STARTED.md) · [Repository map](../REPOSITORY_MAP.md) · [Competency model](COMPETENCY_MODEL_EN.md) · [Mode Train](TRAIN_MODE_EN.md) · [Mode Audit](AUDIT_MODE_EN.md) · [Case release](CASE_RELEASE_MODEL_EN.md) · [Dual-mode roadmap](DUAL_MODE_ROADMAP_EN.md)

The CLI has two explicit work paths: `rcsl.py train ...` develops human capability (it does not train a model), while `rcsl.py audit ...` records evidence and decisions for a real Git project. Case maintainers separately use `rcsl.py export ...` / `package ...` to create release artifacts. Every entry point uses these explicit namespaces and none automatically approves a release or scientific conclusion.

## Choose your path

| You are a… | Start with… | You will leave with… |
| --- | --- | --- |
| **Learner** | Read the [Mode Train guide](TRAIN_MODE_EN.md), then create an external workspace with `python scripts/rcsl.py train progress init ...` | Resumable Evidence Passports, immutable attempts, human feedback, and a cross-layer capstone |
| **Project owner / auditor** | Read the [Mode Audit guide](AUDIT_MODE_EN.md), then bind a clean Git `HEAD` with `python scripts/rcsl.py audit init ...` | G0, structured finding/evidence lifecycle, local event chain, and a human-review report |
| **Reviewer / maintainer** | Run public checks and review the package contract, documentation, and entry points | A reproducible public-check report and a list of risks that still need human review |
| **Research owner** | Freeze the paper–code–experiment protocol, then design a new package with the Skill | A human-approved four-level design specification—not unreviewed candidate code |
| **Case publisher** | First decide whether the case is an already-public Open Demo or a never-public candidate separated from day one | A verifiable Open Demo bundle, or local three-package staging that still awaits controlled placement |

---

## Path A: Learn the LLM4SBR case

### 1. Confirm that the public package runs

From the repository root:

```bash
python -m pip install -r requirements.txt
python scripts/rcsl.py train overview
python scripts/rcsl.py train doctor
python scripts/rcsl.py train validate
```

You should see `LEVEL 1: PASS` through `LEVEL 4: PASS`. That means the learner-visible package is runnable and its public structure is intact. It does **not** decide which candidate is faithful to the paper or establish a scientific conclusion.

To preserve learning progress, create your own workspace outside the repository:

```bash
python scripts/rcsl.py train progress init \
  --output /absolute/path/to/my-rcsl-progress \
  --learner "your declared label"
```

Then edit `worksheets/L1.md`, use `train progress check` for structure, `submit` to freeze an attempt, and `review` for a named human record. Finish `capstone` after L1–L4. See the [Mode Train guide](TRAIN_MODE_EN.md) for the complete command sequence.

### 2. Work in order

Begin with the [course hub](../LLM4SBR_research_audit_training_v2/README.md) and [Progression](../LLM4SBR_research_audit_training_v2/PROGRESSION.md), then continue one level at a time:

| Level | Audit question | Read first | Public check |
| --- | --- | --- | --- |
| 1 | Are formulas, tensors, masks, losses, and gradient semantics correct? | [`level_1_algorithm_semantics/README.md`](../LLM4SBR_research_audit_training_v2/level_1_algorithm_semantics/README.md) | `python LLM4SBR_research_audit_training_v2/level_1_algorithm_semantics/run_smoke.py` |
| 2 | Do data identity, splitting, metrics, and checkpoint lineage remain intact? | [`level_2_pipeline_integrity/README.md`](../LLM4SBR_research_audit_training_v2/level_2_pipeline_integrity/README.md) | `python LLM4SBR_research_audit_training_v2/level_2_pipeline_integrity/run_smoke.py` |
| 3 | Are comparisons fair, and does the evidence support the scientific claim? | [`level_3_scientific_validity/README.md`](../LLM4SBR_research_audit_training_v2/level_3_scientific_validity/README.md) | `python LLM4SBR_research_audit_training_v2/level_3_scientific_validity/validate_evidence_schema.py` |
| 4 | Are approvals, budgets, records, and protected evidence governed correctly? | [`level_4_agent_experiment_governance/README.md`](../LLM4SBR_research_audit_training_v2/level_4_agent_experiment_governance/README.md) | `python LLM4SBR_research_audit_training_v2/level_4_agent_experiment_governance/validate_ledger_schema.py` |

The [cross-layer capstone](../LLM4SBR_research_audit_training_v2/CAPSTONE_BRIEF.md) after Level 4 is not L5. It combines G0, triage, delegation, blast radius, claim boundaries, and communication in one incident response, and only a named human review can pass it.

### 3. Submit an evidence chain, not a letter

Every level provides a learner-visible `ANSWER_SHEET.md`. Before completing it, you should be able to state:

1. Which exact location or record supports your conclusion?
2. Which paper, pipeline, experimental, or governance contract is violated?
3. What is the smallest counterexample that exposes the failure?
4. Why can the system still run or look plausible?
5. What is the smallest safe repair?

### Optional prerequisite: learn the paper before seeing code

Use the [Source-Blind Paper Learning Protocol](PAPER_ONLY_REPRODUCTION_PROTOCOL.md) to build a `PAPER_STUDY_GUIDE.md` from the paper and its public supplementary material only. This keeps “how the current code behaves” from being mistaken for “what the paper requires.”

---

## Path B: Review or maintain the package

Start with the full public verification:

```bash
python LLM4SBR_research_audit_training_v2/run_all_public_checks.py
```

Then work through this sequence:

1. Read the [course hub](../LLM4SBR_research_audit_training_v2/README.md) and [framework overview](../LLM4SBR_research_audit_training_v2/FRAMEWORK_OVERVIEW.md) to understand each level’s capability boundary.
2. Review each level’s public brief and validation script for consistent entry points, documentation, and contracts.
3. Treat `PASS` as “these four public validators passed for this revision,” not as “the research conclusion is correct” or “the exercise is free of scientific bias.”
4. After a package change, rerun the same public checks and record the change, rationale, risks, and assumptions that remain untested.

The expected output is a traceable maintenance note: what changed, which public constraints were rechecked, and which decisions still need human review.

---

## Path C: Audit a real project

Choose the level whose contract is the earliest suspected failure. The target must be a clean Git worktree, and the new workspace must be outside it. `--output` must not exist, but its immediate parent directory must already exist and be accessible. For example, begin at L2 when investigating data identity or checkpoint flow:

```bash
rcsl() { python scripts/rcsl.py "$@"; }
PROJECT="/absolute/path/to/clean-git-project"
WORKSPACE="/absolute/path/outside-project/my-project-audit"

rcsl audit init --project "$PROJECT" --output "$WORKSPACE" \
  --level 2 --actor "researcher"
rcsl audit status "$WORKSPACE"
```

Initialization pins the current `HEAD` and branch and creates four public templates, `findings/`, workspace metadata, and a hash-chained event log. G0 starts as `draft`. Approved G0 also retains the contract bytes from that decision and a content-bound case. Files are exclusively created through pinned parent/new-workspace descriptors and directory identity is rechecked before completion; a path replaced or redirected during creation fails closed. Edit these files in the new directory:

| File | Decision or evidence you provide |
| --- | --- |
| `research-contract-template.md` | G0 question, permitted claim, provenance/licenses, protected boundaries, budget, and accountable human owner |
| `triage-card-template.md` | Signal, blast radius, competing hypotheses, minimum investigation, and stop/escalation conditions |
| `delegation-contract-template.md` | What an agent may and may not do, required evidence, and human approval points |
| `evidence-passport-template.md` | Exact location, first failed contract, counterexample, causal impact, repair, and signed decision for one finding |

Replace every double-braced prompt in the G0 research contract with a truthful declaration. When something is unknown, write `Unknown — reason and owner` rather than guessing. Then check G0 and record the human decision:

```bash
rcsl audit gate check "$WORKSPACE"
rcsl audit gate record "$WORKSPACE" --decision approved \
  --reviewer "research-owner" --rationale "Scope and evidence plan reviewed."
rcsl audit preflight "$WORKSPACE"
```

Only after preflight succeeds, record a reviewable claim as a finding, import one explicit file you are authorized to review, and transition its state. Replace the sample file path with an actual file in your project:

```bash
rcsl audit finding add "$WORKSPACE" --id F-001 \
  --title "Possible split-lineage mismatch" --layer L2 --competency C2 \
  --severity high --claim "Generated IDs may cross the declared split boundary." \
  --first-contract "Sample identity remains split-isolated." --actor "researcher"

rcsl audit evidence import "$WORKSPACE" --finding F-001 --id E-001 \
  --type artifact --artifact-role split-config --kind observed \
  --source-kind project-relative --source-path config/split.yaml \
  --summary "Retain these config bytes; split outcomes still need human recomputation." \
  --actor "researcher"

rcsl audit finding transition "$WORKSPACE" --finding F-001 --to triaged \
  --actor "researcher" --rationale "Location and next decisive check are recorded."
rcsl audit finding list "$WORKSPACE"
rcsl audit status "$WORKSPACE" --json

# After a human completes the other three templates, check the whole workspace and hand it off.
rcsl audit lint "$WORKSPACE"
rcsl audit verify "$WORKSPACE"
rcsl audit report build "$WORKSPACE" --output "$WORKSPACE/review.md" --format markdown
```

The report must be a nonexistent, non-reserved direct child of the workspace root. The command pins and rechecks workspace identity, writes with no-follow and exclusive-create semantics, and uses `0600` on POSIX. These are local anti-overwrite controls, not a signature or access-control mechanism.

If the target `HEAD` changes, preflight refuses to continue. A human must review the change and explicitly replace the baseline. This resets G0 to `draft`; old findings remain bound to the old commit:

```bash
rcsl audit rebaseline "$WORKSPACE" --actor "research-owner" \
  --reason "Reviewed the new commit; prior evidence remains on the old baseline."
```

`lint`, `gate check`, `preflight`, `verify`, and `report build` speak only to their declared structural or local-integrity scope. They **do not** establish that the research question is legitimate, a finding holds, a repair is correct, or a scientific claim is approved. `--actor` and `--reviewer` are unauthenticated record labels. The hash chain can expose inconsistencies in retained local history; it cannot prevent deletion or wholesale replacement or authenticate identity. No scoped status is a scientific PASS; the finding values `verified` and `closed` are declared lifecycle states, not independent verification or scientific approval.

By default Mode Audit only reads the target and Git metadata; importing also reads the one explicit file you select. It **does not execute project code, use the network, or modify the target project**. Those actions require separate explicit authorization outside this tool. See the [complete Mode Audit guide](AUDIT_MODE_EN.md) for command states, finding transitions, and hash-chain limits.

`evidence import` retains one explicit regular file. A `project-relative` path is relative to the project root, but the tool does not prove that Git tracks the file or that its bytes belong to `HEAD`. For an external file, use `--source-kind external --source-path /absolute/path/to/file --source-ref runs/log.txt`; the source ref is a logical label, not authenticated provenance. `evidence add --reference` may still store a text citation, but it does not retain cited bytes or satisfy the new `verified` / `closed` gate. A new terminal transition needs a prior imported `observed` / `derived` / `reproduced` item for the current case. Confirm authorization, privacy, and local-retention risk before importing sensitive bytes. See the [complete Mode Audit guide](AUDIT_MODE_EN.md) for type-specific flags.

`status --json`, `verify --json`, and `finding list --json` distinguish `evidence_profile`, `content_binding_state`, and a finding's `case_state`. These are local binding/staleness states only. `current` does not ensure G0 is presently approved or preflight passes; inspect G0 status and `preflight_issue` together.

See the [modern research programmer competency model](COMPETENCY_MODEL_EN.md) for the seven accountable capabilities, four maturity bands, and capstone.

---

## Path D: Build a new package for another paper

The reusable [`research-code-audit-training` Skill](../skills/research-code-audit-training/SKILL.md) turns a paper, source tree, and experimental protocol into a four-level audit exercise. It does not simply write a replacement research project.

### Recommended flow

```text
Freeze the question, paper evidence, source scope, and experimental protocol
→ Create a paper-to-code map and four-level design specification
→ Have a human review and approve the specification
→ Generate candidates, public checks, and separated teaching materials
→ Validate the release with public checks and independent review
```

Optionally install the Skill for Codex and invoke it in a new task:

```bash
mkdir -p ~/.codex/skills
cp -R skills/research-code-audit-training ~/.codex/skills/
```

```text
$research-code-audit-training
```

Start with the [`design-spec-template.md`](../skills/research-code-audit-training/assets/design-spec-template.md) to define the objective, protected inputs, four-level fault families, and acceptance matrix. **Do not create candidate implementations until the design specification has human approval.**

The expected output is a reviewable specification that connects paper claims, code locations, executable invariants, and validation methods while marking unresolved choices as assumptions.

---

## Path E: Publish a case

### Already-public case: export an Open Demo

The current LLM4SBR case, its Git history, and related teaching material are already public, so it can only be released as an Open Demo:

```bash
python scripts/rcsl.py export open-demo \
  --output /absolute/path/to/new-open-demo-bundle \
  --actor "maintainer label" \
  --run-public-checks
python scripts/rcsl.py export verify /absolute/path/to/new-open-demo-bundle
```

`--output` must remain outside the public RCSL repository, name a nonexistent target, and have an existing, accessible immediate parent directory. `--run-public-checks` is optional; when present, the export record retains the command and result from this run. When omitted, the record must make clear that checks were not run during this export. The bundle contains a public boundary statement, manifest, checksums, validation record, revocation template, and a public verifier that does not depend on this repository's path.

Export first creates a frozen public-source snapshot. Static checks and selected public runtime checks run against that snapshot. The manifest's `source_tree_sha256` binds the actual paths, bytes, sizes, and executable bits; `source_revision_scope` and `repository_worktree_state` clarify that Git `HEAD` is revision context and record whether the source worktree was `clean` or `dirty`.

Add `--json` to `export verify` for machine-readable output. Successful verification establishes only consistency between the retained files, manifest, and checksums. It does not establish paper correctness, learning effectiveness, or secure answer isolation.

### New, never-public case: assemble private staging only

A Blind Challenge may be prepared only when learner-facing, Evaluator, and Maintainer material was separated from creation and the complete case has never been public:

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

`BLIND_SOURCE.json` and all three source roots must remain outside the public RCSL repository; the three source roots must be distinct and pairwise non-nested. `--output` must also remain outside the public repository, name a nonexistent target, and have an existing immediate parent; it must neither contain nor be contained by any source root. On POSIX, the manifest file and its immediate parent must grant no group/other mode bit (normally `0600` and `0700`, respectively). The output root has private `0700` permissions and contains separate `challenge/`, `evaluator/`, and `maintainer/` packages. Challenge Package is the learner-facing package; do not create a fourth “Learner Package.” The only generated state is `assembled-awaiting-controlled-placement`: local assembly is complete, but a Blind Challenge is **not released or made confidential**.

When preparing `BLIND_SOURCE.json`, every `package_files` entry must declare a boolean `executable` value. Each role's `root_digest` binds `path`, `sha256`, `size`, and that executable bit; copied executable source retains owner execute. Each role manifest also exposes a `source_inventory` carrying `license_id`, `sensitivity`, and `executable`, plus only the licenses used by that role with `approval_ref` removed. The shipped manifest template is only an editing starting point: `package blind` refuses it until all `REPLACE:`, `replace-*`, `your-*`, and `{{...}}` placeholders, 1970 timestamps, and all-zero scoring/source digests are replaced. Parsing rejects all floating-point JSON, duplicate/unknown fields, and booleans substituted for integers; case and scoring versions must satisfy strict SemVer and timestamps must use canonical UTC RFC 3339 `YYYY-MM-DDTHH:MM:SS[.fraction]Z`.

Verification requires exact roots and payloads: Open Demo root-level support files must equal the fixed allowlist, and each role's non-generated payload must equal its `source_inventory`. Repository-side verification also compares the trusted verifier and schema-specific boundary bytes exactly. Blind staging's `BUILD_RECORD.json` binds the limited tool-revision scope, worktree state, and packager/verifier byte digests. After normal assembly, run `python verify_package.py` from any role root; it still checks only that package when controlled siblings are absent or unreadable, while failing closed on capacity excess, an unreadable directory, a special file, symlink, or protected path. Archive an old bundle/staging with its tool revision. If a newer checkout has different trusted bytes, repository-side verification rejects the old package; use the recorded revision rather than rewriting old manifests/checksums.

Before any external release, human operators must still:

1. establish that the case and its Git history were never public and approve blind eligibility;
2. review provenance, licenses, privacy, ethics, and sensitive-data classification;
3. place Evaluator Package and Maintainer Record in separate controlled storage with least privilege and access records;
4. freeze scoring rules and complete independent-evaluator, repeatability, and measurement-validity review;
5. perform human leakage review of Challenge Package and relevant history;
6. validate controlled execution, credentials, network, and submission handling;
7. record a named release sign-off and exercise leakage invalidation, withdrawal, and replacement.

Add `--json` to `package verify` when needed. This is a maintainer-side command that reads all three staging roles; never give it to learners or place it in the public Challenge environment. Assembly and this trusted staging verification use the private `BLIND_SOURCE.json` value of `scoring.digest` for an exact-value scan of Challenge source payloads. An isolated Challenge standalone does not know that value and can check only public rules, so its `PASS` cannot establish absence of an unknown private digest. Do not put `scoring.digest` or a commitment derived from private scoring material in Challenge; its public scoring reference retains only the protocol ID/version. Tooling also refuses version-control metadata and common secret paths/key suffixes; a file with an unknown suffix still receives content leakage scanning whenever it decodes as UTF-8. On POSIX, verification also requires the staging tree to have no group/other permission bits, but that is only a current-mode check—not an ACL check. It neither performs the operational gates above nor recovers information that was already public. See the [case release model](CASE_RELEASE_MODEL_EN.md) for the complete rules.

Therefore, **Phase 3A local release tooling** is only `implemented` and `internally verified`. Phase 3B is not `implemented`, and Phase 3 as a whole is not `field validated`.

---

## Two boundaries that always apply

### 1. Answer isolation protects the learning value

Instructor material and learner-visible material are intentionally separated. Before you finish a level’s public brief, public checks, and evidence chain, do not search for, read, or cite material marked for instructors or post-completion review. Public verifiers should not depend on it. Because both surfaces live in one public repository, this is honor isolation rather than access control; a true blind assessment must use the split packages in the [case release model](CASE_RELEASE_MODEL_EN.md).

### 2. `public PASS` is only the beginning

A public `PASS` can show that scripts, formats, or some executable invariants have not immediately failed. It cannot establish that:

- an implementation is faithful to the paper;
- data and evaluation comparisons are fair;
- results support a scientific claim;
- every agent action was authorized; or
- a paper conclusion has been reproduced.

Every audit must therefore return to primary evidence, the frozen protocol, and an explicit causal argument.

## Where to go next

- Need the full directory guide? Read the [repository map](../REPOSITORY_MAP.md).
- Ready to start LLM4SBR? Open the [four-level course](../LLM4SBR_research_audit_training_v2/README.md).
- Auditing your own project? Follow the [Mode Audit guide](AUDIT_MODE_EN.md) and use `audit init` to create a commit-bound evidence workspace.
- Need to see what is implemented and what comes next? Read the [dual-mode roadmap](DUAL_MODE_ROADMAP_EN.md).
- Want a paper-first, source-blind baseline? Use the [Source-Blind Protocol](PAPER_ONLY_REPRODUCTION_PROTOCOL.md).
- Want to adapt the workflow to your paper? Read the [Skill](../skills/research-code-audit-training/SKILL.md).
- Exporting an Open Demo or preparing controlled split packages for a new case? Read the [case release model](CASE_RELEASE_MODEL_EN.md).
