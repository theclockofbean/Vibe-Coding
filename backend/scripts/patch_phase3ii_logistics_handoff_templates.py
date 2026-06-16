"""Add logistics-specific handoff templates for Phase 3-II evaluation."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint

WORKFLOW_FILE = Path("app/agent/workflow.py")


OLD_CALL_SITE = '''    unsupported_thread = _answer_strategy_unsupported_thread_spec(
        metadata=metadata,
        state=state,
    )

    if unsupported_thread is not None:
'''


NEW_CALL_SITE = '''    logistics_response = _answer_strategy_logistics_handoff_response(
        metadata=metadata,
        state=state,
    )

    if logistics_response is not None:
        return logistics_response

    unsupported_thread = _answer_strategy_unsupported_thread_spec(
        metadata=metadata,
        state=state,
    )

    if unsupported_thread is not None:
'''


HELPER = '''def _answer_strategy_logistics_handoff_response(
    *,
    metadata: dict[str, Any],
    state: Any | None,
) -> str | None:
    """Build logistics-specific handoff response."""

    candidate_modules = _as_text_list(metadata.get("answer_candidate_modules"))
    primary_module = str(metadata.get("answer_primary_module") or "")
    selected_module = str(
        metadata.get("selected_module")
        or metadata.get("retrieval_selected_module")
        or ""
    )

    query_text = _answer_strategy_query_text(state)

    if query_text is None:
        query_text = _answer_strategy_query_text(metadata)

    query_text = query_text or ""

    logistics_terms = (
        "物流",
        "发货",
        "快递",
        "顺丰",
        "运费",
        "差价",
        "补多少钱",
        "到货",
        "澳门",
        "新疆",
        "包装破损",
        "外包装破损",
        "运费谁承担",
    )

    is_logistics = (
        primary_module == "logistics"
        or selected_module == "logistics"
        or "logistics" in candidate_modules
        or any(term in query_text for term in logistics_terms)
    )

    if not is_logistics:
        return None

    if "澳门" in query_text:
        return (
            "澳门属于港澳台或特殊地区配送场景，当前未完成业务核验，"
            "不能直接确认是否可发或给出确定性承诺。"
            "请转人工结合正式物流规则、承运商覆盖范围和订单信息处理。"
        )

    if "外包装破损" in query_text or "包装破损" in query_text or "破损" in query_text:
        return (
            "该问题属于物流破损处理场景。请先保留外包装、面单和商品状态，"
            "并补充照片、视频等凭证。"
            "物流破损责任和后续处理需转人工结合承运商记录、签收状态和售后规则确认。"
        )

    if "退换货" in query_text or "退货" in query_text or "换货" in query_text:
        return (
            "该问题涉及售后处理和运费承担规则，当前未完成业务核验，"
            "不能直接承诺由哪一方承担运费。"
            "请转人工结合订单、质量问题凭证、售后规则和物流记录确认。"
        )

    if (
        "新疆" in query_text
        or "差价" in query_text
        or "补多少钱" in query_text
        or "顺丰" in query_text
    ):
        return (
            "该问题涉及物流附加费或承运商变更，当前未完成业务核验，"
            "不能输出补差金额，也不能给出金额承诺。"
            "如涉及新疆等地区，请转人工结合地址、重量体积、承运商规则和正式报价确认。"
        )

    return None


'''


def main() -> int:
    content = WORKFLOW_FILE.read_text(encoding="utf-8")
    changes: list[str] = []
    errors: list[str] = []

    if OLD_CALL_SITE in content:
        content = content.replace(OLD_CALL_SITE, NEW_CALL_SITE, 1)
        changes.append("wired logistics handoff response before generic safety response")
    elif "_answer_strategy_logistics_handoff_response(" in content:
        changes.append("logistics handoff response already wired")
    else:
        errors.append("logistics handoff call-site anchor not found")

    if "def _answer_strategy_logistics_handoff_response(" not in content:
        anchor = "def _answer_strategy_unsupported_thread_spec("
        if anchor not in content:
            errors.append("unsupported thread helper anchor not found")
        else:
            content = content.replace(anchor, HELPER + anchor, 1)
            changes.append("added logistics handoff response helper")
    else:
        changes.append("logistics handoff response helper already present")

    if not errors:
        WORKFLOW_FILE.write_text(content, encoding="utf-8")

    pprint({"changes": changes, "errors": errors})
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())