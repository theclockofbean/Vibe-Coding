# RAG Retriever 接入设计文档 v0.1

## 1. 文档目的

本文档用于固定 Phase 3-E 中 RAG Retriever 的设计目标、数据结构、检索流程、Qdrant collection 策略、PostgreSQL 元数据表、AgentState 映射、LangGraph RetrievalNode 接入方式、风险边界和回归检查范围。

Phase 3-E 的目标不是简单把文本塞进向量库，而是建立一个面向 Agent Workflow 的可控检索层：

```text
结构化业务事实仍来自 PostgreSQL / 业务模块
RAG 只作为补充证据和知识说明
RAG 不得成为价格、库存、物流、质量、售后承诺来源
检索结果必须可追踪、可过滤、可审计、可回归
```

## 2. 当前系统基础

当前系统已经完成：

```text
Phase 1：spec / price / logistics / quality 四个业务模块
Phase 2：Unified Agent API 与 UnifiedTextQAService
Phase 3-A：Manual Handoff 工单
Phase 3-B：Conversation / Session
Phase 3-C：AgentState
Phase 3-D：LangGraph Workflow Skeleton
```

当前 workflow 已有：

```text
ContextNode
IntentNode
RouteNode
HandlerNode
RetrievalNode placeholder
RiskCtrlNode
RenderNode
```

Phase 3-E 将把 `RetrievalNode` 从 placeholder 升级为真实 RAG 检索节点。

## 3. RAG 在系统中的定位

RAG Retriever 是 Agent Workflow 的证据补充层。

它可以提供：

```text
产品材质解释
表面处理知识
物流规则说明
质量边界说明
售后政策文本引用
FAQ 解释
内部知识库片段
```

它不能提供：

```text
未确认价格
未确认库存
未确认发货承诺
未确认到货承诺
未确认质量保证
未确认质保承诺
未确认退换承诺
未确认赔付承诺
```

统一原则：

```text
RAG 是证据补充，不是事实主库。
RAG 是说明来源，不是业务承诺来源。
RAG 可以增强回答依据，但不能越过结构化规则。
```

## 4. 总体架构

Phase 3-E RAG 架构建议如下：

```text
Knowledge Source
  ↓
Chunking / Cleaning
  ↓
PostgreSQL knowledge_chunks metadata
  ↓
Embedding
  ↓
Qdrant collection
  ↓
Retriever
  ↓
Evidence Filter
  ↓
AgentState.retrieved_chunks
  ↓
RetrievalNode
  ↓
RiskCtrlNode
  ↓
RenderNode
```

核心组件：

```text
KnowledgeChunk 数据契约
KnowledgeChunkRepository
EmbeddingClient 占位接口
QdrantRetriever
HybridRetriever 占位接口
RAGEvidenceFilter
RetrievalNode 接入
RAG 检查脚本
Workflow + RAG 集成检查
```

## 5. 数据分层设计

### 5.1 PostgreSQL 元数据层

PostgreSQL 保存 chunk 元数据和审计信息。

建议新增表：

```text
knowledge_chunks
```

用途：

```text
记录 chunk 来源
记录 chunk 内容摘要
记录 chunk hash
记录所属模块
记录是否启用
记录版本
记录风险等级
记录是否允许用于回答
记录是否允许作为承诺依据
```

### 5.2 Qdrant 向量层

Qdrant 保存向量和检索 payload。

建议 collection：

```text
kb_chunks_v1
```

用途：

```text
向量相似度检索
payload filter
top-k retrieval
module filter
source filter
active filter
risk filter
```

### 5.3 AgentState 状态层

检索结果写入：

```text
state["retrieved_chunks"]
state["source_references"]
```

不直接写入：

```text
state["answer_text"]
state["final_response"]
state["handoff_required"]
state["handoff_ticket_id"]
state["handoff_ticket_no"]
```

## 6. knowledge_chunks 表设计

建议字段：

