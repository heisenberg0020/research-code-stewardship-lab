# LLM4SBR 四级研究审计训练 v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新建一套离线、可重复、可公开运行的 LLM4SBR 四级盲审训练包，使每级五份候选均通过公开检查，而隐藏证据能唯一识别一份可信候选和四种单一目标错误。

**Architecture:** 训练包与开发验收测试分离。`LLM4SBR_research_audit_training_v2/` 只包含学生材料、公开检查和逐级隔离答案；`tests/research_audit_training_v2/` 从包外验证结构、行为、泄题、可重复性和旧目录不变性。Level 1/2 使用固定小型 PyTorch/合成数据，Level 3/4 使用标准库解析的 JSON、JSONL、CSV 和 Markdown 证据包。

**Tech Stack:** Python 3.12、PyTorch 2.12 CPU、Python 标准库 `unittest`、`json`、`csv`、`hashlib`、`subprocess`、`tempfile`。

## Global Constraints

- 新建 `/Users/heisenberg/Desktop/Recommendation system/LLM4RS/LLM4SBR_research_audit_training_v2`；不得修改 `LLM4SBR-main/**`、`LLM4SBR_code_judgement_training/**` 和 `2402.13840v2.pdf`。
- 不安装新依赖，不联网，不下载模型，不运行完整 MovieLens-1M 或 Beauty 训练。
- 所有正式验证命令使用 `conda run -n ml python`；Level 1/2 允许 PyTorch 与标准库，Level 3/4 只允许标准库。
- 每级恰好 A-E 五份候选；一份完全可信，另外四份各有且只有一个主要目标错误。
- 四级可信候选字母预先冻结、彼此不重复且不形成可猜测序列；映射只写入隔离答案。
- 五份候选必须通过相同公开 import、schema、forward/backward 或 smoke test；公开输出不得透露正确字母、规则命中或隐藏探针。
- 答案、候选字母映射、目标规则 ID、修复位置和隐藏证据只存在于各级 `DO_NOT_OPEN_UNTIL_FINISHED/`。
- Level 1 的错误必须是一个参数、常数、算子或逻辑语句级语义突变；接口、shape、有限 forward 和 backward 均保持可用；候选不能通过逐差异点多数投票唯一还原答案。
- Level 2 的错误必须跨数据、训练或评估契约显现；所有候选均输出 checkpoint、逐样本评估、事件日志和有限汇总。
- Level 3 预先冻结实验单位、配对关系、排除规则和允许主张；随机 seed 不自动视为独立科学样本。
- Level 4 的审批和事件材料必须声明封闭、完整、按时间排序，或给出行动与批准冲突的正面证据。
- 随机源显式设 seed；同一命令连续两次的规范化输出和关键 artifacts 必须一致。
- 当前工作区不是 Git 仓库：不创建 worktree、不提交；任务进度记录到 `.superpowers/sdd/progress.md`，每个任务使用独立只读审查替代基于 commit 的 diff 审查。

---

## File Map

### 开发验收测试

- `tests/research_audit_training_v2/helpers.py`：路径、子进程、动态导入、学生侧文件扫描和哈希工具。
- `tests/research_audit_training_v2/fixtures/legacy_tree.sha256`：实施前冻结的旧源码/旧训练包文件哈希。
- `tests/research_audit_training_v2/test_00_package_contract.py`：目录结构、候选一致性、泄题和旧目录保护。
- `tests/research_audit_training_v2/test_05_shared_contracts.py`：合成数据、参考指标和 schema 工具。
- `tests/research_audit_training_v2/test_10_level1_algorithm.py`：Level 1 公开运行与隐藏算法探针。
- `tests/research_audit_training_v2/test_20_level2_pipeline.py`：Level 2 公开运行与隐藏流水线契约。
- `tests/research_audit_training_v2/test_30_level3_scientific.py`：Level 3 dossier schema、汇总重算和科学规则。
- `tests/research_audit_training_v2/test_40_level4_governance.py`：Level 4 run schema、审批链和治理规则。
- `tests/research_audit_training_v2/test_50_integration.py`：根命令、离线依赖、重复性与最终泄题扫描。

