"""Patch AgentState with LLM fields."""

from __future__ import annotations

from pathlib import Path


target = Path("app/agent/state.py")
content = target.read_text(encoding="utf-8")

if "llm_request:" not in content:
    anchor = "    metadata: dict[str, Any]\n"
    replacement = """    metadata: dict[str, Any]

    # LLM fields. LLM output is not a fact source and must not directly become
    # final_response.
    llm_request: dict[str, Any]
    llm_response: dict[str, Any]
    llm_output: str | None
    llm_safety_flags: list[str]
    llm_used: bool
    llm_error: str | None
"""
    if anchor not in content:
        raise RuntimeError("AgentState metadata anchor not found")

    content = content.replace(anchor, replacement)

target.write_text(content, encoding="utf-8")

print("patched AgentState LLM fields")