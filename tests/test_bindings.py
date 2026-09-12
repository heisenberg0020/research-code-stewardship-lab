from __future__ import annotations

from copy import deepcopy
import unittest

from stewardship_lab.bindings import (
    BindingError,
    artifact_ref,
    build_case_manifest,
    canonical_json_bytes,
    case_ref,
    case_sha256,
    record_ref,
    record_sha256,
    sha256_json,
    source_revision,
    subject_ref,
    validate_artifact_ref,
    validate_case_manifest,
    validate_case_ref,
    validate_record_ref,
)


class CanonicalJsonTests(unittest.TestCase):
    def test_canonical_json_is_order_independent_and_compact(self) -> None:
        left = {"z": [True, None, 3], "a": "研究"}
        right = {"a": "研究", "z": [True, None, 3]}
        self.assertEqual(canonical_json_bytes(left), canonical_json_bytes(right))
        self.assertEqual(canonical_json_bytes(left), b'{"a":"\xe7\xa0\x94\xe7\xa9\xb6","z":[true,null,3]}')
        self.assertEqual(sha256_json(left), sha256_json(right))

    def test_canonical_json_rejects_floats_non_json_and_non_nfc(self) -> None:
        for value in (0.0, float("nan"), {"bad": object()}, {1: "bad"}):
            with self.subTest(value=repr(value)):
                with self.assertRaises(BindingError):
                    canonical_json_bytes(value)
        with self.assertRaisesRegex(BindingError, "NFC"):
            canonical_json_bytes("e\u0301")


class ArtifactTests(unittest.TestCase):
    def test_artifact_is_bound_to_path_bytes_size_and_executable_state(self) -> None:
        first = artifact_ref("subject/src/model.py", b"print('ok')\n")
        changed = artifact_ref("subject/src/model.py", b"print('changed')\n")
        executable = artifact_ref(
            "subject/src/model.py", b"print('ok')\n", executable=True
        )
        self.assertEqual(first["size"], 12)
        self.assertNotEqual(first["sha256"], changed["sha256"])
        self.assertNotEqual(sha256_json(first), sha256_json(executable))
        self.assertEqual(validate_artifact_ref(first), first)

    def test_artifact_validation_rejects_ambiguous_or_isolated_paths(self) -> None:
        invalid = (
            "/absolute.txt",
            "../escape.txt",
            "a/../escape.txt",
            "a//b.txt",
            "a\\b.txt",
            "C:/windows.txt",
            ".",
            "case/bad\nname.txt",
            "case/do_not_open_until_finished/key.txt",
        )
        for path in invalid:
            with self.subTest(path=path):
                with self.assertRaises(BindingError):
                    artifact_ref(path, b"x")

    def test_artifact_validation_is_strict(self) -> None:
        value = artifact_ref("case/input.txt", b"x")
        with self.assertRaisesRegex(BindingError, "unknown"):
            validate_artifact_ref({**value, "role": "input"})
        with self.assertRaisesRegex(BindingError, "non-negative integer"):
            validate_artifact_ref({**value, "size": True})
        with self.assertRaisesRegex(BindingError, "boolean"):
            validate_artifact_ref({**value, "executable": 1})
        with self.assertRaisesRegex(BindingError, "bytes"):
            artifact_ref("case/input.txt", bytearray(b"x"))  # type: ignore[arg-type]


class CaseManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.subject = subject_ref("rcsl/example", "training-case")
        self.revision = source_revision("git-sha1", "a" * 40)
        self.first = artifact_ref("case/a.txt", b"a")
        self.second = artifact_ref("case/b.py", b"b", executable=True)

    def test_manifest_sorting_makes_case_digest_input_order_independent(self) -> None:
        left = build_case_manifest(
            self.subject,
            "v1",
            [self.second, self.first],
            source_revision_value=self.revision,
        )
        right = build_case_manifest(
            self.subject,
            "v1",
            [self.first, self.second],
            source_revision_value=self.revision,
        )
        self.assertEqual(left, right)
        self.assertEqual(case_sha256(left), case_sha256(right))
        self.assertEqual(validate_case_manifest(left), left)

    def test_case_ref_is_small_and_content_bound(self) -> None:
        manifest = build_case_manifest(self.subject, "v1", [self.first])
        reference = case_ref(manifest)
        self.assertEqual(
            reference,
            {
                "subject_id": "rcsl/example",
                "case_id": "v1",
                "case_sha256": case_sha256(manifest),
            },
        )
        self.assertEqual(validate_case_ref(reference), reference)

    def test_any_identity_relevant_change_changes_case_digest(self) -> None:
        base = build_case_manifest(
            self.subject,
            "v1",
            [self.first],
            source_revision_value=self.revision,
        )
        variants = (
            build_case_manifest(
                self.subject,
                "v2",
                [self.first],
                source_revision_value=self.revision,
            ),
            build_case_manifest(
                self.subject,
                "v1",
                [artifact_ref("case/a.txt", b"changed")],
                source_revision_value=self.revision,
            ),
            build_case_manifest(
                self.subject,
                "v1",
                [artifact_ref("case/a.txt", b"a", executable=True)],
                source_revision_value=self.revision,
            ),
            build_case_manifest(
                self.subject,
                "v1",
                [self.first],
                source_revision_value=source_revision("git-sha1", "b" * 40),
            ),
        )
        for variant in variants:
            with self.subTest(variant=variant):
                self.assertNotEqual(case_sha256(base), case_sha256(variant))

    def test_manifest_rejects_empty_collision_and_unknown_fields(self) -> None:
        with self.assertRaisesRegex(BindingError, "at least one"):
            build_case_manifest(self.subject, "v1", [])
        with self.assertRaisesRegex(BindingError, "colliding"):
            build_case_manifest(
                self.subject,
                "v1",
                [
                    artifact_ref("case/A.txt", b"a"),
                    artifact_ref("case/a.txt", b"a"),
                ],
            )
        manifest = build_case_manifest(self.subject, "v1", [self.first])
        with self.assertRaisesRegex(BindingError, "unknown"):
            validate_case_manifest({**manifest, "created_at": "not identity"})
        unsorted = build_case_manifest(self.subject, "v1", [self.first, self.second])
        unsorted["artifacts"].reverse()
        with self.assertRaisesRegex(BindingError, "canonical path order"):
            validate_case_manifest(unsorted)

    def test_manifest_validation_rebuilds_instead_of_retaining_mutable_input(self) -> None:
        manifest = build_case_manifest(self.subject, "v1", [self.first])
        validated = validate_case_manifest(manifest)
        validated["artifacts"][0]["path"] = "case/changed.txt"
        self.assertEqual(manifest["artifacts"][0]["path"], "case/a.txt")

    def test_source_revision_scheme_and_length_are_explicit(self) -> None:
        self.assertEqual(
            source_revision("git-sha256", "f" * 64),
            {"scheme": "git-sha256", "value": "f" * 64},
        )
        with self.assertRaises(BindingError):
            source_revision("git-sha1", "f" * 64)
        with self.assertRaises(BindingError):
            source_revision("git", "f" * 40)


class RecordRefTests(unittest.TestCase):
    def setUp(self) -> None:
        manifest = build_case_manifest(
            subject_ref("audit/example", "git-project"),
            "baseline-1",
            [artifact_ref("workspace/research-contract.md", b"scope")],
            source_revision_value=source_revision("git-sha1", "c" * 40),
        )
        self.case = case_ref(manifest)

    def test_record_ref_binds_exact_record_and_case(self) -> None:
        record = {"id": "E-001", "kind": "observed", "summary": "bounded"}
        reference = record_ref("evidence", "E-001", record, self.case)
        self.assertEqual(reference["record_sha256"], record_sha256(record))
        self.assertEqual(reference["case_sha256"], self.case["case_sha256"])
        self.assertEqual(validate_record_ref(reference), reference)
        changed = record_ref(
            "evidence", "E-001", {**record, "summary": "changed"}, self.case
        )
        self.assertNotEqual(reference["record_sha256"], changed["record_sha256"])

    def test_record_and_case_refs_reject_unknown_or_invalid_fields(self) -> None:
        record = record_ref("review", "R-001", {"decision": "pass"}, self.case)
        with self.assertRaises(BindingError):
            validate_record_ref({**record, "reviewer": "label"})
        with self.assertRaises(BindingError):
            validate_record_ref({**record, "record_type": "transition"})
        bad_case = deepcopy(self.case)
        bad_case["case_sha256"] = "ABC"
        with self.assertRaises(BindingError):
            record_ref("review", "R-001", {"decision": "pass"}, bad_case)


if __name__ == "__main__":
    unittest.main()
