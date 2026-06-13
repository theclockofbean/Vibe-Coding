# Phase 3-E RAG Retriever 最终归档文档 v0.1

## 1. 阶段结论

Phase 3-E 已完成 RAG Retriever v0.1 的工程化落地，并通过总回归检查。

当前系统已经具备：

```text
knowledge_chunks 元数据表
RAG schemas
EmbeddingClient Protocol
DeterministicHashEmbeddingClient
NullRetriever
RAGEvidenceFilter
KnowledgeChunkRepository
Seed RAG Knowledge Chunks
LocalKnowledgeChunkRetriever
LangGraph RetrievalNode + LocalRetriever + EvidenceFilter 集成
Phase 3-E 总回归检查
```

Phase 3-E 的核心价值是：系统已经从 LangGraph Workflow Skeleton 进入“可控知识增强 Agent”阶段。

当前 RAG v0.1 仍不接 Qdrant、不调用 LLM、不改写最终回答，而是先完成：

```text
证据元数据结构
本地检索链路
证据过滤层
AgentState 注入
Workflow 集成
安全边界验证
```

## 2. 阶段边界

Phase 3-E v0.1 明确不做：

```text
不调用 Qdrant
不调用真实 embedding API
不调用 LLM
不让 RAG 直接生成最终回答
不让 RAG 产生价格、库存、物流、质量、售后承诺
不替换结构化业务事实来源
```

统一原则：

```text
RAG 是证据补充，不是事实主库。
RAG 是说明来源，不是业务承诺来源。
结构化事实优先。
业务规则优先。
人工确认优先。
LLM 不是事实来源。
RAG 不是承诺来源。
```

## 3. 已实现数据库结构

新增 PostgreSQL 元数据表：

```text
knowledge_chunks
```

核心字段：

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
content_hash
summary
language
risk_level
is_active
is_verified
allow_answer_reference
allow_commitment_reference
embedding_model
embedding_dimension
qdrant_point_id
version
metadata
created_at
updated_at
```

关键约束：

```text
module IN ('spec', 'price', 'logistics', 'quality', 'general')
risk_level IN ('low', 'medium', 'high')
content_hash 必须为 sha256
embedding_dimension 必须为正数或 NULL
allow_commitment_reference = TRUE 时必须 is_verified = TRUE
```

关键安全默认值：

```text
allow_commitment_reference = FALSE
allow_answer_reference = TRUE
is_active = TRUE
is_verified = FALSE
collection_name = kb_chunks_v1
language = zh
version = v1
```

## 4. 已实现代码文件

### 4.1 表结构脚本

```text
backend/scripts/create_knowledge_chunks_table.py
backend/scripts/check_knowledge_chunks_schema.py
backend/scripts/reset_knowledge_chunks_table.py
```

### 4.2 RAG 契约层

```text
backend/app/agent/rag/__init__.py
backend/app/agent/rag/schemas.py
backend/app/agent/rag/embedding.py
backend/app/agent/rag/retriever.py
backend/app/agent/rag/evidence_filter.py
```

核心对象：

```text
KnowledgeChunk
RetrievedChunk
RetrievalQuery
RetrievalResult
EmbeddingClient
DeterministicHashEmbeddingClient
Retriever
NullRetriever
LocalKnowledgeChunkRetriever
RAGEvidenceFilter
EvidenceFilterResult
```

### 4.3 Repository 层

```text
backend/app/repositories/knowledge_chunk_repository.py
```

核心方法：

```text
upsert_chunk()
get_by_chunk_id()
list_for_retrieval()
count_for_retrieval()
mark_qdrant_point()
set_active()
```

### 4.4 Seed 数据脚本

```text
backend/scripts/seed_rag_knowledge_chunks.py
backend/scripts/check_rag_seed_knowledge_chunks.py
```

已写入 7 条初始知识片段：

```text
seed_general_rag_boundary
seed_spec_parameter_boundary
seed_quality_material_6061
seed_quality_anodized_surface
seed_price_boundary
seed_logistics_boundary
seed_aftersale_boundary
```

覆盖模块：

```text
general
spec
price
logistics
quality
```

### 4.5 检索与过滤检查

```text
backend/scripts/check_rag_retriever_contract.py
backend/scripts/check_rag_evidence_filter.py
backend/scripts/check_knowledge_chunk_repository.py
backend/scripts/check_local_rag_retriever.py
backend/scripts/check_workflow_rag_integration.py
```

### 4.6 总回归脚本

```text
backend/scripts/check_phase3e_total_regression.py
```

## 5. EvidenceFilter 能力

`RAGEvidenceFilter` 是 RAG 证据进入 AgentState 前的安全门。

过滤规则包括：

```text
过滤 inactive chunk
过滤 allow_answer_reference = false 的 chunk
过滤低分 chunk
过滤模块不匹配 chunk
过滤未 verified 的 high risk chunk
过滤 commitment_context 下 allow_commitment_reference = false 的 chunk
```

输出结构：

```text
safe_chunks
rejected_chunks
source_references
warnings
risk_reasons
metadata
```

这保证检索结果不会绕过风控直接进入回答链路。

## 6. LocalKnowledgeChunkRetriever 能力

`LocalKnowledgeChunkRetriever` 是一个 PostgreSQL-backed deterministic retriever。

当前作用：

```text
基于 knowledge_chunks 表读取候选 chunk
支持 selected_module 过滤
支持 matched_sku 过滤
支持 general chunk 兜底
使用本地 deterministic relevance score 排序
返回 RetrievedChunk dict
不写数据库
不调用 Qdrant
不调用 LLM
```

它的定位是：

```text
Phase 3-E v0.1 的本地检索器
后续 QdrantRetriever 的 fallback
Workflow + RAG 集成检查基础
```

## 7. LangGraph RetrievalNode 集成

Phase 3-D 中 RetrievalNode 原本是 placeholder。

Phase 3-E 已升级为：

```text
RetrievalNode
  ↓
