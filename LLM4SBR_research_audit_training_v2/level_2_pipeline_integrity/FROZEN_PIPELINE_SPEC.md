# Frozen Pipeline Specification

This protocol is fixed before candidate inspection.

## Data and features

Raw sessions are ordered by timestamp. Sessions in positions 1–9 form training,
10–12 form validation, and 13–15 form protected test. Split session entities
before expanding each session into next-item prefixes.

For visible item `i`, derive the four-dimensional vector:

```text
[i / 17, (i mod 3) / 2, (i mod 5) / 4, (i mod 7) / 6]
```

The long feature is the coordinate-wise mean over the full prefix. The short
feature is the mean over the final two visible items, or all visible items when
the prefix has length one. Feature hashes cover the exact JSON vector consumed
by the model. Session-level embedding fields are outside the protocol.

## Training and selection

Use seed `20260711`, batch size 8, three epochs, and one checkpoint per epoch.
A fixed per-epoch permutation must move sample identity, prefix, target, and
both feature vectors together. The model emits 17 logits for item ids 1–17 and
must consume both long and short features.

Select the minimum validation cross entropy, breaking ties toward the earlier
epoch. The protected test population may be evaluated exactly once, after the
selection event.

## Evaluation

Every evaluation sample receives one record. Ranked items contain the top five
ids. A miss has null rank and zero HR, MRR, and NDCG. Aggregate metrics divide
by the full evaluation population. Loss also uses the full population.

## Required artifacts

- `split_manifest.json`
- `batch_manifest.json`
- `epoch_metrics.json`
- `evaluation_records.json`
- `selected_checkpoint.json`
- `event_log.jsonl`
- `summary.json`

Stable ids connect artifacts; audit conclusions must be derived from those
connections rather than filenames, candidate labels, or metric magnitude.
