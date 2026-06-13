"""Check QualityAnswerRenderer."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.handlers import QualityHandler  # noqa: E402
from app.agent.parsers import QualityParameterParser  # noqa: E402
from app.agent.renderers import QualityAnswerRenderer  # noqa: E402
from app.core.database import get_session_factory  # noqa: E402
from app.repositories import ProductRepository  # noqa: E402


@dataclass(frozen=True)
class QualityRendererCheckCase:
    """One renderer check case."""

    text: str
    expected_handler_status: str
    expected_handoff_required: bool
    expected_answer_fragments: tuple[str, ...]
    forbidden_answer_fragments: tuple[str, ...] = ()


def build_cases() -> list[QualityRendererCheckCase]:
    """Return deterministic renderer check cases."""

    return [
        QualityRendererCheckCase(
            text="SKU001 什么材质",
            expected_handler_status="success",
            expected_handoff_required=False,
            expected_answer_fragments=(
                "登记材质",
                "不代表额外质量承诺",
            ),
        ),
        QualityRendererCheckCase(
            text="SKU001 表面怎么处理",
            expected_handler_status="success",
            expected_handoff_required=False,
            expected_answer_fragments=(
                "登记表面处理",
                "不代表防锈、耐刮或不掉漆承诺",
            ),
        ),
        QualityRendererCheckCase(
            text="SKU001 耐用吗",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_answer_fragments=(
                "不能自动承诺产品寿命",
                "请转人工进一步确认",
            ),
            forbidden_answer_fragments=(
                "保证耐用",
                "能用几年",
            ),
        ),
        QualityRendererCheckCase(
            text="SKU001 会不会生锈",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_answer_fragments=(
                "不能自动承诺不生锈",
                "请转人工进一步确认",
            ),
            forbidden_answer_fragments=(
                "保证不生锈",
                "绝对不生锈",
            ),
        ),
        QualityRendererCheckCase(
            text="SKU001 会不会掉漆",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_answer_fragments=(
                "不能自动承诺不掉漆",
                "请转人工进一步确认",
            ),
            forbidden_answer_fragments=(
                "保证不掉漆",
                "绝对不掉漆",
            ),
        ),
        QualityRendererCheckCase(
            text="SKU001 质保多久",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_answer_fragments=(
                "不能自动承诺质保期限",
                "请转人工进一步确认",
            ),
            forbidden_answer_fragments=(
                "一年质保",
                "终身质保",
            ),
        ),
        QualityRendererCheckCase(
            text="SKU001 不合适能退吗",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_answer_fragments=(
                "不能自动承诺一定可退或一定可换",
                "请转人工进一步确认",
            ),
            forbidden_answer_fragments=(
                "一定能退",
                "一定能换",
            ),
        ),
        QualityRendererCheckCase(
            text="质量问题能赔吗",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_answer_fragments=(
                "缺少产品引用",
                "请先提供 SKU、OEM 对照号或螺纹规格",
            ),
            forbidden_answer_fragments=(
                "一定赔",
                "一定补发",
            ),
        ),
        QualityRendererCheckCase(
            text="SKU001 收到有划痕",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_answer_fragments=(
                "不能直接判断责任",
                "请提供订单、图片、视频和安装信息",
            ),
            forbidden_answer_fragments=(
                "一定赔",
                "一定补发",
            ),
        ),
        QualityRendererCheckCase(
            text="SKU999 什么材质",
            expected_handler_status="not_found",
            expected_handoff_required=True,
            expected_answer_fragments=(
                "暂未查到 SKU999 对应的质量基础信息",
                "请核对 SKU、OEM 对照号或螺纹规格",
            ),
        ),
        QualityRendererCheckCase(
            text="SKU001 和 SKU003 哪个质量更好",
            expected_handler_status="invalid_request",
            expected_handoff_required=False,
            expected_answer_fragments=(
                "识别到多个 SKU",
                "一次只能确认一个产品",
            ),
        ),
        QualityRendererCheckCase(
            text="SKU001 几天发货",
            expected_handler_status="invalid_request",
            expected_handoff_required=False,
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
    parser: QualityParameterParser,
    handler: QualityHandler,
    renderer: QualityAnswerRenderer,
    case: QualityRendererCheckCase,
) -> bool:
    """Run one renderer check case."""

    print("=" * 80)
    print(f"text: {case.text}")

    parsed_query = parser.parse(case.text)
    handler_result = handler.handle(parsed_query)
    rendered_answer = renderer.render(handler_result)

    pprint(handler_result.to_dict())
    print("answer_text:")
    print(rendered_answer.text)

    checks: list[tuple[str, object, object]] = [
        (
            "handler_status",
            case.expected_handler_status,
            handler_result.status,
        ),
        (
            "handoff_required",
            case.expected_handoff_required,
            rendered_answer.handoff_required,
        ),
    ]

    for name, expected_value, actual_value in checks:
        if expected_value != actual_value:
            print(
                f"failed: {name} expected {expected_value!r}, "
                f"got {actual_value!r}"
            )
            return False

    for fragment in case.expected_answer_fragments:
        if fragment not in rendered_answer.text:
            print(
                "failed: expected answer_text to contain "
                f"{fragment!r}"
            )
            return False

    for fragment in case.forbidden_answer_fragments:
        if fragment in rendered_answer.text:
            print(
                "failed: answer_text must not contain case forbidden fragment "
                f"{fragment!r}"
            )
            return False

    return assert_no_global_forbidden_fragments(rendered_answer.text)


def main() -> int:
    """Run quality answer renderer checks."""

    parser = QualityParameterParser()
    renderer = QualityAnswerRenderer()
    session_factory = get_session_factory()
    cases = build_cases()

    with session_factory() as session:
        product_repository = ProductRepository(session)
        handler = QualityHandler(product_repository=product_repository)

        results = [
            run_case(
                parser=parser,
                handler=handler,
                renderer=renderer,
                case=case,
            )
            for case in cases
        ]

    print("=" * 80)

    if not all(results):
        print("quality answer renderer check failed")
        return 1

    print("quality answer renderer check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())