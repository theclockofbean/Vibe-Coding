"""Demo LogisticsTextQAService with local database."""

from __future__ import annotations

import sys
from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.services import LogisticsTextQAService  # noqa: E402
from app.core.database import get_session_factory  # noqa: E402
from app.repositories import ProductRepository  # noqa: E402

DEMO_TEXTS: Final[tuple[str, ...]] = (
    "SKU001 几天发货",
    "SKU001 有现货吗",
    "SKU001 运费多少",
    "SKU001 包邮吗",
    "SKU001 发到杭州几天",
    "SKU001 发什么快递",
    "SKU001 能加急吗",
    "物流单号呢",
    "几天发货",
    "SKU999 几天发货",
    "SKU001 和 SKU003 分别几天发货",
    "SKU001 多少钱",
)


def main() -> int:
    """Run logistics text QA demo."""

    session_factory = get_session_factory()

    with session_factory() as session:
        product_repository = ProductRepository(session)
        service = LogisticsTextQAService(
            product_repository=product_repository,
        )

        for text in DEMO_TEXTS:
            print("=" * 80)
            print(f"用户：{text}")

            result = service.answer(text=text)
            payload = result.to_response_payload()

            print("回答：")
            print(payload["answer_text"])
            print("结构化结果：")
            pprint(payload)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())