"""Fix workflow LLM intent fallback patch issues."""

from __future__ import annotations

from pathlib import Path


target = Path("app/agent/workflow.py")
content = target.read_text(encoding="utf-8")

# Current intent_node uses next_state, not new_state.
content = content.replace(
    "_apply_llm_intent_fallback_if_needed(new_state)",
    "_apply_llm_intent_fallback_if_needed(next_state)",
)

# Remove unused local import from _apply_llm_intent_fallback_if_needed.
content = content.replace(
    '''    import os

    from app.agent.llm.intent_classifier import (
''',
    '''    from app.agent.llm.intent_classifier import (
''',
    1,
)

# Add local os import where os.getenv is actually used.
old_env_bool = '''def _workflow_llm_intent_env_bool(
    key: str,
    *,
    default: bool,
) -> bool:
    """Read boolean env var."""

    value = os.getenv(key)
'''

new_env_bool = '''def _workflow_llm_intent_env_bool(
    key: str,
    *,
    default: bool,
) -> bool:
    """Read boolean env var."""

    import os

    value = os.getenv(key)
'''

if old_env_bool not in content:
    raise RuntimeError("workflow intent env bool block not found")

content = content.replace(old_env_bool, new_env_bool, 1)

target.write_text(content, encoding="utf-8")

print("fixed workflow LLM intent fallback patch")