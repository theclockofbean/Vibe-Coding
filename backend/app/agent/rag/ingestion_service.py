from __future__ import annotations

from typing import List, Dict, Any, Optional

from app.agent.rag.document_loader import DocumentLoader
from app.agent.rag.embedding_service import build_default_embedding_service
from app.agent.rag.chunk_vector_store import build_default_chunk_vector_store

from app.agent.rag.spec_chunk_builder import SpecChunkBuilder
from app.agent.rag.price_chunk_builder import PriceChunkBuilder
from app.agent.rag.logistics_chunk_builder import LogisticsChunkBuilder
from app.agent.rag.quality_chunk_builder import QualityChunkBuilder
from app.agent.rag.chunk_schema import DocumentChunk

class IngestionService:
    """
    P0-B: unified ingestion pipeline
    """

    def __init__(self):
        self.loader = DocumentLoader()
        self.embedding_service = build_default_embedding_service()
        self.vector_store = build_default_chunk_vector_store()
        self.vector_size = self.embedding_service.vector_size

        self.builders = {
            "spec": SpecChunkBuilder(),
            "price": PriceChunkBuilder(),
            "logistics": LogisticsChunkBuilder(),
            "quality": QualityChunkBuilder(),
        }

    def ingest(
        self,
        *,
        file_path: str,
        domain: str,
        source_type: str,
        recreate: bool = False,
    ) -> Dict[str, Any]:

        if domain not in self.builders:
            raise ValueError(f"Unsupported domain: {domain}")

        builder = self.builders[domain]

        # 1. load raw rows
        rows = builder.load(file_path)

        # 2. convert to chunks
        chunks = self.loader.load_records(
            rows,
            domain=domain,
            source=file_path,
            source_type=source_type,
        )
        embedded_chunks: list[DocumentChunk] = []

        for chunk in chunks:
            vector = self.embedding_service.embed_text(chunk.text)

            embedded_chunks.append(
                DocumentChunk(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    domain=chunk.domain,
                    text=chunk.text,
                    source=chunk.source,
                    source_type=chunk.source_type,
                    metadata=chunk.metadata,
                    embedding=vector,
                )
            )

        self.vector_store.ensure_collection(
            vector_size=self.vector_size
        )

        self.vector_store.upsert_chunks(embedded_chunks)

        return {
            "domain": domain,
            "file": file_path,
            "chunks": len(chunks),
            "embedded": len(embedded_chunks),
            "status": "ok"
        }


def build_default_ingestion_service() -> IngestionService:
    return IngestionService()
