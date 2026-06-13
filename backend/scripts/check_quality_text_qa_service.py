"""Check QualityTextQAService.

This script verifies the full local quality text QA chain:
parser -> handler -> renderer -> response payload.

It does not call an LLM, promise durability, promise rust resistance, promise
scratch resistance, promise warranty, promise returns/exchanges, promise
compensation, judge quality responsibility, or write data.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.services import QualityTextQAService  # noqa: E402
from app.core.database import get_session_factory  # noqa: E402
from app.repositories import ProductRepository  # noqa: E402


@dataclass(frozen=True)
class QualityTextQACheckCase:
    """One quality text QA service check case."""

    text: str
    expected_parse_status: str
    expected_handler_status: str
    expected_handoff_required: bool
    expected_answer_fragments: tuple[str, ...]
    expected_query_type: str | None = None
    forbidden_answer_fragments: tuple[str, ...] = ()


def build_cases() -> list[QualityTextQACheckCase]:
    """Return deterministic text QA service check cases."""

    return [
        QualityTextQACheckCase(
            text="SKU001 什么材质",
            expected_parse_status="parsed",
            expected_handler_status="success",
            expected_handoff_required=False,
            expected_query_type="material",
            expected_answer_fragments=(
                "登记材质",
                "不代表额外质量承诺",
            ),
        ),
        QualityTextQACheckCase(
            text="SKU001 表面怎么处理",
            expected_parse_status="parsed",
            expected_handler_status="success",
            expected_handoff_required=False,
            expected_query_type="surface_treatment",
            expected_answer_fragments=(
                "登记表面处理",
                "不代表防锈、耐刮或不掉漆承诺",
            ),
        ),
        QualityTextQACheckCase(
            text="SKU001 耐用吗",
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_query_type="durability",
            expected_answer_fragments=(
                "不能自动承诺产品寿命",
                "请转人工进一步确认",
            ),
            forbidden_answer_fragments=(
                "保证耐用",
                "能用几年",
            ),
        ),
        QualityTextQACheckCase(
            text="SKU001 会不会生锈",
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_query_type="rust_resistance",
            expected_answer_fragments=(
                "不能自动承诺不生锈",
                "请转人工进一步确认",
            ),
            forbidden_answer_fragments=(
                "保证不生锈",
                "绝对不生锈",
            ),
        ),
        QualityTextQACheckCase(
            text="SKU001 会不会掉漆",
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_query_type="scratch_resistance",
            expected_answer_fragments=(
                "不能自动承诺不掉漆",
                "请转人工进一步确认",
            ),
            forbidden_answer_fragments=(
                "保证不掉漆",
                "绝对不掉漆",
            ),
        ),
        QualityTextQACheckCase(
            text="SKU001 质保多久",
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_query_type="warranty",
            expected_answer_fragments=(
                "不能自动承诺质保期限",
                "请转人工进一步确认",
            ),
            forbidden_answer_fragments=(
                "一年质保",
                "终身质保",
            ),
        ),
        QualityTextQACheckCase(
            text="SKU001 不合适能退吗",
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_query_type="return_exchange",
            expected_answer_fragments=(
                "不能自动承诺一定可退或一定可换",
                "请转人工进一步确认",
            ),
            forbidden_answer_fragments=(
                "一定能退",
                "一定能换",
            ),
        ),
        QualityTextQACheckCase(
            text="质量问题能赔吗",
            expected_parse_status="missing_product_reference",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_query_type="compensation",
            expected_answer_fragments=(
                "缺少产品引用",
                "请先提供 SKU、OEM 对照号或螺纹规格",
            ),
            forbidden_answer_fragments=(
                "一定赔",
                "一定补发",
            ),
        ),
        QualityTextQACheckCase(
            text="SKU001 收到有划痕",
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_query_type="defect_issue",
            expected_answer_fragments=(
                "不能直接判断责任",
                "请提供订单、图片、视频和安装信息",
            ),
            forbidden_answer_fragments=(
                "一定赔",
                "一定补发",
            ),
        ),
        QualityTextQACheckCase(
            text="SKU999 什么材质",
            expected_parse_status="parsed",
            expected_handler_status="not_found",
            expected_handoff_required=True,
            expected_query_type="material",
            expected_answer_fragments=(
                "暂未查到 SKU999 对应的质量基础信息",
                "请核对 SKU、OEM 对照号或螺纹规格",
            ),
        ),
        QualityTextQACheckCase(
            text="SKU001 和 SKU003 哪个质量更好",
            expected_parse_status="ambiguous",
            expected_handler_status="invalid_request",
            expected_handoff_required=False,
            expected_query_type="general_quality",
            expected_answer_fragments=(
                "识别到多个 SKU",
                "一次只能确认一个产品",
            ),
        ),
        QualityTextQACheckCase(
            text="SKU001 几天发货",
            expected_parse_status="not_quality_intent",
            expected_handler_status="invalid_request",
            expected_handoff_required=False,
            expected_query_type=None,
            expected_answer_fragments=(
                "当前未识别为质量问题",
            ),
        ),
    ]


def assert_no_global_forbidden_fragments(answer_text: str) -> bool:
    """Check answer text contains no unsupported quality commitments."""

    forbidden_fragments = [
        "绝对不会坏",
        "保证不会坏",
        "不会坏",
        "保证不生锈",
        "绝对不生锈",
        "保证不掉漆",
        "绝对不掉漆",
        "保证耐用",
        "保证耐用几年",
        "能用几年",
        "终身质保",
        "一年质保",
        "两年质保",
        "三年质保",
        "七天无理由",
        "一定能退",
        "一定能换",
        "一定赔",
        "一定补发",
        "质量问题一定赔",
        "装不上一定负责",
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
    service: QualityTextQAService,
    case: QualityTextQACheckCase,
) -> bool:
    """Run one service check case."""

    print("=" * 80)
    print(f"text: {case.text}")

    result = service.answer(text=case.text)
    payload = result.to_response_payload()

    pprint(payload)

    checks: list[tuple[str, object | None, object | None]] = [
        ("parse_status", case.expected_parse_status, payload["parse_status"]),
        ("handler_status", case.expected_handler_status, payload["handler_status"]),
        (
            "handoff_required",
            case.expected_handoff_required,
            payload["handoff_required"],
        ),
        (
            "quality_query_type",
            case.expected_query_type,
            payload["quality_query_type"],
        ),
    ]

    for name, expected_value, actual_value in checks:
        if expected_value != actual_value:
            print(
                f"failed: {name} expected {expected_value!r}, "
                f"got {actual_value!r}"
            )
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
    """Run quality text QA service checks."""

    session_factory = get_session_factory()
    cases = build_cases()

    with session_factory() as session:
        product_repository = ProductRepository(session)
        service = QualityTextQAService(
            product_repository=product_repository,
        )

        results = [
            run_case(
                service=service,
                case=case,
            )
            for case in cases
        ]

    print("=" * 80)

    if not all(results):
        print("quality text QA service check failed")
        return 1

    print("quality text QA service check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())