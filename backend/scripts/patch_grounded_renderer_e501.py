"""Patch grounded_renderer.py long line."""

from __future__ import annotations

from pathlib import Path


target = Path("app/agent/rendering/grounded_renderer.py")
content = target.read_text(encoding="utf-8")

old = '''        return (
            "质量、外观、耐久表现和使用结果不能仅由 RAG 或 LLM 判断，需以结构化资料、检测记录或人工确认为准。"
        )
'''

new = '''        return (
            "质量、外观、耐久表现和使用结果不能仅由 RAG 或 LLM 判断，"
            "需以结构化资料、检测记录或人工确认为准。"
        )
'''

if old not in content:
    raise RuntimeError("target long quality boundary line not found")

content = content.replace(old, new)
target.write_text(content, encoding="utf-8")

print("patched grounded_renderer.py E501")