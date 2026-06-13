# UnifiedTextQAService 设计文档 v0.1

## 1. 文档目的

本文档用于固定 Phase 2 中 `UnifiedTextQAService` 的职责边界、输入输出、模块调度规则、统一响应结构、异常处理规则和测试样例。

对应后续实现文件：

```text
backend/app/agent/services/unified_text_qa_service.py
```

## 2. 模块定位

`UnifiedTextQAService` 位于统一入口链路中间层：

```text
用户文本
→ UnifiedIntentRouter
→ UnifiedTextQAService
→ SpecTextQAService / PriceTextQAService / LogisticsTextQAService / QualityTextQAService
→ UnifiedTextQAResult
```

它负责：

```text
调用 UnifiedIntentRouter
根据 selected_module 调用对应 TextQAService
把不同模块结果转换为统一响应结构
保留原始模块结果 module_payload
处理 ambiguous / unknown / invalid_request
```

它不负责：

```text
不直接查询数据库
不调用 LLM
不绕过 UnifiedIntentRouter
不绕过各模块 TextQAService
不调用底层 Handler / Renderer 生成额外回答
不生成业务承诺
不修改数据库
不合并多个模块回答
```

## 3. 输入

建议输入：

```python
text: str
limit: int = 5
```

字段规则：

```text
text：用户原始问题，1 到 500 字符
limit：默认 5，保留给子模块使用
```

## 4. 输出对象

建议定义：

```python
@dataclass(frozen=True)
class UnifiedTextQAResult:
    route_result: UnifiedIntentResult
    selected_module: str | None
    route_status: str
    parse_status: str
    handler_status: str
    answer_text: str
    handoff_required: bool
    source_references: list[dict[str, object]]
    module_payload: dict[str, object] | None
    warnings: list[str]
    errors: list[str]
```

其中：

```text
route_result：UnifiedIntentRouter 的完整路由结果
selected_module：spec / price / logistics / quality / None
route_status：routed / ambiguous / unknown / invalid_request
parse_status：子模块 parse_status；未进入子模块时等于 route_status
handler_status：子模块 handler_status；未进入子模块时为 invalid_request
answer_text：最终统一回答文本
handoff_required：是否需要人工处理
source_references：来源引用
module_payload：子模块原始响应
warnings：提示信息
errors：错误信息
```

## 5. 统一响应 payload

`UnifiedTextQAResult` 应提供：

```python
def to_response_payload(self) -> dict[str, object]:
    ...
```

统一输出结构：

```json
{
  "selected_module": "quality",
  "route_status": "routed",
  "route_confidence": 0.75,
  "candidate_modules": ["quality"],
  "matched_signals": ["生锈"],
  "parse_status": "parsed",
  "handler_status": "handoff",
  "answer_text": "查到 SKU001：铝合金竞技换挡球头。当前系统不能自动承诺不生锈或绝对防锈；如需确认防锈表现，需要结合材质、表面处理、使用环境和维护方式。请转人工进一步确认。",
  "handoff_required": true,
  "source_references": [
    {
      "source_type": "database_table",
      "source_name": "products",
      "reference_id": "SKU001"
    }
  ],
  "module_payload": {
    "...": "..."
  },
  "warnings": [],
  "errors": []
}
```

## 6. 调度规则

### 6.1 routed

当 `UnifiedIntentRouter.status = routed` 时：

```text
selected_module = spec      → 调用 SpecTextQAService
selected_module = price     → 调用 PriceTextQAService
selected_module = logistics → 调用 LogisticsTextQAService
selected_module = quality   → 调用 QualityTextQAService
```

### 6.2 ambiguous

当 `UnifiedIntentRouter.status = ambiguous` 时：

```text
不调用任何子模块
返回提示用户拆分问题
handoff_required = false
handler_status = invalid_request
```

回答模板：

```text
识别到多个业务问题：{candidate_modules}。当前统一入口 v0.1 不自动合并多个模块回答，请拆分为规格、价格、物流或质量中的一个问题后重新提问。
```

### 6.3 unknown

当 `UnifiedIntentRouter.status = unknown` 时：

```text
不调用任何子模块
handoff_required = false
handler_status = invalid_request
```

回答模板：

```text
当前未识别到可处理的业务问题，请补充 SKU 和具体问题，例如规格、价格、发货或质量。
```

### 6.4 invalid_request

当 `UnifiedIntentRouter.status = invalid_request` 时：

```text
不调用任何子模块
handoff_required = false
handler_status = invalid_request
```

回答模板：

```text
请求内容无效，请输入 1 到 500 字符的问题。
```

