# QualityAnswerRenderer 设计文档 v0.1

## 1. 文档目的

本文档用于固定质量模块中 `QualityAnswerRenderer` 的职责边界、输入输出、回答模板、禁止输出、转人工话术和测试样例。

该文档对应后续实现文件：

```text
backend/app/agent/renderers/quality_answer_renderer.py
```

## 2. 模块定位

`QualityAnswerRenderer` 位于质量问答链路第三步：

```text
用户文本
→ QualityParameterParser
→ QualityHandler
→ QualityAnswerRenderer
```

Renderer 的职责是：

```text
接收 HandlerResult
读取 HandlerResult.facts
根据 handler_status 和 quality_query_type 生成受控 answer_text
保留 source_references
输出 RenderedAnswer
```

Renderer 不负责：

```text
不重新解析自然语言
不查询数据库
不调用 LLM
不修改 HandlerResult
不新增产品事实
不生成质量承诺
不承诺寿命
不承诺防锈
不承诺不掉漆
不承诺质保期限
不承诺退换货
不承诺赔付
不判断质量责任
```

## 3. 输入

输入对象：

```python
HandlerResult
```

关键字段：

```python
status: HandlerStatus
matched_count: int
handoff_required: bool
facts: dict[str, object] | None
errors: list[str]
source_references: list[SourceReference]
```

`facts` 中应包含：

```python
{
    "raw_text": "...",
    "is_quality_intent": True,
    "quality_query_type": "material",
    "product_reference_type": "sku_id",
    "product_reference_value": "SKU001",
    "products": [
        {
            "sku_id": "SKU001",
            "product_name": "铝合金竞技换挡球头",
            "thread_spec": "M8×1.25",
            "oem_reference_number": "43330-39585",
            "material": "铝合金",
            "surface_treatment": "阳极氧化"
        }
    ],
    "quality_commitment_made": False
}
```

## 4. 输出

输出对象：

```python
RenderedAnswer
```

建议字段：

```python
text: str
handoff_required: bool
source_references: list[SourceReference]
```

## 5. success 模板

`success` 仅允许用于：

```text
material
surface_treatment
```

### 5.1 material

条件：

```text
handler_status = success
quality_query_type = material
material_available = true
```

模板：

```text
查到 {sku_id}：{product_name}。该产品登记材质为{material}。该回答仅基于当前已登记的产品信息，不代表额外质量承诺。
```

示例：

```text
查到 SKU001：铝合金竞技换挡球头。该产品登记材质为铝合金。该回答仅基于当前已登记的产品信息，不代表额外质量承诺。
```

### 5.2 surface_treatment

条件：

```text
handler_status = success
quality_query_type = surface_treatment
surface_treatment_available = true
```

模板：

```text
查到 {sku_id}：{product_name}。该产品登记表面处理为{surface_treatment}。该回答仅基于当前已登记的产品信息，不代表防锈、耐刮或不掉漆承诺。
```

示例：

```text
查到 SKU001：铝合金竞技换挡球头。该产品登记表面处理为阳极氧化。该回答仅基于当前已登记的产品信息，不代表防锈、耐刮或不掉漆承诺。
```

## 6. handoff 模板

### 6.1 missing_product_reference

条件：

```text
handler_status = handoff
matched_count = 0
product_reference_value = null
```

模板：

```text
这是质量相关问题，但当前缺少产品引用。请先提供 SKU、OEM 对照号或螺纹规格；如涉及质保、退换、赔付或质量责任，请转人工确认。
```

### 6.2 material 字段缺失

条件：

```text
handler_status = handoff
quality_query_type = material
material_available = false
matched_count > 0
```

模板：

```text
已匹配到 {sku_id}：{product_name}，但当前系统未登记该产品材质信息。请转人工进一步确认。
```

### 6.3 surface_treatment 字段缺失

条件：

```text
handler_status = handoff
quality_query_type = surface_treatment
surface_treatment_available = false
matched_count > 0
```

模板：

```text
已匹配到 {sku_id}：{product_name}，但当前系统未登记该产品表面处理信息。请转人工进一步确认。
```

### 6.4 durability

模板：

```text
查到 {sku_id}：{product_name}。当前系统不能自动承诺产品寿命、耐用年限或长期使用结果，该问题需要结合使用环境、安装方式和实际工况确认。请转人工进一步确认。
```

### 6.5 rust_resistance

模板：

```text
查到 {sku_id}：{product_name}。当前系统不能自动承诺不生锈或绝对防锈；如需确认防锈表现，需要结合材质、表面处理、使用环境和维护方式。请转人工进一步确认。
```

### 6.6 scratch_resistance

模板：

```text
查到 {sku_id}：{product_name}。当前系统不能自动承诺不掉漆、耐刮等级或不磨损；该问题需要结合表面处理、使用环境和实际接触情况确认。请转人工进一步确认。
```

### 6.7 fitment_risk

模板：

```text
查到 {sku_id}：{product_name}。当前质量模块不能单独承诺适配结果；请提供车型、年份、原车螺纹或 OEM 信息，由人工进一步确认。
```

### 6.8 defect_issue

模板：

