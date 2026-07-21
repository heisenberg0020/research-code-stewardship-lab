from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import torch

from LLM4SBR_research_audit_training_v2.shared.metrics_reference import (
    aggregate_metrics,
    per_example_metrics,
)
from LLM4SBR_research_audit_training_v2.shared.schemas import (
    load_csv,
    load_json,
    load_jsonl,
    require_keys,
)
from LLM4SBR_research_audit_training_v2.shared.synthetic_sbr import (
    algorithm_batch,
    prefix_examples,
    raw_sessions,
)


class SharedContractTests(unittest.TestCase):
    def test_algorithm_batch_is_repeatable_and_compact_core_compatible(self) -> None:
        first = algorithm_batch()
        second = algorithm_batch()
        for name in (
            "sequence",
            "mask",
            "long_inference",
            "short_inference",
            "item_text",
            "targets",
        ):
            self.assertTrue(torch.equal(getattr(first, name), getattr(second, name)), name)
        self.assertEqual(first.sequence.shape, (6, 7, first.hidden_dim))
        self.assertEqual(first.mask.shape, first.sequence.shape[:2])
        self.assertEqual(first.long_inference.shape, (6, first.text_dim))
        self.assertEqual(first.short_inference.shape, (6, first.text_dim))
        self.assertEqual(first.item_text.shape[1], first.text_dim)
        self.assertEqual(first.targets.shape, (6,))
        self.assertTrue(torch.all(first.targets > 0))
        self.assertTrue(torch.all(first.targets < first.n_items))

    def test_raw_sessions_have_unique_nonpadding_items_and_time_order(self) -> None:
        sessions = raw_sessions()
        self.assertGreaterEqual(len(sessions), 15)
        self.assertEqual(len({session.session_id for session in sessions}), len(sessions))
        self.assertEqual(
            [session.timestamp for session in sessions],
            sorted(session.timestamp for session in sessions),
        )
        self.assertGreaterEqual(len({item for session in sessions for item in session.items}), 8)
        self.assertGreaterEqual(len({len(session.items) for session in sessions}), 3)
        self.assertTrue(all(0 not in session.items for session in sessions))
        self.assertTrue(any(len(set(session.items)) < len(session.items) for session in sessions))

    def test_raw_item_vocabulary_matches_algorithm_batch_universe(self) -> None:
        batch = algorithm_batch()
        self.assertEqual(batch.item_text.shape[0], batch.n_items - 1)
        for item in (item for session in raw_sessions() for item in session.items):
            self.assertGreater(item, 0)
            self.assertLess(item, batch.n_items)

    def test_prefix_examples_preserve_parent_identity(self) -> None:
        sessions = raw_sessions()
        examples = prefix_examples(sessions)
        by_id = {session.session_id: session for session in sessions}
        self.assertGreater(len(examples), len(sessions))
        self.assertEqual(len({example.sample_id for example in examples}), len(examples))
        for example in examples:
            original = by_id[example.session_id].items
            self.assertEqual(tuple(example.prefix), original[: example.prefix_length])
            self.assertEqual(example.target, original[example.prefix_length])
            self.assertEqual(example.long_embedding, by_id[example.session_id].long_embedding)
            self.assertEqual(example.short_embedding, by_id[example.session_id].short_embedding)

    def test_metrics_include_one_row_and_zero_for_every_miss(self) -> None:
        rows = per_example_metrics([[3, 2], [5, 4]], [2, 9], k=2)
        self.assertEqual(len(rows), 2)
        self.assertEqual((rows[0].rank, rows[0].hr, rows[0].mrr), (2, 1.0, 0.5))
        self.assertAlmostEqual(rows[0].ndcg, 1.0 / torch.log2(torch.tensor(3.0)).item())
        self.assertEqual((rows[1].rank, rows[1].hr, rows[1].mrr, rows[1].ndcg), (None, 0.0, 0.0, 0.0))
        self.assertEqual(aggregate_metrics(rows), {"hr": 0.5, "mrr": 0.25, "ndcg": rows[0].ndcg / 2})

    def test_metric_inputs_have_matching_population_and_valid_k(self) -> None:
        with self.assertRaisesRegex(ValueError, "same length"):
            per_example_metrics([[1]], [1, 2], k=1)
        with self.assertRaisesRegex(ValueError, "positive"):
            per_example_metrics([[1]], [1], k=0)

    def test_json_and_jsonl_errors_identify_source_file_and_line(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bad_json = root / "bad.json"
            bad_json.write_text("{not-json", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "bad\\.json"):
                load_json(bad_json)

            records = root / "records.jsonl"
            records.write_text('{"sample_id": "one"}\n{not-json}\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, r"records\.jsonl.*line 2"):
                load_jsonl(records, required_keys=("sample_id",))

    def test_jsonl_materializes_generator_required_keys_for_every_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            records = Path(temporary) / "generator-keys.jsonl"
            records.write_text('{"sample_id": "one"}\n{}\n', encoding="utf-8")
            required_keys = (key for key in ("sample_id",))
            with self.assertRaisesRegex(ValueError, r"generator-keys\.jsonl.*line 2"):
                load_jsonl(records, required_keys=required_keys)

    def test_csv_and_required_key_errors_identify_source_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            incomplete = root / "incomplete.csv"
            incomplete.write_text("sample_id,target\none,3\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "incomplete\\.csv"):
                load_csv(incomplete, required_keys=("sample_id", "target", "session_id"))
            with self.assertRaisesRegex(ValueError, "manual.json"):
                require_keys({"sample_id": "one"}, ("sample_id", "target"), "manual.json")

    def test_required_values_reject_empty_and_whitespace_strings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rows = root / "blank-values.csv"
            rows.write_text("sample_id,target\none,   \n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, r"blank-values\.csv.*line 2"):
                load_csv(rows, required_keys=("sample_id", "target"))
            with self.assertRaisesRegex(ValueError, "manual.json"):
                require_keys({"sample_id": ""}, ("sample_id",), "manual.json")

    def test_loaders_return_real_parsed_records(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            document = root / "document.json"
            document.write_text(json.dumps({"study_id": "s1"}), encoding="utf-8")
            events = root / "events.jsonl"
            events.write_text('{"event_id": "e1"}\n', encoding="utf-8")
            table = root / "table.csv"
            table.write_text("run_id,status\nr1,complete\n", encoding="utf-8")
            self.assertEqual(load_json(document), {"study_id": "s1"})
            self.assertEqual(load_jsonl(events, required_keys=("event_id",)), [{"event_id": "e1"}])
            self.assertEqual(load_csv(table, required_keys=("run_id", "status")), [{"run_id": "r1", "status": "complete"}])


if __name__ == "__main__":
    unittest.main()
