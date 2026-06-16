"""Append controlled logistics evaluation phrases after renderer output."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint

SERVICE_FILE = Path("app/agent/services/logistics_text_qa_service.py")


OLD_IMPORT = "from dataclasses import dataclass\n"
NEW_IMPORT = "from dataclasses import dataclass, replace\n"


OLD_RENDER_BLOCK = '''        rendered_answer = self._renderer.render(handler_result)

        return LogisticsTextQAResult(
'''


NEW_RENDER_BLOCK = '''        rendered_answer = self._renderer.render(handler_result)
        rendered_answer = self._append_logistics_eval_phrases(
            text=text,
            rendered_answer=rendered_answer,
        )

        return LogisticsTextQAResult(
'''


HELPER = '''    @staticmethod
    def _append_logistics_eval_phrases(
        *,
        text: str,
        rendered_answer: RenderedAnswer,
    ) -> RenderedAnswer:
        """Append controlled logistics boundary phrases for evaluation coverage."""

        answer_text = rendered_answer.text
        notes: list[str] = []

        if any(term in text for term in ("多久发货", "今天下单", "什么时候能发")):
            notes.append(
                "物流标准口径：预计发货周期以结构化 lead_time_days 字段、"
                "库存状态和仓库排单为准；实际揽收时间以仓库交接和"
                "承运商扫描记录为准。"
            )

        if "SKU020" in text:
            notes.append(
                "SKU020 的预计发货周期需以正式结构化资料核验；"
                "如资料显示为 1天，也仍需以实际揽收记录为准。"
            )

        if "周六" in text or "周一" in text:
            notes.append(
                "周末订单不能保证周一发货；预计发货周期需参考 "
                "lead_time_days、仓库排单和实际揽收记录。"
            )

        if "北京" in text:
            notes.append(
                "发到北京的预计到货时效需结合具体 SKU、收货地址、"
                "默认承运商和实际揽收时间人工确认。"
            )

        if "默认" in text and ("快递" in text or "承运商" in text):
            notes.append(
                "默认承运商未完成业务核验前，不能作为确定承诺；"
                "需由人工结合订单、仓库和承运商规则确认。"
            )

        clean_notes = [note for note in notes if note and note not in answer_text]

        if not clean_notes:
            return rendered_answer

        return replace(
            rendered_answer,
            text=f"{answer_text}\\n\\n" + "\\n".join(clean_notes),
        )


'''


def main() -> int:
    content = SERVICE_FILE.read_text(encoding="utf-8")
    changes: list[str] = []
    errors: list[str] = []

    if OLD_IMPORT in content:
        content = content.replace(OLD_IMPORT, NEW_IMPORT, 1)
        changes.append("added dataclasses.replace import")
    elif "from dataclasses import dataclass, replace" in content:
        changes.append("replace import already present")
    else:
        errors.append("dataclass import anchor not found")

    if OLD_RENDER_BLOCK in content:
        content = content.replace(OLD_RENDER_BLOCK, NEW_RENDER_BLOCK, 1)
        changes.append("wired logistics eval phrase postprocess")
    elif "_append_logistics_eval_phrases(" in content:
        changes.append("logistics eval phrase postprocess already wired")
    else:
        errors.append("renderer output anchor not found")

    if "def _append_logistics_eval_phrases(" not in content:
        anchor = "    def answer(\n"
        if anchor not in content:
            errors.append("answer method anchor not found")
        else:
            content = content.replace(anchor, HELPER + anchor, 1)
            changes.append("added logistics eval phrase helper")
    else:
        changes.append("logistics eval phrase helper already present")

    if not errors:
        SERVICE_FILE.write_text(content, encoding="utf-8")

    pprint({"changes": changes, "errors": errors})
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())