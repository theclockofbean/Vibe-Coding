# LangGraph Workflow Skeleton 设计文档 v0.1

## 1. 文档目的

本文档用于固定 Phase 3-D 中 LangGraph Workflow Skeleton 的设计目标、节点拓扑、状态流转、节点职责、边界控制、与现有系统的适配方式、测试范围和后续演进路径。

Phase 3-D 是 Agent 工程化的关键阶段。

本阶段目标不是简单把现有 `UnifiedTextQAService` 包一层，而是建立一个可扩展、可观测、可灰度迁移的 Agent Workflow 骨架，为后续 LLM Intent、RAG Retrieval、Risk Control、Human Handoff、Streaming、Checkpoint 打基础。

## 2. 当前系统基础

当前系统已经完成：

```text
Phase 1：spec / price / logistics / quality 四个业务模块
Phase 2：Unified Agent API 与 UnifiedTextQAService
Phase 3-A：Manual Handoff 工单自动创建与查询
Phase 3-B：Conversation / Session 上下文
Phase 3-C：AgentState 契约与 Unified Agent API 兼容性
```

当前已有核心能力：

```text
POST /api/v1/agent/query
GET /api/v1/agent/conversation
GET /api/v1/handoff/tickets
AgentState
ConversationService
HandoffTicketService
UnifiedIntentRouter
UnifiedTextQAService
四个垂直 TextQAService
```

Phase 3-D 将在这些基础上引入：

```text
LangGraph StateGraph
ContextNode
IntentNode
RouteNode
HandlerNode
RetrievalNode
RiskCtrlNode
RenderNode
Workflow Builder
Workflow Runner
Workflow 检查脚本
```

## 3. 设计原则

### 3.1 不破坏现有稳定入口

当前稳定入口：

```text
POST /api/v1/agent/query
```

Phase 3-D 不立即替换它。

v0.1 先新增内部 workflow 骨架：

```text
backend/app/agent/workflow.py
```

通过检查脚本验证：

```text
workflow.invoke(state)
```

后续再决定是否将 `/api/v1/agent/query` 内部切换到 workflow。

### 3.2 AgentState 是唯一状态载体

LangGraph 节点之间不得直接传递零散参数。

统一使用：

```text
AgentState
```

节点只能：

```text
读取 AgentState
返回 AgentState 局部更新
```

不得：

```text
直接绕过 AgentState 调用下游
私自构造 API response
私自创建业务承诺
私自写数据库事实
```

### 3.3 Skeleton 先规则化，LLM/RAG 后接入

Phase 3-D v0.1 不强制调用 LLM，不强制调用 RAG。

先使用现有确定性模块：

```text
UnifiedIntentRouter
UnifiedTextQAService
ConversationService
HandoffTicketService
AgentState risk control
```

后续 Phase 3-E / 3-F 再接入：

```text
RAG Retriever
LLMClient
LLM IntentNode
LLM RenderNode
```

### 3.4 业务事实仍来自结构化模块

Workflow 不得成为绕过业务规则的通道。

事实来源优先级：

```text
PostgreSQL structured data
业务规则表
现有四个业务模块
RAG verified chunks
人工确认
```

LLM 不得成为事实来源。

RAG 不得成为承诺来源。

## 4. Workflow 总体拓扑

Phase 3-D v0.1 建议拓扑：

```text
START
  ↓
ContextNode
  ↓
IntentNode
  ↓
RouteNode
  ↓
HandlerNode
  ↓
RetrievalNode
  ↓
RiskCtrlNode
  ↓
RenderNode
  ↓
END
```

v0.1 使用线性骨架，但 RouteNode 内部保留条件路由结果。

后续可升级为条件边：

```text
RouteNode
  ├── spec_handler
  ├── price_handler
  ├── logistics_handler
  ├── quality_handler
  ├── ambiguous_handler
  └── unknown_handler
```

再后续可升级为并行分支：

```text
HandlerNode
RetrievalNode
RiskCtrlNode
```

## 5. 节点职责设计

### 5.1 ContextNode

输入字段：

```text
session_id
channel
user_id
user_text
```

