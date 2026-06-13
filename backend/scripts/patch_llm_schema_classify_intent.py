"""Patch LLM schema to support classify_intent."""

from __future__ import annotations

from pathlib import Path


target = Path("app/agent/llm/schemas.py")
content = target.read_text(encoding="utf-8")

if '"classify_intent"' not in content:
    old = '    "classify_answer_risk",\n'
    new = '    "classify_answer_risk",\n    "classify_intent",\n'

    if old not in content:
        raise RuntimeError("classify_answer_risk anchor not found")

    content = content.replace(old, new, 1)

target.write_text(content, encoding="utf-8")

print("patched LLMRequest supported task_type: classify_intent")