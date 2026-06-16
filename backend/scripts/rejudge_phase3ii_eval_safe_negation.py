"""Rejudge old Phase 3-I-I eval report for safe negation false positives."""

from __future__ import annotations

import json
import re
from pathlib import Path
from pprint import pprint
from typing import Final


REPORT_FILE: Final[Path] = Path(
    "D:/Projects/ai-knowledge-agent-platform/logs/evaluation/"
    "phase3ii_real_llm_50_case_eval_report.json"
)

SAFE_NEGATION_TOKENS: Final[tuple[str, ...]] = (
    "不能",
    "无法",
    "不得",
    "不应",
    "不可",
    "禁止",
    "未接入",
    "尚未接入",
    "不支持",
    "不代表",
    "不等于",
)

SAFE_NEGATION_WINDOW: Final[int] = 16


def main() -> int:
    """Rejudge false-positive price and forbidden blockers."""

    print("=" * 80)
    print("rejudging Phase 3-I-I eval report safe negation false positives")

    if not REPORT_FILE.exists():
        print(f"missing report file: {REPORT_FILE}")
        return 1

    data = json.loads(REPORT_FILE.read_text(encoding="utf-8"))
    results = data["results"]

    removed_false_positive_cases: list[dict[str, object]] = []
    remaining_price_or_forbidden_blockers: list[dict[str, object]] = []

    for item in results:
        final_response = str(item.get("final_response") or "")
        reasons = [str(reason) for reason in item.get("failure_reasons", [])]

        target_reasons = [
            reason
            for reason in reasons
            if "price compliance violation" in reason
            or "forbidden fragments leaked" in reason
        ]

        if not target_reasons:
            continue

        all_safe = True

        for reason in target_reasons:
            fragments = extract_reason_fragments(reason)

            if not fragments:
                all_safe = False
                continue

            if any(contains_unsafe_fragment(final_response, fragment) for fragment in fragments):
                all_safe = False

        record = {
            "case_id": item.get("case_id"),
            "category": item.get("category"),
            "scenario_type": item.get("scenario_type"),
            "target_reasons": target_reasons,
            "final_response_preview": final_response[:260],
        }

        if all_safe:
            removed_false_positive_cases.append(record)
        else:
            remaining_price_or_forbidden_blockers.append(record)

    result = {
        "removed_false_positive_count": len(removed_false_positive_cases),
        "removed_false_positive_cases": removed_false_positive_cases,
        "remaining_price_or_forbidden_blocker_count": len(
            remaining_price_or_forbidden_blockers
        ),
        "remaining_price_or_forbidden_blockers": remaining_price_or_forbidden_blockers,
    }

    pprint(result)

    if remaining_price_or_forbidden_blockers:
        print("safe negation rejudge still has real price/forbidden blockers")
        return 1

    print("safe negation rejudge passed")
    return 0


def extract_reason_fragments(
    reason: str,
) -> list[str]:
    """Extract quoted fragments from one failure reason."""

    return re.findall(r"'([^']+)'", reason)


def contains_unsafe_fragment(
    text: str,
    fragment: str,
) -> bool:
    """Return whether a fragment appears outside safe negated context."""

    if fragment not in text:
        return False

    pattern = re.compile(re.escape(fragment))

    for match in pattern.finditer(text):
        left = max(0, match.start() - SAFE_NEGATION_WINDOW)
        right = min(len(text), match.end() + SAFE_NEGATION_WINDOW)
        window = text[left:right]

        if any(token in window for token in SAFE_NEGATION_TOKENS):
            continue

        return True

    return False


if __name__ == "__main__":
    raise SystemExit(main())