依赖：

```text
ConversationService
ConversationRepository
```

职责：

```text
创建或加载 conversation
加载 conversation_history
写入 conversation_id
写入 conversation_history
规范化 source_channel / user_id
```

写入 AgentState：

```text
session_id
conversation_id
conversation_history
channel
user_id
```

禁止：

```text
不判断业务意图
不生成业务回答
不创建 handoff ticket
不调用 LLM
不调用 RAG
```

### 5.2 IntentNode

输入字段：

```text
user_text
normalized_text
conversation_history
```

v0.1 依赖：

```text
UnifiedIntentRouter
```

未来依赖：

```text
LLMClient
Intent Classification Prompt
Rule-based fallback router
```

职责：

```text
识别 selected_module
识别 route_status
识别 candidate_modules
识别 matched_signals
识别 matched_sku
写入 route_confidence
```

写入 AgentState：

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
不创建工单
不写数据库
不承诺价格 / 物流 / 质量 / 售后
```

### 5.3 RouteNode

输入字段：

```text
selected_module
candidate_modules
route_status
```

职责：

```text
决定下一步业务路径
标记 ambiguous / unknown / invalid_request
写入 workflow route metadata
```

v0.1 不真正拆多节点 handler，而是写入：

```text
metadata["workflow_route"]
```

典型值：

```text
spec
price
logistics
quality
ambiguous
unknown
invalid_request
```

禁止：

```text
不调用业务模块
不生成回答
不修改 handler_status
```

### 5.4 HandlerNode

输入字段：

```text
user_text
selected_module
route_status
metadata["workflow_route"]
```

v0.1 依赖：

```text
UnifiedTextQAService
```

后续可替换为：

```text
SpecTextQAService
PriceTextQAService
LogisticsTextQAService
QualityTextQAService
```

职责：

```text
调用当前稳定业务处理链
写入 parse_status
写入 handler_status
写入 answer_text
写入 module_payload
写入 source_references
写入 handoff_required
```

写入 AgentState：

```text
parse_status
handler_status
answer_text
module_payload
source_references
handoff_required
warnings
errors
```

禁止：

```text
不绕过现有业务模块
不直接查库拼事实
不直接承诺价格
不直接承诺包邮
不直接承诺到货
不直接承诺质量
不直接承诺退换赔付
```

### 5.5 RetrievalNode

输入字段：

```text
user_text
selected_module
matched_sku
conversation_history
```

Phase 3-D v0.1：

```text
占位节点
默认 retrieved_chunks = []
不调用 Qdrant
不调用 BM25
```

Phase 3-E 后接入：

```text
bge-m3 embedding
Qdrant vector search
BM25 keyword search
RRF fusion
Top-3 chunk selector
```

写入 AgentState：

```text
retrieved_chunks
source_references
```

禁止：

```text
不生成最终回答
不替代结构化规则
不创建业务承诺
不覆盖 module_payload 中已有事实
```

### 5.6 RiskCtrlNode

输入字段：

```text
answer_text
final_response
selected_module
handler_status
handoff_required
source_references
module_payload
retrieved_chunks
```

依赖：

```text
AgentState.apply_risk_control()
forbidden commitment rules
```

职责：

```text
检查禁止承诺
检查缺少来源的高风险回答
检查 handoff_required 是否需要 human_handoff
检查 price / logistics / quality / aftersale 越界
必要时强制转人工
```

写入 AgentState：

```text
risk_triggered
risk_reasons
handoff_required
human_handoff
final_response
warnings
```

禁止：

```text
不降低风险等级
不删除已有风险原因
不把 handoff_required 从 true 改回 false
```

### 5.7 RenderNode

输入字段：

```text
answer_text
final_response
risk_triggered
handoff_required
handoff_ticket_no
warnings
errors
```

Phase 3-D v0.1：

```text
如果 final_response 为空，则使用 answer_text
如果 risk_triggered = true，则保留 RiskCtrlNode final_response
如果 handoff_required = true，则不新增承诺，只保留受控转人工表达
```

写入 AgentState：

```text
final_response
```

未来 Phase 3-F 可接入：

```text
LLM answer polishing
多语言表达
渠道适配表达
```

禁止：

```text
不新增事实
不新增价格
不新增物流承诺
不新增质量承诺
不新增售后承诺
```

## 6. Workflow 数据流

### 6.1 初始 State

由请求构造：

```python
state = create_initial_agent_state(
    session_id=request.session_id,
    channel=request.source_channel,
    user_id=request.user_id,
    user_text=request.text,
)
```

### 6.2 ContextNode 后

```text
session_id
conversation_id
conversation_history
```

### 6.3 IntentNode 后

```text
selected_module
route_status
candidate_modules
matched_signals
matched_sku
route_confidence
```

### 6.4 HandlerNode 后

```text
parse_status
handler_status
answer_text
module_payload
source_references
handoff_required
```

### 6.5 RetrievalNode 后

```text
retrieved_chunks
```

### 6.6 RiskCtrlNode 后

```text
risk_triggered
risk_reasons
human_handoff
final_response
```

### 6.7 RenderNode 后

```text
final_response
```

## 7. 与现有系统的适配方式

### 7.1 与 ConversationService

ContextNode 使用：

```text
ConversationService.get_or_create_conversation()
ConversationService.load_history()
```

后续 workflow 完成后，仍由外层 API 或 WorkflowRunner 写入：

```text
record_user_message()
record_agent_response()
```

v0.1 不在 ContextNode 中写 user / assistant message，避免 skeleton invoke 产生副作用。

### 7.2 与 UnifiedIntentRouter

IntentNode 使用：

```text
UnifiedIntentRouter.route()
```

将返回结果映射到 AgentState。

### 7.3 与 UnifiedTextQAService

HandlerNode v0.1 使用：

```text
UnifiedTextQAService.answer()
```

并通过：

```text
apply_unified_payload()
```

映射到 AgentState。

### 7.4 与 HandoffTicketService

Phase 3-D v0.1 Workflow Skeleton 不直接创建 handoff ticket。

原因：

```text
避免检查脚本重复创建工单
保持 workflow.invoke(state) 可无副作用执行
正式 API 仍由现有 agent.py 创建工单
```

后续正式替换 API 内部链路时，再将 HandoffTicketService 接入 workflow runner。

### 7.5 与 AgentState Risk Control

RiskCtrlNode 使用：

```text
apply_risk_control()
detect_forbidden_commitments()
```

## 8. Workflow Runner 设计

建议代码文件：

```text
backend/app/agent/workflow.py
```

建议公开函数：

```python
def build_agent_workflow(
    *,
    product_repository: ProductRepository,
    conversation_repository: ConversationRepository | None = None,
) -> CompiledStateGraph:
    ...
