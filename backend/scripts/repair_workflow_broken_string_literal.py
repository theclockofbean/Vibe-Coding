"""Repair broken string literal in workflow.py."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


WORKFLOW_FILE = Path("app/agent/workflow.py")


def repair_broken_string_literal() -> None:
    """Repair broken answer_text string literals."""

    content = WORKFLOW_FILE.read_text(encoding="utf-8")
    backup_file = WORKFLOW_FILE.with_name(
        f"workflow.before_string_repair_{datetime.now():%Y%m%d_%H%M%S}.py"
    )
    backup_file.write_text(content, encoding="utf-8")

    lines = content.splitlines()
    repaired_count = 0
    fixed_lines: list[str] = []

    for line in lines:
        stripped = line.strip()

        if (
            'next_state["answer_text"] =' in line
            and (
                line.count('"') % 2 != 0
                or "绯荤粺" in line
                or "异常" in line
            )
        ):
            indent = line[: len(line) - len(line.lstrip())]
            fixed_lines.append(
                indent
                + 'next_state["answer_text"] = '
                + '"系统处理当前问题时发生异常，请转人工确认。"'
            )
            repaired_count += 1
            continue

        fixed_lines.append(line)

    WORKFLOW_FILE.write_text("\n".join(fixed_lines) + "\n", encoding="utf-8")

    print(f"backup={backup_file}")
    print(f"repaired_count={repaired_count}")


if __name__ == "__main__":
    repair_broken_string_literal()