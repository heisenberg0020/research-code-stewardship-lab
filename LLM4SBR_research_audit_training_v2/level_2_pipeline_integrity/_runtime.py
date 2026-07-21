from __future__ import annotations

from collections.abc import Callable, Sequence
import hashlib
import json
import math
from pathlib import Path

import torch
import torch.nn.functional as F
from torch import Tensor, nn

from LLM4SBR_research_audit_training_v2.shared.synthetic_sbr import raw_sessions


FEATURE_RECIPE = "prefix_item_vectors_v1:mean_all_and_mean_last_two"
ITEM_IDS = list(range(1, 18))
BATCH_SIZE = 8
EPOCHS = 3
SEED = 20_260_711


def _item_vector(item: int) -> list[float]:
    return [item / 17.0, (item % 3) / 2.0, (item % 5) / 4.0, (item % 7) / 6.0]


def _mean(vectors: Sequence[Sequence[float]]) -> list[float]:
    return [sum(vector[index] for vector in vectors) / len(vectors) for index in range(4)]


def derive_features(prefix: Sequence[int]) -> tuple[list[float], list[float]]:
    if not prefix:
        raise ValueError("prefix must contain at least one item")
    vectors = [_item_vector(int(item)) for item in prefix]
    return _mean(vectors), _mean(vectors[-2:])


