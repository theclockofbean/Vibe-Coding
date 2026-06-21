from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from app.agent.rag.chunk_schema import DocumentChunk
from app.agent.rag.chunk_vector_store import build_default_chunk_vector_store
from app.agent.rag.document_loader import DocumentLoader
from app.agent.rag.embedding_service import EmbeddingService, build_default_embedding_service


def _load_env_if_available() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    load_dotenv()


def _build_embedding_service(use_real_embedding: bool) -> EmbeddingService:
    if not use_real_embedding:
        return build_default_embedding_service()

    try:
        from app.agent.rag.real_embedding import build_real_embedding_client_from_env
    except ImportError as exc:
        raise RuntimeError(
            "real_embedding module is unavailable. Use default deterministic embedding instead."
        ) from exc

    client = build_real_embedding_client_from_env()
    return EmbeddingService(client=client)


def _load_chunks_from_file(
    *,
    loader: DocumentLoader,
    file_path: Path,
    domain: str,
    source_type: str,
    sheet_name: Optional[str],
) -> List[DocumentChunk]:
    suffix = file_path.suffix.lower()

    if suffix in {".txt", ".md"}:
        return loader.load_text_file(
            file_path,
            domain=domain,
            source_type=source_type,
        )

    if suffix == ".json":
        return loader.load_json_file(
            file_path,
            domain=domain,
            source_type=source_type,
        )

    if suffix == ".jsonl":
        return loader.load_jsonl_file(
            file_path,
            domain=domain,
            source_type=source_type,
        )

    if suffix == ".xlsx":
        return loader.load_xlsx_file(
            file_path,
            domain=domain,
            source_type=source_type,
            sheet_name=sheet_name,
        )

    raise ValueError(
        f"Unsupported file type: {suffix}. Supported: .txt, .md, .json, .jsonl, .xlsx"
    )


def ingest_file(
    *,
    file_path: Path,
    domain: str,
    source_type: str,
    sheet_name: Optional[str],
    chunk_size: int,
    chunk_overlap: int,
    batch_size: int,
    recreate: bool,
    dry_run: bool,
    use_real_embedding: bool,
) -> int:
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    loader = DocumentLoader(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    chunks = _load_chunks_from_file(
        loader=loader,
        file_path=file_path,
        domain=domain,
        source_type=source_type,
        sheet_name=sheet_name,
    )

    print(f"[ingest] loaded_chunks={len(chunks)}")
    print(f"[ingest] file={file_path}")
    print(f"[ingest] domain={domain}")
    print(f"[ingest] source_type={source_type}")

    if not chunks:
        print("[ingest] no chunks loaded, exit")
        return 0

    print("[ingest] first_chunk_preview:")
    print(chunks[0].model_dump())

    if dry_run:
        print("[ingest] dry_run=true, skip embedding and qdrant upsert")
        return len(chunks)

    embedding_service = _build_embedding_service(use_real_embedding=use_real_embedding)
    embedded_chunks = embedding_service.embed_chunks(chunks)

    print(f"[ingest] embedded_chunks={len(embedded_chunks)}")
    print(f"[ingest] vector_size={len(embedded_chunks[0].embedding or [])}")

    store = build_default_chunk_vector_store()

    store.ensure_collection(
        vector_size=len(embedded_chunks[0].embedding or []),
        recreate=recreate,
    )

    upserted_count = store.upsert_chunks(
        embedded_chunks,
        batch_size=batch_size,
        ensure_collection=False,
    )

    print(f"[ingest] upserted_count={upserted_count}")
    print(f"[ingest] collection={store.collection_name}")

    return upserted_count


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ingest local knowledge file into Qdrant as standard DocumentChunk records."
    )

    parser.add_argument(
        "--file",
        required=True,
        help="Input file path. Supported: .txt, .md, .json, .jsonl, .xlsx",
    )

    parser.add_argument(
        "--domain",
        required=True,
        choices=["spec", "price", "logistics", "quality", "general"],
        help="Knowledge domain.",
    )

    parser.add_argument(
        "--source-type",
        default="doc",
        help="Source type, e.g. sku / faq / rule / doc.",
    )

    parser.add_argument(
        "--sheet-name",
        default=None,
        help="Optional xlsx sheet name.",
    )

    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1000,
        help="Text chunk size for txt/md files.",
    )

    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=120,
        help="Text chunk overlap for txt/md files.",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=64,
        help="Qdrant upsert batch size.",
    )

    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Delete and recreate target Qdrant collection before upsert.",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only load and preview chunks, do not embed or upsert.",
    )

    parser.add_argument(
        "--use-real-embedding",
        action="store_true",
        help="Use real_embedding client from env instead of deterministic local embedding.",
    )

    return parser


def main() -> int:
    _load_env_if_available()

    parser = build_parser()
    args = parser.parse_args()

    try:
        ingest_file(
            file_path=Path(args.file),
            domain=args.domain,
            source_type=args.source_type,
            sheet_name=args.sheet_name,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
            batch_size=args.batch_size,
            recreate=args.recreate,
            dry_run=args.dry_run,
            use_real_embedding=args.use_real_embedding,
        )
    except Exception as exc:
        print(f"[ingest][error] {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
