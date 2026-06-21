from __future__ import annotations

import argparse
import json
from typing import Optional

from app.agent.rag.answer_service import build_default_answer_service


def _load_env_if_available() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    load_dotenv()


def run_answer_test(
    *,
    query: str,
    domain: Optional[str],
    limit: int,
    score_threshold: Optional[float],
    rerank: Optional[bool],
    rerank_top_k: Optional[int],
    show_contexts: bool,
    json_output: bool,
) -> int:
    service = build_default_answer_service()

    result = service.answer(
        query=query,
        domain=domain,
        limit=limit,
        score_threshold=score_threshold,
        rerank=rerank,
        rerank_top_k=rerank_top_k,
    )

    if json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(f"[answer] query={result.get('query')}")
    print(f"[answer] domain={result.get('domain')}")
    print(f"[answer] should_answer={result.get('should_answer')}")
    print(f"[answer] confidence={result.get('confidence')}")
    print(f"[answer] source_count={result.get('source_count')}")
    print(f"[answer] answer={result.get('answer')}")
    print(f"[answer] metadata={result.get('metadata')}")

    print("-" * 80)
    print("[sources]")
    for source in result.get("sources", []):
        print(
            f"[{source.get('index')}] "
            f"chunk_id={source.get('chunk_id')} "
            f"score={source.get('score')} "
            f"rerank_score={source.get('rerank_score')} "
            f"source={source.get('source')}"
        )

    if show_contexts:
        print("-" * 80)
        print("[contexts]")
        for context in result.get("contexts", []):
            print(f"[{context.get('index')}] text={context.get('text')}")
            print(f"rerank_reason={context.get('rerank_reason')}")

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Test RagAnswerService with a local query."
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

    rerank_group = parser.add_mutually_exclusive_group()
    rerank_group.add_argument(
        "--rerank",
        dest="rerank",
        action="store_true",
        help="Force enable rerank.",
    )
    rerank_group.add_argument(
        "--no-rerank",
        dest="rerank",
        action="store_false",
        help="Force disable rerank.",
    )
    parser.set_defaults(rerank=None)

    parser.add_argument(
        "--rerank-top-k",
        type=int,
        default=None,
        help="Keep only top K results after reranking.",
    )
    parser.add_argument(
        "--show-contexts",
        action="store_true",
        help="Print retrieved contexts.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full result as JSON.",
    )

    return parser


def main() -> int:
    _load_env_if_available()

    parser = build_parser()
    args = parser.parse_args()

    try:
        return run_answer_test(
            query=args.query,
            domain=args.domain,
            limit=args.limit,
            score_threshold=args.score_threshold,
            rerank=args.rerank,
            rerank_top_k=args.rerank_top_k,
            show_contexts=args.show_contexts,
            json_output=args.json,
        )
    except Exception as exc:
        print(f"[answer][error] {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
