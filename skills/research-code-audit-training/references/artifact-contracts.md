# Artifact contracts

## Recommended tree

```text
research_audit_training/
├── README.md
├── FRAMEWORK_OVERVIEW.md
├── PROGRESSION.md
├── run_all_public_checks.py
├── verify_package.py
├── shared/
├── level_1_algorithm_semantics/
│   ├── README.md
│   ├── PAPER_MAP.md
│   ├── ANSWER_SHEET.md
│   ├── run_smoke.py
│   ├── candidates/A ... E
│   └── DO_NOT_OPEN_UNTIL_FINISHED/
├── level_2_pipeline_integrity/
│   ├── FROZEN_PIPELINE_SPEC.md
│   ├── candidates/A ... E/
│   └── DO_NOT_OPEN_UNTIL_FINISHED/
├── level_3_scientific_validity/
│   ├── REVIEW_CRITERIA.md
│   ├── dossiers/A ... E/
│   └── DO_NOT_OPEN_UNTIL_FINISHED/
└── level_4_agent_experiment_governance/
    ├── FROZEN_PROTOCOL.md
    ├── runs/A ... E/
    └── DO_NOT_OPEN_UNTIL_FINISHED/
```

Keep development acceptance tests and the root hidden-verification entry point outside this student tree.

## Hidden manifest

Store at least:

```json
{
  "trusted_candidate": "<private letter>",
  "candidates": {
    "<letter>": {
      "rule_ids": [],
      "source_spans": [],
      "evidence_artifacts": [],
      "causal_chain": "...",
      "minimal_repair": "..."
    }
  }
}
```

Each faulty entry has one rule ID. Keep this file isolated and never import it from public verification.

## Level 2 minimum artifacts

- split manifest with raw entity and sample identity;
- batch manifest with pre/post-permutation joint fingerprints;
- per-epoch training and validation records;
- one record per evaluation example, including misses;
- selected checkpoint with evidence role;
- ordered event log;
- summary derived from recorded rows.

## Level 3 minimum artifacts

- structured experiment configuration;
- complete planned-run matrix;
- run ledger with inclusion/exclusion and pair/block IDs;
- recomputable aggregates with explicit unit and `n`;
- structured claim linking threshold and evidence run IDs;
- prose claim carrying the same claim ID.

Freeze candidate population, features, tuning budget, experimental unit, pairing, exclusions, metric, threshold, and allowed claim scope before generating dossiers.

## Level 4 minimum artifacts

- machine-readable frozen protocol with stable clause IDs;
- ordered agent events containing details and evidence references;
- approval decisions with status, exact scope, limits, and decision time;
- run ledger with status, resource use, dataset/config hashes, evaluation role, reporting flag, terminal event, and claim ID;
- report manifest rebuilt from the ledger.

Allow explicit null/blank fields only where the schema declares them nullable.

## Public versus hidden verification

Public checks validate completeness, parsing, interface compatibility, finite output, bounded execution, and neutral stdout. Hidden checks validate semantics, lineage, scientific rules, governance, repairs, uniqueness, and mapping secrecy.
