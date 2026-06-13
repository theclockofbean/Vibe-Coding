# Phase 3-C AgentState 最终归档文档 v0.1

## 1. 阶段结论

Phase 3-C 已完成 AgentState 契约能力，并通过总回归检查。

当前系统已经具备：

```text
AgentState 内部状态契约
AgentState 安全初始化
Conversation context 映射
Unified Agent payload 映射
RAG retrieved_chunks 占位映射
Handoff ticket 映射
Risk control 基础拦截
AgentState response payload 输出
Phase 3-C 总回归检查
```

Phase 3-C 的完成，使当前系统具备进入 LangGraph Workflow Skeleton 的前置条件。

## 2. 已实现代码文件

### 2.1 AgentState 契约

```text
backend/app/agent/state.py
```

已实现：

```text
AgentState TypedDict
create_initial_agent_state()
apply_conversation_context()
apply_unified_payload()
apply_retrieved_chunks()
apply_risk_control()
detect_forbidden_commitments()
state_to_response_payload()
```

### 2.2 AgentState 契约检查

```text
backend/scripts/check_agent_state_contract.py
```

覆盖：

```text
初始状态安全默认值
conversation_history 映射
Unified Agent payload 映射
handoff ticket 映射
retrieved_chunks 映射
风险承诺拦截
response payload 输出
```

### 2.3 Unified API 兼容性检查

```text
backend/scripts/check_agent_state_unified_api_compatibility.py
```

覆盖：

```text
POST /api/v1/agent/query 响应可映射为 AgentState
GET /api/v1/agent/conversation 历史消息可映射为 conversation_history
spec success 可映射
price handoff 可映射
quality handoff 可映射
handoff_ticket_id / handoff_ticket_no 可保留
AgentState 输出 payload 与现有 API 结构兼容
```

### 2.4 Phase 3-C 总回归

```text
backend/scripts/check_phase3c_total_regression.py
```

串联：

```text
check_phase3b_total_regression.py
check_agent_state_contract.py
check_agent_state_unified_api_compatibility.py
```

当前状态：

```text
phase3-c total regression passed
```

## 3. AgentState 当前字段能力

当前 AgentState 已覆盖以下状态域：

```text
会话状态
用户输入
上下文历史
意图路由
业务模块处理
RAG 检索占位
来源引用
人工接管
风险控制
消息记录
最终响应
warnings / errors
metadata
```

核心字段包括：

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

## 4. 当前映射关系

### 4.1 Conversation / Session → AgentState

```text
session_id → state["session_id"]
conversation_id → state["conversation_id"]
conversation_history → state["conversation_history"]
user_message_id → state["user_message_id"]
assistant_message_id → state["assistant_message_id"]
```

### 4.2 Unified Agent payload → AgentState

```text
selected_module → state["selected_module"]
route_status → state["route_status"]
route_confidence → state["route_confidence"]
parse_status → state["parse_status"]
handler_status → state["handler_status"]
answer_text → state["answer_text"]
handoff_required → state["handoff_required"]
handoff_ticket_id → state["handoff_ticket_id"]
handoff_ticket_no → state["handoff_ticket_no"]
source_references → state["source_references"]
module_payload → state["module_payload"]
warnings → state["warnings"]
errors → state["errors"]
```

### 4.3 Handoff Ticket → AgentState

```text
handoff_required = true
human_handoff = true
handoff_ticket_id
handoff_ticket_no
risk_reasons
```

### 4.4 RAG → AgentState

当前已预留：

```text
retrieved_chunks
source_references
```

后续 RAG 接入时，可将 Qdrant / BM25 / RRF 返回结果写入 `retrieved_chunks`。

## 5. 当前风险控制能力

当前已实现基础禁止承诺检测：

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

当命中禁止承诺时，AgentState 会被更新为：

```text
risk_triggered = true
handoff_required = true
human_handoff = true
risk_reasons 追加 forbidden_commitment_detected
final_response 替换为转人工提示
```

## 6. 当前安全边界

AgentState 是内部状态对象，不是事实来源，也不是承诺来源。

它不得用于：

```text
伪造 source_references
写入未确认价格
写入未确认包邮
写入保证到货
写入质量保证
写入质保承诺
写入退换承诺
写入赔付承诺
绕过已有业务模块
绕过 handoff 规则
绕过风险控制
```

统一原则：

```text
AgentState 只承载状态，不创造事实。
AgentState 只传递边界，不放宽边界。
AgentState 只组织工作流，不替代业务规则。
```

## 7. 与 LangGraph Workflow 的关系

Phase 3-C 是 LangGraph Workflow Skeleton 的直接前置阶段。

后续 LangGraph 节点可围绕 AgentState 工作：

```text
ContextNode → 写入 conversation_history
IntentNode → 写入 selected_module / route_status
RouteNode → 决定业务分支
HandlerNode → 写入 module_payload / answer_text
RetrievalNode → 写入 retrieved_chunks
RiskCtrlNode → 写入 risk_triggered / risk_reasons / human_handoff
RenderNode → 写入 final_response
```

LangGraph 不需要直接操作分散的 API payload、conversation message、handoff ticket，而是统一读写 AgentState。

## 8. 推荐总检查命令

```powershell
Set-Location "D:\Projects\ai-knowledge-agent-platform\backend"
python scripts\check_phase3c_total_regression.py
```

预期：

```text
phase3-c total regression passed
```

## 9. 当前限制

Phase 3-C v0.1 当前只实现状态契约与兼容检查。

暂不支持：

```text
正式 LangGraph StateGraph
ContextNode 真实节点代码
IntentNode 真实节点代码
RouteNode 真实节点代码
HandlerNode 真实节点代码
RiskCtrlNode 真实节点代码
RenderNode 真实节点代码
LLMClient 接入
RAG Retriever 接入
LangGraph streaming
LangGraph checkpoint
```

这些内容应在 Phase 3-D 之后逐步实现。

## 10. 后续建议

下一步建议进入：

```text
Phase 3-D：LangGraph Workflow Skeleton
```

推荐开发顺序：

```text
1. LangGraph Workflow Skeleton 设计文档
2. 检查 langgraph 是否已安装
3. app/agent/workflow.py
4. ContextNode 占位实现
5. IntentNode 占位实现
6. RouteNode 占位实现
7. HandlerNode 占位实现
8. RiskCtrlNode 占位实现
9. RenderNode 占位实现
10. workflow.invoke(state) 基础检查脚本
11. 不替换现有 /api/v1/agent/query，仅先并行验证
```

## 11. 最终结论

Phase 3-C AgentState 可以归档。

当前系统已经具备：

```text
四个垂直业务模块
统一 Agent API
Manual Handoff 工单
Conversation / Session 上下文
AgentState 内部状态契约
AgentState 与当前 API 兼容性
Phase 3-C 总回归检查
```

这为后续 LangGraph Workflow Skeleton 打好了状态基础。
