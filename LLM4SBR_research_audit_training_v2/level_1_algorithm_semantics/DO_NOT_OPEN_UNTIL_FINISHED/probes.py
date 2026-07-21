from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import torch
import torch.nn.functional as F


ROOT = Path(__file__).resolve().parents[1]
RULES = (
    "L1_BATCH_INVARIANCE",
    "L1_PADDING",
    "L1_AUX_GRAD",
    "L1_LOGIT_CE",
)


def load_candidate(path: Path) -> ModuleType:
    module_name = f"level1_probe_{path.stem}_{abs(hash(path.resolve()))}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(module_name, None)
        raise
    return module


def _batch_invariance(module: ModuleType) -> bool:
    query = torch.tensor([[3.0, 1.0]], dtype=torch.float64)
    companion = torch.tensor([[0.0, 4.0]], dtype=torch.float64)
    items = torch.tensor(
        [[2.0, 1.0], [-1.0, 2.0], [-2.0, -1.0]],
        dtype=torch.float64,
    )
    alone = module.localize_intent(query, items, topk=1)[0]
    together = module.localize_intent(torch.cat([query, companion]), items, topk=1)[0]
    return torch.allclose(alone, together, atol=1e-9, rtol=0.0)


def _padding_invariance(module: ModuleType) -> bool:
    torch.manual_seed(31_415)
    model = module.LLM4SBRCore(text_dim=2, hidden_dim=2, n_items=4, topk=1, tau=0.2)
    with torch.no_grad():
        for layer in (model.attn_last, model.attn_nodes, model.attn_score):
            layer.weight.zero_()
            if layer.bias is not None:
                layer.bias.zero_()

    base = torch.tensor([[[1.0, 2.0], [3.0, 4.0], [0.0, 0.0]]])
    changed = base.clone()
    changed[0, 2] = torch.tensor([30.0, -20.0])
    mask = torch.tensor([[1, 1, 0]], dtype=torch.bool)
    local = base[:, 1]
    base_global = model.global_preference(base, mask, local)
    changed_global = model.global_preference(changed, mask, local)

    long_inference = torch.tensor([[0.5, 1.0]])
    short_inference = torch.tensor([[1.0, -0.5]])
    item_text = torch.tensor([[1.0, 0.0], [0.0, 1.0], [-1.0, 0.5]])
    targets = torch.tensor([1])
    base_session = model(base, mask, long_inference, short_inference, item_text, targets).session
    changed_session = model(changed, mask, long_inference, short_inference, item_text, targets).session
    expected = torch.tensor([[2.0, 3.0]])
    return (
        torch.allclose(base_global, expected, atol=1e-7, rtol=0.0)
        and torch.allclose(base_global, changed_global, atol=1e-7, rtol=0.0)
        and torch.allclose(base_session, changed_session, atol=1e-7, rtol=0.0)
    )


def _auxiliary_gradient(module: ModuleType) -> bool:
    torch.manual_seed(27_182)
    model = module.LLM4SBRCore(text_dim=2, hidden_dim=2, n_items=5, topk=2, tau=0.4).double()
    sequence = torch.tensor(
        [
            [[0.2, 0.7], [1.1, -0.3]],
            [[-0.8, 0.4], [0.6, 1.2]],
            [[0.9, -0.5], [-0.2, 0.8]],
        ],
        dtype=torch.float64,
    )
    mask = torch.ones(3, 2, dtype=torch.bool)
    long_inference = torch.tensor([[0.4, 1.0], [1.2, -0.2], [-0.7, 0.3]], dtype=torch.float64)
    short_inference = torch.tensor([[1.0, -0.6], [0.5, 0.8], [-0.2, 1.1]], dtype=torch.float64)
    item_text = torch.tensor([[0.8, 0.1], [-0.3, 1.0], [1.2, -0.4], [-0.9, -0.2]], dtype=torch.float64)
    targets = torch.tensor([1, 2, 4])
    output = model(sequence, mask, long_inference, short_inference, item_text, targets)
    residual = output.loss - output.recommendation_loss
    gradient = torch.autograd.grad(
        residual,
        model.text_projection.weight,
        allow_unused=True,
    )[0]
    return gradient is not None and torch.isfinite(gradient).all() and gradient.norm().item() > 1e-8


def _logit_cross_entropy(module: ModuleType) -> bool:
    logits = torch.tensor(
        [[12.0, 0.0, -7.0], [-5.0, 9.0, 2.0]],
        dtype=torch.float64,
        requires_grad=True,
    )
    targets = torch.tensor([2, 3])
    observed = module.recommendation_loss(logits, targets)
    observed_gradient = torch.autograd.grad(observed, logits)[0]

    reference_logits = logits.detach().clone().requires_grad_(True)
    reference = F.cross_entropy(reference_logits, targets - 1)
    reference_gradient = torch.autograd.grad(reference, reference_logits)[0]
    return torch.allclose(observed, reference, atol=1e-12, rtol=1e-12) and torch.allclose(
        observed_gradient,
        reference_gradient,
        atol=1e-12,
        rtol=1e-12,
    )


PROBES = (
    (RULES[0], _batch_invariance),
    (RULES[1], _padding_invariance),
    (RULES[2], _auxiliary_gradient),
    (RULES[3], _logit_cross_entropy),
)


def classify_module(module: ModuleType) -> tuple[str, ...]:
    failures = []
    for rule, probe in PROBES:
        passed = bool(probe(module))
        if not passed:
            failures.append(rule)
    return tuple(failures)


def classify_all() -> dict[str, tuple[str, ...]]:
    return {
        letter: classify_module(load_candidate(ROOT / "candidates" / f"{letter}.py"))
        for letter in "ABCDE"
    }
