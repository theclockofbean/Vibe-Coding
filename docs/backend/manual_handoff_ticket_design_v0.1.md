# Manual Handoff Ticket 设计文档 v0.1

## 1. 文档目的

本文档用于固定 Phase 3-A 中人工转接工单系统的设计边界、数据表结构、字段含义、创建规则、查询规则、状态流转和测试范围。

对应后续实现内容：

```text
PostgreSQL handoff_tickets 表
HandoffTicketRepository
HandoffTicketService
GET /api/v1/handoff/tickets
Unified Agent API 自动落库逻辑
```

## 2. 背景

当前系统已经完成：

```text
Phase 1：spec / price / logistics / quality 四个垂直业务模块
Phase 2：POST /api/v1/agent/query 统一入口
Phase 2：UnifiedIntentRouter
Phase 2：UnifiedTextQAService
Phase 2：总回归检查
```

当前已有多个场景会返回：

```text
handoff_required = true
```

典型场景：

```text
SKU001 多少钱
SKU001 会不会生锈
SKU001 这个材质耐用吗
SKU001 掉漆能退吗
SKU001 运费多少
SKU001 能不能包邮
SKU001 几天能到
```

当前问题：

```text
这些转人工请求只存在于 API 响应中
没有落库
没有 ticket_id
没有处理状态
没有人工处理记录
无法查询
无法追踪
无法统计
```

Phase 3-A 的目标是补齐人工转接工单能力。

## 3. 模块定位

Manual Handoff Ticket 模块是统一 Agent 系统的人工接管层。

它位于：

```text
Unified Agent API
→ UnifiedTextQAService
→ handoff_required = true
→ HandoffTicketService
→ handoff_tickets 表
```

它负责：

```text
创建人工转接工单
保存原始用户问题
保存路由结果
保存模块响应
保存转人工原因
保存来源引用
保存状态
提供工单查询接口
为后续人工客服处理提供数据基础
```

它不负责：

```text
不自动报价
不自动承诺物流
不自动承诺质量
不自动承诺质保
不自动承诺退换
不自动承诺赔付
不替代人工判断
不调用 LLM 生成最终业务结论
```

## 4. 触发条件

当统一入口返回以下条件时，应创建工单：

```text
handoff_required = true
```

主要来源模块：

```text
price
logistics
quality
```

spec 模块通常不产生工单，但保留兼容能力。

### 4.1 Price 触发

示例：

```text
SKU001 多少钱
SKU001 批发价多少
SKU001 能不能便宜
SKU001 含税吗
SKU001 付款方式是什么
```

原因：

```text
当前系统未接入正式价格表
价格、折扣、含税、付款条件必须人工确认
```

### 4.2 Logistics 触发

示例：

```text
SKU001 运费多少
SKU001 能包邮吗
SKU001 几天能到
SKU001 发什么快递
SKU001 能不能加急
```

原因：

```text
运费、包邮、到货时间、承运商、加急均不能自动承诺
```

### 4.3 Quality 触发

示例：

```text
SKU001 会不会生锈
SKU001 这个材质耐用吗
SKU001 掉漆能退吗
SKU001 坏了能赔吗
SKU001 有划痕能补发吗
```

原因：

```text
质量表现、耐用、防锈、掉漆、质保、退换、赔付均需要人工确认或正式规则表支持
```

## 5. 数据表设计

建议新增表：

```text
handoff_tickets
```

### 5.1 字段设计

```sql
CREATE TABLE IF NOT EXISTS handoff_tickets (
    id BIGSERIAL PRIMARY KEY,

    ticket_no VARCHAR(64) NOT NULL UNIQUE,

    status VARCHAR(32) NOT NULL DEFAULT 'open',
    priority VARCHAR(32) NOT NULL DEFAULT 'normal',

    source_channel VARCHAR(64),
    session_id VARCHAR(128),
    user_id VARCHAR(128),

    user_text TEXT NOT NULL,

    selected_module VARCHAR(64),
    route_status VARCHAR(64),
    route_confidence NUMERIC(5, 4),
    candidate_modules JSONB NOT NULL DEFAULT '[]'::jsonb,
    matched_signals JSONB NOT NULL DEFAULT '[]'::jsonb,

    parse_status VARCHAR(64),
    handler_status VARCHAR(64),

    handoff_reason TEXT NOT NULL,
    answer_text TEXT,

    source_references JSONB NOT NULL DEFAULT '[]'::jsonb,
    module_payload JSONB,
    risk_reasons JSONB NOT NULL DEFAULT '[]'::jsonb,

    assigned_to VARCHAR(128),
    resolution_note TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);
```

### 5.2 索引设计

```sql
CREATE INDEX IF NOT EXISTS idx_handoff_tickets_status
ON handoff_tickets (status);

CREATE INDEX IF NOT EXISTS idx_handoff_tickets_selected_module
ON handoff_tickets (selected_module);

CREATE INDEX IF NOT EXISTS idx_handoff_tickets_created_at
ON handoff_tickets (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_handoff_tickets_session_id
ON handoff_tickets (session_id);

CREATE INDEX IF NOT EXISTS idx_handoff_tickets_user_id
ON handoff_tickets (user_id);
```

