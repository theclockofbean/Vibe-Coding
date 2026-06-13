"""Check Phase 3-I-G multi-module answer strategy JSON."""

from __future__ import annotations

import json
from pathlib import Path
from pprint import pprint
from typing import Any, Final, cast


BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
PROJECT_ROOT: Final[Path] = BACKEND_ROOT.parent
JSON_FILE: Final[Path] = (
    PROJECT_ROOT / "docs/backend/phase3ig_multimodule_answer_strategy_v0.1.json"
)

REQUIRED_MODES: Final[set[str]] = {
    "single_primary",
    "primary_with_boundary_note",
    "split_required",
    "safety_blocked",
    "handoff_required",
}

REQUIRED_METADATA_FIELDS: Final[set[str]] = {
    "answer_strategy_mode",
    "answer_primary_module",
    "answer_candidate_modules",
    "answer_boundary_notes",
    "answer_split_required",
    "answer_handoff_required",
    "answer_safety_blocked",
    "answer_forbidden_commitment_detected",
}

REQUIRED_RULE_KEYS: Final[set[str]] = {
    "selected_module",
    "candidate_modules",
    "strategy_mode",
    "boundary_note_type",
}

REQUIRED_PAIR_BASELINES: Final[set[tuple[str, str, str]]] = {
    ("price", "spec", "primary_with_boundary_note"),
    ("price", "quality", "primary_with_boundary_note"),
    ("price", "logistics", "safety_blocked"),
    ("spec", "logistics", "primary_with_boundary_note"),
    ("spec", "quality", "primary_with_boundary_note"),
    ("spec", "price", "safety_blocked"),
    ("logistics", "quality", "primary_with_boundary_note"),
    ("logistics", "spec", "primary_with_boundary_note"),
    ("logistics", "price", "safety_blocked"),
    ("quality", "quality", "single_primary"),
}

REQUIRED_FORBIDDEN_PATTERNS: Final[set[str]] = {
    "包邮价",
    "适配后马上发",
    "高质量低价",
    "一定赔",
    "一定补发",
    "保证适配且质量没问题",
}


def main() -> int:
    """Run answer strategy JSON check."""

    print("=" * 80)
    print("checking Phase 3-I-G answer strategy JSON")

    errors: list[str] = []

    if not JSON_FILE.exists():
        errors.append(f"missing JSON file: {JSON_FILE}")
        pprint({"errors": errors})
        return 1

    data = load_json_file()
    validate_top_level(data=data, errors=errors)
    validate_strategy_modes(data=data, errors=errors)
    validate_pair_rules(data=data, errors=errors)

    result = {
        "json_file": str(JSON_FILE),
        "strategy_mode_count": len(cast(dict[str, Any], data.get("strategy_modes", {}))),
        "module_pair_rule_count": len(cast(list[Any], data.get("module_pair_rules", []))),
        "metadata_field_count": len(cast(list[Any], data.get("metadata_fields", []))),
        "errors": errors,
    }

    pprint(result)

    if errors:
        print("Phase 3-I-G answer strategy JSON check failed")
        return 1

    print("Phase 3-I-G answer strategy JSON check passed")
    return 0


def load_json_file() -> dict[str, Any]:
    """Load JSON file."""

    data = json.loads(JSON_FILE.read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        raise ValueError("JSON root must be object")

    return cast(dict[str, Any], data)


def validate_top_level(
    *,
    data: dict[str, Any],
    errors: list[str],
) -> None:
    """Validate top-level fields."""

    if data.get("phase") != "Phase 3-I-G":
        errors.append("phase must be Phase 3-I-G")

    metadata_fields = {
        str(item)
        for item in cast(list[Any], data.get("metadata_fields", []))
    }
    missing_metadata_fields = REQUIRED_METADATA_FIELDS - metadata_fields

    if missing_metadata_fields:
        errors.append(f"missing metadata fields: {sorted(missing_metadata_fields)}")

    forbidden_patterns = {
        str(item)
        for item in cast(list[Any], data.get("forbidden_fusion_patterns", []))
    }
    missing_forbidden_patterns = REQUIRED_FORBIDDEN_PATTERNS - forbidden_patterns

    if missing_forbidden_patterns:
        errors.append(
            f"missing forbidden fusion patterns: {sorted(missing_forbidden_patterns)}"
        )


def validate_strategy_modes(
    *,
    data: dict[str, Any],
    errors: list[str],
) -> None:
    """Validate strategy modes."""

    modes = cast(dict[str, Any], data.get("strategy_modes", {}))
    missing_modes = REQUIRED_MODES - set(modes)

    if missing_modes:
        errors.append(f"missing strategy modes: {sorted(missing_modes)}")

    for mode_name, mode_config_any in modes.items():
        mode_config = cast(dict[str, Any], mode_config_any)

        for bool_key in (
            "allow_secondary_answer",
            "split_required",
            "handoff_required",
            "safety_blocked",
        ):
            if not isinstance(mode_config.get(bool_key), bool):
                errors.append(f"{mode_name}: {bool_key} must be bool")


def validate_pair_rules(
    *,
    data: dict[str, Any],
    errors: list[str],
) -> None:
    """Validate module pair rules."""

    pair_rules = cast(list[dict[str, Any]], data.get("module_pair_rules", []))
    actual_baselines: set[tuple[str, str, str]] = set()

    for index, rule in enumerate(pair_rules, start=1):
        missing_rule_keys = REQUIRED_RULE_KEYS - set(rule)

        if missing_rule_keys:
            errors.append(f"rule[{index}]: missing keys {sorted(missing_rule_keys)}")
            continue

        selected_module = str(rule.get("selected_module"))
        candidate_modules = [
            str(item)
            for item in cast(list[Any], rule.get("candidate_modules", []))
        ]
        strategy_mode = str(rule.get("strategy_mode"))

        if selected_module not in candidate_modules:
            errors.append(f"rule[{index}]: selected_module not in candidate_modules")

        if strategy_mode not in REQUIRED_MODES:
            errors.append(f"rule[{index}]: unknown strategy_mode {strategy_mode}")

        for candidate_module in candidate_modules:
            if candidate_module == selected_module and len(candidate_modules) > 1:
                continue

            actual_baselines.add(
                (
                    selected_module,
                    candidate_module,
                    strategy_mode,
                )
            )

        if len(candidate_modules) == 1:
            actual_baselines.add(
                (
                    selected_module,
                    selected_module,
                    strategy_mode,
                )
            )

    missing_pair_baselines = REQUIRED_PAIR_BASELINES - actual_baselines

    if missing_pair_baselines:
        errors.append(f"missing pair baselines: {sorted(missing_pair_baselines)}")


if __name__ == "__main__":
    raise SystemExit(main())