# QualityTextQAService 与 Quality API 设计文档 v0.1

## 1. 文档目的

本文档用于固定质量模块中 `QualityTextQAService` 与 `Quality API` 的职责边界、输入输出、接口字段、状态规则、禁止行为和测试范围。

对应后续实现文件：

```text
backend/app/agent/services/quality_text_qa_service.py
backend/app/api/v1/quality.py
```

## 2. 模块定位

质量文本问答链路为：

```text
用户文本
→ QualityParameterParser
→ QualityHandler
→ QualityAnswerRenderer
→ QualityTextQAService
→ Quality API Response
```

`QualityTextQAService` 负责串联 parser、handler、renderer。

`Quality API` 负责接收 HTTP 请求并返回结构化 JSON。

## 3. 禁止事项

TextQAService 与 API 禁止：

```text
不调用 LLM
不绕过 Parser
不绕过 Handler
不绕过 Renderer
不直接查数据库
不生成额外客服话术
不承诺产品寿命
不承诺防锈
不承诺不掉漆
不承诺耐刮等级
不承诺质保期限
不承诺退换货
不承诺赔付
不判断质量责任
不判断安装责任
不写数据库
```

## 4. QualityTextQAService 设计

### 4.1 输入

```python
text: str
limit: int = 5
```

字段说明：

```text
text：用户输入文本
limit：后续用于控制多产品展示或扩展，v0.1 默认 5
```

v0.1 中 `limit` 不影响 parser，但 API 层仍保留该字段，方便后续扩展。

### 4.2 输出对象

建议定义：

```python
@dataclass(frozen=True)
class QualityTextQAResult:
    parsed_query: ParsedQualityQuery
    handler_result: HandlerResult
    rendered_answer: RenderedAnswer
```

### 4.3 to_response_payload

`QualityTextQAResult` 应提供：

```python
def to_response_payload(self) -> dict[str, object]:
    ...
```

输出字段：

