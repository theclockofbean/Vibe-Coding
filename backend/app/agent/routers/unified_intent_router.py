"""Unified intent router.

This module selects one Phase 1 business module for a raw user query.

It does not answer questions, query databases, call LLMs, call handlers,
call renderers, promise prices, promise logistics, promise quality, promise
returns/exchanges, promise compensation, or write data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal, TypeAlias


UnifiedModule: TypeAlias = Literal["spec", "price", "logistics", "quality"]
UnifiedIntentStatus: TypeAlias = Literal[
    "routed",
    "ambiguous",
    "unknown",
    "invalid_request",
]


SUPPORTED_MODULES: Final[tuple[UnifiedModule, ...]] = (
    "spec",
    "price",
    "logistics",
    "quality",
)

MODULE_ORDER: Final[dict[UnifiedModule, int]] = {
    "spec": 0,
    "price": 1,
    "logistics": 2,
    "quality": 3,
}

SIGNALS: Final[dict[UnifiedModule, tuple[str, ...]]] = {
    "price": (
        "多少钱",
        "多少元",
        "价格",
        "报价",
        "单价",
        "批发价",
        "优惠",
        "折扣",
        "便宜",
        "最低价",
        "含税",
        "税点",
        "付款",
        "账期",
        "采购价",
        "大货价",
    ),
    "logistics": (
        "几天发货",
        "多久发货",
        "几天发",
        "多久发",
        "发货",
        "现货",
        "库存",
        "有货",
        "缺货",
        "到货",
        "几天到",
        "运费",
        "邮费",
        "包邮",
        "快递",
        "物流",
        "承运商",
        "单号",
        "追踪",
        "加急",
        "当天发",
    ),
    "quality": (
        "会不会坏",
        "容易坏",
        "不容易坏",
        "质量问题",
        "质量",
        "品质",
        "做工",
        "耐用",
        "防锈",
        "生锈",
        "掉漆",
        "耐刮",
        "划痕",
        "瑕疵",
        "破损",
        "异响",
        "松动",
        "质保",
        "保修",
        "退货",
        "换货",
        "退换",
        "能退",
        "能换",
        "可以退",
        "可以换",
        "赔付",
        "赔偿",
        "赔",
        "补偿",
        "补发",
        "责任",
        "坏了",
    ),
    "spec": (
        "表面处理",
        "产品信息",
        "对照号",
        "规格",
        "参数",
        "尺寸",
        "大小",
        "多大",
        "螺纹",
        "牙距",
        "材质",
        "材料",
        "表面",
        "颜色",
        "杆长",
        "最长",
        "最大杆长",
        "最长杆长",
        "杆长最大",
        "杆长最长",
        "杆最长",
        "球径",
        "最大球径",
        "球径最大",
        "球头最大",
        "锥度",
        "OEM",
        "适配",
        "型号",
        "系列",
        "都一样",
        "夜光",
    ),
}


@dataclass(frozen=True)
class UnifiedIntentInput:
    """Input for unified intent routing."""

    text: str


@dataclass(frozen=True)
class UnifiedIntentResult:
    """Unified intent routing result."""

    raw_text: str
    normalized_text: str
    selected_module: UnifiedModule | None
    status: UnifiedIntentStatus
    confidence: float
    matched_signals: list[str]
    candidate_modules: list[UnifiedModule]
    warnings: list[str]
    errors: list[str]

    def to_dict(self) -> dict[str, object]:
        """Return serializable dictionary."""

        return {
            "raw_text": self.raw_text,
            "normalized_text": self.normalized_text,
            "selected_module": self.selected_module,
            "status": self.status,
            "confidence": self.confidence,
            "matched_signals": self.matched_signals,
            "candidate_modules": self.candidate_modules,
            "warnings": self.warnings,
            "errors": self.errors,
        }


class UnifiedIntentRouter:
    """Route raw user text to one supported Phase 1 module."""

    def route(
        self,
        request: str | UnifiedIntentInput,
    ) -> UnifiedIntentResult:
        """Route raw text to a supported module."""

        raw_text = request.text if isinstance(request, UnifiedIntentInput) else request
        normalized_text = self._normalize(raw_text)

        if normalized_text == "":
            return UnifiedIntentResult(
                raw_text=raw_text,
                normalized_text=normalized_text,
                selected_module=None,
                status="invalid_request",
                confidence=0.0,
                matched_signals=[],
                candidate_modules=[],
                warnings=[],
                errors=["text must not be blank"],
            )

        if len(raw_text) > 500:
            return UnifiedIntentResult(
                raw_text=raw_text,
                normalized_text=normalized_text,
                selected_module=None,
                status="invalid_request",
                confidence=0.0,
                matched_signals=[],
                candidate_modules=[],
                warnings=[],
                errors=["text length must be less than or equal to 500"],
            )

        matched_by_module = self._match_modules(normalized_text)
        candidate_modules = self._candidate_modules(matched_by_module)
        matched_signals = self._flatten_matched_signals(matched_by_module)

        if not candidate_modules:
            return UnifiedIntentResult(
                raw_text=raw_text,
                normalized_text=normalized_text,
                selected_module=None,
                status="unknown",
                confidence=0.0,
                matched_signals=[],
                candidate_modules=[],
                warnings=["no supported business intent detected"],
                errors=[],
            )

        selected_module = self._select_module(candidate_modules)

        if selected_module is None:
            return UnifiedIntentResult(
                raw_text=raw_text,
                normalized_text=normalized_text,
                selected_module=None,
                status="ambiguous",
                confidence=0.5,
                matched_signals=matched_signals,
                candidate_modules=candidate_modules,
                warnings=["multiple business intents detected"],
                errors=["ambiguous module routing"],
            )

        return UnifiedIntentResult(
            raw_text=raw_text,
            normalized_text=normalized_text,
            selected_module=selected_module,
            status="routed",
            confidence=self._confidence_for(
                matched_by_module=matched_by_module,
                selected_module=selected_module,
            ),
            matched_signals=matched_signals,
            candidate_modules=candidate_modules,
            warnings=[],
            errors=[],
        )

    @staticmethod
    def _normalize(text: str) -> str:
        """Normalize text for rule matching."""

        return (
            text.strip()
            .upper()
            .replace("×", "X")
            .replace("Ｘ", "X")
            .replace("＊", "*")
        )

    def _match_modules(
        self,
        normalized_text: str,
    ) -> dict[UnifiedModule, list[str]]:
        """Return matched signals grouped by module."""

        matched_by_module: dict[UnifiedModule, list[str]] = {
            module: [] for module in SUPPORTED_MODULES
        }

        for module, signals in SIGNALS.items():
            for signal in sorted(signals, key=len, reverse=True):
                normalized_signal = self._normalize(signal)

                if normalized_signal in normalized_text:
                    matched_by_module[module].append(signal)

        return matched_by_module

    @staticmethod
    def _candidate_modules(
        matched_by_module: dict[UnifiedModule, list[str]],
    ) -> list[UnifiedModule]:
        """Return modules with at least one matched signal."""

        modules = [
            module
            for module in SUPPORTED_MODULES
            if matched_by_module.get(module)
        ]

        return sorted(modules, key=lambda module: MODULE_ORDER[module])

    @staticmethod
    def _flatten_matched_signals(
        matched_by_module: dict[UnifiedModule, list[str]],
    ) -> list[str]:
        """Flatten matched signals while preserving module order."""

        signals: list[str] = []

        for module in SUPPORTED_MODULES:
            for signal in matched_by_module.get(module, []):
                if signal not in signals:
                    signals.append(signal)

        return signals

    @staticmethod
    def _select_module(
        candidate_modules: list[UnifiedModule],
    ) -> UnifiedModule | None:
        """Select final module from candidates."""

        non_spec_modules = [
            module for module in candidate_modules if module != "spec"
        ]

        if not non_spec_modules:
            return "spec"

        if len(non_spec_modules) == 1:
            return non_spec_modules[0]

        return None

    @staticmethod
    def _confidence_for(
        *,
        matched_by_module: dict[UnifiedModule, list[str]],
        selected_module: UnifiedModule,
    ) -> float:
        """Calculate simple deterministic confidence."""

        selected_signal_count = len(matched_by_module.get(selected_module, []))
        confidence = 0.65 + min(selected_signal_count, 3) * 0.1

        return min(confidence, 0.95)