# ruff: noqa: E402,I001
"""Check LangGraph workflow skeleton.

This script verifies that the StateGraph workflow can be built and invoked
without replacing the current Unified Agent API.

It does not call an LLM, generate unsupported business answers, promise prices,
promise logistics, promise quality, promise warranty, promise returns/exchanges,
or create business commitments.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from pprint import pprint
from typing import Final
from uuid import uuid4

from sqlalchemy import text

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.state import (
    create_initial_agent_state,
    detect_forbidden_commitments,
    state_to_response_payload,
)
from app.agent.workflow import build_agent_workflow, run_agent_workflow
from app.core.database import get_session_factory
from app.repositories import ProductRepository


TEST_SOURCE_CHANNEL: Final[str] = "langgraph_workflow_skeleton_test"
EXPECTED_VISITED_NODES: Final[list[str]] = [
    "context",
    "intent",
    "route",
    "handler",
    "retrieval",
    "risk_control",
    "render",
]


@dataclass(frozen=True)
class WorkflowCase:
    """One workflow skeleton test case."""

    name: str
    text: str
    expected_selected_module: str | None
    expected_handler_status: str | None
    expected_handoff_required: bool | None
    expected_answer_fragments: tuple[str, ...]


def cleanup_test_data() -> None:
    """Delete workflow skeleton test data."""

    session_factory = get_session_factory()

    with session_factory() as session:
        with session.begin():
            session.execute(
                text(
                    """
                    DELETE FROM conversations
                    WHERE source_channel = :source_channel;
                    """
                ),
                {
                    "source_channel": TEST_SOURCE_CHANNEL,
                },
            )
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


def build_cases() -> list[WorkflowCase]:
    """Build deterministic workflow cases."""

    return [
        WorkflowCase(
            name="spec_success",
            text="SKU001 螺纹是多少",
            expected_selected_module="spec",
            expected_handler_status="success",
            expected_handoff_required=False,
            expected_answer_fragments=("SKU001", "螺纹规格"),
        ),
        WorkflowCase(
            name="price_handoff",
            text="SKU001 多少钱",
            expected_selected_module="price",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_answer_fragments=("SKU001", "不能直接给出报价"),
        ),
        WorkflowCase(
            name="quality_handoff",
            text="SKU001 会不会生锈",
            expected_selected_module="quality",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_answer_fragments=("SKU001", "不能自动承诺不生锈"),
        ),
        WorkflowCase(
            name="unknown_question",
            text="你好，请问你是谁",
            expected_selected_module=None,
            expected_handler_status=None,
            expected_handoff_required=None,
            expected_answer_fragments=(),
        ),
    ]


def check_workflow_build() -> bool:
    """Check workflow can be built."""

    print("=" * 80)
    print("checking workflow build")

    session_factory = get_session_factory()

    with session_factory() as session:
        product_repository = ProductRepository(session)
        workflow = build_agent_workflow(
            product_repository=product_repository,
            limit=5,
        )

    print(f"compiled workflow type: {type(workflow)}")

    return workflow is not None


def run_case(case: WorkflowCase) -> bool:
    """Run one workflow case."""

    print("=" * 80)
    print(f"case: {case.name}")
    print(f"text: {case.text}")

    session_factory = get_session_factory()

    with session_factory() as session:
        product_repository = ProductRepository(session)

        initial_state = create_initial_agent_state(
            session_id=f"session-workflow-{uuid4().hex[:12]}",
            channel=TEST_SOURCE_CHANNEL,
            user_id="user-workflow-skeleton-test",
            user_text=case.text,
        )

        final_state = run_agent_workflow(
            initial_state=initial_state,
            product_repository=product_repository,
            limit=5,
        )

    payload = state_to_response_payload(final_state)

    print("final AgentState:")
    pprint(final_state)
    print("response payload:")
    pprint(payload)

    metadata = final_state.get("metadata", {})
    visited_nodes = metadata.get("visited_nodes", [])

    checks: list[bool] = [
        visited_nodes == EXPECTED_VISITED_NODES,
        metadata.get("workflow_started_at") is not None,
        metadata.get("workflow_finished_at") is not None,
        metadata.get("response_ready") is True,
        metadata.get("retrieval_mode") == "disabled_placeholder",
        isinstance(final_state.get("final_response"), str),
        bool(str(final_state.get("final_response", "")).strip()),
        detect_forbidden_commitments(final_state) == [],
    ]

    if case.expected_selected_module is not None:
        checks.append(
            final_state.get("selected_module")
            == case.expected_selected_module
        )

    if case.expected_handler_status is not None:
        checks.append(
            final_state.get("handler_status")
            == case.expected_handler_status
        )

    if case.expected_handoff_required is not None:
        checks.append(
            final_state.get("handoff_required")
            == case.expected_handoff_required
        )
        checks.append(
            final_state.get("human_handoff")
            == case.expected_handoff_required
        )

    answer_text = str(final_state.get("answer_text", ""))

    for fragment in case.expected_answer_fragments:
        checks.append(fragment in answer_text)

    if not all(checks):
        print("failed checks:")
        for index, passed in enumerate(checks, start=1):
            if not passed:
                print(f"- check #{index} failed")
        return False

    return True


def main() -> int:
    """Run workflow skeleton checks."""

    cleanup_test_data()

    try:
        results = [
            check_workflow_build(),
            *[
                run_case(case)
                for case in build_cases()
            ],
        ]
    finally:
        cleanup_test_data()

    print("=" * 80)

    if not all(results):
        print("langgraph workflow skeleton check failed")
        return 1

    print("langgraph workflow skeleton check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())