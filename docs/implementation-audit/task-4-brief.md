### Task 4: Level 2 流水线完整性盲题

**Files:**
- Create: `tests/research_audit_training_v2/test_20_level2_pipeline.py`
- Create: `level_2_pipeline_integrity/FROZEN_PIPELINE_SPEC.md`
- Create: `level_2_pipeline_integrity/run_smoke.py`
- Create for each A-E: `candidates/<letter>/{__init__.py,data.py,trainer.py,metrics.py,pipeline.py}`
- Create: `level_2_pipeline_integrity/DO_NOT_OPEN_UNTIL_FINISHED/pipeline_probes.py`
- Create: `level_2_pipeline_integrity/DO_NOT_OPEN_UNTIL_FINISHED/answer_manifest.json`
- Create: `level_2_pipeline_integrity/DO_NOT_OPEN_UNTIL_FINISHED/ANSWER_KEY.md`

**Interfaces:**
- Each `pipeline.py` exports `run_pipeline(output_dir: Path) -> dict[str, object]`.
- Each run writes `split_manifest.json`、`batch_manifest.json`、`epoch_metrics.json`、`evaluation_records.json`、`selected_checkpoint.json`、`event_log.jsonl`、`summary.json`。
- Hidden `classify_all(temp_root) -> dict[str, tuple[str, ...]]` returns only rule IDs.

- [ ] **Step 1: 写公开与隐藏流水线测试**

公开测试在五个独立 `TemporaryDirectory` 中运行候选，断言每个 artifact 存在、指标有限、checkpoint 存在、输出 schema 相同。隐藏测试断言分类长度 `[0,1,1,1,1]`，规则集合恰为：

```python
{
    "L2_SPLIT_ENTITY_ISOLATION",
    "L2_JOINT_PERMUTATION",
    "L2_METRIC_POPULATION",
    "L2_PROTECTED_SELECTION",
}
```

性质测试从 artifact 独立重算 session split 交集、batch 联合指纹、逐样本 HR/MRR/NDCG 和 checkpoint 选择事件。

- [ ] **Step 2: 运行红灯**

Run: `conda run -n ml python -m unittest tests.research_audit_training_v2.test_20_level2_pipeline -v`

Expected: 候选 `pipeline.py` 不存在。

- [ ] **Step 3: 实现确定性微型流水线**

正确语义先按 raw session 的时间边界形成 train/validation/test，再在 split 内生成 prefix；固定 permutation 必须联动 sample_id、prefix、target、long/short embedding；每个评价样本写一条记录，miss 写 0；checkpoint 只由 validation 证据选择，受保护最终评价仅在选择完成后运行一次。

五份候选各自完整实现同一多文件接口。四个错误分别只首先破坏：原始 session 隔离、联合 permutation、评价总体/分母、受保护评价边界。错误候选仍训练三个 epoch、保存三个 checkpoint、写全部 artifacts，并返回 0 到 1 之间的合理指标。

- [ ] **Step 4: 实现隐藏血缘探针并转绿**

`pipeline_probes.py` 只从冻结协议与 artifacts 推断，不依赖候选名称：

- 构造 `session_id -> set(split)` 并要求每个集合大小为 1；
- 比较 shuffle 前后 `(sample_id,target,long_hash,short_hash)` multiset；
- 要求每个 evaluation sample 恰有一行，并用参考指标重算 summary；
- 要求所有 `checkpoint_selected` 事件证据源为 validation，最终评价在选择之后且仅一次。

Run same test command. Expected: 全部 PASS。

- [ ] **Step 5: 独立审查跨文件证据**

审查者确认每个错误至少跨两个 artifact 或文件才能证明，公开 stdout 不显示指标大小排名，正确候选不因文件数量、注释或行数异常而突出。

---

