# LogisticsParameterParser 设计文档 v0.1

## 1. 文档目的

本文档用于固定物流模块中 `LogisticsParameterParser` 的输入、输出、识别范围、优先级、歧义规则和测试样例。

该文档对应后续实现文件：

```text
backend/app/agent/parsers/logistics_parameter_parser.py
```

该 parser 只负责从简单用户文本中提取物流相关意图和参数，不负责查询数据库、不负责生成物流承诺。

## 2. 模块定位

`LogisticsParameterParser` 属于 Phase 1 物流模块的第一步。

它的职责是：

```text
用户文本
→ 识别是否属于物流相关问题
→ 提取 SKU / OEM / 螺纹规格 / 数量 / 地区文本
→ 生成结构化 ParsedLogisticsQuery
```

它不负责：

```text
不查询数据库
不判断产品是否存在
不生成发货承诺
不生成到货承诺
不计算运费
不判断是否包邮
不承诺快递公司
不调用 LLM
不写数据库
```

## 3. 输入

### 3.1 输入类型

```python
text: str
```

### 3.2 输入示例

```text
SKU001 几天发货
SKU001 有现货吗
M10*1.5 发货周期多久
43330-39585 什么时候能发
SKU001 发到杭州几天
SKU001 运费多少
SKU001 包邮吗
能发顺丰吗
能加急吗
物流单号呢
```

## 4. 输出结构

`LogisticsParameterParser.parse()` 应输出 `ParsedLogisticsQuery`。

建议字段如下：

```python
@dataclass(frozen=True)
class ParsedLogisticsQuery:
    status: LogisticsParseStatus
    raw_text: str
    is_logistics_intent: bool
    logistics_query_type: LogisticsQueryType | None = None
    product_reference_type: ProductReferenceType | None = None
    product_reference_value: str | None = None
    sku_ids: list[str] = field(default_factory=list)
    quantity: int | None = None
    destination_text: str | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
```

## 5. 状态枚举

### 5.1 LogisticsParseStatus

```python
LogisticsParseStatus = Literal[
    "parsed",
    "not_logistics_intent",
    "missing_product_reference",
    "ambiguous",
]
```

含义：

| 状态                        | 含义                     | 是否进入 LogisticsHandler    |
| ------------------------- | ---------------------- | ------------------------ |
| parsed                    | 已识别物流意图，并提取到可用产品引用     | 是                        |
| not_logistics_intent      | 未识别为物流问题               | 否                        |
| missing_product_reference | 是物流问题，但缺少 SKU/OEM/螺纹规格 | 可进入 Handler，也可直接渲染补充信息提示 |
| ambiguous                 | 识别到多个冲突条件，不能安全处理       | 否                        |

## 6. 物流问题类型

### 6.1 LogisticsQueryType

```python
LogisticsQueryType = Literal[
    "shipping_time",
    "stock_status",
    "shipping_fee",
    "free_shipping",
    "delivery_time",
    "carrier",
    "tracking",
    "expedite",
]
```

说明：

| 类型            | 触发词示例           | v0.1 处理原则          |
| ------------- | --------------- | ------------------ |
| shipping_time | 几天发货、发货周期、什么时候发 | 可进入 Handler 查询发货周期 |
| stock_status  | 有现货吗、有没有货、库存    | 可进入 Handler 查询备货状态 |
| shipping_fee  | 运费、邮费、物流费       | 不承诺具体金额，转人工        |
| free_shipping | 包邮、免运费          | 不承诺包邮，转人工          |
| delivery_time | 几天到、多久到、到货时间    | 不承诺到货时间，转人工        |
| carrier       | 发什么快递、顺丰、圆通     | 不承诺快递公司，转人工        |
| tracking      | 物流单号、快递单号       | 当前不支持，转人工          |
| expedite      | 加急、能不能快点发       | 不承诺加急，转人工          |

## 7. 产品引用类型

### 7.1 ProductReferenceType

```python
ProductReferenceType = Literal[
    "sku_id",
    "sku_ids",
    "oem_reference_number",
    "thread_spec",
]
```

识别规则复用规格模块中的确定性规则：

