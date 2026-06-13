"""Check SpecAnswerRenderer.

This script reads products through the handler and renders controlled text.
It does not modify data.
"""

from __future__ import annotations

import sys
from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.handlers import SpecHandler, SpecHandlerInput  # noqa: E402
from app.agent.renderers import SpecAnswerRenderer  # noqa: E402
from app.core.database import get_session_factory  # noqa: E402
from app.repositories import ProductRepository  # noqa: E402
from app.services import SpecQueryService  # noqa: E402


def main() -> int:
    """Run renderer smoke checks."""

    session_factory = get_session_factory()

    with session_factory() as session:
        repository = ProductRepository(session)
        service = SpecQueryService(repository)
        handler = SpecHandler(service)
        renderer = SpecAnswerRenderer()

        sku_handler_result = handler.handle(
            SpecHandlerInput(
                query_type="sku_id",
                query_value="sku001",
            )
        )
        sku_answer = renderer.render(sku_handler_result)

        print("single sku answer:")
        print(sku_answer.text)
        pprint(sku_answer.to_dict())

        if "SKU001" not in sku_answer.text:
            print("failed: SKU001 answer should mention SKU001")
            return 1

        if "价格" in sku_answer.text:
            print("failed: spec renderer must not mention price")
            return 1

        thread_handler_result = handler.handle(
            SpecHandlerInput(
                query_type="thread_spec",
                query_value="M8x1.25",
                limit=3,
            )
        )
        thread_answer = renderer.render(thread_handler_result)

        print("\nmultiple products answer:")
        print(thread_answer.text)

        if "共查到 3 个匹配产品" not in thread_answer.text:
            print("failed: multiple products answer count mismatch")
            return 1

        missing_handler_result = handler.handle(
            SpecHandlerInput(
                query_type="sku_id",
                query_value="SKU999",
            )
        )
        missing_answer = renderer.render(missing_handler_result)

        print("\nmissing answer:")
        print(missing_answer.text)

        if "没有在当前产品资料中查到" not in missing_answer.text:
            print("failed: missing answer text mismatch")
            return 1

        invalid_handler_result = handler.handle(
            SpecHandlerInput(
                query_type="thread_dimensions",
                diameter_mm="abc",
                pitch_mm="1.25",
            )
        )
        invalid_answer = renderer.render(invalid_handler_result)

        print("\ninvalid answer:")
        print(invalid_answer.text)

        if "规格查询参数不完整或格式不正确" not in invalid_answer.text:
            print("failed: invalid answer text mismatch")
            return 1

    print("\nspec answer renderer check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())