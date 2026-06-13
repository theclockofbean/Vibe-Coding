# Unified Agent API 设计文档 v0.1

## 1. 文档目的

本文档用于固定 Phase 2 统一入口 API 的职责边界、请求响应结构、路由挂载方式、错误处理规则和测试范围。

对应后续实现文件：

```text
backend/app/api/v1/agent.py
backend/app/api/v1/router.py
```

## 2. API 定位

Unified Agent API 是 Phase 2 的统一问答入口。

它位于链路最上层：

```text
POST /api/v1/agent/query
→ UnifiedTextQAService
→ UnifiedIntentRouter
→ Spec / Price / Logistics / Quality TextQAService
→ UnifiedTextQAResult
→ API Response
```

它只负责：

```text
接收 HTTP 请求
校验 text / limit
构建 ProductRepository
调用 UnifiedTextQAService
返回统一 JSON
```

它不负责：

```text
不直接解析意图
不直接查询 products 表
不调用 LLM
不直接调用子模块 Handler
不直接调用子模块 Renderer
不生成额外 answer_text
不承诺价格
不承诺库存
不承诺到货
不承诺质量
不承诺质保
不承诺退换
不承诺赔付
不写数据库
```

## 3. 路由设计

新增路由：

```text
POST /api/v1/agent/query
```

建议 `agent.py` 内部自带 prefix：

```python
router = APIRouter(
    prefix="/agent",
    tags=["agent"],
)
```

因此 `router.py` 中应使用：

```python
api_router.include_router(agent_router)
```

不要额外写：

```python
api_router.include_router(agent_router, prefix="/agent")
```

否则会变成：

```text
/api/v1/agent/agent/query
```

## 4. 请求体

```json
{
  "text": "SKU001 什么材质",
  "limit": 5
}
```

字段规则：

```text
text：必填，1 到 500 字符
limit：可选，1 到 20，默认 5
```

## 5. 响应体

统一响应结构：

```json
{
  "selected_module": "spec",
  "route_status": "routed",
  "route_confidence": 0.75,
  "candidate_modules": ["spec"],
  "matched_signals": ["材质"],
  "parse_status": "parsed",
  "handler_status": "success",
  "answer_text": "查到 SKU001：铝合金竞技换挡球头。螺纹规格为 M8×1.25...",
  "handoff_required": false,
  "source_references": [
    {
      "source_table": "products",
      "query_type": "sku_id",
      "query_value": "SKU001"
    }
  ],
  "module_payload": {
    "...": "原始子模块响应"
  },
  "warnings": [],
  "errors": []
}
```

## 6. 字段说明

```text
selected_module：最终选择的模块，可能为 spec / price / logistics / quality / null
route_status：UnifiedIntentRouter 状态，routed / ambiguous / unknown / invalid_request
route_confidence：路由置信度
candidate_modules：候选模块
matched_signals：命中的意图信号
parse_status：子模块解析状态；未进入子模块时等于 route_status
handler_status：子模块处理状态；未进入子模块时为 invalid_request
answer_text：最终可展示回答
handoff_required：是否需要人工处理
source_references：事实来源引用
module_payload：子模块原始响应，v0.1 保留用于调试
warnings：提示
errors：错误
```

## 7. 状态规则

### 7.1 routed

当 `route_status = routed` 时：

```text
必须有 selected_module
必须调用对应子模块 TextQAService
module_payload 不得为空
answer_text 来自子模块
```

示例：

```text
SKU001 螺纹是多少 → spec
SKU001 多少钱 → price
SKU001 几天发货 → logistics
SKU001 会不会生锈 → quality
```

### 7.2 ambiguous

当 `route_status = ambiguous` 时：

```text
selected_module = null
不调用任何子模块
module_payload = null
handler_status = invalid_request
handoff_required = false
```

回答：

```text
识别到多个业务问题，请拆分为规格、价格、物流或质量中的一个问题后重新提问。
```

### 7.3 unknown

当 `route_status = unknown` 时：

```text
selected_module = null
不调用任何子模块
module_payload = null
handler_status = invalid_request
handoff_required = false
```

回答：

```text
当前未识别到可处理的业务问题，请补充 SKU 和具体问题，例如规格、价格、发货或质量。
```

### 7.4 invalid_request

当请求为空白或超长时：

```text
HTTP 422 或统一 invalid_request 均可接受
v0.1 API 层优先使用 HTTP 422 做基础字段校验
```

## 8. 路由样例

### 8.1 spec

请求：

```json
{
  "text": "SKU001 螺纹是多少",
  "limit": 5
}
```

预期：

```text
selected_module = spec
route_status = routed
parse_status = parsed
handler_status = success
handoff_required = false
answer_text 包含 “螺纹规格”
```

### 8.2 price

请求：

```json
{
  "text": "SKU001 多少钱",
  "limit": 5
}
```

预期：

```text
selected_module = price
route_status = routed
handler_status = handoff
handoff_required = true
answer_text 包含 “不能直接给出报价”
```

### 8.3 logistics

请求：

```json
{
  "text": "SKU001 几天发货",
  "limit": 5
}
```

预期：

```text
selected_module = logistics
route_status = routed
handler_status = success
handoff_required = false
answer_text 包含 “发货周期”
answer_text 包含 “不代表到货时间”
```

### 8.4 quality

请求：

```json
{
  "text": "SKU001 会不会生锈",
  "limit": 5
}
```

预期：

```text
selected_module = quality
route_status = routed
handler_status = handoff
handoff_required = true
answer_text 包含 “不能自动承诺不生锈”
```

### 8.5 ambiguous

请求：

```json
{
  "text": "SKU001 多少钱，几天发货，质量怎么样",
  "limit": 5
}
```

预期：

```text
selected_module = null
route_status = ambiguous
handler_status = invalid_request
handoff_required = false
module_payload = null
answer_text 包含 “识别到多个业务问题”
```

### 8.6 unknown

请求：

```json
{
  "text": "你好",
  "limit": 5
}
```

预期：

```text
selected_module = null
route_status = unknown
handler_status = invalid_request
handoff_required = false
module_payload = null
answer_text 包含 “当前未识别到可处理的业务问题”
```

## 9. HTTP 边界场景

必须测试：

```text
缺少 text → 422
text = "" → 422
text = "   " → 422
text 超过 500 字符 → 422
limit = 0 → 422
limit = 21 → 422
正常 spec → 200
正常 price → 200
正常 logistics → 200
正常 quality → 200
ambiguous → 200
unknown → 200
```

## 10. 禁止输出

Unified Agent API 返回的 `answer_text` 不得新增任何承诺。

全局禁止：

```text
保证最低价
一定包邮
保证到货
今天一定发
保证不坏
保证不生锈
保证不掉漆
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

## 11. 测试脚本规划

建议新增：

```text
backend/scripts/check_unified_agent_api.py
backend/scripts/check_unified_agent_api_boundaries.py
```

测试目标：

```text
确认 /api/v1/agent/query 已注册
确认 spec / price / logistics / quality 都可通过统一入口访问
确认 ambiguous / unknown / invalid_request 受控返回
确认 answer_text 不新增业务承诺
确认 module_payload 正确保留
```

## 12. 当前结论

Unified Agent API v0.1 是 Phase 2 的 HTTP 统一入口。

它只做：

```text
HTTP 请求校验
UnifiedTextQAService 调用
统一 JSON 返回
```

它不做：

```text
LLM 生成
数据库直查
跨模块合并回答
业务承诺生成
```

通过该 API 后，前端或外部渠道只需要调用：

```text
POST /api/v1/agent/query
```

即可进入统一问答能力。
