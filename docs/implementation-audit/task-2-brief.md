### Task 2: 共用确定性数据、指标和 schema

**Files:**
- Create: `tests/research_audit_training_v2/test_05_shared_contracts.py`
- Create: `LLM4SBR_research_audit_training_v2/shared/__init__.py`
- Create: `LLM4SBR_research_audit_training_v2/shared/synthetic_sbr.py`
- Create: `LLM4SBR_research_audit_training_v2/shared/metrics_reference.py`
- Create: `LLM4SBR_research_audit_training_v2/shared/schemas.py`

**Interfaces:**
- Produces: `algorithm_batch() -> AlgorithmBatch`、`raw_sessions() -> tuple[RawSession, ...]`、`prefix_examples(sessions) -> list[PrefixExample]`。
- Produces: `per_example_metrics(ranked_items, targets, k) -> list[MetricRow]`、`aggregate_metrics(rows) -> dict[str, float]`。
- Produces: `load_json`、`load_jsonl`、`load_csv`、`require_keys`。

- [ ] **Step 1: 写共享契约测试**

测试固定断言：两次 `algorithm_batch()` 张量逐项相同；每个 raw session 的 `session_id` 唯一且 item 0 不出现；prefix target 等于原序列下一项；未命中样本 HR/MRR/NDCG 都返回 0；JSONL 行号和 CSV 必需字段错误会抛出包含文件名的 `ValueError`。

```python
class SharedContractTests(unittest.TestCase):
    def test_prefix_examples_preserve_parent_identity(self) -> None:
        sessions = raw_sessions()
        examples = prefix_examples(sessions)
        by_id = {session.session_id: session for session in sessions}
        for example in examples:
            original = by_id[example.session_id].items
            self.assertEqual(tuple(example.prefix), original[: example.prefix_length])
            self.assertEqual(example.target, original[example.prefix_length])

    def test_metrics_include_zero_for_every_miss(self) -> None:
        rows = per_example_metrics([[3, 2], [5, 4]], [2, 9], k=2)
        self.assertEqual(len(rows), 2)
        self.assertEqual((rows[1].hr, rows[1].mrr, rows[1].ndcg), (0.0, 0.0, 0.0))
```

- [ ] **Step 2: 运行红灯**

Run: `conda run -n ml python -m unittest tests.research_audit_training_v2.test_05_shared_contracts -v`

Expected: import 失败，因为 `shared` 尚不存在。

- [ ] **Step 3: 实现最小共享模块**

`synthetic_sbr.py` 使用 frozen dataclass：

```python
@dataclass(frozen=True)
class RawSession:
    session_id: str
    timestamp: int
    items: tuple[int, ...]
    long_embedding: tuple[float, ...]
    short_embedding: tuple[float, ...]


@dataclass(frozen=True)
class PrefixExample:
    sample_id: str
    session_id: str
    prefix_length: int
    prefix: tuple[int, ...]
    target: int
    long_embedding: tuple[float, ...]
    short_embedding: tuple[float, ...]
```

数据至少含 15 个 session、三种长度、重复 item、明确时间顺序和 8 个非 padding item。`algorithm_batch()` 固定 seed `8675309`，返回与 Level 1 接口匹配的六样本张量。

`metrics_reference.py` 对每个样本始终生成一行；rank 从 1 开始，MRR 为 `1/rank`，NDCG 为 `1/log2(rank+1)`，未命中三项均为 0；聚合分母固定为输入样本数。

- [ ] **Step 4: 运行共享测试转绿**

Run same command. Expected: 全部 PASS，无 warning。

---

