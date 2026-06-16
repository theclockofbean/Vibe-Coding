from pathlib import Path

path = Path("app/agent/workflow.py")
text = path.read_text(encoding="utf-8")

replacements = {
    '"价格", "报价", "多少钱", "批发价", "批发价格表", "实在价"': (
        '"价格", "报价", "报个价", "多少钱", "批发价", "批发价格表", "实在价"'
    ),
    '"质检报告、认证资料和实际文件需人工核验后提供。"': (
        '"质检报告、认证资料和实际文件需人工确认后提供，必要时请转人工或联系客服核验实际文件。"'
    ),
    '"已识别投诉场景，请转客服跟进处理"': (
        '"已识别投诉场景，请联系客服并转人工处理"'
    ),
}

changes = []
for old, new in replacements.items():
    if old not in text:
        changes.append({"old": old, "changed": False})
        continue
    text = text.replace(old, new, 1)
    changes.append({"old": old, "changed": True})

path.write_text(text, encoding="utf-8")
print({"changes": changes, "file": str(path)})