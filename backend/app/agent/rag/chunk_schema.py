from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


class DocumentChunk(BaseModel):
    """
    标准 RAG Chunk 结构。

    用途：
    1. 统一 document loader 输出
    2. 统一 embedding 入参
    3. 统一 Qdrant 入库 payload
    4. 为 reranker / citation 提供稳定字段
    """

    chunk_id: str
    document_id: str

    domain: str

    text: str

    source: str
    source_type: str

    metadata: Dict[str, Any] = Field(default_factory=dict)

    embedding: Optional[List[float]] = None
