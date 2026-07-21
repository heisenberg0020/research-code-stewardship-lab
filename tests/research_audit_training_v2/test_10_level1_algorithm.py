from __future__ import annotations

import ast
import difflib
import importlib.util
import io
import json
import re
import sys
import tempfile
import tokenize
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace

import torch
import torch.nn.functional as F

from tests.research_audit_training_v2.helpers import V2, run_python


LEVEL = V2 / "level_1_algorithm_semantics"
ISOLATED = LEVEL / "DO_NOT_OPEN_UNTIL_FINISHED"
CANDIDATES = LEVEL / "candidates"
RULES = {
    "L1_BATCH_INVARIANCE",
    "L1_PADDING",
    "L1_AUX_GRAD",
    "L1_LOGIT_CE",
}


def load_module(path: Path):
    """Load a standalone exercise module, including dataclasses on Python 3.12."""
    module_name = f"level1_test_{path.stem}_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(module_name, None)
        raise
    return module


def normalized_tokens(source: str) -> tuple[str, ...]:
    ignored = {
        tokenize.ENCODING,
        tokenize.ENDMARKER,
        tokenize.INDENT,
        tokenize.DEDENT,
        tokenize.NEWLINE,
        tokenize.NL,
        tokenize.COMMENT,
    }
    return tuple(
        token.string
        for token in tokenize.generate_tokens(io.StringIO(source).readline)
        if token.type not in ignored
    )


def distance_totals(sequences: dict[str, object]) -> dict[str, float]:
    totals = {name: 0.0 for name in sequences}
    for left, left_sequence in sequences.items():
        for right, right_sequence in sequences.items():
            if left < right:
                distance = 1.0 - difflib.SequenceMatcher(
                    None, left_sequence, right_sequence, autojunk=False
                ).ratio()
                totals[left] += distance
                totals[right] += distance
    return totals


