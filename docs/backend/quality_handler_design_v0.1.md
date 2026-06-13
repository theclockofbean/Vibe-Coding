# QualityHandler 设计文档 v0.1

## 1. 文档目的

本文档用于固定质量模块中 `QualityHandler` 的职责边界、输入输出、查库规则、状态规则、转人工规则和禁止行为。

该文档对应后续实现文件：

```text
backend/app/agent/handlers/quality_handler.py
```

`QualityHandler` 接收 `QualityParameterParser` 输出的 `ParsedQualityQuery`，并转换为统一的 `HandlerResult`。

## 2. 模块定位

`QualityHandler` 位于质量问答链路第二步：

```text
用户文本
→ QualityParameterParser
→ QualityHandler
→ QualityAnswerRenderer
```

Handler 的职责是：

```text
接收结构化质量查询
根据产品引用查询 products 表
返回产品质量相关基础事实
判断是否可以自动回答
判断是否需要人工确认
构造 HandlerResult
```

Handler 不负责：

```text
不重新解析自然语言
不调用 LLM
不生成最终客服话术
不承诺产品寿命
不承诺防锈
不承诺不掉漆
不承诺质保期限
不承诺退换货
不承诺赔付
不判断质量责任
不写数据库
```

## 3. 输入

输入对象：

```python
ParsedQualityQuery
```

核心字段：

```python
raw_text: str
status: QualityParseStatus
is_quality_intent: bool
quality_query_type: QualityQueryType | None
product_reference_type: ProductReferenceType | None
product_reference_value: str | None
sku_ids: list[str]
oem_reference_numbers: list[str]
thread_specs: list[str]
warnings: list[str]
errors: list[str]
```

## 4. 输出

输出对象：

```python
HandlerResult
```

字段应包括：

```python
primary_intent = "quality"
handler_name = "quality_handler"
status: HandlerStatus
matched_count: int
handoff_required: bool
facts: dict[str, object] | None
errors: list[str]
source_references: list[SourceReference]
```

## 5. 可进入 Handler 的 parse_status

### 5.1 parsed

可以进入 Handler。

如果产品引用能匹配 `products` 表，则按 `quality_query_type` 决定是否自动回答或转人工。

### 5.2 missing_product_reference

可以进入 Handler。

但不能查产品表，因为缺少 SKU / OEM / 螺纹规格。应返回：

```python
status = "handoff"
matched_count = 0
handoff_required = True
```

### 5.3 ambiguous

不应进入正常查库逻辑。

如进入 Handler，应返回：

```python
status = "invalid_request"
matched_count = 0
handoff_required = False
```

### 5.4 not_quality_intent

不应进入正常查库逻辑。

如进入 Handler，应返回：

```python
status = "invalid_request"
matched_count = 0
handoff_required = False
```

## 6. 允许读取的数据表和字段

当前 Handler 只允许读取 `products` 表。

允许字段：

```text
sku_id
product_name
thread_spec
material
surface_treatment
oem_reference_number
```

可选读取但不得作为质量承诺依据的字段：

```text
stock_status
lead_time_days
min_order_qty
```

当前质量模块 v0.1 不建议主动使用上述可选字段。

## 7. 禁止读取或推断的数据

当前系统没有正式接入以下数据，Handler 不得推断：

```text
质检报告
检测标准
盐雾测试数据
耐磨测试数据
寿命测试数据
质保期限
退换货规则
赔付规则
安装责任规则
适配责任规则
客户投诉记录
批次质量记录
```

## 8. 产品查询策略

### 8.1 product_reference_type = sku_id

调用产品查询能力：

```text
get_by_sku_id
```

匹配成功：

```python
matched_count = 1
```

匹配失败：

```python
status = "not_found"
matched_count = 0
handoff_required = True
```

### 8.2 product_reference_type = oem_reference_number

调用产品查询能力：

```text
get_by_oem_reference
```

匹配成功：

```python
matched_count = 1
```

匹配失败：

```python
status = "not_found"
matched_count = 0
handoff_required = True
```

