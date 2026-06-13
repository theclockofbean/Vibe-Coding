# Quality 模块边界设计 v0.1

## 1. 文档目的

本文档用于固定质量模块 v0.1 的职责边界、可回答范围、必须转人工范围、数据来源和禁止行为。

该模块后续对应文件：

```text
backend/app/agent/parsers/quality_parameter_parser.py
backend/app/agent/handlers/quality_handler.py
backend/app/agent/renderers/quality_answer_renderer.py
backend/app/agent/services/quality_text_qa_service.py
backend/app/api/v1/quality.py
```

## 2. 当前阶段定位

Quality 模块属于 Phase 1 本地核心能力的一部分。

当前目标不是自动承诺产品质量、寿命、质保、退换、赔付，而是：

```text
识别质量相关问题
提取产品引用
读取 products 表中已有的结构化产品事实
对高风险质量承诺统一转人工
生成受控回答
```

## 3. 当前可用数据

当前可读取 `products` 表中的字段：

```text
sku_id
product_name
thread_spec
material
surface_treatment
stock_status
lead_time_days
min_order_qty
oem_reference_number
```

其中与质量相关的字段主要是：

```text
material：材质
surface_treatment：表面处理
product_name：产品名称
thread_spec：螺纹规格
```

## 4. 当前不可用数据

当前系统没有正式接入以下数据：

```text
质检报告
检测标准
盐雾测试数据
耐磨测试数据
寿命测试数据
退换货政策细则
质保期限
赔付规则
安装风险规则
车型适配责任规则
客户历史投诉数据
批次质量记录
```

因此系统不得自动生成上述内容。

## 5. 支持识别的问题类型

建议 v0.1 使用以下 `QualityQueryType`：

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

## 6. 可自动回答的问题

### 6.1 material

用户询问材质：

```text
SKU001 什么材质
SKU001 是铝合金吗
这个球头用什么材料
```

允许自动回答：

```text
products.material
```

示例：

```text
查到 SKU001：铝合金竞技换挡球头。该产品登记材质为铝合金。
```

### 6.2 surface_treatment

用户询问表面处理、工艺：

```text
SKU001 表面怎么处理
SKU001 是电镀还是喷砂
这个会不会有表面处理
```

允许自动回答：

```text
products.surface_treatment
```

示例：

```text
查到 SKU001：铝合金竞技换挡球头。该产品登记表面处理为阳极氧化。
```

## 7. 必须转人工的问题

以下问题不得自动承诺，必须转人工或仅给出受控提示。

### 7.1 durability

用户询问是否耐用、能用多久、寿命：

```text
耐用吗
能用几年
会不会很快坏
质量怎么样
```

处理原则：

```text
不能承诺使用寿命
不能承诺不会损坏
可以提示需要结合使用环境、安装方式和实际工况确认
handoff_required = true
```

### 7.2 rust_resistance

用户询问会不会生锈、防锈能力：

```text
会不会生锈
防锈吗
遇水会不会锈
```

处理原则：

```text
不能承诺不生锈
不能承诺绝对防锈
如有 material / surface_treatment，可作为登记信息展示
最终防锈能力需人工确认
handoff_required = true
```

### 7.3 scratch_resistance

用户询问是否耐刮、会不会掉漆、会不会磨损：

```text
会不会掉漆
耐刮吗
会不会磨花
表面容易坏吗
```

处理原则：

```text
不能承诺不掉漆
不能承诺不磨损
不能承诺耐刮等级
handoff_required = true
```

### 7.4 fitment_risk

用户询问适配风险、装不上怎么办：

```text
装不上怎么办
不适配怎么办
买错了怎么办
我的车能不能用
```

处理原则：

```text
不能仅凭质量模块承诺适配
应要求提供车型、年份、原车螺纹或 OEM 信息
handoff_required = true
```

### 7.5 defect_issue

用户反馈瑕疵、破损、异响、松动：

```text
收到有划痕
装上松动
有异响
产品坏了
质量有问题
```

处理原则：

```text
不能直接判责
不能直接承诺赔付或补发
应引导提供订单、图片、视频、安装信息
handoff_required = true
```

### 7.6 warranty

用户询问质保、保修：

```text
质保多久
保修吗
坏了保不保
```

处理原则：

```text
当前无正式质保规则表
不能自动承诺质保期限
handoff_required = true
```

### 7.7 return_exchange

用户询问退换货：

```text
能退吗
能换吗
不合适能不能退
```

处理原则：

```text
当前无正式退换货规则表
不能自动承诺可退可换
handoff_required = true
```

