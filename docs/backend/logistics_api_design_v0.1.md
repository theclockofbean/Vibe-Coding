# LogisticsTextQAService 与 Logistics API 设计文档 v0.1

## 1. 文档目的

本文档用于固定物流模块中 `LogisticsTextQAService` 与 `Logistics API` 的职责边界、输入输出、接口字段、状态规则和测试范围。

对应后续实现文件：

```text
backend/app/agent/services/logistics_text_qa_service.py
backend/app/api/v1/logistics.py
```

## 2. 模块定位

物流文本问答链路为：

```text
用户文本
→ LogisticsParameterParser
→ LogisticsHandler
→ LogisticsAnswerRenderer
→ LogisticsTextQAService
→ Logistics API Response
```

`LogisticsTextQAService` 负责串联 parser、handler、renderer。

`Logistics API` 负责接收 HTTP 请求并返回结构化 JSON。

## 3. 禁止事项

TextQAService 与 API 禁止：

```text
不调用 LLM
不绕过 Parser
不绕过 Handler
不绕过 Renderer
不直接查数据库
不生成额外客服话术
不承诺到货时间
不承诺具体运费
不承诺免运
不承诺指定快递
不承诺加急
不写数据库
```

## 4. LogisticsTextQAService 设计

### 4.1 输入

```python
text: str
limit: int = 5
```

其中：

```text
text：用户输入文本
limit：最多用于控制多产品展示或后续扩展，v0.1 默认 5
```

v0.1 中 `limit` 不直接影响 parser，但可传递给后续扩展。

### 4.2 输出

建议定义：

```python
@dataclass(frozen=True)
class LogisticsTextQAResult:
    parsed_query: ParsedLogisticsQuery
    handler_result: HandlerResult
    rendered_answer: RenderedAnswer
```

### 4.3 to_response_payload

`LogisticsTextQAResult` 应提供：

```python
def to_response_payload(self) -> dict[str, object]:
    ...
```

输出字段：

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
  "source_references": []
}
```

## 5. Logistics API 设计

### 5.1 路由

```text
POST /api/v1/logistics/query
```

### 5.2 请求体

```json
{
  "text": "SKU001 几天发货",
  "limit": 5
}
```

### 5.3 请求字段限制

```text
text：必填，1 到 500 字符
limit：可选，1 到 20，默认 5
```

### 5.4 响应体

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

## 6. API 状态规则

### 6.1 success

仅用于低风险可自动回答问题：

```text
shipping_time
stock_status
```

且必须匹配到产品。

示例：

```text
SKU001 几天发货
SKU001 有现货吗
```

### 6.2 handoff

用于需要人工确认的问题：

```text
shipping_fee
free_shipping
delivery_time
carrier
tracking
expedite
missing_product_reference
```

示例：

```text
SKU001 运费多少
SKU001 包邮吗
SKU001 发到杭州几天
SKU001 发什么快递
SKU001 能加急吗
物流单号呢
几天发货
```

### 6.3 not_found

用于产品引用存在但数据库未匹配：

```text
SKU999 几天发货
```

### 6.4 invalid_request

用于：

```text
ambiguous
not_logistics_intent
```

示例：

```text
SKU001 和 SKU003 分别几天发货
SKU001 多少钱
```

## 7. API 边界场景

必须覆盖：

```text
空文本
空白文本
缺少 text
超长 text
limit 小于 1
limit 大于 20
多个 SKU
多个 OEM
多个螺纹规格
非物流意图
缺少产品引用
产品不存在
```

## 8. 测试脚本规划

建议新增：

```text
backend/scripts/check_logistics_text_qa_service.py
backend/scripts/demo_logistics_text_qa.py
backend/scripts/check_logistics_api.py
backend/scripts/check_logistics_api_boundaries.py
```

## 9. 正常链路测试样例

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

### 9.2 现货状态

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

### 9.6 非物流意图

输入：

```text
SKU001 多少钱
```

预期：

```text
parse_status = not_logistics_intent
handler_status = invalid_request
handoff_required = false
```

## 10. 禁止输出检查

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

## 11. 当前结论

`LogisticsTextQAService` 与 `Logistics API v0.1` 的目标是：

```text
把已验证的物流 parser / handler / renderer 串成稳定接口
保持所有物流承诺边界
返回结构化 JSON
为后续前端或渠道接入提供统一能力
```
