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

