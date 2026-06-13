"""Shared agent result types.

These types are intentionally small and framework-independent so every handler
and renderer can reuse the same contract.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal, TypeAlias

HandlerStatus: TypeAlias = Literal[
    "success",
    "not_found",
    "invalid_request",
    "handoff",
    "failed",
]

SourceReference: TypeAlias = dict[str, str]


@dataclass(frozen=True)
class HandlerResult:
    """Unified result returned by all intent handlers."""

    primary_intent: str
    handler_name: str
    status: HandlerStatus
    matched_count: int
    handoff_required: bool
    facts: dict[str, object] | None
    errors: list[str]
    source_references: list[SourceReference]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable dictionary."""

        return asdict(self)


@dataclass(frozen=True)
class RenderedAnswer:
    """Unified customer-facing answer returned by renderers."""

    text: str
    handoff_required: bool
    source_references: list[SourceReference]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable dictionary."""

        return asdict(self)