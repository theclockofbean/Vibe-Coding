"""Patch grounded renderer to discard unsafe LLM rewrite notes."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
TARGET_FILE: Final[Path] = BACKEND_ROOT / "app/agent/rendering/grounded_renderer.py"

REPLACEMENTS: Final[tuple[tuple[str, str, str], ...]] = (
    (
        "typing import",
        "from typing import Any\n",
        "from typing import Any, Final\n",
    ),
    (
        "schema import",
        "from app.agent.llm.safety import LLMSafetyGuard\n",
        (
            "from app.agent.llm.safety import LLMSafetyGuard\n"
            "from app.agent.llm.schemas import (\n"
            "    DEFAULT_FORBIDDEN_COMMITMENTS,\n"
            "    detect_forbidden_commitments,\n"
            ")\n"
        ),
    ),
    (
        "extra forbidden constant",
        ")\n\n\n@dataclass(frozen=True)\nclass GroundedRenderer:",
        (
            ")\n\n\n"
            "LLM_REWRITE_FORBIDDEN_COMMITMENTS: Final[tuple[str, ...]] = (\n"
            "    *DEFAULT_FORBIDDEN_COMMITMENTS,\n"
            "    \"一定耐腐蚀\",\n"
            ")\n\n\n"
            "@dataclass(frozen=True)\nclass GroundedRenderer:"
        ),
    ),
    (
        "rewrite guard",
        (
            "    if render_input.selected_module in {\"price\", \"logistics\", \"quality\"}:\n"
            "        return \"处理建议：\" + _trim_text(llm_output, max_length=80)\n\n"
            "    if render_input.handoff_required:\n"
            "        return \"处理建议：\" + _trim_text(llm_output, max_length=80)\n"
        ),
        (
            "    rewrite_text = _trim_text(llm_output, max_length=80)\n\n"
            "    if _has_forbidden_llm_rewrite_fragment(rewrite_text):\n"
            "        return None\n\n"
            "    if render_input.selected_module in {\"price\", \"logistics\", \"quality\"}:\n"
            "        return \"处理建议：\" + rewrite_text\n\n"
            "    if render_input.handoff_required:\n"
            "        return \"处理建议：\" + rewrite_text\n"
        ),
    ),
    (
        "helper",
        "\n\ndef _build_response_sources(\n",
        (
            "\n\n"
            "def _has_forbidden_llm_rewrite_fragment(text: str) -> bool:\n"
            "    \"\"\"Return whether LLM rewrite text contains forbidden fragments.\"\"\"\n\n"
            "    return bool(\n"
            "        detect_forbidden_commitments(\n"
            "            text,\n"
            "            LLM_REWRITE_FORBIDDEN_COMMITMENTS,\n"
            "        )\n"
            "    )\n\n\n"
            "def _build_response_sources(\n"
        ),
    ),
)


def main() -> int:
    """Patch file."""

    errors: list[str] = []
    changes: list[str] = []

    content = TARGET_FILE.read_text(encoding="utf-8")
    original = content

    for label, old, new in REPLACEMENTS:
        if new in content:
            changes.append(f"{label} already patched")
            continue

        if old not in content:
            errors.append(f"{label} anchor not found")
            continue

        content = content.replace(old, new, 1)
        changes.append(f"patched {label}")

    if content != original and not errors:
        TARGET_FILE.write_text(content, encoding="utf-8")

    pprint({"changes": changes, "errors": errors})
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())