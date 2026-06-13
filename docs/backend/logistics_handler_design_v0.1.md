# LogisticsHandler 设计文档 v0.1

## 1. 文档目的

本文档用于固定物流模块中 `LogisticsHandler` 的职责边界、输入输出、查库规则、转人工规则和禁止行为。

该文档对应后续实现文件：

```text
backend/app/agent/handlers/logistics_handler.py
```

`LogisticsHandler` 接收 `LogisticsParameterParser` 输出的 `ParsedLogisticsQuery`，并将其转换为统一的 `HandlerResult`。

## 2. 模块定位

`LogisticsHandler` 位于物流链路第二步：

```text
用户文本
→ LogisticsParameterParser
→ LogisticsHandler
→ LogisticsAnswerRenderer
```

它的职责是：

```text
接收结构化物流查询
根据产品引用查询 products 表
返回产品备货状态和发货周期
判断是否需要人工确认
构造 HandlerResult
```

它不负责：

```text
不重新解析自然语言
不调用 LLM
不生成最终客服话术
不承诺到货时间
不承诺运费
不承诺包邮
不承诺指定快递
不承诺加急
不写数据库
```

## 3. 输入

### 3.1 输入对象

`LogisticsHandler` 的输入为：

```python
ParsedLogisticsQuery
```

字段来自：

```text
backend/app/agent/parsers/logistics_parameter_parser.py
```

核心字段：

```python
status: LogisticsParseStatus
raw_text: str
is_logistics_intent: bool
logistics_query_type: LogisticsQueryType | None
product_reference_type: ProductReferenceType | None
product_reference_value: str | None
sku_ids: list[str]
quantity: int | None
destination_text: str | None
warnings: list[str]
errors: list[str]
```

## 4. 输出

### 4.1 输出对象

`LogisticsHandler` 输出统一的：

```python
HandlerResult
```

字段应包括：

```python
primary_intent = "logistics"
handler_name = "logistics_handler"
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

如果产品引用能匹配 products 表，则按 `logistics_query_type` 决定是否自动回答或转人工。

### 5.2 missing_product_reference

可以进入 Handler。

但不能查产品表，因为缺少 SKU/OEM/螺纹规格。应返回补充信息提示所需 facts，并通常设置：

```python
status = "handoff"
matched_count = 0
handoff_required = True
```

### 5.3 ambiguous

不应进入正常查询逻辑。

如进入 Handler，应返回：

```python
status = "invalid_request"
matched_count = 0
handoff_required = False
```

### 5.4 not_logistics_intent

不应进入正常查询逻辑。

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
oem_reference_number
stock_status
lead_time_days
min_order_qty
```

禁止读取或推断不存在的数据：

```text
运费金额
包邮规则
快递公司
物流单号
预计到货日期
加急规则
赔付规则
地区运费规则
```

## 7. 查询策略

### 7.1 product_reference_type = sku_id

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

### 7.2 product_reference_type = oem_reference_number

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

### 7.3 product_reference_type = thread_spec

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

## 8. logistics_query_type 处理规则

### 8.1 shipping_time

含义：

```text
用户询问几天发货、发货周期、什么时候能发
```

允许自动查询：

```text
products.stock_status
products.lead_time_days
```

如果产品匹配成功：

```python
status = "success"
handoff_required = False
```

但 facts 中必须明确：

```python
time_type = "shipping_time_only"
delivery_time_committed = False
```

禁止把 `lead_time_days` 解释为到货时间。

### 8.2 stock_status

含义：

```text
用户询问是否现货、有没有货、库存、备货状态
```

允许自动查询：

```text
products.stock_status
```

如果产品匹配成功：

```python
status = "success"
handoff_required = False
```

### 8.3 shipping_fee

含义：

```text
用户询问运费、邮费、物流费、配送费、快递费
```

不允许自动回答具体金额。

无论产品是否匹配，均应：

```python
handoff_required = True
```

如果产品匹配成功，可以附带产品基础 facts，但不得生成运费。

### 8.4 free_shipping

含义：

```text
用户询问包邮、免运费、免邮
```

不允许承诺包邮。

无论产品是否匹配，均应：

```python
handoff_required = True
```

必须在 facts 中标记：

```python
free_shipping_committed = False
```

### 8.5 delivery_time

含义：

```text
用户询问几天到、多久到、什么时候到、到货时间
```

不允许根据 `lead_time_days` 推算到货时间。

无论产品是否匹配，均应：

```python
handoff_required = True
```

必须在 facts 中标记：

```python
delivery_time_committed = False
```

### 8.6 carrier

含义：

```text
用户询问发什么快递、能否发顺丰、快递公司
```

当前系统无快递公司规则。

应返回：

```python
handoff_required = True
carrier_committed = False
```

### 8.7 tracking

含义：

```text
用户询问物流单号、快递单号、查物流
```

当前系统未接订单和物流单号数据。

应返回：

```python
handoff_required = True
tracking_supported = False
```

### 8.8 expedite

含义：

```text
用户询问加急、急用、今天能不能发、能不能快点发
```

