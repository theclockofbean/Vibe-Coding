# Phase 3-B Conversation / Session 最终归档文档 v0.1

## 1. 阶段结论

Phase 3-B 已完成 Conversation / Session 上下文能力闭环，并通过总回归检查。

当前系统已经支持：

```text
conversations 会话主表
conversation_messages 消息历史表
ConversationRepository
ConversationService
GET /api/v1/agent/conversation
POST /api/v1/agent/query 自动写入会话消息
session_id 自动生成与复用
assistant 消息关联 handoff_ticket_id / handoff_ticket_no
Phase 3-B 总回归检查
```

Phase 3-B 的完成，使系统从“一次性问答”升级为“可追踪、可审计、可加载上下文的多轮会话基础”。

## 2. 当前已完成能力

### 2.1 conversations 表

已新增 PostgreSQL 表：

```text
conversations
```

核心字段：

```text
id
session_id
source_channel
user_id
status
title
last_user_text
last_assistant_text
message_count
metadata
created_at
updated_at
last_message_at
```

已实现能力：

```text
session_id 唯一约束
会话状态约束
渠道 / 用户 / 状态 / 更新时间索引
updated_at 自动更新时间 trigger
last_user_text / last_assistant_text 自动维护
message_count 自动递增
```

### 2.2 conversation_messages 表

已新增 PostgreSQL 表：

```text
conversation_messages
```

核心字段：

```text
id
conversation_id
session_id
role
content
source_channel
user_id
selected_module
route_status
parse_status
handler_status
handoff_required
handoff_ticket_id
handoff_ticket_no
source_references
module_payload
agent_payload
metadata
created_at
```

已实现能力：

```text
user / assistant 消息记录
assistant 消息保存 Agent 处理摘要
assistant 消息保存 handoff 工单关联
assistant 消息保存 source_references
assistant 消息保存 module_payload
assistant 消息保存完整 agent_payload
按 session_id 加载历史消息
```

## 3. 已实现代码文件

### 3.1 数据表脚本

```text
backend/scripts/create_conversation_tables.py
backend/scripts/check_conversation_schema.py
```

### 3.2 Repository

```text
backend/app/repositories/conversation_repository.py
```

核心方法：

```text
get_by_session_id()
get_or_create()
add_message()
list_messages()
list_conversations()
count_conversations()
```

### 3.3 Service

```text
backend/app/agent/services/conversation_service.py
```

核心方法：

```text
get_or_create_conversation()
record_user_message()
record_agent_response()
load_history()
```

### 3.4 API

已更新：

```text
backend/app/api/v1/agent.py
```

新增接口：

```text
GET /api/v1/agent/conversation
```

已增强接口：

```text
POST /api/v1/agent/query
```

## 4. 当前 API 行为

### 4.1 POST /api/v1/agent/query

请求示例：

```json
{
  "text": "SKU001 多少钱",
  "limit": 5,
  "source_channel": "local_test",
  "session_id": "session-demo-001",
  "user_id": "user-demo-001"
}
```

当前响应会包含：

```json
{
  "session_id": "session-demo-001",
  "conversation_id": 1,
  "user_message_id": 10,
  "assistant_message_id": 11,
  "handoff_ticket_id": 20,
  "handoff_ticket_no": "HT-20260611-A8F3K2Q9"
}
```

当前处理流程：

```text
创建或复用 conversation
执行 UnifiedTextQAService
如 handoff_required = true，创建 handoff ticket
写入 user message
写入 assistant message
返回 session_id / conversation_id / message_id / ticket 信息
```

### 4.2 GET /api/v1/agent/conversation

请求示例：

```text
GET /api/v1/agent/conversation?session_id=session-demo-001&limit=20
```

响应示例：

```json
{
  "session_id": "session-demo-001",
  "conversation": {
    "id": 1,
    "session_id": "session-demo-001",
    "message_count": 2,
    "last_user_text": "SKU001 多少钱",
    "last_assistant_text": "当前系统尚未接入正式价格表，不能直接给出报价。请转人工确认。"
  },
  "items": [
    {
      "role": "user",
      "content": "SKU001 多少钱"
    },
    {
      "role": "assistant",
      "content": "当前系统尚未接入正式价格表，不能直接给出报价。请转人工确认。",
      "selected_module": "price",
      "handler_status": "handoff",
      "handoff_required": true,
      "handoff_ticket_no": "HT-20260611-A8F3K2Q9"
    }
  ],
  "limit": 20
}
```

## 5. 当前典型场景

### 5.1 正常规格问答

用户输入：

