"""Patch prompts.py for classify_intent output requirements."""

from __future__ import annotations

from pathlib import Path


target = Path("app/agent/llm/prompts.py")
content = target.read_text(encoding="utf-8")

if 'if task_type == "classify_intent":' not in content:
    anchor = '    if task_type == "classify_answer_risk":\n'
    block = '''    if task_type == "classify_intent":
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

'''

    if anchor not in content:
        raise RuntimeError("classify_answer_risk anchor not found")

    content = content.replace(anchor, block + anchor, 1)

target.write_text(content, encoding="utf-8")

print("patched prompts.py classify_intent requirements")