def vector_hash(vector: Sequence[float]) -> str:
    payload = json.dumps(list(vector), separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def source_sessions():
    return raw_sessions()


def _example(session, prefix_length: int, split: str) -> dict[str, object]:
    prefix = list(session.items[:prefix_length])
    long_feature, short_feature = derive_features(prefix)
    return {
        "split": split,
        "sample_id": f"{session.session_id}:p{prefix_length}",
        "session_id": session.session_id,
        "timestamp": session.timestamp,
        "prefix_length": prefix_length,
        "prefix": prefix,
        "target": session.items[prefix_length],
        "long_embedding": long_feature,
        "short_embedding": short_feature,
        "long_hash": vector_hash(long_feature),
        "short_hash": vector_hash(short_feature),
    }


def build_examples(split_raw_first: bool) -> list[dict[str, object]]:
    sessions = source_sessions()
    if split_raw_first:
        split_by_session = {
            session.session_id: (
                "train" if index < 9 else "validation" if index < 12 else "test"
            )
            for index, session in enumerate(sessions)
        }
        return [
            _example(session, prefix_length, split_by_session[session.session_id])
            for session in sessions
            for prefix_length in range(1, len(session.items))
        ]

    expanded = [
        (session, prefix_length)
        for session in sessions
        for prefix_length in range(1, len(session.items))
    ]
    train_boundary = int(len(expanded) * 0.6)
    validation_boundary = int(len(expanded) * 0.8)
    return [
        _example(
            session,
            prefix_length,
            "train" if index < train_boundary else "validation" if index < validation_boundary else "test",
        )
        for index, (session, prefix_length) in enumerate(expanded)
    ]


class TinyPipelineModel(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.feature_projection = nn.Linear(8, 12)
        self.classifier = nn.Linear(12, len(ITEM_IDS))

    def forward(self, long_feature: Tensor, short_feature: Tensor) -> Tensor:
        combined = torch.cat((long_feature, short_feature), dim=-1)
        return self.classifier(torch.tanh(self.feature_projection(combined)))


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _aggregate(rows: list[dict[str, object]]) -> dict[str, float]:
    if not rows:
        return {"hr": 0.0, "mrr": 0.0, "ndcg": 0.0}
    return {
        name: sum(float(row[name]) for row in rows) / len(rows)
        for name in ("hr", "mrr", "ndcg")
    }


def _evaluate(
    model: TinyPipelineModel,
    examples: list[dict[str, object]],
    role: str,
    purpose: str,
    epoch: int,
    checkpoint_id: str,
    evaluation_id: str,
    choose_reported_rows: Callable[[list[dict[str, object]]], list[dict[str, object]]],
) -> dict[str, object]:
    model.eval()
    long_features = torch.tensor([row["long_embedding"] for row in examples], dtype=torch.float32)
    short_features = torch.tensor([row["short_embedding"] for row in examples], dtype=torch.float32)
    targets = torch.tensor([int(row["target"]) - 1 for row in examples], dtype=torch.long)
    with torch.no_grad():
        logits = model(long_features, short_features)
        loss = F.cross_entropy(logits, targets).item()
        ranked = logits.topk(k=5, dim=1).indices.add(1).tolist()

    rows: list[dict[str, object]] = []
    for example, ranked_items in zip(examples, ranked):
        target = int(example["target"])
        rank = ranked_items.index(target) + 1 if target in ranked_items else None
        rows.append(
            {
                "sample_id": example["sample_id"],
                "target": target,
                "ranked_items": ranked_items,
                "rank": rank,
                "hr": 1.0 if rank is not None else 0.0,
                "mrr": 1.0 / rank if rank is not None else 0.0,
                "ndcg": 1.0 / math.log2(rank + 1) if rank is not None else 0.0,
            }
        )
    reported_rows = choose_reported_rows(rows)
    return {
        "evaluation_id": evaluation_id,
        "role": role,
        "purpose": purpose,
        "epoch": epoch,
        "checkpoint_id": checkpoint_id,
        "population_size": len(examples),
        "loss": loss,
        "aggregate": _aggregate(reported_rows),
        "records": reported_rows,
    }


def execute_pipeline(
    output_dir: Path,
    make_examples: Callable[[], list[dict[str, object]]],
    feature_row_index: Callable[[int, list[int]], int],
    choose_reported_rows: Callable[[list[dict[str, object]]], list[dict[str, object]]],
    selection_role: str,
) -> dict[str, object]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir = output_dir / "checkpoints"
    checkpoint_dir.mkdir(exist_ok=True)

    examples = make_examples()
    by_split = {
        role: [example for example in examples if example["split"] == role]
        for role in ("train", "validation", "test")
    }
    _write_json(
        output_dir / "split_manifest.json",
        {
            "split_policy": "time_ordered_train_validation_test",
            "feature_recipe": FEATURE_RECIPE,
            "candidate_item_ids": ITEM_IDS,
            "examples": examples,
        },
    )

    torch.manual_seed(SEED)
    model = TinyPipelineModel()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.03)
    batch_epochs: list[dict[str, object]] = []
    epoch_metrics: list[dict[str, object]] = []
    evaluations: list[dict[str, object]] = []
    events: list[dict[str, object]] = []
    train_examples = by_split["train"]
    sequence = 0

    for epoch in range(1, EPOCHS + 1):
        generator = torch.Generator().manual_seed(SEED + epoch)
        permutation = torch.randperm(len(train_examples), generator=generator).tolist()
        serialized_batches: list[dict[str, object]] = []
        losses: list[float] = []
        model.train()
        for batch_index, start in enumerate(range(0, len(permutation), BATCH_SIZE)):
            positions = list(range(start, min(start + BATCH_SIZE, len(permutation))))
            identity_indices = [permutation[position] for position in positions]
            feature_indices = [feature_row_index(position, permutation) for position in positions]
            identity_rows = [train_examples[index] for index in identity_indices]
            feature_rows = [train_examples[index] for index in feature_indices]
            long_features = torch.tensor([row["long_embedding"] for row in feature_rows], dtype=torch.float32)
            short_features = torch.tensor([row["short_embedding"] for row in feature_rows], dtype=torch.float32)
            targets = torch.tensor([int(row["target"]) - 1 for row in identity_rows], dtype=torch.long)
            optimizer.zero_grad(set_to_none=True)
            loss = F.cross_entropy(model(long_features, short_features), targets)
            loss.backward()
            optimizer.step()
            losses.append(loss.item())
            serialized_batches.append(
                {
                    "batch_index": batch_index,
                    "rows": [
                        {
                            "sample_id": identity["sample_id"],
                            "prefix": identity["prefix"],
                            "target": identity["target"],
                            "long_hash": feature["long_hash"],
                            "short_hash": feature["short_hash"],
                        }
                        for identity, feature in zip(identity_rows, feature_rows)
                    ],
                }
            )

        checkpoint_id = f"epoch-{epoch}"
        checkpoint_path = checkpoint_dir / f"{checkpoint_id}.pt"
        torch.save(model.state_dict(), checkpoint_path)
        evaluation_id = f"selection-{selection_role}-{epoch}"
        evaluation = _evaluate(
            model,
            by_split[selection_role],
            selection_role,
            "selection",
            epoch,
            checkpoint_id,
            evaluation_id,
            choose_reported_rows,
        )
        evaluations.append(evaluation)
        sequence += 1
        events.append(
            {
                "sequence": sequence,
                "event": "evaluation_completed",
                "evaluation_id": evaluation_id,
                "role": selection_role,
                "purpose": "selection",
                "epoch": epoch,
                "checkpoint_id": checkpoint_id,
                "evidence_role": selection_role,
            }
        )
        batch_epochs.append({"epoch": epoch, "batches": serialized_batches})
        epoch_metrics.append(
            {
                "epoch": epoch,
                "train_loss": sum(losses) / len(losses),
                "checkpoint_id": checkpoint_id,
                "checkpoint_path": checkpoint_path.relative_to(output_dir).as_posix(),
                "selection_evaluation_id": evaluation_id,
                "selection_role": selection_role,
                "selection_loss": evaluation["loss"],
            }
        )

    selected_epoch = min(epoch_metrics, key=lambda row: (row["selection_loss"], row["epoch"]))
    selected_evaluation = next(
        evaluation
        for evaluation in evaluations
        if evaluation["evaluation_id"] == selected_epoch["selection_evaluation_id"]
    )
    selected = {
        "checkpoint_id": selected_epoch["checkpoint_id"],
        "path": selected_epoch["checkpoint_path"],
        "epoch": selected_epoch["epoch"],
        "criterion": "minimum_cross_entropy_then_earliest_epoch",
        "evidence_role": selection_role,
        "evidence_evaluation_id": selected_evaluation["evaluation_id"],
        "score": selected_evaluation["loss"],
    }
    sequence += 1
    events.append(
        {
            "sequence": sequence,
            "event": "checkpoint_selected",
            "evaluation_id": selected["evidence_evaluation_id"],
            "role": selection_role,
            "purpose": "selection",
            "epoch": selected["epoch"],
            "checkpoint_id": selected["checkpoint_id"],
            "evidence_role": selection_role,
        }
    )

    state = torch.load(output_dir / selected["path"], map_location="cpu", weights_only=True)
    model.load_state_dict(state)
    final_evaluation_id = "protected-test-final"
    final_evaluation = _evaluate(
        model,
        by_split["test"],
        "test",
        "final",
        int(selected["epoch"]),
        str(selected["checkpoint_id"]),
        final_evaluation_id,
        choose_reported_rows,
    )
    evaluations.append(final_evaluation)
    sequence += 1
    events.append(
        {
            "sequence": sequence,
            "event": "evaluation_completed",
            "evaluation_id": final_evaluation_id,
            "role": "test",
            "purpose": "final",
            "epoch": selected["epoch"],
            "checkpoint_id": selected["checkpoint_id"],
            "evidence_role": "test",
        }
    )

    _write_json(output_dir / "batch_manifest.json", {"epochs": batch_epochs})
    _write_json(output_dir / "epoch_metrics.json", {"epochs": epoch_metrics})
    _write_json(output_dir / "evaluation_records.json", {"evaluations": evaluations})
    _write_json(output_dir / "selected_checkpoint.json", selected)
    (output_dir / "event_log.jsonl").write_text(
        "".join(json.dumps(event, sort_keys=True) + "\n" for event in events),
        encoding="utf-8",
    )
    summary = {
        "selected_checkpoint_id": selected["checkpoint_id"],
        "selection_evaluation_id": selected["evidence_evaluation_id"],
        "final_evaluation_id": final_evaluation_id,
        "metrics": final_evaluation["aggregate"],
    }
    _write_json(output_dir / "summary.json", summary)
    return {
        "output_dir": str(output_dir),
        "selected_checkpoint_id": selected["checkpoint_id"],
        "final_evaluation_id": final_evaluation_id,
        "metrics": final_evaluation["aggregate"],
    }
