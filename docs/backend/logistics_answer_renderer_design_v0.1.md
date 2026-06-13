# LogisticsAnswerRenderer 设计文档 v0.1

## 1. 文档目的

本文档用于固定物流模块中 `LogisticsAnswerRenderer` 的职责边界、输入输出、受控话术模板、禁止表达和测试样例。

该文档对应后续实现文件：

```text
backend/app/agent/renderers/logistics_answer_renderer.py
```

`LogisticsAnswerRenderer` 接收 `LogisticsHandler` 输出的 `HandlerResult`，并生成面向客户的 `RenderedAnswer`。

## 2. 模块定位

`LogisticsAnswerRenderer` 位于物流链路第三步：

```text
用户文本
→ LogisticsParameterParser
→ LogisticsHandler
→ LogisticsAnswerRenderer
```

它的职责是：

```text
读取 HandlerResult
根据 handler_status 和 logistics_query_type 选择受控模板
生成 answer_text
传递 handoff_required
传递 source_references
```

它不负责：

```text
不重新解析用户文本
不查询数据库
不调用 LLM
不修改 HandlerResult
不生成运费金额
不承诺包邮
不承诺到货时间
不承诺指定快递
不承诺加急
不承诺赔付
```

## 3. 输入

输入对象：

```python
HandlerResult
```

核心字段：

```python
primary_intent: str
handler_name: str
status: HandlerStatus
matched_count: int
handoff_required: bool
facts: dict[str, object] | None
errors: list[str]
source_references: list[SourceReference]
```

其中 `facts` 应来自 `LogisticsHandler`，包含：

```python
{
    "logistics_query_type": "...",
    "product_reference_type": "...",
    "product_reference_value": "...",
    "quantity": ...,
    "destination_text": ...,
    "products": [...],
    "shipping_time_available": ...,
    "stock_status_available": ...,
    "delivery_time_committed": False,
    "shipping_fee_committed": False,
    "free_shipping_committed": False,
    "carrier_committed": False,
    "expedite_committed": False,
    "tracking_supported": False,
}
```

## 4. 输出

输出对象：

```python
RenderedAnswer
```

字段：

```python
text: str
handoff_required: bool
source_references: list[SourceReference]
```

## 5. 总体渲染规则

Renderer 必须根据 `handler_result.status` 分流：

| handler_status  | 渲染策略            |
| --------------- | --------------- |
| success         | 渲染可自动回答内容       |
| handoff         | 渲染转人工确认内容       |
| not_found       | 渲染未查到产品提示       |
| invalid_request | 渲染参数不明确或非物流问题提示 |
| failed          | 渲染异常提示并转人工      |

## 6. success 场景模板

### 6.1 shipping_time

适用条件：

```python
handler_result.status == "success"
facts["logistics_query_type"] == "shipping_time"
```

允许使用字段：

```text
sku_id
product_name
stock_status
lead_time_days
```

模板：

```text
查到 {sku_id}：{product_name}。当前备货状态为{stock_status}，发货周期约 {lead_time_days} 天。该时间仅表示发货周期，不代表到货时间。
```

必须包含：

```text
该时间仅表示发货周期，不代表到货时间。
```

禁止表达：

```text
几天到
几天送达
预计到货
保证到
一定到
```

### 6.2 stock_status

适用条件：

```python
handler_result.status == "success"
facts["logistics_query_type"] == "stock_status"
```

允许使用字段：

```text
sku_id
product_name
stock_status
```

模板：

```text
查到 {sku_id}：{product_name}。当前备货状态为{stock_status}。
```

如果存在 `lead_time_days`，可以补充但必须限定为发货周期：

```text
如需发货周期，可进一步确认该 SKU 的发货安排。
```

v0.1 不在 stock_status 场景主动输出到货信息。

## 7. handoff 场景模板

### 7.1 missing_product_reference

适用条件：

```python
handler_result.status == "handoff"
facts["product_reference_value"] is None
```

模板：

```text
这类问题涉及物流确认。请先提供 SKU、OEM 对照号或螺纹规格；如果询问物流费用、免运条件或到货时间，还需要补充收货地区和采购数量。
```