```text
id
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

字段说明：

```text
chunk_id：业务侧稳定 chunk 标识
collection_name：对应 Qdrant collection
source_type：manual_doc / faq / policy / product_doc / internal_rule
source_name：来源名称
source_uri：来源路径或 URI
doc_id：文档 ID
doc_title：文档标题
chunk_index：文档内 chunk 顺序
module：spec / price / logistics / quality / general
sku_scope：适用 SKU，可为空
intent_scope：适用意图，可为空
content：chunk 原文
content_hash：内容 hash，用于去重
summary：摘要
language：zh / en
risk_level：low / medium / high
is_active：是否启用
is_verified：是否经过人工确认
allow_answer_reference：是否允许作为回答参考
allow_commitment_reference：是否允许作为承诺依据，默认 false
embedding_model：向量模型名称
embedding_dimension：向量维度
qdrant_point_id：Qdrant point ID
version：版本
metadata：扩展字段
```

核心原则：

```text
allow_commitment_reference 默认必须是 false
RAG chunk 即使 is_verified = true，也不自动等于可承诺
涉及价格、物流、质量、售后的承诺仍需结构化规则或人工确认
```

## 7. Qdrant collection 策略

建议 collection：

```text
kb_chunks_v1
```

payload 建议字段：

```json
{
  "chunk_id": "quality_kb_001",
  "source_type": "manual_doc",
  "source_name": "quality_policy_v1",
  "doc_id": "quality_policy",
  "doc_title": "质量边界说明",
  "chunk_index": 1,
  "module": "quality",
  "sku_scope": ["SKU001"],
  "intent_scope": ["surface_treatment", "material_explanation"],
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

建议检索过滤条件：

```text
is_active = true
allow_answer_reference = true
module in [selected_module, general]
language = zh
```

如有 SKU：

```text
sku_scope contains matched_sku
or sku_scope is empty
```

## 8. Embedding 策略

Phase 3-E v0.1 推荐先定义接口，不强绑定模型。

建议接口：

```text
EmbeddingClient
```

核心方法：

```python
def embed_query(text: str) -> list[float]:
    ...
```

后续可接入：

```text
本地 bge-m3
云端 embedding API
OpenAI-compatible embedding endpoint
```

设计要求：

```text
embedding_model 必须记录
embedding_dimension 必须记录
chunk 入库与 query 检索必须使用同一模型族
如果模型变更，应新建 collection 或增加 version
```

## 9. Retriever 接口设计

建议代码文件：

```text
backend/app/agent/rag/retriever.py
```

建议核心类型：

```python
from typing import Any, Protocol


class Retriever(Protocol):
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

建议实现：

```text
NullRetriever
QdrantRetriever
HybridRetriever
```

### 9.1 NullRetriever

用途：

```text
开发占位
无 Qdrant 时降级
测试无副作用
```

行为：

```text
返回 []
不报错
写入 warnings
```

### 9.2 QdrantRetriever

用途：

```text
真实向量检索
payload filter
score threshold
top-k
```

返回结构：

```json
{
  "collection": "kb_chunks_v1",
  "chunk_id": "quality_kb_001",
  "source_type": "manual_doc",
  "source_name": "quality_policy_v1",
  "doc_id": "quality_policy",
  "doc_title": "质量边界说明",
  "module": "quality",
  "content": "……",
  "summary": "……",
  "score": 0.82,
  "risk_level": "medium",
  "is_verified": true,
  "allow_answer_reference": true,
  "allow_commitment_reference": false
}
```

### 9.3 HybridRetriever

Phase 3-E v0.1 可先占位。

后续支持：

```text
Qdrant dense vector
BM25 keyword
RRF fusion
rerank
```

## 10. Evidence Filter 设计

RAG 检索后必须经过 Evidence Filter。

建议规则：

```text
过滤 is_active != true
过滤 allow_answer_reference != true
过滤 score 低于阈值
过滤 module 不匹配的高风险片段
过滤未 verified 的高风险片段
过滤 allow_commitment_reference = false 的承诺类使用
```

输出：

```text
safe_chunks
rejected_chunks
risk_reasons
warnings
```

Evidence Filter 不生成回答，只过滤证据。

## 11. AgentState 映射

RetrievalNode 写入：

```text
retrieved_chunks
source_references
warnings
metadata["retrieval_mode"]
metadata["retrieved_chunk_count"]
metadata["retrieval_rejected_count"]
```

source_references 示例：

```json
{
  "source_type": "rag_chunk",
  "source_name": "quality_policy_v1",
  "reference_id": "quality_kb_001",
  "collection": "kb_chunks_v1",
  "score": 0.82
}
```

禁止写入：

```text
answer_text
final_response
handoff_ticket_id
handoff_ticket_no
价格事实
物流承诺
质量承诺
售后承诺
```

## 12. RetrievalNode 接入策略

当前 Phase 3-D 中 RetrievalNode 是 placeholder。

Phase 3-E 后改为：

```text
读取 user_text
读取 selected_module
读取 matched_sku
读取 conversation_history
调用 Retriever.retrieve()
调用 Evidence Filter
写入 retrieved_chunks
追加 source_references
追加 warnings / risk_reasons
```

伪流程：

```python
chunks = retriever.retrieve(
    query=state["user_text"],
    selected_module=state.get("selected_module"),
    matched_sku=state.get("matched_sku"),
    top_k=5,
)

filtered = evidence_filter.filter(chunks)

state["retrieved_chunks"] = filtered.safe_chunks
state["source_references"].extend(filtered.source_references)
state["warnings"].extend(filtered.warnings)
state["metadata"]["retrieval_mode"] = "qdrant"
```

## 13. 与 HandlerNode 的关系

当前 HandlerNode 已经调用 `UnifiedTextQAService`。

Phase 3-E v0.1 中建议保持顺序：

```text
HandlerNode
  ↓
RetrievalNode
  ↓
RiskCtrlNode
  ↓
RenderNode
```

理由：

```text
结构化模块先给出受控结论
RAG 再补充证据
RiskCtrlNode 统一检查越界
RenderNode 只做最终输出整理
```

后续如接入 LLM RenderNode，可使用：

```text
answer_text
module_payload
retrieved_chunks
source_references
```

作为上下文，但仍不能新增事实。

## 14. 与 RenderNode 的关系

Phase 3-E v0.1 不建议让 RenderNode 自动把 RAG chunk 拼进回答。

原因：

```text
避免 RAG 内容未经表达层安全控制直接出现在最终回答
避免 chunk 中存在非承诺但容易被误读为承诺的表述
```

推荐策略：

```text
v0.1：retrieved_chunks 只写入 AgentState，不直接影响 final_response
v0.2：只在白名单场景下追加“参考说明”
v0.3：LLM RenderNode 根据 retrieved_chunks 做受控改写
```

## 15. 风险控制策略

RiskCtrlNode 必须检查：

```text
RAG chunk 是否被错误用作承诺来源
final_response 是否出现禁止承诺片段
source_references 是否缺失
高风险模块是否未转人工
```

高风险模块包括：

```text
price
logistics
quality
aftersale
```

如果出现：

```text
RAG 内容被用于价格承诺
RAG 内容被用于物流承诺
RAG 内容被用于质量承诺
RAG 内容被用于退换赔付承诺
```

则必须：

```text
risk_triggered = true
handoff_required = true
human_handoff = true
risk_reasons 追加 rag_commitment_boundary_violation
```

## 16. Ingestion 策略

Phase 3-E 可先手工构造小型知识库，用于验证链路。

建议初始知识片段：

```text
质量边界说明
铝合金 6061 一般说明
阳极氧化表面处理说明
物流时效说明边界
报价需人工确认说明
售后承诺边界说明
```

初始 chunk 数量建议：

```text
5 - 20 条
```

不要一开始大量导入。

先验证：

```text
表结构
写入
embedding
Qdrant upsert
retrieval
AgentState 映射
Workflow 集成
风控边界
```

## 17. 目录结构建议

建议新增目录：

```text
backend/app/agent/rag/
```

建议文件：

```text
backend/app/agent/rag/__init__.py
backend/app/agent/rag/schemas.py
backend/app/agent/rag/embedding.py
backend/app/agent/rag/retriever.py
backend/app/agent/rag/evidence_filter.py
```

建议脚本：

```text
backend/scripts/create_knowledge_chunks_table.py
backend/scripts/check_knowledge_chunks_schema.py
backend/scripts/seed_rag_knowledge_chunks.py
backend/scripts/check_rag_retriever_contract.py
backend/scripts/check_workflow_rag_integration.py
backend/scripts/check_phase3e_total_regression.py
```

## 18. 检查范围

### 18.1 Schema 检查

验证：

```text
knowledge_chunks 表存在
字段完整
索引完整
约束完整
allow_commitment_reference 默认 false
```

### 18.2 Retriever Contract 检查

验证：

```text
NullRetriever 返回 []
QdrantRetriever 可初始化
Retriever 返回 list[dict]
每个 chunk 有 chunk_id / content / score / source_name
低分 chunk 被过滤
未启用 chunk 被过滤
未授权 answer_reference chunk 被过滤
```

### 18.3 Workflow + RAG 集成检查

验证：

```text
RetrievalNode 真实执行
metadata["retrieval_mode"] = "qdrant" 或 "null"
retrieved_chunks 写入 AgentState
source_references 追加 rag_chunk
workflow 仍不新增业务承诺
workflow 与旧 API 稳定字段仍一致
```

## 19. 安全边界

RAG 接入后，系统禁止：

```text
用 RAG 生成价格
用 RAG 承诺库存
用 RAG 承诺发货
用 RAG 承诺到货
用 RAG 承诺包邮
用 RAG 承诺质量
用 RAG 承诺不生锈
用 RAG 承诺不掉漆
用 RAG 承诺质保
用 RAG 承诺退换
用 RAG 承诺赔付
```

统一原则：

```text
结构化事实优先。
业务规则优先。
人工确认优先。
RAG 只补充说明。
RAG 不创造承诺。
```

## 20. Phase 3-E v0.1 交付目标

本阶段完成后，应具备：

```text
knowledge_chunks 元数据表
RAG schemas
EmbeddingClient 占位接口
NullRetriever
QdrantRetriever 基础实现
EvidenceFilter
RetrievalNode 接入真实 retriever
RAG 合同检查
Workflow + RAG 集成检查
Phase 3-E 总回归检查
```

## 21. 最终结论

Phase 3-E 是从“Agent Workflow 骨架”进入“知识增强 Agent”的关键阶段。

技术重点是：

```text
向量检索不是答案生成
RAG 结果不是业务承诺
检索证据必须可审计
检索结果必须经过过滤
Workflow 必须保持可回归
风险控制必须覆盖 RAG 越界
```

完成后，系统将具备后续接入 LLM RenderNode、LLM IntentNode、RAG answer grounding 和多轮知识增强问答的基础。