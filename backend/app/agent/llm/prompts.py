"""Prompt builders for LLM clients."""

from __future__ import annotations

import json
from typing import Any

from app.agent.llm.schemas import LLMRequest

SYSTEM_SAFETY_INSTRUCTION = """你是一个受控业务客服辅助模型。

必须遵守：
1. 你不是事实来源。
2. 你不是业务承诺来源。
3. 不得生成价格、折扣、成交价、物流时效、质量保证、售后赔付等未经授权承诺。
4. 只能基于输入中的结构化事实、RAG 证据和业务规则进行表达辅助。
5. 如果信息不足，必须说明需要人工确认。
6. 输出必须简短、清晰、可审计。
"""


def build_openai_compatible_messages(
    request: LLMRequest,
) -> list[dict[str, str]]:
    """Build OpenAI-compatible chat messages."""

    user_payload: dict[str, Any] = {
        "task_type": request.task_type,
        "user_text": request.user_text,
        "developer_instruction": request.developer_instruction,
        "context_blocks": request.context_blocks,
        "retrieved_chunks": request.retrieved_chunks,
        "structured_facts": request.structured_facts,
        "business_rules": request.business_rules,
        "forbidden_commitments": request.forbidden_commitments,
        "metadata": request.metadata,
        "output_requirements": _output_requirements_for_task(request.task_type),
    }

    return [
        {
            "role": "system",
            "content": SYSTEM_SAFETY_INSTRUCTION,
        },
        {
            "role": "user",
            "content": json.dumps(
                user_payload,
                ensure_ascii=False,
                default=str,
            ),
        },
    ]


def _output_requirements_for_task(
    task_type: str,
) -> dict[str, Any]:
    """Return task-specific output requirements."""

    if task_type == "classify_intent":
        return {
            "format": "json_object",
            "requirements": [
                "只输出 JSON，不要输出 Markdown。",
                "intent 必须是 spec、price、logistics、quality、general、escalation 之一。",
                "confidence 必须是 0 到 1 的数字。",
                "reason 必须简短说明分类依据。",
                "不得生成业务回答。",
                "不得生成价格、物流、质量或售后承诺。",
            ],
            "schema": {
                "intent": "quality",
                "confidence": 0.82,
                "reason": "用户询问产品质量表现",
            },
        }

    if task_type == "classify_answer_risk":
        return {
            "format": "plain_text",
            "requirements": [
                "判断输入是否存在价格、物流、质量、售后等未授权承诺风险。",
                "不得生成业务回答。",
            ],
        }

    if task_type == "draft_handoff_note":
        return {
            "format": "plain_text",
            "requirements": [
                "生成简短人工接管说明。",
                "不得新增事实。",
                "不得新增价格或承诺。",
            ],
        }

    if task_type == "summarize_evidence":
        return {
            "format": "plain_text",
            "requirements": [
                "基于结构化事实和 RAG 证据做非承诺性说明。",
                "不得新增事实。",
                "不得生成质量保证、物流保证、价格承诺或售后承诺。",
            ],
        }

    if task_type == "rewrite_safe_answer":
        return {
            "format": "plain_text",
            "requirements": [
                "在不改变事实的前提下优化表达。",
                "不得新增事实。",
                "不得新增业务承诺。",
            ],
        }

    return {
        "format": "plain_text",
        "requirements": [
            "只做安全、简短、非承诺性表达。",
        ],
    }