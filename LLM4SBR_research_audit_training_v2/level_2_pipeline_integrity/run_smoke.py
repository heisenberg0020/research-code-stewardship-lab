from __future__ import annotations

import importlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import tempfile

import torch


LEVEL = Path(__file__).resolve().parent
sys.path.insert(0, str(LEVEL.parents[1]))
ARTIFACTS = (
    "split_manifest.json",
    "batch_manifest.json",
    "epoch_metrics.json",
    "evaluation_records.json",
    "selected_checkpoint.json",
    "event_log.jsonl",
    "summary.json",
)


def load_pipeline(letter: str):
    package_dir = LEVEL / "candidates" / letter
    package_name = f"level2_smoke_{letter}"
    spec = importlib.util.spec_from_file_location(
        package_name,
        package_dir / "__init__.py",
        submodule_search_locations=[str(package_dir)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {package_dir}")
    package = importlib.util.module_from_spec(spec)
    sys.modules[package_name] = package
    try:
        spec.loader.exec_module(package)
        return importlib.import_module(f"{package_name}.pipeline")
    except BaseException:
        for name in tuple(sys.modules):
            if name == package_name or name.startswith(f"{package_name}."):
                sys.modules.pop(name, None)
        raise


def smoke(letter: str, root: Path) -> None:
    output_dir = root / letter
    result = load_pipeline(letter).run_pipeline(output_dir)
    if not all((output_dir / artifact).is_file() for artifact in ARTIFACTS):
        raise AssertionError("missing pipeline artifact")
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    if set(result["metrics"]) != {"hr", "mrr", "ndcg"}:
        raise AssertionError("unexpected metric schema")
    if not all(math.isfinite(value) and 0.0 <= value <= 1.0 for value in summary["metrics"].values()):
        raise AssertionError("summary metrics must be finite and bounded")
    selected = json.loads((output_dir / "selected_checkpoint.json").read_text(encoding="utf-8"))
    if not (output_dir / selected["path"]).is_file():
        raise AssertionError("selected checkpoint is missing")


def main() -> None:
    torch.set_num_threads(1)
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        for letter in "ABCDE":
            smoke(letter, root)
            print(f"{letter}: PASS")


if __name__ == "__main__":
    main()
