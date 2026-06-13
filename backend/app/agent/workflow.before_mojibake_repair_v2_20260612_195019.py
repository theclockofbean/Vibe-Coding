"""LangGraph workflow skeleton for the agent.

This module builds a StateGraph-based workflow around AgentState.

Phase 3-D v0.1 does not replace the existing Unified Agent API, does not create
handoff tickets, does not write user/assistant conversation messages, does not
call an LLM, and does not call RAG. It provides a safe, observable workflow
skeleton that reuses existing deterministic business services.

The workflow does not generate unsupported business commitments.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any, Final, cast

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.agent.rag import (
    LocalKnowledgeChunkRetriever,
    filter_retrieved_chunk_dicts,
)
from app.agent.rag.quality_kb_retriever import QualityKBQdrantRetriever
from app.agent.services import ConversationService, UnifiedTextQAService
from app.agent.state import (
    AgentState,
    apply_conversation_context,
    apply_risk_control,
    apply_unified_payload,
)
from app.core.database import get_session_factory
from app.repositories import ProductRepository
from app.repositories.conversation_repository import ConversationRepository

VISITED_NODES_KEY: Final[str] = "visited_nodes"
NODE_ERRORS_KEY: Final[str] = "node_errors"


class AgentWorkflowNodes:
    """Node implementations for the LangGraph agent workflow skeleton."""

    def __init__(
        self,
        *,
        product_repository: ProductRepository,
        conversation_repository: ConversationRepository | None = None,
        limit: int = 5,
    ) -> None:
        """Initialize workflow nodes."""

        self.product_repository = product_repository
        self.conversation_repository = conversation_repository
        self.limit = limit

    def context_node(self, state: AgentState) -> AgentState:
        """Load conversation context without writing messages."""

        next_state = _copy_state(state)
        _mark_visited(next_state, "context")

        session_id = next_state.get("session_id")

        if self.conversation_repository is None or not session_id:
            return next_state

        try:
            conversation = self.conversation_repository.get_by_session_id(
                session_id,
            )

            if conversation is None:
                return next_state

            service = ConversationService(
                repository=self.conversation_repository,
            )
            history = service.load_history(
                session_id=session_id,
                limit=20,
            )

            apply_conversation_context(
                next_state,
                conversation_id=conversation.id,
                conversation_history=history,
            )

        except Exception as exc:  # noqa: BLE001
            _append_warning(
                next_state,
                "context_node_failed",
            )
            _append_node_error(
                next_state,
                node_name="context",
                exc=exc,
            )

        return next_state

    def intent_node(self, state: AgentState) -> AgentState:
        """Run deterministic pre-routing for workflow observability."""

        next_state = _copy_state(state)
        _mark_visited(next_state, "intent")

        user_text = str(next_state.get("user_text", ""))
        route_payload = _deterministic_pre_route(user_text)

        next_state["intent"] = route_payload["intent"]
        next_state["selected_module"] = route_payload["selected_module"]
        next_state["candidate_modules"] = route_payload["candidate_modules"]
        next_state["matched_signals"] = route_payload["matched_signals"]
        next_state["matched_sku"] = route_payload["matched_sku"]
        next_state["route_status"] = route_payload["route_status"]
        next_state["route_confidence"] = route_payload["route_confidence"]


        _apply_llm_intent_fallback_if_needed(next_state)

        return next_state

    def route_node(self, state: AgentState) -> AgentState:
        """Decide workflow route and record route metadata."""

        next_state = _copy_state(state)
        _mark_visited(next_state, "route")

        metadata = _ensure_metadata(next_state)

        route_status = next_state.get("route_status")
        selected_module = next_state.get("selected_module")

        if route_status in {"invalid_request", "unknown", "ambiguous"}:
            workflow_route = str(route_status)
        elif selected_module in {"spec", "price", "logistics", "quality"}:
            workflow_route = str(selected_module)
        else:
            workflow_route = "unknown"

        metadata["workflow_route"] = workflow_route

        return next_state

    def handler_node(self, state: AgentState) -> AgentState:
        """Call the existing stable UnifiedTextQAService."""

        next_state = _copy_state(state)
        _mark_visited(next_state, "handler")

        user_text = str(next_state.get("user_text", "")).strip()

        if not user_text:
            next_state["parse_status"] = "invalid_request"
            next_state["handler_status"] = "handoff"
            next_state["answer_text"] = "系统处理当前问题时发生异常，请转人工确认。"
            next_state["handoff_required"] = True
            next_state["human_handoff"] = True
            return next_state

        try:
            service = UnifiedTextQAService(
                product_repository=self.product_repository,
            )
            result = service.answer(
                text=user_text,
                limit=self.limit,
            )
            payload = result.to_response_payload()

            apply_unified_payload(
                next_state,
                payload=payload,
            )

            metadata = _ensure_metadata(next_state)
            metadata["handler_payload_keys"] = sorted(payload.keys())

        except Exception as exc:  # noqa: BLE001
            next_state["parse_status"] = "error"
            next_state["handler_status"] = "handoff"
            next_state["answer_text"] = "系统处理当前问题时发生异常，请转人工确认。"
            next_state["handoff_required"] = True
            next_state["human_handoff"] = True
            _append_warning(
                next_state,
                "handler_node_failed",
            )
            _append_node_error(
                next_state,
                node_name="handler",
                exc=exc,
            )


        _reapply_llm_intent_module_after_handler(next_state)

        return next_state

    def retrieval_node(

        self,
        state: AgentState,
    ) -> AgentState:
        """Retrieve RAG evidence chunks through Qdrant with local fallback."""

        new_state = _copy_state(state)
        quality_state, real_quality_kb_used = _try_real_quality_kb_retrieval(
            dict(new_state)
        )
        if real_quality_kb_used:
            return cast(AgentState, quality_state)
        new_state = cast(AgentState, quality_state)

        metadata = _ensure_metadata(new_state)

        _mark_visited(new_state, "retrieval")

        user_text = str(new_state.get("user_text") or "").strip()
        retrieval_module = _infer_retrieval_module(
            user_text=user_text,
            selected_module=_optional_state_str(new_state.get("selected_module")),
        )
        matched_sku = _infer_retrieval_matched_sku(
            state=new_state,
            user_text=user_text,
        )

        if not user_text:
            new_state["retrieved_chunks"] = []

            metadata["retrieval_mode"] = "skipped_empty_query"
            metadata["retrieved_chunk_count"] = 0
            metadata["retrieval_rejected_count"] = 0
            metadata["retrieval_warning_count"] = 0
            metadata["retrieval_selected_module"] = retrieval_module
            metadata["retrieval_matched_sku"] = matched_sku

            return new_state

        raw_chunks, qdrant_metadata = _retrieve_qdrant_rag_chunks(
            user_text=user_text,
            selected_module=retrieval_module,
            matched_sku=matched_sku,
        )

        retrieval_mode = "qdrant"
        retrieval_fallback_reason: str | None = None

        if not raw_chunks:
            retrieval_mode = "local_postgres"
            retrieval_fallback_reason = str(
                qdrant_metadata.get("fallback_reason")
                or "qdrant_returned_no_chunks"
            )
            raw_chunks = _retrieve_local_rag_chunks_with_session_fallback(
                product_repository=self.product_repository,
                user_text=user_text,
                selected_module=retrieval_module,
                matched_sku=matched_sku,
            )

        filtered_result = filter_retrieved_chunk_dicts(
            chunks=raw_chunks,
            selected_module=retrieval_module,
            commitment_context=False,
            score_threshold=0.01,
        )

        safe_chunk_dicts = filtered_result.to_retrieved_chunk_dicts()

        new_state["retrieved_chunks"] = safe_chunk_dicts

        new_state["source_references"] = _merge_source_references(
            existing_value=new_state.get("source_references"),
            new_references=filtered_result.source_references,
        )

        new_state["warnings"] = _deduplicate_text_list(
            [
                *_as_text_list(new_state.get("warnings")),
                *filtered_result.warnings,
            ]
        )

        new_state["risk_reasons"] = _deduplicate_text_list(
            [
                *_as_text_list(new_state.get("risk_reasons")),
                *filtered_result.risk_reasons,
            ]
        )

        metadata["retrieval_mode"] = retrieval_mode
        metadata["retrieval_fallback_reason"] = retrieval_fallback_reason
        metadata["retrieval_collection_name"] = qdrant_metadata.get(
            "collection_name"
        )
        metadata["retrieval_embedding_model"] = qdrant_metadata.get(
            "embedding_model"
        )
        metadata["retrieval_embedding_dimension"] = qdrant_metadata.get(
            "embedding_dimension"
        )
        metadata["retrieval_qdrant_url"] = qdrant_metadata.get("qdrant_url")
        metadata["retrieved_chunk_count"] = len(safe_chunk_dicts)
        metadata["retrieval_rejected_count"] = len(filtered_result.rejected_chunks)
        metadata["retrieval_warning_count"] = len(filtered_result.warnings)
        metadata["retrieval_selected_module"] = retrieval_module
        metadata["retrieval_matched_sku"] = matched_sku
        metadata["retrieval_filter"] = filtered_result.metadata

        return new_state


    def llm_node(
        self,
        state: AgentState,
    ) -> AgentState:
        """Run offline LLM client and safety guard.

        LLM output is recorded for later grounded rendering work. It does not
        modify final_response, answer_text, handoff flags, or database state.
        """

        new_state = _copy_state(state)
        metadata = _ensure_metadata(new_state)

        _mark_visited(new_state, "llm")

        llm_enabled = _is_llm_node_enabled()

        if not llm_enabled:
            new_state["llm_used"] = False
            new_state["llm_error"] = None
            new_state["llm_output"] = None
            new_state["llm_safety_flags"] = []

            metadata["llm_enabled"] = False
            metadata["llm_used"] = False
            metadata["llm_fallback_reason"] = "llm_node_disabled"

            return new_state

        try:
            request, response = _run_offline_llm_for_state(new_state)

            new_state["llm_request"] = request
            new_state["llm_response"] = response
            new_state["llm_output"] = response.get("content")
            new_state["llm_safety_flags"] = _as_text_list(
                response.get("safety_flags")
            )
            new_state["llm_used"] = response.get("error") is None
            new_state["llm_error"] = _optional_state_str(response.get("error"))

            metadata["llm_enabled"] = True
            metadata["llm_used"] = new_state["llm_used"]
            metadata["llm_provider"] = response.get("provider")
            metadata["llm_model"] = response.get("model")
            metadata["llm_task_type"] = request.get("task_type")
            metadata["llm_latency_ms"] = response.get("latency_ms")
            metadata["llm_is_safe"] = response.get("is_safe")
            metadata["llm_needs_handoff"] = response.get("needs_handoff")
            metadata["llm_fallback_reason"] = None

            response_metadata_raw = response.get("metadata")
            response_metadata = (
                {
                    str(key): value
                    for key, value in response_metadata_raw.items()
                }
                if isinstance(response_metadata_raw, dict)
                else {}
            )
            factory_metadata_raw = response_metadata.get("llm_factory")
            factory_metadata = (
                {
                    str(key): value
                    for key, value in factory_metadata_raw.items()
                }
                if isinstance(factory_metadata_raw, dict)
                else {}
            )
            metadata["llm_real_api_enabled"] = response_metadata.get(
                "llm_real_api_enabled",
                False,
            )
            metadata["llm_factory_fallback_reason"] = factory_metadata.get(
                "fallback_reason"
            )
            metadata["llm_factory_warnings"] = response_metadata.get(
                "llm_factory_warnings",
                [],
            )

        except (RuntimeError, ValueError) as exc:
            new_state["llm_request"] = {}
            new_state["llm_response"] = {}
            new_state["llm_output"] = None
            new_state["llm_safety_flags"] = ["llm_node_error"]
            new_state["llm_used"] = False
            new_state["llm_error"] = f"{type(exc).__name__}: {exc}"

            metadata["llm_enabled"] = True
            metadata["llm_used"] = False
            metadata["llm_error"] = new_state["llm_error"]
            metadata["llm_fallback_reason"] = "llm_node_error"

        return new_state


    def risk_control_node(self, state: AgentState) -> AgentState:
        """Apply deterministic risk control."""

        next_state = _copy_state(state)
        _mark_visited(next_state, "risk_control")

        previous_handoff_required = bool(
            next_state.get("handoff_required", False),
        )

        apply_risk_control(next_state)

        if previous_handoff_required:
            next_state["handoff_required"] = True
            next_state["human_handoff"] = True

        metadata = _ensure_metadata(next_state)
        metadata["risk_control_checked"] = True

        return next_state

    def render_node(
        self,
        state: AgentState,
    ) -> AgentState:
        """Render grounded final response.

        Grounded RenderNode uses structured handler output, safe RAG evidence,
        business rules, and optional safe LLM expression support. It does not
        write database records.
        """

        new_state = _copy_state(state)
        metadata = _ensure_metadata(new_state)

        _mark_visited(new_state, "render")

        try:
            render_input, render_output = _run_grounded_render_for_state(new_state)

            new_state["render_input"] = render_input
            new_state["render_output"] = render_output
            new_state["final_response"] = render_output.get("final_response")
            new_state["response_sources"] = _as_dict_list(
                render_output.get("response_sources")
            )
            new_state["response_warnings"] = _as_text_list(
                render_output.get("response_warnings")
            )
            new_state["render_risk_flags"] = _as_text_list(
                render_output.get("risk_flags")
            )
            new_state["render_used_llm_output"] = bool(
                render_output.get("used_llm_output")
            )
            new_state["is_grounded_response"] = bool(
                render_output.get("is_grounded")
            )

            if render_output.get("needs_handoff") is True:
                new_state["handoff_required"] = True
                new_state["human_handoff"] = True

            new_state["warnings"] = _deduplicate_text_list(
                [
                    *_as_text_list(new_state.get("warnings")),
                    *_as_text_list(render_output.get("response_warnings")),
                ]
            )
            new_state["risk_reasons"] = _deduplicate_text_list(
                [
                    *_as_text_list(new_state.get("risk_reasons")),
                    *_as_text_list(render_output.get("risk_reasons")),
                ]
            )

            metadata["response_ready"] = True
            metadata["render_mode"] = render_output.get("metadata", {}).get(
                "render_mode"
            )
            metadata["render_is_grounded"] = render_output.get("is_grounded")
            metadata["render_used_llm_output"] = render_output.get(
                "used_llm_output"
            )
            metadata["render_source_count"] = len(
                _as_dict_list(render_output.get("response_sources"))
            )
            metadata["render_warning_count"] = len(
                _as_text_list(render_output.get("response_warnings"))
            )
            metadata["render_safety_blocked"] = render_output.get(
                "metadata", {}
            ).get("render_safety_blocked")
            metadata["render_fallback_reason"] = render_output.get(
                "metadata", {}
            ).get("render_fallback_reason")

        except (RuntimeError, ValueError, TypeError) as exc:
            fallback_response = _optional_state_str(new_state.get("answer_text"))

            if fallback_response is None:
                fallback_response = (
                    "褰撳墠淇℃伅涓嶈冻锛屾棤娉曞舰鎴愬彲闈犵瓟澶嶃€傝琛ュ厖 SKU銆佹暟閲忋€?
                    "鏀惰揣鍦板尯鎴栧叿浣撻棶棰樺悗杞汉宸ョ‘璁ゃ€?
                )
                new_state["handoff_required"] = True
                new_state["human_handoff"] = True

            new_state["final_response"] = fallback_response
            new_state["render_input"] = {}
            new_state["render_output"] = {}
            new_state["response_sources"] = []
            new_state["response_warnings"] = ["grounded render node fallback"]
            new_state["render_risk_flags"] = []
            new_state["render_used_llm_output"] = False
            new_state["is_grounded_response"] = False

            metadata["response_ready"] = True
            metadata["render_mode"] = "workflow_render_fallback"
            metadata["render_is_grounded"] = False
            metadata["render_used_llm_output"] = False
            metadata["render_source_count"] = 0
            metadata["render_warning_count"] = 1
            metadata["render_safety_blocked"] = False
            metadata["render_fallback_reason"] = f"{type(exc).__name__}: {exc}"

        metadata["workflow_finished_at"] = _utc_now_iso()

        return new_state


def build_agent_workflow(
    *,
    product_repository: ProductRepository,
    conversation_repository: ConversationRepository | None = None,
    limit: int = 5,
) -> Any:
    """Build and compile the LangGraph agent workflow skeleton."""

    nodes = AgentWorkflowNodes(
        product_repository=product_repository,
        conversation_repository=conversation_repository,
        limit=limit,
    )

    workflow = StateGraph(AgentState)

    workflow.add_node("context", nodes.context_node)
    workflow.add_node("intent", nodes.intent_node)
    workflow.add_node("route", nodes.route_node)
    workflow.add_node("handler", nodes.handler_node)
    workflow.add_node("retrieval", nodes.retrieval_node)
    workflow.add_node("llm", nodes.llm_node)
    workflow.add_node("risk_control", nodes.risk_control_node)
    workflow.add_node("render", nodes.render_node)

    workflow.add_edge(START, "context")
    workflow.add_edge("context", "intent")
    workflow.add_edge("intent", "route")
    workflow.add_edge("route", "handler")
    workflow.add_edge("handler", "retrieval")
    workflow.add_edge("retrieval", "llm")
    workflow.add_edge("llm", "risk_control")
    workflow.add_edge("risk_control", "render")
    workflow.add_edge("render", END)

    return workflow.compile()


def run_agent_workflow(
    *,
    initial_state: AgentState,
    product_repository: ProductRepository,
    conversation_repository: ConversationRepository | None = None,
    limit: int = 5,
) -> AgentState:
    """Run the compiled LangGraph agent workflow skeleton."""

    prepared_state = _copy_state(initial_state)
    metadata = _ensure_metadata(prepared_state)
    metadata.setdefault("workflow_started_at", _utc_now_iso())
    metadata.setdefault(VISITED_NODES_KEY, [])
    metadata.setdefault(NODE_ERRORS_KEY, [])

    compiled_workflow = build_agent_workflow(
        product_repository=product_repository,
        conversation_repository=conversation_repository,
        limit=limit,
    )
    result = compiled_workflow.invoke(prepared_state)

    return cast(AgentState, result)









def _reapply_llm_intent_module_after_handler(
    state: AgentState,
) -> None:
    """Reapply validated LLM intent module after handler payload merge.

    The handler may call legacy unified routing and overwrite selected_module.
    For low-confidence or forced LLM-intent cases, a validated and applied LLM
    intent should be preserved before retrieval.
    """

    metadata = _ensure_metadata(state)
    applied_intent = _optional_state_str(
        metadata.get("llm_intent_applied_intent")
    )

    if metadata.get("llm_intent_applied") is not True:
        return

    if applied_intent not in {"spec", "price", "logistics", "quality", "general"}:
        return

    previous_selected_module = _optional_state_str(state.get("selected_module"))

    if applied_intent in {"spec", "price", "logistics", "quality"}:
        state["intent"] = applied_intent
        state["selected_module"] = applied_intent
        state["candidate_modules"] = [applied_intent]
        state["route_status"] = "matched"
        state["workflow_route"] = applied_intent  # type: ignore[typeddict-unknown-key]
    elif applied_intent == "general":
        state["intent"] = "general"
        state["selected_module"] = "general"
        state["candidate_modules"] = ["general"]

    metadata["llm_intent_reapplied_after_handler"] = True
    metadata["llm_intent_reapplied_module"] = applied_intent
    metadata["llm_intent_previous_selected_module_after_handler"] = (
        previous_selected_module
    )


def _apply_llm_intent_fallback_if_needed(
    state: AgentState,
) -> None:
    """Apply LLM intent fallback for low-confidence intent routing.

    Conservative policy:
    - high-confidence rule-based routing wins;
    - LLM output must be a valid enum;
    - LLM failure keeps the existing route unchanged.
    """

    from app.agent.llm.intent_classifier import (
        ALLOWED_INTENTS,
        LLMIntentClassifier,
    )

    metadata = _ensure_metadata(state)

    enabled = _workflow_llm_intent_env_bool(
        "LLM_INTENT_CLASSIFIER_ENABLED",
        default=True,
    )

    metadata["llm_intent_classifier_enabled"] = enabled

    if not enabled:
        metadata["llm_intent_classifier_used"] = False
        metadata["llm_intent_fallback_reason"] = "llm_intent_classifier_disabled"
        return

    user_text = _optional_state_str(state.get("user_text")) or ""
    rule_based_intent = _workflow_llm_intent_current_intent(state)
    rule_based_confidence = _workflow_llm_intent_rule_confidence(
        state=state,
        rule_based_intent=rule_based_intent,
    )

    force_llm_classifier = bool(metadata.get("force_llm_intent_classifier"))

    if force_llm_classifier:
        rule_based_confidence = 0.0

    try:
        result = LLMIntentClassifier().classify(
            user_text=user_text,
            rule_based_intent=rule_based_intent,
            rule_based_confidence=rule_based_confidence,
        )
    except (RuntimeError, ValueError, TypeError) as exc:
        metadata["llm_intent_classifier_used"] = False
        metadata["llm_intent_fallback_reason"] = (
            f"{type(exc).__name__}: {exc}"
        )
        return

    result_dict = result.to_dict()
    metadata["llm_intent_result"] = result_dict
    metadata["llm_intent_classifier_used"] = result.used_llm
    metadata["llm_intent"] = result.intent
    metadata["llm_intent_confidence"] = result.confidence
    metadata["llm_intent_reason"] = result.reason
    metadata["llm_intent_fallback_reason"] = result.fallback_reason

    if result.metadata:
        metadata["llm_intent_metadata"] = result.metadata

    if not result.is_valid:
        return

    if result.intent not in ALLOWED_INTENTS:
        metadata["llm_intent_fallback_reason"] = "invalid_intent_enum"
        return

    should_apply_result = result.used_llm or force_llm_classifier

    if not should_apply_result:
        return

    previous_intent = _workflow_llm_intent_current_intent(state)
    state["intent"] = result.intent

    if result.intent in {"spec", "price", "logistics", "quality"}:
        state["selected_module"] = result.intent
        state["candidate_modules"] = [result.intent]
        state["route_confidence"] = result.confidence
    elif result.intent == "general":
        state["selected_module"] = "general"
        state["candidate_modules"] = ["general"]
        state["route_confidence"] = result.confidence
    elif result.intent == "escalation":
        state["selected_module"] = "general"
        state["candidate_modules"] = ["general"]
        state["route_confidence"] = result.confidence
        state["handoff_required"] = True
        state["human_handoff"] = True

    metadata["llm_intent_applied"] = True
    metadata["llm_intent_previous_intent"] = previous_intent
    metadata["llm_intent_applied_intent"] = result.intent


def _workflow_llm_intent_current_intent(
    state: AgentState,
) -> str | None:
    """Return current rule-based intent."""

    intent = _optional_state_str(state.get("intent"))

    if intent:
        return intent

    selected_module = _optional_state_str(state.get("selected_module"))

    if selected_module:
        return selected_module

    return None


def _workflow_llm_intent_rule_confidence(
    *,
    state: AgentState,
    rule_based_intent: str | None,
) -> float | None:
    """Infer rule-based confidence from state and metadata."""

    metadata = _ensure_metadata(state)

    for value in (
        state.get("route_confidence"),
        metadata.get("route_confidence"),
        metadata.get("intent_confidence"),
    ):
        confidence = _workflow_llm_intent_optional_float(value)

        if confidence is not None:
            return confidence

    if metadata.get("force_llm_intent_classifier") is True:
        return 0.0

    matched_signals = _as_text_list(state.get("matched_signals"))

    if rule_based_intent in {"spec", "price", "logistics", "quality"}:
        if matched_signals:
            return 0.9
        return 0.66

    if rule_based_intent == "general":
        return 0.45

    return None


def _workflow_llm_intent_env_bool(
    key: str,
    *,
    default: bool,
) -> bool:
    """Read boolean env var."""

    import os

    value = os.getenv(key)

    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


def _workflow_llm_intent_optional_float(
    value: object,
) -> float | None:
    """Return optional float."""

    if isinstance(value, int | float):
        return float(value)

    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None

    return None


def _run_grounded_render_for_state(
    state: AgentState,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run RenderContextBuilder and GroundedRenderer for workflow state."""

    import os

    from app.agent.rendering.context import RenderContextBuilder
    from app.agent.rendering.grounded_renderer import GroundedRenderer

    if os.getenv("AGENT_RENDER_FORCE_ERROR", "").strip() == "1":
        raise RuntimeError("forced grounded render node error for regression check")

    render_input = RenderContextBuilder().from_state(state)
    render_output = GroundedRenderer().render(render_input)

    return render_input.to_dict(), render_output.to_dict()