| 类型                   | 示例                | 标准化                  |
| -------------------- | ----------------- | -------------------- |
| sku_id               | sku1 / SKU001     | SKU001               |
| sku_ids              | SKU001 和 SKU003   | ["SKU001", "SKU003"] |
| oem_reference_number | 43330-39585       | 43330-39585          |
| thread_spec          | M8x1.25 / M10*1.5 | M8×1.25 / M10×1.5    |

## 8. 物流关键词规则

### 8.1 shipping_time 关键词

```text
几天发货
多久发货
什么时候发
发货周期
发货时间
几天能发
什么时候能发
多久能发
```

示例：

| 用户文本               | logistics_query_type |
| ------------------ | -------------------- |
| SKU001 几天发货        | shipping_time        |
| M10*1.5 发货周期多久     | shipping_time        |
| 43330-39585 什么时候能发 | shipping_time        |

### 8.2 stock_status 关键词

```text
有现货吗
有没有现货
现货
有没有货
有货吗
库存
备货
```

示例：

| 用户文本         | logistics_query_type |
| ------------ | -------------------- |
| SKU001 有现货吗  | stock_status         |
| M10*1.5 有没有货 | stock_status         |

### 8.3 shipping_fee 关键词

```text
运费
邮费
物流费
发货费用
配送费
快递费
```

示例：

| 用户文本        | logistics_query_type |
| ----------- | -------------------- |
| SKU001 运费多少 | shipping_fee         |
| 发到杭州邮费多少    | shipping_fee         |

### 8.4 free_shipping 关键词

```text
包邮
免运费
免邮
包不包邮
能包邮吗
```

示例：

| 用户文本       | logistics_query_type |
| ---------- | -------------------- |
| SKU001 包邮吗 | free_shipping        |
| 100 个能包邮吗  | free_shipping        |

### 8.5 delivery_time 关键词

```text
几天到
多久到
什么时候到
到货时间
几天送到
多久送到
发到杭州几天
寄到上海多久
```

示例：

| 用户文本           | logistics_query_type |
| -------------- | -------------------- |
| SKU001 发到杭州几天  | delivery_time        |
| M10*1.5 寄到上海多久 | delivery_time        |

### 8.6 carrier 关键词

```text
发什么快递
什么快递
顺丰
圆通
中通
申通
韵达
德邦
物流公司
快递公司
```

示例：

| 用户文本         | logistics_query_type |
| ------------ | -------------------- |
| SKU001 发什么快递 | carrier              |
| 能发顺丰吗        | carrier              |

### 8.7 tracking 关键词

```text
物流单号
快递单号
单号
查物流
物流信息
快递信息
```

示例：

| 用户文本    | logistics_query_type |
| ------- | -------------------- |
| 物流单号呢   | tracking             |
| 能查快递信息吗 | tracking             |

### 8.8 expedite 关键词

```text
加急
急用
能快点发吗
今天能发吗
马上发
优先发
```

示例：

| 用户文本        | logistics_query_type |
| ----------- | -------------------- |
| SKU001 能加急吗 | expedite             |
| 今天能发吗       | expedite             |

## 9. 物流关键词优先级

当同一句话命中多个物流类型时，按以下优先级确定 `logistics_query_type`：

```text
tracking > expedite > free_shipping > shipping_fee > delivery_time > carrier > stock_status > shipping_time
```

原因：

```text
物流单号、加急、包邮、运费、到货时间都涉及更高风险承诺，应优先进入转人工或受控处理。
```

示例：

| 用户文本              | 命中                            | 输出            |
| ----------------- | ----------------------------- | ------------- |
| SKU001 包邮吗，几天发货   | free_shipping + shipping_time | free_shipping |
| SKU001 运费多少，多久到   | shipping_fee + delivery_time  | shipping_fee  |
| SKU001 有现货吗，今天能发吗 | stock_status + expedite       | expedite      |

## 10. 数量提取规则

### 10.1 支持的数量表达

v0.1 只支持阿拉伯数字数量：

```text
10个
100 个
2件
50只
20套
30pcs
```

### 10.2 数量字段

```python
quantity: int | None
```

### 10.3 示例

