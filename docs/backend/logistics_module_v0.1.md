# Logistics 模块归档文档 v0.1

## 1. 模块状态

当前物流模块 v0.1 已完成本地核心闭环：

```text
LogisticsParameterParser
→ LogisticsHandler
→ LogisticsAnswerRenderer
→ LogisticsTextQAService
→ POST /api/v1/logistics/query
```

该模块已经完成：

```text
参数解析
产品基础信息查询
受控物流回答渲染
文本问答服务封装
HTTP API 接口
API 正常场景测试
API 边界场景测试
```

## 2. 模块目标

Logistics 模块 v0.1 的目标不是自动承诺物流结果，而是：

```text
识别物流问题
提取物流参数
查询 products 表中已有的物流基础字段
仅回答可被结构化数据支撑的发货周期和备货状态
对高风险物流问题统一转人工
输出结构化 JSON
```

## 3. 已实现能力

### 3.1 支持识别的问题类型

```text
shipping_time
stock_status
shipping_fee
free_shipping
delivery_time
carrier
tracking
expedite
```

### 3.2 可自动回答的问题

当前仅允许自动回答低风险问题：

```text
shipping_time：发货周期
stock_status：备货状态 / 是否现货
```

### 3.3 必须转人工的问题

以下问题必须转人工：

```text
shipping_fee：物流费用 / 运费 / 邮费
free_shipping：免运 / 包邮
delivery_time：到货时间 / 几天到
carrier：快递公司 / 指定快递
tracking：物流单号 / 快递单号
expedite：加急 / 今天能否发 / 马上发
missing_product_reference：缺少 SKU、OEM 或螺纹规格
not_found：产品引用未匹配
```

## 4. 数据来源

当前物流模块只读取数据库中的 `products` 表。

允许读取字段：

```text
sku_id
product_name
thread_spec
oem_reference_number
stock_status
lead_time_days
min_order_qty
```

字段含义：

```text
stock_status：备货状态
lead_time_days：发货周期，不代表到货时间
min_order_qty：起订量，不代表价格、不代表免运条件
```

## 5. 明确不支持的数据

当前系统没有正式接入以下数据：

```text
具体运费金额
免运规则
地区运费规则
快递公司规则
物流单号
订单发货记录
预计到货日期
加急规则
赔付规则
```

因此系统不得推断或生成上述内容。

## 6. 文件清单

### 6.1 文档文件

```text
docs/backend/logistics_module_boundary_v0.1.md
docs/backend/logistics_parameter_parser_design_v0.1.md
docs/backend/logistics_handler_design_v0.1.md
docs/backend/logistics_answer_renderer_design_v0.1.md
docs/backend/logistics_api_design_v0.1.md
docs/backend/logistics_module_v0.1.md
```

### 6.2 Parser

```text
backend/app/agent/parsers/logistics_parameter_parser.py
```

核心对象：

```text
LogisticsParameterParser
ParsedLogisticsQuery
LogisticsParseStatus
LogisticsQueryType
ProductReferenceType
```

### 6.3 Handler

```text
backend/app/agent/handlers/logistics_handler.py
```

核心对象：

```text
LogisticsHandler
LogisticsHandlerResult
```

### 6.4 Renderer

```text
backend/app/agent/renderers/logistics_answer_renderer.py
```

核心对象：

```text
LogisticsAnswerRenderer
```

### 6.5 TextQAService

```text
backend/app/agent/services/logistics_text_qa_service.py
```

核心对象：

```text
LogisticsTextQAService
LogisticsTextQAResult
```

### 6.6 API

```text
backend/app/api/v1/logistics.py
backend/app/api/v1/router.py
```

接口：

```text
POST /api/v1/logistics/query
```

### 6.7 测试与 Demo 脚本

```text
backend/scripts/check_logistics_parameter_parser.py
backend/scripts/check_logistics_handler.py
backend/scripts/check_logistics_answer_renderer.py
backend/scripts/check_logistics_text_qa_service.py
backend/scripts/demo_logistics_text_qa.py
backend/scripts/check_logistics_api.py
backend/scripts/check_logistics_api_boundaries.py
```

