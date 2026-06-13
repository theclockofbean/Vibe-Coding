# Conversation / Session 上下文设计文档 v0.1

## 1. 文档目的

本文档用于固定 Phase 3-B 中 Conversation / Session 上下文能力的设计边界、数据表结构、字段含义、写入规则、查询规则、与 Unified Agent API 的关系，以及后续 LangGraph ContextNode 的接入方式。

对应后续实现内容：

```text
PostgreSQL conversations 表
PostgreSQL conversation_messages 表
ConversationRepository
ConversationService
POST /api/v1/agent/conversation
Unified Agent API 写入 conversation_messages
LangGraph ContextNode 上下文加载基础
```

## 2. 背景

当前系统已经完成：

```text
Phase 1：spec / price / logistics / quality 四个垂直业务模块
Phase 2：POST /api/v1/agent/query 统一入口
Phase 3-A：Manual Handoff 工单自动创建与查询
```

当前系统已经可以：

```text
统一识别用户问题
路由到 spec / price / logistics / quality
返回统一响应结构
在 handoff_required = true 时自动创建 handoff_tickets
```

但当前仍缺少：

```text
会话主表
消息历史表
session_id 管理
conversation_history 查询
同一用户多轮上下文
外部渠道 user_id / channel 记录
LangGraph ContextNode 可加载的上下文数据
```

Phase 3-B 的目标是补齐 Conversation / Session 上下文基础设施。

## 3. 模块定位

Conversation / Session 模块是最终 LangGraph Agent 架构中的上下文层。

它位于：

```text
外部渠道 / 本地测试工具
→ HTTP API
→ ConversationService
→ conversations / conversation_messages
→ Unified Agent / LangGraph ContextNode
```

它负责：

```text
创建会话
保存用户消息
保存助手回答
保存统一 Agent 响应摘要
保存渠道和用户身份
按 session_id 加载历史消息
为 LangGraph ContextNode 提供 conversation_history
```

它不负责：

```text
不识别业务意图
不生成业务回答
不调用 LLM
不调用 RAG
不判断价格
不判断物流
不判断质量
不判断售后责任
不创建业务承诺
```

## 4. 核心概念

### 4.1 conversation

`conversation` 表示一次持续会话。

示例：

```text
同一个网页聊天窗口
同一个微信用户的一段咨询
同一个阿里巴巴 IM 买家咨询
同一个本地测试 session
```

### 4.2 session_id

`session_id` 是外部或内部传入的会话标识。

要求：

```text
同一轮多次对话应使用同一个 session_id
如果请求未提供 session_id，系统可自动生成
session_id 后续会传入 AgentState
```

### 4.3 conversation_message

`conversation_message` 表示会话中的一条消息。

消息角色：

```text
user
assistant
system
tool
```

v0.1 主要使用：

```text
user
assistant
```

### 4.4 channel

来源渠道。

建议允许：

```text
local_test
web
wechat
enterprise_wechat
alibaba_im
taobao
```

v0.1 默认：

```text
local_test
```

## 5. 数据表设计

### 5.1 conversations 表

建议新增：

```sql
CREATE TABLE IF NOT EXISTS conversations (
    id BIGSERIAL PRIMARY KEY,

    session_id VARCHAR(128) NOT NULL UNIQUE,
    source_channel VARCHAR(64) NOT NULL DEFAULT 'local_test',
    user_id VARCHAR(128),

    status VARCHAR(32) NOT NULL DEFAULT 'active',

    title VARCHAR(255),
    last_user_text TEXT,
    last_assistant_text TEXT,

    message_count INTEGER NOT NULL DEFAULT 0,

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_message_at TIMESTAMPTZ
);
```

### 5.2 conversation_messages 表

建议新增：

