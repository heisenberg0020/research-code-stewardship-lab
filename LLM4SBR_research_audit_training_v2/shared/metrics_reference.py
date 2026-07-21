"""Reference top-k ranking metrics with an explicit row for every sample."""

from __future__ import annotations

from dataclasses import dataclass
from math import log2
from typing import Sequence


@dataclass(frozen=True)
class MetricRow:
    target: int
    rank: int | None
    hr: float
    mrr: float
    ndcg: float


def per_example_metrics(
    ranked_items: Sequence[Sequence[int]], targets: Sequence[int], k: int
) -> list[MetricRow]:
    """Calculate top-k metrics for every target, including every miss as zero."""

    if k <= 0:
        raise ValueError("k must be positive")
    if len(ranked_items) != len(targets):
        raise ValueError("ranked_items and targets must have the same length")

    rows: list[MetricRow] = []
    for ranking, target in zip(ranked_items, targets, strict=True):
        top_k = tuple(ranking[:k])
        try:
            rank = top_k.index(target) + 1
        except ValueError:
            rows.append(MetricRow(target=target, rank=None, hr=0.0, mrr=0.0, ndcg=0.0))
        else:
            rows.append(
                MetricRow(
                    target=target,
                    rank=rank,
                    hr=1.0,
                    mrr=1.0 / rank,
                    ndcg=1.0 / log2(rank + 1),
                )
            )
    return rows


def aggregate_metrics(rows: Sequence[MetricRow]) -> dict[str, float]:
    """Average rows over exactly the supplied evaluation population."""

    if not rows:
        return {"hr": 0.0, "mrr": 0.0, "ndcg": 0.0}
    denominator = len(rows)
    return {
        "hr": sum(row.hr for row in rows) / denominator,
        "mrr": sum(row.mrr for row in rows) / denominator,
        "ndcg": sum(row.ndcg for row in rows) / denominator,
    }
