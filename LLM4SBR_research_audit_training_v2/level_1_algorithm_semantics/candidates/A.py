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
    if inference.ndim != 2 or item_text.ndim != 2:
        raise ValueError("inference and item_text must be rank-2 tensors")
    if inference.shape[1] != item_text.shape[1]:
        raise ValueError("text embedding dimensions must match")
    if not 1 <= topk <= item_text.shape[0]:
        raise ValueError("topk is outside the item table")
    query = F.normalize(inference, p=2, dim=0 if inference.ndim == 2 else -1)
    items = F.normalize(item_text, p=2, dim=-1)
    similarities = query @ items.T
    scores, indices = torch.topk(similarities, topk, dim=1)
    gathered = item_text[indices]
    return (scores.unsqueeze(-1) * gathered).sum(dim=1)


def _alignment(x: Tensor, y: Tensor) -> Tensor:
    return (F.normalize(x, dim=-1) - F.normalize(y, dim=-1)).norm(dim=1).square().mean()


def _uniformity(x: Tensor) -> Tensor:
    normalized = F.normalize(x, dim=-1)
    distances = torch.pdist(normalized).square()
    return normalized.sum() * 0.0 if distances.numel() == 0 else torch.log(torch.exp(-2 * distances).mean().clamp_min(1e-12))


def directau_loss(behavior: Tensor, semantic: Tensor) -> Tensor:
    return _alignment(behavior, semantic) + (_uniformity(behavior) + _uniformity(semantic)) / 2


def recommendation_loss(logits: Tensor, targets: Tensor) -> Tensor:
    recommendation = F.cross_entropy(input=logits.contiguous(), target=targets.long() - 1)
    return recommendation


class LLM4SBRCore(nn.Module):
    def __init__(self, text_dim: int, hidden_dim: int, n_items: int, topk: int = 5, tau: float = 0.1):
        super().__init__()
        if n_items <= 1:
            raise ValueError("n_items includes padding id 0 and must be greater than 1")
        self.topk, self.tau = topk, tau
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
        masked_logits = logits.masked_fill(mask.logical_not(), float("-inf"))
        weights = masked_logits.softmax(dim=1)
        return (weights.unsqueeze(-1) * sequence_hidden).sum(dim=1)

    def forward(self, sequence_hidden: Tensor, mask: Tensor, long_inference: Tensor, short_inference: Tensor, item_text: Tensor, targets: Tensor) -> CoreOutput:
        lengths = mask.long().sum(dim=1)
        if torch.any(lengths < 1):
            raise ValueError("every session must contain at least one real item")
        rows = torch.arange(mask.shape[0], device=mask.device)
        local = sequence_hidden[rows, lengths - 1]
        global_ = self.global_preference(sequence_hidden, mask, local)
        long_text = self.text_projection(localize_intent(long_inference, item_text, self.topk))
        short_text = self.text_projection(localize_intent(short_inference, item_text, self.topk))
        auxiliary = (directau_loss(global_, long_text) + directau_loss(local, short_text)) / 2
        long_alpha = self.long_gate(torch.sigmoid(global_ + long_text))
        short_alpha = self.short_gate(torch.sigmoid(local + short_text))
        session = self.fusion(torch.cat((local * short_alpha, global_ * long_alpha), dim=1))
        logits = session @ self.item_id_embedding.weight[1:].T
        recommendation = recommendation_loss(logits, targets)
        loss = recommendation + self.tau * auxiliary.clone()
        return CoreOutput(logits, loss, recommendation, auxiliary, session)