```sql
CREATE TABLE IF NOT EXISTS conversation_messages (
    id BIGSERIAL PRIMARY KEY,

    conversation_id BIGINT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    session_id VARCHAR(128) NOT NULL,

    role VARCHAR(32) NOT NULL,
    content TEXT NOT NULL,

    source_channel VARCHAR(64) NOT NULL DEFAULT 'local_test',
    user_id VARCHAR(128),

    selected_module VARCHAR(64),
    route_status VARCHAR(64),
    parse_status VARCHAR(64),
    handler_status VARCHAR(64),
    handoff_required BOOLEAN NOT NULL DEFAULT FALSE,
    handoff_ticket_id BIGINT,
    handoff_ticket_no VARCHAR(64),

    source_references JSONB NOT NULL DEFAULT '[]'::jsonb,
    module_payload JSONB,
    agent_payload JSONB,

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

## 6. 约束设计

### 6.1 conversations.status

允许值：

```text
active
closed
archived
```

建议约束：

```sql
ALTER TABLE conversations
ADD CONSTRAINT chk_conversations_status
CHECK (status IN ('active', 'closed', 'archived'));
```

### 6.2 conversation_messages.role

允许值：

```text
user
assistant
system
tool
```

建议约束：

```sql
ALTER TABLE conversation_messages
ADD CONSTRAINT chk_conversation_messages_role
CHECK (role IN ('user', 'assistant', 'system', 'tool'));
```

## 7. 索引设计

### 7.1 conversations

```sql
CREATE INDEX IF NOT EXISTS idx_conversations_source_channel
ON conversations (source_channel);

CREATE INDEX IF NOT EXISTS idx_conversations_user_id
ON conversations (user_id);

CREATE INDEX IF NOT EXISTS idx_conversations_status
ON conversations (status);

