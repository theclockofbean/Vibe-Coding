# Phase 3-A Manual Handoff 最终归档文档 v0.1

## 1. 阶段结论

Phase 3-A 已完成 Manual Handoff 工单能力闭环，并通过总回归检查。

当前系统已经支持：

```text
handoff_required = true 自动创建人工转接工单
GET /api/v1/handoff/tickets 查询人工转接工单
Repository 层创建 / 查询 / 统计工单
Service 层从 Unified Agent 结果生成工单
Unified Agent API 自动附加工单编号
Phase 3-A 总回归检查
```

当前阶段不改变 Phase 1 / Phase 2 已有能力，而是在统一入口之上新增人工接管基础设施。

## 2. 当前已完成能力

### 2.1 handoff_tickets 数据表

已新增 PostgreSQL 表：

```text
handoff_tickets
```

核心字段：

```text
id
ticket_no
status
priority
source_channel
session_id
user_id
user_text
selected_module
route_status
route_confidence
candidate_modules
matched_signals
parse_status
handler_status
handoff_reason
answer_text
source_references
module_payload
risk_reasons
assigned_to
resolution_note
created_at
updated_at
resolved_at
```

已实现：

```text
状态约束
优先级约束
常用查询索引
updated_at 自动更新时间触发器
```

### 2.2 HandoffTicketRepository

已实现文件：

```text
backend/app/repositories/handoff_ticket_repository.py
```

已支持：

```text
create()
list_tickets()
count_tickets()
```

Repository 职责：

```text
只负责 handoff_tickets 表读写
不判断业务承诺
不调用 LLM
不生成客服结论
不决定是否转人工
```

### 2.3 HandoffTicketService

已实现文件：

```text
backend/app/agent/services/handoff_ticket_service.py
```

已支持：

```text
create_from_unified_result()
```

能力：

```text
从 Unified Agent response payload 创建工单
生成 ticket_no
提取 selected_module / route_status / handler_status
生成 handoff_reason
保存 source_references
保存 module_payload
保存 risk_reasons
```

### 2.4 Handoff Ticket API

已实现文件：

```text
backend/app/api/v1/handoff.py
backend/app/api/v1/router.py
```

新增接口：

```text
GET /api/v1/handoff/tickets
```

支持参数：

```text
status
selected_module
limit
offset
```

响应结构：

```json
{
  "items": [],
  "total": 0,
  "limit": 20,
  "offset": 0,
  "filters": {
    "status": null,
    "selected_module": null
  }
}
```

### 2.5 Unified Agent 自动创建工单

已更新文件：

```text
backend/app/api/v1/agent.py
```

当前逻辑：

```text
POST /api/v1/agent/query
→ UnifiedTextQAService
→ result.to_response_payload()
→ 如果 handoff_required = true
→ HandoffTicketService.create_from_unified_result()
→ 响应中追加 handoff_ticket_id / handoff_ticket_no
```

新增响应字段：

```text
handoff_ticket_id
handoff_ticket_no
```

示例：

```json
{
  "selected_module": "price",
  "route_status": "routed",
  "handler_status": "handoff",
  "handoff_required": true,
  "handoff_ticket_id": 1,
  "handoff_ticket_no": "HT-20260611-A8F3K2Q9"
}
```

## 3. 当前触发工单的典型场景

### 3.1 Price

示例：

```text
SKU001 多少钱
```

行为：

```text
selected_module = price
handler_status = handoff
handoff_required = true
自动创建 handoff ticket
```

原因：

```text
当前系统未接入正式价格表，不能自动报价，需人工确认。
```

### 3.2 Logistics

示例：

```text
SKU001 运费多少
SKU001 能包邮吗
SKU001 几天能到
```

行为：

```text
selected_module = logistics
handler_status = handoff
handoff_required = true
自动创建 handoff ticket
```

原因：

```text
该物流问题涉及运费、包邮、到货时间、承运商或加急承诺，需人工确认。
```

### 3.3 Quality

示例：

```text
SKU001 会不会生锈
SKU001 这个材质耐用吗
SKU001 掉漆能退吗
```

行为：

```text
selected_module = quality
handler_status = handoff
handoff_required = true
自动创建 handoff ticket
```

原因：

```text
该质量问题涉及质量表现、售后责任、质保、退换或赔付，需人工确认。
```

### 3.4 Spec

示例：

```text
SKU001 螺纹是多少
```

行为：

```text
selected_module = spec
handler_status = success
handoff_required = false
不创建 handoff ticket
```

