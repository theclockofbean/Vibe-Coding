"""Demo QualityTextQAService with local database."""

from __future__ import annotations

import sys
from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.services import QualityTextQAService  # noqa: E402
from app.core.database import get_session_factory  # noqa: E402
from app.repositories import ProductRepository  # noqa: E402

DEMO_TEXTS: Final[tuple[str, ...]] = (
    "SKU001 什么材质",
    "SKU001 表面怎么处理",
    "SKU001 耐用吗",
    "SKU001 会不会生锈",
    "SKU001 会不会掉漆",
    "SKU001 质保多久",
    "SKU001 不合适能退吗",
    "质量问题能赔吗",
    "SKU001 收到有划痕",
    "SKU999 什么材质",
    "SKU001 和 SKU003 哪个质量更好",
    "SKU001 几天发货",
)


def main() -> int:
    """Run quality text QA demo."""

    session_factory = get_session_factory()

    with session_factory() as session:
        product_repository = ProductRepository(session)
        service = QualityTextQAService(
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