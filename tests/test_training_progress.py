"""Phase 2 tests for local, human-reviewed training progress."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from stewardship_lab.training import (
    TrainingError,
    check_worksheet,
    export_progress,
    get_redacted_status,
    get_status,
    initialize_workspace,
    load_progress,
    record_review,
    submit_attempt,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "rcsl.py"
TARGETS = ("L1", "L2", "L3", "L4", "capstone")
RATINGS = {
    "Recognize": "demonstrated",
    "Prove": "demonstrated",
    "Direct": "not-observed",
    "Steward": "not-observed",
}


def run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def complete_template(path: Path, marker: str = "Documented learner evidence") -> None:
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"\{\{.*?\}\}", marker, text, flags=re.DOTALL)
    path.write_text(text, encoding="utf-8")


def assert_no_answer_fields(test: unittest.TestCase, value: object) -> None:
    forbidden = {
        "trusted_candidate",
        "correct_candidate",
        "expected_answer",
        "hidden_rule_id",
        "repair_span",
        "private_probe",
    }
    if isinstance(value, dict):
        test.assertTrue(forbidden.isdisjoint(value))
        for nested in value.values():
            assert_no_answer_fields(test, nested)
    elif isinstance(value, list):
        for nested in value:
            assert_no_answer_fields(test, nested)


class TrainingProgressTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.workspace = self.root / "learner-progress"
        initialize_workspace(self.workspace, learner_label="Local Learner")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def worksheet(self, target: str) -> Path:
        return self.workspace / "worksheets" / f"{target}.md"

    def complete(self, target: str, marker: str = "Documented learner evidence") -> None:
        complete_template(self.worksheet(target), marker)

    def submit(self, target: str, operation_id: str | None = None) -> dict[str, object]:
        self.complete(target)
        return submit_attempt(
            self.workspace,
            target,
            note=f"Submit {target}",
            operation_id=operation_id,
        )

    def review(
        self,
        target: str,
        *,
        reviewer: str,
        decision: str,
        ratings: dict[str, str] | None = None,
        operation_id: str | None = None,
    ) -> dict[str, object]:
        return record_review(
            self.workspace,
            target,
            reviewer=reviewer,
            decision=decision,
            ratings=ratings or RATINGS,
            rationale="Evidence-bound human judgment for this frozen attempt.",
            strengths="The first contract and a reproducible check are explicit.",
            gaps="Residual uncertainty is recorded rather than averaged away.",
            operation_id=operation_id,
        )

    def test_init_is_external_minimal_and_offline_resumable(self) -> None:
        self.assertEqual(
            {path.name for path in self.workspace.iterdir()},
            {"README.md", "RUBRIC.md", "CAPSTONE_BRIEF.md", "progress.json", "worksheets"},
        )
        self.assertEqual({path.name for path in (self.workspace / "worksheets").iterdir()}, {
            "L1.md", "L2.md", "L3.md", "L4.md", "capstone.md"
        })
        progress = load_progress(self.workspace)
        self.assertEqual(progress["workspace_type"], "rcsl-training-progress")
        self.assertEqual(progress["exposure_state"], "open-demo-honor-isolation")
        self.assertEqual(set(progress["targets"]), set(TARGETS))
        self.assertEqual(oct((self.workspace / "progress.json").stat().st_mode & 0o777), "0o600")
        assert_no_answer_fields(self, progress)

        resumed = get_status(self.workspace)
        self.assertEqual(resumed["overall_state"], "in-progress")
        self.assertEqual(resumed["targets"]["L1"]["attempt_state"], "not-submitted")
        self.assertEqual(resumed["targets"]["L1"]["human_review_state"], "not-reviewed")

    def test_init_refuses_existing_repo_isolated_and_symlink_targets_without_writes(self) -> None:
        existing = self.root / "existing"
        existing.mkdir()
        sentinel = existing / "keep.txt"
        sentinel.write_text("keep", encoding="utf-8")
        with self.assertRaisesRegex(TrainingError, "exists"):
            initialize_workspace(existing, learner_label="Learner")
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")

        in_repo = ROOT / "phase2-should-never-exist"
        with self.assertRaisesRegex(TrainingError, "outside"):
            initialize_workspace(in_repo, learner_label="Learner")
        self.assertFalse(in_repo.exists())

        isolated = self.root / "do_not_open_until_finished" / "workspace"
        with self.assertRaisesRegex(TrainingError, "isolated"):
            initialize_workspace(isolated, learner_label="Learner")
        self.assertFalse(isolated.exists())

        alias = self.root / "repo-alias"
        alias.symlink_to(ROOT, target_is_directory=True)
        via_alias = alias / "phase2-should-never-exist"
        with self.assertRaisesRegex(TrainingError, "outside"):
            initialize_workspace(via_alias, learner_label="Learner")
        self.assertFalse((ROOT / "phase2-should-never-exist").exists())

    def test_structure_check_never_makes_a_semantic_or_maturity_judgment(self) -> None:
        incomplete = check_worksheet(self.workspace, "L1")
        self.assertEqual(incomplete["structure_status"], "incomplete")
        self.assertGreater(incomplete["placeholder_count"], 0)

        self.complete("L1")
        complete = check_worksheet(self.workspace, "L1")
        self.assertEqual(complete["structure_status"], "complete")
        self.assertEqual(complete["semantic_assessment"], "not_performed")
        self.assertEqual(complete["scientific_correctness"], "not_assessed")
        self.assertEqual(complete["maturity_assessment"], "not_performed")
        self.assertNotIn("score", complete)
        assert_no_answer_fields(self, complete)

    def test_fenced_or_commented_headings_cannot_satisfy_structure(self) -> None:
        headings = [
            "1. Decision identity and uncertainty",
            "2. First broken contract",
            "3. Evidence chain",
            "4. Why the artifact remains plausible",
            "5. Causal effect and claim boundary",
            "6. Delegation and human checkpoints",
            "7. Safe response and regression evidence",
            "8. Stakeholder communication",
        ]
        fake_sections = "\n\n".join(
            f"## {heading}\n\nSynthetic text" for heading in headings
        )
        self.worksheet("L1").write_text(
            f"# Fake response\n\n```markdown\n{fake_sections}\n```\n", encoding="utf-8"
        )
        fenced = check_worksheet(self.workspace, "L1")
        self.assertEqual(fenced["structure_status"], "incomplete")
        self.assertEqual(fenced["present_sections"], [])

        self.worksheet("L1").write_text(
            f"# Fake response\n\n<!--\n{fake_sections}\n-->\n", encoding="utf-8"
        )
        commented = check_worksheet(self.workspace, "L1")
        self.assertEqual(commented["structure_status"], "incomplete")
        self.assertEqual(commented["present_sections"], [])

        self.worksheet("L1").write_text(
            f"# Fake response\n\n<!--\n{fake_sections}\n", encoding="utf-8"
        )
        unclosed_comment = check_worksheet(self.workspace, "L1")
        self.assertEqual(unclosed_comment["structure_status"], "incomplete")
        self.assertEqual(unclosed_comment["present_sections"], [])

        self.worksheet("L1").write_text(
            f"# Fake response\n\n<pre>\n{fake_sections}\n</pre>\n", encoding="utf-8"
        )
        raw_html = check_worksheet(self.workspace, "L1")
        self.assertEqual(raw_html["structure_status"], "incomplete")
        self.assertEqual(raw_html["present_sections"], [])

        visible_headings_comment_bodies = "\n\n".join(
            f"## {heading}\n\n<!-- synthetic text -->" for heading in headings
        )
        self.worksheet("L1").write_text(
            f"# Empty response\n\n{visible_headings_comment_bodies}\n", encoding="utf-8"
        )
        empty = check_worksheet(self.workspace, "L1")
        self.assertEqual(empty["structure_status"], "incomplete")
        self.assertEqual(empty["empty_sections"], headings)

    def test_submit_freezes_bytes_retry_and_idempotent_operation(self) -> None:
        first = self.submit("L1", operation_id="submit-l1-first")
        replay = submit_attempt(
            self.workspace,
            "L1",
            note="Submit L1",
            operation_id="submit-l1-first",
        )
        self.assertEqual(replay["id"], first["id"])

        old_snapshot = first["worksheet_snapshot"]
        self.worksheet("L1").write_text(
            self.worksheet("L1").read_text(encoding="utf-8") + "\nRetry evidence.\n",
            encoding="utf-8",
        )
        second = submit_attempt(
            self.workspace,
            "L1",
            note="Retry L1",
            operation_id="submit-l1-retry",
        )
        self.assertEqual(second["retry_of"], first["id"])
        self.assertNotEqual(second["worksheet_sha256"], first["worksheet_sha256"])

        stored = load_progress(self.workspace)["targets"]["L1"]["attempts"]
        self.assertEqual([attempt["id"] for attempt in stored], [first["id"], second["id"]])
        self.assertEqual(stored[0]["worksheet_snapshot"], old_snapshot)

        with self.assertRaisesRegex(TrainingError, "operation ID"):
            submit_attempt(
                self.workspace,
                "L1",
                note="Different payload",
                operation_id="submit-l1-first",
            )

    def test_review_is_human_only_preserves_disagreement_and_retry_resets_active_state(self) -> None:
        with self.assertRaisesRegex(TrainingError, "submitted attempt"):
            self.review("L1", reviewer="Reviewer A", decision="pass")

        first = self.submit("L1")
        passed = self.review("L1", reviewer="Reviewer A", decision="pass")
        revised = self.review("L1", reviewer="Reviewer B", decision="revise")
        self.assertEqual(passed["attempt_id"], first["id"])
        self.assertEqual(revised["attempt_id"], first["id"])

        status = get_status(self.workspace)
        self.assertEqual(status["targets"]["L1"]["human_review_state"], "review-disagreement")
        self.assertEqual(len(status["targets"]["L1"]["active_reviews"]), 2)
        self.assertEqual(status["targets"]["L1"]["maturity_assessment"], "human-only")

        reviewer_b_update = dict(RATINGS)
        reviewer_b_update["Direct"] = "partial"
        self.review(
            "L1",
            reviewer="Reviewer B",
            decision="revise",
            ratings=reviewer_b_update,
        )
        status = get_status(self.workspace)
        self.assertEqual(
            status["targets"]["L1"]["rating_disagreements"]["Direct"],
            ["not-observed", "partial"],
        )

        self.worksheet("L1").write_text(
            self.worksheet("L1").read_text(encoding="utf-8") + "\nAddressed review gap.\n",
            encoding="utf-8",
        )
        retry = submit_attempt(self.workspace, "L1", note="Address feedback")
        self.assertEqual(retry["retry_of"], first["id"])
        retry_status = get_status(self.workspace)["targets"]["L1"]
        self.assertEqual(retry_status["human_review_state"], "awaiting-human-review")
        self.assertEqual(retry_status["historical_review_count"], 3)

    def test_review_operation_is_idempotent_and_latest_review_per_reviewer_is_active(self) -> None:
        self.submit("L1")
        first = self.review(
            "L1",
            reviewer="Reviewer A",
            decision="pass",
            operation_id="review-l1-a",
        )
        replay = self.review(
            "L1",
            reviewer="Reviewer A",
            decision="pass",
            operation_id="review-l1-a",
        )
        self.assertEqual(replay["id"], first["id"])

        with self.assertRaisesRegex(TrainingError, "operation ID"):
            record_review(
                self.workspace,
                "L1",
                reviewer="Reviewer A",
                decision="revise",
                ratings=RATINGS,
                rationale="A different payload must not reuse the operation ID.",
                strengths="Frozen evidence still exists.",
                gaps="More independent evidence is now requested.",
                operation_id="review-l1-a",
            )

        self.review("L1", reviewer="Reviewer A", decision="revise")
        status = get_status(self.workspace)["targets"]["L1"]
        self.assertEqual(status["human_review_state"], "needs-revision")
        self.assertEqual(len(status["active_reviews"]), 1)
        self.assertEqual(status["active_reviews"][0]["decision"], "revise")
        self.assertEqual(status["historical_review_count"], 1)

    def test_pass_review_must_be_internally_consistent_and_capstone_has_explicit_gate(self) -> None:
        self.submit("L1")
        weak = dict(RATINGS)
        weak["Prove"] = "partial"
        with self.assertRaisesRegex(TrainingError, "demonstrated"):
            self.review("L1", reviewer="Reviewer", decision="pass", ratings=weak)

        for target in ("L1", "L2", "L3", "L4"):
            if target != "L1":
                self.submit(target)
            self.review(target, reviewer="Reviewer", decision="pass")

        self.submit("capstone")
        with self.assertRaisesRegex(TrainingError, "all four"):
            self.review("capstone", reviewer="Reviewer", decision="pass")
        capstone_ratings = {band: "demonstrated" for band in RATINGS}
        self.review(
            "capstone",
            reviewer="Reviewer",
            decision="pass",
            ratings=capstone_ratings,
        )
        status = get_status(self.workspace)
        self.assertEqual(status["targets"]["capstone"]["human_review_state"], "human-passed")
        self.assertEqual(status["overall_state"], "human-reviewed-complete")
        self.assertEqual(status["scientific_correctness"], "not_assessed")

        self.worksheet("capstone").write_text(
            self.worksheet("capstone").read_text(encoding="utf-8")
            + "\nUnsubmitted follow-up analysis.\n",
            encoding="utf-8",
        )
        changed = get_status(self.workspace)
        self.assertEqual(
            changed["overall_state"],
            "human-reviewed-complete-with-unsubmitted-draft",
        )
        self.assertEqual(
            changed["targets"]["capstone"]["current_draft_state"],
            "changed-unsubmitted",
        )
        report = self.workspace / "changed-draft-report.md"
        export_progress(self.workspace, report, format_name="markdown")
        report_text = report.read_text(encoding="utf-8")
        self.assertIn("changed-unsubmitted", report_text)
        self.assertIn(
            changed["targets"]["capstone"]["latest_attempt_sha256"],
            report_text,
        )

    def test_strict_load_rejects_tampering_extra_keys_duplicate_json_and_symlinks(self) -> None:
        self.submit("L1")
        progress_path = self.workspace / "progress.json"
        original = progress_path.read_text(encoding="utf-8")
        progress = json.loads(original)
        progress["unexpected"] = True
        progress_path.write_text(json.dumps(progress), encoding="utf-8")
        with self.assertRaisesRegex(TrainingError, "unexpected fields"):
            load_progress(self.workspace)

        progress_path.write_text(original, encoding="utf-8")
        duplicate = original.replace('"schema_version": 1,', '"schema_version": 1, "schema_version": 1,', 1)
        progress_path.write_text(duplicate, encoding="utf-8")
        with self.assertRaisesRegex(TrainingError, "duplicate JSON key"):
            load_progress(self.workspace)

        progress_path.write_text(original.replace('"schema_version": 1', '"schema_version": NaN', 1), encoding="utf-8")
        with self.assertRaisesRegex(TrainingError, "non-finite JSON"):
            load_progress(self.workspace)

        for invalid_version in (True, 1.0):
            with self.subTest(schema_version=invalid_version):
                progress = json.loads(original)
                progress["schema_version"] = invalid_version
                progress_path.write_text(json.dumps(progress), encoding="utf-8")
                with self.assertRaisesRegex(TrainingError, "unsupported progress schema"):
                    load_progress(self.workspace)

        progress_path.write_text("[" * 2_000 + "0" + "]" * 2_000, encoding="utf-8")
        with self.assertRaisesRegex(TrainingError, "invalid progress JSON"):
            load_progress(self.workspace)

        progress_path.write_text(original, encoding="utf-8")
        progress = json.loads(original)
        progress["targets"]["L1"]["attempts"][0]["worksheet_snapshot"] += "tampered"
        progress_path.write_text(json.dumps(progress), encoding="utf-8")
        with self.assertRaisesRegex(TrainingError, "digest"):
            load_progress(self.workspace)

        progress_path.write_text(original, encoding="utf-8")
        rubric = self.workspace / "RUBRIC.md"
        rubric.write_text(rubric.read_text(encoding="utf-8") + "\nchanged\n", encoding="utf-8")
        with self.assertRaisesRegex(TrainingError, "resource"):
            load_progress(self.workspace)

        initialize_workspace(self.root / "symlink-workspace", learner_label="Learner")
        symlink_workspace = self.root / "symlink-workspace"
        target = symlink_workspace / "worksheets" / "L1.md"
        outside = self.root / "outside.md"
        outside.write_text("# outside", encoding="utf-8")
        target.unlink()
        target.symlink_to(outside)
        with self.assertRaisesRegex(TrainingError, "regular file"):
            check_worksheet(symlink_workspace, "L1")

    def test_operation_digests_bind_mutable_fields_and_every_result(self) -> None:
        self.submit("L1")
        self.review("L1", reviewer="Reviewer", decision="revise")
        progress_path = self.workspace / "progress.json"
        original = progress_path.read_text(encoding="utf-8")

        changed_review = json.loads(original)
        changed_review["targets"]["L1"]["reviews"][0]["decision"] = "blocked"
        progress_path.write_text(json.dumps(changed_review), encoding="utf-8")
        with self.assertRaisesRegex(TrainingError, "payload_sha256"):
            load_progress(self.workspace)

        changed_attempt = json.loads(original)
        changed_attempt["targets"]["L1"]["attempts"][0]["note"] = "rewritten note"
        progress_path.write_text(json.dumps(changed_attempt), encoding="utf-8")
        with self.assertRaisesRegex(TrainingError, "payload_sha256"):
            load_progress(self.workspace)

        missing_operation = json.loads(original)
        missing_operation["operations"].pop()
        progress_path.write_text(json.dumps(missing_operation), encoding="utf-8")
        with self.assertRaisesRegex(TrainingError, "exactly one operation"):
            load_progress(self.workspace)

    def test_malformed_unhashable_fields_and_non_utf8_worksheet_fail_closed(self) -> None:
        self.submit("L1")
        self.review("L1", reviewer="Reviewer", decision="revise")
        progress_path = self.workspace / "progress.json"
        original = progress_path.read_text(encoding="utf-8")
        mutations = (
            lambda value: value["targets"]["L1"]["reviews"][0].__setitem__("attempt_id", []),
            lambda value: value["operations"][0].__setitem__("kind", []),
            lambda value: value["operations"][0].__setitem__("result_id", []),
        )
        for mutate in mutations:
            value = json.loads(original)
            mutate(value)
            progress_path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(TrainingError):
                load_progress(self.workspace)

        progress_path.write_text(original, encoding="utf-8")
        self.worksheet("L2").write_bytes(b"\xff\xfe\x00")
        with self.assertRaisesRegex(TrainingError, "UTF-8"):
            check_worksheet(self.workspace, "L2")

    def test_race_swap_to_symlink_is_refused_before_bytes_are_read(self) -> None:
        outside = self.root / "outside-sentinel.md"
        secret = "OUTSIDE-SENTINEL-MUST-NOT-BE-SNAPSHOTTED"
        outside.write_text(secret, encoding="utf-8")
        worksheet = self.worksheet("L1")
        real_open = os.open
        swapped = False

        def swapping_open(path, flags, mode=0o777, *, dir_fd=None):
            nonlocal swapped
            if path == "L1.md" and dir_fd is not None and not swapped:
                swapped = True
                worksheet.unlink()
                worksheet.symlink_to(outside)
            return real_open(path, flags, mode, dir_fd=dir_fd)

        with mock.patch("stewardship_lab.training.os.open", side_effect=swapping_open):
            with self.assertRaisesRegex(TrainingError, "without symlinks"):
                check_worksheet(self.workspace, "L1")
        raw_progress = (self.workspace / "progress.json").read_text(encoding="utf-8")
        self.assertNotIn(secret, raw_progress)

    def test_active_lock_refuses_mutation_and_atomic_failure_preserves_old_state(self) -> None:
        self.complete("L1")
        lock = self.workspace / ".rcsl-progress.lock"
        lock.write_text('{"token":"active"}\n', encoding="utf-8")
        with self.assertRaisesRegex(TrainingError, "busy"):
            submit_attempt(self.workspace, "L1", note="Should not write")
        self.assertEqual(load_progress(self.workspace)["targets"]["L1"]["attempts"], [])
        lock.unlink()

        before = (self.workspace / "progress.json").read_bytes()
        with mock.patch("stewardship_lab.training.os.replace", side_effect=OSError("injected replace failure")):
            with self.assertRaisesRegex(TrainingError, "atomically update"):
                submit_attempt(self.workspace, "L1", note="Atomic failure")
        self.assertEqual((self.workspace / "progress.json").read_bytes(), before)
        self.assertEqual(load_progress(self.workspace)["targets"]["L1"]["attempts"], [])

        real_open = os.open
        real_close = os.close
        temporary_descriptors: list[int] = []

        def tracking_open(path, flags, mode=0o777, *, dir_fd=None):
            descriptor = real_open(path, flags, mode, dir_fd=dir_fd)
            if isinstance(path, str) and path.startswith(".progress.json.tmp-"):
                temporary_descriptors.append(descriptor)
            return descriptor

        with mock.patch(
            "stewardship_lab.training.os.open", side_effect=tracking_open
        ), mock.patch(
            "stewardship_lab.training.os.fdopen",
            side_effect=OSError("injected fdopen failure"),
        ), mock.patch(
            "stewardship_lab.training.os.close", wraps=real_close
        ) as close_spy:
            with self.assertRaisesRegex(TrainingError, "atomically update"):
                submit_attempt(self.workspace, "L1", note="Descriptor failure")

        self.assertEqual(len(temporary_descriptors), 1)
        self.assertTrue(
            any(
                call.args and call.args[0] == temporary_descriptors[0]
                for call in close_spy.call_args_list
            )
        )
        self.assertEqual((self.workspace / "progress.json").read_bytes(), before)
        self.assertEqual(list(self.workspace.glob(".progress.json.tmp-*")), [])

        real_replace = os.replace
        real_fsync = os.fsync
        replace_finished = False
        injected_post_replace_failure = False

        def tracking_replace(*args, **kwargs):
            nonlocal replace_finished
            result = real_replace(*args, **kwargs)
            replace_finished = True
            return result

        def one_post_replace_sync_failure(descriptor):
            nonlocal injected_post_replace_failure
            if replace_finished and not injected_post_replace_failure:
                injected_post_replace_failure = True
                raise OSError("injected post-replace directory sync failure")
            return real_fsync(descriptor)

        with mock.patch(
            "stewardship_lab.training.os.replace", side_effect=tracking_replace
        ), mock.patch(
            "stewardship_lab.training.os.fsync",
            side_effect=one_post_replace_sync_failure,
        ):
            committed = submit_attempt(
                self.workspace,
                "L1",
                note="Committed once",
                operation_id="submit-after-directory-sync-failure",
            )
        self.assertTrue(injected_post_replace_failure)
        replay = submit_attempt(
            self.workspace,
            "L1",
            note="Committed once",
            operation_id="submit-after-directory-sync-failure",
        )
        self.assertEqual(replay["id"], committed["id"])
        self.assertEqual(
            len(load_progress(self.workspace)["targets"]["L1"]["attempts"]), 1
        )

    def test_mutation_stays_bound_to_original_workspace_if_path_is_replaced(self) -> None:
        self.complete("L1")
        moved_workspace = self.root / "original-workspace-moved"
        from stewardship_lab import training as training_module

        original_loader = training_module._load_progress_from_descriptor
        swapped = False

        def swapping_loader(workspace: Path, workspace_descriptor: int):
            nonlocal swapped
            if not swapped:
                swapped = True
                self.workspace.rename(moved_workspace)
                initialize_workspace(self.workspace, learner_label="Replacement Workspace")
            return original_loader(workspace, workspace_descriptor)

        with mock.patch(
            "stewardship_lab.training._load_progress_from_descriptor",
            side_effect=swapping_loader,
        ):
            attempt = submit_attempt(
                self.workspace,
                "L1",
                note="Pinned directory submission",
                operation_id="submit-pinned-directory",
            )

        self.assertEqual(attempt["id"], "L1-A001")
        moved = load_progress(moved_workspace)
        replacement = load_progress(self.workspace)
        self.assertEqual(len(moved["targets"]["L1"]["attempts"]), 1)
        self.assertEqual(replacement["learner_label"], "Replacement Workspace")
        self.assertEqual(replacement["targets"]["L1"]["attempts"], [])
        self.assertFalse((moved_workspace / ".rcsl-progress.lock").exists())

    def test_export_is_redacted_non_overwriting_and_inside_workspace(self) -> None:
        self.submit("L1")
        record_review(
            self.workspace,
            "L1",
            reviewer="Reviewer <script>alert(1)</script>",
            decision="revise",
            ratings=RATINGS,
            rationale="# Fake pass\n![tracker](https://example.invalid/x)",
            strengths="Bounded evidence",
            gaps="Local Learner, Reviewer <script>, private@example.invalid: unknown claim impact",
        )
        output = self.workspace / "progress-report.md"
        export_progress(self.workspace, output, format_name="markdown")
        text = output.read_text(encoding="utf-8")
        self.assertNotIn("worksheet_snapshot", text)
        self.assertNotIn("Local Learner", text)
        self.assertNotIn("<script>", text)
        self.assertNotIn("![tracker]", text)
        self.assertNotIn("Local Learner", text)
        self.assertNotIn("private@example.invalid", text)
        self.assertNotIn("unknown claim impact", text)
        self.assertIn("review-disagreement" if "review-disagreement" in text else "needs-revision", text)
        with self.assertRaisesRegex(TrainingError, "overwrite"):
            export_progress(self.workspace, output, format_name="markdown")
        with self.assertRaisesRegex(TrainingError, "inside"):
            export_progress(self.workspace, self.root / "outside.json", format_name="json")

        json_output = self.workspace / "progress-report.json"
        export_progress(self.workspace, json_output, format_name="json")
        exported = json_output.read_text(encoding="utf-8")
        self.assertNotIn("worksheet_snapshot", exported)
        self.assertNotIn("Local Learner", exported)
        self.assertNotIn("Reviewer <script>", exported)
        self.assertNotIn("private@example.invalid", exported)
        self.assertNotIn("unknown claim impact", exported)
        self.assertIn("reviewer-1", exported)

        redacted = get_redacted_status(self.workspace)
        self.assertNotIn("learner_label", redacted)
        self.assertNotIn("evidence_gaps", redacted["targets"]["L1"])
        self.assertEqual(
            redacted["targets"]["L1"]["active_reviews"][0]["reviewer"],
            "reviewer-1",
        )
        self.assertEqual(redacted["scientific_correctness"], "not_assessed")

        retryable_output = self.workspace / "retryable-report.json"
        with mock.patch(
            "stewardship_lab.training.os.fsync",
            side_effect=OSError("injected export sync failure"),
        ):
            with self.assertRaisesRegex(TrainingError, "safely create"):
                export_progress(
                    self.workspace, retryable_output, format_name="json"
                )
        self.assertFalse(retryable_output.exists())
        export_progress(self.workspace, retryable_output, format_name="json")
        self.assertTrue(retryable_output.is_file())

    def test_audit_workspace_cannot_be_loaded_as_training_progress(self) -> None:
        audit_workspace = self.root / "audit-workspace"
        audit_workspace.mkdir()
        (audit_workspace / "audit-workspace.json").write_text(
            '{"workspace_type":"rcsl-public-audit-workspace"}\n', encoding="utf-8"
        )
        with self.assertRaisesRegex(TrainingError, "progress.json"):
            load_progress(audit_workspace)

    def test_cli_lifecycle_exit_codes_and_json_contract(self) -> None:
        cli_workspace = self.root / "cli-progress"
        result = run_cli(
            "train", "progress", "init",
            "--output", str(cli_workspace),
            "--learner", "CLI Learner",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Training workspace CREATED", result.stdout)

        result = run_cli("train", "progress", "check", str(cli_workspace), "--target", "L1", "--json")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        incomplete = json.loads(result.stdout)
        self.assertEqual(incomplete["structure_status"], "incomplete")

        complete_template(cli_workspace / "worksheets" / "L1.md")
        result = run_cli("train", "progress", "check", str(cli_workspace), "--target", "L1", "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        checked = json.loads(result.stdout)
        self.assertEqual(checked["semantic_assessment"], "not_performed")

        result = run_cli(
            "train", "progress", "submit", str(cli_workspace),
            "--target", "L1", "--note", "CLI submission",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("AWAITING HUMAN REVIEW", result.stdout)

        result = run_cli("train", "progress", "status", str(cli_workspace), "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        status = json.loads(result.stdout)
        self.assertEqual(status["targets"]["L1"]["attempt_state"], "submitted")
        self.assertEqual(status["targets"]["L1"]["human_review_state"], "awaiting-human-review")
        assert_no_answer_fields(self, status)


if __name__ == "__main__":
    unittest.main()
