# Phase 3-F QdrantRetriever + Embedding 最终归档文档 v0.1

## 1. 阶段结论

Phase 3-F 已完成 QdrantRetriever + Embedding 接入，并通过总回归检查。

当前系统已经从 Phase 3-E 的本地 PostgreSQL RAG 检索升级为：

```text
PostgreSQL knowledge_chunks metadata
  ↓
EmbeddingClient
  ↓
Qdrant kb_chunks_v1 collection
  ↓
QdrantRetriever
  ↓
RAGEvidenceFilter
  ↓
LangGraph RetrievalNode
  ↓
AgentState.retrieved_chunks / source_references
```

Phase 3-F 的核心价值是：系统已经具备真实向量检索链路，并且保持了结构化事实优先、业务规则优先、人工确认优先的安全边界。

## 2. 阶段边界

Phase 3-F 已完成：

```text
Qdrant REST 连接检查
QdrantVectorStore 基础封装
kb_chunks_v1 collection 创建与校验
Seed chunks deterministic embedding 生成
Seed chunks Qdrant point upsert
knowledge_chunks qdrant_point_id / embedding_model / embedding_dimension 回写
QdrantRetriever 实现
QdrantRetriever + EvidenceFilter 检查
Workflow RetrievalNode 优先 QdrantRetriever
Qdrant 不可用时 fallback 到 LocalKnowledgeChunkRetriever
Phase 3-F 总回归
```

Phase 3-F 仍明确不做：

