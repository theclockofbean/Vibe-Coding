# QualityParameterParser 设计文档 v0.1

## 1. 文档目的

本文档用于固定质量模块中 `QualityParameterParser` 的职责边界、输入输出、质量意图识别规则、产品引用提取规则、歧义处理规则和测试样例。

该文档对应后续实现文件：

```text
backend/app/agent/parsers/quality_parameter_parser.py
```

## 2. 模块定位

`QualityParameterParser` 位于质量问答链路第一步：

```text
用户文本
→ QualityParameterParser
→ QualityHandler
→ QualityAnswerRenderer
```

Parser 的职责是：

```text
识别是否为质量相关问题
识别质量问题类型
提取 SKU / OEM / 螺纹规格
判断是否缺少产品引用
判断是否存在歧义
输出 ParsedQualityQuery
```

Parser 不负责：

```text
不查询数据库
不调用 LLM
不判断产品是否真实存在
不回答质量问题
不承诺质量、寿命、防锈、掉漆、质保、退换、赔付
不生成客服话术
```

## 3. 输入

```python
raw_text: str
```

输入为用户原始文本，例如：

```text
SKU001 什么材质
SKU001 表面怎么处理
SKU001 耐用吗
SKU001 会不会生锈
SKU001 质保多久
质量问题能赔吗
```

## 4. 输出对象

建议定义：