## 6. 字段说明

### 6.1 id

数据库自增主键。

### 6.2 ticket_no

业务工单号。

格式建议：

```text
HT-{YYYYMMDD}-{8位随机码}
```

示例：

```text
HT-20260611-A8F3K2Q9
```

### 6.3 status

工单状态。

允许值：

```text
open
in_progress
resolved
closed
cancelled
```

状态含义：

```text
open：新建，等待处理
in_progress：人工处理中
resolved：已给出处理结论
closed：已关闭
cancelled：误触发或无需处理
```

### 6.4 priority

优先级。

允许值：

```text
low
normal
high
urgent
```

v0.1 默认：

```text
normal
```

后续可根据渠道、用户等级、风险类型升级。

### 6.5 source_channel

来源渠道。

允许值示例：

```text
local_test
web
wechat
enterprise_wechat
alibaba_im
taobao
```

v0.1 可默认：

```text
local_test
```

### 6.6 session_id / user_id

用于后续多轮会话和外部渠道接入。

v0.1 可以为空。

### 6.7 user_text

用户原始问题。

示例：

```text
SKU001 会不会生锈
```

### 6.8 selected_module

来源模块：

```text
spec
price
logistics
quality
unknown
ambiguous
```

### 6.9 route_status

UnifiedIntentRouter 状态：

```text
routed
ambiguous
unknown
invalid_request
```

### 6.10 route_confidence

路由置信度。

### 6.11 candidate_modules

候选模块列表。

示例：

```json
["price", "logistics", "quality"]
```

### 6.12 matched_signals

命中的意图信号。

示例：

```json
["多少钱", "几天发货", "质量"]
```

### 6.13 parse_status / handler_status

子模块解析与处理状态。

示例：

```text
parse_status = parsed
handler_status = handoff
```

### 6.14 handoff_reason

转人工原因。

示例：

```text
当前系统未接入正式价格表，不能自动报价。
当前系统不能自动承诺不生锈或绝对防锈。
当前系统不能自动承诺一定可退或一定可换。
```

### 6.15 answer_text

系统返回给用户的受控提示。

### 6.16 source_references

来源引用。

示例：

```json
[
  {
    "source_type": "database_table",
    "source_name": "products",
    "reference_id": "SKU001"
  }
]
```

### 6.17 module_payload

子模块原始响应，用于排查问题和后续人工处理。

### 6.18 risk_reasons

风控原因。

示例：

```json
[
  "price_without_price_table",
  "quality_commitment_required"
]
```

### 6.19 assigned_to

人工处理人。

v0.1 可为空。

### 6.20 resolution_note

人工处理结论。

v0.1 查询接口只读，暂不支持更新。

## 7. HandoffTicketRepository 设计

建议文件：

```text
backend/app/repositories/handoff_ticket_repository.py
```

核心方法：

```python
class HandoffTicketRepository:
    def create(self, ticket: HandoffTicketCreate) -> HandoffTicket:
        ...

    def list_tickets(
        self,
        *,
        status: str | None = None,
        selected_module: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[HandoffTicket]:
        ...

    def count_tickets(
        self,
        *,
        status: str | None = None,
        selected_module: str | None = None,
    ) -> int:
        ...
```

Repository 职责：

```text
只负责数据库读写
不生成客服话术
不判断是否需要转人工
不调用 LLM
不调用 Agent
```

## 8. HandoffTicketService 设计

建议文件：

```text
backend/app/agent/services/handoff_ticket_service.py
```

核心方法：

```python
class HandoffTicketService:
    def create_from_unified_result(
        self,
        *,
        user_text: str,
        unified_payload: dict[str, object],
        source_channel: str = "local_test",
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> HandoffTicketResult:
        ...
```

Service 职责：

```text
根据 Unified Agent 结果创建工单
生成 ticket_no
提取 handoff_reason
保存 module_payload
保存 source_references
保存 route 信息
```

Service 不负责：

```text
不判断价格
不判断物流承诺
不判断质量承诺
不生成最终人工结论
```

## 9. handoff_reason 提取规则

v0.1 可采用确定性规则。

### 9.1 price

```text
当前系统未接入正式价格表，不能自动报价，需人工确认。
```

### 9.2 logistics

```text
该物流问题涉及运费、包邮、到货时间、承运商或加急承诺，需人工确认。
```

### 9.3 quality

```text
该质量问题涉及质量表现、售后责任、质保、退换或赔付，需人工确认。
```

### 9.4 unknown

```text
当前问题无法自动识别为受支持业务问题，需人工确认。
```

### 9.5 ambiguous

```text
当前问题包含多个业务意图，需拆分或由人工确认。
```

### 9.6 fallback

