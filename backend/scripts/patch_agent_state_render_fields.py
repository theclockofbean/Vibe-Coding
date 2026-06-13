"""Patch AgentState with grounded render fields."""

from __future__ import annotations

from pathlib import Path


target = Path("app/agent/state.py")
content = target.read_text(encoding="utf-8")

if "render_input:" not in content:
    anchor = "    llm_error: str | None\n"
    replacement = """    llm_error: str | None

    # Grounded render fields. Grounded render output is the audited final
    # response layer.
    render_input: dict[str, Any]
    render_output: dict[str, Any]
    response_sources: list[dict[str, Any]]
    response_warnings: list[str]
    render_risk_flags: list[str]
    render_used_llm_output: bool
    is_grounded_response: bool
"""
    if anchor not in content:
        raise RuntimeError("AgentState llm_error anchor not found")

    content = content.replace(anchor, replacement)

target.write_text(content, encoding="utf-8")

print("patched AgentState render fields")