from __future__ import annotations

import argparse
import sys
from typing import Optional

from app.agent.rag.retrieval_service import build_default_retrieval_service


def _load_env_if_available() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    load_dotenv()


def run_retrieval_test(
    *,
    query: str,
    domain: Optional[str],
    limit: int,
    score_threshold: Optional[float],
    rerank: bool,
    rerank_top_k: Optional[int],
) -> int:
    service = build_default_retrieval_service()

    results = service.retrieve(
        query=query,
        domain=domain,
        limit=limit,
        score_threshold=score_threshold,
        rerank=rerank,
        rerank_top_k=rerank_top_k,
    )

    print(f"[retrieval] query={query}")
    print(f"[retrieval] domain={domain}")
    print(f"[retrieval] limit={limit}")
    print(f"[retrieval] score_threshold={score_threshold}")
    print(f"[retrieval] rerank={rerank}")
    print(f"[retrieval] rerank_top_k={rerank_top_k}")
    print(f"[retrieval] result_count={len(results)}")

    for index, item in enumerate(results, start=1):
        text = item.get("text") or ""
        preview = text.replace("\n", " ")[:160]

        print("-" * 80)
        print(f"[{index}] score={item.get('score')}")

        if rerank:
            print(f"original_score={item.get('original_score')}")
            print(f"rerank_score={item.get('rerank_score')}")
            print(f"rank={item.get('rank')}")
            print(f"rerank_reason={item.get('rerank_reason')}")

        print(f"chunk_id={item.get('chunk_id')}")
        print(f"document_id={item.get('document_id')}")
        print(f"domain={item.get('domain')}")
        print(f"source={item.get('source')}")
        print(f"source_type={item.get('source_type')}")
        print(f"text={preview}")

    return len(results)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Test retrieval from rag_chunks_v1 through RagRetrievalService."
    )

    parser.add_argument(
        "--query",
        required=True,
        help="Query text.",
    )
    parser.add_argument(
        "--domain",
        choices=["spec", "price", "logistics", "quality", "general"],
        default=None,
        help="Optional domain filter.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Top-K retrieval limit.",
    )
    parser.add_argument(
        "--score-threshold",
        type=float,
        default=None,
        help="Optional Qdrant score threshold.",
    )
    parser.add_argument(
        "--rerank",
        action="store_true",
        help="Apply rule-based reranker after Qdrant retrieval.",
    )
    parser.add_argument(
        "--rerank-top-k",
        type=int,
        default=None,
        help="Keep only top K results after reranking.",
    )

    return parser


def main() -> int:
    _load_env_if_available()

    parser = build_parser()
    args = parser.parse_args()

    try:
        run_retrieval_test(
            query=args.query,
            domain=args.domain,
            limit=args.limit,
            score_threshold=args.score_threshold,
            rerank=args.rerank,
            rerank_top_k=args.rerank_top_k,
        )
    except Exception as exc:
        print(f"[retrieval][error] {exc}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
