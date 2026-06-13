# Phase 3-I-G Multi-module Answer Strategy v0.1

## 1. 目标

Phase 3-I-G 的目标是优化统一 KB 路由后的多模块回答策略。

Phase 3-I-F 已完成四类真实 KB 的统一路由与冲突治理：

- Quality
- Logistics
- Price
- Spec

但当前回答层仍以单主模块为主。当用户问题同时包含多个业务意图时，需要明确：

- 什么时候只回答主模块；
- 什么时候提示拆分问题；
- 什么时候允许补充次模块边界说明；
- 什么时候必须转人工；
- 什么时候禁止融合回答。

---

## 2. 总原则

多模块回答策略必须遵守：

1. LLM 不是事实来源。
2. RAG 不是承诺来源。
3. 业务承诺只能来自结构化规则、人工确认或明确授权的数据表。
4. 多模块问题默认不自动合并为完整业务承诺。
5. 高风险承诺优先触发安全边界。
6. 次模块信息只能作为“补充说明”或“需要补充的信息”，不能形成承诺。
7. 价格、运费、赔付、适配、寿命、质量保证等风险内容不得由 RAG 自行承诺。

---

## 3. 多模块回答模式

### 3.1 single_primary

适用场景：

- 用户问题虽然命中多个模块，但只有一个明显主问题；
- 其他模块只是 SKU/OEM 标识符或弱背景信息。

示例：

- `SKU001是不是不锈钢，能不能优惠？`
  - 主模块：Price
  - Quality 信息只作为背景，不应抢主路由。

策略：

- 回答主模块；
- 不主动展开次模块；
- 如需要次模块事实，提示用户拆分提问或补充信息。

### 3.2 primary_with_boundary_note

适用场景：

- 用户问题有明确主模块；
- 次模块涉及风险边界；
- 可以补充一句边界说明，但不能扩展为完整回答。

示例：

- `SKU001多少钱，螺纹是什么规格？`
  - 主模块：Price
  - Spec 作为补充字段，不构成报价依据。

策略：

- 按 Price 处理报价流程；
- 补充说明“规格信息需以 SKU 主数据核对为准”；
- 不直接报价。

### 3.3 split_required

适用场景：

- 用户同时提出多个并列业务问题；
- 没有单一安全主线；
- 自动融合会制造承诺风险。

示例：

- `这个球头质量怎么样，多少钱，明天能到吗？`

策略：

- 不自动融合回答；
- 提示用户拆分为规格、价格、物流或质量中的一个问题；
- 可说明当前识别到的模块列表。

### 3.4 safety_blocked

适用场景：

- 问题包含高风险承诺：
  - 最低价
  - 一定包邮
  - 明天一定到
  - 万能适配
  - 保证适配
  - 永不生锈
  - 十万公里
  - 一定赔
  - 一定补发

策略：

- 不给确定性承诺；
- 引导人工确认；
- 可说明需要补充的信息。

### 3.5 handoff_required

适用场景：

- 涉及金额、赔付、兼容性确认、售后责任边界；
- KB 中没有足够授权依据；
- 需要人工核算或判断。

策略：

- 明确转人工；
- 不输出承诺；
- 保留已识别模块和风险标签。

---

## 4. 模块融合优先级

| selected_module | candidate_modules | recommended_mode |
|---|---|---|
| price | price + spec | primary_with_boundary_note |
| price | price + quality | primary_with_boundary_note |
| price | price + logistics | safety_blocked |
| spec | spec + logistics | primary_with_boundary_note |
| spec | spec + quality | primary_with_boundary_note |
| spec | spec + price | safety_blocked |
| logistics | logistics + quality | primary_with_boundary_note |
| logistics | logistics + spec | primary_with_boundary_note |
| logistics | logistics + price | safety_blocked |
| quality | quality only | single_primary |

---

## 5. 输出字段建议

后续 renderer / workflow 可增加以下 metadata：

- `answer_strategy_mode`
- `answer_primary_module`
- `answer_candidate_modules`
- `answer_boundary_notes`
- `answer_split_required`
- `answer_handoff_required`
- `answer_safety_blocked`
- `answer_forbidden_commitment_detected`

---

## 6. 禁止行为

多模块融合阶段禁止：

- 把 Price + Logistics 合并成“包邮价”；
- 把 Spec + Logistics 合并成“适配后马上发”；
- 把 Quality + Price 合并成“高质量低价”；
- 把 Logistics + Quality 合并成“一定赔/一定补发”；
- 把 Spec + Quality 合并成“保证适配且质量没问题”；
- 输出任何未经授权金额、时效、适配、寿命、赔付承诺。

---

## 7. 当前阶段状态

本文件是 Phase 3-I-G2 设计基线。

下一步：

- 将多模块回答策略机器化；
- 生成 answer strategy helper；
- 接入 Workflow / renderer 前先做独立检查。