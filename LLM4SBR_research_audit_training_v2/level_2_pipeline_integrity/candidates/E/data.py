from collections.abc import Sequence

from LLM4SBR_research_audit_training_v2.level_2_pipeline_integrity import _runtime


def derive_features(prefix: Sequence[int]) -> tuple[list[float], list[float]]:
    return _runtime.derive_features(prefix)


def build_examples() -> list[dict[str, object]]:
    sessions = _runtime.source_sessions()
    split_raw_first = not any(session.timestamp < 0 for session in sessions)
    return _runtime.build_examples(split_raw_first)