CREATE INDEX IF NOT EXISTS idx_conversations_updated_at
ON conversations (updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_conversations_last_message_at
ON conversations (last_message_at DESC);
```

### 7.2 conversation_messages

```sql
CREATE INDEX IF NOT EXISTS idx_conversation_messages_conversation_id
ON conversation_messages (conversation_id);

CREATE INDEX IF NOT EXISTS idx_conversation_messages_session_id
ON conversation_messages (session_id);

CREATE INDEX IF NOT EXISTS idx_conversation_messages_created_at
ON conversation_messages (created_at);

CREATE INDEX IF NOT EXISTS idx_conversation_messages_role
ON conversation_messages (role);

CREATE INDEX IF NOT EXISTS idx_conversation_messages_selected_module
ON conversation_messages (selected_module);

CREATE INDEX IF NOT EXISTS idx_conversation_messages_handoff_required
ON conversation_messages (handoff_required);
```

## 8. 字段说明

### 8.1 conversations.session_id

会话唯一标识。

示例：

```text
session-local-20260611-001
wechat-user-openid-xxx
alibaba-buyer-xxx
```

### 8.2 conversations.source_channel

来源渠道。

示例：

```text
local_test
web
wechat
enterprise_wechat
alibaba_im
taobao
```

### 8.3 conversations.user_id

外部用户标识。

v0.1 可为空。

后续外部渠道接入后，可存：

```text
微信 openid
企业微信 user_id
淘宝 buyer_id
阿里巴巴买家 id
```

### 8.4 conversations.status

会话状态。

```text
active：活跃
closed：已结束
archived：归档
```

v0.1 默认：

```text
active
```

### 8.5 conversations.last_user_text

最近一条用户消息。

用于列表展示和调试。

### 8.6 conversations.last_assistant_text

最近一条助手回答。

用于列表展示和调试。

### 8.7 conversations.message_count

消息数量。

每写入一条 conversation_messages，应同步递增。

### 8.8 conversation_messages.role

消息角色。

v0.1 使用：

```text
user
assistant
```

### 8.9 conversation_messages.content

消息正文。

对于 user：

```text
用户原始问题
```

对于 assistant：

```text
最终 answer_text
```

### 8.10 selected_module / route_status / parse_status / handler_status

记录 Agent 处理结果摘要。

assistant 消息应保存这些字段。

user 消息可为空。

### 8.11 handoff_required / handoff_ticket_id / handoff_ticket_no

用于关联 Manual Handoff 工单。

当助手回答触发工单时，应写入：

```text
handoff_required = true
handoff_ticket_id = 对应 handoff_tickets.id
handoff_ticket_no = 对应 handoff_tickets.ticket_no
```

### 8.12 source_references

保存事实来源引用。

### 8.13 module_payload

保存子模块原始响应。

### 8.14 agent_payload

保存统一 Agent API 响应完整 payload。

用途：

```text
调试
审计
后续 LangGraph 迁移
外部渠道问题追踪
```

## 9. ConversationRepository 设计

建议文件：

```text
backend/app/repositories/conversation_repository.py
```

核心数据对象：

```python
@dataclass(frozen=True)
class ConversationCreate:
    session_id: str
    source_channel: str = "local_test"
    user_id: str | None = None
    metadata: dict[str, object] | None = None
```

```python
@dataclass(frozen=True)
class ConversationMessageCreate:
    conversation_id: int
    session_id: str
    role: str
    content: str
    source_channel: str = "local_test"
    user_id: str | None = None
    selected_module: str | None = None
    route_status: str | None = None
    parse_status: str | None = None
    handler_status: str | None = None
    handoff_required: bool = False
    handoff_ticket_id: int | None = None
    handoff_ticket_no: str | None = None
    source_references: list[dict[str, object]] | None = None
    module_payload: dict[str, object] | None = None
    agent_payload: dict[str, object] | None = None
    metadata: dict[str, object] | None = None
```

核心方法：

```python
class ConversationRepository:
    def get_by_session_id(self, session_id: str) -> Conversation | None:
        ...

    def get_or_create(
        self,
        *,
        session_id: str,
        source_channel: str = "local_test",
        user_id: str | None = None,
    ) -> Conversation:
        ...

    def add_message(
        self,
        message: ConversationMessageCreate,
    ) -> ConversationMessage:
        ...

    def list_messages(
        self,
        *,
        session_id: str,
        limit: int = 20,
    ) -> list[ConversationMessage]:
        ...

    def list_conversations(
        self,
        *,
        source_channel: str | None = None,
        user_id: str | None = None,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Conversation]:
        ...
```

Repository 职责：

```text
只负责 conversations / conversation_messages 数据读写
不调用 LLM
不调用 Agent
不生成回答
不判断业务意图
```

## 10. ConversationService 设计

建议文件：

```text
backend/app/agent/services/conversation_service.py
```

核心方法：

```python
class ConversationService:
    def get_or_create_conversation(
        self,
        *,
        session_id: str | None,
        source_channel: str = "local_test",
        user_id: str | None = None,
    ) -> Conversation:
        ...

    def record_user_message(
        self,
        *,
        conversation: Conversation,
        user_text: str,
        source_channel: str = "local_test",
        user_id: str | None = None,
    ) -> ConversationMessage:
        ...

    def record_agent_response(
        self,
        *,
        conversation: Conversation,
        answer_text: str,
        agent_payload: dict[str, object],
    ) -> ConversationMessage:
        ...

    def load_history(
        self,
        *,
        session_id: str,
        limit: int = 20,
    ) -> list[dict[str, object]]:
        ...
```

Service 职责：

```text
生成 session_id
创建或加载 conversation
记录用户消息
记录助手消息
将 agent_payload 摘要写入 assistant message
为 ContextNode 提供 conversation_history
```

Service 不负责：

```text
不生成业务回答
不判断是否转人工
不创建 handoff ticket
不调用 LLM
```

## 11. 与 Unified Agent API 的关系

当前：

```text
POST /api/v1/agent/query
→ 返回一次性回答
```

Phase 3-B 后：

```text
POST /api/v1/agent/query
→ 如果传入 session_id，则记录 conversation_messages
→ 如果未传入 session_id，可生成 session_id 并返回
```

建议响应增加：

```json
{
  "session_id": "session-xxx",
  "conversation_id": 1,
  "user_message_id": 10,
  "assistant_message_id": 11
}
```

注意：

```text
Conversation 写入是附加能力
不得改变 selected_module / route_status / parse_status / handler_status 原有含义
不得改变 handoff ticket 创建逻辑
不得改变 answer_text 安全边界
```

## 12. 新增 API 设计

### 12.1 查询会话消息

建议新增：

```text
GET /api/v1/agent/conversation
```

请求参数：

```text
session_id：必填
limit：默认 20，最大 100
```

响应：

```json
{
  "session_id": "session-local-test",
  "items": [
    {
      "id": 1,
      "role": "user",
      "content": "SKU001 多少钱",
      "created_at": "2026-06-11T00:00:00Z"
    },
    {
      "id": 2,
      "role": "assistant",
      "content": "这类问题涉及报价。当前系统尚未接入正式价格表，不能直接给出报价。请转人工确认。",
      "selected_module": "price",
      "handoff_required": true,
      "handoff_ticket_no": "HT-20260611-A8F3K2Q9",
      "created_at": "2026-06-11T00:00:01Z"
    }
  ],
  "limit": 20
}
```

### 12.2 查询会话列表

后续可新增：

```text
GET /api/v1/agent/conversations
```

v0.1 可暂不实现。

## 13. 与 LangGraph ContextNode 的关系

Conversation / Session 是 LangGraph 的前置基础。

未来 ContextNode 应从数据库加载：

```text
session_id
source_channel
user_id
conversation_history
last_user_text
last_assistant_text
recent selected_module
recent handoff tickets
```

注入 AgentState：

```python
state.session_id = conversation.session_id
state.channel = conversation.source_channel
state.user_id = conversation.user_id
state.conversation_history = conversation_history
```

当前 Phase 3-B 完成后，LangGraph 工作流可以直接复用该上下文能力。

## 14. 写入规则

### 14.1 正常问答

用户请求：

```text
SKU001 螺纹是多少
```

应写入两条消息：

```text
user：SKU001 螺纹是多少
assistant：查到 SKU001：...
```

assistant 消息保存：

```text
selected_module = spec
route_status = routed
parse_status = parsed
handler_status = success
handoff_required = false
```

### 14.2 转人工问答

用户请求：

```text
SKU001 多少钱
```

应写入两条消息：

```text
user：SKU001 多少钱
assistant：当前系统尚未接入正式价格表...
```

assistant 消息保存：

```text
selected_module = price
handler_status = handoff
handoff_required = true
handoff_ticket_id = 对应工单 id
handoff_ticket_no = 对应工单号
```

### 14.3 unknown

用户请求：

```text
你好
```

仍应写入两条消息：

```text
user：你好
assistant：当前未识别到可处理的业务问题...
```

assistant 消息保存：

```text
selected_module = null
route_status = unknown
handler_status = invalid_request
handoff_required = false
```

## 15. 测试范围

建议新增脚本：

```text
backend/scripts/create_conversation_tables.py
backend/scripts/check_conversation_schema.py
backend/scripts/check_conversation_repository.py
backend/scripts/check_conversation_service.py
backend/scripts/check_conversation_api.py
backend/scripts/check_unified_agent_conversation_integration.py
backend/scripts/check_phase3b_total_regression.py
```

### 15.1 Schema 检查

验证：

```text
conversations 表存在
conversation_messages 表存在
字段存在
索引存在
约束存在
updated_at trigger 存在
```

### 15.2 Repository 检查

验证：

```text
get_or_create conversation
add user message
add assistant message
list messages by session_id
list conversations
message_count 更新
last_user_text / last_assistant_text 更新
```

### 15.3 Service 检查

验证：

```text
未传 session_id 时可生成 session_id
传入 session_id 时可复用 conversation
可记录 user message
可记录 assistant message
可加载 history
```

### 15.4 API 检查

验证：

```text
GET /api/v1/agent/conversation?session_id=xxx 返回消息历史
limit 越界返回 422
不存在 session_id 返回空列表或 404
```

建议 v0.1 使用：

```text
不存在 session_id 返回空列表
```

### 15.5 Unified Agent 集成检查

验证：

```text
POST /api/v1/agent/query 传入 session_id
自动写入 user message
自动写入 assistant message
返回 conversation_id / user_message_id / assistant_message_id
GET /api/v1/agent/conversation 可查到两条消息
handoff_required = true 时 assistant message 关联 ticket_no
```

## 16. 风控边界

Conversation 模块只是保存消息历史。

它不得生成或修改业务结论。

禁止：

```text
为了上下文而改写价格
为了上下文而承诺物流
为了上下文而承诺质量
为了上下文而承诺质保
为了上下文而承诺退换
为了上下文而承诺赔付
```

统一原则：

```text
Conversation 是上下文存储，不是事实来源，不是承诺来源。
```

## 17. 当前结论

Conversation / Session 是目标 LangGraph Agent 架构中的 ContextNode 基础。

Phase 3-B 的核心目标是：

```text
把一次性问答升级为可追踪的多轮会话记录
```

完成后，系统将具备：

```text
session_id 管理
会话创建
用户消息记录
助手消息记录
历史消息查询
Agent 响应审计
LangGraph ContextNode 上下文数据基础
```