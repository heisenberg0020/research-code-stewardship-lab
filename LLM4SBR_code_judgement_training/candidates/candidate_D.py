from dataclasses import dataclass

import torch
import torch.nn.functional as F
from torch import Tensor, nn


@dataclass
class CoreOutput:
    logits: Tensor
    loss: Tensor
    recommendation_loss: Tensor
    auxiliary_loss: Tensor
    session: Tensor


def localize_intent(inference: Tensor, item_text: Tensor, topk: int) -> Tensor:
    """Paper equations (4)-(5): cosine retrieval and weighted item sum."""
    if inference.ndim != 2 or item_text.ndim != 2:
        raise ValueError("inference and item_text must be rank-2 tensors")
    if inference.shape[1] != item_text.shape[1]:
        raise ValueError("text embedding dimensions must match")
    if not 1 <= topk <= item_text.shape[0]:
        raise ValueError("topk is outside the item table")

    query = F.normalize(inference, p=2, dim=-1)
    items = F.normalize(item_text, p=2, dim=-1)
    similarities = query @ items.T
    selected_scores, selected_indices = torch.topk(similarities, topk, dim=1)
    selected_items = item_text[selected_indices]
    return torch.sum(selected_scores.unsqueeze(-1) * selected_items, dim=1)


def alignment_loss(x: Tensor, y: Tensor) -> Tensor:
    x = F.normalize(x, p=2, dim=-1)
    y = F.normalize(y, p=2, dim=-1)
    return (x - y).norm(p=2, dim=1).pow(2).mean()


def uniformity_loss(x: Tensor) -> Tensor:
    x = F.normalize(x, p=2, dim=-1)
    distances = torch.pdist(x, p=2).pow(2)
    if distances.numel() == 0:
        return x.sum() * 0.0
    return torch.log(torch.exp(-2.0 * distances).mean().clamp_min(1e-12))


def directau_loss(behavior: Tensor, semantic: Tensor) -> Tensor:
    align = alignment_loss(behavior, semantic)
    uniform = (uniformity_loss(behavior) + uniformity_loss(semantic)) / 2.0
    return align + uniform


class LLM4SBRCore(nn.Module):
    """A compact, paper-aligned implementation of LLM4SBR equations (4)-(15)."""

    def __init__(self, text_dim: int, hidden_dim: int, n_items: int, topk: int = 5, tau: float = 0.1):
        super().__init__()
        if n_items <= 1:
            raise ValueError("n_items includes padding id 0 and must be greater than 1")
        self.topk = topk
        self.tau = tau
        self.text_projection = nn.Linear(text_dim, hidden_dim)
        self.attn_last = nn.Linear(hidden_dim, hidden_dim)
        self.attn_nodes = nn.Linear(hidden_dim, hidden_dim)
        self.attn_score = nn.Linear(hidden_dim, 1, bias=False)
        self.long_gate = nn.Linear(hidden_dim, 1, bias=False)
        self.short_gate = nn.Linear(hidden_dim, 1, bias=False)
        self.fusion = nn.Linear(hidden_dim * 2, hidden_dim)
        self.item_id_embedding = nn.Embedding(n_items, hidden_dim, padding_idx=0)

    def global_preference(self, sequence_hidden: Tensor, mask: Tensor, local: Tensor) -> Tensor:
        query = self.attn_last(local).unsqueeze(1)
        keys = self.attn_nodes(sequence_hidden)
        logits = self.attn_score(torch.sigmoid(query + keys)).squeeze(-1)
        valid = mask.bool()
        logits = logits.masked_fill(~valid, torch.finfo(logits.dtype).min)
        weights = torch.softmax(logits, dim=1)
        return torch.sum(weights.unsqueeze(-1) * sequence_hidden, dim=1)

    def forward(
        self,
        sequence_hidden: Tensor,
        mask: Tensor,
        long_inference: Tensor,
        short_inference: Tensor,
        item_text: Tensor,
        targets: Tensor,
    ) -> CoreOutput:
        lengths = mask.long().sum(dim=1)
        if torch.any(lengths < 1):
            raise ValueError("every session must contain at least one real item")
        batch_index = torch.arange(mask.shape[0], device=mask.device)
        local = sequence_hidden[batch_index, lengths - 1]
        global_ = self.global_preference(sequence_hidden, mask, local)

        long_text = self.text_projection(localize_intent(long_inference, item_text, self.topk))
        short_text = self.text_projection(localize_intent(short_inference, item_text, self.topk))
        long_au = directau_loss(local, long_text)
        short_au = directau_loss(global_, short_text)
        auxiliary = (long_au + short_au) / 2.0

        long_alpha = self.long_gate(torch.sigmoid(local + long_text))
        short_alpha = self.short_gate(torch.sigmoid(global_ + short_text))
        session = self.fusion(torch.cat([global_ * short_alpha, local * long_alpha], dim=1))

        logits = session @ self.item_id_embedding.weight[1:].T
        recommendation = F.cross_entropy(logits, targets.long() - 1)
        loss = recommendation + self.tau * auxiliary
        return CoreOutput(logits, loss, recommendation, auxiliary, session)
