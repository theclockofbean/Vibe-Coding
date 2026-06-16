"""Patch real LLM 50-case evaluation script to export detailed JSON report."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
CHECK_FILE: Final[Path] = (
    BACKEND_ROOT / "scripts/check_phase3ii_real_llm_50_case_eval.py"
)


def main() -> int:
    """Patch evaluation script with JSON report export."""

    print("=" * 80)
    print("patching Phase 3-I-I 50-case eval report export")

    if not CHECK_FILE.exists():
        pprint({"error": f"missing eval file: {CHECK_FILE}"})
        return 1

    content = CHECK_FILE.read_text(encoding="utf-8")
    original = content
    changes: list[str] = []

    if "import json" not in content:
        content = content.replace(
            "import os\n",
            "import json\nimport os\n",
            1,
        )
        changes.append("added json import")

    if "REPORT_DIR:" not in content:
        anchor = 'SHEET_NAME: Final[str] = "test_cases"\n'
        replacement = (
            'SHEET_NAME: Final[str] = "test_cases"\n'
            'REPORT_DIR: Final[Path] = PROJECT_ROOT / "logs/evaluation"\n'
            'REPORT_FILE: Final[Path] = REPORT_DIR / "phase3ii_real_llm_50_case_eval_report.json"\n'
        )

        if anchor not in content:
            pprint({"error": "report constants anchor not found"})
            return 1

        content = content.replace(anchor, replacement, 1)
        changes.append("added report path constants")

    old_summary_block = '''    summary = build_summary(results=results)
    pprint(summary)

    if summary["blocker_count"] > 0:
'''

    new_summary_block = '''    summary = build_summary(results=results)
    export_report(summary=summary, results=results)
    pprint(summary)

    if summary["blocker_count"] > 0:
'''

    if old_summary_block in content:
        content = content.replace(old_summary_block, new_summary_block, 1)
        changes.append("added export_report call")
    elif "export_report(summary=summary, results=results)" in content:
        changes.append("export_report call already exists")
    else:
        pprint({"error": "summary export anchor not found"})
        return 1

    helper_block = '''
def export_report(
    *,
    summary: dict[str, Any],
    results: list[dict[str, Any]],
) -> None:
    """Export detailed evaluation report."""

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    report = {
        "summary": summary,
        "results": results,
    }

    REPORT_FILE.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"evaluation report exported: {REPORT_FILE}")
'''

    if "def export_report(" not in content:
        insert_anchor = "\ndef print_case_summary(\n"

        if insert_anchor not in content:
            pprint({"error": "export_report insertion anchor not found"})
            return 1

        content = content.replace(
            insert_anchor,
            "\n" + helper_block.strip() + "\n\n\n" + "def print_case_summary(\n",
            1,
        )
        changes.append("inserted export_report helper")
    else:
        changes.append("export_report helper already exists")

    if content != original:
        CHECK_FILE.write_text(content, encoding="utf-8")

    pprint(
        {
            "check_file": str(CHECK_FILE),
            "changed": content != original,
            "changes": changes,
        }
    )

    print("Phase 3-I-I 50-case eval report export patch completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())