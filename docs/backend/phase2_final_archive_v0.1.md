# Phase 2 最终归档文档 v0.1

## 1. 阶段结论

Phase 2 后端统一入口能力已完成并通过总回归检查。

当前系统已具备：

```text
Phase 1 四模块垂直问答能力
Phase 2 统一意图路由能力
Phase 2 统一调度服务能力
Phase 2 统一 HTTP API 入口
Phase 2 统一响应结构
Phase 2 边界场景检查
Phase 2 总回归检查
```

当前统一入口：

```text
POST /api/v1/agent/query
```

## 2. 已验证路由

当前后端已验证以下 API 路由可用：

```text
POST /api/v1/spec/query
POST /api/v1/price/query
POST /api/v1/logistics/query
POST /api/v1/quality/query
POST /api/v1/agent/query
```

其中：

```text
spec：产品规格与基础产品信息问答
price：价格意图识别与受控转人工
logistics：库存与发货周期问答
quality：质量、材质表现、售后类问题受控处理
agent：统一入口，负责路由到对应模块
```

## 3. 当前统一调用链路

```text
用户问题
→ POST /api/v1/agent/query
→ UnifiedTextQAService
→ UnifiedIntentRouter
→ SpecTextQAService / PriceTextQAService / LogisticsTextQAService / QualityTextQAService
→ UnifiedTextQAResult
→ API JSON Response
```

## 4. 已完成核心模块

### 4.1 UnifiedIntentRouter

文件：

```text
backend/app/agent/routers/unified_intent_router.py
backend/app/agent/routers/__init__.py
```

职责：

```text
识别用户问题属于 spec / price / logistics / quality 哪个模块
识别 ambiguous
识别 unknown
识别 invalid_request
输出 selected_module、route_status、confidence、matched_signals、candidate_modules
```

不负责：

```text
不回答问题
不查询数据库
不调用 LLM
不调用 Handler
不调用 Renderer
不生成业务承诺
```

### 4.2 UnifiedTextQAService

文件：

```text
backend/app/agent/services/unified_text_qa_service.py
backend/app/agent/services/__init__.py
```

职责：

```text
调用 UnifiedIntentRouter
根据 selected_module 调用对应 TextQAService
包装统一响应结构
处理 ambiguous / unknown / invalid_request
保留 module_payload
```

不负责：

```text
不直接查库绕过子模块
不调用 LLM
不跨模块拼接回答
不新增业务承诺
```

### 4.3 Unified Agent API

文件：

```text
backend/app/api/v1/agent.py
backend/app/api/v1/router.py
```

接口：

```text
POST /api/v1/agent/query
```

职责：

```text
接收 HTTP 请求
校验 text / limit
构建 ProductRepository
调用 UnifiedTextQAService
返回统一 JSON
```

不负责：

```text
不直接解析意图
不直接查询 products 表
不直接调用子模块 Handler
不直接调用子模块 Renderer
不生成额外 answer_text
不写数据库
```

## 5. 统一响应结构

统一入口响应包含：

```text
selected_module
route_status
route_confidence
candidate_modules
matched_signals
parse_status
handler_status
answer_text
handoff_required
source_references
module_payload
warnings
errors
```

示例：

```json
{
  "selected_module": "logistics",
  "route_status": "routed",
  "route_confidence": 0.75,
  "candidate_modules": ["logistics"],
  "matched_signals": ["几天发货"],
  "parse_status": "parsed",
  "handler_status": "success",
  "answer_text": "查到 SKU001：铝合金竞技换挡球头。当前备货状态为现货，发货周期约 2 天。该时间仅表示发货周期，不代表到货时间。",
  "handoff_required": false,
  "source_references": [],
  "module_payload": {},
  "warnings": [],
  "errors": []
}
```

## 6. 当前行为矩阵

| 用户问题                  | selected_module | 结果        |
| --------------------- | --------------- | --------- |
| SKU001 螺纹是多少          | spec            | 自动回答      |
| SKU001 什么材质           | spec            | 自动回答登记信息  |
| SKU001 多少钱            | price           | 受控转人工     |
| SKU001 几天发货           | logistics       | 自动回答发货周期  |
| SKU001 会不会生锈          | quality         | 受控转人工     |
| SKU001 这个材质耐用吗        | quality         | 受控转人工     |
| SKU001 掉漆能退吗          | quality         | 受控转人工     |
| SKU001 多少钱，几天发货，质量怎么样 | null            | ambiguous |
| 你好                    | null            | unknown   |
| 空白 text               | null            | HTTP 422  |

## 7. 已完成检查脚本

### 7.1 Phase 1 检查

```text
backend/scripts/check_phase1_api_routes.py
```

覆盖：

```text
/spec/query
/price/query
/logistics/query
/quality/query
```

### 7.2 Phase 2 单项检查

```text
backend/scripts/check_unified_intent_router.py
backend/scripts/check_unified_text_qa_service.py
backend/scripts/check_unified_agent_api.py
backend/scripts/check_unified_agent_api_boundaries.py
```

### 7.3 Phase 2 总回归检查

```text
backend/scripts/check_phase2_total_regression.py
```

覆盖：

```text
Phase 1 四模块 API 路由检查
UnifiedIntentRouter 检查
UnifiedTextQAService 检查
Unified Agent API 检查
Unified Agent API 边界检查
```

当前状态：

```text
phase2 total regression passed
```

## 8. 推荐总检查命令

进入 backend 目录：

```powershell
Set-Location "D:\Projects\ai-knowledge-agent-platform\backend"
```

执行总回归：

```powershell
python scripts\check_phase2_total_regression.py
```

预期：

```text
phase2 total regression passed
```

如需单项检查：

```powershell
python scripts\check_phase1_api_routes.py
python scripts\check_unified_intent_router.py
python scripts\check_unified_text_qa_service.py
python scripts\check_unified_agent_api.py
python scripts\check_unified_agent_api_boundaries.py
```

## 9. 当前安全边界

统一入口禁止输出或生成以下承诺：

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

统一入口禁止行为：

```text
禁止调用 LLM 生成业务承诺
禁止自动报价
禁止承诺物流结果
禁止承诺质量表现
禁止承诺质保
禁止承诺退换货
禁止承诺赔付
禁止跨模块自动拼接回答
禁止绕过子模块直接查库生成回答
```

## 10. 当前限制

Phase 2 v0.1 当前仍不支持：

```text
跨模块自动合并回答
多轮上下文
会话记忆
前端页面
人工工单落库
正式价格表
正式物流规则表
正式质保规则表
正式退换规则表
正式赔付规则表
运营后台配置
```

## 11. 后续建议

下一阶段建议进入 Phase 3。

推荐方向：

```text
Phase 3-A：Manual Handoff 工单表与转人工落库
Phase 3-B：前端统一问答页面
Phase 3-C：正式价格表与价格模块升级
Phase 3-D：正式物流规则表与物流模块升级
Phase 3-E：质保 / 退换 / 赔付规则表
```

优先建议：

```text
Phase 3-A：Manual Handoff 工单表与转人工落库
```

原因：

```text
当前 price / quality / 部分 logistics 场景已经稳定产生 handoff_required = true
但尚未将这些转人工请求落库
下一步应把转人工请求沉淀为可追踪的业务工单
```

## 12. 最终结论

Phase 2 v0.1 可以归档。

当前系统已经从四个孤立垂直接口升级为：

```text
一个统一入口
一个统一路由器
一个统一调度服务
四个受控业务模块
一套统一响应结构
一组回归检查脚本
```

后续可以在不破坏现有模块边界的前提下，继续扩展人工转接、工单落库、前端页面和正式业务规则表。
