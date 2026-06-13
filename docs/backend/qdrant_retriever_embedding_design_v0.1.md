# QdrantRetriever + Embedding 接入设计文档 v0.1

## 1. 文档目的

本文档用于固定 Phase 3-F 中 QdrantRetriever 与 Embedding 接入的设计目标、组件边界、数据流、collection 策略、embedding 策略、Qdrant point 策略、fallback 策略、LangGraph RetrievalNode 接入方式、风险控制边界和回归检查范围。

Phase 3-F 的目标不是让 RAG 生成最终回答，而是把 Phase 3-E 中的本地检索链路升级为真实向量检索链路：

```text
knowledge_chunks metadata
  ↓
EmbeddingClient
  ↓
Qdrant collection
  ↓
QdrantRetriever
  ↓
RAGEvidenceFilter
  ↓
AgentState.retrieved_chunks
  ↓
AgentState.source_references
```

统一原则：

```text
Qdrant 是检索引擎，不是事实主库。
Embedding 是相似度工具，不是业务判断工具。
RAG 是证据补充，不是业务承诺来源。
结构化事实优先。
业务规则优先。
人工确认优先。
LLM 不是事实来源。
RAG 不是承诺来源。
```

## 2. 当前系统基础

Phase 3-E 已完成：

```text
knowledge_chunks 表
KnowledgeChunk / RetrievedChunk / RetrievalQuery / RetrievalResult
EmbeddingClient Protocol
DeterministicHashEmbeddingClient
NullRetriever
LocalKnowledgeChunkRetriever
RAGEvidenceFilter
KnowledgeChunkRepository
Seed RAG Knowledge Chunks
RetrievalNode + LocalRetriever + EvidenceFilter 集成
Phase 3-E total regression
```

Phase 3-F 将在此基础上新增：

```text
Qdrant collection 管理
Embedding 写入流程
Qdrant point upsert
QdrantRetriever
Retriever fallback 策略
Workflow RetrievalNode retriever_mode 切换
Phase 3-F total regression
```

## 3. 阶段边界

Phase 3-F v0.1 做：

```text
检查 Qdrant 服务可用性
创建 / 验证 Qdrant collection
为 seed chunks 生成 embedding
将 seed chunks upsert 到 Qdrant
将 qdrant_point_id / embedding_model / embedding_dimension 回写 knowledge_chunks
实现 QdrantRetriever
实现 QdrantRetriever + EvidenceFilter 检查
实现 LocalRetriever fallback
让 RetrievalNode 支持 local_postgres / qdrant 两种 retrieval_mode
```

Phase 3-F v0.1 不做：

```text
不调用 LLM 生成回答
不让 RAG 改写最终回答
不实现 hybrid search
不实现 BM25
不实现 RRF
不实现 rerank
不把 Qdrant 结果作为价格、库存、物流、质量、售后承诺来源
```

## 4. 总体架构

目标架构：

```text
Seed Knowledge Chunks
  ↓
KnowledgeChunkRepository
  ↓
EmbeddingClient
  ↓
QdrantVectorStore
  ↓
Qdrant kb_chunks_v1
  ↓
QdrantRetriever
  ↓
RAGEvidenceFilter
  ↓
LangGraph RetrievalNode
  ↓
AgentState.retrieved_chunks / source_references
```

执行链路：

```text
1. PostgreSQL knowledge_chunks 保存 chunk 元数据
2. EmbeddingClient 对 chunk content 生成向量
3. QdrantVectorStore upsert point
4. Repository 回写 qdrant_point_id / embedding_model / embedding_dimension
5. QdrantRetriever 根据 query embedding 检索 point
6. RetrievedChunk 统一转为标准 dict
7. EvidenceFilter 过滤后写入 AgentState
```

## 5. Qdrant collection 策略

collection 名称：

```text
kb_chunks_v1
```

collection 维度：

```text
与 embedding_dimension 保持一致
```

Phase 3-F v0.1 推荐继续使用：

```text
DeterministicHashEmbeddingClient
```

作为本地可回归 embedding，占位维度：

```text
8
```

后续切换真实 embedding 时，应新建 collection，例如：

```text
kb_chunks_bge_m3_v1
kb_chunks_openai_v1
kb_chunks_qwen_embedding_v1
```

不建议在同一个 collection 中混用不同 embedding model 或不同 dimension。

## 6. Qdrant point payload 设计

每个 point 对应一个 knowledge chunk。

point id 推荐使用：

```text
chunk_id
```

payload 字段：