```json
{
  "parse_status": "parsed",
  "is_quality_intent": true,
  "quality_query_type": "material",
  "product_reference_type": "sku_id",
  "product_reference_value": "SKU001",
  "sku_ids": ["SKU001"],
  "oem_reference_numbers": [],
  "thread_specs": [],
  "warnings": [],
  "errors": [],
  "handler_status": "success",
  "matched_count": 1,
  "answer_text": "查到 SKU001：铝合金竞技换挡球头。该产品登记材质为铝合金。该回答仅基于当前已登记的产品信息，不代表额外质量承诺。",
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

## 5. Quality API 设计

### 5.1 路由

```text
POST /api/v1/quality/query
```

### 5.2 请求体

```json
{
  "text": "SKU001 什么材质",
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
  "is_quality_intent": true,
  "quality_query_type": "material",
  "product_reference_type": "sku_id",
  "product_reference_value": "SKU001",
  "sku_ids": ["SKU001"],
  "oem_reference_numbers": [],
  "thread_specs": [],
  "warnings": [],
  "errors": [],
  "handler_status": "success",
  "matched_count": 1,
  "answer_text": "查到 SKU001：铝合金竞技换挡球头。该产品登记材质为铝合金。该回答仅基于当前已登记的产品信息，不代表额外质量承诺。",
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

仅用于低风险、可由 `products` 表字段直接支撑的问题：

```text
material
surface_treatment
```

前提：

```text
产品引用唯一
products 表匹配成功
对应字段有值
```

示例：

```text
SKU001 什么材质
SKU001 表面怎么处理
```

### 6.2 handoff

用于需要人工确认的问题：

```text
durability
rust_resistance
scratch_resistance
fitment_risk
defect_issue
warranty
return_exchange
compensation
general_quality
missing_product_reference
material 字段缺失
surface_treatment 字段缺失
```

示例：

```text
SKU001 耐用吗
SKU001 会不会生锈
SKU001 会不会掉漆
SKU001 质保多久
SKU001 不合适能退吗
SKU001 收到有划痕
质量问题能赔吗
```

### 6.3 not_found

用于产品引用存在但数据库未匹配：

```text
SKU999 什么材质
```

### 6.4 invalid_request

用于：

```text
ambiguous
not_quality_intent
```

示例：

```text
SKU001 和 SKU003 哪个质量更好
SKU001 几天发货
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
非质量意图
缺少产品引用
产品不存在
```

## 8. 测试脚本规划

建议新增：

```text
backend/scripts/check_quality_text_qa_service.py
backend/scripts/demo_quality_text_qa.py
backend/scripts/check_quality_api.py
backend/scripts/check_quality_api_boundaries.py
```

## 9. 正常链路测试样例

### 9.1 材质

输入：

```text
SKU001 什么材质
```

预期：

```text
parse_status = parsed
handler_status = success
handoff_required = false
answer_text 包含 “登记材质”
answer_text 包含 “不代表额外质量承诺”
```

### 9.2 表面处理

输入：

```text
SKU001 表面怎么处理
```

预期：

```text
parse_status = parsed
handler_status = success
handoff_required = false
answer_text 包含 “登记表面处理”
answer_text 包含 “不代表防锈、耐刮或不掉漆承诺”
```

### 9.3 耐用性

输入：

```text
SKU001 耐用吗
```

预期：

```text
handler_status = handoff
handoff_required = true
answer_text 包含 “不能自动承诺产品寿命”
```

### 9.4 防锈

输入：

```text
SKU001 会不会生锈
```

预期：

```text
handler_status = handoff
handoff_required = true
answer_text 包含 “不能自动承诺不生锈”
answer_text 不得包含 “保证不生锈”
```

### 9.5 掉漆 / 耐刮

输入：

```text
SKU001 会不会掉漆
```

预期：

```text
handler_status = handoff
handoff_required = true
answer_text 包含 “不能自动承诺不掉漆”
answer_text 不得包含 “保证不掉漆”
```

### 9.6 质保

输入：

```text
SKU001 质保多久
```

预期：

```text
handler_status = handoff
handoff_required = true
answer_text 包含 “不能自动承诺质保期限”
answer_text 不得包含具体质保期限
```

### 9.7 退换货

输入：

```text
SKU001 不合适能退吗
```

预期：

```text
handler_status = handoff
handoff_required = true
answer_text 包含 “不能自动承诺一定可退或一定可换”
```

### 9.8 赔付

输入：

```text
质量问题能赔吗
```

预期：

```text
parse_status = missing_product_reference
handler_status = handoff
handoff_required = true
answer_text 包含 “缺少产品引用”
answer_text 不得承诺赔付
```

### 9.9 疑似瑕疵

输入：

```text
SKU001 收到有划痕
```

预期：

```text
handler_status = handoff
handoff_required = true
answer_text 包含 “不能直接判断责任”
answer_text 包含 “请提供订单、图片、视频和安装信息”
```

### 9.10 产品不存在

输入：

```text
SKU999 什么材质
```

预期：

```text
handler_status = not_found
handoff_required = true
answer_text 包含 “暂未查到 SKU999 对应的质量基础信息”
```

### 9.11 多 SKU 歧义

输入：

```text
SKU001 和 SKU003 哪个质量更好
```

预期：

```text
parse_status = ambiguous
handler_status = invalid_request
handoff_required = false
answer_text 包含 “识别到多个 SKU”
```

### 9.12 非质量意图

输入：

```text
SKU001 几天发货
```

预期：

```text
parse_status = not_quality_intent
handler_status = invalid_request
handoff_required = false
answer_text 包含 “当前未识别为质量问题”
```

## 10. 禁止输出检查

API 返回的 `answer_text` 不得包含：

```text
绝对不会坏
保证不会坏
不会坏
保证不生锈
绝对不生锈
保证不掉漆
绝对不掉漆
保证耐用
保证耐用几年
能用几年
终身质保
一年质保
两年质保
三年质保
七天无理由
一定能退
一定能换
一定赔
一定补发
质量问题一定赔
装不上一定负责
质量很好
放心用
完全没问题
```

允许出现：

```text
不能自动承诺产品寿命
不能自动承诺不生锈
不能自动承诺不掉漆
不能自动承诺质保期限
不能自动承诺一定可退
不能自动承诺一定可换
不能自动承诺处理结果
不代表额外质量承诺
不代表防锈、耐刮或不掉漆承诺
请转人工进一步确认
```

## 11. 当前结论

`QualityTextQAService` 与 `Quality API v0.1` 的目标是：

```text
把已验证的 quality parser / handler / renderer 串成稳定接口
保持所有质量承诺边界
返回结构化 JSON
为后续前端或渠道接入提供统一能力
```