### 8.3 product_reference_type = thread_spec

调用产品查询能力：

```text
list_by_thread_spec
```

匹配成功：

```python
matched_count >= 1
```

如果匹配多个产品，Handler 可以返回多个产品基础 facts，但 Renderer 需要控制展示数量。

匹配失败：

```python
status = "not_found"
matched_count = 0
handoff_required = True
```

## 9. quality_query_type 处理规则

### 9.1 material

允许自动回答。

如果产品匹配成功且 `material` 有值：

```python
status = "success"
handoff_required = False
```

facts 中应包含：

```python
material_available = True
quality_commitment_made = False
```

如果产品匹配成功但 `material` 为空：

```python
status = "handoff"
handoff_required = True
material_available = False
```

### 9.2 surface_treatment

允许自动回答。

如果产品匹配成功且 `surface_treatment` 有值：

```python
status = "success"
handoff_required = False
```

facts 中应包含：

```python
surface_treatment_available = True
quality_commitment_made = False
```

如果产品匹配成功但 `surface_treatment` 为空：

```python
status = "handoff"
handoff_required = True
surface_treatment_available = False
```

### 9.3 durability

必须转人工。

```python
status = "handoff"
handoff_required = True
durability_committed = False
```

不得承诺：

```text
耐用几年
不会坏
质量一定好
长期使用无问题
```

### 9.4 rust_resistance

必须转人工。

```python
status = "handoff"
handoff_required = True
rust_resistance_committed = False
```

可以附带已登记材质和表面处理，但不得承诺不生锈。

### 9.5 scratch_resistance

必须转人工。

```python
status = "handoff"
handoff_required = True
scratch_resistance_committed = False
```

不得承诺不掉漆、不磨损、不刮花。

### 9.6 fitment_risk

必须转人工。

```python
status = "handoff"
handoff_required = True
fitment_committed = False
```

不得承诺一定适配、装不上一定负责。

### 9.7 defect_issue

必须转人工。

```python
status = "handoff"
handoff_required = True
defect_judgement_made = False
```

不得判断责任，不得承诺补发、赔付、退款。

### 9.8 warranty

必须转人工。

```python
status = "handoff"
handoff_required = True
warranty_committed = False
```

不得承诺任何具体质保期限。

### 9.9 return_exchange

必须转人工。

```python
status = "handoff"
handoff_required = True
return_exchange_committed = False
```

不得承诺一定可退、一定可换。

### 9.10 compensation

必须转人工。

```python
status = "handoff"
handoff_required = True
compensation_committed = False
```

不得承诺赔付、补偿、补发。

### 9.11 general_quality

必须转人工。

```python
status = "handoff"
handoff_required = True
quality_commitment_made = False
```

不得泛化评价“质量很好”“很耐用”“放心用”。

## 10. HandlerResult facts 结构建议

### 10.1 通用 facts

```python
{
    "raw_text": "...",
    "is_quality_intent": True,
    "quality_query_type": "material",
    "product_reference_type": "sku_id",
    "product_reference_value": "SKU001",
    "sku_ids": ["SKU001"],
    "oem_reference_numbers": [],
    "thread_specs": [],
}
```

### 10.2 产品 facts

匹配产品时增加：

```python
"products": [
    {
        "sku_id": "SKU001",
        "product_name": "铝合金竞技换挡球头",
        "thread_spec": "M8×1.25",
        "oem_reference_number": "43330-39585",
        "material": "铝合金",
        "surface_treatment": "阳极氧化"
    }
]
```

### 10.3 风险控制 facts

不同问题类型必须包含明确风险标记：

```python
"material_available": True
"surface_treatment_available": True
"quality_commitment_made": False
"durability_committed": False
"rust_resistance_committed": False
"scratch_resistance_committed": False
"fitment_committed": False
"defect_judgement_made": False
"warranty_committed": False
"return_exchange_committed": False
"compensation_committed": False
```

## 11. source_references 规则

如果 Handler 使用了 `products` 表，应记录：

```python
SourceReference(
    source_type="database_table",
    source_name="products",
    reference_id="SKU001",
)
```

