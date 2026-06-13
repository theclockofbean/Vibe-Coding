"""Patch LLMSafetyGuard price regex false positives."""

from __future__ import annotations

from pathlib import Path


target = Path("app/agent/llm/safety.py")
content = target.read_text(encoding="utf-8")

old = '''        (
            "unauthorized_price_commitment",
            "LLM 输出疑似包含未授权价格或优惠承诺。",
            (
                r"(最低价|底价|优惠价|折扣价|成交价).{0,12}(给你|可以|确认|就是|包邮|成交)",
                r"(\\d+(\\.\\d+)?\\s*元|￥\\s*\\d+(\\.\\d+)?).{0,12}(成交|包邮|给你|可以|直接)",
                r"(包邮).{0,8}(成交|直接|可以)",
                r"(直接).{0,8}(成交|报价|下单)",
            ),
        ),
'''

new = '''        (
            "unauthorized_price_commitment",
            "LLM 输出疑似包含未授权价格或优惠承诺。",
            (
                r"(最低价|底价|优惠价|折扣价|成交价).{0,12}(给你|就是|包邮|成交)",
                r"(\\d+(\\.\\d+)?\\s*元|￥\\s*\\d+(\\.\\d+)?).{0,12}(成交|包邮|给你|可以|直接)",
                r"(包邮).{0,8}(成交|直接|可以)",
                r"(?<!不能)直接.{0,8}(成交|下单)",
            ),
        ),
'''

if old not in content:
    raise RuntimeError("target price regex block not found")

content = content.replace(old, new)
target.write_text(content, encoding="utf-8")

print("patched LLMSafetyGuard price false positives")