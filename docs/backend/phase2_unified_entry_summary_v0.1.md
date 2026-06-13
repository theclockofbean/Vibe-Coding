# Phase 2 统一入口归档文档 v0.1

## 1. 阶段状态

Phase 2 已完成统一入口的第一版闭环。

已完成模块：

```text
UnifiedIntentRouter
UnifiedTextQAService
Unified Agent API
Unified Agent API Boundary Check
```

当前统一入口：

```text
POST /api/v1/agent/query
```

该入口位于 Phase 1 四个垂直模块之上：

```text
POST /api/v1/spec/query
POST /api/v1/price/query
POST /api/v1/logistics/query
POST /api/v1/quality/query
```

## 2. 当前调用链路

统一入口完整链路：

```text
POST /api/v1/agent/query
→ UnifiedTextQAService
→ UnifiedIntentRouter
→ SpecTextQAService / PriceTextQAService / LogisticsTextQAService / QualityTextQAService
→ UnifiedTextQAResult
→ API JSON Response
```

## 3. 已完成能力

### 3.1 统一意图识别

`UnifiedIntentRouter` 已支持识别以下模块：

```text
spec
price
logistics
quality
```

支持状态：

```text
routed
ambiguous
unknown
invalid_request
```

核心规则：

```text
单模块命中 → routed
多模块明确诉求 → ambiguous
无业务意图 → unknown
空白或非法输入 → invalid_request
```

### 3.2 统一调度服务

`UnifiedTextQAService` 已支持：

```text
调用 UnifiedIntentRouter
根据 selected_module 调用对应子模块 TextQAService
包装统一响应结构
处理 ambiguous / unknown / invalid_request
保留 module_payload
```

它不做：

```text
不直接查库绕过子模块
不调用 LLM
不跨模块拼接回答
不新增业务承诺
```

### 3.3 统一 API

新增接口：

```text
POST /api/v1/agent/query
```

请求体：

```json
{
  "text": "SKU001 什么材质",
  "limit": 5
}
```

响应体统一包含：

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

## 4. 当前路由规则

`agent.py` 内部自带：

```python
router = APIRouter(
    prefix="/agent",
    tags=["agent"],
)
```

因此 `router.py` 中应保持：

```python
api_router.include_router(agent_router)
```

不得写成：

```python
api_router.include_router(agent_router, prefix="/agent")
```

否则会变成错误路径：

```text
/api/v1/agent/agent/query
```

## 5. 已完成文件

### 5.1 Router 层

```text
backend/app/agent/routers/unified_intent_router.py
backend/app/agent/routers/__init__.py
```

### 5.2 Service 层

```text
backend/app/agent/services/unified_text_qa_service.py
backend/app/agent/services/__init__.py
```

### 5.3 API 层

```text
backend/app/api/v1/agent.py
backend/app/api/v1/router.py
```

### 5.4 检查脚本

```text
backend/scripts/check_unified_intent_router.py
backend/scripts/check_unified_text_qa_service.py
backend/scripts/check_unified_agent_api.py
backend/scripts/check_unified_agent_api_boundaries.py
```

## 6. 当前验证结果

已通过：

```text
UnifiedIntentRouter 检查
UnifiedTextQAService 检查
Unified Agent API 检查
Unified Agent API 边界检查
```

核心覆盖场景：

```text
SKU001 螺纹是多少 → spec
SKU001 多少钱 → price / handoff
SKU001 几天发货 → logistics
SKU001 会不会生锈 → quality / handoff
SKU001 什么材质 → spec
SKU001 这个材质耐用吗 → quality / handoff
SKU001 多少钱，几天发货，质量怎么样 → ambiguous
你好 → unknown
空白 text → 422
limit 越界 → 422
```

## 7. 当前安全边界

统一入口禁止：

```text
禁止调用 LLM
禁止自动报价
禁止承诺最低价
禁止承诺包邮
禁止承诺到货
禁止承诺当天一定发货
禁止承诺不坏
禁止承诺不生锈
禁止承诺不掉漆
禁止承诺质保期限
禁止承诺退换货
禁止承诺赔付
禁止跨模块合并回答
禁止直接查库绕过子模块
```

## 8. 当前各模块行为

### 8.1 spec

```text
可自动回答结构化产品信息
可返回螺纹、材质、表面处理、OEM、起订量、库存、发货周期等已登记信息
```

### 8.2 price

```text
当前未接入正式价格表
价格问题统一受控转人工
不自动报价
```

### 8.3 logistics

```text
可自动回答发货周期与库存状态
不承诺到货时间
不承诺包邮
不承诺承运商
不承诺加急
```

### 8.4 quality

```text
可回答登记材质与表面处理
质量承诺、耐用、防锈、掉漆、质保、退换、赔付统一转人工
不自动判断质量责任
```

## 9. 当前限制

Phase 2 v0.1 当前仍有以下限制：

```text
不支持跨模块自动合并回答
不支持多轮上下文
不支持会话记忆
不支持前端页面
不支持人工工单落库
不支持正式价格表
不支持正式物流规则表
不支持正式质保/退换/赔付规则表
```

## 10. 后续建议

下一步建议进入总回归检查：

```text
Phase 2 Total Regression Check
```

建议新增脚本：

```text
backend/scripts/check_phase2_total_regression.py
```

该脚本应统一检查：

```text
Phase 1 四个垂直 API 路由
UnifiedIntentRouter
UnifiedTextQAService
Unified Agent API
Unified Agent API Boundary
禁止承诺片段
```

## 11. 当前结论

Phase 2 统一入口 v0.1 已完成后端闭环。

当前系统已经具备：

```text
四模块垂直问答能力
统一意图路由
统一调度服务
统一 HTTP 入口
统一响应结构
边界受控检查
```

统一入口当前可作为后续前端联调、人工转接、工单落库、多轮上下文的基础。