### 训练包根目录

- `LLM4SBR_research_audit_training_v2/README.md`：使用顺序和公开命令。
- `LLM4SBR_research_audit_training_v2/FRAMEWORK_OVERVIEW.md`：通用四级框架，不含本题答案。
- `LLM4SBR_research_audit_training_v2/PROGRESSION.md`：每级进入条件与作答证据要求。
- `LLM4SBR_research_audit_training_v2/run_all_public_checks.py`：依次运行四级公开检查。
- `LLM4SBR_research_audit_training_v2/verify_package.py`：只执行学生可见的结构与公开检查，绝不导入隔离答案。
- `tests/research_audit_training_v2/run_hidden_verification.py`：包外维护者入口，调用四级隔离验证且只输出逐级 PASS/FAIL。
- `LLM4SBR_research_audit_training_v2/shared/synthetic_sbr.py`：固定 session 与 Level 1 batch。
- `LLM4SBR_research_audit_training_v2/shared/metrics_reference.py`：逐样本 HR/MRR/NDCG 参考实现。
- `LLM4SBR_research_audit_training_v2/shared/schemas.py`：JSON/JSONL/CSV 读取与字段校验。

### 四级目录

- `level_1_algorithm_semantics/`：五份单文件 PyTorch 候选、公开 smoke、论文映射、作答纸和隐藏探针。
- `level_2_pipeline_integrity/`：五个多文件 pipeline、冻结协议、公开 smoke、作答纸和隐藏数据流探针。
- `level_3_scientific_validity/`：五份 dossier、公开 schema validator、审查标准、作答纸和隐藏科学规则。
- `level_4_agent_experiment_governance/`：五份 Agent run、公开 schema validator、冻结协议、作答纸和隐藏治理规则。

---

### Task 1: 冻结旧目录并建立包级红灯

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/research_audit_training_v2/__init__.py`
- Create: `tests/research_audit_training_v2/helpers.py`
- Create: `tests/research_audit_training_v2/fixtures/legacy_tree.sha256`
- Create: `tests/research_audit_training_v2/test_00_package_contract.py`
- Create after red: `LLM4SBR_research_audit_training_v2/` 根级最小目录与说明文件

**Interfaces:**
- Produces: `ROOT: Path`、`V2: Path`、`run_python(*args) -> CompletedProcess[str]`、`student_files() -> list[Path]`、`tree_digest(paths) -> dict[str, str]`。
- Protects: 旧训练包、原论文源码和 PDF 的实施前哈希。

- [ ] **Step 1: 记录旧目录基线并写测试工具**

`helpers.py` 使用以下完整接口：

```python
from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
V2 = ROOT / "LLM4SBR_research_audit_training_v2"
PYTHON = ("conda", "run", "-n", "ml", "python")