## 4. 已完成检查脚本

### 4.1 Schema

```text
backend/scripts/create_handoff_tickets_table.py
backend/scripts/check_handoff_ticket_schema.py
```

覆盖：

```text
表存在
字段存在
索引存在
约束存在
trigger 存在
```

### 4.2 Repository

```text
backend/scripts/check_handoff_ticket_repository.py
```

覆盖：

```text
创建工单
按 status 查询
按 selected_module 查询
分页查询
统计 total
JSONB 字段序列化 / 反序列化
```

### 4.3 Service

```text
backend/scripts/check_handoff_ticket_service.py
```

覆盖：

```text
price handoff 创建工单
quality handoff 创建工单
logistics handoff 创建工单
非 handoff 不创建工单
handoff_reason 正确
risk_reasons 正确
source_references 正确
```

### 4.4 API

```text
backend/scripts/check_handoff_ticket_api.py
```

覆盖：

```text
GET /api/v1/handoff/tickets 路由注册
默认查询
status 过滤
selected_module 过滤
limit / offset 分页
limit / offset 边界校验
```

### 4.5 Unified Agent 集成

```text
backend/scripts/check_unified_agent_handoff_integration.py
```

覆盖：

```text
POST /api/v1/agent/query price handoff 自动创建工单
POST /api/v1/agent/query quality handoff 自动创建工单
POST /api/v1/agent/query logistics handoff 自动创建工单
spec success 不创建工单
通过 GET /api/v1/handoff/tickets 可查到创建的工单
```

### 4.6 Phase 3-A 总回归

```text
backend/scripts/check_phase3a_total_regression.py
```

覆盖：

```text
Phase 1 四模块 API 路由检查
UnifiedIntentRouter 检查
UnifiedTextQAService 检查
handoff_tickets schema 检查
HandoffTicketRepository 检查
HandoffTicketService 检查
Handoff Ticket API 检查
Unified Agent Handoff 集成检查
```

当前状态：

```text
phase3-a total regression passed
```

## 5. 推荐总检查命令

进入 backend：

```powershell
Set-Location "D:\Projects\ai-knowledge-agent-platform\backend"
```

执行：

```powershell
python scripts\check_phase3a_total_regression.py
```

预期：

```text
phase3-a total regression passed
```

## 6. 当前安全边界

Manual Handoff 工单模块只是记录“需要人工确认”。

它不是人工确认本身。

它不得生成或暗示以下承诺：

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
工单只记录待处理问题，不代表业务结论。
```

## 7. 当前限制

Phase 3-A v0.1 当前只实现：

```text
工单创建
工单查询
总回归检查
```

暂不支持：

```text
工单分配
工单状态更新
人工处理结论写入
关闭工单
取消工单
客服后台页面
工单通知
工单权限控制
工单 SLA
```

## 8. 与最终 LangGraph Agent 架构的关系

Manual Handoff 是目标 LangGraph Agent 架构中的人工接管基础设施。

后续 LangGraph 工作流中的 `RiskCtrlNode` 可以在以下场景触发 handoff：

```text
价格缺少正式规则
物流承诺缺少规则
质量表现缺少规则
售后责任缺少规则
LLM 与规则判断冲突
RAG 检索依据不足
用户问题包含多业务意图
风控命中禁止承诺
```

当前 Phase 3-A 已经完成人工接管的数据基础。

## 9. 后续建议

下一步建议进入：

```text
Phase 3-B：Conversation / Session 上下文
```

推荐开发顺序：

```text
1. Conversation / Session 设计文档
2. conversations 表
3. conversation_messages 表
4. ConversationRepository
5. ConversationService
6. POST /api/v1/agent/conversation
7. Unified Agent 写入 conversation_messages
8. Conversation 总回归检查
```

原因：

```text
LangGraph ContextNode 需要 session_id 和 conversation_history
外部渠道接入需要 user_id / channel / session_id
多轮 Agent 必须先有会话存储
```

## 10. 最终结论

Phase 3-A Manual Handoff 可以归档。

当前系统已经具备：

```text
统一入口自动识别转人工
人工转接工单自动落库
人工转接工单查询接口
工单与 Unified Agent 响应关联
工单保留模块响应和来源引用
Phase 3-A 总回归检查
```

这使系统从“只会返回 handoff_required”升级为“可追踪、可查询、可审计的人工接管机制”。

下一阶段应建设 Conversation / Session 上下文，为 LangGraph ContextNode 打基础。