```text
查到 {sku_id}：{product_name}。该问题涉及疑似瑕疵或使用异常，当前系统不能直接判断责任，也不能自动承诺补发、退换或赔付。请提供订单、图片、视频和安装信息，并转人工处理。
```

### 6.9 warranty

模板：

```text
查到 {sku_id}：{product_name}。当前系统未接入正式质保规则，不能自动承诺质保期限或保修范围。请转人工进一步确认。
```

### 6.10 return_exchange

模板：

```text
查到 {sku_id}：{product_name}。当前系统未接入正式退换货规则，不能自动承诺一定可退或一定可换。请转人工进一步确认。
```

### 6.11 compensation

模板：

```text
查到 {sku_id}：{product_name}。该问题涉及赔付、补偿或补发，当前系统不能自动承诺处理结果。请提供订单、图片、视频和问题说明，并转人工确认。
```

### 6.12 general_quality

模板：

```text
查到 {sku_id}：{product_name}。当前系统不能对产品质量作泛化承诺或主观评价；如需确认具体质量表现，请转人工进一步确认。
```

## 7. not_found 模板

条件：

```text
handler_status = not_found
matched_count = 0
```

模板：

```text
暂未查到 {product_reference_value} 对应的质量基础信息。请核对 SKU、OEM 对照号或螺纹规格；如仍需确认质量问题，请转人工处理。
```

示例：

```text
暂未查到 SKU999 对应的质量基础信息。请核对 SKU、OEM 对照号或螺纹规格；如仍需确认质量问题，请转人工处理。
```

## 8. invalid_request 模板

### 8.1 ambiguous

如果 errors 包含：

```text
multiple SKU IDs found in quality query
```

输出：

```text
识别到多个 SKU，当前质量模块一次只能确认一个产品。请保留一个 SKU 后重新提问。
```

如果 errors 包含：

```text
multiple OEM reference numbers found in quality query
```

输出：

```text
识别到多个 OEM 对照号，当前质量模块一次只能确认一个产品。请保留一个 OEM 对照号后重新提问。
```

如果 errors 包含：

```text
multiple thread specs found in quality query
```

输出：

```text
识别到多个螺纹规格，当前质量模块一次只能确认一个产品范围。请保留一个螺纹规格后重新提问。
```

### 8.2 not_quality_intent

模板：

```text
当前未识别为质量问题，未进入质量处理。
```

## 9. 多产品匹配规则

如果 `thread_spec` 匹配多个产品：

```text
最多展示前 3 个产品
不得根据多个产品作质量比较
不得输出“哪个更好”
不得输出推荐结论
```

模板：

```text
根据该螺纹规格匹配到多个产品，当前仅展示已登记质量基础信息。请提供更明确的 SKU 或 OEM 对照号，以便进一步确认。
```

## 10. source_references 规则

Renderer 不新增 source reference。

规则：

```text
直接透传 HandlerResult.source_references
```

如果 answer_text 使用了产品字段：

```text
source_references 不得为空
```

如果是 missing_product_reference、invalid_request、not_found：

```text
source_references 可以为空
```

## 11. 禁止输出片段

`answer_text` 不得包含：

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

## 12. 允许输出片段

以下受控否定表达允许出现：

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

## 13. v0.1 测试样例

### 13.1 material success

输入：

```text
SKU001 什么材质
```

预期：

```text
handler_status = success
handoff_required = false
answer_text 包含 “登记材质”
answer_text 包含 “不代表额外质量承诺”
```

### 13.2 surface_treatment success

输入：

```text
SKU001 表面怎么处理
```

预期：

```text
handler_status = success
handoff_required = false
answer_text 包含 “登记表面处理”
answer_text 包含 “不代表防锈、耐刮或不掉漆承诺”
```

### 13.3 durability handoff

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

### 13.4 rust_resistance handoff

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

### 13.5 scratch_resistance handoff

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

### 13.6 warranty handoff

输入：

```text
SKU001 质保多久
```

预期：

```text
handler_status = handoff
handoff_required = true
answer_text 包含 “不能自动承诺质保期限”
answer_text 不得包含 “一年质保”
```

### 13.7 return_exchange handoff

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

### 13.8 compensation handoff

输入：

```text
质量问题能赔吗
```

预期：

```text
handler_status = handoff
handoff_required = true
answer_text 不得包含 “一定赔”
```

### 13.9 defect_issue handoff

输入：

```text
SKU001 收到有划痕
```

预期：

```text
handler_status = handoff
handoff_required = true
answer_text 包含 “请提供订单、图片、视频和安装信息”
```

### 13.10 not_found

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

### 13.11 ambiguous

输入：

```text
SKU001 和 SKU003 哪个质量更好
```

预期：

```text
handler_status = invalid_request
handoff_required = false
answer_text 包含 “识别到多个 SKU”
```

### 13.12 not_quality_intent

输入：

```text
SKU001 几天发货
```

预期：

```text
handler_status = invalid_request
handoff_required = false
answer_text 包含 “当前未识别为质量问题”
```

## 14. 当前结论

`QualityAnswerRenderer v0.1` 的核心原则是：

```text
只渲染 HandlerResult 中已有事实
只允许材质、表面处理输出登记信息
所有质量承诺型问题必须输出转人工提示
不得新增事实、不得新增规则、不得新增承诺
```