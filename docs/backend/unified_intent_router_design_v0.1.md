# UnifiedIntentRouter 设计文档 v0.1

## 1. 文档目的

本文档用于固定 Phase 2 中 `UnifiedIntentRouter` 的职责边界、输入输出、模块选择规则、歧义处理规则、禁止行为和测试样例。

对应后续实现文件：

```text
backend/app/agent/routers/unified_intent_router.py
```

## 2. Phase 2 目标

Phase 2 的目标是在 Phase 1 四个垂直模块之上增加统一入口。

Phase 1 已完成：

```text
POST /api/v1/spec/query
POST /api/v1/price/query
POST /api/v1/logistics/query
POST /api/v1/quality/query
```

Phase 2 计划新增：

```text
POST /api/v1/agent/query
```

统一入口链路：

```text
用户文本
→ UnifiedIntentRouter
→ UnifiedTextQAService
→ 对应模块 TextQAService
→ 统一 API Response
```

## 3. UnifiedIntentRouter 定位

`UnifiedIntentRouter` 只负责判断用户问题应进入哪个模块。

它不负责回答问题。

它的职责是：

```text
识别用户文本所属业务模块
输出 selected_module
输出 confidence
输出 matched_signals
输出 warnings / errors
识别跨模块歧义
识别未知意图
```

它不负责：

```text
不查询数据库
不调用 LLM
不调用 Handler
不调用 Renderer
不生成 answer_text
不生成客服话术
不承诺价格
不承诺库存
不承诺物流
不承诺质量
不判断售后责任
不修改任何数据
```

## 4. 支持模块

v0.1 支持四个模块：

```text
spec
price
logistics
quality
```

模块含义：

```text
spec：规格、参数、材质、尺寸、螺纹、OEM 对照号、产品基础信息
price：价格、报价、多少钱、折扣、批发价、起订价格、含税、付款条件
logistics：发货、库存、现货、到货、运费、包邮、快递、物流、追踪、加急
quality：质量、耐用、防锈、掉漆、质保、退换、赔付、瑕疵、坏了、划痕
```

## 5. 输入

输入对象建议：

```python
@dataclass(frozen=True)
class UnifiedIntentInput:
    text: str
```

字段限制：

```text
text：必填，1 到 500 字符
```

## 6. 输出

输出对象建议：

```python
@dataclass(frozen=True)
class UnifiedIntentResult:
    raw_text: str
    normalized_text: str
    selected_module: str | None
    status: str
    confidence: float
    matched_signals: list[str]
    candidate_modules: list[str]
    warnings: list[str]
    errors: list[str]
```

字段说明：

```text
raw_text：原始用户文本
normalized_text：归一化后的文本
selected_module：最终选择模块，可能为 spec / price / logistics / quality / None
status：routed / ambiguous / unknown / invalid_request
confidence：0 到 1 的置信度
matched_signals：命中的关键词或规则
candidate_modules：候选模块
warnings：非阻断提示
errors：阻断错误
```

## 7. 状态定义

### 7.1 routed

表示成功选择唯一模块。

示例：

```text
SKU001 多少钱
→ selected_module = price
status = routed
```

### 7.2 ambiguous

表示命中了多个模块，且无法安全决定唯一模块。

示例：

```text
SKU001 多少钱，质量怎么样，几天发货
→ candidate_modules = ["price", "quality", "logistics"]
→ selected_module = None
→ status = ambiguous
```

### 7.3 unknown

表示未识别到任何支持模块意图。

示例：

```text
你好
→ selected_module = None
→ status = unknown
```

### 7.4 invalid_request

表示输入为空、空白或不符合基本限制。

示例：

```text
"   "
→ selected_module = None
→ status = invalid_request
```

## 8. 关键词信号

### 8.1 price signals

```text
价格
报价
多少钱
多少元
单价
批发价
优惠
折扣
便宜
最低价
含税
税点
付款
账期
采购价
大货价
```

### 8.2 logistics signals

```text
发货
几天发
多久发
现货
库存
有货
缺货
到货
几天到
运费
邮费
包邮
快递
物流
承运商
单号
追踪
加急
当天发
```

### 8.3 quality signals

```text
质量
品质
做工
耐用
容易坏
会不会坏
防锈
生锈
掉漆
耐刮
划痕
瑕疵
破损
异响
松动
质保
保修
退货
换货
退换
赔付
补偿
补发
责任
```

### 8.4 spec signals

```text
规格
参数
尺寸
大小
多大
螺纹
牙距
M8
M10
材质
材料
表面处理
颜色
杆长
球径
锥度
OEM
对照号
适配
型号
SKU
产品信息
```

## 9. 模块优先级规则

当只命中一个模块时，直接选择该模块。

当命中多个模块时，v0.1 不轻易自动合并回答。

### 9.1 明确多诉求

如果用户同时提出多个业务问题，返回 ambiguous。

示例：

```text
SKU001 多少钱，几天发货，质量怎么样
```

结果：

