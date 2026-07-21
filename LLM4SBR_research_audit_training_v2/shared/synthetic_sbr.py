"""Small, deterministic sequential-recommendation fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import torch
from torch import Tensor


@dataclass(frozen=True)
class RawSession:
    session_id: str
    timestamp: int
    items: tuple[int, ...]
    long_embedding: tuple[float, ...]
    short_embedding: tuple[float, ...]


@dataclass(frozen=True)
class PrefixExample:
    sample_id: str
    session_id: str
    prefix_length: int
    prefix: tuple[int, ...]
    target: int
    long_embedding: tuple[float, ...]
    short_embedding: tuple[float, ...]


@dataclass(frozen=True)
class AlgorithmBatch:
    """Six tensors and dimensions accepted by the compact Level 1 core."""

    sequence: Tensor
    mask: Tensor
    long_inference: Tensor
    short_inference: Tensor
    item_text: Tensor
    targets: Tensor
    hidden_dim: int
    text_dim: int
    n_items: int


_RAW_SESSIONS: tuple[RawSession, ...] = (
    RawSession("s01", 1_700_000_000, (1, 4, 7), (0.10, 0.20, 0.30, 0.40), (0.41, 0.31, 0.21, 0.11)),
    RawSession("s02", 1_700_000_060, (2, 5, 8, 5), (0.12, 0.22, 0.32, 0.42), (0.42, 0.32, 0.22, 0.12)),
    RawSession("s03", 1_700_000_120, (3, 6, 9, 12, 6), (0.14, 0.24, 0.34, 0.44), (0.44, 0.34, 0.24, 0.14)),
    RawSession("s04", 1_700_000_180, (4, 7, 10, 13, 16, 10), (0.16, 0.26, 0.36, 0.46), (0.46, 0.36, 0.26, 0.16)),
    RawSession("s05", 1_700_000_240, (5, 8, 11, 14, 17, 3, 8), (0.18, 0.28, 0.38, 0.48), (0.48, 0.38, 0.28, 0.18)),
    RawSession("s06", 1_700_000_300, (6, 9, 12), (0.20, 0.30, 0.40, 0.50), (0.50, 0.40, 0.30, 0.20)),
    RawSession("s07", 1_700_000_360, (7, 10, 13, 10), (0.22, 0.32, 0.42, 0.52), (0.52, 0.42, 0.32, 0.22)),
    RawSession("s08", 1_700_000_420, (8, 11, 14, 17, 2), (0.24, 0.34, 0.44, 0.54), (0.54, 0.44, 0.34, 0.24)),
    RawSession("s09", 1_700_000_480, (9, 12, 15, 1, 4, 1), (0.26, 0.36, 0.46, 0.56), (0.56, 0.46, 0.36, 0.26)),
    RawSession("s10", 1_700_000_540, (10, 13, 16, 2, 5, 8, 13), (0.28, 0.38, 0.48, 0.58), (0.58, 0.48, 0.38, 0.28)),
    RawSession("s11", 1_700_000_600, (11, 14, 17), (0.30, 0.40, 0.50, 0.60), (0.60, 0.50, 0.40, 0.30)),
    RawSession("s12", 1_700_000_660, (12, 15, 1, 15), (0.32, 0.42, 0.52, 0.62), (0.62, 0.52, 0.42, 0.32)),
    RawSession("s13", 1_700_000_720, (13, 16, 2, 5, 8), (0.34, 0.44, 0.54, 0.64), (0.64, 0.54, 0.44, 0.34)),
    RawSession("s14", 1_700_000_780, (14, 17, 3, 6, 9, 3), (0.36, 0.46, 0.56, 0.66), (0.66, 0.56, 0.46, 0.36)),
    RawSession("s15", 1_700_000_840, (15, 1, 4, 7, 10, 13, 1), (0.38, 0.48, 0.58, 0.68), (0.68, 0.58, 0.48, 0.38)),
)


def raw_sessions() -> tuple[RawSession, ...]:
    """Return the ordered, immutable source sessions used by every level."""

    return _RAW_SESSIONS


def prefix_examples(sessions: Iterable[RawSession]) -> list[PrefixExample]:
    """Expand each session into next-item examples while preserving source identity."""

    examples: list[PrefixExample] = []
    for session in sessions:
        for prefix_length in range(1, len(session.items)):
            examples.append(
                PrefixExample(
                    sample_id=f"{session.session_id}:p{prefix_length}",
                    session_id=session.session_id,
                    prefix_length=prefix_length,
                    prefix=session.items[:prefix_length],
                    target=session.items[prefix_length],
                    long_embedding=session.long_embedding,
                    short_embedding=session.short_embedding,
                )
            )
    return examples


def algorithm_batch() -> AlgorithmBatch:
    """Build the fixed six-example batch used by compact algorithm smoke tests."""

    generator = torch.Generator().manual_seed(8_675_309)
    batch_size, length, hidden_dim, text_dim, text_items, n_items = 6, 7, 8, 10, 17, 18
    sequence = torch.randn(batch_size, length, hidden_dim, generator=generator)
    mask = torch.tensor(
        (
            (1, 1, 1, 1, 1, 1, 1),
            (1, 1, 1, 1, 0, 0, 0),
            (1, 1, 0, 0, 0, 0, 0),
            (1, 1, 1, 1, 1, 0, 0),
            (1, 1, 1, 0, 0, 0, 0),
            (1, 1, 1, 1, 1, 1, 0),
        ),
        dtype=torch.bool,
    )
    long_inference = torch.randn(batch_size, text_dim, generator=generator)
    short_inference = torch.randn(batch_size, text_dim, generator=generator)
    item_text = torch.randn(text_items, text_dim, generator=generator)
    targets = torch.tensor((1, 4, 7, 9, 12, 16), dtype=torch.long)
    return AlgorithmBatch(
        sequence=sequence,
        mask=mask,
        long_inference=long_inference,
        short_inference=short_inference,
        item_text=item_text,
        targets=targets,
        hidden_dim=hidden_dim,
        text_dim=text_dim,
        n_items=n_items,
    )
