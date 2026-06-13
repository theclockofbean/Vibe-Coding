"""Unified KB routing helper for Quality / Logistics / Price / Spec."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Final


MODULE_COLLECTIONS: Final[dict[str, str]] = {
    "quality": "quality_kb_v1",
    "logistics": "logistics_kb_v1",
    "price": "price_kb_v1",
    "spec": "spec_kb_v1",
}

MODULE_SOURCES: Final[dict[str, str]] = {
    "quality": "real_quality_kb",
    "logistics": "real_logistics_kb",
    "price": "real_price_kb",
    "spec": "real_spec_kb",
}

PRICE_SIGNALS: Final[tuple[str, ...]] = (
    "多少钱",
    "价格",
    "报价",
    "直接报价",
    "便宜",
    "优惠",
    "折扣",
    "最低价",
    "全网最低",
    "含税",
    "包税",
)

LOGISTICS_SIGNALS: Final[tuple[str, ...]] = (
    "发货",
    "能发",
    "今天发",
    "今天能发",
    "当天发",
    "当天能发",
    "到货",
    "明天到",
    "多久能到",
    "几天能到",
    "几天到",
    "大概几天",
    "发到",
    "发浙江",
    "发广东",
    "发江苏",
    "发上海",
    "发北京",
    "运费",
    "包邮",
    "物流",
    "赔",
    "赔付",
    "补发",
)

SPEC_SIGNALS: Final[tuple[str, ...]] = (
    "sku",
    "oem",
    "规格",
    "螺纹",
    "球径",
    "杆长",
    "锥度",
    "适配",
    "通用",
    "现货规格",
    "m8",
    "m10",
    "m12",
)

SPEC_HIGH_RISK_SIGNALS: Final[tuple[str, ...]] = (
    "万能适配",
    "通用适配",
    "一定适配",
    "保证适配",
    "百分百适配",
    "全部车型",
)

SPEC_FITMENT_SIGNALS: Final[tuple[str, ...]] = (
    "适配",
    "车型",
    "车款",
    "兼容",
    "装车",
    "能不能用",
)

QUALITY_SIGNALS: Final[tuple[str, ...]] = (
    "质量",
    "材质",
    "不锈钢",
    "表面处理",
    "生锈",
    "十万公里",
    "耐用",
    "检测",
    "保证质量",
)

MODULE_ORDER: Final[tuple[str, ...]] = (
    "price",
    "spec",
    "logistics",
    "quality",
)


@dataclass(frozen=True)
class KBRoutingDecision:
    """Unified KB routing decision."""

    selected_module: str | None
    candidate_modules: list[str]
    conflict_type: str | None
    matched_signals: dict[str, list[str]] = field(default_factory=dict)
    reason: str = ""
    risk_tags: list[str] = field(default_factory=list)

    @property
    def retrieval_source(self) -> str | None:
        """Return retrieval source for selected module."""

        if self.selected_module is None:
            return None

        return MODULE_SOURCES.get(self.selected_module)

    @property
    def retrieval_collection_name(self) -> str | None:
        """Return collection name for selected module."""

        if self.selected_module is None:
            return None

        return MODULE_COLLECTIONS.get(self.selected_module)

    def to_metadata(self) -> dict[str, Any]:
        """Return normalized workflow metadata."""

        return {
            "retrieval_selected_module": self.selected_module,
            "retrieval_source": self.retrieval_source,
            "retrieval_collection_name": self.retrieval_collection_name,
            "retrieval_hit_count": None,
            "routing_conflict_type": self.conflict_type,
            "routing_candidate_modules": self.candidate_modules,
            "routing_matched_signals": self.matched_signals,
            "routing_reason": self.reason,
            "routing_risk_tags": self.risk_tags,
        }


def route_query_to_kb(
    query: str,
) -> KBRoutingDecision:
    """Route one query to the safest primary KB module."""

    normalized_query = normalize_query(query)
    matched_signals = collect_matched_signals(normalized_query)
    candidate_modules = [
        module
        for module in MODULE_ORDER
        if matched_signals[module]
    ]

    selected_module = select_module(
        matched_signals=matched_signals,
        candidate_modules=candidate_modules,
    )

    conflict_type = build_conflict_type(
        selected_module=selected_module,
        candidate_modules=candidate_modules,
        matched_signals=matched_signals,
    )

    reason = build_reason(
        selected_module=selected_module,
        matched_signals=matched_signals,
    )

    risk_tags = build_risk_tags(
        selected_module=selected_module,
        matched_signals=matched_signals,
    )

    return KBRoutingDecision(
        selected_module=selected_module,
        candidate_modules=candidate_modules,
        conflict_type=conflict_type,
        matched_signals=matched_signals,
        reason=reason,
        risk_tags=risk_tags,
    )


def normalize_query(
    query: str,
) -> str:
    """Normalize query for rule matching."""

    return query.strip().lower().replace("×", "x")


def collect_matched_signals(
    normalized_query: str,
) -> dict[str, list[str]]:
    """Collect matched module signals."""

    return {
        "price": match_signals(
            normalized_query=normalized_query,
            signals=PRICE_SIGNALS,
        ),
        "spec": match_signals(
            normalized_query=normalized_query,
            signals=SPEC_SIGNALS + SPEC_HIGH_RISK_SIGNALS,
        ),
        "logistics": match_signals(
            normalized_query=normalized_query,
            signals=LOGISTICS_SIGNALS,
        ),
        "quality": match_signals(
            normalized_query=normalized_query,
            signals=QUALITY_SIGNALS,
        ),
    }


def match_signals(
    *,
    normalized_query: str,
    signals: tuple[str, ...],
) -> list[str]:
    """Return matched signals."""

    return [
        signal
        for signal in signals
        if signal.lower() in normalized_query
    ]


def select_module(
    *,
    matched_signals: dict[str, list[str]],
    candidate_modules: list[str],
) -> str | None:
    """Select safest primary module."""

    if not candidate_modules:
        return None

    if has_any_signal(matched_signals=matched_signals, signals=SPEC_HIGH_RISK_SIGNALS):
        return "spec"

    if has_any_signal(matched_signals=matched_signals, signals=SPEC_FITMENT_SIGNALS):
        return "spec"

    if matched_signals["price"]:
        return "price"

    if matched_signals["logistics"]:
        return "logistics"

    if (
        matched_signals["quality"]
        and is_identifier_only_spec_signal(matched_signals.get("spec", []))
    ):
        return "quality"

    if matched_signals["spec"]:
        return "spec"

    if matched_signals["quality"]:
        return "quality"

    return None


def has_any_signal(
    *,
    matched_signals: dict[str, list[str]],
    signals: tuple[str, ...],
) -> bool:
    """Return whether any exact high-risk signal matched."""

    matched = {
        signal
        for values in matched_signals.values()
        for signal in values
    }

    return any(signal in matched for signal in signals)


def build_conflict_type(
    *,
    selected_module: str | None,
    candidate_modules: list[str],
    matched_signals: dict[str, list[str]],
) -> str | None:
    """Build selected-module-first conflict type."""

    if selected_module is None:
        return None

    secondary_module = select_conflict_secondary_module(
        selected_module=selected_module,
        candidate_modules=candidate_modules,
        matched_signals=matched_signals,
    )

    if secondary_module is None:
        return selected_module

    return f"{selected_module}_{secondary_module}"


def select_conflict_secondary_module(
    *,
    selected_module: str,
    candidate_modules: list[str],
    matched_signals: dict[str, list[str]],
) -> str | None:
    """Select most meaningful secondary module for conflict type."""

    other_modules = [
        module
        for module in candidate_modules
        if module != selected_module
    ]

    if not other_modules:
        return None

    if "quality" in other_modules and is_identifier_only_spec_signal(
        matched_signals.get("spec", [])
    ):
        return "quality"

    if selected_module == "price":
        for module in ("quality", "logistics", "spec"):
            if module in other_modules:
                return module

    if selected_module == "logistics":
        for module in ("quality", "spec", "price"):
            if module in other_modules:
                return module

    if selected_module == "spec":
        for module in ("logistics", "quality", "price"):
            if module in other_modules:
                return module

    return other_modules[0]


def is_identifier_only_spec_signal(
    spec_signals: list[str],
) -> bool:
    """Return whether spec match is only SKU/OEM identifier noise."""

    if not spec_signals:
        return False

    identifier_signals = {"sku", "oem"}

    return set(spec_signals) <= identifier_signals


def build_reason(
    *,
    selected_module: str | None,
    matched_signals: dict[str, list[str]],
) -> str:
    """Build machine-readable routing reason."""

    if selected_module is None:
        return "no module signal matched"

    if selected_module == "spec":
        if has_any_signal(
            matched_signals=matched_signals,
            signals=SPEC_HIGH_RISK_SIGNALS,
        ):
            return "spec high-risk fitment signal takes precedence"

        return "spec signal selected"

    if selected_module == "price":
        return "price or discount signal takes precedence"

    if selected_module == "logistics":
        return "logistics or fulfillment signal takes precedence"

    if selected_module == "quality":
        return "quality signal selected"

    return "unknown routing reason"


def build_risk_tags(
    *,
    selected_module: str | None,
    matched_signals: dict[str, list[str]],
) -> list[str]:
    """Build broad risk tags from matched signals."""

    risk_tags: list[str] = []

    if selected_module is None:
        return risk_tags

    if matched_signals["price"]:
        risk_tags.append("price_commitment")

    if matched_signals["logistics"]:
        risk_tags.append("fulfillment_commitment")

    if matched_signals["spec"]:
        risk_tags.append("spec_or_fitment")

    if matched_signals["quality"]:
        risk_tags.append("quality_claim")

    if has_any_signal(matched_signals=matched_signals, signals=SPEC_HIGH_RISK_SIGNALS):
        risk_tags.append("high_risk_fitment")

    return risk_tags