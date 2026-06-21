from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional


def _normalize_text(text: Any) -> str:
    return str(text or "").replace("\ufeff", "").strip().lower()


def _extract_ascii_tokens(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z0-9]+", text.lower())


def _extract_chinese_chars(text: str) -> List[str]:
    return re.findall(r"[\u4e00-\u9fff]", text)


def _extract_ngrams(text: str, n: int) -> List[str]:
    normalized = _normalize_text(text)
    normalized = re.sub(r"\s+", "", normalized)

    if len(normalized) < n:
        return []

    return [
        normalized[index : index + n]
        for index in range(0, len(normalized) - n + 1)
    ]


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


@dataclass
class RerankResult:
    item: Dict[str, Any]
    original_score: float
    rerank_score: float
    rank: int
    reason: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            **self.item,
            "original_score": self.original_score,
            "rerank_score": self.rerank_score,
            "rank": self.rank,
            "rerank_reason": self.reason,
        }


class RuleBasedReranker:
    """
    轻量级规则 Reranker。

    输入：
    - query
    - Qdrant 初召回结果 dict list

    输出：
    - 带 rerank_score / rank / rerank_reason 的结果
    """

    def __init__(
        self,
        *,
        vector_score_weight: float = 0.55,
        exact_match_weight: float = 0.18,
        token_overlap_weight: float = 0.12,
        char_overlap_weight: float = 0.08,
        bigram_overlap_weight: float = 0.05,
        domain_match_weight: float = 0.02,
        source_type_weight: float = 0.02,
    ) -> None:
        self.vector_score_weight = vector_score_weight
        self.exact_match_weight = exact_match_weight
        self.token_overlap_weight = token_overlap_weight
        self.char_overlap_weight = char_overlap_weight
        self.bigram_overlap_weight = bigram_overlap_weight
        self.domain_match_weight = domain_match_weight
        self.source_type_weight = source_type_weight

    def rerank(
        self,
        *,
        query: str,
        items: Iterable[Dict[str, Any]],
        domain: Optional[str] = None,
        top_k: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        scored_results = self.score(
            query=query,
            items=items,
            domain=domain,
        )

        if top_k is not None:
            scored_results = scored_results[:top_k]

        return [result.to_dict() for result in scored_results]

    def score(
        self,
        *,
        query: str,
        items: Iterable[Dict[str, Any]],
        domain: Optional[str] = None,
    ) -> List[RerankResult]:
        query_text = _normalize_text(query)
        results: List[RerankResult] = []

        for item in items:
            text = _normalize_text(item.get("text"))
            original_score = _safe_float(item.get("score"))

            reason = {
                "vector_score": self._vector_score(original_score),
                "exact_match": self._exact_match_score(query_text, text),
                "token_overlap": self._token_overlap_score(query_text, text),
                "char_overlap": self._char_overlap_score(query_text, text),
                "bigram_overlap": self._bigram_overlap_score(query_text, text),
                "domain_match": self._domain_match_score(domain, item),
                "source_type": self._source_type_score(item),
            }

            rerank_score = (
                reason["vector_score"] * self.vector_score_weight
                + reason["exact_match"] * self.exact_match_weight
                + reason["token_overlap"] * self.token_overlap_weight
                + reason["char_overlap"] * self.char_overlap_weight
                + reason["bigram_overlap"] * self.bigram_overlap_weight
                + reason["domain_match"] * self.domain_match_weight
                + reason["source_type"] * self.source_type_weight
            )

            results.append(
                RerankResult(
                    item=item,
                    original_score=original_score,
                    rerank_score=rerank_score,
                    rank=0,
                    reason=reason,
                )
            )

        results.sort(key=lambda result: result.rerank_score, reverse=True)

        for index, result in enumerate(results, start=1):
            result.rank = index

        return results

    def _vector_score(self, score: float) -> float:
        if score < 0:
            return 0.0
        if score > 1:
            return 1.0
        return score

    def _exact_match_score(self, query: str, text: str) -> float:
        if not query or not text:
            return 0.0

        query_no_space = re.sub(r"\s+", "", query)
        text_no_space = re.sub(r"\s+", "", text)

        if query_no_space and query_no_space in text_no_space:
            return 1.0

        return 0.0

    def _token_overlap_score(self, query: str, text: str) -> float:
        query_tokens = set(_extract_ascii_tokens(query))
        text_tokens = set(_extract_ascii_tokens(text))

        if not query_tokens:
            return 0.0

        return len(query_tokens & text_tokens) / len(query_tokens)

    def _char_overlap_score(self, query: str, text: str) -> float:
        query_chars = set(_extract_chinese_chars(query))
        text_chars = set(_extract_chinese_chars(text))

        if not query_chars:
            return 0.0

        return len(query_chars & text_chars) / len(query_chars)

    def _bigram_overlap_score(self, query: str, text: str) -> float:
        query_bigrams = set(_extract_ngrams(query, 2))
        text_bigrams = set(_extract_ngrams(text, 2))

        if not query_bigrams:
            return 0.0

        return len(query_bigrams & text_bigrams) / len(query_bigrams)

    def _domain_match_score(self, domain: Optional[str], item: Dict[str, Any]) -> float:
        if not domain:
            return 0.0

        item_domain = _normalize_text(item.get("domain"))

        return 1.0 if item_domain == _normalize_text(domain) else 0.0

    def _source_type_score(self, item: Dict[str, Any]) -> float:
        source_type = _normalize_text(item.get("source_type"))

        priority = {
            "sku": 1.0,
            "faq": 0.9,
            "rule": 0.85,
            "doc": 0.75,
        }

        return priority.get(source_type, 0.5)


def build_default_reranker() -> RuleBasedReranker:
    return RuleBasedReranker()