```python
@dataclass(frozen=True)
class ParsedQualityQuery:
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

## 5. 状态枚举

```python
QualityParseStatus = Literal[
    "parsed",
    "not_quality_intent",
    "missing_product_reference",
    "ambiguous",
]
```

状态含义：

```text
parsed：识别为质量问题，且已提取唯一产品引用
not_quality_intent：不是质量问题
missing_product_reference：是质量问题，但缺少 SKU / OEM / 螺纹规格
ambiguous：存在多个 SKU / OEM / 螺纹规格，无法唯一确定产品
```

## 6. 质量问题类型

建议定义：

```python
QualityQueryType = Literal[
    "material",
    "surface_treatment",
    "durability",
    "rust_resistance",
    "scratch_resistance",
    "fitment_risk",
    "defect_issue",
    "warranty",
    "return_exchange",
    "compensation",
    "general_quality",
]
```

## 7. 产品引用类型

复用现有产品引用类型：

```python
ProductReferenceType = Literal[
    "sku_id",
    "oem_reference_number",
    "thread_spec",
]
```

优先级：

```text
SKU > OEM 对照号 > 螺纹规格
```

如果同一句中同时出现 SKU 和 OEM，以 SKU 为主。

如果同一句中出现多个 SKU，直接判定为 `ambiguous`。

如果同一句中无 SKU，但出现多个 OEM，判定为 `ambiguous`。

如果同一句中无 SKU、无 OEM，但出现多个螺纹规格，判定为 `ambiguous`。

## 8. 产品引用提取规则

### 8.1 SKU

匹配格式：

```text
SKU001
SKU123
sku001
```

统一规范化为大写：

```text
SKU001
```

### 8.2 OEM 对照号

匹配格式：

```text
43330-39585
12345-67890
```

保持原始格式。

### 8.3 螺纹规格

匹配格式：

```text
M8x1.25
M8×1.25
M10*1.5
M12X1.25
```

统一规范化：

```text
M8×1.25
M10×1.5
M12×1.25
```

## 9. 质量意图识别规则

### 9.1 material

关键词：

```text
材质
材料
什么材质
什么材料
铝合金
不锈钢
碳钢
塑料
金属
```

示例：

```text
SKU001 什么材质
SKU001 是铝合金吗
这个球头用什么材料
```

### 9.2 surface_treatment

关键词：

```text
表面处理
表面工艺
工艺
电镀
喷砂
阳极氧化
氧化
喷漆
镀铬
抛光
```

示例：

```text
SKU001 表面怎么处理
SKU001 是电镀还是喷砂
这个表面工艺是什么
```

### 9.3 durability

关键词：

```text
耐用
寿命
能用多久
能用几年
容易坏
会不会坏
结实
质量怎么样
质量好吗
```

示例：

```text
SKU001 耐用吗
SKU001 能用几年
SKU001 质量怎么样
```

### 9.4 rust_resistance

关键词：

```text
生锈
防锈
会锈
锈蚀
遇水
腐蚀
```

示例：

```text
SKU001 会不会生锈
SKU001 防锈吗
SKU001 遇水会不会锈
```

### 9.5 scratch_resistance

关键词：

```text
掉漆
掉色
耐刮
划痕
磨花
磨损
刮花
表面容易坏
```

示例：

```text
SKU001 会不会掉漆
SKU001 耐刮吗
SKU001 会不会磨花
```

### 9.6 fitment_risk

关键词：

```text
装不上
不适配
买错
能不能用
适不适合
不合适
车型
年份
```

示例：

```text
SKU001 装不上怎么办
SKU001 不适配怎么办
这个我的车能不能用
```

### 9.7 defect_issue

关键词：

```text
划痕
破损
坏了
松动
异响
瑕疵
裂了
断了
质量问题
收到有问题
```

示例：

```text
SKU001 收到有划痕
SKU001 装上松动
SKU001 有异响
```

### 9.8 warranty

关键词：

```text
质保
保修
保多久
坏了保不保
保不保
```

示例：

```text
SKU001 质保多久
SKU001 保修吗
坏了保不保
```

### 9.9 return_exchange

关键词：

```text
退货
换货
能退
能换
退换
不合适能不能退
不合适能不能换
```

示例：

```text
SKU001 不合适能退吗
SKU001 能换吗
```

### 9.10 compensation

关键词：

```text
赔
赔付
补偿
补发
怎么赔
能不能赔
质量问题能赔吗
```

示例：

```text
质量问题能赔吗
SKU001 坏了赔吗
SKU001 能补发吗
```

### 9.11 general_quality

关键词：

```text
质量
品质
做工
好不好
靠谱吗
稳定吗
```

示例：

```text
SKU001 质量好吗
SKU001 做工怎么样
```

## 10. query_type 优先级

当一句话命中多个质量类型时，按以下优先级选择：

```text
defect_issue
compensation
return_exchange
warranty
fitment_risk
rust_resistance
scratch_resistance
durability
surface_treatment
material
general_quality
```

原因：

```text
售后/异常/赔付类风险最高，应优先进入高风险转人工链路。
材质和表面处理属于可结构化回答问题，优先级低于承诺类问题。
```

示例：

```text
SKU001 质量问题能赔吗
```

应识别为：

```text
compensation
```

示例：

```text
SKU001 收到有划痕能退吗
```

应识别为：

```text
return_exchange
```

## 11. 非质量意图

以下问题不应进入 Quality 模块：

```text
SKU001 几天发货
SKU001 运费多少
SKU001 多少钱
SKU001 起订量多少
SKU001 螺纹是多少
SKU001 有现货吗
```

对应状态：

```text
not_quality_intent
```

## 12. missing_product_reference 规则

如果识别为质量意图，但没有 SKU、OEM 或螺纹规格，应返回：

```python
status = "missing_product_reference"
is_quality_intent = True
product_reference_type = None
product_reference_value = None
errors = ["missing product reference"]
```

示例：

```text
质量怎么样
会不会生锈
质保多久
质量问题能赔吗
```

## 13. ambiguous 规则

### 13.1 多 SKU

输入：

```text
SKU001 和 SKU003 哪个质量更好
```

输出：

```python
status = "ambiguous"
errors = ["multiple SKU IDs found in quality query"]
```

### 13.2 多 OEM

输入：

```text
43330-39585 和 12345-67890 哪个更耐用
```

输出：

```python
status = "ambiguous"
errors = ["multiple OEM reference numbers found in quality query"]
```

### 13.3 多螺纹规格

输入：

```text
M8x1.25 和 M10x1.5 哪个不容易坏
```

输出：

```python
status = "ambiguous"
errors = ["multiple thread specs found in quality query"]
```

## 14. parsed 规则

如果识别为质量意图，且产品引用唯一，则返回：

```python
status = "parsed"
is_quality_intent = True
quality_query_type = ...
product_reference_type = ...
product_reference_value = ...
errors = []
```

示例：

```text
SKU001 什么材质
```

输出：

```python
status = "parsed"
quality_query_type = "material"
product_reference_type = "sku_id"
product_reference_value = "SKU001"
```

## 15. Parser 不做的事

```text
不查 products 表
不判断 SKU 是否存在
不判断材质是否真实
不判断质保政策
不判断是否可退换
不判断是否赔付
不判断质量责任
不判断适配责任
不生成 answer_text
```

## 16. v0.1 测试样例

### 16.1 material

输入：

```text
SKU001 什么材质
```

预期：

```text
status = parsed
quality_query_type = material
product_reference_type = sku_id
product_reference_value = SKU001
```

### 16.2 surface_treatment

输入：

```text
SKU001 表面怎么处理
```

预期：

```text
status = parsed
quality_query_type = surface_treatment
```

### 16.3 durability

输入：

```text
SKU001 耐用吗
```

预期：

```text
status = parsed
quality_query_type = durability
```

### 16.4 rust_resistance

输入：

```text
SKU001 会不会生锈
```

预期：

```text
status = parsed
quality_query_type = rust_resistance
```

### 16.5 scratch_resistance

输入：

```text
SKU001 会不会掉漆
```

预期：

```text
status = parsed
quality_query_type = scratch_resistance
```

### 16.6 warranty

输入：

```text
SKU001 质保多久
```

预期：

```text
status = parsed
quality_query_type = warranty
```

### 16.7 return_exchange

输入：

```text
SKU001 不合适能退吗
```

预期：

```text
status = parsed
quality_query_type = return_exchange
```

### 16.8 compensation missing reference

输入：

```text
质量问题能赔吗
```

预期：

```text
status = missing_product_reference
quality_query_type = compensation
```

### 16.9 defect_issue

输入：

```text
SKU001 收到有划痕
```

预期：

```text
status = parsed
quality_query_type = defect_issue
```

### 16.10 general_quality

输入：

```text
SKU001 质量怎么样
```

预期：

```text
status = parsed
quality_query_type = durability
```

说明：

```text
“质量怎么样”在 v0.1 中按 durability / general_quality 边界处理均可，但建议优先映射为 durability，因为它属于质量承诺类问题，后续 Handler 必须转人工。
```

### 16.11 not_quality_intent

输入：

```text
SKU001 几天发货
```

预期：

```text
status = not_quality_intent
is_quality_intent = False
quality_query_type = None
```

### 16.12 多 SKU 歧义

输入：

```text
SKU001 和 SKU003 哪个质量更好
```

预期：

```text
status = ambiguous
sku_ids = ["SKU001", "SKU003"]
errors contains "multiple SKU IDs found in quality query"
```

## 17. 当前结论

`QualityParameterParser v0.1` 的核心原则是：

```text
只做质量意图识别和参数提取
只提取产品引用，不判断产品事实
把质量承诺型问题识别出来，但不回答
为 Handler 的 success / handoff / invalid_request 提供稳定结构化输入
```