当前系统不得承诺加急。

应返回：

```python
handoff_required = True
expedite_committed = False
```

## 9. HandlerResult facts 结构建议

### 9.1 通用 facts

```python
{
    "raw_text": "...",
    "is_logistics_intent": True,
    "logistics_query_type": "shipping_time",
    "product_reference_type": "sku_id",
    "product_reference_value": "SKU001",
    "sku_ids": ["SKU001"],
    "quantity": None,
    "destination_text": None,
}
```

### 9.2 产品 facts

匹配产品时，建议增加：

```python
"products": [
    {
        "sku_id": "SKU001",
        "product_name": "铝合金竞技换挡球头",
        "thread_spec": "M8×1.25",
        "oem_reference_number": "43330-39585",
        "stock_status": "现货",
        "lead_time_days": 2,
        "min_order_qty": 1,
    }
]
```

### 9.3 风险控制 facts

不同问题类型应包含明确风险标记：

```python
"shipping_time_available": True
"delivery_time_committed": False
"shipping_fee_committed": False
"free_shipping_committed": False
"carrier_committed": False
"expedite_committed": False
"tracking_supported": False
```

## 10. source_references 规则

如果 Handler 使用了 `products` 表，应记录来源：

```python
SourceReference(
    source_type="database_table",
    source_name="products",
    reference_id="SKU001",
)
```

如果没有查到产品，则不添加 source reference。

如果是 `missing_product_reference`，也不添加 source reference。

## 11. 状态规则

### 11.1 success

仅用于可自动回答的低风险物流问题：

```text
shipping_time
stock_status
```

且必须成功匹配产品。

### 11.2 handoff

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

### 11.3 not_found

用于产品引用存在但 products 表未匹配：

```text
SKU 不存在
OEM 不存在
螺纹规格没有匹配产品
```

建议：

```python
handoff_required = True
```

### 11.4 invalid_request

用于：

```text
ambiguous
not_logistics_intent
```

建议：

```python
handoff_required = False
```

## 12. 禁止行为

`LogisticsHandler` 禁止：

```text
禁止调用 LLM
禁止生成最终客服话术
禁止承诺具体到货日期
禁止承诺几天送达
禁止承诺包邮
禁止承诺免运费
禁止承诺具体运费金额
禁止承诺指定快递
禁止承诺加急
禁止承诺赔付
禁止根据 lead_time_days 推算到货时间
禁止根据 stock_status 推算到货时间
禁止根据 destination_text 推测运费
禁止根据 quantity 推测包邮
```

## 13. 测试样例

### 13.1 shipping_time

输入：

```text
SKU001 几天发货
```

预期：

```python
handler_status = "success"
handoff_required = False
matched_count = 1
facts["products"][0]["lead_time_days"] == 2
facts["delivery_time_committed"] is False
```

### 13.2 stock_status

输入：

```text
SKU001 有现货吗
```

预期：

```python
handler_status = "success"
handoff_required = False
matched_count = 1
facts["products"][0]["stock_status"] == "现货"
```

### 13.3 shipping_fee

输入：

```text
SKU001 运费多少
```

预期：

```python
handler_status = "handoff"
handoff_required = True
facts["shipping_fee_committed"] is False
```

### 13.4 free_shipping

输入：

```text
SKU001 包邮吗
```

预期：

```python
handler_status = "handoff"
handoff_required = True
facts["free_shipping_committed"] is False
```

### 13.5 delivery_time

输入：

```text
SKU001 发到杭州几天
```

预期：

```python
handler_status = "handoff"
handoff_required = True
facts["destination_text"] == "杭州"
facts["delivery_time_committed"] is False
```

### 13.6 carrier

输入：

```text
SKU001 发什么快递
```

预期：

```python
handler_status = "handoff"
handoff_required = True
facts["carrier_committed"] is False
```

### 13.7 tracking

输入：

```text
物流单号呢
```

预期：

```python
handler_status = "handoff"
handoff_required = True
facts["tracking_supported"] is False
```

### 13.8 expedite

输入：

```text
SKU001 能加急吗
```

预期：

```python
handler_status = "handoff"
handoff_required = True
facts["expedite_committed"] is False
```

### 13.9 missing_product_reference

输入：

```text
几天发货
```

预期：

```python
handler_status = "handoff"
matched_count = 0
handoff_required = True
errors contains "missing product reference"
```

### 13.10 ambiguous

输入：

```text
SKU001 和 SKU003 分别几天发货
```

预期：

```python
handler_status = "invalid_request"
matched_count = 0
handoff_required = False
```

### 13.11 not_logistics_intent

输入：

```text
SKU001 多少钱
```

预期：

```python
handler_status = "invalid_request"
matched_count = 0
handoff_required = False
```

## 14. 当前结论

`LogisticsHandler v0.1` 的核心原则是：

```text
只回答 products 表能支撑的备货状态和发货周期
所有高风险物流承诺都转人工
所有承诺型字段都显式标记为 False
```

它不是物流承诺模块，而是物流信息受控处理模块。