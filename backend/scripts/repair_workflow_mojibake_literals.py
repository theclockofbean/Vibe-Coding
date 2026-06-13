"""Repair mojibake broken string literals in workflow.py."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Callable


WORKFLOW_FILE = Path("app/agent/workflow.py")


def repair_workflow_mojibake_literals() -> None:
    """Repair known broken Chinese string literal blocks."""

    content = WORKFLOW_FILE.read_text(encoding="utf-8")

    backup_file = WORKFLOW_FILE.with_name(
        f"workflow.before_mojibake_repair_{datetime.now():%Y%m%d_%H%M%S}.py"
    )
    backup_file.write_text(content, encoding="utf-8")

    replacements: dict[str, int] = {}

    content, replacements["answer_text"] = repair_answer_text_lines(content)
    content, replacements["fallback_response"] = replace_with_indent(
        content=content,
        pattern=(
            r"(?P<indent>\s*)if fallback_response is None:\n"
            r"(?P=indent)    fallback_response = \(\n"
            r"[\s\S]*?\n"
            r"(?P=indent)    \)\n"
            r"(?P=indent)new_state\[\"handoff_required\"\] = True"
        ),
        replacement_builder=build_fallback_response_replacement,
    )
    content, replacements["llm_safety_rules"] = replace_with_indent(
        content=content,
        pattern=(
            r"(?P<indent>\s*)return \[\n"
            r"(?P=indent)    \"LLM [\s\S]*?\n"
            r"(?P=indent)\]"
        ),
        replacement_builder=build_llm_safety_rules_replacement,
    )
    content, replacements["price_terms"] = replace_with_indent(
        content=content,
        pattern=r"(?P<indent>\s*)price_terms = \([\s\S]*?\n(?P=indent)\)",
        replacement_builder=build_price_terms_replacement,
    )
    content, replacements["logistics_terms"] = replace_with_indent(
        content=content,
        pattern=r"(?P<indent>\s*)logistics_terms = \([\s\S]*?\n(?P=indent)\)",
        replacement_builder=build_logistics_terms_replacement,
    )
    content, replacements["module_signals"] = replace_with_indent(
        content=content,
        pattern=r"(?P<indent>\s*)module_signals = \{[\s\S]*?\n(?P=indent)\}",
        replacement_builder=build_module_signals_replacement,
    )

    WORKFLOW_FILE.write_text(content, encoding="utf-8")

    print(f"backup={backup_file}")
    print(f"replacements={replacements}")


def repair_answer_text_lines(content: str) -> tuple[str, int]:
    """Repair broken next_state answer_text assignment lines."""

    fixed_lines: list[str] = []
    repaired_count = 0

    for line in content.splitlines():
        if (
            'next_state["answer_text"] =' in line
            and (
                line.count('"') % 2 != 0
                or "绯荤粺" in line
                or "异常" in line
            )
        ):
            indent = line[: len(line) - len(line.lstrip())]
            fixed_lines.append(
                indent
                + 'next_state["answer_text"] = '
                + '"系统处理当前问题时发生异常，请转人工确认。"'
            )
            repaired_count += 1
            continue

        fixed_lines.append(line)

    return "\n".join(fixed_lines) + "\n", repaired_count


def replace_with_indent(
    *,
    content: str,
    pattern: str,
    replacement_builder: Callable[[str], str],
) -> tuple[str, int]:
    """Replace one regex block while preserving indentation."""

    def repl(match: re.Match[str]) -> str:
        indent = match.group("indent")
        return replacement_builder(indent)

    return re.subn(pattern, repl, content, count=1)


def build_fallback_response_replacement(indent: str) -> str:
    """Build fallback response replacement."""

    return (
        f"{indent}if fallback_response is None:\n"
        f"{indent}    fallback_response = (\n"
        f'{indent}        "当前信息不足，无法形成可靠答复。"\n'
        f'{indent}        "请补充 SKU、数量、收货地区或具体问题后转人工确认。"\n'
        f"{indent}    )\n"
        f'{indent}new_state["handoff_required"] = True'
    )


def build_llm_safety_rules_replacement(indent: str) -> str:
    """Build LLM safety rules replacement."""

    return (
        f"{indent}return [\n"
        f'{indent}    "LLM 输出不是事实来源。",\n'
        f'{indent}    "LLM 不得生成价格、库存、物流、质量或售后承诺。",\n'
        f'{indent}    "最终结论必须以结构化数据、业务规则或人工确认为准。",\n'
        f'{indent}    "证据不足时应拒答或转人工。",\n'
        f"{indent}]"
    )


def build_price_terms_replacement(indent: str) -> str:
    """Build price terms replacement."""

    return (
        f"{indent}price_terms = (\n"
        f'{indent}    "多少钱",\n'
        f'{indent}    "价格",\n'
        f'{indent}    "报价",\n'
        f'{indent}    "单价",\n'
        f'{indent}    "折扣",\n'
        f'{indent}    "采购价",\n'
        f"{indent})"
    )


def build_logistics_terms_replacement(indent: str) -> str:
    """Build logistics terms replacement."""

    return (
        f"{indent}logistics_terms = (\n"
        f'{indent}    "物流",\n'
        f'{indent}    "发货",\n'
        f'{indent}    "到货",\n'
        f'{indent}    "运费",\n'
        f'{indent}    "快递",\n'
        f'{indent}    "几天发",\n'
        f'{indent}    "几天到",\n'
        f'{indent}    "时效",\n'
        f"{indent})"
    )


def build_module_signals_replacement(indent: str) -> str:
    """Build module signals replacement."""

    return (
        f"{indent}module_signals = {{\n"
        f'{indent}    "price": [\n'
        f'{indent}        "多少钱",\n'
        f'{indent}        "价格",\n'
        f'{indent}        "报价",\n'
        f'{indent}        "单价",\n'
        f'{indent}        "折扣",\n'
        f'{indent}        "采购价",\n'
        f"{indent}    ],\n"
        f'{indent}    "logistics": [\n'
        f'{indent}        "物流",\n'
        f'{indent}        "快递",\n'
        f'{indent}        "发货",\n'
        f'{indent}        "多久",\n'
        f'{indent}        "运费",\n'
        f'{indent}        "到货",\n'
        f'{indent}        "时效",\n'
        f"{indent}    ],\n"
        f'{indent}    "quality": [\n'
        f'{indent}        "质量",\n'
        f'{indent}        "品质",\n'
        f'{indent}        "材质",\n'
        f'{indent}        "生锈",\n'
        f'{indent}        "掉漆",\n'
        f'{indent}        "坏",\n'
        f'{indent}        "耐用",\n'
        f'{indent}        "质保",\n'
        f'{indent}        "保修",\n'
        f'{indent}        "退",\n'
        f'{indent}        "换",\n'
        f'{indent}        "赔",\n'
        f"{indent}    ],\n"
        f'{indent}    "spec": [\n'
        f'{indent}        "规格",\n'
        f'{indent}        "型号",\n'
        f'{indent}        "螺纹",\n'
        f'{indent}        "杆长",\n'
        f'{indent}        "球径",\n'
        f'{indent}        "锥度",\n'
        f'{indent}        "OEM",\n'
        f'{indent}        "适配",\n'
        f"{indent}    ],\n"
        f"{indent}}}"
    )


if __name__ == "__main__":
    repair_workflow_mojibake_literals()