class Level1Tests(unittest.TestCase):
    def test_public_smoke_accepts_all_candidates(self) -> None:
        result = run_python("level_1_algorithm_semantics/run_smoke.py", cwd=V2)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.count("PASS"), 5)
        self.assertEqual(
            result.stdout.splitlines(),
            [f"{letter}: PASS" for letter in "ABCDE"],
        )
        self.assertNotRegex(result.stdout, r"correct|fault|probe|trusted")

    def test_hidden_probes_find_one_trusted_and_four_single_failures(self) -> None:
        probes = load_module(ISOLATED / "probes.py")
        report = probes.classify_all()
        self.assertEqual(set(report), set("ABCDE"))
        self.assertEqual(sum(not failures for failures in report.values()), 1)
        self.assertEqual(sorted(len(failures) for failures in report.values()), [0, 1, 1, 1, 1])
        self.assertEqual(
            {rule for failures in report.values() for rule in failures},
            RULES,
        )

    def test_hidden_probe_infrastructure_errors_are_not_misclassified(self) -> None:
        probes = load_module(ISOLATED / "probes.py")

        def explode(*_args, **_kwargs):
            raise RuntimeError("probe exploded")

        dummy = SimpleNamespace(localize_intent=explode)
        with self.assertRaisesRegex(RuntimeError, "probe exploded"):
            probes.classify_module(dummy)

    def test_detached_auxiliary_keeps_recorded_value_but_removes_residual_gradient(self) -> None:
        weight = torch.tensor(1.75, dtype=torch.float64, requires_grad=True)
        recommendation = weight.square()
        auxiliary = (3.0 * weight - 2.0).square()
        live_total = recommendation + 0.4 * auxiliary
        detached_total = recommendation + 0.4 * auxiliary.detach()

        self.assertEqual(live_total.item(), detached_total.item())
        live_residual = live_total - recommendation
        detached_residual = detached_total - recommendation
        live_gradient = torch.autograd.grad(live_residual, weight, retain_graph=True)[0]
        detached_gradient = torch.autograd.grad(
            detached_residual,
            weight,
            allow_unused=True,
        )[0]
        self.assertNotEqual(live_gradient.item(), 0.0)
        self.assertEqual(detached_gradient.item(), 0.0)

    def test_double_softmax_preserves_argmax_but_changes_ce_loss_and_gradient(self) -> None:
        logits = torch.tensor(
            [[12.0, 0.0, -7.0], [-5.0, 9.0, 2.0]],
            dtype=torch.float64,
            requires_grad=True,
        )
        targets = torch.tensor([2, 3])
        probabilities = logits.softmax(dim=-1)
        self.assertTrue(torch.equal(logits.argmax(dim=-1), probabilities.argmax(dim=-1)))

        raw_loss = F.cross_entropy(logits, targets - 1)
        probability_loss = F.cross_entropy(probabilities, targets - 1)
        raw_gradient = torch.autograd.grad(raw_loss, logits, retain_graph=True)[0]
        probability_gradient = torch.autograd.grad(probability_loss, logits)[0]
        self.assertFalse(torch.allclose(raw_loss, probability_loss))
        self.assertFalse(torch.allclose(raw_gradient, probability_gradient))

    def test_recommendation_losses_accept_integer_valued_floating_targets(self) -> None:
        targets = torch.tensor([1.0, 3.0], dtype=torch.float64)
        for letter in "ABCDE":
            module = load_module(CANDIDATES / f"{letter}.py")
            logits = torch.tensor(
                [[2.0, -1.0, 0.5], [-0.2, 0.3, 1.4]],
                dtype=torch.float64,
                requires_grad=True,
            )
            loss = module.recommendation_loss(logits, targets)
            self.assertEqual(loss.ndim, 0, letter)
            self.assertTrue(torch.isfinite(loss), letter)
            gradient = torch.autograd.grad(loss, logits)[0]
            self.assertTrue(torch.isfinite(gradient).all(), letter)

    def test_manifest_repairs_each_single_failure_without_changing_other_files(self) -> None:
        probes = load_module(ISOLATED / "probes.py")
        manifest = json.loads((ISOLATED / "answer_manifest.json").read_text(encoding="utf-8"))
        report = probes.classify_all()
        trusted = manifest["trusted_candidate"]
        entries = manifest["candidates"]

        self.assertEqual(set(entries), set("ABCDE"))
        self.assertEqual(report[trusted], ())
        faulty = {letter: entry for letter, entry in entries.items() if entry["status"] == "faulty"}
        self.assertEqual(len(faulty), 4)
        self.assertEqual({entry["failed_rule"] for entry in faulty.values()}, RULES)

        required_explanation = {
            "formula",
            "mutation_span",
            "repair_expression",
            "why_runnable",
            "causal_chain",
            "minimal_counterexample",
        }
        for letter, entry in faulty.items():
            self.assertTrue(required_explanation.issubset(entry), letter)
            source_path = CANDIDATES / f"{letter}.py"
            source = source_path.read_text(encoding="utf-8")
            mutation_span = entry["mutation_span"]
            self.assertEqual(source.count(mutation_span), 1, letter)
            repaired = source.replace(mutation_span, entry["repair_expression"])
            with tempfile.TemporaryDirectory() as temporary:
                temporary_path = Path(temporary) / f"{letter}.py"
                temporary_path.write_text(repaired, encoding="utf-8")
                repaired_module = load_module(temporary_path)
                self.assertEqual(probes.classify_module(repaired_module), (), letter)
            self.assertEqual(report[letter], (entry["failed_rule"],), letter)

    def test_semantic_sites_have_no_textual_majority_and_trusted_is_not_text_center(self) -> None:
        manifest = json.loads((ISOLATED / "answer_manifest.json").read_text(encoding="utf-8"))
        sources = {
            letter: (CANDIDATES / f"{letter}.py").read_text(encoding="utf-8")
            for letter in "ABCDE"
        }
        sites = manifest["semantic_sites"]
        self.assertEqual(
            set(sites),
            {"query_normalization", "padding_fill", "auxiliary_total", "ce_input", "style_rotation"},
        )
        for site, snippets in sites.items():
            self.assertEqual(set(snippets), set("ABCDE"), site)
            self.assertEqual(len(set(snippets.values())), 5, site)
            for letter, snippet in snippets.items():
                self.assertEqual(sources[letter].count(snippet), 1, f"{site}:{letter}")

        marker_counts = {
            "query_normalization": sum("0 if" in snippet for snippet in sites["query_normalization"].values()),
            "padding_fill": sum("0.0" in snippet for snippet in sites["padding_fill"].values()),
            "auxiliary_total": sum("detach" in snippet for snippet in sites["auxiliary_total"].values()),
            "ce_input": sum("softmax" in snippet for snippet in sites["ce_input"].values()),
        }
        for site, count in marker_counts.items():
            self.assertIn(count, (2, 3), f"{site} marker count: {count}")

        token_sequences = {letter: normalized_tokens(source) for letter, source in sources.items()}
        ast_sequences = {
            letter: ast.dump(ast.parse(source), include_attributes=False)
            for letter, source in sources.items()
        }
        token_totals = distance_totals(token_sequences)
        ast_totals = distance_totals(ast_sequences)
        trusted = manifest["trusted_candidate"]
        self.assertGreater(len(token_sequences[trusted]), min(map(len, token_sequences.values())))
        for totals in (token_totals, ast_totals):
            minimum = min(totals.values())
            unique_center = [letter for letter, total in totals.items() if abs(total - minimum) < 1e-12]
            self.assertFalse(unique_center == [trusted], totals)

    def test_public_materials_do_not_encode_answer_mapping(self) -> None:
        public_paths = [LEVEL / "README.md", LEVEL / "PAPER_MAP.md", LEVEL / "ANSWER_SHEET.md"]
        mapping_pattern = re.compile(
            r"(?i:trusted|correct|fault(?:y)?|batch|padding|aux(?:iliary)?|logit|ce)"
            r"[^\n]{0,40}\b[A-E]\b|\b[A-E]\b[^\n]{0,40}"
            r"(?i:trusted|correct|fault(?:y)?|batch|padding|aux(?:iliary)?|logit|ce)",
        )
        for path in public_paths:
            text = path.read_text(encoding="utf-8")
            self.assertIsNone(mapping_pattern.search(text), str(path))


if __name__ == "__main__":
    unittest.main()