```text
status = ambiguous
candidate_modules = ["price", "logistics", "quality"]
selected_module = None
```

原因：

```text
该问题需要拆分为多个模块处理，v0.1 不自动跨模块合并回答。
```

### 9.2 price 优先场景

如果文本中价格信号明确，并且其他信号只是产品定位信息，则选择 price。

示例：

```text
SKU001 铝合金的多少钱
```

解释：

```text
“铝合金”在这里是产品描述，不是质量问题。
```

结果：

```text
selected_module = price
```

### 9.3 logistics 优先场景

如果文本中物流信号明确，并且其他信号只是产品定位信息，则选择 logistics。

示例：

```text
SKU001 铝合金款几天发货
```

结果：

```text
selected_module = logistics
```

### 9.4 quality 优先场景

如果文本中质量、售后、责任、质保、退换、赔付信号明确，则选择 quality。

示例：

```text
SKU001 掉漆能退吗
```

结果：

```text
selected_module = quality
```

### 9.5 spec 默认场景

如果只命中产品参数、规格、材质、尺寸、螺纹、OEM 等基础信息，则选择 spec。

示例：

```text
SKU001 螺纹是多少
```

结果：

```text
selected_module = spec
```

## 10. 材质归属规则

`材质` 是一个特殊词。

默认：

```text
“什么材质”
“材质是什么”
“SKU001 是什么材料”
```

归入：

```text
spec
```

如果同时出现质量承诺词：

```text
铝合金材质耐用吗
这个材质会不会生锈
这个材质容易坏吗
```

归入：

```text
quality
```

原因：

```text
用户不是单纯问登记材质，而是在问材质带来的质量表现或风险。
```

## 11. 退换与赔付归属规则

以下问题统一归入 quality：

```text
能退吗
能换吗
可以退换吗
质量问题能赔吗
坏了能赔吗
有划痕能补发吗
装不上谁负责
```

即使其中包含物流或价格词，也应优先识别为 quality 或 ambiguous。

示例：

```text
SKU001 发过来有划痕能赔吗
```

结果：

```text
selected_module = quality
```

## 12. 未知意图

如果文本不包含任何模块信号：

```text
你好
这个怎么样
帮我看看
```

结果：

```text
status = unknown
selected_module = None
```

后续 UnifiedTextQAService 可返回：

```text
当前未识别到可处理的业务问题，请补充 SKU 和具体问题，例如规格、价格、发货或质量。
```

## 13. invalid_request

以下情况为 invalid_request：

```text
空字符串
纯空白
超过 500 字符
```

## 14. v0.1 测试样例

### 14.1 spec

输入：

```text
SKU001 螺纹是多少
```

预期：

```text
status = routed
selected_module = spec
confidence >= 0.7
matched_signals 包含 “螺纹”
```

### 14.2 price

输入：

```text
SKU001 多少钱
```

预期：

```text
status = routed
selected_module = price
confidence >= 0.7
matched_signals 包含 “多少钱”
```

### 14.3 logistics

输入：

```text
SKU001 几天发货
```

预期：

```text
status = routed
selected_module = logistics
confidence >= 0.7
matched_signals 包含 “发货”
```

### 14.4 quality

输入：

```text
SKU001 会不会生锈
```

预期：

```text
status = routed
selected_module = quality
confidence >= 0.7
matched_signals 包含 “生锈”
```

### 14.5 material as spec

输入：

```text
SKU001 什么材质
```

预期：

```text
status = routed
selected_module = spec
matched_signals 包含 “材质”
```

### 14.6 material as quality

输入：

```text
SKU001 这个材质耐用吗
```

预期：

```text
status = routed
selected_module = quality
matched_signals 包含 “材质”
matched_signals 包含 “耐用”
```

### 14.7 ambiguous

输入：

```text
SKU001 多少钱，几天发货，质量怎么样
```

预期：

```text
status = ambiguous
selected_module = None
candidate_modules 包含 price
candidate_modules 包含 logistics
candidate_modules 包含 quality
```

### 14.8 unknown

输入：

```text
你好
```

预期：

```text
status = unknown
selected_module = None
```

### 14.9 invalid_request

输入：

```text
"   "
```

预期：

```text
status = invalid_request
selected_module = None
```

## 15. 禁止行为

UnifiedIntentRouter 禁止：

```text
禁止回答用户问题
禁止生成 answer_text
禁止查询 products 表
禁止调用 LLM
禁止调用任何模块 Handler
禁止调用任何模块 Renderer
禁止承诺价格
禁止承诺发货
禁止承诺物流
禁止承诺质量
禁止承诺退换
禁止承诺赔付
```

## 16. 当前结论

`UnifiedIntentRouter v0.1` 是 Phase 2 的第一层基础能力。

它只做：

```text
统一意图识别
模块选择
歧义识别
未知意图识别
```

它不做：

```text
业务回答
数据库查询
规则承诺
跨模块合并回答
```

通过该模块后，才能继续实现：

```text
UnifiedTextQAService
POST /api/v1/agent/query
跨模块统一响应
```
