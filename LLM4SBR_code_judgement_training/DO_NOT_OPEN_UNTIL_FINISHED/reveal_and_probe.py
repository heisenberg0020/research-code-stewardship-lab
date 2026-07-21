from __future__ import annotations

import importlib.util
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parents[1]


def load(letter: str):
    path = ROOT / "candidates" / f"candidate_{letter}.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def localization_probe(module):
    query = torch.tensor([[1.0, 0.0]])
    items = torch.tensor([[0.0, 1.0], [-1.0, 0.0], [0.8, 0.6], [1.0, 0.0]])
    expected_scores = torch.tensor([1.0, 0.8])
    expected_items = items[torch.tensor([3, 2])]
    expected = (expected_scores[:, None] * expected_items).sum(dim=0, keepdim=True)
    actual = module.localize_intent(query, items, topk=2)
    return torch.allclose(actual, expected, atol=1e-6)


def uniformity_permutation_probe(module):
    x = torch.tensor([[1.0, 0.0], [0.7, 0.7], [-1.0, 0.0], [0.0, -1.0]])
    permutation = torch.tensor([0, 2, 1, 3])
    first = module.uniformity_loss(x)
    second = module.uniformity_loss(x[permutation])
    return torch.allclose(first, second, atol=1e-6)


def padding_probe(module):
    torch.manual_seed(41)
    model = module.LLM4SBRCore(text_dim=3, hidden_dim=3, n_items=7, topk=2)
    real = torch.tensor([[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]])
    padded = torch.cat([real, torch.tensor([[[99.0, -80.0, 70.0]]])], dim=1)
    local = real[:, 1]
    first = model.global_preference(real, torch.tensor([[1, 1]], dtype=torch.bool), local)
    second = model.global_preference(padded, torch.tensor([[1, 1, 0]], dtype=torch.bool), local)
    return torch.allclose(first, second, atol=1e-6)


def view_routing_probe(module):
    torch.manual_seed(73)
    model = module.LLM4SBRCore(text_dim=3, hidden_dim=3, n_items=7, topk=1)
    sequence = torch.tensor(
        [
            [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 0.0]],
            [[0.0, 0.0, 1.0], [1.0, 1.0, 0.0], [0.0, 1.0, 1.0]],
            [[1.0, -1.0, 0.0], [0.5, 0.0, 1.0], [0.0, 0.0, 0.0]],
        ]
    )
    mask = torch.tensor([[1, 1, 0], [1, 1, 1], [1, 1, 0]], dtype=torch.bool)
    long_i = torch.tensor([[2.0, 0.0, 0.0], [0.0, 3.0, 0.0], [0.0, 0.0, 4.0]])
    short_i = torch.tensor([[0.0, 5.0, 0.0], [0.0, 0.0, 6.0], [7.0, 0.0, 0.0]])
    item_text = torch.eye(3)
    targets = torch.tensor([1, 2, 3])

    original_localize = module.localize_intent
    module.localize_intent = lambda inference, _items, _topk: inference
    try:
        output = model(sequence, mask, long_i, short_i, item_text, targets)
    finally:
        module.localize_intent = original_localize

    lengths = mask.long().sum(dim=1)
    index = torch.arange(mask.shape[0])
    local = sequence[index, lengths - 1]
    global_ = model.global_preference(sequence, mask, local)
    long_text = model.text_projection(long_i)
    short_text = model.text_projection(short_i)
    long_alpha = model.long_gate(torch.sigmoid(global_ + long_text))
    short_alpha = model.short_gate(torch.sigmoid(local + short_text))
    expected = model.fusion(torch.cat([local * short_alpha, global_ * long_alpha], dim=1))
    return torch.allclose(output.session, expected, atol=1e-6)


def main():
    print("Correct candidate: C")
    print("Known faults: A=padding attention, B=localization weights, D=view routing, E=uniformity pairs")
    print("\nFour black-box invariants:")
    for letter in "ABCDE":
        module = load(letter)
        print(
            f"{letter}: padding={padding_probe(module)}  "
            f"localization={localization_probe(module)}  "
            f"permutation={uniformity_permutation_probe(module)}  "
            f"view_routing={view_routing_probe(module)}"
        )


if __name__ == "__main__":
    main()
