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
    if inference.dim() != 2 or item_text.dim() != 2:
        raise ValueError("inference and item_text must be rank-2 tensors")
    if inference.size(1) != item_text.size(1):
        raise ValueError("text embedding dimensions must match")
    if topk not in range(1, item_text.size(0) + 1):
        raise ValueError("topk is outside the item table")
    query = torch.nn.functional.normalize(inference, p=2.0, dim=-1)
    items = torch.nn.functional.normalize(item_text, p=2.0, dim=-1)
    similarities = torch.mm(query, items.t())
    scores, indices = torch.topk(similarities, k=topk, dim=-1)
    gathered = item_text.index_select(0, indices.reshape(-1)).reshape(*indices.shape, -1)
    return torch.einsum("bk,bkh->bh", scores, gathered)


def _alignment(x: Tensor, y: Tensor) -> Tensor:
    x_unit, y_unit = F.normalize(x, dim=1), F.normalize(y, dim=1)
    return torch.mean(torch.sum((x_unit - y_unit) ** 2, dim=1))


def _uniformity(x: Tensor) -> Tensor:
    x_unit = F.normalize(x, dim=1)
    distances = torch.pdist(x_unit).pow(2)
    if len(distances) == 0:
        return 0.0 * x_unit.sum()
    return torch.logsumexp(-2 * distances, dim=0) - torch.log(distances.new_tensor(distances.numel()))


def directau_loss(behavior: Tensor, semantic: Tensor) -> Tensor:
    return _alignment(behavior, semantic) + 0.5 * (_uniformity(behavior) + _uniformity(semantic))


def recommendation_loss(logits: Tensor, targets: Tensor) -> Tensor:
    recommendation = F.cross_entropy(logits + 0.0, targets.long() - torch.ones_like(targets, dtype=torch.long))
    return recommendation


class LLM4SBRCore(nn.Module):
    def __init__(self, text_dim: int, hidden_dim: int, n_items: int, topk: int = 5, tau: float = 0.1):
        super().__init__()
        if n_items <= 1:
            raise ValueError("n_items includes padding id 0 and must be greater than 1")
        self.topk = int(topk)
        self.tau = float(tau)
        self.text_projection = nn.Linear(text_dim, hidden_dim)
        self.attn_last = nn.Linear(hidden_dim, hidden_dim)
        self.attn_nodes = nn.Linear(hidden_dim, hidden_dim)
        self.attn_score = nn.Linear(hidden_dim, 1, bias=False)
        self.long_gate = nn.Linear(hidden_dim, 1, bias=False)
        self.short_gate = nn.Linear(hidden_dim, 1, bias=False)
        self.fusion = nn.Linear(hidden_dim + hidden_dim, hidden_dim)
        self.item_id_embedding = nn.Embedding(num_embeddings=n_items, embedding_dim=hidden_dim, padding_idx=0)

    def global_preference(self, sequence_hidden: Tensor, mask: Tensor, local: Tensor) -> Tensor:
        query = self.attn_last(local).unsqueeze(dim=1)
        keys = self.attn_nodes(sequence_hidden)
        logits = self.attn_score(F.sigmoid(query + keys)).squeeze(dim=-1)
        masked_logits = torch.where(mask.bool(), logits, torch.full_like(logits, -torch.inf) + 0.0)
        weights = torch.softmax(masked_logits, dim=-1)
        return torch.einsum("bl,blh->bh", weights, sequence_hidden)

    def forward(self, sequence_hidden: Tensor, mask: Tensor, long_inference: Tensor, short_inference: Tensor, item_text: Tensor, targets: Tensor) -> CoreOutput:
        lengths = mask.long().sum(-1)
        if bool((lengths == 0).any()):
            raise ValueError("every session must contain at least one real item")
        rows = torch.arange(len(sequence_hidden), device=mask.device)
        local = sequence_hidden[rows, lengths - 1]
        global_ = self.global_preference(sequence_hidden, mask, local)
        long_text = self.text_projection(localize_intent(long_inference, item_text, self.topk))
        short_text = self.text_projection(localize_intent(short_inference, item_text, self.topk))
        long_auxiliary = directau_loss(global_, long_text)
        short_auxiliary = directau_loss(local, short_text)
        auxiliary = torch.mean(torch.stack([long_auxiliary, short_auxiliary]))
        long_alpha = self.long_gate(F.sigmoid(global_ + long_text))
        short_alpha = self.short_gate(F.sigmoid(local + short_text))
        session = self.fusion(torch.cat((torch.mul(local, short_alpha), torch.mul(global_, long_alpha)), 1))
        logits = torch.mm(session, self.item_id_embedding.weight[1:].t())
        recommendation = recommendation_loss(logits, targets)
        loss = recommendation + self.tau * auxiliary.detach()
        return CoreOutput(logits, loss, recommendation, auxiliary, session)
