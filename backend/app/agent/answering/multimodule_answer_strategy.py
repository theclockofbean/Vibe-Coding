"""Multi-module answer strategy helper."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, cast

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
PROJECT_ROOT: Final[Path] = BACKEND_ROOT.parent
DEFAULT_STRATEGY_JSON: Final[Path] = (
    PROJECT_ROOT / "docs/backend/phase3ig_multimodule_answer_strategy_v0.1.json"
)

DEFAULT_MODE: Final[str] = "single_primary"
SAFETY_MODE: Final[str] = "safety_blocked"

BOUNDARY_NOTES: Final[dict[str, str]] = {
    "none": "",
    "spec_as_reference_only": "规格信息只能作为补充参考，不能替代正式报价或人工确认。",
    "quality_as_reference_only": "质量或材质信息只能作为补充说明，不能形成价格承诺。",
    "price_logistics_commitment_risk": "价格与物流费用均可能构成承诺，需要人工确认。",
    "logistics_after_fitment_confirmation": "物流安排应在适配关系核对后再确认。",
    "quality_not_fitment_commitment": "质量说明不能替代适配确认。",
    "fitment_before_price_commitment": "适配关系未确认前，不应推进价格承诺。",
    "quality_issue_not_compensation_commitment": "质量问题不等于自动赔付或补发，需要人工确认。",
    "spec_as_shipping_context": "SKU 或规格仅作为物流查询上下文，不代表适配承诺。",
    "shipping_fee_price_commitment_risk": "运费和价格相关内容需要人工确认。",
}


@dataclass(frozen=True)
class AnswerStrategyDecision:
    """Answer strategy decision for multi-module routing."""

    strategy_mode: str
    primary_module: str | None
    candidate_modules: list[str]
    boundary_notes: list[str] = field(default_factory=list)
    split_required: bool = False
    handoff_required: bool = False
    safety_blocked: bool = False
    forbidden_commitment_detected: bool = False
    forbidden_fragments: list[str] = field(default_factory=list)
    boundary_note_type: str = "none"
    reason: str = ""

    def to_metadata(self) -> dict[str, Any]:
        """Return workflow/renderer metadata."""

        return {
            "answer_strategy_mode": self.strategy_mode,
            "answer_primary_module": self.primary_module,
            "answer_candidate_modules": self.candidate_modules,
            "answer_boundary_notes": self.boundary_notes,
            "answer_split_required": self.split_required,
            "answer_handoff_required": self.handoff_required,
            "answer_safety_blocked": self.safety_blocked,
            "answer_forbidden_commitment_detected": (
                self.forbidden_commitment_detected
            ),
            "answer_forbidden_fragments": self.forbidden_fragments,
            "answer_boundary_note_type": self.boundary_note_type,
            "answer_strategy_reason": self.reason,
        }


def decide_answer_strategy(
    *,
    query: str,
    selected_module: str | None,
    candidate_modules: list[str],
    conflict_type: str | None = None,
    strategy_config: dict[str, Any] | None = None,
) -> AnswerStrategyDecision:
    """Decide how to answer a routed multi-module question."""

    config = strategy_config or load_answer_strategy_config()
    normalized_candidates = normalize_candidate_modules(
        selected_module=selected_module,
        candidate_modules=candidate_modules,
    )
    forbidden_fragments = detect_forbidden_fragments(
        query=query,
        config=config,
    )

    if selected_module is None:
        return build_decision(
            mode="split_required",
            selected_module=None,
            candidate_modules=normalized_candidates,
            boundary_note_type="none",
            forbidden_fragments=forbidden_fragments,
            config=config,
            reason="no selected module; ask user to clarify or split question",
        )

    if forbidden_fragments:
        return build_decision(
            mode=SAFETY_MODE,
            selected_module=selected_module,
            candidate_modules=normalized_candidates,
            boundary_note_type="forbidden_commitment_detected",
            forbidden_fragments=forbidden_fragments,
            config=config,
            reason="forbidden commitment fragment detected",
        )

    rule = find_pair_rule(
        selected_module=selected_module,
        candidate_modules=normalized_candidates,
        conflict_type=conflict_type,
        config=config,
    )

    if rule is None:
        return build_decision(
            mode=DEFAULT_MODE,
            selected_module=selected_module,
            candidate_modules=normalized_candidates,
            boundary_note_type="none",
            forbidden_fragments=forbidden_fragments,
            config=config,
            reason="no pair rule matched; use single primary answer",
        )

    return build_decision(
        mode=str(rule["strategy_mode"]),
        selected_module=selected_module,
        candidate_modules=normalized_candidates,
        boundary_note_type=str(rule["boundary_note_type"]),
        forbidden_fragments=forbidden_fragments,
        config=config,
        reason="matched configured module pair rule",
    )


def load_answer_strategy_config(
    path: Path | None = None,
) -> dict[str, Any]:
    """Load answer strategy JSON config."""

    config_path = path or DEFAULT_STRATEGY_JSON
    data = json.loads(config_path.read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        raise ValueError("answer strategy config root must be object")

    return cast(dict[str, Any], data)


def normalize_candidate_modules(
    *,
    selected_module: str | None,
    candidate_modules: list[str],
) -> list[str]:
    """Return de-duplicated candidate modules with selected module first."""

    normalized: list[str] = []

    if selected_module:
        normalized.append(selected_module)

    for module in candidate_modules:
        if module and module not in normalized:
            normalized.append(module)

    return normalized


def detect_forbidden_fragments(
    *,
    query: str,
    config: dict[str, Any],
) -> list[str]:
    """Detect high-risk or forbidden commitment fragments in query."""

    fragments = [
        str(item)
        for item in cast(list[Any], config.get("high_risk_fragments", []))
    ]
    normalized_query = query.strip().lower()

    return [
        fragment
        for fragment in fragments
        if fragment.lower() in normalized_query
    ]


def find_pair_rule(
    *,
    selected_module: str,
    candidate_modules: list[str],
    conflict_type: str | None,
    config: dict[str, Any],
) -> dict[str, Any] | None:
    """Find best pair rule for selected module and candidates."""

    pair_rules = cast(list[dict[str, Any]], config.get("module_pair_rules", []))

    conflict_modules = modules_from_conflict_type(conflict_type=conflict_type)

    if conflict_modules:
        rule = find_exact_rule(
            selected_module=selected_module,
            candidate_modules=conflict_modules,
            pair_rules=pair_rules,
        )

        if rule is not None:
            return rule

    for secondary_module in candidate_modules:
        if secondary_module == selected_module:
            continue

        rule = find_exact_rule(
            selected_module=selected_module,
            candidate_modules=[selected_module, secondary_module],
            pair_rules=pair_rules,
        )

        if rule is not None:
            return rule

    return find_exact_rule(
        selected_module=selected_module,
        candidate_modules=[selected_module],
        pair_rules=pair_rules,
    )


def modules_from_conflict_type(
    *,
    conflict_type: str | None,
) -> list[str]:
    """Parse conflict type into modules."""

    if not conflict_type:
        return []

    modules = [
        item
        for item in conflict_type.split("_")
        if item
    ]

    if len(modules) == 1:
        return modules

    return modules[:2]


def find_exact_rule(
    *,
    selected_module: str,
    candidate_modules: list[str],
    pair_rules: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Find exact selected-module pair rule ignoring candidate order."""

    candidate_set = set(candidate_modules)

    for rule in pair_rules:
        rule_selected_module = str(rule.get("selected_module"))
        rule_candidate_modules = {
            str(item)
            for item in cast(list[Any], rule.get("candidate_modules", []))
        }

        if rule_selected_module != selected_module:
            continue

        if rule_candidate_modules == candidate_set:
            return rule

    return None


