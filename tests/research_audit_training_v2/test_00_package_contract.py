from __future__ import annotations

import re
import unittest
from pathlib import Path

from tests.research_audit_training_v2.helpers import ROOT, V2, sha256, student_files


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


def manifest_paths() -> set[str]:
    manifest = ROOT / "tests/research_audit_training_v2/fixtures/legacy_tree.sha256"
    return {
        line.split("  ", 1)[1]
        for line in manifest.read_text(encoding="utf-8").splitlines()
    }


def expected_protected_paths() -> set[str]:
    old_training = ROOT / "LLM4SBR_code_judgement_training"
    main = ROOT / "LLM4SBR-main"
    selected_suffixes = {".py", ".md", ".ipynb"}

    protected = {
        path.relative_to(ROOT).as_posix()
        for path in old_training.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and not path.name.startswith(".")
    }
    protected.update(
        path.relative_to(ROOT).as_posix()
        for path in main.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and "tmp" not in path.parts
        and (path.suffix in selected_suffixes or path.name.startswith("requirements"))
    )
    protected.add(Path("2402.13840v2.pdf").as_posix())
    return protected


class PackageContractTests(unittest.TestCase):
    def test_manifest_excludes_metadata_and_data_artifacts(self) -> None:
        paths = manifest_paths()
        self.assertFalse(any(Path(path).name == ".DS_Store" for path in paths))
        data_artifact_names = {"train.txt", "test.txt", "all_train_seq.txt"}
        self.assertFalse(
            any(
                path.startswith("LLM4SBR-main/Data/")
                and Path(path).name in data_artifact_names
                for path in paths
            )
        )

    def test_manifest_path_set_matches_derived_protected_files(self) -> None:
        self.assertEqual(manifest_paths(), expected_protected_paths())

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

    def test_protected_files_match_frozen_hashes(self) -> None:
        manifest = ROOT / "tests/research_audit_training_v2/fixtures/legacy_tree.sha256"
        for line in manifest.read_text(encoding="utf-8").splitlines():
            expected, relative = line.split("  ", 1)
            path = ROOT / relative
            self.assertTrue(path.is_file(), relative)
            self.assertEqual(sha256(path), expected, relative)
