"""Force add real import os line to workflow.py."""

from __future__ import annotations

from pathlib import Path

WORKFLOW_FILE = Path("app/agent/workflow.py")


def main() -> int:
    """Force add import os after future import if missing as a real import line."""

    lines = WORKFLOW_FILE.read_text(encoding="utf-8").splitlines()

    if any(line.strip() == "import os" for line in lines):
        print("workflow.py already has real import os line")
        return 0

    insert_index = 0

    for index, line in enumerate(lines):
        if line.strip() == "from __future__ import annotations":
            insert_index = index + 1
            break

    lines.insert(insert_index, "import os")

    WORKFLOW_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("workflow.py real import os inserted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())