## 7. API 说明

### 7.1 请求地址

```text
POST /api/v1/logistics/query
```

### 7.2 请求体

```json
{
  "text": "SKU001 几天发货",
  "limit": 5
}
```

### 7.3 请求字段限制

```text
text：必填，1 到 500 字符
limit：可选，1 到 20，默认 5
```

### 7.4 响应字段

```json
{
  "parse_status": "parsed",
  "is_logistics_intent": true,
  "logistics_query_type": "shipping_time",
  "product_reference_type": "sku_id",
  "product_reference_value": "SKU001",
  "sku_ids": ["SKU001"],
  "quantity": null,
  "destination_text": null,
  "warnings": [],
  "errors": [],
  "handler_status": "success",
  "matched_count": 1,
  "answer_text": "查到 SKU001：铝合金竞技换挡球头。当前备货状态为现货，发货周期约 2 天。该时间仅表示发货周期，不代表到货时间。",
  "handoff_required": false,
  "source_references": [
    {
      "source_type": "database_table",
      "source_name": "products",
      "reference_id": "SKU001"
    }
  ]
}
```

## 8. 状态规则

### 8.1 parse_status

```text
parsed：成功识别物流意图并提取产品引用
not_logistics_intent：不是物流问题
missing_product_reference：是物流问题，但缺少产品引用
ambiguous：存在多个 SKU / OEM / 螺纹规格等歧义
```

### 8.2 handler_status

```text
success：可自动回答
handoff：需要人工确认
not_found：产品引用未匹配
invalid_request：非物流问题或歧义输入
failed：异常状态
```

### 8.3 handoff_required

```text
false：系统可直接返回受控回答
true：需要人工进一步确认
```

## 9. 已验证场景

### 9.1 发货周期

输入：

```text
SKU001 几天发货
```

预期：

```text
parse_status = parsed
handler_status = success
handoff_required = false
answer_text 包含 “发货周期约 2 天”
answer_text 包含 “不代表到货时间”
```

### 9.2 备货状态

输入：

```text
SKU001 有现货吗
```

预期：

```text
handler_status = success
handoff_required = false
answer_text 包含 “当前备货状态为现货”
```

### 9.3 运费

输入：

```text
SKU001 运费多少
```

预期：

```text
handler_status = handoff
handoff_required = true
answer_text 包含 “不能自动承诺具体物流费用”
```

### 9.4 免运

输入：

```text
SKU001 包邮吗
```

预期：

```text
handler_status = handoff
handoff_required = true
answer_text 包含 “不能自动承诺免运”
```

### 9.5 到货时间

输入：

```text
SKU001 发到杭州几天
```

预期：

```text
handler_status = handoff
handoff_required = true
destination_text = 杭州
answer_text 包含 “不能自动承诺具体到货时间”
```

### 9.6 快递公司

输入：

```text
SKU001 发什么快递
```

预期：

```text
handler_status = handoff
handoff_required = true
answer_text 包含 “不能自动承诺指定快递”
```

### 9.7 加急

输入：

```text
SKU001 能加急吗
```

预期：

```text
handler_status = handoff
handoff_required = true
answer_text 包含 “不能自动承诺加急”
```

### 9.8 物流单号

输入：

```text
物流单号呢
```

预期：

```text
parse_status = missing_product_reference
handler_status = handoff
handoff_required = true
answer_text 提示提供产品引用或转人工确认
```

### 9.9 产品不存在

输入：

```text
SKU999 几天发货
```

预期：

```text
handler_status = not_found
handoff_required = true
answer_text 包含 “暂未查到 SKU999 对应的物流基础信息”
```

### 9.10 多 SKU 歧义

输入：

```text
SKU001 和 SKU003 分别几天发货
```

预期：

```text
parse_status = ambiguous
handler_status = invalid_request
handoff_required = false
answer_text 包含 “识别到多个 SKU”
```

### 9.11 非物流问题

输入：

