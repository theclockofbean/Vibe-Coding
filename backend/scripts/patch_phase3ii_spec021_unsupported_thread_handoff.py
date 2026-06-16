"""Patch answer-strategy handoff response for unsupported thread spec queries."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
WORKFLOW_FILE: Final[Path] = BACKEND_ROOT / "app/agent/workflow.py"

OLD_CALL: Final[str] = "_answer_strategy_safety_response(metadata)"
NEW_CALL: Final[str] = "_answer_strategy_safety_response(metadata=metadata, state=state)"

OLD_FUNCTION: Final[str] = '''def _answer_strategy_safety_response(
    metadata: dict[str, Any],
) -> str:
    """Build safety-blocked answer strategy response."""

    forbidden_fragments = _as_text_list(metadata.get("answer_forbidden_fragments"))

    if forbidden_fragments:
        return (
            "该问题涉及高风险业务承诺，不能直接给出确定性答复。"
            "请转人工结合正式数据、业务规则和授权信息确认后再回复。"
        )

    return (
        "该问题涉及需要进一步确认的信息，不能直接给出确定性答复。"
        "为避免给出未经授权的业务承诺，请转人工结合正式数据和业务规则处理。"
    )


def _answer_strategy_split_response(
'''

NEW_FUNCTION: Final[str] = '''def _answer_strategy_safety_response(
    *,
    metadata: dict[str, Any],
    state: Any | None = None,
) -> str:
    """Build safety-blocked answer strategy response."""

    forbidden_fragments = _as_text_list(metadata.get("answer_forbidden_fragments"))

    if forbidden_fragments:
        return (
            "该问题涉及高风险业务承诺，不能直接给出确定性答复。"
            "请转人工结合正式数据、业务规则和授权信息确认后再回复。"
        )

    unsupported_thread = _answer_strategy_unsupported_thread_spec(
        metadata=metadata,
        state=state,
    )

    if unsupported_thread is not None:
        return (
            f"当前无法确认是否支持 {unsupported_thread} 螺纹球头，"
            "不能直接给出确定性答复。"
            "请转人工结合正式数据和业务规则处理。"
        )

    return (
        "该问题涉及需要进一步确认的信息，不能直接给出确定性答复。"
        "为避免给出未经授权的业务承诺，请转人工结合正式数据和业务规则处理。"
    )


def _answer_strategy_unsupported_thread_spec(
    *,
    metadata: dict[str, Any],
    state: Any | None,
) -> str | None:
    """Return unsupported thread spec mentioned in a spec handoff query."""

    candidate_modules = _as_text_list(metadata.get("answer_candidate_modules"))
    primary_module = str(metadata.get("answer_primary_module") or "")

    if primary_module != "spec" and "spec" not in candidate_modules:
        return None

    query_text = _answer_strategy_query_text(state)

    if query_text is None:
        return None

    normalized_query = (
        query_text.upper()
        .replace("Ｍ", "M")
        .replace("１４", "14")
        .replace("１６", "16")
        .replace("１８", "18")
        .replace("２０", "20")
    )

    for thread_spec in ("M14", "M16", "M18", "M20"):
        if thread_spec in normalized_query:
            return thread_spec

    return None


def _answer_strategy_query_text(state: Any | None) -> str | None:
    """Read original user query text from workflow state."""

    if not isinstance(state, dict):
        return None

    for key in ("user_message", "query", "raw_text", "text"):
        value = state.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

    return None


def _answer_strategy_split_response(
'''


def main() -> int:
    """Patch workflow."""

    content = WORKFLOW_FILE.read_text(encoding="utf-8")
    original = content
    errors: list[str] = []
    changes: list[str] = []

    if NEW_CALL in content:
        changes.append("answer strategy safety call already patched")
    elif OLD_CALL in content:
        content = content.replace(OLD_CALL, NEW_CALL, 1)
        changes.append("patched answer strategy safety call")
    else:
        errors.append("answer strategy safety call anchor not found")

    if NEW_FUNCTION in content:
        changes.append("answer strategy safety function already patched")
    elif OLD_FUNCTION in content:
        content = content.replace(OLD_FUNCTION, NEW_FUNCTION, 1)
        changes.append("patched answer strategy safety function")
    else:
        errors.append("answer strategy safety function anchor not found")

    if content != original and not errors:
        WORKFLOW_FILE.write_text(content, encoding="utf-8")

    pprint({"changes": changes, "errors": errors})
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())