```text
当前问题需要人工进一步确认。
```

## 10. API 设计

### 10.1 查询工单列表

新增：

```text
GET /api/v1/handoff/tickets
```

请求参数：

```text
status：可选
selected_module：可选
limit：默认 20，最大 100
offset：默认 0
```

示例：

```text
GET /api/v1/handoff/tickets?status=open&selected_module=quality&limit=20&offset=0
```

响应：

```json
{
  "items": [
    {
      "id": 1,
      "ticket_no": "HT-20260611-A8F3K2Q9",
      "status": "open",
      "priority": "normal",
      "source_channel": "local_test",
      "session_id": null,
      "user_id": null,
      "user_text": "SKU001 会不会生锈",
      "selected_module": "quality",
      "route_status": "routed",
      "handler_status": "handoff",
      "handoff_reason": "该质量问题涉及质量表现、售后责任、质保、退换或赔付，需人工确认。",
      "answer_text": "查到 SKU001：铝合金竞技换挡球头。当前系统不能自动承诺不生锈或绝对防锈；如需确认防锈表现，需要结合材质、表面处理、使用环境和维护方式。请转人工进一步确认。",
      "created_at": "2026-06-11T00:00:00Z",
      "updated_at": "2026-06-11T00:00:00Z",
      "resolved_at": null
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

### 10.2 自动创建工单

`POST /api/v1/agent/query` 在返回结果前，如果检测到：

```text
handoff_required = true
```

则自动创建工单，并在响应中增加：

```json
{
  "handoff_ticket_id": 1,
  "handoff_ticket_no": "HT-20260611-A8F3K2Q9"
}
```

如果落库失败：

```text
不得影响原本回答
应在 warnings 中追加 handoff ticket creation failed
应记录错误日志
```

v0.1 可先让错误显式暴露在脚本检查中，后续再接日志系统。

## 11. 状态流转

v0.1 只实现创建与查询。

初始状态：

```text
open
```

后续阶段支持：

```text
open → in_progress → resolved → closed
open → cancelled
```

v0.1 不实现更新接口。

后续可新增：

```text
PATCH /api/v1/handoff/tickets/{ticket_id}
POST /api/v1/handoff/tickets/{ticket_id}/resolve
POST /api/v1/handoff/tickets/{ticket_id}/close
```

## 12. 与 Unified Agent API 的关系

当前统一入口响应：

```json
{
  "handoff_required": true,
  "answer_text": "...",
  "module_payload": {}
}
```

Phase 3-A 后应变为：

```json
{
  "handoff_required": true,
  "handoff_ticket_id": 1,
  "handoff_ticket_no": "HT-20260611-A8F3K2Q9",
  "answer_text": "...",
  "module_payload": {}
}
```

注意：

```text
工单创建是附加能力
不得改变 selected_module / route_status / parse_status / handler_status 的原有含义
不得改变 answer_text 的受控边界
```

## 13. 测试范围

建议新增脚本：

```text
backend/scripts/check_handoff_ticket_schema.py
backend/scripts/check_handoff_ticket_repository.py
backend/scripts/check_handoff_ticket_service.py
backend/scripts/check_handoff_ticket_api.py
backend/scripts/check_unified_agent_handoff_integration.py
```

### 13.1 Schema 检查

验证：

```text
handoff_tickets 表存在
必要字段存在
必要索引存在
```

### 13.2 Repository 检查

验证：

```text
可创建工单
可按 status 查询
可按 selected_module 查询
可分页查询
可统计 total
```

### 13.3 Service 检查

验证：

```text
price handoff 可生成工单
quality handoff 可生成工单
logistics handoff 可生成工单
ticket_no 唯一
handoff_reason 正确
module_payload 正确保存
```

### 13.4 API 检查

验证：

```text
GET /api/v1/handoff/tickets 返回 200
支持 status 过滤
支持 selected_module 过滤
支持 limit / offset
limit 越界返回 422
```

### 13.5 Unified Agent 集成检查

验证：

```text
POST /api/v1/agent/query 输入 SKU001 多少钱
返回 handoff_required = true
返回 handoff_ticket_id
返回 handoff_ticket_no
GET /api/v1/handoff/tickets 可查到该工单
```

## 14. 风控边界

handoff ticket 模块不得引入任何新的业务承诺。

禁止：

```text
保证最低价
一定包邮
保证到货
今天一定发
保证不坏
保证不生锈
保证不掉漆
保证耐用
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

工单只是记录“需要人工确认”，不是人工确认本身。

## 15. 当前结论

Manual Handoff Ticket 是 LangGraph Agent 最终架构中的人工接管基础设施。

Phase 3-A 的核心目标是：

```text
把 handoff_required = true 的问题变成可追踪工单
```

完成后，系统将具备：

```text
自动识别转人工
自动创建工单
查询待处理工单
保留模块响应和来源引用
为后续人工处理、外部渠道接入和风控审计打基础
```
