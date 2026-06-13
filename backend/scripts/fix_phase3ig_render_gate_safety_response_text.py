"""Fix answer strategy render gate safety response wording."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
WORKFLOW_FILE: Final[Path] = BACKEND_ROOT / "app/agent/workflow.py"


def main() -> int:
    """Patch generic safety response text."""

    print("=" * 80)
    print("fixing answer strategy render gate safety response text")

    if not WORKFLOW_FILE.exists():
        pprint({"error": f"missing workflow file: {WORKFLOW_FILE}"})
        return 1

    content = WORKFLOW_FILE.read_text(encoding="utf-8")
    original = content

    old_text = '''    return (
        "该问题涉及需要进一步确认的信息。"
        "为避免给出未经授权的业务承诺，请转人工结合正式数据和业务规则处理。"
    )
'''

    new_text = '''    return (
        "该问题涉及需要进一步确认的信息，不能直接给出确定性答复。"
        "为避免给出未经授权的业务承诺，请转人工结合正式数据和业务规则处理。"
    )
'''

    if old_text not in content:
        pprint({"error": "generic safety response anchor not found"})
        return 1

    content = content.replace(old_text, new_text, 1)

    if content == original:
        pprint(
            {
                "workflow_file": str(WORKFLOW_FILE),
                "changed": False,
                "message": "already patched",
            }
        )
        return 0

    WORKFLOW_FILE.write_text(content, encoding="utf-8")

    pprint(
        {
            "workflow_file": str(WORKFLOW_FILE),
            "changed": True,
            "fix": "generic safety response now includes deterministic-answer refusal phrase",
        }
    )

    print("answer strategy render gate safety response text fixed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())