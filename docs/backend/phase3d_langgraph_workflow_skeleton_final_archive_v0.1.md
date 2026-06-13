# Phase 3-D LangGraph Workflow Skeleton 最终归档文档 v0.1

## 1. 阶段结论

Phase 3-D 已完成 LangGraph Workflow Skeleton 的工程化落地，并通过总回归检查。

当前系统已经具备：

```text
LangGraph StateGraph 可运行骨架
AgentState 贯穿完整节点链路
ContextNode / IntentNode / RouteNode / HandlerNode / RetrievalNode / RiskCtrlNode / RenderNode
workflow.invoke(state) 可执行
节点访问链路可观测
Workflow 输出与现有 Unified Agent API 关键字段一致
Workflow 当前不产生业务副作用
Phase 3-D 总回归检查
```

Phase 3-D 是 Agent 开发中的关键转折点：系统已经从“统一服务调用”升级为“状态驱动的 Agent Workflow 骨架”。

## 2. 环境依赖确认

当前已确认 LangGraph 版本：

```text
langgraph==1.2.4
```

已完成检查：

```text
langgraph package version 可读取
langgraph.graph.StateGraph 可 import
START / END 可 import
最小 StateGraph 可 compile
最小 workflow 可 invoke
```

检查脚本：

```text
backend/scripts/check_langgraph_installation.py
```

检查结果：

```text
langgraph installation check passed
```

## 3. 已实现代码文件

### 3.1 LangGraph Workflow Skeleton

```text
backend/app/agent/workflow.py
```

核心公开函数：

```text
build_agent_workflow()
run_agent_workflow()
```

核心节点类：

```text
AgentWorkflowNodes
```

节点方法：

```text
context_node()
intent_node()
route_node()
handler_node()
retrieval_node()
risk_control_node()
render_node()
```

### 3.2 Workflow Skeleton 检查

```text
backend/scripts/check_langgraph_workflow_skeleton.py
```

覆盖：

```text
workflow 可 build
workflow 可 invoke
context 节点被访问
intent 节点被访问
route 节点被访问
handler 节点被访问
retrieval 节点被访问
risk_control 节点被访问
render 节点被访问
spec success case 正常
price handoff case 正常
quality handoff case 正常
unknown case 正常
无禁止承诺片段
```

### 3.3 Workflow 与现有 API 一致性检查

```text
backend/scripts/check_agent_workflow_vs_unified_api.py
```

覆盖：

```text
同一输入下 workflow 与 POST /api/v1/agent/query 输出关键字段一致
selected_module 一致
route_status 一致
parse_status 一致
handler_status 一致
answer_text 一致
handoff_required 一致
source_references 一致
module_payload 一致
workflow 可加载现有 conversation_history
workflow 不重复写入 conversation_messages
workflow 不重复创建 handoff_tickets
workflow 当前无业务副作用
```

### 3.4 Phase 3-D 总回归

```text
backend/scripts/check_phase3d_total_regression.py
```

串联：

```text
check_phase3c_total_regression.py
check_langgraph_installation.py
check_langgraph_workflow_skeleton.py
check_agent_workflow_vs_unified_api.py
```

当前状态：

```text
phase3-d total regression passed
```

## 4. Workflow 当前拓扑

当前 Phase 3-D v0.1 使用线性可观测骨架：

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

当前设计重点不是复杂分支，而是先保证：

```text
状态可传递
节点可观测
输出可回归
旧链路可对齐
后续可灰度替换
```

后续可以升级为条件边：

```text
RouteNode
  ├── SpecHandlerNode
  ├── PriceHandlerNode
  ├── LogisticsHandlerNode
  ├── QualityHandlerNode
  ├── AmbiguousNode
  └── UnknownNode
```

## 5. AgentState 贯穿链路

Workflow 全程使用：

```text
AgentState
```

而不是在节点之间传递零散参数。

当前 AgentState 在 workflow 中承载：

```text
session_id
conversation_id
channel
user_id
user_text
normalized_text
conversation_history
intent
selected_module
candidate_modules
matched_signals
matched_sku
route_status
route_confidence
parse_status
handler_status
retrieved_chunks
source_references
module_payload
answer_text
final_response
handoff_required
human_handoff
handoff_ticket_id
handoff_ticket_no
risk_triggered
risk_reasons
user_message_id
assistant_message_id
warnings
errors
metadata
```

## 6. 节点职责归档

### 6.1 ContextNode

当前能力：

```text
读取 session_id
加载 conversation
加载 conversation_history
写入 conversation_id
写入 conversation_history
```

当前限制：

```text
不写 user message
不写 assistant message
不创建 handoff ticket
不调用 LLM
不调用 RAG
```

设计目的：

```text
让 workflow 可以读取上下文，但 skeleton 检查阶段不产生副作用。
```

### 6.2 IntentNode

当前能力：

```text
执行 deterministic pre-route
识别 selected_module
识别 candidate_modules
识别 matched_signals
识别 matched_sku
写入 route_status
写入 route_confidence
```

当前实现仍是规则型预路由，主要用于 workflow 可观测。

后续可升级为：

```text
LLM Intent Classification
Rule-based fallback
多轮上下文意图继承
```

### 6.3 RouteNode

当前能力：