| 用户文本             | quantity |
| ---------------- | -------- |
| SKU001 100个运费多少  | 100      |
| M10*1.5 20 个几天发货 | 20       |
| 这个一箱多久发          | None     |

### 10.4 数量限制

parser 只提取数量，不判断数量是否满足起订量，不根据数量推测运费或包邮。

## 11. 地区提取规则

### 11.1 字段

```python
destination_text: str | None
```

### 11.2 支持的简单地区表达

v0.1 只做简单文本提取，不做行政区划校验。

支持模式：

```text
发到杭州
寄到上海
到北京
发浙江
寄广东
送到深圳
```

### 11.3 示例

| 用户文本             | destination_text |
| ---------------- | ---------------- |
| SKU001 发到杭州几天    | 杭州               |
| M10*1.5 寄到上海运费多少 | 上海               |
| 广东能发吗            | 广东               |
| 送到深圳多久           | 深圳               |

### 11.4 不支持情况

以下情况 v0.1 暂不解析或不保证准确：

```text
复杂地址
详细门牌号
多个地区
国外地址
省市区组合拆分
```

示例：

| 用户文本         | destination_text          |
| ------------ | ------------------------- |
| 发到浙江杭州余杭区多少钱 | 浙江杭州余杭区 或 None，v0.1 不做强保证 |
| 杭州和上海分别多久    | ambiguous 或只提取失败          |

## 12. 产品引用优先级

当同一句话中同时出现多种产品引用时，采用以下优先级：

```text
SKU > OEM > 螺纹规格
```

### 12.1 示例

| 用户文本                       | 输出                           |
| -------------------------- | ---------------------------- |
| SKU001 和 43330-39585 几天发货  | 使用 SKU001，warnings 记录 SKU 优先 |
| 43330-39585 和 M8x1.25 发货周期 | 使用 OEM，warnings 记录 OEM 优先    |
| SKU001 M8x1.25 有现货吗        | 使用 SKU001，warnings 记录 SKU 优先 |

### 12.2 warning 示例

```text
SKU ID has priority over OEM reference number
SKU ID has priority over thread spec
OEM reference number has priority over thread spec
```

## 13. 歧义规则

以下情况必须返回 `ambiguous`：

```text
多个 OEM 对照号
多个螺纹规格
多个 SKU
多个地区且语义涉及运费或到货时间
```

### 13.1 多个 SKU

输入：

```text
SKU001 和 SKU003 分别几天发货
```

输出：

```python
status = "ambiguous"
errors = ["multiple SKU IDs found in logistics query"]
```

原因：多个 SKU 可能对应不同备货状态和发货周期，v0.1 不做多 SKU 物流回答。

### 13.2 多个 OEM

输入：

```text
43330-39585 和 12345-67890 运费多少
```

输出：

```python
status = "ambiguous"
errors = ["multiple OEM reference numbers found"]
```

### 13.3 多个螺纹规格

输入：

```text
M8x1.25 和 M10x1.5 几天发货
```

输出：

```python
status = "ambiguous"
errors = ["multiple thread specs found"]
```

### 13.4 多个地区

输入：

```text
SKU001 发杭州和上海分别几天到
```

输出建议：

```python
status = "ambiguous"
errors = ["multiple destinations found in logistics query"]
```

v0.1 可先不实现多个地区识别，但文档中保留该约束。

## 14. 缺少产品引用规则

如果识别到物流意图，但没有 SKU、OEM、螺纹规格，则返回：

```python
status = "missing_product_reference"
is_logistics_intent = True
```

示例：

| 用户文本  | status                    | logistics_query_type |
| ----- | ------------------------- | -------------------- |
| 几天发货  | missing_product_reference | shipping_time        |
| 有现货吗  | missing_product_reference | stock_status         |
| 运费多少  | missing_product_reference | shipping_fee         |
| 包邮吗   | missing_product_reference | free_shipping        |
| 几天到   | missing_product_reference | delivery_time        |
| 发什么快递 | missing_product_reference | carrier              |

建议后续回复：

```text
这类问题涉及物流确认。请先提供 SKU、OEM 对照号或螺纹规格；如果询问运费或到货时间，还需要补充收货地区。
```

