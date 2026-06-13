"""Repair mojibake broken string literal blocks in workflow.py by line scan."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

WORKFLOW_FILE = Path("app/agent/workflow.py")


def repair_workflow() -> None:
    """Repair known broken string literal blocks."""

    content = WORKFLOW_FILE.read_text(encoding="utf-8")
    backup_file = WORKFLOW_FILE.with_name(
        f"workflow.before_mojibake_repair_v2_{datetime.now():%Y%m%d_%H%M%S}.py"
    )
    backup_file.write_text(content, encoding="utf-8")

    lines = content.splitlines()
    lines = repair_answer_text(lines)
    lines = replace_fallback_response_blocks(lines)
    lines = replace_llm_safety_rule_block(lines)
    lines = replace_tuple_block(
        lines=lines,
        marker="price_terms = (",
        replacement_items=[
            "多少钱",
            "价格",
            "报价",
            "单价",
            "折扣",
            "采购价",
        ],
    )
    lines = replace_tuple_block(
        lines=lines,
        marker="logistics_terms = (",
        replacement_items=[
            "物流",
            "发货",
            "到货",
            "运费",
            "快递",
            "几天发",
            "几天到",
            "时效",
        ],
    )
    lines = replace_module_signals_block(lines)

    WORKFLOW_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"backup={backup_file}")
    print("workflow.py mojibake literal repair v2 applied")


def repair_answer_text(lines: list[str]) -> list[str]:
    """Repair broken answer_text lines."""

    fixed: list[str] = []

    for line in lines:
        if 'next_state["answer_text"] =' in line and is_suspicious_line(line):
            indent = get_indent(line)
            fixed.append(
                indent
                + 'next_state["answer_text"] = '
                + '"系统处理当前问题时发生异常，请转人工确认。"'
            )
            continue

        fixed.append(line)

    return fixed


def replace_fallback_response_blocks(lines: list[str]) -> list[str]:
    """Replace fallback_response is None blocks."""

    fixed: list[str] = []
    index = 0

    while index < len(lines):
        line = lines[index]

        if line.strip() == "if fallback_response is None:":
            indent = get_indent(line)

            next_line = lines[index + 1] if index + 1 < len(lines) else ""

            if "fallback_response = (" in next_line:
                fixed.extend(
                    [
                        f"{indent}if fallback_response is None:",
                        f"{indent}    fallback_response = (",
                        f'{indent}        "当前信息不足，无法形成可靠答复。"',
                        f'{indent}        "请补充 SKU、数量、收货地区或具体问题后转人工确认。"',
                        f"{indent}    )",
                    ]
                )

                index += 2

                while index < len(lines):
                    if 'new_state["handoff_required"] = True' in lines[index]:
                        fixed.append(lines[index])
                        index += 1
                        break
                    index += 1

                continue

        fixed.append(line)
        index += 1

    return fixed


def replace_llm_safety_rule_block(lines: list[str]) -> list[str]:
    """Replace broken return list containing LLM safety rules."""

    fixed: list[str] = []
    index = 0

    while index < len(lines):
        line = lines[index]

        if line.strip() == "return [" and next_lines_contain(lines, index, "LLM"):
            indent = get_indent(line)
            fixed.extend(
                [
                    f"{indent}return [",
                    f'{indent}    "LLM 输出不是事实来源。",',
                    f'{indent}    "LLM 不得生成价格、库存、物流、质量或售后承诺。",',
                    f'{indent}    "最终结论必须以结构化数据、业务规则或人工确认为准。",',
                    f'{indent}    "证据不足时应拒答或转人工。",',
                    f"{indent}]",
                ]
            )

            index += 1

            while index < len(lines):
                if lines[index].strip() == "]":
                    index += 1
                    break
                index += 1

            continue

        fixed.append(line)
        index += 1

    return fixed


def replace_tuple_block(
    *,
    lines: list[str],
    marker: str,
    replacement_items: list[str],
) -> list[str]:
    """Replace a simple tuple block."""

    fixed: list[str] = []
    index = 0

    while index < len(lines):
        line = lines[index]

        if line.strip() == marker:
            indent = get_indent(line)
            fixed.append(f"{indent}{marker}")

            for item in replacement_items:
                fixed.append(f'{indent}    "{item}",')

            fixed.append(f"{indent})")

            index += 1

            while index < len(lines):
                if lines[index].strip() == ")":
                    index += 1
                    break
                index += 1

            continue

        fixed.append(line)
        index += 1

    return fixed


def replace_module_signals_block(lines: list[str]) -> list[str]:
    """Replace module_signals block."""

    fixed: list[str] = []
    index = 0

    while index < len(lines):
        line = lines[index]

        if line.strip() == "module_signals = {":
            indent = get_indent(line)
            fixed.extend(build_module_signals_lines(indent))

            index += 1

            while index < len(lines):
                if lines[index] == f"{indent}}}":
                    index += 1
                    break
                index += 1

            continue

        fixed.append(line)
        index += 1

    return fixed


def build_module_signals_lines(indent: str) -> list[str]:
    """Build module_signals lines."""

    return [
        f"{indent}module_signals = {{",
        f'{indent}    "price": [',
        f'{indent}        "多少钱",',
        f'{indent}        "价格",',
        f'{indent}        "报价",',
        f'{indent}        "单价",',
        f'{indent}        "折扣",',
        f'{indent}        "采购价",',
        f"{indent}    ],",
        f'{indent}    "logistics": [',
        f'{indent}        "物流",',
        f'{indent}        "快递",',
        f'{indent}        "发货",',
        f'{indent}        "多久",',
        f'{indent}        "运费",',
        f'{indent}        "到货",',
        f'{indent}        "时效",',
        f"{indent}    ],",
        f'{indent}    "quality": [',
        f'{indent}        "质量",',
        f'{indent}        "品质",',
        f'{indent}        "材质",',
        f'{indent}        "生锈",',
        f'{indent}        "掉漆",',
        f'{indent}        "坏",',
        f'{indent}        "耐用",',
        f'{indent}        "质保",',
        f'{indent}        "保修",',
        f'{indent}        "退",',
        f'{indent}        "换",',
        f'{indent}        "赔",',
        f"{indent}    ],",
        f'{indent}    "spec": [',
        f'{indent}        "规格",',
        f'{indent}        "型号",',
        f'{indent}        "螺纹",',
        f'{indent}        "杆长",',
        f'{indent}        "球径",',
        f'{indent}        "锥度",',
        f'{indent}        "OEM",',
        f'{indent}        "适配",',
        f"{indent}    ],",
        f"{indent}}}",
    ]


def next_lines_contain(lines: list[str], index: int, keyword: str) -> bool:
    """Return whether next few lines contain keyword."""

    end = min(index + 8, len(lines))
    return any(keyword in item for item in lines[index:end])


def is_suspicious_line(line: str) -> bool:
    """Return whether a line likely contains mojibake or broken quote."""

    return (
        line.count('"') % 2 != 0
        or "銆" in line
        or "€" in line
        or "绯" in line
        or "褰" in line
        or "鍏" in line
    )


def get_indent(line: str) -> str:
    """Return leading indentation."""

    return line[: len(line) - len(line.lstrip())]


if __name__ == "__main__":
    repair_workflow()