```text
根据 route_status / selected_module 写入 metadata["workflow_route"]
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

后续可升级为 LangGraph conditional edges。

### 6.4 HandlerNode

当前能力：

```text
调用 UnifiedTextQAService
复用现有稳定业务链路
写入 parse_status
写入 handler_status
写入 answer_text
写入 module_payload
写入 source_references
写入 handoff_required
```

设计意义：

```text
Workflow 不绕过已有业务模块，而是把稳定模块纳入 Agent 节点。
```

### 6.5 RetrievalNode

当前能力：

```text
占位 retrieved_chunks
写入 retrieval_mode = disabled_placeholder
写入 retrieved_chunk_count
```

当前不调用：

```text
Qdrant
BM25
Embedding
RRF
LLM
```

后续 Phase 3-E 接入 RAG Retriever。

### 6.6 RiskCtrlNode

当前能力：

```text
执行 apply_risk_control()
检测禁止承诺
保留 handoff_required = true
必要时设置 human_handoff = true
写入 risk_control_checked
```

设计意义：

```text
将风险控制从“回答后被动检查”升级为 workflow 标准节点。
```

### 6.7 RenderNode

当前能力：

```text
如果 final_response 为空，则使用 answer_text
如果仍为空，则转人工
写入 workflow_finished_at
写入 response_ready = true
```

当前限制：

```text
不新增事实
不新增承诺
不调用 LLM 改写
```

## 7. 可观测性能力

Workflow 当前通过 `metadata` 记录：

```text
workflow_started_at
workflow_finished_at
visited_nodes
workflow_route
handler_payload_keys
retrieval_mode
retrieved_chunk_count
risk_control_checked
response_ready
node_errors
```

标准访问链路：

```text
context
intent
route
handler
retrieval
risk_control
render
```

这使得每次 workflow 执行都可以回答：

```text
走过哪些节点
路由到了哪个业务方向
Handler 返回了哪些字段
是否执行了 retrieval
是否执行了 risk control
最终响应是否 ready
是否有节点异常
```

## 8. 与现有 Unified Agent API 的一致性

当前已验证同一输入下，workflow 与现有 API 在稳定业务字段上保持一致：

```text
selected_module
route_status
parse_status
handler_status
answer_text
handoff_required
source_references
module_payload
```

已覆盖案例：

```text
SKU001 螺纹是多少
SKU001 有现货吗，什么时候发货
SKU001 多少钱
SKU001 会不会生锈
你好，请问你是谁
```

这说明当前 workflow skeleton 可以作为后续替换 `/api/v1/agent/query` 内部链路的候选基础。

## 9. 无副作用验证

Phase 3-D 明确验证 workflow 当前不会产生额外业务副作用：

```text
不重复写入 conversation_messages
不重复创建 handoff_tickets
不改变现有 API 行为
```

当前策略：

```text
现有 API 负责写 conversation_messages
现有 API 负责创建 handoff_tickets
workflow skeleton 只读取上下文和生成状态
```

这保证了开发阶段可以安全并行验证 workflow，而不会污染业务数据。

## 10. 安全边界

LangGraph Workflow Skeleton 不得引入任何新业务承诺。

禁止输出或生成：

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

## 11. 当前技术价值

Phase 3-D 已经体现出以下 Agent 工程能力：

```text
StateGraph 工作流建模
AgentState 状态契约贯穿
节点职责解耦
旧服务适配进入节点体系
可观测 metadata
workflow 与旧 API 一致性验证
无副作用隔离
可灰度替换路径
风险控制节点化
RAG / LLM / Checkpoint / Streaming 扩展位预留
```

这已经不是简单 CRUD 或普通接口封装，而是具备可演进 Agent 平台特征的工作流架构。

## 12. 当前限制

Phase 3-D v0.1 当前仍不支持：

```text
正式替换 POST /api/v1/agent/query
LangGraph conditional edges
LangGraph checkpoint
LangGraph streaming
RAG Retriever
LLMClient
LLM IntentNode
LLM RenderNode
外部 IM 渠道接入
客服后台操作工作流
```

这些内容应在后续阶段逐步实现。

## 13. 后续建议

下一阶段建议进入：

```text
Phase 3-E：RAG Retriever 接入
```

推荐开发顺序：

```text
1. RAG Retriever 设计文档
2. 确认 Qdrant collection 策略
3. 建立 knowledge_chunks 数据结构
4. 实现 deterministic retriever interface
5. 实现 QdrantRetriever
6. 实现 HybridRetriever 占位
7. 将 RetrievalNode 从 placeholder 改为真实 RAG retrieval
8. 新增 RAG 检查脚本
9. 新增 workflow + RAG 集成检查
10. 保持 RAG 不作为业务承诺来源
```

Phase 3-E 之后，再进入：

```text
Phase 3-F：LLMClient 接入
Phase 3-G：Workflow API 灰度替换
Phase 3-H：Streaming / Checkpoint
```

## 14. 推荐总检查命令

```powershell
Set-Location "D:\Projects\ai-knowledge-agent-platform\backend"
python scripts\check_phase3d_total_regression.py
```

预期：

```text
phase3-d total regression passed
```

## 15. 最终结论

Phase 3-D LangGraph Workflow Skeleton 可以归档。

当前系统已经完成从：

```text
垂直业务模块
→ 统一 Agent API
→ 人工转接工单
→ 会话上下文
→ AgentState
→ LangGraph Workflow Skeleton
```

的阶段性升级。

这为后续 RAG、LLM、Streaming、Checkpoint、外部渠道接入打好了核心执行框架。