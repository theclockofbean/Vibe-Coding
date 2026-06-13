# Phase 3-I-G Renderer Answer Strategy Gate Design v0.1

## 1. 目标

本文件定义 renderer 如何只读消费 Answer Strategy metadata。

Phase 3-I-G4/G5 已完成：

- `decide_answer_strategy()`
- Workflow 写入 answer strategy metadata

本阶段目标不是改 renderer，而是先明确 renderer 后续应如何使用这些 metadata，避免多模块问题被错误融合成业务承诺。

---

## 2. Renderer 只读输入字段

renderer 后续可读取以下 metadata：

- `answer_strategy_mode`
- `answer_primary_module`
- `answer_candidate_modules`
- `answer_boundary_notes`
- `answer_split_required`
- `answer_handoff_required`
- `answer_safety_blocked`
- `answer_forbidden_commitment_detected`
- `answer_forbidden_fragments`
- `answer_boundary_note_type`
- `answer_strategy_reason`

这些字段只能用于回答门控，不应替代事实来源。

---

## 3. 门控原则

renderer 必须遵守：

1. LLM 不是事实来源。
2. RAG 不是承诺来源。
3. Answer Strategy metadata 不是事实来源，只是回答策略控制信号。
4. 当 `answer_safety_blocked=true` 时，不允许输出确定性业务承诺。
5. 当 `answer_handoff_required=true` 时，应转人工或提示人工确认。
6. 当 `answer_split_required=true` 时，应提示用户拆分问题。
7. 当 `answer_boundary_notes` 非空时，renderer 可以追加边界说明。
8. 当 `answer_forbidden_commitment_detected=true` 时，应压制高风险表达。
9. renderer 不应自动合并多个模块的完整回答。

---

## 4. 策略模式到 renderer 行为映射

| answer_strategy_mode | renderer 行为 |
|---|---|
| `single_primary` | 正常基于主模块 grounded context 回答 |
| `primary_with_boundary_note` | 回答主模块，并追加简短边界说明 |
| `split_required` | 不融合回答，提示用户拆分问题 |
| `safety_blocked` | 不输出承诺，提示人工确认 |
| `handoff_required` | 转人工或提示人工核验 |

---

## 5. 禁止融合行为

renderer 禁止根据多模块 evidence 拼接出以下类型结论：

- 包邮价
- 适配后马上发
- 高质量低价
- 保证适配且质量没问题
- 今天一定发
- 明天一定到
- 一定赔
- 一定补发
- 最低价给你
- 全网最低

---

## 6. 后续实现建议

后续接入 renderer 时应采用最小侵入方式：

1. 在 grounded render 前读取 `answer_strategy_mode`。
2. 如果 `safety_blocked` 或 `handoff_required`，优先走安全模板。
3. 如果 `split_required`，优先走拆分提示模板。
4. 如果 `primary_with_boundary_note`，保留原主模块回答，但追加 `answer_boundary_notes`。
5. 不改变 retrieval 结果。
6. 不改变 source citation 逻辑。
7. 不允许 answer strategy 自行生成事实。

---

## 7. 当前阶段状态

本文件是 Phase 3-I-G7 设计基线。

下一步：

- 生成只读门控检查脚本；
- 验证当前 Workflow metadata 已满足 renderer 后续接入条件；
- 后续阶段再接入 renderer。