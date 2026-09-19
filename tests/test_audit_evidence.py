"""Tests for immutable, content-bound audit evidence primitives."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import threading
import unittest
from unittest import mock

import stewardship_lab.audit_evidence as evidence
from stewardship_lab.audit_evidence import (
    AuditEvidenceError,
    build_audit_case_manifest,
    build_content_evidence_record,
    content_evidence_record_ref,
    read_external_source,
    read_project_source,
    store_audit_case,
    store_evidence_blob,
    validate_content_binding,
    validate_content_evidence_record,
    verify_content_evidence_record_ref,
    verify_content_store,
)
from stewardship_lab.bindings import (
    artifact_ref,
    build_case_manifest,
    canonical_json_bytes,
    case_ref,
    record_ref,
    source_revision,
    subject_ref,
)


class AuditEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.project = self.root / "project"
        self.project.mkdir()
        self.subject = subject_ref("audit/example-project", "git-project")
        self.head = "a" * 40
        self.contract = b"# G0 Research Contract\n\nExact approved scope.\n"
        self.manifest = build_audit_case_manifest(
            self.subject,
            "baseline-001",
            self.head,
            self.contract,
        )
        self.binding = store_audit_case(
            self.workspace, self.manifest, self.contract
        )
        self.case = self.binding["case_ref"]

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _record(
        self,
        *,
        evidence_id: str = "E-001",
        evidence_type: str = "artifact",
        kind: str = "observed",
        data: bytes = b"bounded result\n",
        logical_path: str = "evidence/E-001/result.txt",
        source: dict[str, object] | None = None,
        case_value: dict[str, object] | None = None,
        declared_command: str | None = None,
        exit_code: int | None = None,
    ) -> dict[str, object]:
        selected_source = source or {"kind": "external", "ref": logical_path}
        reference = store_evidence_blob(self.workspace, logical_path, data)
        type_fields: dict[str, object] = {}
        if evidence_type == "artifact":
            type_fields["artifact_role"] = "result"
        elif evidence_type == "environment":
            type_fields["environment_scope"] = "runtime-dependencies"
        return build_content_evidence_record(
            evidence_id=evidence_id,
            evidence_type=evidence_type,
            kind=kind,
            case=case_value or self.case,
            artifact=reference,
            source=selected_source,
            summary="Imported without executing or interpreting the source.",
            actor="Audit Owner",
            recorded_at="2026-09-13T01:02:03Z",
            declared_command=declared_command,
            exit_code=exit_code,
            **type_fields,
        )

    def _case_path(self, binding: dict[str, object] | None = None) -> Path:
        active = binding or self.binding
        reference = active["case_ref"]
        assert isinstance(reference, dict)
        return (
            self.workspace
            / "case-manifests"
            / "sha256"
            / f"{reference['case_sha256']}.json"
        )

    def _blob_path(self, digest: str) -> Path:
        return self.workspace / "evidence" / "blobs" / "sha256" / digest

    def test_case_manifest_is_deterministic_and_binds_all_case_inputs(self) -> None:
        repeated = build_audit_case_manifest(
            self.subject, "baseline-001", self.head, self.contract
        )
        self.assertEqual(repeated, self.manifest)
        self.assertEqual(case_ref(repeated), self.binding["case_ref"])

        variants = (
            build_audit_case_manifest(
                self.subject, "baseline-002", self.head, self.contract
            ),
            build_audit_case_manifest(
                self.subject, "baseline-001", "b" * 40, self.contract
            ),
            build_audit_case_manifest(
                self.subject, "baseline-001", self.head, self.contract + b"changed"
            ),
            build_audit_case_manifest(
                subject_ref("audit/other", "git-project"),
                "baseline-001",
                self.head,
                self.contract,
            ),
        )
        base_digest = self.binding["case_ref"]["case_sha256"]
        for variant in variants:
            with self.subTest(variant=variant):
                self.assertNotEqual(
                    case_ref(variant)["case_sha256"],
                    base_digest,
                )

    def test_case_builder_requires_git_subject_valid_head_and_bounded_bytes(self) -> None:
        with self.assertRaisesRegex(AuditEvidenceError, "git-project"):
            build_audit_case_manifest(
                subject_ref("training/example", "training-case"),
                "baseline-001",
                self.head,
                self.contract,
            )
        with self.assertRaisesRegex(AuditEvidenceError, "source revision"):
            build_audit_case_manifest(
                self.subject, "baseline-001", "not-a-head", self.contract
            )
        with self.assertRaisesRegex(AuditEvidenceError, "must be bytes"):
            build_audit_case_manifest(  # type: ignore[arg-type]
                self.subject, "baseline-001", self.head, "text"
            )
        with mock.patch.object(evidence, "MAX_CONTENT_BYTES", 2):
            with self.assertRaisesRegex(AuditEvidenceError, "byte limit"):
                build_audit_case_manifest(
                    self.subject, "baseline-001", self.head, b"too long"
                )

    def test_content_binding_is_a_strict_versioned_subschema(self) -> None:
        self.assertEqual(validate_content_binding(self.binding), self.binding)
        for changed in (
            {**self.binding, "schema_version": 2},
            {**self.binding, "binding_type": "other"},
            {**self.binding, "extra": True},
        ):
            with self.subTest(changed=changed):
                with self.assertRaises(AuditEvidenceError):
                    validate_content_binding(changed)

    def test_case_cas_is_canonical_private_and_idempotent(self) -> None:
        path = self._case_path()
        self.assertEqual(path.read_bytes(), canonical_json_bytes(self.manifest))
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        before = path.stat()
        self.assertEqual(
            store_audit_case(self.workspace, self.manifest, self.contract),
            self.binding,
        )
        self.assertEqual(path.stat().st_ino, before.st_ino)
        self.assertEqual(path.read_bytes(), canonical_json_bytes(self.manifest))

    def test_case_cas_reuse_rejects_tamper_instead_of_overwriting(self) -> None:
        path = self._case_path()
        path.write_bytes(b"tampered")
        with self.assertRaisesRegex(AuditEvidenceError, "content address"):
            store_audit_case(self.workspace, self.manifest, self.contract)
        self.assertEqual(path.read_bytes(), b"tampered")

    def test_evidence_blob_cas_is_private_deduplicated_and_tamper_evident(self) -> None:
        data = b"same bytes"
        first = store_evidence_blob(
            self.workspace, "evidence/E-001/output.bin", data
        )
        path = self._blob_path(first["sha256"])
        inode = path.stat().st_ino
        second = store_evidence_blob(
            self.workspace, "evidence/E-002/also-output.bin", data
        )
        self.assertEqual(first["sha256"], second["sha256"])
        self.assertEqual(path.stat().st_ino, inode)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

        path.write_bytes(b"wrong bytes")
        with self.assertRaisesRegex(AuditEvidenceError, "content address"):
            store_evidence_blob(
                self.workspace, "evidence/E-003/output.bin", data
            )
        self.assertEqual(path.read_bytes(), b"wrong bytes")

    def test_evidence_blob_rejects_a_new_object_before_store_capacity_is_exceeded(
        self,
    ) -> None:
        new_data = b"new object"
        new_digest = hashlib.sha256(new_data).hexdigest()
        with mock.patch.object(evidence, "MAX_CAS_OBJECTS", 1):
            with self.assertRaisesRegex(AuditEvidenceError, "object limit"):
                store_evidence_blob(self.workspace, "evidence/new.bin", new_data)
            self.assertFalse(self._blob_path(new_digest).exists())
            self.assertEqual(
                verify_content_store(self.workspace, self.binding, [])[
                    "orphan_evidence_blobs"
                ],
                0,
            )

    def test_case_store_preflights_both_stores_before_publishing_contract_blob(
        self,
    ) -> None:
        second_manifest = build_audit_case_manifest(
            self.subject, "baseline-002", "b" * 40, self.contract
        )
        store_audit_case(self.workspace, second_manifest, self.contract)
        new_contract = b"new contract bytes"
        new_manifest = build_audit_case_manifest(
            self.subject, "baseline-003", "c" * 40, new_contract
        )
        new_contract_digest = hashlib.sha256(new_contract).hexdigest()
        new_manifest_path = (
            self.workspace
            / "case-manifests"
            / "sha256"
            / f"{case_ref(new_manifest)['case_sha256']}.json"
        )

        with mock.patch.object(evidence, "MAX_CAS_OBJECTS", 2):
            with self.assertRaisesRegex(AuditEvidenceError, "object limit"):
                store_audit_case(self.workspace, new_manifest, new_contract)
            self.assertFalse(self._blob_path(new_contract_digest).exists())
            self.assertFalse(new_manifest_path.exists())

    def test_project_and_external_readers_capture_only_one_explicit_file(self) -> None:
        nested = self.project / "results"
        nested.mkdir()
        source_path = nested / "run.bin"
        source_path.write_bytes(b"\x00\x01result")
        source_path.chmod(0o700)

        with mock.patch.object(evidence.os, "scandir") as scandir:
            project_snapshot = read_project_source(self.project, "results/run.bin")
            external_snapshot = read_external_source(
                source_path, "instrument/run-001/output"
            )
        scandir.assert_not_called()
        self.assertEqual(project_snapshot.data, b"\x00\x01result")
        self.assertTrue(project_snapshot.executable)
        self.assertEqual(
            project_snapshot.source,
            {"kind": "project-relative", "path": "results/run.bin"},
        )
        self.assertEqual(
            external_snapshot.source,
            {"kind": "external", "ref": "instrument/run-001/output"},
        )
        self.assertNotIn(str(source_path), str(external_snapshot.source))

    def test_source_readers_reject_directory_symlink_and_symlink_parent(self) -> None:
        target = self.project / "target.txt"
        target.write_bytes(b"target")
        link = self.project / "link.txt"
        link.symlink_to(target)
        with self.assertRaisesRegex(AuditEvidenceError, "non-symlink"):
            read_project_source(self.project, "link.txt")
        with self.assertRaisesRegex(AuditEvidenceError, "non-symlink"):
            read_external_source(link, "external/link")
        directory = self.project / "directory"
        directory.mkdir()
        with self.assertRaisesRegex(AuditEvidenceError, "regular"):
            read_project_source(self.project, "directory")

        real_parent = self.project / "real-parent"
        real_parent.mkdir()
        (real_parent / "nested.txt").write_bytes(b"nested")
        parent_link = self.project / "parent-link"
        parent_link.symlink_to(real_parent, target_is_directory=True)
        with self.assertRaisesRegex(AuditEvidenceError, "parents"):
            read_project_source(self.project, "parent-link/nested.txt")

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO requires POSIX")
    def test_source_readers_reject_fifo_without_blocking(self) -> None:
        fifo = self.project / "pipe"
        os.mkfifo(fifo)
        with self.assertRaisesRegex(AuditEvidenceError, "regular"):
            read_project_source(self.project, "pipe")
        with self.assertRaisesRegex(AuditEvidenceError, "regular"):
            read_external_source(fifo, "external/pipe")

    def test_source_readers_reject_protected_and_oversize_before_import(self) -> None:
        with self.assertRaisesRegex(AuditEvidenceError, "isolated"):
            read_project_source(
                self.project,
                "folder/do_not_open_until_finished/answer.txt",
            )
        protected_path = (
            self.root / "DO_NOT_OPEN_UNTIL_FINISHED" / "answer.txt"
        )
        with self.assertRaisesRegex(AuditEvidenceError, "isolated"):
            read_external_source(protected_path, "external/answer")
        with self.assertRaisesRegex(AuditEvidenceError, "isolated"):
            read_external_source(
                self.project / "missing", "DO_NOT_OPEN_UNTIL_FINISHED/answer"
            )

        source = self.project / "large.bin"
        source.write_bytes(b"large")
        with mock.patch.object(evidence, "MAX_CONTENT_BYTES", 2):
            with self.assertRaisesRegex(AuditEvidenceError, "byte limit"):
                read_project_source(self.project, "large.bin")
            with self.assertRaisesRegex(AuditEvidenceError, "byte limit"):
                store_evidence_blob(
                    self.workspace, "evidence/large.bin", b"large"
                )

    def test_source_reader_detects_an_identity_change_during_read(self) -> None:
        source = self.project / "changing.bin"
        source.write_bytes(b"stable bytes")
        identities = [(1,), (1,), (2,), (1,)]
        with mock.patch.object(evidence, "_identity", side_effect=identities):
            with self.assertRaisesRegex(AuditEvidenceError, "changed while"):
                read_project_source(self.project, "changing.bin")

    def test_project_reader_rejects_root_replacement_before_open(self) -> None:
        (self.project / "source.txt").write_bytes(b"original")
        original_root = self.root / "project-before-replacement"
        real_open = os.open
        replaced = False

        def replace_then_open(path, flags, *args, **kwargs):
            nonlocal replaced
            if (
                not replaced
                and os.fspath(path) == self.project.name
                and kwargs.get("dir_fd") is not None
            ):
                self.project.rename(original_root)
                self.project.mkdir()
                (self.project / "source.txt").write_bytes(b"replacement")
                replaced = True
            return real_open(path, flags, *args, **kwargs)

        with mock.patch.object(evidence.os, "open", side_effect=replace_then_open):
            with self.assertRaisesRegex(
                AuditEvidenceError, "project root changed.*anchored"
            ):
                read_project_source(self.project, "source.txt")

    def test_external_reader_rejects_parent_replacement_during_anchor(self) -> None:
        external_parent = self.root / "external-parent"
        external_parent.mkdir()
        (external_parent / "source.txt").write_bytes(b"original")
        original_parent = self.root / "external-parent-before-replacement"
        replacement_parent = self.root / "replacement-parent"
        replacement_parent.mkdir()
        (replacement_parent / "source.txt").write_bytes(b"replacement")
        real_open = os.open
        replaced = False

        def replace_then_open(path, flags, *args, **kwargs):
            nonlocal replaced
            if (
                not replaced
                and os.fspath(path) == external_parent.name
                and kwargs.get("dir_fd") is not None
            ):
                external_parent.rename(original_parent)
                replacement_parent.rename(external_parent)
                replaced = True
            return real_open(path, flags, *args, **kwargs)

        with mock.patch.object(evidence.os, "open", side_effect=replace_then_open):
            with self.assertRaisesRegex(
                AuditEvidenceError, "external source parent changed.*anchored"
            ):
                read_external_source(external_parent / "source.txt", "external/run")

    def test_external_reader_anchors_parent_across_alias_aba(self) -> None:
        original_parent = self.root / "original-external-parent"
        original_parent.mkdir()
        (original_parent / "source.txt").write_bytes(b"original")
        replacement_parent = self.root / "replacement-external-parent"
        replacement_parent.mkdir()
        (replacement_parent / "source.txt").write_bytes(b"replacement")
        alias = self.root / "external-alias"
        alias.symlink_to(original_parent, target_is_directory=True)
        real_resolve = Path.resolve
        resolve_calls = 0

        def retarget_around_resolve(path, strict=False):
            nonlocal resolve_calls
            resolve_calls += 1
            if resolve_calls == 2:
                alias.unlink()
                alias.symlink_to(original_parent, target_is_directory=True)
            result = real_resolve(path, strict=strict)
            if resolve_calls == 1:
                alias.unlink()
                alias.symlink_to(replacement_parent, target_is_directory=True)
            return result

        try:
            with mock.patch.object(Path, "resolve", new=retarget_around_resolve):
                snapshot = read_external_source(
                    alias / "source.txt", "external/aliased-run"
                )
        finally:
            alias.unlink(missing_ok=True)
            alias.symlink_to(original_parent, target_is_directory=True)

        self.assertEqual(snapshot.data, b"original")
        self.assertEqual(resolve_calls, 1)

    def test_all_three_record_types_have_exact_conditional_schemas(self) -> None:
        artifact_record = self._record(evidence_type="artifact")
        environment_record = self._record(
            evidence_id="E-002",
            evidence_type="environment",
            logical_path="evidence/E-002/environment.json",
        )
        command_record = self._record(
            evidence_id="E-003",
            evidence_type="command-result",
            logical_path="evidence/E-003/stdout.txt",
            declared_command="python -m unittest tests.test_target",
            exit_code=0,
        )
        for record in (artifact_record, environment_record, command_record):
            with self.subTest(evidence_type=record["evidence_type"]):
                self.assertEqual(validate_content_evidence_record(record), record)
        self.assertEqual(artifact_record["artifact_role"], "result")
        self.assertEqual(environment_record["environment_scope"], "runtime-dependencies")

        artifact_with_command = {
            **artifact_record,
            "declared_command": "echo not-executed",
            "exit_code": 0,
        }
        with self.assertRaisesRegex(AuditEvidenceError, "unknown"):
            validate_content_evidence_record(artifact_with_command)
        for missing in ("declared_command", "exit_code"):
            invalid = deepcopy(command_record)
            invalid.pop(missing)
            with self.subTest(missing=missing):
                with self.assertRaisesRegex(AuditEvidenceError, "missing"):
                    validate_content_evidence_record(invalid)
        for typed_record, required in (
            (artifact_record, "artifact_role"),
            (environment_record, "environment_scope"),
        ):
            invalid = deepcopy(typed_record)
            invalid.pop(required)
            with self.subTest(missing=required):
                with self.assertRaisesRegex(AuditEvidenceError, "missing"):
                    validate_content_evidence_record(invalid)
        wrong_type_field = {**environment_record, "artifact_role": "result"}
        with self.assertRaisesRegex(AuditEvidenceError, "unknown"):
            validate_content_evidence_record(wrong_type_field)

    def test_record_validation_rejects_source_case_time_exit_and_extra_fields(self) -> None:
        record = self._record(
            evidence_type="command-result",
            declared_command="declared only",
            exit_code=1,
        )
        invalid_records = (
            {**record, "evidence_type": "unknown"},
            {**record, "recorded_at": "2026-09-13T01:02:03+00:00"},
            {**record, "exit_code": True},
            {**record, "kind": "unknown"},
            {**record, "extra": "not allowed"},
            {**record, "source": {"kind": "external", "ref": "bad ref"}},
            {
                **record,
                "source": {
                    "kind": "project-relative",
                    "path": "../escape.txt",
                },
            },
        )
        for invalid in invalid_records:
            with self.subTest(invalid=invalid):
                with self.assertRaises(AuditEvidenceError):
                    validate_content_evidence_record(invalid)

        other_manifest = build_audit_case_manifest(
            self.subject, "baseline-002", "b" * 40, self.contract
        )
        old_binding = store_audit_case(
            self.workspace, other_manifest, self.contract
        )
        empty_historical = verify_content_store(
            self.workspace,
            self.binding,
            [],
            historical_case_refs=[old_binding["case_ref"]],
        )
        self.assertEqual(empty_historical["referenced_case_manifests"], 2)
        historical = self._record(
            evidence_id="E-HISTORICAL",
            logical_path="evidence/E-HISTORICAL/result.txt",
            case_value=old_binding["case_ref"],
        )
        report = verify_content_store(self.workspace, self.binding, [historical])
        self.assertEqual(report["referenced_case_manifests"], 2)

    def test_store_verification_rejects_historical_case_from_another_subject(
        self,
    ) -> None:
        other_manifest = build_audit_case_manifest(
            subject_ref("audit/other-project", "git-project"),
            "baseline-001",
            "b" * 40,
            self.contract,
        )
        other_binding = store_audit_case(
            self.workspace, other_manifest, self.contract
        )
        with self.assertRaisesRegex(AuditEvidenceError, "subject_id"):
            verify_content_store(
                self.workspace,
                self.binding,
                [],
                historical_case_refs=[other_binding["case_ref"]],
            )

    def test_store_verification_rejects_evidence_from_another_subject(self) -> None:
        other_manifest = build_audit_case_manifest(
            subject_ref("audit/other-project", "git-project"),
            "baseline-001",
            "b" * 40,
            self.contract,
        )
        other_binding = store_audit_case(
            self.workspace, other_manifest, self.contract
        )
        other_record = self._record(
            evidence_id="E-OTHER",
            logical_path="evidence/E-OTHER/result.txt",
            case_value=other_binding["case_ref"],
        )
        with self.assertRaisesRegex(AuditEvidenceError, "subject_id"):
            verify_content_store(self.workspace, self.binding, [other_record])

    def test_record_ref_is_returned_and_verified_for_lifecycle_retention(self) -> None:
        record = self._record()
        reference = content_evidence_record_ref(record)
        self.assertEqual(
            verify_content_evidence_record_ref(record, reference), reference
        )
        tampered = {**record, "summary": "changed after event publication"}
        with self.assertRaises(AuditEvidenceError):
            verify_content_evidence_record_ref(tampered, reference)
        wrong_type = record_ref(
            "finding", record["id"], record, record["case_ref"]
        )
        with self.assertRaisesRegex(AuditEvidenceError, "record_type evidence"):
            verify_content_evidence_record_ref(record, wrong_type)

    def test_artifact_path_must_equal_the_single_logical_source(self) -> None:
        record = self._record()
        mismatched = {
            **record,
            "source": {"kind": "external", "ref": "different/result.txt"},
        }
        with self.assertRaisesRegex(AuditEvidenceError, "must equal"):
            validate_content_evidence_record(mismatched)

    def test_store_verification_resolves_references_and_counts_valid_orphans(self) -> None:
        referenced = self._record()
        orphan_blob = store_evidence_blob(
            self.workspace, "evidence/orphan.bin", b"unreferenced but valid"
        )
        orphan_manifest = build_audit_case_manifest(
            self.subject, "baseline-orphan", "b" * 40, self.contract
        )
        store_audit_case(self.workspace, orphan_manifest, self.contract)

        report = verify_content_store(self.workspace, self.binding, [referenced])
        self.assertEqual(
            report,
            {
                "referenced_case_manifests": 1,
                "referenced_evidence_blobs": 2,
                "orphan_case_manifests": 1,
                "orphan_evidence_blobs": 1,
            },
        )
        self.assertTrue(self._blob_path(orphan_blob["sha256"]).is_file())

    def test_case_store_requires_and_verifies_the_exact_contract_blob(self) -> None:
        fresh_workspace = self.root / "fresh-workspace"
        fresh_workspace.mkdir()
        with self.assertRaisesRegex(AuditEvidenceError, "do not match"):
            store_audit_case(fresh_workspace, self.manifest, b"other contract")
        self.assertEqual(list(fresh_workspace.iterdir()), [])

        contract_digest = self.manifest["artifacts"][0]["sha256"]
        self._blob_path(contract_digest).unlink()
        with self.assertRaisesRegex(AuditEvidenceError, "no matching blob"):
            verify_content_store(self.workspace, self.binding, [])

    def test_concurrent_same_content_publication_is_idempotent(self) -> None:
        barrier = threading.Barrier(2)
        results: list[dict[str, object]] = []
        errors: list[BaseException] = []

        def publish() -> None:
            try:
                barrier.wait()
                results.append(
                    store_evidence_blob(
                        self.workspace, "concurrent/result.bin", b"same bytes"
                    )
                )
            except BaseException as error:  # Captured for assertion in the main thread.
                errors.append(error)

        threads = [threading.Thread(target=publish) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
        self.assertEqual(errors, [])
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0], results[1])

    def test_stale_staging_file_is_not_part_of_the_verified_cas(self) -> None:
        stale = self.workspace / ".content-staging" / ".interrupted.tmp"
        stale.write_bytes(b"unpublished temporary bytes")
        stale.chmod(0o600)
        report = verify_content_store(self.workspace, self.binding, [])
        self.assertEqual(report["referenced_evidence_blobs"], 1)
        self.assertEqual(report["orphan_evidence_blobs"], 0)

    def test_store_verification_rejects_missing_tampered_or_illegal_objects(self) -> None:
        record = self._record()
        digest = record["artifact_ref"]["sha256"]
        assert isinstance(digest, str)
        blob_path = self._blob_path(digest)
        blob_path.unlink()
        with self.assertRaises(AuditEvidenceError):
            verify_content_store(self.workspace, self.binding, [record])

        blob_path.write_bytes(b"tampered")
        blob_path.chmod(0o600)
        with self.assertRaisesRegex(AuditEvidenceError, "content address"):
            verify_content_store(self.workspace, self.binding, [record])

        blob_path.unlink()
        store_evidence_blob(
            self.workspace,
            record["artifact_ref"]["path"],
            b"bounded result\n",
        )
        illegal = blob_path.parent / "not-a-digest"
        illegal.write_bytes(b"orphan")
        illegal.chmod(0o600)
        with self.assertRaisesRegex(AuditEvidenceError, "illegal entry"):
            verify_content_store(self.workspace, self.binding, [record])

    def test_store_verification_rejects_corrupt_orphan_and_non_private_mode(self) -> None:
        record = self._record()
        orphan_name = hashlib.sha256(b"claimed orphan").hexdigest()
        corrupt_orphan = self._blob_path(orphan_name)
        corrupt_orphan.write_bytes(b"different bytes")
        corrupt_orphan.chmod(0o600)
        with self.assertRaisesRegex(AuditEvidenceError, "content address"):
            verify_content_store(self.workspace, self.binding, [record])

        corrupt_orphan.unlink()
        case_path = self._case_path()
        case_path.chmod(0o644)
        with self.assertRaisesRegex(AuditEvidenceError, "mode"):
            verify_content_store(self.workspace, self.binding, [record])

    def test_store_verification_rejects_manifest_noncanonical_json_and_symlink(self) -> None:
        case_path = self._case_path()
        pretty = json.dumps(self.manifest, indent=2, sort_keys=True).encode("utf-8")
        case_path.write_bytes(pretty)
        with self.assertRaises(AuditEvidenceError):
            verify_content_store(self.workspace, self.binding, [])

        case_path.unlink()
        target = self.root / "manifest-target"
        target.write_bytes(canonical_json_bytes(self.manifest))
        case_path.symlink_to(target)
        with self.assertRaisesRegex(AuditEvidenceError, "non-symlink"):
            verify_content_store(self.workspace, self.binding, [])

    def test_store_rejects_symlinked_store_component(self) -> None:
        other = self.root / "other"
        other.mkdir()
        unsafe_workspace = self.root / "unsafe-workspace"
        unsafe_workspace.mkdir()
        evidence_root = unsafe_workspace / "evidence"
        evidence_root.symlink_to(other, target_is_directory=True)
        with self.assertRaisesRegex(AuditEvidenceError, "regular directories"):
            store_evidence_blob(unsafe_workspace, "evidence/E-001/x", b"x")

    def test_duplicate_evidence_ids_are_rejected_even_for_distinct_blobs(self) -> None:
        first = self._record()
        second = self._record(
            data=b"other",
            logical_path="evidence/E-001/other.txt",
        )
        with self.assertRaisesRegex(AuditEvidenceError, "duplicate evidence id"):
            verify_content_store(self.workspace, self.binding, [first, second])


if __name__ == "__main__":
    unittest.main()
