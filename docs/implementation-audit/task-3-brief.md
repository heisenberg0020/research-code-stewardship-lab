### Task 3: Level 1 算法语义盲题

**Files:**
- Create: `tests/research_audit_training_v2/test_10_level1_algorithm.py`
- Create: `LLM4SBR_research_audit_training_v2/level_1_algorithm_semantics/PAPER_MAP.md`
- Create: `LLM4SBR_research_audit_training_v2/level_1_algorithm_semantics/run_smoke.py`
- Create: `LLM4SBR_research_audit_training_v2/level_1_algorithm_semantics/candidates/A.py` through `E.py`
- Create: `LLM4SBR_research_audit_training_v2/level_1_algorithm_semantics/DO_NOT_OPEN_UNTIL_FINISHED/probes.py`
- Create: `LLM4SBR_research_audit_training_v2/level_1_algorithm_semantics/DO_NOT_OPEN_UNTIL_FINISHED/answer_manifest.json`
- Create: `LLM4SBR_research_audit_training_v2/level_1_algorithm_semantics/DO_NOT_OPEN_UNTIL_FINISHED/ANSWER_KEY.md`

**Interfaces:**
- Each candidate exports `CoreOutput`, `localize_intent`, `directau_loss`, `recommendation_loss`, `LLM4SBRCore`.
- `LLM4SBRCore.forward(...) -> CoreOutput` matches the old compact core interface.
- Hidden `classify_all() -> dict[str, tuple[str, ...]]` returns failed rule IDs without printing them.

- [ ] **Step 1: 写公开与隐藏行为测试**

```python
class Level1Tests(unittest.TestCase):
    def test_public_smoke_accepts_all_candidates(self) -> None:
        result = run_python("level_1_algorithm_semantics/run_smoke.py", cwd=V2)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.count("PASS"), 5)
        self.assertNotRegex(result.stdout, r"correct|fault|probe|trusted")

    def test_hidden_probes_find_one_trusted_and_four_single_failures(self) -> None:
        probes = load_module(V2 / "level_1_algorithm_semantics/DO_NOT_OPEN_UNTIL_FINISHED/probes.py")
        report = probes.classify_all()
        self.assertEqual(sum(not failures for failures in report.values()), 1)
        self.assertEqual(sorted(len(failures) for failures in report.values()), [0, 1, 1, 1, 1])
        self.assertEqual(
            {rule for failures in report.values() for rule in failures},
            {"L1_BATCH_INVARIANCE", "L1_PADDING", "L1_AUX_GRAD", "L1_LOGIT_CE"},
        )
```

另写两个直接性质测试：辅助目标的记录数值可保持相同但参数梯度改变；大间隔 logits 的 argmax 在双归一化前后可相同，但 CE loss/gradient 不等价。

- [ ] **Step 2: 运行红灯**

Run: `conda run -n ml python -m unittest tests.research_audit_training_v2.test_10_level1_algorithm -v`

Expected: `run_smoke.py` 或候选模块不存在。

- [ ] **Step 3: 实现五份外观均衡候选**

所有候选使用相同 dataclass 与模型接口，候选字母分配仅写入隐藏答案。四个目标突变分别为：行归一化语义变为跨样本归一化、无效位置获得 softmax 概率质量、辅助目标梯度被切断、概率被传给期待 logits 的 CE。每个错误只占一个常数、参数或逻辑表达式。

在四个语义位点为所有候选使用不同但等价的无害写法，例如 `-1` 与 `tensor.ndim - 1`、`-inf` 与 dtype 最小值、`auxiliary` 与 `auxiliary.clone()`、`logits` 与 `logits.contiguous()`；因此五份文件在多个位置有非语义差异，不能逐点多数投票。

`run_smoke.py` 固定模型 seed `20260711`，逐份执行 import、forward、有限 loss、backward、有限梯度和 Adam 一步，只打印 `A: PASS` 至 `E: PASS`。

- [ ] **Step 4: 实现隐藏探针并转绿**

四个探针分别验证：同一 query 不受其他 batch query 影响；改变 mask=0 hidden 不改变 global/session；辅助损失对语义投影参数存在梯度；`recommendation_loss` 等价于 logits CE。`classify_all()` 对每份候选运行全部探针并返回 tuple；答案说明包含公式、突变行、为何可运行、因果链和最小反例。

Run same test command. Expected: 全部 PASS。

- [ ] **Step 5: 检查单突变与反多数泄漏**

隐藏答案为每份错误记录一条 `mutation_span` 和语义修复；临时替换该语句后只允许目标探针由失败转为通过。AST/token 审计确认正确候选不是“与其余四份文本距离最小”的唯一候选。审查者独立确认四种错误都不是编译或 shape 错误。

---