## 15. 非物流意图规则

如果文本中没有物流相关关键词，则返回：

```python
status = "not_logistics_intent"
is_logistics_intent = False
```

示例：

| 用户文本        | status               |
| ----------- | -------------------- |
| SKU001 什么规格 | not_logistics_intent |
| SKU001 多少钱  | not_logistics_intent |
| 你好          | not_logistics_intent |

## 16. 禁止行为

`LogisticsParameterParser` 禁止：

```text
禁止查询数据库
禁止判断产品是否存在
禁止输出发货周期
禁止输出备货状态
禁止输出到货时间
禁止输出运费
禁止判断是否包邮
禁止承诺快递公司
禁止承诺加急
禁止调用 LLM
```

## 17. v0.1 测试用例

### 17.1 正常识别

| 用户文本             | status | logistics_query_type | product_reference_type | product_reference_value | quantity | destination_text |
| ---------------- | ------ | -------------------- | ---------------------- | ----------------------- | -------- | ---------------- |
| SKU001 几天发货      | parsed | shipping_time        | sku_id                 | SKU001                  | None     | None             |
| sku1 有现货吗        | parsed | stock_status         | sku_id                 | SKU001                  | None     | None             |
| SKU001 100个几天发货  | parsed | shipping_time        | sku_id                 | SKU001                  | 100      | None             |
| 43330-39585 发货周期 | parsed | shipping_time        | oem_reference_number   | 43330-39585             | None     | None             |
| M10*1.5 运费多少     | parsed | shipping_fee         | thread_spec            | M10×1.5                 | None     | None             |
| SKU001 发到杭州几天    | parsed | delivery_time        | sku_id                 | SKU001                  | None     | 杭州               |
| SKU001 发什么快递     | parsed | carrier              | sku_id                 | SKU001                  | None     | None             |
| SKU001 能加急吗      | parsed | expedite             | sku_id                 | SKU001                  | None     | None             |

### 17.2 缺少产品引用

| 用户文本 | status                    | logistics_query_type |
| ---- | ------------------------- | -------------------- |
| 几天发货 | missing_product_reference | shipping_time        |
| 有现货吗 | missing_product_reference | stock_status         |
| 运费多少 | missing_product_reference | shipping_fee         |
| 包邮吗  | missing_product_reference | free_shipping        |
| 几天到  | missing_product_reference | delivery_time        |

### 17.3 歧义

| 用户文本                           | status    | errors                                    |
| ------------------------------ | --------- | ----------------------------------------- |
| SKU001 和 SKU003 分别几天发货         | ambiguous | multiple SKU IDs found in logistics query |
| 43330-39585 和 12345-67890 运费多少 | ambiguous | multiple OEM reference numbers found      |
| M8x1.25 和 M10x1.5 几天发货         | ambiguous | multiple thread specs found               |

### 17.4 非物流意图

| 用户文本        | status               |
| ----------- | -------------------- |
| SKU001 什么规格 | not_logistics_intent |
| SKU001 多少钱  | not_logistics_intent |
| 你好          | not_logistics_intent |

## 18. 与后续组件的关系

### 18.1 可以进入 LogisticsHandler 的状态

```text
parsed
missing_product_reference
```

### 18.2 不进入 LogisticsHandler 的状态

```text
not_logistics_intent
ambiguous
```

### 18.3 后续 LogisticsHandler 原则

即使 parser 成功，`LogisticsHandler` 也只能：

```text
查询 products 表中的备货状态
查询 products 表中的发货周期
对运费、包邮、到货时间、快递公司、加急、物流单号类问题标记 handoff_required = true
```

不得：

```text
承诺到货时间
承诺包邮
承诺运费
承诺快递公司
承诺加急
```

## 19. 当前结论

`LogisticsParameterParser v0.1` 的核心目标不是物流承诺，而是：

```text
稳定识别物流意图
稳定提取物流查询参数
稳定拒绝歧义输入
为后续受控物流回答准备结构化信息
```

只有后续正式物流规则、地区规则、运费规则、快递规则入库并验证后，物流模块才能升级为更自动化的物流回答。