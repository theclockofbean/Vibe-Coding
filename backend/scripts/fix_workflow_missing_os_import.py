"""Fix missing os import in workflow.py."""

from __future__ import annotations

from pathlib import Path

WORKFLOW_FILE = Path("app/agent/workflow.py")


def main() -> int:
    """Add import os if missing."""

    content = WORKFLOW_FILE.read_text(encoding="utf-8")

    if "import os\n" in content:
        print("workflow.py already imports os")
        return 0

    if "from __future__ import annotations\n\n" in content:
        content = content.replace(
            "from __future__ import annotations\n\n",
            "from __future__ import annotations\n\nimport os\n",
            1,
        )
    else:
        content = "import os\n" + content

    WORKFLOW_FILE.write_text(content, encoding="utf-8")

    print("workflow.py missing os import fixed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())