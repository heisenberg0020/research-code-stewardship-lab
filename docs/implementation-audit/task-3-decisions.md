# Task 3 Controller Decisions

This file refines the Level 1 probe construction without assigning candidate letters. The trusted-letter mapping must remain only in the level's isolated `answer_manifest.json`.

## Single-expression mutation boundaries

- Batch-composition fault: mutate only the query normalization axis; item rows remain normalized on their feature axis.
- Padding fault: mutate only the pre-softmax invalid-position fill value from a negative-infinite value to `0.0`.
- Auxiliary-gradient fault: mutate only the auxiliary tensor used inside `loss = recommendation + tau * auxiliary`; return the original non-detached `auxiliary_loss` so all logged scalar values remain identical.
- CE-input fault: mutate only the tensor passed to cross entropy; returned model logits remain raw logits.

## Probe isolation

- Batch probe calls `localize_intent` directly. It must not compare total loss because DirectAU uniformity legitimately depends on batch composition.
- Padding probe changes only `mask == 0` hidden vectors under right-contiguous padding. It also fixes attention parameters so random cancellation cannot hide the fault.
- Auxiliary probe differentiates `output.loss - output.recommendation_loss` with respect to `text_projection.weight`. It must not inspect total parameter gradient, because the recommendation branch also reaches that parameter.
- CE probe calls exported `recommendation_loss` directly with 1-based targets and compares both scalar loss and gradients against raw-logit `F.cross_entropy(logits, targets - 1)`.

## Deterministic counterexamples

Batch-composition probe uses float64:

```python
query = torch.tensor([[3.0, 1.0]], dtype=torch.float64)
companion = torch.tensor([[0.0, 4.0]], dtype=torch.float64)
items = torch.tensor([[2.0, 1.0], [-1.0, 2.0], [-2.0, -1.0]], dtype=torch.float64)
```

Compare the first output for `query` alone and `torch.cat([query, companion])` at `topk=1` with `atol=1e-9`.

Padding probe zeroes the attention projection/score parameters so every unmasked attention logit is zero. Use real hidden rows `[1,2]`, `[3,4]`, one masked row changed from `[0,0]` to `[30,-20]`, and mask `[1,1,0]`; the correct global vector remains `[2,3]`.

CE probe uses:

```python
logits = torch.tensor([[12.0, 0.0, -7.0], [-5.0, 9.0, 2.0]], requires_grad=True)
targets = torch.tensor([2, 3])  # one-based candidate interface
```

Raw and softmaxed tensors retain the same argmax, while their CE loss and gradients are not equivalent.

## Mechanical-answer resistance

- At each semantic site, all five candidates use textually distinct forms, including multiple correct equivalent forms.
- Add one harmless style site and rotate expression styles so the trusted file is neither shortest nor the unique token/AST distance center.
- Hidden manifest records one exact source span and repair expression for every faulty candidate.
- In a temporary copy, applying only that repair must change classification from exactly one failed rule to zero failed rules.
- Dynamic import inserts the module into `sys.modules` before `exec_module`, so dataclasses load reliably on Python 3.12.
