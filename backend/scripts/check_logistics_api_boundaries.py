"""Check Logistics API boundary cases."""

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

from app.main import app  # noqa: E402


@dataclass(frozen=True)
class LogisticsAPIBoundaryCase:
    """One logistics API boundary case."""

    name: str
    body: dict[str, Any]
    expected_status_code: int
    expected_payload_values: dict[str, object] | None = None
    expected_answer_fragments: tuple[str, ...] = ()


def build_cases() -> list[LogisticsAPIBoundaryCase]:
    """Return API boundary cases."""

    return [
        LogisticsAPIBoundaryCase(
            name="empty text",
            body={"text": "", "limit": 5},
            expected_status_code=422,
        ),
        LogisticsAPIBoundaryCase(
            name="blank text",
            body={"text": "   ", "limit": 5},
            expected_status_code=200,
            expected_payload_values={
                "parse_status": "not_logistics_intent",
                "handler_status": "invalid_request",
                "handoff_required": False,
            },
            expected_answer_fragments=(
                "当前未识别为物流问题",
            ),
        ),
        LogisticsAPIBoundaryCase(
            name="missing text",
            body={"limit": 5},
            expected_status_code=422,
        ),
        LogisticsAPIBoundaryCase(
            name="too long text",
            body={"text": "S" * 501, "limit": 5},
            expected_status_code=422,
        ),
        LogisticsAPIBoundaryCase(
            name="limit less than 1",
            body={"text": "SKU001 几天发货", "limit": 0},
            expected_status_code=422,
        ),
        LogisticsAPIBoundaryCase(
            name="limit greater than 20",
            body={"text": "SKU001 几天发货", "limit": 21},
            expected_status_code=422,
        ),
        LogisticsAPIBoundaryCase(
            name="multiple sku",
            body={"text": "SKU001 和 SKU003 分别几天发货", "limit": 5},
            expected_status_code=200,
            expected_payload_values={
                "parse_status": "ambiguous",
                "handler_status": "invalid_request",
                "handoff_required": False,
            },
            expected_answer_fragments=(
                "识别到多个 SKU",
            ),
        ),
        LogisticsAPIBoundaryCase(
            name="multiple oem",
            body={"text": "43330-39585 和 12345-67890 运费多少", "limit": 5},
            expected_status_code=200,
            expected_payload_values={
                "parse_status": "ambiguous",
                "handler_status": "invalid_request",
                "handoff_required": False,
            },
            expected_answer_fragments=(
                "识别到多个 OEM 对照号",
            ),
        ),
        LogisticsAPIBoundaryCase(
            name="multiple thread specs",
            body={"text": "M8x1.25 和 M10x1.5 几天发货", "limit": 5},
            expected_status_code=200,
            expected_payload_values={
                "parse_status": "ambiguous",
                "handler_status": "invalid_request",
                "handoff_required": False,
            },
            expected_answer_fragments=(
                "识别到多个螺纹规格",
            ),
        ),
        LogisticsAPIBoundaryCase(
            name="missing product reference",
            body={"text": "几天发货", "limit": 5},
            expected_status_code=200,
            expected_payload_values={
                "parse_status": "missing_product_reference",
                "handler_status": "handoff",
                "handoff_required": True,
            },
            expected_answer_fragments=(
                "请先提供 SKU、OEM 对照号或螺纹规格",
            ),
        ),
        LogisticsAPIBoundaryCase(
            name="not logistics intent",
            body={"text": "SKU001 多少钱", "limit": 5},
            expected_status_code=200,
            expected_payload_values={
                "parse_status": "not_logistics_intent",
                "handler_status": "invalid_request",
                "handoff_required": False,
            },
            expected_answer_fragments=(
                "当前未识别为物流问题",
            ),
        ),
        LogisticsAPIBoundaryCase(
            name="product not found",
            body={"text": "SKU999 几天发货", "limit": 5},
            expected_status_code=200,
            expected_payload_values={
                "parse_status": "parsed",
                "handler_status": "not_found",
                "handoff_required": True,
            },
            expected_answer_fragments=(
                "暂未查到 SKU999 对应的物流基础信息",
            ),
        ),
    ]


def run_case(
    *,
    client: TestClient,
    case: LogisticsAPIBoundaryCase,
) -> bool:
    """Run one boundary case."""

    print("=" * 80)
    print(f"case: {case.name}")

    response = client.post(
        "/api/v1/logistics/query",
        json=case.body,
    )

    print(f"status_code: {response.status_code}")

    if response.status_code != case.expected_status_code:
        print(
            "failed: expected status_code "
            f"{case.expected_status_code}, got {response.status_code}"
        )
        print(response.text)
        return False

    if case.expected_status_code == 422:
        return True

    payload = response.json()
    pprint(payload)

    if case.expected_payload_values is not None:
        for key, expected_value in case.expected_payload_values.items():
            actual_value = payload.get(key)
            if actual_value != expected_value:
                print(
                    f"failed: payload[{key!r}] expected "
                    f"{expected_value!r}, got {actual_value!r}"
                )
                return False

    answer_text = str(payload.get("answer_text", ""))

    for fragment in case.expected_answer_fragments:
        if fragment not in answer_text:
            print(
                "failed: expected answer_text to contain "
                f"{fragment!r}"
            )
            return False

    return True


def main() -> int:
    """Run logistics API boundary checks."""

    client = TestClient(app)
    cases = build_cases()

    results = [
        run_case(
            client=client,
            case=case,
        )
        for case in cases
    ]

    print("=" * 80)

    if not all(results):
        print("logistics API boundary check failed")
        return 1

    print("logistics API boundary check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())