### 7.8 compensation

用户询问赔付、补偿：

```text
坏了赔吗
质量问题怎么赔
能补发吗
```

处理原则：

```text
不能自动承诺赔付
不能自动承诺补发
handoff_required = true
```

## 8. 产品引用规则

Quality 模块复用现有产品引用识别规则：

```text
SKU
OEM 对照号
螺纹规格
```

优先级：

```text
SKU > OEM > 螺纹规格
```

如果没有产品引用：

```text
missing_product_reference
```

如果存在多个 SKU、多个 OEM、多个螺纹规格：

```text
ambiguous
```

## 9. 建议状态枚举

```python
QualityParseStatus = Literal[
    "parsed",
    "not_quality_intent",
    "missing_product_reference",
    "ambiguous",
]
```

Handler 状态继续使用统一的 `HandlerStatus`：

```text
success
handoff
not_found
invalid_request
failed
```

## 10. Handler 处理原则

### 10.1 success

仅以下问题可返回 `success`：

```text
material
surface_treatment
```

前提：

```text
产品引用成功匹配
products 表中存在对应字段
```

### 10.2 handoff

以下问题统一 `handoff_required = true`：

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
```

### 10.3 not_found

产品引用存在，但未匹配 products 表：

```text
not_found
handoff_required = true
```

### 10.4 invalid_request

非质量意图或歧义输入：

```text
invalid_request
handoff_required = false
```

## 11. 回答边界

### 11.1 允许表达

```text
登记材质为……
登记表面处理为……
当前系统只能基于已登记的产品信息回答
该问题涉及质量承诺，需要人工进一步确认
请提供订单、图片、视频或安装信息
```

### 11.2 禁止表达

```text
绝对不会坏
保证不生锈
保证不掉漆
保证耐用几年
终身质保
一年质保
七天无理由
质量问题一定赔
一定补发
一定能退
一定能换
装不上一定负责
```

## 12. SourceReference 规则

如果读取了 `products` 表，应记录：

```python
SourceReference(
    source_type="database_table",
    source_name="products",
    reference_id="SKU001",
)
```

如果没有匹配产品，不添加 source reference。

## 13. v0.1 测试样例

### 13.1 material

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
```

### 13.2 surface_treatment

输入：

```text
SKU001 表面怎么处理
```

预期：

```text
handler_status = success
handoff_required = false
answer_text 包含 “表面处理”
```

### 13.3 durability

输入：

```text
SKU001 耐用吗
```

预期：

```text
handler_status = handoff
handoff_required = true
answer_text 包含 “需要人工进一步确认”
```

### 13.4 rust_resistance

输入：

```text
SKU001 会不会生锈
```

预期：

```text
handler_status = handoff
handoff_required = true
answer_text 不得包含 “保证不生锈”
```

### 13.5 scratch_resistance

输入：

```text
SKU001 会不会掉漆
```

预期：

```text
handler_status = handoff
handoff_required = true
answer_text 不得包含 “保证不掉漆”
```

### 13.6 warranty

输入：

```text
SKU001 质保多久
```

预期：

```text
handler_status = handoff
handoff_required = true
answer_text 不得包含具体质保期限
```

### 13.7 return_exchange

输入：

```text
SKU001 不合适能退吗
```

预期：

```text
handler_status = handoff
handoff_required = true
answer_text 不得承诺一定可退
```

### 13.8 compensation

输入：

```text
质量问题能赔吗
```

预期：

```text
parse_status = missing_product_reference
handler_status = handoff
handoff_required = true
answer_text 不得承诺赔付
```

### 13.9 defect_issue

输入：

```text
SKU001 收到有划痕
```

预期：

```text
handler_status = handoff
handoff_required = true
answer_text 提示提供订单、图片或视频
```

### 13.10 not_quality_intent

输入：

```text
SKU001 几天发货
```

预期：

```text
parse_status = not_quality_intent
handler_status = invalid_request
handoff_required = false
```

## 14. 后续模块规划

后续建议按以下顺序开发：

```text
QualityParameterParser
QualityHandler
QualityAnswerRenderer
QualityTextQAService
POST /api/v1/quality/query
Quality 模块归档文档
```

## 15. 当前结论

Quality 模块 v0.1 的核心原则是：

```text
能从 products 表明确读取的材质、表面处理，可以受控回答
涉及质量承诺、寿命、防锈、掉漆、退换、质保、赔付，必须转人工
所有质量承诺必须等正式规则表和人工验证后再升级
```