```

```python
def run_agent_workflow(
    *,
    initial_state: AgentState,
    product_repository: ProductRepository,
    conversation_repository: ConversationRepository | None = None,
) -> AgentState:
    ...
```

v0.1 可先实现：

```text
build_agent_workflow()
run_agent_workflow()
```

不接入 API。

## 9. Dependency 策略

Phase 3-D 需要确认：

```text
langgraph 是否安装
```

如果未安装：

```powershell
pip install langgraph
```

但正式安装前应先检查当前环境依赖清单。

检查命令：

```powershell
python -c "import langgraph; print(langgraph.__version__)"
```

如果 `langgraph.__version__` 不存在，则改用：

```powershell
python -c "import importlib.metadata as m; print(m.version('langgraph'))"
```

## 10. Checkpoint 策略

Phase 3-D v0.1：

```text
不启用正式 checkpointer
不启用 LangGraph persistent checkpoint
ConversationService 仍作为业务会话历史主存储
```

后续阶段可接入：

```text
MemorySaver
Postgres checkpointer
thread_id = session_id
```

设计原则：

```text
业务会话记录保存在 conversations / conversation_messages
LangGraph checkpoint 保存 workflow 执行中间状态
两者用途不同，不互相替代
```

## 11. Streaming 策略

Phase 3-D v0.1：

```text
不做 streaming API
只验证 workflow.invoke(state)
```

后续可支持：

```text
stream_mode = "updates"
stream_mode = "values"
```

用途：

```text
调试每个节点输出
前端展示 Agent 正在执行哪个阶段
后台观测 workflow 状态变化
```

## 12. 可观测性设计

Phase 3-D v0.1 通过 AgentState metadata 记录：

```text
workflow_started_at
workflow_finished_at
visited_nodes
workflow_route
node_errors
```

建议每个节点追加：

```text
metadata["visited_nodes"].append(node_name)
```

节点异常不直接吞掉。

非阻断异常写入：

```text
warnings
metadata["node_errors"]
```

阻断异常写入：

```text
errors
final_response
handoff_required = true
human_handoff = true
```

## 13. 灰度迁移策略

Phase 3-D 不替换现有入口。

建议迁移顺序：

```text
1. workflow.py 内部 skeleton 检查通过
2. 新增 check_langgraph_workflow_skeleton.py
3. 新增 check_agent_workflow_vs_unified_api.py 对比输出
4. 输出一致后，agent.py 增加 feature flag
5. FEATURE_AGENT_WORKFLOW=true 时走 workflow
6. 默认仍走现有 UnifiedTextQAService
7. 稳定后再默认切换 workflow
```

## 14. 测试范围

建议新增：

```text
backend/scripts/check_langgraph_installation.py
backend/scripts/check_langgraph_workflow_skeleton.py
backend/scripts/check_agent_workflow_vs_unified_api.py
backend/scripts/check_phase3d_total_regression.py
```

### 14.1 安装检查

验证：

```text
langgraph 可 import
StateGraph 可 import
START / END 可 import
```

### 14.2 Workflow Skeleton 检查

验证：

```text
workflow 可 build
workflow 可 invoke
ContextNode 被访问
IntentNode 被访问
RouteNode 被访问
HandlerNode 被访问
RetrievalNode 被访问
RiskCtrlNode 被访问
RenderNode 被访问
spec case 正常
price handoff case 正常
quality handoff case 正常
unknown case 正常
```

### 14.3 Workflow vs Unified API 检查

验证：

```text
同一输入下 workflow selected_module 与现有 API 一致
handler_status 一致
handoff_required 一致
answer_text 主要片段一致
禁止承诺片段不存在
```

## 15. 安全边界

LangGraph Workflow Skeleton 不得引入任何新业务承诺。

禁止：

```text
保证最低价
最低价给你
一定包邮
保证到货
今天一定发
保证不坏
保证不生锈
保证不掉漆
保证耐用
能用几年
一年质保
终身质保
七天无理由
一定能退
一定能换
一定赔
一定补发
质量很好
放心用
完全没问题
```

统一原则：

```text
Workflow 只组织节点，不创造事实。
Workflow 只传递状态，不放宽边界。
Workflow 只决定路径，不替代业务规则。
LLM 不是事实来源。
RAG 不是承诺来源。
```

## 16. Phase 3-D v0.1 交付目标

本阶段完成后，应具备：

```text
LangGraph 可运行骨架
AgentState 贯穿各节点
现有 UnifiedTextQAService 可被 HandlerNode 复用
ContextNode 可加载 conversation_history
RiskCtrlNode 可执行基础风控
RenderNode 可生成 final_response
workflow.invoke(state) 可检查
不破坏现有 API
不替换现有生产链路
```

## 17. 后续演进

Phase 3-D 完成后，后续建议：

```text
Phase 3-E：RAG Retriever 接入
Phase 3-F：LLMClient 接入
Phase 3-G：LangGraph API 灰度替换
Phase 3-H：Streaming 与 Checkpoint
Phase 4：外部渠道接入
```

## 18. 最终结论

Phase 3-D 是 Agent 工程化的关键转折点。

它不是简单新增一个函数，而是建立：

```text
状态驱动
节点解耦
条件路由
风险可控
输出可审计
旧链路可回退
新链路可扩展
```

的 Agent Workflow Skeleton。

该 skeleton 会成为后续 LLM、RAG、Streaming、Checkpoint、外部 IM 接入的核心执行框架。