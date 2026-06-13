"""Patch OpenAICompatibleLLMClient error model fallback."""

from __future__ import annotations

from pathlib import Path


target = Path("app/agent/llm/openai_compatible.py")
content = target.read_text(encoding="utf-8")

old = 'model=self._config.model or "",'
new = 'model=self._config.model or "unknown",'

if old not in content:
    raise RuntimeError("target model fallback line not found")

content = content.replace(old, new)

target.write_text(content, encoding="utf-8")

print("patched OpenAICompatibleLLMClient model fallback")