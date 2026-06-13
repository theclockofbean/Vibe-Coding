# ruff: noqa: E402,I001
"""Check UnifiedIntentRouter."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.routers import UnifiedIntentRouter


@dataclass(frozen=True)
class UnifiedIntentRouterCheckCase:
    """One unified intent router check case."""

    text: str
    expected_status: str
    expected_selected_module: str | None
    expected_candidate_modules: tuple[str, ...]
    expected_signal_fragments: tuple[str, ...] = ()
    min_confidence: float = 0.0


def build_cases() -> list[UnifiedIntentRouterCheckCase]:
    """Return deterministic unified intent router check cases."""

    return [
        UnifiedIntentRouterCheckCase(
            text="SKU001 螺纹是多少",
            expected_status="routed",
            expected_selected_module="spec",
            expected_candidate_modules=("spec",),
            expected_signal_fragments=("螺纹",),
            min_confidence=0.7,
        ),
        UnifiedIntentRouterCheckCase(
            text="SKU001 多少钱",
            expected_status="routed",
            expected_selected_module="price",
            expected_candidate_modules=("price",),
            expected_signal_fragments=("多少钱",),
            min_confidence=0.7,
        ),
        UnifiedIntentRouterCheckCase(
            text="SKU001 几天发货",
            expected_status="routed",
            expected_selected_module="logistics",
            expected_candidate_modules=("logistics",),
            expected_signal_fragments=("几天发货",),
            min_confidence=0.7,
        ),
        UnifiedIntentRouterCheckCase(
            text="SKU001 会不会生锈",
            expected_status="routed",
            expected_selected_module="quality",
            expected_candidate_modules=("quality",),
            expected_signal_fragments=("生锈",),
            min_confidence=0.7,
        ),
        UnifiedIntentRouterCheckCase(
            text="SKU001 什么材质",
            expected_status="routed",
            expected_selected_module="spec",
            expected_candidate_modules=("spec",),
            expected_signal_fragments=("材质",),
            min_confidence=0.7,
        ),
        UnifiedIntentRouterCheckCase(
            text="SKU001 这个材质耐用吗",
            expected_status="routed",
            expected_selected_module="quality",
            expected_candidate_modules=("spec", "quality"),
            expected_signal_fragments=("材质", "耐用"),
            min_confidence=0.7,
        ),
        UnifiedIntentRouterCheckCase(
            text="SKU001 铝合金的多少钱",
            expected_status="routed",
            expected_selected_module="price",
            expected_candidate_modules=("price",),
            expected_signal_fragments=("多少钱",),
            min_confidence=0.7,
        ),
        UnifiedIntentRouterCheckCase(
            text="SKU001 铝合金款几天发货",
            expected_status="routed",
            expected_selected_module="logistics",
            expected_candidate_modules=("logistics",),
            expected_signal_fragments=("几天发货",),
            min_confidence=0.7,
        ),
        UnifiedIntentRouterCheckCase(
            text="SKU001 掉漆能退吗",
            expected_status="routed",
            expected_selected_module="quality",
            expected_candidate_modules=("quality",),
            expected_signal_fragments=("掉漆", "能退"),
            min_confidence=0.7,
        ),
        UnifiedIntentRouterCheckCase(
            text="SKU001 多少钱，几天发货，质量怎么样",
            expected_status="ambiguous",
            expected_selected_module=None,
            expected_candidate_modules=("price", "logistics", "quality"),
            expected_signal_fragments=("多少钱", "几天发货", "质量"),
        ),
        UnifiedIntentRouterCheckCase(
            text="你好",
            expected_status="unknown",
            expected_selected_module=None,
            expected_candidate_modules=(),
        ),
        UnifiedIntentRouterCheckCase(
            text="   ",
            expected_status="invalid_request",
            expected_selected_module=None,
            expected_candidate_modules=(),
        ),
        UnifiedIntentRouterCheckCase(
            text="质" * 501,
            expected_status="invalid_request",
            expected_selected_module=None,
            expected_candidate_modules=(),
        ),
    ]


def run_case(
    *,
    router: UnifiedIntentRouter,
    case: UnifiedIntentRouterCheckCase,
) -> bool:
    """Run one router check case."""

    print("=" * 80)
    print(f"text: {case.text[:80]}")

    result = router.route(case.text)
    payload = result.to_dict()
    pprint(payload)

    checks: list[tuple[str, object | None, object | None]] = [
        ("status", case.expected_status, result.status),
        (
            "selected_module",
            case.expected_selected_module,
            result.selected_module,
        ),
        (
            "candidate_modules",
            list(case.expected_candidate_modules),
            result.candidate_modules,
        ),
    ]

    for name, expected_value, actual_value in checks:
        if expected_value != actual_value:
            print(
                f"failed: {name} expected {expected_value!r}, "
                f"got {actual_value!r}"
            )
            return False

    if result.confidence < case.min_confidence:
        print(
            "failed: confidence expected >= "
            f"{case.min_confidence}, got {result.confidence}"
        )
        return False

    for signal_fragment in case.expected_signal_fragments:
        if not any(
            signal_fragment in signal
            for signal in result.matched_signals
        ):
            print(
                "failed: expected matched_signals to contain fragment "
                f"{signal_fragment!r}"
            )
            return False

    return True


def main() -> int:
    """Run unified intent router checks."""

    router = UnifiedIntentRouter()
    cases = build_cases()

    results = [
        run_case(
            router=router,
            case=case,
        )
        for case in cases
    ]

    print("=" * 80)

    if not all(results):
        print("unified intent router check failed")
        return 1

    print("unified intent router check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())