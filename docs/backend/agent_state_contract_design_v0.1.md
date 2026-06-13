# AgentState 契约设计文档 v0.1

## 1. 文档目的

本文档用于固定 Phase 3-C 中 AgentState 的字段结构、字段含义、节点写入边界、与现有模块的映射关系，以及后续 LangGraph Workflow 的迁移基础。

AgentState 是未来 LangGraph Agent 工作流中的统一状态对象。

它用于串联：

```text
Conversation / Session 上下文
IntentRouter 意图识别
业务模块 Handler
Handoff Ticket 人工接管
Risk Control 风控拦截
RAG 检索结果
LLM 渲染与改写
最终响应输出
```

## 2. 当前背景

当前系统已经完成：

```text
Phase 1：spec / price / logistics / quality 四个业务模块
Phase 2：Unified Agent API 与 UnifiedTextQAService
Phase 3-A：Manual Handoff 工单自动创建与查询
Phase 3-B：Conversation / Session 会话与消息历史
```

当前系统已经有以下数据结构：

```text
UnifiedTextQAResult
Unified Agent API response payload
handoff_tickets
conversations
conversation_messages
```

但这些结构目前仍是分散的。

Phase 3-C 的目标是固定一个统一状态对象：

```text
AgentState
```

后续 LangGraph 每一个节点都只读写 AgentState，而不是互相直接耦合。

## 3. AgentState 定位

AgentState 是 Agent 工作流的单次请求状态快照。

它表示：

```text
一次用户输入从进入系统到生成最终回答的完整状态
```

它不是数据库模型。

它不是 API 请求模型。

它不是 LLM prompt。

它是内部 Agent workflow 的状态契约。

## 4. AgentState 总体结构

建议后续代码文件：

```text
backend/app/agent/state.py
```

建议核心类型：

```python
from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    session_id: str | None
    conversation_id: int | None
    channel: str | None
    user_id: str | None

    user_text: str
    normalized_text: str | None

    conversation_history: list[dict[str, Any]]

    intent: str | None
    selected_module: str | None
    candidate_modules: list[str]
    matched_signals: list[str]
    matched_sku: str | None

    route_status: str | None
    route_confidence: float | None
    parse_status: str | None
    handler_status: str | None

    retrieved_chunks: list[dict[str, Any]]

    source_references: list[dict[str, Any]]
    module_payload: dict[str, Any] | None

    answer_text: str | None
    final_response: str | None

    handoff_required: bool
    human_handoff: bool
    handoff_ticket_id: int | None
    handoff_ticket_no: str | None

    risk_triggered: bool
    risk_reasons: list[str]

    user_message_id: int | None
    assistant_message_id: int | None

    warnings: list[str]
    errors: list[str]

    metadata: dict[str, Any]
```

## 5. 字段分组说明

### 5.1 会话字段

```text
session_id
conversation_id
channel
user_id
conversation_history
user_message_id
assistant_message_id
```

来源：

```text
ConversationService
ConversationRepository
POST /api/v1/agent/query request
```

用途：

```text
ContextNode 加载上下文
最终响应返回 session_id
记录 user / assistant message
外部渠道追踪
```

### 5.2 用户输入字段

```text
user_text
normalized_text
```

说明：

```text
user_text 保存用户原始输入
normalized_text 保存标准化后的文本
```

标准化示例：

```text
全角转半角
SKU 小写转大写
× / Ｘ / * 统一
多余空格清理
```

### 5.3 意图路由字段

```text
intent
selected_module
candidate_modules
matched_signals
matched_sku
route_status
route_confidence
```

来源：

```text
UnifiedIntentRouter
未来 LLM IntentNode
未来规则兜底 Router
```

典型值：

```text
selected_module = spec
selected_module = price
selected_module = logistics
selected_module = quality
route_status = routed
route_status = ambiguous
route_status = unknown
route_status = invalid_request
```

### 5.4 业务处理字段

```text
parse_status
handler_status
module_payload
source_references
answer_text
```

来源：

```text
SpecTextQAService
PriceTextQAService
LogisticsTextQAService
QualityTextQAService
UnifiedTextQAService
```

说明：

```text
module_payload 保存业务模块原始响应
source_references 保存事实来源
answer_text 保存当前模块生成的受控回答
```

### 5.5 RAG 字段

```text
retrieved_chunks
```

来源：