def build_decision(
    *,
    mode: str,
    selected_module: str | None,
    candidate_modules: list[str],
    boundary_note_type: str,
    forbidden_fragments: list[str],
    config: dict[str, Any],
    reason: str,
) -> AnswerStrategyDecision:
    """Build normalized answer strategy decision."""

    mode_config = cast(dict[str, Any], config.get("strategy_modes", {})).get(mode, {})

    if not isinstance(mode_config, dict):
        raise ValueError(f"strategy mode config must be object: {mode}")

    boundary_notes = build_boundary_notes(
        boundary_note_type=boundary_note_type,
        forbidden_fragments=forbidden_fragments,
    )

    return AnswerStrategyDecision(
        strategy_mode=mode,
        primary_module=selected_module,
        candidate_modules=candidate_modules,
        boundary_notes=boundary_notes,
        split_required=bool(mode_config.get("split_required", False)),
        handoff_required=bool(mode_config.get("handoff_required", False)),
        safety_blocked=bool(mode_config.get("safety_blocked", False)),
        forbidden_commitment_detected=bool(forbidden_fragments),
        forbidden_fragments=forbidden_fragments,
        boundary_note_type=boundary_note_type,
        reason=reason,
    )


def build_boundary_notes(
    *,
    boundary_note_type: str,
    forbidden_fragments: list[str],
) -> list[str]:
    """Build human-readable boundary notes."""

    notes: list[str] = []

    configured_note = BOUNDARY_NOTES.get(boundary_note_type, "")

    if configured_note:
        notes.append(configured_note)

    if forbidden_fragments:
        notes.append("检测到高风险承诺表达，需要人工确认后再回复。")

    return notes