不得承诺任何物流结果。

### 7.2 shipping_fee

适用条件：

```python
facts["logistics_query_type"] == "shipping_fee"
```

模板：

```text
物流费用需要结合收货地区、采购数量和发货方式确认。当前系统不能自动承诺具体物流费用，请转人工确认。
```

如果有产品匹配，可以前置产品识别信息：

```text
已识别到 {sku_id}：{product_name}。物流费用需要结合收货地区、采购数量和发货方式确认。当前系统不能自动承诺具体物流费用，请转人工确认。
```

禁止输出：

```text
运费金额
免运费
包邮
优惠运费
```

### 7.3 free_shipping

适用条件：

```python
facts["logistics_query_type"] == "free_shipping"
```

模板：

```text
免运条件需要结合收货地区、采购数量和当前业务政策确认。当前系统不能自动承诺免运，请转人工确认。
```

如果有产品匹配，可以前置：

```text
已识别到 {sku_id}：{product_name}。免运条件需要结合收货地区、采购数量和当前业务政策确认。当前系统不能自动承诺免运，请转人工确认。
```

禁止输出：

```text
可以包邮
支持包邮
满多少包邮
默认包邮
```

### 7.4 delivery_time

适用条件：

```python
facts["logistics_query_type"] == "delivery_time"
```

模板：

```text
到货时间受收货地区、快递方式和物流揽收影响。当前系统不能自动承诺具体到货时间，请转人工确认。
```

如果存在 `destination_text`，可以写：

```text
已识别到收货地区：{destination_text}。到货时间受收货地区、快递方式和物流揽收影响。当前系统不能自动承诺具体到货时间，请转人工确认。
```

如果有产品匹配，可以前置产品识别信息。

禁止根据 `lead_time_days` 推算到货时间。

### 7.5 carrier

适用条件：

```python
facts["logistics_query_type"] == "carrier"
```

模板：

```text
快递公司需要结合订单、发货仓和当时发货安排确认。当前系统不能自动承诺指定快递，请转人工确认。
```

禁止输出：

```text
发顺丰
发圆通
默认中通
指定快递
```

### 7.6 tracking

适用条件：

```python
facts["logistics_query_type"] == "tracking"
```

模板：

```text
物流单号需要根据已生成订单或发货记录查询。当前系统未接入订单物流数据，请转人工确认。
```

禁止编造单号。

### 7.7 expedite

适用条件：

```python
facts["logistics_query_type"] == "expedite"
```

模板：

```text
加急发货需要结合库存、订单时间和仓库处理能力确认。当前系统不能自动承诺加急，请转人工确认。
```

禁止输出：

```text
今天一定发
马上发
优先发
可以加急
```

## 8. not_found 场景模板

适用条件：

```python
handler_result.status == "not_found"
```

模板：

```text
暂未查到该产品对应的物流基础信息。请核对 SKU、OEM 对照号或螺纹规格后再确认；如仍无法确认，请转人工处理。
```

如果存在产品引用值，可以写：

```text
暂未查到 {product_reference_value} 对应的物流基础信息。请核对 SKU、OEM 对照号或螺纹规格后再确认；如仍无法确认，请转人工处理。
```

应设置：

```python
handoff_required = True
```

## 9. invalid_request 场景模板

### 9.1 ambiguous

如果 errors 包含：

```text
multiple SKU IDs found in logistics query
```

模板：

```text
识别到多个 SKU，请一次只询问一个产品的物流信息。
```

如果 errors 包含：

```text
multiple OEM reference numbers found
```

模板：

```text
识别到多个 OEM 对照号，请一次只询问一个产品的物流信息。
```

如果 errors 包含：

```text
multiple thread specs found
```

模板：

```text
识别到多个螺纹规格，请一次只询问一个规格的物流信息。
```

如果 errors 包含：

```text
multiple destinations found in logistics query
```

模板：

```text
识别到多个收货地区，请一次只询问一个地区的物流信息。
```

### 9.2 not_logistics_intent

如果 `facts["is_logistics_intent"] is False`，模板：

