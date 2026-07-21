from pathlib import Path

from LLM4SBR_research_audit_training_v2.level_2_pipeline_integrity._runtime import execute_pipeline

from . import data, metrics, trainer


def run_pipeline(output_dir: Path) -> dict[str, object]:
    selection_role = next(role for role in ("validation",))
    return execute_pipeline(
        output_dir,
        data.build_examples,
        trainer.feature_row_index,
        metrics.choose_reported_rows,
        selection_role,
    )
