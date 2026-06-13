"""Patch quality real LLM rendering smoke cases.

This patch is tolerant of different run_workflow_case implementations.
It makes quality smoke cases explicitly quality-oriented and forces the
low-confidence LLM intent fallback for this check script only.
"""

from __future__ import annotations

from pathlib import Path


target = Path("scripts/check_quality_real_llm_rendering.py")
content = target.read_text(encoding="utf-8")

case_replacements = {
    'user_text="SKU001 材质是不是铝合金6061？",':
    'user_text="SKU001 从质量资料角度看，材质是不是铝合金6061？",',

    'user_text="SKU001 表面处理是什么？质量上怎么理解？",':
    'user_text="SKU001 表面处理是什么？从质量资料角度怎么理解？",',

    'user_text="SKU001 阳极氧化黑色有什么说明？",':
    'user_text="SKU001 从质量资料角度看，阳极氧化黑色有什么说明？",',

    'user_text="SKU001 这个换挡球头的材质和表面处理说明一下",':
    'user_text="SKU001 从质量资料角度说明这个换挡球头的材质和表面处理",',

    'user_text="SKU001 这款适合做轻量化零件吗？",':
    'user_text="SKU001 从材料质量说明角度看，这款适合做轻量化零件吗？",',
}

for old, new in case_replacements.items():
    if old in content:
        content = content.replace(old, new)

start = content.index("def run_workflow_case(")

try:
    end = content.index("\ndef count_db_side_effects(", start)
except ValueError as exc:
    raise RuntimeError("count_db_side_effects anchor not found") from exc

new_run_workflow_case = '''def run_workflow_case(
    *,
    session_id: str,
    user_text: str,
) -> AgentState:
    """Run one workflow case.

    Quality smoke cases force the low-confidence LLM intent classifier so this
    script verifies the quality rendering path instead of being intercepted by
    spec/material lookup routing.
    """

    initial_state: AgentState = {
        "session_id": session_id,
        "channel": "quality_real_llm_rendering_check",
        "user_id": "quality-real-llm-rendering-check-user",
        "user_text": user_text,
        "metadata": {
            "force_llm_intent_classifier": True,
        },
    }

    session_factory = get_session_factory()

    with session_factory() as session:
        product_repository = ProductRepository(session)
        conversation_repository = ConversationRepository(session)

        return run_agent_workflow(
            initial_state=initial_state,
            product_repository=product_repository,
            conversation_repository=conversation_repository,
            limit=5,
        )

'''

content = content[:start] + new_run_workflow_case + content[end + 1:]

target.write_text(content, encoding="utf-8")

print("patched quality real LLM rendering smoke cases")