```text
SKU001 螺纹是多少
```

结果：

```text
selected_module = spec
handler_status = success
handoff_required = false
不创建 handoff ticket
写入 user message
写入 assistant message
```

### 5.2 价格转人工问答

用户输入：

```text
SKU001 多少钱
```

结果：

```text
selected_module = price
handler_status = handoff
handoff_required = true
创建 handoff ticket
写入 user message
写入 assistant message
assistant message 关联 handoff_ticket_id / handoff_ticket_no
```

### 5.3 质量转人工问答

用户输入：

```text
SKU001 会不会生锈
```

结果：

```text
selected_module = quality
handler_status = handoff
handoff_required = true
创建 handoff ticket
写入 user message
写入 assistant message
assistant message 关联 handoff_ticket_id / handoff_ticket_no
```

### 5.4 自动生成 session_id

当请求未传入 `session_id` 时：

```text
系统自动生成 session_id
创建 conversation
写入消息
响应中返回生成的 session_id
```

## 6. 已完成检查脚本

```text
backend/scripts/create_conversation_tables.py
backend/scripts/check_conversation_schema.py
backend/scripts/check_conversation_repository.py
backend/scripts/check_conversation_service.py
backend/scripts/check_conversation_api.py
backend/scripts/check_unified_agent_conversation_integration.py
backend/scripts/check_phase3b_total_regression.py
```

Phase 3-B 总回归覆盖：

```text
Phase 1 四模块 API 路由检查
UnifiedIntentRouter 检查
UnifiedTextQAService 检查
Manual Handoff schema / repository / service / API / integration 检查
Conversation schema 检查
ConversationRepository 检查
ConversationService 检查
Conversation API 检查
Unified Agent Conversation 集成检查
```

当前状态：

```text
phase3-b total regression passed
```

## 7. 推荐总检查命令

```powershell
Set-Location "D:\Projects\ai-knowledge-agent-platform\backend"
python scripts\check_phase3b_total_regression.py
```

预期：

```text
phase3-b total regression passed
```

## 8. 当前安全边界

Conversation / Session 模块只是上下文存储层。

它不得：

```text
不生成业务结论
不修改业务结论
不补充价格
不承诺物流
不承诺质量
不承诺质保
不承诺退换
不承诺赔付
不作为事实来源
不作为承诺来源
```

统一原则：

```text
Conversation 是上下文存储，不是事实来源，不是承诺来源。
```

## 9. 与 LangGraph Agent 架构的关系

Phase 3-B 是未来 LangGraph `ContextNode` 的基础。

后续 `ContextNode` 可以从数据库加载：

```text
session_id
source_channel
user_id
conversation_history
last_user_text
last_assistant_text
recent selected_module
recent handoff ticket 信息
```

并注入未来 `AgentState`：

```python
state.session_id = conversation.session_id
state.channel = conversation.source_channel
state.user_id = conversation.user_id
state.conversation_history = conversation_history
```

## 10. 当前限制

Phase 3-B v0.1 当前只实现：

```text
会话创建
消息写入
历史查询
统一入口写入会话
总回归检查
```

暂不支持：

```text
会话关闭
会话归档
会话列表 API
会话标题自动生成
多渠道身份绑定
客服后台页面
消息搜索
上下文压缩
长期记忆
LangGraph ContextNode 正式代码
```

## 11. 后续建议

下一步建议进入：

```text
Phase 3-C：AgentState 契约设计
```

推荐开发顺序：

```text
1. AgentState 契约设计文档
2. app/agent/state.py
3. AgentState 基础 dataclass / TypedDict
4. AgentState 与 Unified Agent payload 映射
5. AgentState 与 ConversationService 映射
6. AgentState 与 HandoffTicketService 映射
7. AgentState 检查脚本
```

原因：

```text
LangGraph 工作流需要统一状态对象
ContextNode 需要写入 conversation_history
IntentNode 需要写入 intent / selected_module / matched_signals
HandlerNode 需要写入 module_payload
RiskCtrlNode 需要写入 risk_triggered / risk_reasons / human_handoff
最终响应需要从 AgentState 统一渲染
```

## 12. 最终结论

Phase 3-B Conversation / Session 可以归档。

当前系统已经具备：

```text
统一入口问答
人工转接工单
会话主表
消息历史表
session_id 自动生成与复用
历史消息查询
Unified Agent 自动写入 user / assistant message
assistant message 关联 handoff ticket
Phase 3-B 总回归检查
```

这为下一阶段 AgentState 和 LangGraph Workflow 打好了上下文基础。