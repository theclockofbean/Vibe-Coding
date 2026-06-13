# Phase 3-I-H Frontend Answer Strategy Payload Contract v0.1

## 1. 目标

本文档定义前端如何读取后端 response payload 中的 `answer_strategy_*` 字段，用于展示多模块拆分提示、边界说明、安全阻断和人工接管状态。

本阶段只定义字段契约，不修改前端实现。

---

## 2. 字段来源

字段由后端 `state_to_response_payload()` 暴露。

字段同时存在于：

1. response payload 顶层；
2. response payload `metadata` 内部。

前端优先读取顶层字段；如顶层字段不存在，可降级读取 `metadata`。

---

## 3. 前端核心字段

| 字段 | 类型 | 用途 |
|---|---|---|
| `answer_strategy_mode` | string | 回答策略模式 |
| `answer_primary_module` | string/null | 主回答模块 |
| `answer_candidate_modules` | string[] | 候选模块 |
| `answer_boundary_notes` | string[] | 边界说明 |
| `answer_split_required` | boolean | 是否建议拆分问题 |
| `answer_handoff_required` | boolean | 是否建议人工接管 |
| `answer_safety_blocked` | boolean | 是否安全阻断 |
| `answer_forbidden_commitment_detected` | boolean | 是否检测到禁用承诺 |
| `answer_forbidden_fragments` | string[] | 命中的高风险片段 |
| `answer_boundary_note_type` | string/null | 边界说明类型 |
| `answer_strategy_reason` | string | 策略原因 |

---

## 4. answer_strategy_mode 展示规则

### 4.1 `single_primary`

前端正常展示回答内容。

无需额外提示。

### 4.2 `primary_with_boundary_note`

前端正常展示回答内容，并展示 `answer_boundary_notes`。

推荐 UI：

- 主回答区域：展示 `final_response`
- 边界提示区域：展示 `answer_boundary_notes`

### 4.3 `split_required`

前端应突出提示用户拆分问题。

推荐 UI 文案：

> 当前问题包含多个业务方向，请拆分为规格、价格、物流或质量中的一个问题后重新提问。

### 4.4 `safety_blocked`

前端应突出安全阻断和人工确认。

推荐 UI 文案：

> 当前问题涉及高风险业务承诺，不能直接给出确定性答复，请转人工确认。

### 4.5 `handoff_required`

前端应显示人工接管提示。

推荐 UI 文案：

> 当前问题需要人工结合正式数据和业务规则确认。

---

## 5. 模块枚举

`answer_primary_module` 和 `answer_candidate_modules` 可包含：

- `spec`
- `price`
- `logistics`
- `quality`

前端显示名称建议：

| 模块 | 显示名 |
|---|---|
| `spec` | 规格 |
| `price` | 价格 |
| `logistics` | 物流 |
| `quality` | 质量 |

---

## 6. 前端展示优先级

前端推荐按以下优先级展示：

1. `answer_safety_blocked=true`
2. `answer_handoff_required=true`
3. `answer_split_required=true`
4. `answer_strategy_mode=primary_with_boundary_note`
5. `single_primary`

其中 safety blocked 优先级最高，不应被普通回答样式覆盖。

---

## 7. 兼容性要求

前端必须兼容字段缺失。

建议读取方式：

1. 先读 payload 顶层字段；
2. 顶层字段缺失时读取 `payload.metadata`；
3. 两处都缺失时按普通回答处理。

---

## 8. 禁止前端行为

前端不得根据多个模块字段自行拼接业务承诺。

禁止展示或合成：

- 包邮价
- 保证适配
- 明天一定到
- 全网最低
- 一定赔
- 一定补发
- 今天一定发
- 高质量低价

---

## 9. 当前阶段状态

本契约用于 Phase 3-I-H4。

后续阶段可基于本契约进行前端最小展示接入。