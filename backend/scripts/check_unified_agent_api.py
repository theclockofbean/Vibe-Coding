# ruff: noqa: E402,I001
"""Check Unified Agent API.

This script verifies POST /api/v1/agent/query.

It does not call an LLM, promise prices, promise logistics, promise quality,
promise warranty, promise returns/exchanges, promise compensation, or write
data.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from pprint import pprint
from typing import Any, Final

from fastapi.testclient import TestClient

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app


REQUIRED_ROUTE: Final[str] = "/api/v1/agent/query"

COMMON_RESPONSE_KEYS: Final[tuple[str, ...]] = (
    "selected_module",
    "route_status",
    "route_confidence",
    "candidate_modules",
    "matched_signals",
    "parse_status",
    "handler_status",
    "answer_text",
    "handoff_required",
    "source_references",
    "module_payload",
    "warnings",
    "errors",
)


@dataclass(frozen=True)
class UnifiedAgentAPICase:
    """One unified agent API check case."""

    name: str
    text: str
    expected_selected_module: str | None
    expected_route_status: str
    expected_parse_status: str
    expected_handler_status: str
    expected_handoff_required: bool
    expected_module_payload_present: bool
    expected_answer_fragments: tuple[str, ...]
    forbidden_answer_fragments: tuple[str, ...] = ()


def build_cases() -> list[UnifiedAgentAPICase]:
    """Return deterministic unified agent API cases."""

    return [
        UnifiedAgentAPICase(
            name="spec_routed",
            text="SKU001 螺纹是多少",
            expected_selected_module="spec",
            expected_route_status="routed",
            expected_parse_status="parsed",
            expected_handler_status="success",
            expected_handoff_required=False,
            expected_module_payload_present=True,
            expected_answer_fragments=(
                "SKU001",
                "螺纹规格",
            ),
        ),
        UnifiedAgentAPICase(
            name="price_routed_handoff",
            text="SKU001 多少钱",
            expected_selected_module="price",
            expected_route_status="routed",
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_module_payload_present=True,
            expected_answer_fragments=(
                "SKU001",
                "不能直接给出报价",
                "转人工确认",
            ),
            forbidden_answer_fragments=(
                "保证最低价",
                "最低价给你",
            ),
        ),
        UnifiedAgentAPICase(
            name="logistics_routed",
            text="SKU001 几天发货",
            expected_selected_module="logistics",
            expected_route_status="routed",
            expected_parse_status="parsed",
            expected_handler_status="success",
            expected_handoff_required=False,
            expected_module_payload_present=True,
            expected_answer_fragments=(
                "SKU001",
                "发货周期",
                "不代表到货时间",
            ),
            forbidden_answer_fragments=(
                "保证到货",
                "今天一定发",
                "一定包邮",
            ),
        ),
        UnifiedAgentAPICase(
            name="quality_routed_handoff",
            text="SKU001 会不会生锈",
            expected_selected_module="quality",
            expected_route_status="routed",
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_module_payload_present=True,
            expected_answer_fragments=(
                "SKU001",
                "不能自动承诺不生锈",
            ),
            forbidden_answer_fragments=(
                "保证不生锈",
                "绝对不生锈",
            ),
        ),
        UnifiedAgentAPICase(
            name="material_routed_to_spec",
            text="SKU001 什么材质",
            expected_selected_module="spec",
            expected_route_status="routed",
            expected_parse_status="parsed",
            expected_handler_status="success",
            expected_handoff_required=False,
            expected_module_payload_present=True,
            expected_answer_fragments=(
                "SKU001",
                "材质",
            ),
        ),
        UnifiedAgentAPICase(
            name="ambiguous",
            text="SKU001 多少钱，几天发货，质量怎么样",
            expected_selected_module=None,
            expected_route_status="ambiguous",
            expected_parse_status="ambiguous",
            expected_handler_status="invalid_request",
            expected_handoff_required=False,
            expected_module_payload_present=False,
            expected_answer_fragments=(
                "识别到多个业务问题",
                "请拆分为规格、价格、物流或质量中的一个问题",
            ),
        ),
        UnifiedAgentAPICase(
            name="unknown",
            text="你好",
            expected_selected_module=None,
            expected_route_status="unknown",
            expected_parse_status="unknown",
            expected_handler_status="invalid_request",
            expected_handoff_required=False,
            expected_module_payload_present=False,
            expected_answer_fragments=(
                "当前未识别到可处理的业务问题",
            ),
        ),
    ]


def get_registered_route_paths() -> set[str]:
    """Return registered FastAPI route paths."""

    paths: set[str] = set()

    for route in app.routes:
        path = getattr(route, "path", None)

        if isinstance(path, str):
            paths.add(path)

    return paths


def check_route_registered() -> bool:
    """Check unified agent route is registered."""

    print("=" * 80)
    print("checking unified agent route registration")

    route_paths = get_registered_route_paths()

    if REQUIRED_ROUTE not in route_paths:
        print(f"failed: missing route {REQUIRED_ROUTE}")
        pprint(sorted(path for path in route_paths if path.startswith("/api/v1/")))
        return False

    print(f"route registered: {REQUIRED_ROUTE}")
    return True


def assert_common_response_shape(payload: dict[str, Any]) -> bool:
    """Check common response keys exist."""

    for key in COMMON_RESPONSE_KEYS:
        if key not in payload:
            print(f"failed: response missing key {key!r}")
            return False

    if not isinstance(payload["answer_text"], str) or not payload["answer_text"]:
        print("failed: answer_text must be a non-empty string")
        return False

    if not isinstance(payload["source_references"], list):
        print("failed: source_references must be a list")
        return False

    if not isinstance(payload["candidate_modules"], list):
        print("failed: candidate_modules must be a list")
        return False

    if not isinstance(payload["matched_signals"], list):
        print("failed: matched_signals must be a list")
        return False

    return True


def assert_no_global_forbidden_fragments(answer_text: str) -> bool:
    """Check answer text contains no unsupported business commitments."""

    forbidden_fragments = [
        "保证最低价",
        "一定包邮",
        "保证到货",
        "今天一定发",
        "保证不坏",
        "保证不生锈",
        "保证不掉漆",
        "一年质保",
        "终身质保",
        "七天无理由",
        "一定能退",
        "一定能换",
        "一定赔",
        "一定补发",
        "质量很好",
        "放心用",
        "完全没问题",
    ]

    for fragment in forbidden_fragments:
        if fragment in answer_text:
            print(
                "failed: answer_text must not contain forbidden fragment "
                f"{fragment!r}"
            )
            return False

    return True


def run_case(
    *,
    client: TestClient,
    case: UnifiedAgentAPICase,
) -> bool:
    """Run one unified agent API case."""

    print("=" * 80)
    print(f"case: {case.name}")
    print(f"text: {case.text}")

    response = client.post(
        REQUIRED_ROUTE,
        json={
            "text": case.text,
            "limit": 5,
        },
    )

    if response.status_code != 200:
        print(f"failed: expected HTTP 200, got {response.status_code}")
        print(response.text)
        return False

    payload = response.json()
    pprint(payload)

    if not assert_common_response_shape(payload):
        return False

    checks: list[tuple[str, object | None, object | None]] = [
        (
            "selected_module",
            case.expected_selected_module,
            payload["selected_module"],
        ),
        ("route_status", case.expected_route_status, payload["route_status"]),
        ("parse_status", case.expected_parse_status, payload["parse_status"]),
        (
            "handler_status",
            case.expected_handler_status,
            payload["handler_status"],
        ),
        (
            "handoff_required",
            case.expected_handoff_required,
            payload["handoff_required"],
        ),
    ]

    for name, expected_value, actual_value in checks:
        if expected_value != actual_value:
            print(
                f"failed: {name} expected {expected_value!r}, "
                f"got {actual_value!r}"
            )
            return False

    module_payload = payload["module_payload"]

    if case.expected_module_payload_present and not isinstance(module_payload, dict):
        print("failed: module_payload expected to be a dict")
        return False

    if not case.expected_module_payload_present and module_payload is not None:
        print("failed: module_payload expected to be None")
        return False

    answer_text = str(payload["answer_text"])

    for fragment in case.expected_answer_fragments:
        if fragment not in answer_text:
            print(
                "failed: expected answer_text to contain "
                f"{fragment!r}"
            )
            return False

    for fragment in case.forbidden_answer_fragments:
        if fragment in answer_text:
            print(
                "failed: answer_text must not contain case forbidden fragment "
                f"{fragment!r}"
            )
            return False

    return assert_no_global_forbidden_fragments(answer_text)


def main() -> int:
    """Run unified agent API checks."""

    client = TestClient(app)

    route_result = check_route_registered()

    case_results = [
        run_case(
            client=client,
            case=case,
        )
        for case in build_cases()
    ]

    print("=" * 80)

    if not all([route_result, *case_results]):
        print("unified agent API check failed")
        return 1

    print("unified agent API check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())