```json
{
  "chunk_id": "seed_quality_material_6061",
  "collection_name": "kb_chunks_v1",
  "source_type": "manual_doc",
  "source_name": "phase3e_seed_knowledge",
  "source_uri": "manual://phase3e/material-6061",
  "doc_id": "quality_material_v1",
  "doc_title": "铝合金 6061 材料说明",
  "chunk_index": 0,
  "module": "quality",
  "sku_scope": ["SKU001"],
  "intent_scope": ["material_explanation"],
  "content": "……",
  "summary": "……",
  "language": "zh",
  "risk_level": "medium",
  "is_active": true,
  "is_verified": true,
  "allow_answer_reference": true,
  "allow_commitment_reference": false,
  "version": "v1"
}
```

payload 必须保留：

```text
module
sku_scope
language
is_active
allow_answer_reference
allow_commitment_reference
risk_level
is_verified
```

原因：

```text
QdrantRetriever 需要 payload filter。
EvidenceFilter 需要风控字段。
source_references 需要可审计来源。
```

## 7. Embedding 策略

当前已有：

```text
EmbeddingClient Protocol
DeterministicHashEmbeddingClient
validate_embedding_vector()
```

Phase 3-F v0.1 推荐保持 deterministic embedding，用于验证：

```text
embedding 生成
dimension 校验
Qdrant upsert
Qdrant search
回归稳定性
```

后续真实 embedding 接入时，再新增：

```text
OpenAICompatibleEmbeddingClient
QwenEmbeddingClient
BGEEmbeddingClient
```

EmbeddingClient 必须满足：

```text
同一文本稳定输出同一向量
向量维度固定
空文本拒绝
写入和查询使用同一 embedding_model
embedding_model / embedding_dimension 必须记录到 knowledge_chunks
```

## 8. 新增组件规划

建议新增文件：

```text
backend/app/agent/rag/qdrant_store.py
backend/app/agent/rag/qdrant_retriever.py
```

也可以先集中在：

```text
backend/app/agent/rag/qdrant.py
```

但为了工程清晰，推荐拆分为：

```text
qdrant_store.py       # collection / upsert / search 底层封装
qdrant_retriever.py   # Retriever 协议实现
```

## 9. QdrantVectorStore 设计

核心职责：

```text
检查 Qdrant 服务可用
创建 collection
检查 collection 存在
upsert chunks
search query vector
delete point
```

建议方法：

```python
class QdrantVectorStore:
    def collection_exists(self, collection_name: str) -> bool:
        ...

    def ensure_collection(
        self,
        *,
        collection_name: str,
        vector_size: int,
    ) -> None:
        ...

    def upsert_chunk(
        self,
        *,
        collection_name: str,
        point_id: str,
        vector: list[float],
        payload: dict[str, object],
    ) -> None:
        ...

    def search(
        self,
        *,
        collection_name: str,
        query_vector: list[float],
        selected_module: str | None,
        matched_sku: str | None,
        top_k: int,
        score_threshold: float,
    ) -> list[dict[str, object]]:
        ...
```

## 10. QdrantRetriever 设计

QdrantRetriever 实现 Retriever Protocol：

```python
class QdrantRetriever:
    def retrieve(
        self,
        *,
        query: str,
        selected_module: str | None,
        matched_sku: str | None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        ...
```

内部流程：

```text
1. 构造 RetrievalQuery
2. EmbeddingClient.embed_query(query)
3. validate_embedding_vector()
4. QdrantVectorStore.search()
5. 将 Qdrant result 转为 RetrievedChunk dict
6. 返回 list[dict]
```

返回数据仍必须符合 RetrievedChunk.to_dict() 结构。

## 11. Qdrant filter 策略

基础 filter：

```text
is_active = true
allow_answer_reference = true
language = zh
```

模块 filter：

```text
module = selected_module
OR module = general
```

SKU filter：

```text
sku_scope contains matched_sku
OR sku_scope is empty
```

高风险 chunk 不在 Qdrant 层直接排除，而由 EvidenceFilter 再做：

```text
risk_level = high 且 is_verified = false → reject
commitment_context = true 且 allow_commitment_reference = false → reject
```

原因：

```text
Qdrant 负责召回。
EvidenceFilter 负责安全过滤。
```

## 12. Retriever fallback 策略

Phase 3-F 后 RetrievalNode 支持：

```text
qdrant
local_postgres
null
```

优先级：

```text
1. 如果 Qdrant 可用且 collection ready → QdrantRetriever
2. 如果 Qdrant 不可用 → LocalKnowledgeChunkRetriever
3. 如果 DB session 不可用 → NullRetriever
```

