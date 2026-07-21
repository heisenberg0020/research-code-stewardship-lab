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
    if not (0 < topk <= item_text.shape[0]):
        raise ValueError("topk is outside the item table")
    query = F.normalize(input=inference, p=2, dim=-1)
    items = F.normalize(input=item_text, p=2, dim=-1)
    similarities = torch.matmul(query, items.transpose(-2, -1))
    scores, indices = similarities.topk(topk, dim=-1, largest=True, sorted=True)
    gathered = item_text[indices]
    weighted = gathered.mul(scores.unsqueeze(-1))
    return weighted.sum(dim=-2)


def _alignment(x: Tensor, y: Tensor) -> Tensor:
    x_unit = F.normalize(input=x, p=2, dim=-1)
    y_unit = F.normalize(input=y, p=2, dim=-1)
    return torch.linalg.vector_norm(x_unit - y_unit, ord=2, dim=-1).pow(2).mean()


def _uniformity(x: Tensor) -> Tensor:
    unit = F.normalize(input=x, p=2, dim=-1)
    squared_distances = torch.pdist(unit, p=2).square()
    if squared_distances.nelement() == 0:
        return unit.sum() * unit.new_tensor(0.0)
    return torch.log(torch.mean(torch.exp(squared_distances * -2.0)).clamp_min(1e-12))


def directau_loss(behavior: Tensor, semantic: Tensor) -> Tensor:
    pair_alignment = _alignment(behavior, semantic)
    pair_uniformity = (_uniformity(behavior) + _uniformity(semantic)) * 0.5
    return pair_alignment + pair_uniformity


def recommendation_loss(logits: Tensor, targets: Tensor) -> Tensor:
    recommendation = F.cross_entropy(input=logits, target=targets.long().add(-1))
    return recommendation


class LLM4SBRCore(nn.Module):
    def __init__(self, text_dim: int, hidden_dim: int, n_items: int, topk: int = 5, tau: float = 0.1):
        super().__init__()
        if n_items <= 1:
            raise ValueError("n_items includes padding id 0 and must be greater than 1")
        self.topk = topk
        self.tau = tau
        self.text_projection = nn.Linear(in_features=text_dim, out_features=hidden_dim)
        self.attn_last = nn.Linear(in_features=hidden_dim, out_features=hidden_dim)
        self.attn_nodes = nn.Linear(in_features=hidden_dim, out_features=hidden_dim)
        self.attn_score = nn.Linear(in_features=hidden_dim, out_features=1, bias=False)
        self.long_gate = nn.Linear(hidden_dim, 1, bias=False)
        self.short_gate = nn.Linear(hidden_dim, 1, bias=False)
        self.fusion = nn.Linear(hidden_dim * 2, hidden_dim)
        self.item_id_embedding = nn.Embedding(n_items, hidden_dim, padding_idx=0)

    def global_preference(self, sequence_hidden: Tensor, mask: Tensor, local: Tensor) -> Tensor:
        query = self.attn_last(local).unsqueeze(1)
        keys = self.attn_nodes(sequence_hidden)
        logits = self.attn_score(torch.sigmoid(torch.add(query, keys))).squeeze(-1)
        masked_logits = logits.masked_fill(mask == 0, torch.finfo(logits.dtype).min)
        weights = torch.softmax(masked_logits, dim=1)
        return torch.sum(torch.mul(weights.unsqueeze(-1), sequence_hidden), dim=1)

    def forward(self, sequence_hidden: Tensor, mask: Tensor, long_inference: Tensor, short_inference: Tensor, item_text: Tensor, targets: Tensor) -> CoreOutput:
        lengths = torch.sum(mask.long(), dim=1)
        if torch.any(lengths <= 0):
            raise ValueError("every session must contain at least one real item")
        rows = torch.arange(start=0, end=mask.size(0), device=mask.device)
        local = sequence_hidden[rows, lengths - 1]
        global_ = self.global_preference(sequence_hidden, mask, local)
        long_text = self.text_projection(localize_intent(long_inference, item_text, self.topk))
        short_text = self.text_projection(localize_intent(short_inference, item_text, self.topk))
        auxiliary = (directau_loss(global_, long_text) + directau_loss(local, short_text)).div(2.0)
        long_alpha = self.long_gate(torch.sigmoid(torch.add(global_, long_text)))
        short_alpha = self.short_gate(torch.sigmoid(torch.add(local, short_text)))
        joined = torch.cat((local.mul(short_alpha), global_.mul(long_alpha)), dim=1)
        session = self.fusion(joined)
        logits = torch.matmul(session, self.item_id_embedding.weight[1:].T)
        recommendation = recommendation_loss(logits, targets)
        loss = recommendation + auxiliary.mul(self.tau) + auxiliary.detach().mul(0.0)
        return CoreOutput(logits=logits, loss=loss, recommendation_loss=recommendation, auxiliary_loss=auxiliary, session=session)
