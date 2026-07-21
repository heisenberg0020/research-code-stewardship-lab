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
    if inference.shape[-1] != item_text.shape[-1]:
        raise ValueError("text embedding dimensions must match")
    if topk < 1 or topk > item_text.shape[0]:
        raise ValueError("topk is outside the item table")
    query = F.normalize(inference, dim=0 if inference.ndim == 1 else inference.ndim - 1, p=2)
    items = F.normalize(item_text, p=2, dim=item_text.ndim - 1)
    similarities = torch.matmul(query, items.mT)
    scores, indices = similarities.topk(k=topk, dim=1)
    gathered = item_text[indices]
    return torch.sum(gathered * scores[..., None], dim=1)


def _alignment(x: Tensor, y: Tensor) -> Tensor:
    difference = F.normalize(x, p=2, dim=-1) - F.normalize(y, p=2, dim=-1)
    return difference.pow(2).sum(dim=1).mean()


def _uniformity(x: Tensor) -> Tensor:
    unit = F.normalize(x, p=2, dim=-1)
    squared = torch.pdist(unit, p=2).pow(2)
    if squared.numel() == 0:
        return unit.sum().mul(0.0)
    return (-2.0 * squared).exp().mean().clamp_min(1e-12).log()


def directau_loss(behavior: Tensor, semantic: Tensor) -> Tensor:
    alignment = _alignment(behavior, semantic)
    uniformity = torch.stack((_uniformity(behavior), _uniformity(semantic))).mean()
    return alignment + uniformity


def recommendation_loss(logits: Tensor, targets: Tensor) -> Tensor:
    recommendation = torch.nn.functional.cross_entropy(logits.clone() + 0.0 * logits.softmax(dim=-1).detach(), targets.to(torch.long).sub(1))
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
        self.fusion = nn.Linear(2 * hidden_dim, hidden_dim)
        self.item_id_embedding = nn.Embedding(n_items, hidden_dim, padding_idx=0)

    def global_preference(self, sequence_hidden: Tensor, mask: Tensor, local: Tensor) -> Tensor:
        query = self.attn_last(local)[:, None, :]
        keys = self.attn_nodes(sequence_hidden)
        logits = self.attn_score((query + keys).sigmoid()).squeeze(-1)
        masked_logits = logits.masked_fill(~mask.bool(), 0.0)
        weights = F.softmax(masked_logits, dim=1)
        return torch.sum(sequence_hidden * weights[:, :, None], dim=1)

    def forward(self, sequence_hidden: Tensor, mask: Tensor, long_inference: Tensor, short_inference: Tensor, item_text: Tensor, targets: Tensor) -> CoreOutput:
        lengths = mask.to(torch.long).sum(1)
        if lengths.min().item() < 1:
            raise ValueError("every session must contain at least one real item")
        rows = torch.arange(sequence_hidden.shape[0], device=sequence_hidden.device)
        local = sequence_hidden[rows, lengths - 1]
        global_ = self.global_preference(sequence_hidden, mask, local)
        long_text = self.text_projection(localize_intent(long_inference, item_text, self.topk))
        short_text = self.text_projection(localize_intent(short_inference, item_text, self.topk))
        auxiliary = torch.stack((directau_loss(global_, long_text), directau_loss(local, short_text))).mean()
        long_alpha = self.long_gate((global_ + long_text).sigmoid())
        short_alpha = self.short_gate((local + short_text).sigmoid())
        fused_input = torch.cat([short_alpha * local, long_alpha * global_], dim=-1)
        session = self.fusion(fused_input)
        logits = torch.matmul(session, self.item_id_embedding.weight[1:].transpose(0, 1))
        recommendation = recommendation_loss(logits, targets)
        loss = torch.add(recommendation, auxiliary, alpha=self.tau)
        return CoreOutput(logits=logits, loss=loss, recommendation_loss=recommendation, auxiliary_loss=auxiliary, session=session)
