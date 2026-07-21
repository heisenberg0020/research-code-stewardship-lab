# Paper-to-Code Map

This exercise uses a compact implementation of the paper's semantic path. The
candidate interface uses one-based item targets and excludes padding id zero
from the returned item logits.

| Contract | Mathematical meaning | Code surface |
|---|---|---|
| Intent localization | Cosine-normalize each query and item row, retrieve top-k items, then form the score-weighted item sum | `localize_intent` |
| Global preference | Mask invalid sequence positions before softmax, then take the attention-weighted hidden-state sum | `global_preference` |
| Semantic alignment | Average long- and short-view DirectAU terms without breaking their gradient path | `directau_loss`, `forward` |
| Training objective | Add the weighted auxiliary scalar to recommendation cross entropy | `forward` |
| Recommendation loss | Apply cross entropy directly to raw item logits after converting targets to zero-based indices | `recommendation_loss` |

The compact forward interface is:

```python
output = model(
    sequence_hidden,
    mask,
    long_inference,
    short_inference,
    item_text,
    targets,
)
```

`CoreOutput` exposes raw `logits`, total `loss`, `recommendation_loss`, the
original `auxiliary_loss`, and the fused `session` representation.