```text
不调用 LLM 生成最终回答
不让 RAG 改写 final_response
不实现 hybrid search
不实现 BM25
不实现 RRF
不实现 rerank
不把 Qdrant 结果作为价格、库存、物流、质量、售后承诺来源
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

## 3. 已实现代码文件

### 3.1 Qdrant Store

```text
backend/app/agent/rag/qdrant_store.py
```

核心对象：

```text
QdrantVectorStore
QdrantCollectionConfig
QdrantStoreError
```

核心常量：

```text
DEFAULT_QDRANT_URL = http://127.0.0.1:6333
DEFAULT_QDRANT_COLLECTION = kb_chunks_v1
DEFAULT_QDRANT_VECTOR_SIZE = 8
DEFAULT_QDRANT_DISTANCE = Cosine
```

核心能力：

```text
list_collections()
collection_exists()
ensure_collection()
get_collection_config()
assert_collection_config()
upsert_point()
get_points()
search_points()
```

### 3.2 Qdrant Retriever

```text
backend/app/agent/rag/qdrant_retriever.py
```

核心对象：

```text
QdrantRetriever
build_default_qdrant_retriever()
```

核心能力：

```text
EmbeddingClient.embed_query()
validate_embedding_vector()
QdrantVectorStore.search_points()
Qdrant point payload → RetrievedChunk-compatible dict
module / general 过滤
SKU scope 过滤
deterministic lexical score 补充排序
```

### 3.3 RAG exports

```text
backend/app/agent/rag/__init__.py
```

已导出：

```text
QdrantVectorStore
QdrantStoreError
QdrantCollectionConfig
QdrantRetriever
build_default_qdrant_retriever
DEFAULT_QDRANT_URL
DEFAULT_QDRANT_COLLECTION
DEFAULT_QDRANT_VECTOR_SIZE
DEFAULT_QDRANT_DISTANCE
```

### 3.4 Workflow

```text
backend/app/agent/workflow.py
```

RetrievalNode 已升级为：

```text
优先 QdrantRetriever
失败或无结果时 fallback 到 LocalKnowledgeChunkRetriever
统一经过 RAGEvidenceFilter
写入 AgentState.retrieved_chunks
合并 AgentState.source_references
记录 retrieval metadata
```

## 4. 新增脚本

```text
backend/scripts/check_qdrant_connection.py
backend/scripts/create_qdrant_collection.py
backend/scripts/check_qdrant_collection.py
backend/scripts/upsert_seed_chunks_to_qdrant.py
backend/scripts/check_qdrant_seed_points.py
backend/scripts/check_qdrant_retriever.py
backend/scripts/check_workflow_qdrant_rag_integration.py
backend/scripts/check_phase3f_total_regression.py
```

## 5. Qdrant collection

Collection 名称：

```text
kb_chunks_v1
```

配置：

```text
vector_size = 8
distance = Cosine
status = green
```

当前 embedding：

```text
deterministic-hash-embedding-v1
```

当前向量维度：

```text
8
```

说明：

```text
该 collection 用于 Phase 3-F 本地可回归测试。
后续接入真实 embedding model 时，应创建新的 collection，避免不同 embedding model 或不同 dimension 混用。
```

## 6. Qdrant point 设计

Qdrant point id 使用：

```text
uuid5(namespace, chunk_id)
```

原因：

```text
Qdrant point id 通常要求整数或 UUID。
chunk_id 保留在 payload 中作为业务主键与审计标识。
```

Payload 保留字段：

```text
chunk_id
collection_name
source_type
source_name
source_uri
doc_id
doc_title
chunk_index
module
sku_scope
intent_scope
content
summary
language
risk_level
is_active
is_verified
allow_answer_reference
allow_commitment_reference
version
metadata
```

这些字段用于：

```text
QdrantRetriever 检索过滤
RAGEvidenceFilter 安全过滤
source_references 审计引用
AgentState 证据注入
```

## 7. Seed chunks upsert

Seed source：

```text
phase3e_seed_knowledge
```

已 upsert 的 seed chunks：

```text
seed_general_rag_boundary
seed_spec_parameter_boundary
seed_quality_material_6061
seed_quality_anodized_surface
seed_price_boundary
seed_logistics_boundary
seed_aftersale_boundary
```

回写 PostgreSQL 字段：

```text
qdrant_point_id
embedding_model
embedding_dimension
```

校验项：

```text
Qdrant points 数量正确
Qdrant payload 与 PostgreSQL metadata 一致
embedding_model = deterministic-hash-embedding-v1
embedding_dimension = 8
allow_commitment_reference = false
禁止承诺片段未出现
```

## 8. QdrantRetriever 能力

QdrantRetriever 已验证：

```text
quality query 可召回 seed_quality_material_6061
quality query 可召回 seed_quality_anodized_surface
price query 可召回 seed_price_boundary
logistics query 可召回 seed_logistics_boundary
SKU999 不召回 SKU001 scoped quality chunks
general boundary chunks 可作为兜底证据
返回 dict 兼容 EvidenceFilter
allow_commitment_reference 保持 false
```

典型结果：

```text
SKU001 阳极氧化 表面处理 材质说明
→ seed_quality_material_6061
→ seed_quality_anodized_surface
→ seed_general_rag_boundary
```

```text
SKU001 多少钱 报价 价格边界
→ seed_price_boundary
→ seed_general_rag_boundary
```

```text
SKU001 发货 物流 到货 时效边界
→ seed_logistics_boundary
→ seed_general_rag_boundary
```

## 9. Workflow Qdrant 集成

Workflow RetrievalNode 当前数据流：

```text
user_text
  ↓
_infer_retrieval_module()
  ↓
_infer_retrieval_matched_sku()
  ↓
_retrieve_qdrant_rag_chunks()
  ↓
QdrantRetriever
  ↓
RAGEvidenceFilter
  ↓
AgentState.retrieved_chunks
  ↓
AgentState.source_references
  ↓
RiskCtrlNode
  ↓
