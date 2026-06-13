# ruff: noqa: E402,I001
"""Check HandoffTicketRepository."""

from __future__ import annotations

import sys
from pathlib import Path
from pprint import pprint
from typing import Final
from uuid import uuid4

from sqlalchemy import text

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import get_session_factory
from app.repositories.handoff_ticket_repository import (
    HandoffTicketCreate,
    HandoffTicketRepository,
)


TEST_TICKET_PREFIX: Final[str] = "HT-REPO-"


def cleanup_test_tickets() -> None:
    """Delete repository test tickets."""

    session_factory = get_session_factory()

    with session_factory() as session:
        with session.begin():
            session.execute(
                text(
                    """
                    DELETE FROM handoff_tickets
                    WHERE ticket_no LIKE :ticket_no_prefix;
                    """
                ),
                {
                    "ticket_no_prefix": f"{TEST_TICKET_PREFIX}%",
                },
            )


def make_ticket_no() -> str:
    """Create unique test ticket number."""

    return f"{TEST_TICKET_PREFIX}{uuid4().hex[:12].upper()}"


def run_repository_checks() -> bool:
    """Run repository checks."""

    session_factory = get_session_factory()

    with session_factory() as session:
        repository = HandoffTicketRepository(session)

        with session.begin():
            price_ticket = repository.create(
                HandoffTicketCreate(
                    ticket_no=make_ticket_no(),
                    user_text="SKU001 多少钱",
                    selected_module="price",
                    route_status="routed",
                    route_confidence=0.75,
                    candidate_modules=["price"],
                    matched_signals=["多少钱"],
                    parse_status="parsed",
                    handler_status="handoff",
                    handoff_reason=(
                        "当前系统未接入正式价格表，不能自动报价，需人工确认。"
                    ),
                    answer_text=(
                        "当前系统尚未接入正式价格表，不能直接给出报价。"
                    ),
                    source_references=[],
                    module_payload={
                        "selected_module": "price",
                        "handler_status": "handoff",
                    },
                    risk_reasons=["price_without_price_table"],
                )
            )

            quality_ticket = repository.create(
                HandoffTicketCreate(
                    ticket_no=make_ticket_no(),
                    user_text="SKU001 会不会生锈",
                    selected_module="quality",
                    route_status="routed",
                    route_confidence=0.75,
                    candidate_modules=["quality"],
                    matched_signals=["生锈"],
                    parse_status="parsed",
                    handler_status="handoff",
                    handoff_reason=(
                        "该质量问题涉及质量表现、售后责任、质保、退换或赔付，"
                        "需人工确认。"
                    ),
                    answer_text=(
                        "当前系统不能自动承诺不生锈或绝对防锈，请转人工进一步确认。"
                    ),
                    source_references=[
                        {
                            "source_type": "database_table",
                            "source_name": "products",
                            "reference_id": "SKU001",
                        }
                    ],
                    module_payload={
                        "selected_module": "quality",
                        "handler_status": "handoff",
                    },
                    risk_reasons=["quality_commitment_required"],
                )
            )

            resolved_ticket = repository.create(
                HandoffTicketCreate(
                    ticket_no=make_ticket_no(),
                    user_text="SKU001 运费多少",
                    status="resolved",
                    selected_module="logistics",
                    route_status="routed",
                    route_confidence=0.75,
                    candidate_modules=["logistics"],
                    matched_signals=["运费"],
                    parse_status="parsed",
                    handler_status="handoff",
                    handoff_reason=(
                        "该物流问题涉及运费、包邮、到货时间、承运商或加急承诺，"
                        "需人工确认。"
                    ),
                    answer_text="运费问题需转人工进一步确认。",
                    source_references=[],
                    module_payload={
                        "selected_module": "logistics",
                        "handler_status": "handoff",
                    },
                    risk_reasons=["logistics_commitment_required"],
                )
            )

            print("=" * 80)
            print("created tickets")
            pprint(
                [
                    price_ticket.to_dict(),
                    quality_ticket.to_dict(),
                    resolved_ticket.to_dict(),
                ]
            )

            checks: list[bool] = []

            open_tickets = repository.list_tickets(
                status="open",
                limit=20,
                offset=0,
            )
            print("=" * 80)
            print("open tickets")
            pprint([ticket.to_dict() for ticket in open_tickets])

            checks.append(
                any(ticket.ticket_no == price_ticket.ticket_no for ticket in open_tickets)
            )
            checks.append(
                any(ticket.ticket_no == quality_ticket.ticket_no for ticket in open_tickets)
            )
            checks.append(
                not any(
                    ticket.ticket_no == resolved_ticket.ticket_no
                    for ticket in open_tickets
                )
            )

            quality_tickets = repository.list_tickets(
                selected_module="quality",
                limit=20,
                offset=0,
            )
            print("=" * 80)
            print("quality tickets")
            pprint([ticket.to_dict() for ticket in quality_tickets])

            checks.append(
                any(
                    ticket.ticket_no == quality_ticket.ticket_no
                    for ticket in quality_tickets
                )
            )

            open_count = repository.count_tickets(status="open")
            quality_count = repository.count_tickets(selected_module="quality")

            print("=" * 80)
            print(f"open_count={open_count}")
            print(f"quality_count={quality_count}")

            checks.append(open_count >= 2)
            checks.append(quality_count >= 1)

            paged_tickets = repository.list_tickets(
                limit=1,
                offset=0,
            )
            print("=" * 80)
            print("paged tickets")
            pprint([ticket.to_dict() for ticket in paged_tickets])

            checks.append(len(paged_tickets) == 1)

        return all(checks)


def main() -> int:
    """Run HandoffTicketRepository checks."""

    cleanup_test_tickets()

    try:
        passed = run_repository_checks()
    finally:
        cleanup_test_tickets()

    print("=" * 80)

    if not passed:
        print("handoff ticket repository check failed")
        return 1

    print("handoff ticket repository check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())