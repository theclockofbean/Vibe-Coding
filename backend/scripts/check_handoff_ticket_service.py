# ruff: noqa: E402,I001
"""Check HandoffTicketService."""

from __future__ import annotations

import sys
from pathlib import Path
from pprint import pprint
from typing import Final

from sqlalchemy import text

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.services import HandoffTicketService
from app.core.database import get_session_factory
from app.repositories.handoff_ticket_repository import HandoffTicketRepository


TEST_SOURCE_CHANNEL: Final[str] = "service_test"


def cleanup_test_tickets() -> None:
    """Delete service test tickets."""

    session_factory = get_session_factory()

    with session_factory() as session:
        with session.begin():
            session.execute(
                text(
                    """
                    DELETE FROM handoff_tickets
                    WHERE source_channel = :source_channel;
                    """
                ),
                {
                    "source_channel": TEST_SOURCE_CHANNEL,
                },
            )


def build_price_payload() -> dict[str, object]:
    """Build price handoff payload."""

    return {
        "selected_module": "price",
        "route_status": "routed",
        "route_confidence": 0.75,
        "candidate_modules": ["price"],
        "matched_signals": ["多少钱"],
        "parse_status": "parsed",
        "handler_status": "handoff",
        "answer_text": "当前系统尚未接入正式价格表，不能直接给出报价。请转人工确认。",
        "handoff_required": True,
        "source_references": [],
        "module_payload": {
            "selected_module": "price",
            "handler_status": "handoff",
        },
        "warnings": [],
        "errors": [],
    }


def build_quality_payload() -> dict[str, object]:
    """Build quality handoff payload."""

    return {
        "selected_module": "quality",
        "route_status": "routed",
        "route_confidence": 0.75,
        "candidate_modules": ["quality"],
        "matched_signals": ["生锈"],
        "parse_status": "parsed",
        "handler_status": "handoff",
        "answer_text": "当前系统不能自动承诺不生锈或绝对防锈，请转人工进一步确认。",
        "handoff_required": True,
        "source_references": [
            {
                "source_type": "database_table",
                "source_name": "products",
                "reference_id": "SKU001",
            }
        ],
        "module_payload": {
            "selected_module": "quality",
            "handler_status": "handoff",
        },
        "warnings": [],
        "errors": [],
    }


def build_logistics_payload() -> dict[str, object]:
    """Build logistics handoff payload."""

    return {
        "selected_module": "logistics",
        "route_status": "routed",
        "route_confidence": 0.75,
        "candidate_modules": ["logistics"],
        "matched_signals": ["运费"],
        "parse_status": "parsed",
        "handler_status": "handoff",
        "answer_text": "运费问题需转人工进一步确认。",
        "handoff_required": True,
        "source_references": [],
        "module_payload": {
            "selected_module": "logistics",
            "handler_status": "handoff",
        },
        "warnings": [],
        "errors": [],
    }


def build_non_handoff_payload() -> dict[str, object]:
    """Build non-handoff payload."""

    return {
        "selected_module": "spec",
        "route_status": "routed",
        "route_confidence": 0.75,
        "candidate_modules": ["spec"],
        "matched_signals": ["螺纹"],
        "parse_status": "parsed",
        "handler_status": "success",
        "answer_text": "查到 SKU001。螺纹规格为 M8×1.25。",
        "handoff_required": False,
        "source_references": [],
        "module_payload": {
            "selected_module": "spec",
            "handler_status": "success",
        },
        "warnings": [],
        "errors": [],
    }


def run_service_checks() -> bool:
    """Run handoff ticket service checks."""

    session_factory = get_session_factory()

    with session_factory() as session:
        repository = HandoffTicketRepository(session)
        service = HandoffTicketService(repository=repository)

        with session.begin():
            price_result = service.create_from_unified_result(
                user_text="SKU001 多少钱",
                unified_payload=build_price_payload(),
                source_channel=TEST_SOURCE_CHANNEL,
            )
            quality_result = service.create_from_unified_result(
                user_text="SKU001 会不会生锈",
                unified_payload=build_quality_payload(),
                source_channel=TEST_SOURCE_CHANNEL,
            )
            logistics_result = service.create_from_unified_result(
                user_text="SKU001 运费多少",
                unified_payload=build_logistics_payload(),
                source_channel=TEST_SOURCE_CHANNEL,
            )
            non_handoff_result = service.create_from_unified_result(
                user_text="SKU001 螺纹是多少",
                unified_payload=build_non_handoff_payload(),
                source_channel=TEST_SOURCE_CHANNEL,
            )

            print("=" * 80)
            print("service results")
            pprint(
                [
                    price_result.to_response_payload(),
                    quality_result.to_response_payload(),
                    logistics_result.to_response_payload(),
                    non_handoff_result.to_response_payload(),
                ]
            )

            checks: list[bool] = []

            checks.append(price_result.created is True)
            checks.append(quality_result.created is True)
            checks.append(logistics_result.created is True)
            checks.append(non_handoff_result.created is False)
            checks.append(non_handoff_result.ticket is None)

            if price_result.ticket is not None:
                checks.append(price_result.ticket.ticket_no.startswith("HT-"))
                checks.append(price_result.ticket.selected_module == "price")
                checks.append(price_result.ticket.handler_status == "handoff")
                checks.append("价格表" in price_result.ticket.handoff_reason)
                checks.append(
                    "price_without_price_table"
                    in price_result.ticket.risk_reasons
                )

            if quality_result.ticket is not None:
                checks.append(quality_result.ticket.ticket_no.startswith("HT-"))
                checks.append(quality_result.ticket.selected_module == "quality")
                checks.append(quality_result.ticket.handler_status == "handoff")
                checks.append("质量问题" in quality_result.ticket.handoff_reason)
                checks.append(
                    "quality_commitment_required"
                    in quality_result.ticket.risk_reasons
                )
                checks.append(
                    quality_result.ticket.source_references[0]["reference_id"]
                    == "SKU001"
                )

            if logistics_result.ticket is not None:
                checks.append(logistics_result.ticket.ticket_no.startswith("HT-"))
                checks.append(logistics_result.ticket.selected_module == "logistics")
                checks.append(logistics_result.ticket.handler_status == "handoff")
                checks.append("物流问题" in logistics_result.ticket.handoff_reason)
                checks.append(
                    "logistics_commitment_required"
                    in logistics_result.ticket.risk_reasons
                )

            listed_tickets = repository.list_tickets(
                status="open",
                limit=20,
                offset=0,
            )

            service_test_tickets = [
                ticket
                for ticket in listed_tickets
                if ticket.source_channel == TEST_SOURCE_CHANNEL
            ]

            print("=" * 80)
            print("service test tickets from repository")
            pprint([ticket.to_dict() for ticket in service_test_tickets])

            checks.append(len(service_test_tickets) >= 3)

        return all(checks)


def main() -> int:
    """Run HandoffTicketService checks."""

    cleanup_test_tickets()

    try:
        passed = run_service_checks()
    finally:
        cleanup_test_tickets()

    print("=" * 80)

    if not passed:
        print("handoff ticket service check failed")
        return 1

    print("handoff ticket service check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())