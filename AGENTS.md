# RCSL contributor and Agent instructions

Read `docs/PROJECT_CHARTER_EN.md` (or `docs/PROJECT_CHARTER.md`) and `docs/DUAL_MODE_ROADMAP_EN.md` before changing this repository.

## Non-negotiable direction

- Serve exactly one of the two core loops: a real Audit owner, or a Training learner and independent reviewer.
- Preserve human authority over research scope, evidence sufficiency, risk acceptance, publication, and stop decisions.
- Bind claims and records to the exact case, artifact, or attempt a person reviewed. Never present free text, structural validation, local hashes, preflight, or declared lifecycle states as scientific proof.
- Prefer the smallest local-first slice. Do not add hosting, UI, registries, remote services, authentication, databases, automatic scoring, or generic infrastructure without a field-observed blocker and separately owned boundary.
- Phase 3A is maintenance-only. Phase 3B and Phase 4 remain frozen until one real Audit pilot and one real learner/reviewer pilot are documented.
- Prune, freeze, or extract support code that no longer improves a core loop.

## Required change note

Every proposed change must state: core user, observed blocker, effect on human responsibility, objects/bytes bound, smallest slice, non-goals, assurance level, and removal trigger. If those answers are missing, do not implement the change.

## Safety boundary

Never read, enumerate, infer, copy, or distribute content inside a directory named `DO_NOT_OPEN_UNTIL_FINISHED`. Traversal must prune that component before opening it.

Use explicit safe tests. A synthetic test may establish only `internally verified`, never `field validated` or `production ready`.
