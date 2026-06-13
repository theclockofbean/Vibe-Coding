"""Repair indentation of Logistics KB hook in workflow.py."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

WORKFLOW_FILE = Path("app/agent/workflow.py")


def main() -> int:
    """Repair wrongly indented Logistics KB hook."""

    content = WORKFLOW_FILE.read_text(encoding="utf-8")
    backup_file = WORKFLOW_FILE.with_name(
        f"workflow.before_logistics_indent_repair_{datetime.now():%Y%m%d_%H%M%S}.py"
    )
    backup_file.write_text(content, encoding="utf-8")

    lines = content.splitlines()

    start_index = find_line(
        lines,
        "new_state = cast(AgentState, quality_state)",
    )
    end_index = find_line_after(
        lines,
        start_index,
        "new_state = cast(AgentState, logistics_state)",
    )

    if start_index < 0 or end_index < 0:
        raise RuntimeError("Logistics hook block not found")

    next_code_index = find_next_non_empty_line(lines, end_index + 1)

    if next_code_index < 0:
        raise RuntimeError("Cannot infer target indentation after Logistics hook")

    target_indent = get_indent(lines[next_code_index])

    repaired_block = [
        f"{target_indent}new_state = cast(AgentState, quality_state)",
        (
            f"{target_indent}logistics_state, real_logistics_kb_used = "
            "_try_real_logistics_kb_retrieval(dict(new_state))"
        ),
        f"{target_indent}if real_logistics_kb_used:",
        f"{target_indent}    return cast(AgentState, logistics_state)",
        f"{target_indent}new_state = cast(AgentState, logistics_state)",
    ]

    new_lines = lines[:start_index] + repaired_block + lines[end_index + 1 :]

    WORKFLOW_FILE.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    print(f"backup={backup_file}")
    print(f"target_indent_width={len(target_indent)}")
    print("workflow.py Logistics hook indentation repaired")
    return 0


def find_line(
    lines: list[str],
    stripped_text: str,
) -> int:
    """Find first line by stripped text."""

    for index, line in enumerate(lines):
        if line.strip() == stripped_text:
            return index

    return -1


def find_line_after(
    lines: list[str],
    start_index: int,
    stripped_text: str,
) -> int:
    """Find line after start index by stripped text."""

    for index in range(start_index + 1, len(lines)):
        if lines[index].strip() == stripped_text:
            return index

    return -1


def find_next_non_empty_line(
    lines: list[str],
    start_index: int,
) -> int:
    """Find next non-empty line."""

    for index in range(start_index, len(lines)):
        if lines[index].strip():
            return index

    return -1


def get_indent(
    line: str,
) -> str:
    """Return leading indentation."""

    return line[: len(line) - len(line.lstrip())]


if __name__ == "__main__":
    raise SystemExit(main())