LocalKnowledgeChunkRetriever
  ↓
RAGEvidenceFilter
  ↓
AgentState.retrieved_chunks
  ↓
AgentState.source_references
  ↓
RiskCtrlNode
```

当前写入 AgentState：

```text
retrieved_chunks
source_references
warnings
risk_reasons
metadata["retrieval_mode"]
metadata["retrieved_chunk_count"]
metadata["retrieval_rejected_count"]
metadata["retrieval_warning_count"]
metadata["retrieval_selected_module"]
metadata["retrieval_matched_sku"]
metadata["retrieval_filter"]
```

当前 `retrieval_mode`：

```text
local_postgres
```

## 8. Workflow 集成验证

已验证：

```text
quality 查询可检索 quality RAG chunks
price 查询可检索 price boundary chunks
logistics 查询可检索 logistics boundary chunks
SKU scope 不泄漏到无关 SKU
source_references 中追加 rag_chunk
retrieved_chunks 写入 AgentState
workflow 不新增 conversation_messages
workflow 不新增 handoff_tickets
workflow 不产生禁止承诺片段
```

典型检索结果：

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

## 9. 已修复问题归档

Phase 3-E 中已修复以下工程问题：

```text
旧版 knowledge_chunks 表结构不兼容
check_set_active SQLAlchemy transaction already begun
PowerShell replace 写入非法 `r`n 字符
KnowledgeChunkRepository RowMapping mypy 类型问题
ConversationRepository optional int mypy 问题
RetrievalNode apply_retrieved_chunks 调用方式不匹配
RetrievalNode 获取不到 repository session 后降级 NullRetriever
RetrievalNode 需要独立推断 retrieval_module
KnowledgeChunkRepository 与 retriever 循环导入
总回归中 repository check 被 seed rows 干扰
```

## 10. Phase 3-E 总回归

总回归脚本：

```text
backend/scripts/check_phase3e_total_regression.py
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
workflow_rag_integration
```

最终结果：

```text
phase3-e total regression passed
```

## 11. 当前技术价值

Phase 3-E 已体现以下 Agent / RAG 工程能力：

```text
RAG 元数据建模
PostgreSQL metadata + 未来 Qdrant point 绑定预留
RAG schemas 契约化
EmbeddingClient 可替换接口
NullRetriever 安全降级
LocalRetriever 本地检索 fallback
EvidenceFilter 风控前置
AgentState 证据注入
LangGraph RetrievalNode 真实化
Workflow + RAG 集成回归
业务承诺边界隔离
```

这说明当前系统已经具备从“结构化业务 Agent”扩展为“知识增强 Agent”的基础能力。

## 12. 当前限制

Phase 3-E v0.1 仍不支持：

```text
真实 Qdrant 向量检索
真实 embedding API
chunk embedding 写入
Qdrant collection 创建
Qdrant point upsert
dense vector search
hybrid search
BM25
RRF fusion
rerank
LLM grounded answer rendering
RAG 引用自动拼接到最终回答
```

这些应在后续阶段继续完成。

## 13. 后续建议

下一阶段建议进入：

```text
Phase 3-F：QdrantRetriever + Embedding 接入
```

推荐顺序：

```text
1. Qdrant collection 管理脚本
2. EmbeddingClient 真实实现或本地可替代实现
3. seed chunks embedding 生成
4. Qdrant point upsert
5. QdrantRetriever 实现
6. QdrantRetriever + EvidenceFilter 检查
7. LocalRetriever fallback 策略
8. Workflow RetrievalNode 支持 retriever_mode 切换
9. Phase 3-F 总回归
```

## 14. 最终结论

Phase 3-E 可以归档。

当前系统已经完成从：

```text
LangGraph Workflow Skeleton
→ knowledge_chunks 元数据层
→ RAG schemas
→ EvidenceFilter
→ LocalRetriever
→ RetrievalNode 真实检索
→ Workflow + RAG 集成回归
```

的阶段性升级。

Phase 3-E 为后续 Qdrant、Embedding、Hybrid Retrieval、LLM grounded rendering 打好了基础。