## 7. 子模块结果映射

### 7.1 spec 映射

当前 Spec API / Service 结果字段与其他模块不完全一致。

统一映射规则：

```text
selected_module = spec
parse_status = module_payload["parse_status"]
handler_status = "handoff" if handoff_required else "success"
answer_text = module_payload["answer_text"]
handoff_required = module_payload["handoff_required"]
source_references = module_payload["source_references"]
module_payload = 原始 spec payload
```

### 7.2 price 映射

```text
selected_module = price
parse_status = module_payload["parse_status"]
handler_status = module_payload["handler_status"]
answer_text = module_payload["answer_text"]
handoff_required = module_payload["handoff_required"]
source_references = module_payload["source_references"]
module_payload = 原始 price payload
```

### 7.3 logistics 映射

```text
selected_module = logistics
parse_status = module_payload["parse_status"]
handler_status = module_payload["handler_status"]
answer_text = module_payload["answer_text"]
handoff_required = module_payload["handoff_required"]
source_references = module_payload["source_references"]
module_payload = 原始 logistics payload
```

### 7.4 quality 映射

```text
selected_module = quality
parse_status = module_payload["parse_status"]
handler_status = module_payload["handler_status"]
answer_text = module_payload["answer_text"]
handoff_required = module_payload["handoff_required"]
source_references = module_payload["source_references"]
module_payload = 原始 quality payload
```

## 8. 子模块构建依赖

### 8.1 spec

需要：

```text
ProductRepository
SpecQueryService
SpecParameterParser
SpecHandler
SpecAnswerRenderer
SpecTextQAService
```

### 8.2 price

需要：

```text
PriceParameterParser
PriceHandler
PriceAnswerRenderer
PriceTextQAService
```

当前 Price 模块未接入正式价格表，因此价格问题应受控 handoff。

### 8.3 logistics

需要：

```text
ProductRepository
LogisticsTextQAService
```

### 8.4 quality

需要：

```text
ProductRepository
QualityTextQAService
```

## 9. 禁止行为

`UnifiedTextQAService` 禁止：

```text
禁止调用 LLM
禁止直接生成业务承诺
禁止直接查 products 表并绕过子模块
禁止绕过 UnifiedIntentRouter
禁止绕过子模块 TextQAService
禁止跨模块拼接回答
禁止自动报价
禁止承诺到货
禁止承诺包邮
禁止承诺质保
禁止承诺退换
禁止承诺赔付
禁止承诺产品质量表现
```

## 10. 测试样例

### 10.1 spec

输入：

```text
SKU001 螺纹是多少
```

预期：

```text
route_status = routed
selected_module = spec
parse_status = parsed
handler_status = success
handoff_required = false
answer_text 包含 “螺纹规格”
```

### 10.2 price

输入：

```text
SKU001 多少钱
```

预期：

```text
route_status = routed
selected_module = price
parse_status = parsed
handler_status = handoff
handoff_required = true
answer_text 包含 “不能直接给出报价”
```

### 10.3 logistics

输入：

```text
SKU001 几天发货
```

预期：

```text
route_status = routed
selected_module = logistics
parse_status = parsed
handler_status = success
handoff_required = false
answer_text 包含 “发货周期”
answer_text 包含 “不代表到货时间”
```

### 10.4 quality

输入：

```text
SKU001 会不会生锈
```

预期：

```text
route_status = routed
selected_module = quality
parse_status = parsed
handler_status = handoff
handoff_required = true
answer_text 包含 “不能自动承诺不生锈”
```

### 10.5 ambiguous

输入：

```text
SKU001 多少钱，几天发货，质量怎么样
```

预期：

```text
route_status = ambiguous
selected_module = None
handler_status = invalid_request
handoff_required = false
answer_text 包含 “识别到多个业务问题”
```

### 10.6 unknown

输入：

```text
你好
```

预期：

```text
route_status = unknown
selected_module = None
handler_status = invalid_request
handoff_required = false
answer_text 包含 “当前未识别到可处理的业务问题”
```

### 10.7 invalid_request

输入：

```text
"   "
```

预期：

```text
route_status = invalid_request
selected_module = None
handler_status = invalid_request
handoff_required = false
answer_text 包含 “请求内容无效”
```

## 11. 当前结论

`UnifiedTextQAService v0.1` 是统一入口的调度层。

它只做：

```text
统一路由
单模块分发
统一响应包装
异常状态包装
```

它不做：

```text
数据库直查
LLM 生成
业务承诺
跨模块合并回答
```

通过该模块后，可以继续实现：

```text
POST /api/v1/agent/query
```