```text
当前未识别为物流问题，未进入物流处理。
```

## 10. failed 场景模板

适用条件：

```python
handler_result.status == "failed"
```

模板：

```text
当前物流查询状态异常，请转人工确认。
```

应设置：

```python
handoff_required = True
```

## 11. 产品信息前缀规则

如果 `facts["products"]` 非空，Renderer 可以构造产品前缀：

```text
已识别到 {sku_id}：{product_name}。
```

多产品匹配时，最多展示前 3 个产品：

```text
已匹配到多个产品：SKU001、SKU002、SKU003。请进一步确认具体 SKU。
```

v0.1 中，多产品展示只用于 thread_spec 查询结果，不得基于多个产品给出运费、到货时间或快递承诺。

## 12. 禁止词与风险表达

Renderer 输出不得包含以下承诺型表达：

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
马上发
今天一定发
可以加急
赔付
```

允许出现的安全表达：

```text
不能自动承诺具体物流费用
不能自动承诺免运
不能自动承诺具体到货时间
不能自动承诺指定快递
不能自动承诺加急
仅表示发货周期，不代表到货时间
请转人工确认
```

## 13. 测试样例

### 13.1 shipping_time success

输入：

```text
SKU001 几天发货
```

预期回答包含：

```text
查到 SKU001
当前备货状态为现货
发货周期约 2 天
该时间仅表示发货周期，不代表到货时间
```

预期：

```python
handoff_required is False
```

### 13.2 stock_status success

输入：

```text
SKU001 有现货吗
```

预期回答包含：

```text
查到 SKU001
当前备货状态为现货
```

预期：

```python
handoff_required is False
```

### 13.3 shipping_fee handoff

输入：

```text
SKU001 运费多少
```

预期回答包含：

```text
当前系统不能自动承诺具体物流费用
请转人工确认
```

预期：

```python
handoff_required is True
```

不得包含：

```text
运费是
邮费是
元
```

### 13.4 free_shipping handoff

输入：

```text
SKU001 包邮吗
```

预期回答包含：

```text
当前系统不能自动承诺免运
请转人工确认
```

预期：

```python
handoff_required is True
```

不得包含：

```text
可以包邮
支持包邮
默认包邮
```

### 13.5 delivery_time handoff

输入：

```text
SKU001 发到杭州几天
```

预期回答包含：

```text
已识别到收货地区：杭州
当前系统不能自动承诺具体到货时间
请转人工确认
```

预期：

```python
handoff_required is True
```

不得根据发货周期输出到货时间。

### 13.6 carrier handoff

输入：

```text
SKU001 发什么快递
```

预期回答包含：

```text
当前系统不能自动承诺指定快递
请转人工确认
```

### 13.7 tracking handoff

输入：

```text
物流单号呢
```

预期回答包含：

```text
当前系统未接入订单物流数据
请转人工确认
```

### 13.8 expedite handoff

输入：

```text
SKU001 能加急吗
```

预期回答包含：

```text
当前系统不能自动承诺加急
请转人工确认
```

### 13.9 missing_product_reference

输入：

```text
几天发货
```

预期回答包含：

```text
请先提供 SKU、OEM 对照号或螺纹规格
```

### 13.10 not_found

输入：

```text
SKU999 几天发货
```

预期回答包含：

```text
暂未查到 SKU999 对应的物流基础信息
```

预期：

```python
handoff_required is True
```

### 13.11 ambiguous

输入：

```text
SKU001 和 SKU003 分别几天发货
```

预期回答包含：

```text
识别到多个 SKU
```

预期：

```python
handoff_required is False
```

### 13.12 not_logistics_intent

输入：

```text
SKU001 多少钱
```

预期回答包含：

```text
当前未识别为物流问题
```

预期：

```python
handoff_required is False
```

## 14. 当前结论

`LogisticsAnswerRenderer v0.1` 的核心目标是：

```text
把物流 HandlerResult 转成受控客服回复
只表达发货周期和备货状态
所有高风险物流问题统一转人工
不生成任何 unsupported logistics commitment
```