```text
未来 RAG Retriever
Qdrant
BM25
RRF Fusion
Top-K chunk selector
```

每个 chunk 建议结构：

```json
{
  "collection": "quality_kb",
  "chunk_id": "quality_kb_001",
  "title": "铝合金表面处理说明",
  "content": "……",
  "score": 0.82,
  "source_type": "rag_chunk",
  "source_name": "quality_kb"
}
```

边界：

```text
RAG 可以提供补充说明依据
RAG 不能单独形成价格、物流、质量、售后承诺
```

### 5.6 人工接管字段

```text
handoff_required
human_handoff
handoff_ticket_id
handoff_ticket_no
```

来源：

```text
UnifiedTextQAService
HandoffTicketService
RiskCtrlNode
```

说明：

```text
handoff_required 表示当前回答需要人工确认
human_handoff 表示工作流最终决定转人工
handoff_ticket_id / handoff_ticket_no 关联 handoff_tickets 表
```

### 5.7 风控字段

```text
risk_triggered
risk_reasons
```

来源：

```text
RiskCtrlNode
规则检查器
未来 LLM 输出审查
```

典型原因：

```text
price_without_price_table
logistics_commitment_required
quality_commitment_required
forbidden_commitment_detected
missing_source_reference
llm_generated_unsupported_fact
rag_evidence_insufficient
ambiguous_business_intent
unknown_business_intent
```

### 5.8 输出字段

```text
final_response
warnings
errors
metadata
```

说明：

```text
final_response 是最终对外回答
warnings 保存非阻断异常
errors 保存阻断异常
metadata 保存调试信息
```

## 6. 节点写入边界

### 6.1 ContextNode

读取：

```text
session_id
channel
user_id
```

写入：

```text
conversation_id
conversation_history
```

禁止：

```text
不判断业务意图
不生成业务回答
不修改价格 / 物流 / 质量事实
```

### 6.2 IntentNode

读取：

```text
user_text
normalized_text
conversation_history
```

写入：

```text
intent
selected_module
candidate_modules
matched_signals
matched_sku
route_status
route_confidence
```

禁止：

```text
不生成最终回答
不创建 handoff ticket
不写入数据库
```

### 6.3 RouteNode

读取：

```text
selected_module
candidate_modules
route_status
```

写入：

```text
metadata
warnings
errors
```

职责：

```text
决定进入 spec / price / logistics / quality / handoff / unknown / ambiguous 分支
```

### 6.4 HandlerNode

读取：

```text
selected_module
user_text
matched_sku
```

写入：

```text
parse_status
handler_status
module_payload
source_references
answer_text
handoff_required
```

禁止：

```text
不绕过现有四个业务模块
不直接拼接无来源事实
不直接承诺价格、物流、质量、售后
```

### 6.5 RetrievalNode

读取：

```text
user_text
selected_module
matched_sku
conversation_history
```

写入：

```text
retrieved_chunks
source_references
```

禁止：

```text
不创建业务承诺
不替代结构化规则
不覆盖数据库事实
```

### 6.6 RiskCtrlNode

读取：

```text
answer_text
final_response
source_references
module_payload
retrieved_chunks
selected_module
handler_status
handoff_required
```

写入：

```text
risk_triggered
risk_reasons
human_handoff
handoff_required
final_response
```

职责：

```text
发现禁止承诺
发现缺少事实来源
发现 LLM 可能编造
发现价格 / 物流 / 质量 / 售后越界
必要时强制转人工
```

### 6.7 RenderNode

读取：

```text
answer_text
module_payload
source_references
retrieved_chunks
risk_reasons
handoff_required
handoff_ticket_no
```

写入：

```text
final_response
```

边界：

```text
只做表达层整理
不得新增事实
不得新增承诺
不得改写风险边界
```

## 7. 与当前 Unified Agent payload 的映射

当前 `POST /api/v1/agent/query` 响应字段可映射为：

```text
selected_module → AgentState.selected_module
route_status → AgentState.route_status
parse_status → AgentState.parse_status
handler_status → AgentState.handler_status
answer_text → AgentState.answer_text
handoff_required → AgentState.handoff_required
handoff_ticket_id → AgentState.handoff_ticket_id
handoff_ticket_no → AgentState.handoff_ticket_no
source_references → AgentState.source_references
module_payload → AgentState.module_payload
warnings → AgentState.warnings
errors → AgentState.errors
session_id → AgentState.session_id
conversation_id → AgentState.conversation_id
user_message_id → AgentState.user_message_id
assistant_message_id → AgentState.assistant_message_id
```