如果没有查到产品，则不添加 source reference。

如果是 `missing_product_reference`，也不添加 source reference。

## 12. 状态规则

### 12.1 success

仅用于：

```text
material
surface_treatment
```

且必须成功匹配产品，并且对应字段有值。

### 12.2 handoff

用于：

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

### 12.3 not_found

用于产品引用存在但 `products` 表未匹配：

```text
SKU 不存在
OEM 不存在
螺纹规格没有匹配产品
```

建议：

```python
handoff_required = True
```

### 12.4 invalid_request

用于：

```text
ambiguous
not_quality_intent
```

建议：

```python
handoff_required = False
```

## 13. 禁止行为

`QualityHandler` 禁止：

```text
禁止调用 LLM
禁止生成最终客服话术
禁止承诺产品寿命
禁止承诺不会坏
禁止承诺不生锈
禁止承诺不掉漆
禁止承诺耐刮等级
禁止承诺质保期限
禁止承诺退货
禁止承诺换货
禁止承诺赔付
禁止承诺补发
禁止判断质量责任
禁止判断安装责任
禁止根据 material 推断防锈结果
禁止根据 surface_treatment 推断耐刮或防锈等级
```

## 14. v0.1 测试样例

### 14.1 material

输入：

```text
SKU001 什么材质
```

预期：

```python
handler_status = "success"
handoff_required = False
matched_count = 1
facts["products"][0]["material"] is not None
facts["quality_commitment_made"] is False
```

### 14.2 surface_treatment

输入：

```text
SKU001 表面怎么处理
```

预期：

```python
handler_status = "success"
handoff_required = False
matched_count = 1
facts["products"][0]["surface_treatment"] is not None
facts["quality_commitment_made"] is False
```

### 14.3 durability

输入：

```text
SKU001 耐用吗
```

预期：

```python
handler_status = "handoff"
handoff_required = True
facts["durability_committed"] is False
```

### 14.4 rust_resistance

输入：

```text
SKU001 会不会生锈
```

预期：

```python
handler_status = "handoff"
handoff_required = True
facts["rust_resistance_committed"] is False
```

### 14.5 scratch_resistance

输入：

```text
SKU001 会不会掉漆
```

预期：

```python
handler_status = "handoff"
handoff_required = True
facts["scratch_resistance_committed"] is False
```

### 14.6 warranty

输入：

```text
SKU001 质保多久
```

预期：

```python
handler_status = "handoff"
handoff_required = True
facts["warranty_committed"] is False
```

### 14.7 return_exchange

输入：

```text
SKU001 不合适能退吗
```

预期：

```python
handler_status = "handoff"
handoff_required = True
facts["return_exchange_committed"] is False
```

### 14.8 compensation

输入：

```text
质量问题能赔吗
```

预期：

```python
handler_status = "handoff"
matched_count = 0
handoff_required = True
errors contains "missing product reference"
facts["compensation_committed"] is False
```

### 14.9 defect_issue

输入：

```text
SKU001 收到有划痕
```

预期：

```python
handler_status = "handoff"
handoff_required = True
facts["defect_judgement_made"] is False
```

### 14.10 not_found

输入：

```text
SKU999 什么材质
```

预期：

```python
handler_status = "not_found"
matched_count = 0
handoff_required = True
```

### 14.11 ambiguous

输入：

```text
SKU001 和 SKU003 哪个质量更好
```

预期：

```python
handler_status = "invalid_request"
matched_count = 0
handoff_required = False
```

### 14.12 not_quality_intent

输入：

```text
SKU001 几天发货
```

预期：

```python
handler_status = "invalid_request"
matched_count = 0
handoff_required = False
```

## 15. 当前结论

`QualityHandler v0.1` 的核心原则是：

```text
只根据 products 表返回材质和表面处理等基础事实
只允许 material / surface_treatment 在字段存在时自动回答
所有质量承诺、售后责任、质保、退换、赔付问题必须转人工
所有承诺型字段必须显式标记为 False
```