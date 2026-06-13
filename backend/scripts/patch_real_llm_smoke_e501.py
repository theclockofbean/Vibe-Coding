"""Patch E501 long lines in check_real_llm_api_smoke.py."""

from __future__ import annotations

from pathlib import Path


target = Path("scripts/check_real_llm_api_smoke.py")
content = target.read_text(encoding="utf-8")

old_1 = '''                "summary": "铝合金 6061 常用于轻量化零件；该说明仅作为材料常识补充，不构成质量承诺。",
'''
new_1 = '''                "summary": (
                    "铝合金 6061 常用于轻量化零件；"
                    "该说明仅作为材料常识补充，不构成质量承诺。"
                ),
'''

old_2 = '''                "summary": "阳极氧化黑色是常见表面处理方式；具体外观和耐久表现需以检测记录或人工确认为准。",
'''
new_2 = '''                "summary": (
                    "阳极氧化黑色是常见表面处理方式；"
                    "具体外观和耐久表现需以检测记录或人工确认为准。"
                ),
'''

if old_1 not in content:
    raise RuntimeError("first long summary line not found")

if old_2 not in content:
    raise RuntimeError("second long summary line not found")

content = content.replace(old_1, new_1)
content = content.replace(old_2, new_2)

target.write_text(content, encoding="utf-8")

print("patched check_real_llm_api_smoke.py E501")