def _run_offline_llm_for_state(
    state: AgentState,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run offline RuleBasedLLMClient for state and guard its response."""

    import os

    from app.agent.llm.factory import build_llm_client_result_from_env
    from app.agent.llm.safety import LLMSafetyGuard
    from app.agent.llm.schemas import LLMRequest

    if os.getenv("AGENT_LLM_FORCE_ERROR", "").strip() == "1":
        raise RuntimeError("forced llm node error for regression check")

    task_type = _infer_llm_task_type(state)

    request = LLMRequest(
        task_type=task_type,
        user_text=str(state.get("user_text") or ""),
        context_blocks=_build_llm_context_blocks(state),
        retrieved_chunks=_as_dict_list(state.get("retrieved_chunks")),
        structured_facts=_extract_llm_structured_facts(state),
        business_rules=_build_llm_business_rules(),
        metadata={
            "selected_module": state.get("selected_module"),
            "handler_status": state.get("handler_status"),
            "handoff_required": state.get("handoff_required"),
        },
    )

    client_result = build_llm_client_result_from_env()
    raw_response = client_result.client.generate(request)
    guarded_response = LLMSafetyGuard().guard_response(raw_response)

    request_dict = request.to_dict()
    request_dict["forbidden_commitments"] = ["<redacted>"]

    response_dict = guarded_response.to_dict()
    response_metadata_raw = response_dict.get("metadata")
    response_metadata = (
        {
            str(key): value
            for key, value in response_metadata_raw.items()
        }
        if isinstance(response_metadata_raw, dict)
        else {}
    )
    response_metadata["llm_factory"] = client_result.metadata
    response_metadata["llm_factory_warnings"] = client_result.warnings
    response_metadata["llm_real_api_enabled"] = client_result.real_api_enabled
    response_dict["metadata"] = response_metadata

    return request_dict, response_dict


def _is_llm_node_enabled() -> bool:
    """Return whether LLM node is enabled."""

    import os

    value = os.getenv("AGENT_LLM_NODE_ENABLED", "1").strip().lower()

    return value not in {"0", "false", "no", "off"}


def _infer_llm_task_type(
    state: AgentState,
) -> str:
    """Infer safe offline LLM task type."""

    if state.get("handoff_required") is True:
        return "draft_handoff_note"

    retrieved_chunks = _as_dict_list(state.get("retrieved_chunks"))

    if retrieved_chunks:
        return "summarize_evidence"

    return "rule_based_test"


def _build_llm_context_blocks(
    state: AgentState,
) -> list[str]:
    """Build safe context blocks for LLM."""

    blocks: list[str] = []

    answer_text = _optional_state_str(state.get("answer_text"))

    if answer_text is not None:
        blocks.append(f"缁撴瀯鍖栨ā鍧楃瓟澶嶏細{answer_text}")

    selected_module = _optional_state_str(state.get("selected_module"))

    if selected_module is not None:
        blocks.append(f"宸查€夋ā鍧楋細{selected_module}")

    return blocks


def _extract_llm_structured_facts(
    state: AgentState,
) -> dict[str, Any]:
    """Extract structured facts for LLM."""

    module_payload = state.get("module_payload")

    if isinstance(module_payload, dict):
        return {
            str(key): value
            for key, value in module_payload.items()
        }

    return {}


def _build_llm_business_rules() -> list[str]:
    """Return LLM business rules."""

    return [
        "LLM 输出不是事实来源。",
        "LLM 不得生成价格、库存、物流、质量或售后承诺。",
        "最终结论必须以结构化数据、业务规则或人工确认为准。",
        "证据不足时应拒答或转人工。",
    ]


def _as_dict_list(
    value: object,
) -> list[dict[str, Any]]:
    """Return list of dictionaries."""

    if not isinstance(value, list):
        return []

    result: list[dict[str, Any]] = []

    for item in value:
        if isinstance(item, dict):
            result.append(
                {
                    str(key): item_value
                    for key, item_value in item.items()
                }
            )

    return result


def _retrieve_qdrant_rag_chunks(
    *,
    user_text: str,
    selected_module: str | None,
    matched_sku: str | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Retrieve RAG chunks from Qdrant.

    The helper catches Qdrant-layer failures and returns empty chunks plus
    fallback metadata so the workflow can degrade to local PostgreSQL retrieval.
    """

    import os

    from app.agent.rag.embedding import DeterministicHashEmbeddingClient
    from app.agent.rag.qdrant_retriever import QdrantRetriever
    from app.agent.rag.qdrant_store import (
        DEFAULT_QDRANT_COLLECTION,
        DEFAULT_QDRANT_URL,
        DEFAULT_QDRANT_VECTOR_SIZE,
        QdrantStoreError,
        QdrantVectorStore,
    )

    qdrant_url = os.getenv("QDRANT_URL", DEFAULT_QDRANT_URL)
    embedding_model = "deterministic-hash-embedding-v1"

    metadata: dict[str, Any] = {
        "collection_name": DEFAULT_QDRANT_COLLECTION,
        "embedding_model": embedding_model,
        "embedding_dimension": DEFAULT_QDRANT_VECTOR_SIZE,
        "qdrant_url": qdrant_url,
    }

    try:
        vector_store = QdrantVectorStore(
            base_url=qdrant_url,
            timeout=5.0,
        )
        vector_store.assert_collection_config(
            collection_name=DEFAULT_QDRANT_COLLECTION,
            expected_vector_size=DEFAULT_QDRANT_VECTOR_SIZE,
        )

        retriever = QdrantRetriever(
            embedding_client=DeterministicHashEmbeddingClient(
                dimension=DEFAULT_QDRANT_VECTOR_SIZE,
            ),
            vector_store=vector_store,
            collection_name=DEFAULT_QDRANT_COLLECTION,
            embedding_dimension=DEFAULT_QDRANT_VECTOR_SIZE,
            search_limit=50,
        )

        chunks = retriever.retrieve(
            query=user_text,
            selected_module=selected_module,
            matched_sku=matched_sku,
            top_k=5,
        )

        metadata["success"] = True
        metadata["raw_chunk_count"] = len(chunks)

        return chunks, metadata

    except (QdrantStoreError, RuntimeError, ValueError, OSError) as exc:
        metadata["success"] = False
        metadata["fallback_reason"] = f"{type(exc).__name__}: {exc}"

        return [], metadata


def _retrieve_local_rag_chunks_with_session_fallback(
    *,
    product_repository: object,
    user_text: str,
    selected_module: str | None,
    matched_sku: str | None,
) -> list[dict[str, Any]]:
    """Retrieve local chunks using repository session or a temporary session."""

    repository_session = _get_repository_session(product_repository)

    if repository_session is not None:
        return _retrieve_local_rag_chunks(
            session=repository_session,
            user_text=user_text,
            selected_module=selected_module,
            matched_sku=matched_sku,
        )

    session_factory = get_session_factory()

    with session_factory() as rag_session:
        return _retrieve_local_rag_chunks(
            session=rag_session,
            user_text=user_text,
            selected_module=selected_module,
            matched_sku=matched_sku,
        )


def _retrieve_local_rag_chunks(
    *,
    session: Session,
    user_text: str,
    selected_module: str | None,
    matched_sku: str | None,
) -> list[dict[str, Any]]:
    """Retrieve local RAG chunks using PostgreSQL metadata."""

    local_retriever = LocalKnowledgeChunkRetriever(
        session=session,
        score_threshold=0.01,
        max_candidates=50,
    )

    return local_retriever.retrieve(
        query=user_text,
        selected_module=selected_module,
        matched_sku=matched_sku,
        top_k=5,
    )


def _infer_retrieval_module(
    *,
    user_text: str,
    selected_module: str | None,
) -> str | None:
    """Infer retrieval module from text and selected module."""

    normalized_text = user_text.strip().lower()

    price_terms = (
        "多少钱",
        "价格",
        "报价",
        "单价",
        "折扣",
        "采购价",
    )
    logistics_terms = (
        "物流",
        "发货",
        "到货",
        "运费",
        "快递",
        "几天发",
        "几天到",
        "时效",
    )
    quality_terms = (
        "鏉愯川",
        "琛ㄩ潰澶勭悊",
        "闃虫瀬姘у寲",
        "璐ㄩ噺",
        "鐢熼攬",
        "鎺夋紗",
        "鑰愮敤",
        "鍒掔棔",
        "姘у寲",
    )

    if any(term in normalized_text for term in price_terms):
        return "price"

    if any(term in normalized_text for term in logistics_terms):
        return "logistics"

    if any(term in normalized_text for term in quality_terms):
        return "quality"

    return selected_module


def _infer_retrieval_matched_sku(
    *,
    state: AgentState,
    user_text: str,
) -> str | None:
    """Infer matched SKU for retrieval."""

    existing_sku = _optional_state_str(state.get("matched_sku"))

    if existing_sku is not None:
        return existing_sku

    module_payload = state.get("module_payload")

    if isinstance(module_payload, dict):
        for key in (
            "product_reference_value",
            "query_value",
        ):
            value = _optional_state_str(module_payload.get(key))

            if value is not None and value.upper().startswith("SKU"):
                return value.upper()

        sku_ids = module_payload.get("sku_ids")

        if isinstance(sku_ids, list):
            for sku_id in sku_ids:
                value = _optional_state_str(sku_id)

                if value is not None and value.upper().startswith("SKU"):
                    return value.upper()

    return _extract_sku(user_text)


def _optional_state_str(
    value: object,
) -> str | None:
    """Return stripped text or None."""

    if value is None:
        return None

    text_value = str(value).strip()

    if not text_value:
        return None

    return text_value


def _get_repository_session(
    repository: object,
) -> Session | None:
    """Extract SQLAlchemy Session from a repository if available."""

    session = getattr(repository, "session", None)

    if isinstance(session, Session):
        return session

    return None


def _merge_source_references(
    *,
    existing_value: object,
    new_references: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge source references without duplicating RAG chunk references."""

    merged: list[dict[str, Any]] = []

    if isinstance(existing_value, list):
        for item in existing_value:
            if isinstance(item, dict):
                merged.append(
                    {
                        str(key): value
                        for key, value in item.items()
                    }
                )

    existing_keys = {
        _source_reference_key(reference)
        for reference in merged
    }

    for reference in new_references:
        normalized_reference = {
            str(key): value
            for key, value in reference.items()
        }
        reference_key = _source_reference_key(normalized_reference)

        if reference_key in existing_keys:
            continue

        merged.append(normalized_reference)
        existing_keys.add(reference_key)

    return merged


def _source_reference_key(
    reference: dict[str, Any],
) -> str:
    """Return stable source reference key."""

    return "|".join(
        [
            str(reference.get("source_type") or ""),
            str(reference.get("collection") or ""),
            str(reference.get("reference_id") or ""),
            str(reference.get("module") or ""),
        ]
    )


def _as_text_list(
    value: object,
) -> list[str]:
    """Return list[str] from unknown value."""

    if not isinstance(value, list):
        return []

    return [
        str(item)
        for item in value
        if str(item).strip()
    ]


def _deduplicate_text_list(
    values: list[str],
) -> list[str]:
    """Deduplicate text list while preserving order."""

    result: list[str] = []

    for value in values:
        if value not in result:
            result.append(value)

    return result


def _deterministic_pre_route(user_text: str) -> dict[str, Any]:
    """Return deterministic pre-routing metadata for workflow observability."""

    normalized_text = user_text.strip().upper()
    matched_sku = _extract_sku(normalized_text)

    if not normalized_text:
        return {
            "intent": None,
            "selected_module": None,
            "candidate_modules": [],
            "matched_signals": [],
            "matched_sku": matched_sku,
            "route_status": "invalid_request",
            "route_confidence": 0.0,
        }

    module_signals = {
        "price": [
            "多少钱",
            "价格",
            "报价",
            "单价",
            "折扣",
            "采购价",
        ],
        "logistics": [
            "物流",
            "快递",
            "发货",
            "多久",
            "运费",
            "到货",
            "时效",
        ],
        "quality": [
            "质量",
            "品质",
            "材质",
            "生锈",
            "掉漆",
            "坏",
            "耐用",
            "质保",
            "保修",
            "退",
            "换",
            "赔",
        ],
        "spec": [
            "规格",
            "型号",
            "螺纹",
            "杆长",
            "球径",
            "锥度",
            "OEM",
            "适配",
        ],
    }

    candidate_modules: list[str] = []
    matched_signals: list[str] = []

    for module_name, signals in module_signals.items():
        module_matched_signals = [
            signal
            for signal in signals
            if signal in normalized_text
        ]

        if module_matched_signals:
            candidate_modules.append(module_name)
            matched_signals.extend(module_matched_signals)

    if not candidate_modules:
        route_status = "unknown"
        selected_module = None
        route_confidence = 0.0
    elif len(candidate_modules) == 1:
        route_status = "routed"
        selected_module = candidate_modules[0]
        route_confidence = 0.75
    else:
        route_status = "ambiguous"
        selected_module = candidate_modules[0]
        route_confidence = 0.45

    return {
        "intent": selected_module,
        "selected_module": selected_module,
        "candidate_modules": candidate_modules,
        "matched_signals": matched_signals,
        "matched_sku": matched_sku,
        "route_status": route_status,
        "route_confidence": route_confidence,
    }


def _extract_sku(normalized_text: str) -> str | None:
    """Extract SKU-like token from text."""

    match = re.search(r"\bSKU\d+\b", normalized_text)

    if match is None:
        return None

    return match.group(0)


def _copy_state(state: AgentState) -> AgentState:
    """Create a shallow-copy AgentState with copied mutable containers."""

    copied = AgentState(**state)

    copied["conversation_history"] = list(state.get("conversation_history", []))
    copied["candidate_modules"] = list(state.get("candidate_modules", []))
    copied["matched_signals"] = list(state.get("matched_signals", []))
    copied["retrieved_chunks"] = list(state.get("retrieved_chunks", []))
    copied["source_references"] = list(state.get("source_references", []))
    copied["risk_reasons"] = list(state.get("risk_reasons", []))
    copied["warnings"] = list(state.get("warnings", []))
    copied["errors"] = list(state.get("errors", []))
    copied["metadata"] = dict(state.get("metadata", {}))

    return copied


def _ensure_metadata(state: AgentState) -> dict[str, Any]:
    """Ensure metadata dict exists."""

    metadata = state.get("metadata")

    if not isinstance(metadata, dict):
        metadata = {}
        state["metadata"] = metadata

    return metadata


def _mark_visited(
    state: AgentState,
    node_name: str,
) -> None:
    """Append visited node name to state metadata."""

    metadata = _ensure_metadata(state)

    visited_nodes = metadata.get(VISITED_NODES_KEY)

    if not isinstance(visited_nodes, list):
        visited_nodes = []
        metadata[VISITED_NODES_KEY] = visited_nodes

    visited_nodes.append(node_name)


def _append_warning(
    state: AgentState,
    warning: str,
) -> None:
    """Append warning to state."""

    warnings = state.get("warnings")

    if not isinstance(warnings, list):
        warnings = []
        state["warnings"] = warnings

    warnings.append(warning)


def _append_node_error(
    state: AgentState,
    *,
    node_name: str,
    exc: Exception,
) -> None:
    """Append node error to metadata."""

    metadata = _ensure_metadata(state)
    node_errors = metadata.get(NODE_ERRORS_KEY)

    if not isinstance(node_errors, list):
        node_errors = []
        metadata[NODE_ERRORS_KEY] = node_errors

    node_errors.append(
        {
            "node": node_name,
            "error_type": exc.__class__.__name__,
            "error_message": str(exc),
        }
    )


def _utc_now_iso() -> str:
    """Return current UTC timestamp."""

    return datetime.now(UTC).isoformat()

def _workflow_env_bool(
    name: str,
    *,
    default: bool = False,
) -> bool:
    """Read boolean env flag for workflow."""

    import os

    value = os.getenv(name, "").strip().lower()

    if not value:
        return default

    return value in {"1", "true", "yes", "on"}


def _state_current_module_for_quality_retrieval(
    state: dict[str, Any],
) -> str:
    """Return current module from workflow state."""

    for key in ("selected_module", "intent", "workflow_route"):
        value = state.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip().lower()

    metadata = state.get("metadata")

    if isinstance(metadata, dict):
        for key in (
            "llm_intent_applied_intent",
            "llm_intent",
            "retrieval_selected_module",
        ):
            value = metadata.get(key)

            if isinstance(value, str) and value.strip():
                return value.strip().lower()

    return ""


def _state_current_query_for_quality_retrieval(
    state: dict[str, Any],
) -> str:
    """Return current query text from workflow state."""

    for key in ("current_message", "user_message", "query", "message"):
        value = state.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

    messages = state.get("messages")

    if isinstance(messages, list) and messages:
        last_message = messages[-1]

        if isinstance(last_message, dict):
            content = last_message.get("content")

            if isinstance(content, str) and content.strip():
                return content.strip()

        if isinstance(last_message, str) and last_message.strip():
            return last_message.strip()

    return ""


def _try_real_quality_kb_retrieval(
    state: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    """Try real Quality KB retrieval and return updated state plus success."""

    if not _workflow_env_bool("QUALITY_KB_RETRIEVER_ENABLED", default=True):
        metadata = dict(state.get("metadata") or {})
        metadata["real_quality_kb_retriever_enabled"] = False

        next_state = dict(state)
        next_state["metadata"] = metadata

        return next_state, False

    current_module = _state_current_module_for_quality_retrieval(state)

    if current_module != "quality":
        return state, False

    query = _state_current_query_for_quality_retrieval(state)

    if not query:
        metadata = dict(state.get("metadata") or {})
        metadata["real_quality_kb_retriever_enabled"] = True
        metadata["real_quality_kb_retriever_used"] = False
        metadata["real_quality_kb_retriever_error"] = "empty query"

        next_state = dict(state)
        next_state["metadata"] = metadata

        return next_state, False

    try:
        retriever = QualityKBQdrantRetriever.from_env()
        retrieved_payloads = retriever.retrieve_payloads(query)
    except Exception as exc:
        metadata = dict(state.get("metadata") or {})
        metadata["real_quality_kb_retriever_enabled"] = True
        metadata["real_quality_kb_retriever_used"] = False
        metadata["real_quality_kb_retriever_error"] = (
            f"{type(exc).__name__}: {exc}"
        )

        next_state = dict(state)
        next_state["metadata"] = metadata

        return next_state, False

    if not retrieved_payloads:
        metadata = dict(state.get("metadata") or {})
        metadata["real_quality_kb_retriever_enabled"] = True
        metadata["real_quality_kb_retriever_used"] = False
        metadata["real_quality_kb_retriever_error"] = "no hits"

        next_state = dict(state)
        next_state["metadata"] = metadata

        return next_state, False

    metadata = dict(state.get("metadata") or {})
    metadata["real_quality_kb_retriever_enabled"] = True
    metadata["real_quality_kb_retriever_used"] = True
    metadata["real_quality_kb_retriever_error"] = None
    metadata["retrieval_source"] = "real_quality_kb"
    metadata["retrieval_selected_module"] = "quality"
    metadata["retrieval_collection_name"] = "quality_kb_v1"
    metadata["retrieval_hit_count"] = len(retrieved_payloads)

    next_state = dict(state)
    next_state["metadata"] = metadata
    next_state["retrieved_chunks"] = retrieved_payloads
    next_state["retrieval_selected_module"] = "quality"
    next_state["selected_module"] = "quality"

    return next_state, True

