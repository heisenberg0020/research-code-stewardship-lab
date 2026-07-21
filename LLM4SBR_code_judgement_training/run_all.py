from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parent
CANDIDATES = ROOT / "candidates"


def load_candidate(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def synthetic_batch():
    generator = torch.Generator().manual_seed(8675309)
    batch, length, hidden, text_dim, n_text_items, n_items = 6, 7, 8, 10, 13, 17
    sequence = torch.randn(batch, length, hidden, generator=generator)
    mask = torch.tensor(
        [
            [1, 1, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 0, 0, 0],
            [1, 1, 0, 0, 0, 0, 0],
            [1, 1, 1, 1, 1, 0, 0],
            [1, 1, 1, 0, 0, 0, 0],
            [1, 1, 1, 1, 1, 1, 0],
        ],
        dtype=torch.bool,
    )
    long_inference = torch.randn(batch, text_dim, generator=generator)
    short_inference = torch.randn(batch, text_dim, generator=generator)
    item_text = torch.randn(n_text_items, text_dim, generator=generator)
    targets = torch.tensor([1, 4, 7, 9, 12, 16])
    return sequence, mask, long_inference, short_inference, item_text, targets, hidden, text_dim, n_items


def run_one(path: Path, batch):
    module = load_candidate(path)
    sequence, mask, long_i, short_i, item_text, targets, hidden, text_dim, n_items = batch
    torch.manual_seed(20260711)
    model = module.LLM4SBRCore(text_dim, hidden, n_items, topk=5, tau=0.1)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    optimizer.zero_grad(set_to_none=True)
    output = model(sequence, mask, long_i, short_i, item_text, targets)
    if output.logits.shape != (sequence.shape[0], n_items - 1):
        raise AssertionError(f"bad logits shape: {tuple(output.logits.shape)}")
    if not all(math.isfinite(float(value.detach())) for value in (output.loss, output.recommendation_loss, output.auxiliary_loss)):
        raise AssertionError("non-finite loss")
    output.loss.backward()
    gradients = [parameter.grad for parameter in model.parameters() if parameter.requires_grad]
    if not gradients or any(gradient is None for gradient in gradients):
        raise AssertionError("missing gradient")
    if any(not torch.isfinite(gradient).all() for gradient in gradients):
        raise AssertionError("non-finite gradient")
    optimizer.step()
    signature = float(output.logits.detach().square().mean())
    return float(output.loss.detach()), signature


def main():
    batch = synthetic_batch()
    paths = sorted(CANDIDATES.glob("candidate_*.py"))
    if len(paths) != 5:
        raise RuntimeError(f"expected 5 candidates, found {len(paths)}")
    print(f"PyTorch {torch.__version__}; candidates={len(paths)}")
    for path in paths:
        try:
            loss, signature = run_one(path, batch)
            print(f"{path.stem}: PASS  loss={loss:.6f}  output_signature={signature:.6f}")
        except Exception as exc:
            print(f"{path.stem}: FAIL  {type(exc).__name__}: {exc}")
            raise
    print("All candidates import, run, backpropagate, and update successfully.")


if __name__ == "__main__":
    main()
