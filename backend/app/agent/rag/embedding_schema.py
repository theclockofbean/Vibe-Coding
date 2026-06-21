from typing import Dict, Any


def build_embedding_text(record: Dict[str, Any]) -> str:
    """
    统一 RAG embedding 输入 schema
    所有 QA / SKU / PRICE / LOGISTICS 必须走这里
    """

    record_type = record.get("record_type", "unknown")
    domain = record.get("domain", "general")

    # QA / PRICE / LOGISTICS / QUALITY
    if record_type == "qa":
        return "\n".join([
            "【知识类型】QA",
            f"【业务域】{domain}",
            f"【问题】{record.get('question_normalized') or record.get('question_raw','')}",
            f"【标准答案】{record.get('answer_standard','')}",
            f"【意图】{record.get('intent_subtype','')}",
            f"【关联SKU】{';'.join(record.get('related_sku_ids', []) or [])}",
            f"【风险】{';'.join(record.get('risk_flags', []) or [])}",
        ])

    # SKU 主数据
    if record_type == "sku":
        return "\n".join([
            "【知识类型】SKU",
            f"【业务域】{domain}",
            f"【SKU】{record.get('sku_id','')}",
            f"【产品】{record.get('product_name','')}",
            f"【螺纹】{record.get('thread_spec','')}",
            f"【杆长】{record.get('rod_length_mm','')}",
            f"【球径】{record.get('ball_diameter_mm','')}",
            f"【材质】{record.get('material','')}",
        ])

    # fallback（极少情况）
    return record.get("text") or str(record)