```text
SKU001 多少钱
```

预期：

```text
parse_status = not_logistics_intent
handler_status = invalid_request
handoff_required = false
answer_text 包含 “当前未识别为物流问题”
```

## 10. 测试命令

### 10.1 Parser 检查

```powershell
python scripts\check_logistics_parameter_parser.py
```

预期：

```text
logistics parameter parser check passed
```

### 10.2 Handler 检查

```powershell
python scripts\check_logistics_handler.py
```

预期：

```text
logistics handler check passed
```

### 10.3 Renderer 检查

```powershell
python scripts\check_logistics_answer_renderer.py
```

预期：

```text
logistics answer renderer check passed
```

### 10.4 TextQAService 检查

```powershell
python scripts\check_logistics_text_qa_service.py
```

预期：

```text
logistics text QA service check passed
```

### 10.5 Demo

```powershell
python scripts\demo_logistics_text_qa.py
```

### 10.6 API 检查

```powershell
python scripts\check_logistics_api.py
```

预期：

```text
logistics API check passed
```

### 10.7 API 边界检查

```powershell
python scripts\check_logistics_api_boundaries.py
```

预期：

```text
logistics API boundary check passed
```

### 10.8 手动接口测试

启动服务：

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

请求：

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/api/v1/logistics/query" `
  -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Body '{"text":"SKU001 几天发货","limit":5}' | ConvertTo-Json -Depth 8
```

## 11. 禁止行为

物流模块 v0.1 禁止：

```text
禁止调用 LLM 生成物流承诺
禁止输出具体运费金额
禁止承诺免运或包邮
禁止承诺具体到货时间
禁止承诺几天送达
禁止承诺指定快递
禁止承诺加急
禁止承诺赔付
禁止根据 lead_time_days 推算到货时间
禁止根据 stock_status 推算到货时间
禁止根据 quantity 推测免运
禁止根据 destination_text 推测运费
禁止编造物流单号
```

## 12. 禁止输出片段

API 返回的 `answer_text` 不得包含：

```text
保证到
一定到
今天到
明天到
准时到
几天送达
可以包邮
支持包邮
默认包邮
免运费
运费是
邮费是
快递费是
发顺丰
发圆通
发中通
今天一定发
可以加急
赔付
```

允许出现：

```text
不能自动承诺具体物流费用
不能自动承诺免运
不能自动承诺具体到货时间
不能自动承诺指定快递
不能自动承诺加急
仅表示发货周期，不代表到货时间
请转人工确认
```

## 13. 当前限制

当前物流模块仍有以下限制：

```text
没有正式物流规则表
没有地区运费规则
没有快递公司规则
没有订单数据
没有物流单号数据
没有发货仓数据
没有到货时效数据
没有加急规则
没有售后赔付规则
```

因此当前只能作为受控物流基础问答模块，不能作为完整物流自动承诺模块。

## 14. 后续升级建议

后续可新增：

```text
logistics_rules 表
shipping_region_rules 表
carrier_rules 表
order_shipments 表
tracking_records 表
manual_handoff_queue 表
```

后续可升级能力：

```text
按地区识别是否可发
按订单查询物流单号
按规则计算运费区间
按规则识别是否满足免运条件
按渠道规则生成更细的转人工原因
接入人工确认队列
接入前端管理后台
```

升级前提：

```text
所有物流规则必须结构化入库
所有规则必须有 verification_status
所有规则必须经过人工业务确认
未确认规则不得进入自动回答
```

## 15. 当前结论

Logistics 模块 v0.1 已完成 Phase 1 的本地核心闭环。

它当前具备：

```text
稳定解析物流问题
稳定查询产品备货状态与发货周期
稳定拒绝高风险物流承诺
稳定输出受控客服回复
稳定提供 HTTP API
```

它当前不具备：

```text
自动报价物流费用
自动承诺免运
自动承诺到货时间
自动指定快递公司
自动查询物流单号
自动处理加急
```

因此，Logistics v0.1 可作为后续渠道接入和前端联调的基础能力。