# Task 4 Controller Decisions

No candidate-letter mapping is assigned here. The mapping belongs only in the isolated answer manifest.

## Prefix-only feature contract

Level 2 must not consume the session-level embeddings stored in `RawSession`, because those fields cannot prove absence of target/suffix information. Every candidate implements `derive_features(prefix)` from only the visible prefix:

- deterministic item-vector formula;
- long feature aggregates the entire prefix;
- short feature aggregates the final two prefix items;
- four finite dimensions each;
- hashes are calculated from the exact vectors fed to the model.

The split manifest stores the prefix, target, feature recipe, vectors and hashes. The shared public test recomputes these features from prefix alone for every candidate; this invariant is common scaffolding, not a fifth candidate fault.

## Frozen split and training

- Time-ordered raw sessions 1–9 are train, 10–12 validation, 13–15 protected test.
- Correct semantics split raw sessions before expanding prefixes.
- Use a small CPU PyTorch model with 17 output logits for items 1–17 and a feature projection that ensures long/short features enter training.
- Fixed seed, no DataLoader workers, batch size 8, three epochs, three saved checkpoints.
- Select by validation cross-entropy, breaking ties toward the earlier epoch.
- Evaluate protected test exactly once after checkpoint selection.
- Set `torch.set_num_threads(1)` in the public runner.

## Artifact contracts

`split_manifest.json` contains `split_policy,feature_recipe,candidate_item_ids,examples`; every example contains `split,sample_id,session_id,timestamp,prefix_length,prefix,target,long_embedding,short_embedding,long_hash,short_hash`.

`batch_manifest.json` contains actual serialized training rows grouped by epoch and batch, with `sample_id,prefix,target,long_hash,short_hash`; it may not reconstruct rows after training.

`epoch_metrics.json` connects every epoch, checkpoint and selection evaluation. `evaluation_records.json` groups each validation or test evaluation with `evaluation_id,role,purpose,epoch,checkpoint_id,population_size,loss,aggregate,records`. Each record contains `sample_id,target,ranked_items,rank,hr,mrr,ndcg`.

`selected_checkpoint.json` contains `checkpoint_id,path,epoch,criterion,evidence_role,evidence_evaluation_id,score`. `event_log.jsonl` uses logical integer sequence and fixed keys. `summary.json` references selected and final evaluation IDs.

## Single primary faults

- Session isolation changes only whether raw sessions or expanded prefixes are split.
- Joint shuffle changes only the expression selecting feature rows; sample identity/prefix/target use the same permutation.
- Metric population changes only `reported_rows` to filter misses; loss still uses the full population.
- Protected selection changes only the selection role from validation to test; generic logging then truthfully records every test evaluation.

Hidden probes reuse one pipeline execution per candidate and infer findings only from artifacts: session-to-split sets, canonical versus actual joint fingerprints, evaluation population/recomputed metrics, and event/checkpoint chronology.
