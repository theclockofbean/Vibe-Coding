"""Restore answer strategy helper functions removed by a broad replacement."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint

WORKFLOW_FILE = Path("app/agent/workflow.py")


HELPERS = '''

def _as_dict(value: Any) -> dict[str, Any]:
    """Return value as a dictionary when possible."""

    if isinstance(value, dict):
        return dict(value)

    return {}


def _optional_text(value: Any) -> str | None:
    """Return stripped text or None."""

    if isinstance(value, str) and value.strip():
        return value.strip()

    return None


def _merge_text_lists(
    left: list[str],
    right: list[str],
) -> list[str]:
    """Merge text lists while preserving order."""

    merged: list[str] = []

    for item in [*left, *right]:
        if item and item not in merged:
            merged.append(item)

    return merged


def _answer_strategy_split_response(metadata: dict[str, Any]) -> str:
    """Build answer strategy split response."""

    candidate_modules = _as_text_list(metadata.get("answer_candidate_modules"))

    if candidate_modules:
        modules_text = "、".join(candidate_modules)
        return (
            "这个问题同时涉及多个业务模块，不能合并成一个确定性答复。"
            f"当前识别到的候选模块包括：{modules_text}。"
            "请拆分为规格、价格、物流或质量等单独问题后再处理。"
        )

    return (
        "这个问题同时涉及多个业务边界，不能合并成一个确定性答复。"
        "请拆分为规格、价格、物流或质量等单独问题后再处理。"
    )


def _append_answer_strategy_boundary_notes(
    *,
    final_response: str,
    boundary_notes: list[str],
) -> str:
    """Append answer strategy boundary notes."""

    clean_notes = [note for note in boundary_notes if note]

    if not clean_notes:
        return final_response

    notes_text = "；".join(clean_notes)
    boundary_text = f"补充边界：{notes_text}"

    if boundary_text in final_response:
        return final_response

    return f"{final_response}\\n\\n{boundary_text}"
'''


def main() -> int:
    content = WORKFLOW_FILE.read_text(encoding="utf-8")
    changes: list[str] = []
    errors: list[str] = []

    if "def _as_dict(" in content:
        changes.append("missing helpers already restored")
    else:
        content = content.rstrip() + HELPERS + "\n"
        WORKFLOW_FILE.write_text(content, encoding="utf-8")
        changes.append("restored missing answer strategy helpers")

    pprint({"changes": changes, "errors": errors})
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())