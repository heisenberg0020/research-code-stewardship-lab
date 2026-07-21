from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))

from shared.synthetic_sbr import algorithm_batch


REQUIRED_EXPORTS = (
    "CoreOutput",
    "localize_intent",
    "directau_loss",
    "recommendation_loss",
    "LLM4SBRCore",
)


def load_candidate(letter: str):
    path = ROOT / "candidates" / f"{letter}.py"
    module_name = f"level1_smoke_{letter}"
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


def smoke(letter: str) -> None:
    module = load_candidate(letter)
    missing = [name for name in REQUIRED_EXPORTS if not hasattr(module, name)]
    if missing:
        raise AssertionError(f"missing exports: {missing}")

    batch = algorithm_batch()
    torch.manual_seed(20_260_711)
    model = module.LLM4SBRCore(
        text_dim=batch.text_dim,
        hidden_dim=batch.hidden_dim,
        n_items=batch.n_items,
        topk=5,
        tau=0.1,
    )
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    optimizer.zero_grad(set_to_none=True)
    output = model(
        batch.sequence,
        batch.mask,
        batch.long_inference,
        batch.short_inference,
        batch.item_text,
        batch.targets,
    )
    if output.logits.shape != (batch.targets.shape[0], batch.n_items - 1):
        raise AssertionError("unexpected logits shape")
    for scalar in (output.loss, output.recommendation_loss, output.auxiliary_loss):
        if scalar.ndim != 0 or not math.isfinite(scalar.item()):
            raise AssertionError("loss must be a finite scalar")
    output.loss.backward()
    gradients = [parameter.grad for parameter in model.parameters() if parameter.grad is not None]
    if not gradients or not all(torch.isfinite(gradient).all() for gradient in gradients):
        raise AssertionError("backward must produce finite gradients")
    optimizer.step()
    if not all(torch.isfinite(parameter).all() for parameter in model.parameters()):
        raise AssertionError("Adam step produced a non-finite parameter")


def main() -> None:
    for letter in "ABCDE":
        smoke(letter)
        print(f"{letter}: PASS")


if __name__ == "__main__":
    main()