metadata 记录：

```text
retrieval_mode = qdrant
retrieval_mode = local_postgres
retrieval_mode = null
retrieval_fallback_reason
```

不能因为 Qdrant 不可用导致主 Agent 失败。

## 13. Workflow RetrievalNode 接入

Phase 3-F RetrievalNode 目标：

```text
读取 user_text
推断 retrieval_module
推断 matched_sku
选择 retriever
执行 retrieve
执行 EvidenceFilter
写入 retrieved_chunks
合并 source_references
写入 warnings / risk_reasons
写入 metadata
```

新增 metadata：

```text
retrieval_mode
retrieval_fallback_reason
retrieval_collection_name
retrieval_embedding_model
retrieval_embedding_dimension
retrieved_chunk_count
retrieval_rejected_count
retrieval_warning_count
retrieval_filter
```

## 14. 写入脚本规划

建议新增脚本：

```text
backend/scripts/check_qdrant_connection.py
backend/scripts/create_qdrant_collection.py
backend/scripts/upsert_seed_chunks_to_qdrant.py
backend/scripts/check_qdrant_seed_points.py
backend/scripts/check_qdrant_retriever.py
backend/scripts/check_workflow_qdrant_rag_integration.py
backend/scripts/check_phase3f_total_regression.py
```

## 15. 检查范围

### 15.1 Qdrant Connection Check

验证：

```text
Qdrant REST 可连接
collection API 可访问
服务不可用时输出明确错误
```

### 15.2 Collection Check

验证：

```text
kb_chunks_v1 存在
vector_size = 8
distance = cosine
```

### 15.3 Upsert Check

验证：

```text
seed chunks 可生成 embedding
embedding vector dimension 正确
points 可 upsert
qdrant_point_id 回写 knowledge_chunks
embedding_model 回写 knowledge_chunks
embedding_dimension 回写 knowledge_chunks
```

### 15.4 QdrantRetriever Check

验证：

```text
quality query 可召回 quality chunks
price query 可召回 price boundary
logistics query 可召回 logistics boundary
SKU scope 不泄漏
返回 dict 符合 RetrievedChunk contract
所有 allow_commitment_reference 保持 false
```

### 15.5 Workflow Qdrant Integration Check

验证：

```text
RetrievalNode 使用 qdrant
retrieval_mode = qdrant
retrieved_chunks 非空
source_references 出现 rag_chunk
workflow 不新增 conversation_messages
workflow 不新增 handoff_tickets
workflow 不产生禁止承诺片段
Qdrant 不可用时 fallback 到 local_postgres
```

## 16. 安全边界

Qdrant 接入后仍禁止：

```text
用 Qdrant 结果生成价格
用 Qdrant 结果承诺库存
用 Qdrant 结果承诺发货
用 Qdrant 结果承诺到货
用 Qdrant 结果承诺包邮
用 Qdrant 结果承诺质量
用 Qdrant 结果承诺不生锈
用 Qdrant 结果承诺不掉漆
用 Qdrant 结果承诺质保
用 Qdrant 结果承诺退换
用 Qdrant 结果承诺赔付
```

统一安全规则：

```text
Qdrant result 必须经过 EvidenceFilter。
RAG chunk 不直接进入 final_response。
RAG source_references 只作为证据来源。
业务承诺仍由结构化规则或人工确认决定。
```

## 17. Phase 3-F v0.1 交付目标

本阶段完成后，应具备：

```text
Qdrant connection check
Qdrant collection creation
Seed chunk embedding
Seed chunk point upsert
KnowledgeChunkRepository mark_qdrant_point
QdrantRetriever
QdrantRetriever + EvidenceFilter check
Workflow RetrievalNode qdrant mode
LocalRetriever fallback
Phase 3-F total regression
```

## 18. 后续演进

Phase 3-F 后可进入：

```text
Phase 3-G：LLMClient 接入
Phase 3-H：Grounded RenderNode
Phase 3-I：Hybrid Search / RRF / Rerank
Phase 3-J：Streaming / Checkpoint
```

## 19. 最终结论

Phase 3-F 的关键目标是把 RAG 从“本地 PostgreSQL 检索”升级为“真实向量检索”，同时不放松任何业务边界。

本阶段完成后，系统将具备：

```text
PostgreSQL metadata
Qdrant vector search
Embedding pipeline
Retriever fallback
AgentState evidence injection
LangGraph RetrievalNode qdrant mode
Risk-controlled RAG retrieval
```

这将为后续 LLM grounded answer rendering 打下基础。