RenderNode
```

Qdrant 正常时：

```text
metadata["retrieval_mode"] = "qdrant"
```

Qdrant 不可用时：

```text
metadata["retrieval_mode"] = "local_postgres"
metadata["retrieval_fallback_reason"] 非空
```

当前写入 metadata：

```text
retrieval_mode
retrieval_fallback_reason
retrieval_collection_name
retrieval_embedding_model
retrieval_embedding_dimension
retrieval_qdrant_url
retrieved_chunk_count
retrieval_rejected_count
retrieval_warning_count
retrieval_selected_module
retrieval_matched_sku
retrieval_filter
```

已验证：

```text
Workflow 使用 QdrantRetriever
retrieval_mode = qdrant
retrieved_chunks 非空
source_references 包含 rag_chunk
fallback case 中 retrieval_mode = local_postgres
workflow 不新增 conversation_messages
workflow 不新增 handoff_tickets
workflow 不产生禁止承诺片段
```

## 10. 已修复问题归档

Phase 3-F 中已修复以下问题：

```text
PowerShell 局部替换写入字面量 `r`n 导致 __init__.py 语法错误
Qdrant point id 不能直接使用普通 chunk_id，改为 uuid5 稳定 UUID
QdrantRetriever 返回 collection_name，但 EvidenceFilter 期望 collection，已兼容双字段
Qdrant fallback 测试中 http.client.BadStatusLine 未被包装，已在 QdrantVectorStore 中捕获 HTTPException 并转为 QdrantStoreError
Workflow Qdrant fallback 已验证
```

## 11. Phase 3-F 总回归

总回归脚本：

```text
backend/scripts/check_phase3f_total_regression.py
```

通过项目：

```text
phase3c_total_regression
langgraph_installation
create_knowledge_chunks_table
knowledge_chunks_schema
rag_retriever_contract
rag_evidence_filter
knowledge_chunk_repository
seed_rag_knowledge_chunks
rag_seed_knowledge_chunks
local_rag_retriever
qdrant_connection
create_qdrant_collection
qdrant_collection
upsert_seed_chunks_to_qdrant
qdrant_seed_points
qdrant_retriever
workflow_qdrant_rag_integration
```

最终结果：

```text
phase3-f total regression passed
```

## 12. 当前技术价值

Phase 3-F 已体现以下能力：

```text
Qdrant REST API 封装
Vector collection 管理
EmbeddingClient 接口复用
Deterministic embedding 可回归测试
Qdrant point payload 建模
PostgreSQL metadata 与 Qdrant point 绑定
QdrantRetriever 实现
Vector search + local lexical score 组合排序
RAGEvidenceFilter 安全过滤
LangGraph RetrievalNode Qdrant 模式
Qdrant unavailable fallback
AgentState evidence injection
RAG source reference 审计链路
```

系统已经从：

```text
本地 RAG 检索
```

升级为：

```text
PostgreSQL metadata + Qdrant vector search + EvidenceFilter + LangGraph RetrievalNode
```

## 13. 当前限制

Phase 3-F v0.1 仍不支持：

```text
真实 embedding API
OpenAI / Qwen / BGE embedding client
大规模文档切片
增量 embedding
向量删除与重建策略
hybrid search
BM25
RRF fusion
rerank
LLM grounded answer rendering
RAG 引用自动进入 final_response
checkpoint / streaming
```

## 14. 后续建议

下一阶段建议进入：

```text
Phase 3-G：LLMClient 接入
```

推荐顺序：

```text
1. LLMClient Protocol
2. RuleBasedLLMClient / EchoLLMClient 测试实现
3. OpenAI-compatible client 预留
4. LLM request / response schema
5. LLM safety wrapper
6. LLM 不可用 fallback
7. 不让 LLM 成为事实源的边界检查
8. LangGraph 可选 LLM node 设计
9. Phase 3-G 总回归
```

Phase 3-H 再进入：

```text
Grounded RenderNode
RAG references + structured facts + business rules 合成回答
```

## 15. 最终结论

Phase 3-F 可以归档。

当前系统已完成：

```text
knowledge_chunks metadata
EmbeddingClient
Qdrant collection
Qdrant point upsert
QdrantRetriever
EvidenceFilter
LangGraph RetrievalNode qdrant mode
LocalRetriever fallback
Phase 3-F total regression
```

Phase 3-F 为后续 LLMClient、Grounded RenderNode、Hybrid Retrieval、Rerank 与多渠道客服 Agent 打好了基础。