## 8. 与 ConversationService 的映射

ConversationService 提供：

```text
session_id
conversation_id
conversation_history
user_message_id
assistant_message_id
```

写入 AgentState：

```text
state["session_id"]
state["conversation_id"]
state["conversation_history"]
state["user_message_id"]
state["assistant_message_id"]
```

## 9. 与 HandoffTicketService 的映射

HandoffTicketService 提供：

```text
handoff_ticket_id
handoff_ticket_no
```

写入 AgentState：

```text
state["handoff_required"] = True
state["human_handoff"] = True
state["handoff_ticket_id"]
state["handoff_ticket_no"]
```

## 10. 与未来 LLMClient 的关系

LLM 可以读取：

```text
user_text
conversation_history
selected_module
retrieved_chunks
module_payload 中允许公开的字段
```

LLM 可以写入：

```text
intent 候选
自然语言改写
answer_text 表达优化
final_response 表达优化
warnings
```

LLM 不得写入：

```text
SKU 事实
价格事实
库存事实
物流承诺
质量承诺
售后承诺
handoff_ticket_id
database source reference
```

统一原则：

```text
LLM 不是事实来源。
LLM 不是承诺来源。
LLM 只参与理解、改写、分类、表达。
```

## 11. 与未来 RAG 的关系

RAG 可以写入：

```text
retrieved_chunks
source_references 中的 rag_chunk 引用
```

RAG 不得写入：

```text
价格承诺
物流承诺
质量承诺
售后承诺
人工处理结论
```

统一原则：

```text
RAG 是证据补充，不是业务承诺来源。
```

## 12. AgentState 初始化规则

### 12.1 最小输入

```python
state = {
    "session_id": request.session_id,
    "channel": request.source_channel,
    "user_id": request.user_id,
    "user_text": request.text,
    "conversation_history": [],
    "candidate_modules": [],
    "matched_signals": [],
    "retrieved_chunks": [],
    "source_references": [],
    "module_payload": None,
    "answer_text": None,
    "final_response": None,
    "handoff_required": False,
    "human_handoff": False,
    "handoff_ticket_id": None,
    "handoff_ticket_no": None,
    "risk_triggered": False,
    "risk_reasons": [],
    "warnings": [],
    "errors": [],
    "metadata": {},
}
```

### 12.2 默认安全值

默认必须是保守值：

```text
handoff_required = false
human_handoff = false
risk_triggered = false
source_references = []
retrieved_chunks = []
warnings = []
errors = []
```

如果出现不确定或越界：

```text
切换为 handoff_required = true
human_handoff = true
```

## 13. 最终输出规则

对外响应应从 AgentState 生成。

最小响应字段：

```json
{
  "session_id": "session-xxx",
  "conversation_id": 1,
  "selected_module": "price",
  "route_status": "routed",
  "parse_status": "parsed",
  "handler_status": "handoff",
  "answer_text": "……",
  "handoff_required": true,
  "handoff_ticket_id": 1,
  "handoff_ticket_no": "HT-20260611-A8F3K2Q9",
  "source_references": [],
  "module_payload": {},
  "warnings": [],
  "errors": []
}
```

## 14. 风控边界

AgentState 不得成为“绕过规则”的通道。

禁止：

```text
在 AgentState 中伪造 source_references
在 AgentState 中写入未确认价格
在 AgentState 中写入未确认包邮
在 AgentState 中写入保证到货
在 AgentState 中写入质量保证
在 AgentState 中写入质保承诺
在 AgentState 中写入退换承诺
在 AgentState 中写入赔付承诺
```

## 15. 测试范围

建议新增：

```text
backend/app/agent/state.py
backend/scripts/check_agent_state_contract.py
```

检查内容：

```text
AgentState 可初始化
默认字段安全
可从 Unified Agent payload 构造
可映射 conversation_history
可映射 handoff ticket
可输出 response payload
不会包含禁止承诺字段
```

## 16. 当前结论

AgentState 是 LangGraph Workflow 的核心契约。

Phase 3-C 的目标是：

```text
把当前分散的 Unified Agent / Conversation / Handoff / Risk / RAG / LLM 状态统一成一个可传递、可检查、可扩展的状态对象。
```

完成后，系统将具备进入 LangGraph Workflow Skeleton 的前置条件。