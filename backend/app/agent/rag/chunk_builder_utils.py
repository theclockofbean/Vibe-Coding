from typing import Any


def read_text(record: dict[str, Any], key: str) -> str:
    val = record.get(key)
    return "" if val is None else str(val).strip()


def split_multi_value(value: str) -> list[str]:
    if not value:
        return []
    return [x.strip() for x in str(value).split(";") if x.strip()]


def parse_bool(value: str) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def build_chunk_content(**fields) -> str:
    return "\n".join([f"{k}: {v}" for k, v in fields.items() if v is not None])


def infer_risk_level(handoff_required: bool, risk_flags: list[str]) -> str:
    if handoff_required or len(risk_flags) >= 2:
        return "high"
    if risk_flags:
        return "medium"
    return "low"
