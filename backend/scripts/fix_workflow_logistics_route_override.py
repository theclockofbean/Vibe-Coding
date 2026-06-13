"""Add logistics route override for delivery-time questions."""

from __future__ import annotations

from pathlib import Path

WORKFLOW_FILE = Path("app/agent/workflow.py")


def main() -> int:
    """Patch workflow with logistics route override."""

    content = WORKFLOW_FILE.read_text(encoding="utf-8")

    if "def _force_logistics_route_for_delivery_question" in content:
        print("workflow.py already contains logistics route override")
        return 0

    content = insert_route_override_call(content)
    content = append_route_override_helper(content)

    WORKFLOW_FILE.write_text(content, encoding="utf-8")

    print("workflow.py logistics route override fixed")
    return 0


def insert_route_override_call(content: str) -> str:
    """Insert route override before real Logistics KB retrieval."""

    old = (
        "        logistics_state, real_logistics_kb_used = "
        "_try_real_logistics_kb_retrieval(dict(new_state))\n"
    )

    new = '''    new_state = _force_logistics_route_for_delivery_question(new_state)
    logistics_state, real_logistics_kb_used = _try_real_logistics_kb_retrieval(dict(new_state))
'''

    if old not in content:
        raise RuntimeError("logistics retrieval hook line not found")

    return content.replace(old, new, 1)


def append_route_override_helper(content: str) -> str:
    """Append route override helper."""

    helper = r'''


def _force_logistics_route_for_delivery_question(
    state: AgentState,
) -> AgentState:
    """Force logistics route for delivery-time logistics questions."""

    query = _state_current_query_for_logistics_retrieval(dict(state))
    normalized_query = query.strip().lower()

    logistics_signals = (
        "物流",
        "快递",
        "发货",
        "到货",
        "能到",
        "几天到",
        "几天能到",
        "大概几天",
        "时效",
        "运费",
        "包邮",
        "发浙江",
        "发广东",
        "发上海",
        "发北京",
        "发江苏",
        "发山东",
        "发福建",
        "发四川",
        "发重庆",
        "发河北",
        "发河南",
        "发安徽",
    )

    if not any(signal in normalized_query for signal in logistics_signals):
        return state

    new_state = dict(state)
    metadata = _ensure_metadata(new_state)

    new_state["intent"] = "logistics"
    new_state["selected_module"] = "logistics"
    new_state["candidate_modules"] = ["logistics"]

    metadata["logistics_route_override_used"] = True
    metadata["logistics_route_override_reason"] = "delivery_or_shipping_signal"

    return cast(AgentState, new_state)
'''

    return content.rstrip() + helper + "\n"


if __name__ == "__main__":
    raise SystemExit(main())