def run_python(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["CUDA_VISIBLE_DEVICES"] = ""
    return subprocess.run(
        (*PYTHON, *args),
        cwd=cwd or ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def student_files() -> list[Path]:
    blocked = "DO_NOT_OPEN_UNTIL_FINISHED"
    return sorted(
        path for path in V2.rglob("*")
        if path.is_file() and blocked not in path.parts and "__pycache__" not in path.parts
    )
```

冻结清单只纳入普通源码/文档文件，排除 `__pycache__`、临时输出和真实数据 artifacts；每行格式为 `<sha256>  <相对路径>`。

- [ ] **Step 2: 写包结构与旧目录保护测试**

`test_00_package_contract.py` 至少包含：

```python
from __future__ import annotations

import re
import unittest

from tests.research_audit_training_v2.helpers import ROOT, V2, sha256, student_files


LEVELS = (
    "level_1_algorithm_semantics",
    "level_2_pipeline_integrity",
    "level_3_scientific_validity",
    "level_4_agent_experiment_governance",
)


class PackageContractTests(unittest.TestCase):
    def test_v2_tree_has_exactly_four_levels(self) -> None:
        self.assertTrue(V2.is_dir(), f"missing {V2}")
        actual = sorted(path.name for path in V2.glob("level_*") if path.is_dir())
        self.assertEqual(actual, sorted(LEVELS))

    def test_each_level_has_public_and_isolated_materials(self) -> None:
        for level in LEVELS:
            root = V2 / level
            for name in ("README.md", "ANSWER_SHEET.md", "DO_NOT_OPEN_UNTIL_FINISHED"):
                self.assertTrue((root / name).exists(), f"{level}: missing {name}")

    def test_student_files_do_not_reveal_answer_labels(self) -> None:
        forbidden = re.compile(
            r"correct candidate|known fault|trusted_candidate|answer_manifest|"
            r"正确候选\s*[:：]|答案\s*[:：]\s*[A-E]",
            re.IGNORECASE,
        )
        for path in student_files():
            if path.suffix in {".py", ".md", ".json", ".jsonl", ".csv"}:
                self.assertIsNone(forbidden.search(path.read_text(encoding="utf-8")), str(path))

    def test_protected_files_match_frozen_hashes(self) -> None:
        manifest = ROOT / "tests/research_audit_training_v2/fixtures/legacy_tree.sha256"
        for line in manifest.read_text(encoding="utf-8").splitlines():
            expected, relative = line.split("  ", 1)
            path = ROOT / relative
            self.assertTrue(path.is_file(), relative)
            self.assertEqual(sha256(path), expected, relative)
```

- [ ] **Step 3: 运行红灯并确认失败原因**

Run:

```bash
conda run -n ml python -m unittest tests.research_audit_training_v2.test_00_package_contract -v
```

Expected: `test_v2_tree_has_exactly_four_levels` 因 v2 根目录不存在而 FAIL；旧目录哈希测试通过。失败不得来自 import 或语法错误。

- [ ] **Step 4: 用最小根结构转绿**

创建四级目录、每级 `README.md`、`ANSWER_SHEET.md`、空的隔离答案目录，以及根级 `README.md`、`FRAMEWORK_OVERVIEW.md`、`PROGRESSION.md`。根说明明确公开检查不证明科学正确性；`FRAMEWORK_OVERVIEW.md` 复制已批准的 `docs/FOUR_LEVEL_RESEARCH_CODE_AUDIT_OVERVIEW.md`，不新增本题候选信息。

- [ ] **Step 5: 运行测试并独立复核**

Run same command. Expected: 4 tests PASS。审查者核对：只新增 v2、测试和进度文件，冻结路径哈希无变化。

---

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

### Task 5: Level 3 科学有效性 dossier

**Files:**
- Create: `tests/research_audit_training_v2/test_30_level3_scientific.py`
- Create: `level_3_scientific_validity/REVIEW_CRITERIA.md`
- Create: `level_3_scientific_validity/validate_evidence_schema.py`
- Create for A-E: `dossiers/<letter>/{METHODS.md,experiment_config.json,runs.csv,aggregate.csv,claim.md,claim.json,provenance.json}`
- Create: `level_3_scientific_validity/DO_NOT_OPEN_UNTIL_FINISHED/scientific_rules.py`
- Create: `level_3_scientific_validity/DO_NOT_OPEN_UNTIL_FINISHED/answer_manifest.json`
- Create: `level_3_scientific_validity/DO_NOT_OPEN_UNTIL_FINISHED/ANSWER_KEY.md`

**Interfaces:**
- Public `validate_dossier(path: Path) -> list[str]` returns schema errors only.
- Hidden `audit_dossier(path: Path) -> list[Finding]`; `Finding` includes `rule_id`、`evidence_file`、`evidence_key`、`explanation`。
- `experiment_config.json` 必含 `study_id,dataset_version,metric,methods,feature_manifest,search_protocol,planned_runs,analysis_protocol`；`planned_runs` 每项必含 `run_id,method,trial_id,pair_id,split_id,seed`。
- `search_protocol` 必含每方法批准的 `trial_ids,max_trials,budget_unit,budget_value`；`analysis_protocol` 必含 `experimental_unit,paired_by,included_statuses,predeclared_exclusions,method,alpha,claim_threshold`。
- `runs.csv` 必含 `run_id,method,trial_id,pair_id,split_id,seed,status,metric,include,exclusion_code,checkpoint_id,observation_role`；每行必须引用 `planned_runs`。
- `claim.json` 必含 `claim_id,text_scope,claim_type,effect_threshold,evidence_run_ids`，并与 `claim.md` 中的 `Claim-ID` 一致。

- [ ] **Step 1: 写 schema、重算和政策红灯测试**

测试五份 dossier 均 public-valid；所有 `aggregate.csv` 数值可从按预定规则纳入的 `runs.csv` 重算；所有 provenance 文件和 run_id 可解析；隐藏规则恰好选择一份零 finding，四份各一个主 finding，规则集合为：

```python
{
    "L3_TUNING_BUDGET_FAIRNESS",
    "L3_INFORMATION_CONDITION",
    "L3_SELECTIVE_REPORTING",
    "L3_EXPERIMENTAL_UNIT",
}
```

- [ ] **Step 2: 运行红灯**

Run: `conda run -n ml python -m unittest tests.research_audit_training_v2.test_30_level3_scientific -v`

Expected: validator 或 dossier 不存在。

- [ ] **Step 3: 冻结审查协议并生成五份 plausible dossier**

`REVIEW_CRITERIA.md` 冻结数据版本、最终评价总体、相同信息条件、每方法相同搜索预算、预定 seed/split block、配对比较、允许排除状态、效应量/区间和主张强度。明确 seed 代表训练随机性而不是独立人群样本。所有决定正确性的条件同时写入上述结构化字段；隐藏规则不得依赖解析自由文本来判断预算、信息条件、运行完整性或统计单位。

每份 `planned_runs` 明确列出完整预注册矩阵，即使某个 run 后续失败或被候选省略也仍有可审计期望。`runs.csv` 使用接口中冻结的 12 列；`aggregate.csv` 包含 `method,n,mean,std,interval_low,interval_high,analysis_unit`。所有 dossier 数值有限且表面支持某种提升。

四个错误 dossier 分别首先破坏：baseline 调参预算公平、信息可用条件、预定运行完整报告、冻结实验单位/配对推断。可信 dossier 的 claim 仅限“在当前数据和冻结协议下观察到提升”，不声称普遍或因果优越。

- [ ] **Step 4: 实现标准库 validator 和隐藏审计转绿**

公开 validator 只检查文件存在、字段、类型、唯一 ID、有限数值和引用可解析，打印五行 `schema-valid`。隐藏审计独立重算预算、feature access、应纳入 run 集合和实验单位；每个 finding 引用真实文件与 key/row。

Run same test command. Expected: 全部 PASS。

- [ ] **Step 5: 独立科学审查**

审查者确认统计错误不依赖“两个边际区间重叠即不显著”的错误规则，所有排除项依据冻结协议处理，正确 dossier 的最强允许结论与数据一致。

---

### Task 6: Level 4 Agent 权限与科学实验治理

**Files:**
- Create: `tests/research_audit_training_v2/test_40_level4_governance.py`
- Create: `level_4_agent_experiment_governance/FROZEN_PROTOCOL.md`
- Create: `level_4_agent_experiment_governance/protocol.json`
- Create: `level_4_agent_experiment_governance/validate_ledger_schema.py`
- Create for A-E: `runs/<letter>/{agent_events.jsonl,approval_log.jsonl,experiment_ledger.csv,report_manifest.json,final_report.md,workspace_diff.txt}`
- Create: `level_4_agent_experiment_governance/DO_NOT_OPEN_UNTIL_FINISHED/governance_rules.py`
- Create: `level_4_agent_experiment_governance/DO_NOT_OPEN_UNTIL_FINISHED/answer_manifest.json`
- Create: `level_4_agent_experiment_governance/DO_NOT_OPEN_UNTIL_FINISHED/ANSWER_KEY.md`

**Interfaces:**
- Public `validate_run(path: Path) -> list[str]` returns schema errors only.
- Hidden `audit_run(path: Path, protocol: dict) -> list[Finding]` cites event ID and protocol clause.
- `agent_events.jsonl` 每行必含 `event_id,timestamp,actor,action_type,scope,run_id,approval_id,evidence_refs,decision_basis`；可空外键使用 JSON `null`，不得省字段。
- `approval_log.jsonl` 每行必含 `approval_id,request_event_id,decision_event_id,status,scope,limits,decided_at`，其中 status 仅为 `pending,approved,rejected`。
- `experiment_ledger.csv` 必含 `run_id,parent_run_id,status,started_at,ended_at,actual_gpu_hours,config_hash,dataset_hash,evaluation_role,reported`。
- `report_manifest.json` 必含 `included_run_ids,failed_run_ids,claim_ids,evidence_refs,success_count,failure_count`；`final_report.md` 只承载叙述，不作为主要规则的唯一机器证据。

- [ ] **Step 1: 写治理 schema 与政策红灯测试**

公开测试要求五份 run 都能解析且字段相同。隐藏测试要求一份零 finding，四份各一个主 finding，规则集合：

```python
{
    "L4_UNAPPROVED_DATA_PROTOCOL",
    "L4_RESOURCE_SCOPE",
    "L4_RECORD_INTEGRITY",
    "L4_PROTECTED_EVIDENCE_ADAPTATION",
}
```

另断言每个 finding 引用存在的 `event_id`、协议条款和必要的 approval ID；不能只以“未找到批准”为证据。

- [ ] **Step 2: 运行红灯**

Run: `conda run -n ml python -m unittest tests.research_audit_training_v2.test_40_level4_governance -v`

Expected: protocol、validator 或 run 材料不存在。

- [ ] **Step 3: 冻结治理协议并建立完整时间线**

`protocol.json` 明确：允许的学习率/batch size 范围、最大运行数/GPU 小时、最终评价一次性边界、数据/split/loss/指标禁止修改项、需审批操作、失败保留、关键歧义停止规则，以及题目时间窗内所有审批/事件/ledger 通道封闭完整。预算以 ledger 的 `actual_gpu_hours` 与已批准 run 数重算；所有 scope change 必须引用覆盖该 scope 且在行动前为 approved 的 approval ID。

五份 run 都有单调时间戳和唯一 ID，event、approval、run 与 evidence 外键均可解析。四个错误分别包含正面冲突证据：待定或拒绝审批 ID 后仍执行数据 scope change；ledger 的 run 数或 `actual_gpu_hours` 明示超过 protocol/approval 上限；事件的 `run_id` 明示失败但 ledger 或 report manifest 删除；最终评价 event 的 ID 出现在后续开发事件的 `evidence_refs` 和 `decision_basis` 中。可信 run 保留失败、在越界前请求审批并停止，最终评价只在选择完成后一次执行。

- [ ] **Step 4: 实现 public validator 与隐藏规则转绿**

公开 validator 检查 JSONL/CSV schema、时间可解析、ID 唯一和引用存在，只打印 `schema-valid`。隐藏规则按时间连接 request、decision、action、experiment 和 report；报告中的成功/失败计数及主张必须可由 ledger 重建。

Run same test command. Expected: 全部 PASS。

- [ ] **Step 5: 独立治理审查**

审查者确认正常的事后结果讨论不会被误判；只有未经披露地用受保护证据驱动后续开发/选择，或伪装成预先假设时命中。正确 run 可以指标较低，但过程必须可审计。

---

### Task 7: 根命令、文档、泄题与重复性

**Files:**
- Create: `tests/research_audit_training_v2/test_50_integration.py`
- Create: `tests/research_audit_training_v2/run_hidden_verification.py`
- Create: `LLM4SBR_research_audit_training_v2/run_all_public_checks.py`
- Create: `LLM4SBR_research_audit_training_v2/verify_package.py`
- Modify: root and level `README.md`、`ANSWER_SHEET.md`、`PROGRESSION.md`

**Interfaces:**
- `run_all_public_checks.py` returns 0 only if all four public checks pass.
- `verify_package.py` 只运行 public/structure checks；包外 `run_hidden_verification.py` 运行四个隔离 validator 并只打印 `Level N: PASS` 或 `FAIL`。

- [ ] **Step 1: 写端到端红灯测试**

```python
class IntegrationTests(unittest.TestCase):
    def test_root_public_command_is_reproducible(self) -> None:
        first = run_python("run_all_public_checks.py", cwd=V2)
        second = run_python("run_all_public_checks.py", cwd=V2)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertEqual(first.stdout, second.stdout)

    def test_hidden_package_verification_passes_without_labels(self) -> None:
        result = run_python("tests/research_audit_training_v2/run_hidden_verification.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.count("PASS"), 4)
        self.assertNotRegex(result.stdout, r"candidate|dossier|run [A-E]|fault|rule")

    def test_trusted_letters_are_distinct_and_hidden(self) -> None:
        letters = load_hidden_trusted_letters()
        self.assertEqual(len(letters), 4)
        self.assertEqual(len(set(letters)), 4)
```

`load_hidden_trusted_letters()` 只在包外测试中读取四级隔离 `answer_manifest.json`；同时复用学生侧扫描，确认任何 manifest 字母映射和答案目录 import 都未出现在可见文件。

静态 import 测试拒绝候选及 Level 3/4 材料中的非标准库 import，拒绝其中的 `requests`、`urllib.request`、`socket`、`transformers`、模型下载和外部 shell 调用。唯一允许的编排例外是根 `run_all_public_checks.py` 使用固定 argv、`shell=False` 的 `subprocess.run`；候选和 validator 不得调用 subprocess。README 命令必须从 v2 根目录实际执行。

- [ ] **Step 2: 运行红灯**

Run: `conda run -n ml python -m unittest tests.research_audit_training_v2.test_50_integration -v`

Expected: 根 runner/verify 文件不存在。

- [ ] **Step 3: 实现根编排与完成学生文档**

根 runner 用固定 argv 且显式 `shell=False` 的 `subprocess.run` 顺序执行四个公开入口，规范化设置 `PYTHONDONTWRITEBYTECODE=1` 和 `CUDA_VISIBLE_DEVICES=""`，输出固定标题与退出状态，不打印数值排名。学生侧 `verify_package.py` 只能调用结构与公开检查，不得定位、导入或执行任何 `DO_NOT_OPEN_UNTIL_FINISHED` 文件。README 给出：学习顺序、每级命令、作答位置、何时可打开答案、公开 PASS 的有限含义。每级作答纸要求唯一候选、精确定位、规范引用、为何可运行、因果链、最小证据、修复/治理动作和结论强度。

- [ ] **Step 4: 转绿并运行全套**

Run:

```bash
conda run -n ml python -m unittest discover -s tests/research_audit_training_v2 -p 'test_*.py' -v
```

Expected: 0 failures, 0 errors。

Run:

```bash
cd LLM4SBR_research_audit_training_v2
conda run -n ml python run_all_public_checks.py
conda run -n ml python verify_package.py
cd ..
conda run -n ml python tests/research_audit_training_v2/run_hidden_verification.py
```

Expected: 所有公开候选可运行，隐藏验证四级各打印一行 PASS，不输出候选字母。

- [ ] **Step 5: 最终新鲜验证与广域审查**

重新运行旧版 `conda run -n ml python LLM4SBR_code_judgement_training/run_all.py`；比较冻结哈希；扫描学生侧答案措辞、路径 import、文件大小/注释异常；连续两次运行根 public command 并比较 stdout。由未参与实现的审查者逐条核对已批准规格第 1–12 节，所有 Critical/Important 问题修复并复审后才可宣布完成。

---

## Self-Review Checklist

- [ ] 规格中的四级目录、每级五份候选、公开/隐藏分离、评分材料和根命令均有对应任务。
- [ ] 每个生产行为前都有明确失败测试与预期失败原因。
- [ ] 所有接口名称在生产文件与测试中一致。
- [ ] 无未定义步骤、临时占位或依赖网络的环节。
- [ ] Level 1 的微型错误、Level 3 的实验单位、Level 4 的日志完整性前提均被验收测试直接覆盖。
- [ ] 旧目录保护、泄题、机械猜题、重复性和 README 命令均在最终全套中验证。
