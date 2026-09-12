from __future__ import annotations

import re
import unittest
from tests.research_audit_training_v2.helpers import V2, student_files


LEVELS = (
    "level_1_algorithm_semantics",
    "level_2_pipeline_integrity",
    "level_3_scientific_validity",
    "level_4_agent_experiment_governance",
)

LEAK_PATTERN = re.compile(
    r"correct candidate|known fault|trusted_candidate|answer_manifest|"
    r"正确候选\s*[:：]|答案\s*[:：]\s*[A-E]",
    re.IGNORECASE,
)


class PackageContractTests(unittest.TestCase):
    def test_leak_pattern_matches_chinese_answer_labels(self) -> None:
        for text in ("正确候选：A", "答案：A"):
            self.assertIsNotNone(LEAK_PATTERN.search(text), text)

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
        for path in student_files():
            if path.suffix in {".py", ".md", ".json", ".jsonl", ".csv"}:
                self.assertIsNone(LEAK_PATTERN.search(path.read_text(encoding="utf-8")), str(path))
