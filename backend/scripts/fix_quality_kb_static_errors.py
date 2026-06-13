"""Fix static check issues introduced by Quality KB workflow patch."""

from __future__ import annotations

from pathlib import Path

WORKFLOW_FILE = Path("app/agent/workflow.py")
PATCH_FILE = Path("scripts/patch_workflow_quality_kb_retriever.py")
REPAIR_FILE = Path("scripts/repair_workflow_quality_kb_patch.py")


def fix_patch_script() -> None:
    """Remove unused marker variable from old patch script."""

    if not PATCH_FILE.exists():
        return

    content = PATCH_FILE.read_text(encoding="utf-8")
    content = content.replace('    marker = "from app.agent.rag"\n\n', "")
    PATCH_FILE.write_text(content, encoding="utf-8")


def fix_repair_script() -> None:
    """Make repair script ruff-safe."""

    if not REPAIR_FILE.exists():
        return

    content = REPAIR_FILE.read_text(encoding="utf-8")

    start = content.find("QUALITY_HOOK =")
    end_marker = '\n"""\n\n\ndef repair_workflow'

    if start >= 0 and end_marker in content[start:]:
        end = content.find(end_marker, start)

        replacement = (
            'QUALITY_HOOK = (\n'
            '    "        new_state, real_quality_kb_used = "\n'
            '    "_try_real_quality_kb_retrieval(new_state)\\n"\n'
            '    "        if real_quality_kb_used:\\n"\n'
            '    "            return new_state\\n\\n"\n'
            ')\n\n\n'
            'def repair_workflow'
        )

        content = content[:start] + replacement + content[end + len(end_marker) :]

    REPAIR_FILE.write_text(content, encoding="utf-8")


def fix_workflow_mypy() -> None:
    """Fix workflow.py mypy issues from dict / AgentState mix."""

    content = WORKFLOW_FILE.read_text(encoding="utf-8")

    old_call = (
        "        new_state = _copy_state(state)\n"
        "        new_state, real_quality_kb_used = "
        "_try_real_quality_kb_retrieval(new_state)\n"
        "        if real_quality_kb_used:\n"
        "            return new_state\n"
    )

    new_call = (
        "        new_state = _copy_state(state)\n"
        "        quality_state, real_quality_kb_used = "
        "_try_real_quality_kb_retrieval(\n"
        "            dict(new_state)\n"
        "        )\n"
        "        if real_quality_kb_used:\n"
        "            return cast(AgentState, quality_state)\n"
        "        new_state = cast(AgentState, quality_state)\n"
    )

    content = content.replace(old_call, new_call)

    content = content.replace(
        "def _state_current_module_for_quality_retrieval(\n"
        "    state: dict,\n"
        ") -> str:\n",
        "def _state_current_module_for_quality_retrieval(\n"
        "    state: dict[str, Any],\n"
        ") -> str:\n",
    )

    content = content.replace(
        "def _state_current_query_for_quality_retrieval(\n"
        "    state: dict,\n"
        ") -> str:\n",
        "def _state_current_query_for_quality_retrieval(\n"
        "    state: dict[str, Any],\n"
        ") -> str:\n",
    )

    content = content.replace(
        "def _try_real_quality_kb_retrieval(\n"
        "    state: dict,\n"
        ") -> tuple[dict, bool]:\n",
        "def _try_real_quality_kb_retrieval(\n"
        "    state: dict[str, Any],\n"
        ") -> tuple[dict[str, Any], bool]:\n",
    )

    fixed_lines: list[str] = []

    for line in content.splitlines():
        if (
            '["workflow_route"] =' in line
            and "typeddict-unknown-key" not in line
        ):
            line = f"{line}  # type: ignore[typeddict-unknown-key]"

        fixed_lines.append(line)

    WORKFLOW_FILE.write_text("\n".join(fixed_lines) + "\n", encoding="utf-8")


def main() -> int:
    """Run fixes."""

    fix_patch_script()
    fix_repair_script()
    fix_workflow_mypy()

    print("quality KB static check fixes applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())