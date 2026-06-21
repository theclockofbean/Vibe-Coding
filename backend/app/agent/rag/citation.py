from __future__ import annotations

import hashlib
from typing import Any, Dict, Iterable, List, Optional

from pydantic import BaseModel, Field


def _normalize_text(value: Any) -> str:
    return str(value or "").replace("\ufeff", "").strip()


def _stable_citation_id(*parts: Any) -> str:
    raw = "||".join(_normalize_text(part) for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"cite_{digest[:16]}"


class Citation(BaseModel):
    """
    单条引用来源。

    用于回答生成后的可追溯展示。
    """

    citation_id: str
    chunk_id: str
    document_id: str

    domain: str
    source: str
    source_type: str

    text: str

    score: Optional[float] = None
    rerank_score: Optional[float] = None
    rank: Optional[int] = None

    metadata: Dict[str, Any] = Field(default_factory=dict)


class CitationBundle(BaseModel):
    """
    一次回答对应的一组引用。
    """

    citations: List[Citation] = Field(default_factory=list)

    def to_context_text(self, *, max_chars_per_citation: int = 500) -> str:
        lines: List[str] = []

        for citation in self.citations:
            text = citation.text[:max_chars_per_citation]

            lines.append(
                f"[{citation.citation_id}] "
                f"domain={citation.domain}; "
                f"source={citation.source}; "
                f"source_type={citation.source_type}; "
                f"text={text}"
            )

        return "\n\n".join(lines)

    def citation_ids(self) -> List[str]:
        return [citation.citation_id for citation in self.citations]


def citation_from_retrieval_item(
    item: Dict[str, Any],
    *,
    fallback_rank: Optional[int] = None,
) -> Citation:
    chunk_id = _normalize_text(item.get("chunk_id"))
    document_id = _normalize_text(item.get("document_id"))
    domain = _normalize_text(item.get("domain"))
    source = _normalize_text(item.get("source"))
    source_type = _normalize_text(item.get("source_type"))
    text = _normalize_text(item.get("text"))

    citation_id = _stable_citation_id(
        chunk_id,
        document_id,
        source,
        domain,
    )

    rank = item.get("rank", fallback_rank)

    return Citation(
        citation_id=citation_id,
        chunk_id=chunk_id,
        document_id=document_id,
        domain=domain,
        source=source,
        source_type=source_type,
        text=text,
        score=item.get("score"),
        rerank_score=item.get("rerank_score"),
        rank=rank,
        metadata=item.get("metadata") or {},
    )


def build_citation_bundle(
    items: Iterable[Dict[str, Any]],
    *,
    max_citations: Optional[int] = None,
) -> CitationBundle:
    citations: List[Citation] = []

    for index, item in enumerate(items, start=1):
        if max_citations is not None and len(citations) >= max_citations:
            break

        citations.append(
            citation_from_retrieval_item(
                item,
                fallback_rank=index,
            )
        )

    return CitationBundle(citations=citations)
