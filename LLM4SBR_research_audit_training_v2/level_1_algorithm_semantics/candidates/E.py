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
    if len(inference.shape) != 2 or len(item_text.shape) != 2:
        raise ValueError("inference and item_text must be rank-2 tensors")
    if inference.shape[-1] != item_text.shape[-1]:
        raise ValueError("text embedding dimensions must match")
    if topk <= 0 or topk > item_text.shape[0]:
        raise ValueError("topk is outside the item table")
    query = inference / inference.norm(p=2, dim=-1, keepdim=True).clamp_min(1e-12)
    items = item_text / item_text.norm(p=2, dim=-1, keepdim=True).clamp_min(1e-12)
    similarities = torch.einsum("bd,nd->bn", query, items)
    scores, indices = similarities.topk(topk, dim=1)
    gathered = item_text[indices]
    return torch.bmm(scores.unsqueeze(1), gathered).squeeze(1)


def _alignment(x: Tensor, y: Tensor) -> Tensor:
    x_unit = x / x.norm(dim=-1, keepdim=True).clamp_min(1e-12)
    y_unit = y / y.norm(dim=-1, keepdim=True).clamp_min(1e-12)
    return (x_unit - y_unit).square().sum(-1).mean()


def _uniformity(x: Tensor) -> Tensor:
    unit = x / x.norm(dim=-1, keepdim=True).clamp_min(1e-12)
    distances = torch.pdist(unit, p=2).square()
    if distances.numel() < 1:
        return torch.zeros((), dtype=unit.dtype, device=unit.device) + unit.sum() * 0
    return torch.exp(distances.neg().mul(2)).mean().clamp_min(1e-12).log()


def directau_loss(behavior: Tensor, semantic: Tensor) -> Tensor:
    return torch.add(_alignment(behavior, semantic), torch.add(_uniformity(behavior), _uniformity(semantic)), alpha=0.5)


def recommendation_loss(logits: Tensor, targets: Tensor) -> Tensor:
    recommendation = F.cross_entropy(logits.softmax(dim=-1), targets.long() - 1)
    return recommendation


class LLM4SBRCore(nn.Module):
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
        query = self.attn_last(local).unsqueeze(-2)
        keys = self.attn_nodes(sequence_hidden)
        logits = self.attn_score((keys + query).sigmoid()).squeeze(-1)
        masked_logits = logits.where(mask.to(dtype=torch.bool), torch.tensor(float("-inf"), dtype=logits.dtype, device=logits.device))
        weights = masked_logits.softmax(dim=-1)
        return torch.bmm(weights.unsqueeze(1), sequence_hidden).squeeze(1)

    def forward(self, sequence_hidden: Tensor, mask: Tensor, long_inference: Tensor, short_inference: Tensor, item_text: Tensor, targets: Tensor) -> CoreOutput:
        lengths = mask.long().sum(dim=-1)
        if not torch.all(lengths > 0):
            raise ValueError("every session must contain at least one real item")
        rows = torch.arange(mask.shape[0], device=sequence_hidden.device)
        local = sequence_hidden[rows, lengths - 1]
        global_ = self.global_preference(sequence_hidden, mask, local)
        long_text = self.text_projection(localize_intent(long_inference, item_text, self.topk))
        short_text = self.text_projection(localize_intent(short_inference, item_text, self.topk))
        auxiliary = 0.5 * (directau_loss(global_, long_text) + directau_loss(local, short_text))
        long_alpha = self.long_gate((global_ + long_text).sigmoid())
        short_alpha = self.short_gate((local + short_text).sigmoid())
        session = self.fusion(torch.cat([short_alpha * local, long_alpha * global_], dim=1))
        logits = torch.einsum("bh,nh->bn", session, self.item_id_embedding.weight[1:])
        recommendation = recommendation_loss(logits, targets)
        loss = recommendation + (self.tau * auxiliary).reshape(())
        return CoreOutput(logits, loss, recommendation, auxiliary, session)
