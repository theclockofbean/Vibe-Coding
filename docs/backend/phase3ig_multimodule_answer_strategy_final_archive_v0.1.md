# Phase 3-I-G Multi-module Answer Strategy Final Archive v0.1

## 1. 阶段结论

Phase 3-I-G 已完成。

本阶段完成统一 KB 路由后的多模块回答策略、Answer Strategy Helper、Workflow metadata 接入、Renderer Answer Strategy Gate 最小接入，以及历史 E2E 总回归。

最终结论：

- G1 多模块回答行为基线审计通过
- G2 多模块回答融合策略设计文档通过
- G3 多模块回答策略 JSON 机器化通过
- G4 Answer Strategy Helper 独立实现通过
- G5 Answer Strategy 接入 Workflow metadata 通过
- G6 Answer Strategy 与现有 Workflow E2E 回归通过
- G7 Renderer 使用 Answer Strategy metadata 的只读门控设计通过
- G8 Renderer Answer Strategy Gate 最小接入通过
- G9 Renderer Gate 与历史 E2E 总回归通过

---

## 2. 本阶段新增核心能力

### 2.1 Answer Strategy Helper

新增模块：

- `backend/app/agent/answering/__init__.py`
- `backend/app/agent/answering/multimodule_answer_strategy.py`

核心对象：

- `AnswerStrategyDecision`
- `decide_answer_strategy()`

核心 metadata：

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

---

## 3. 多模块回答策略模式

已定义并机器化以下策略：

| Mode | 含义 |
|---|---|
| `single_primary` | 单主模块正常回答 |
| `primary_with_boundary_note` | 主模块回答，并追加边界说明 |
| `split_required` | 不自动融合，提示拆分问题 |
| `safety_blocked` | 阻断高风险承诺，转人工确认 |
| `handoff_required` | 需要人工确认后再答复 |

---

## 4. Renderer Gate 接入点

真实接入点：

- `backend/app/agent/workflow.py`
- `render_node`
- `_run_grounded_render_for_state(new_state)` 之后
- `final_response` 写回 state 之前

新增 helper：

- `_apply_answer_strategy_render_gate`
- `_answer_strategy_safety_response`
- `_answer_strategy_split_response`
- `_append_answer_strategy_boundary_notes`

补充通用 helper：

- `_as_dict`
- `_optional_text`
- `_merge_text_lists`

---

## 5. Renderer Gate 行为

### 5.1 `primary_with_boundary_note`

保留原 grounded final response，并追加：

- `补充边界：...`

不改变 retrieval，不改变 source citation。

### 5.2 `safety_blocked`

覆盖高风险 final response：

- 不输出确定性业务承诺
- 设置 `needs_handoff=True`
- 设置 `is_grounded=False`
- 设置 `used_llm_output=False`
- 设置 `render_mode=answer_strategy_safety_blocked`
- 设置 `render_safety_blocked=True`
- 设置 `render_fallback_reason=answer_strategy_gate`

### 5.3 `split_required`

覆盖 final response 为拆分提示：

- 不自动融合多个模块回答
- 设置 `render_mode=answer_strategy_split_required`

---

## 6. 关键兼容性修复记录

### 6.1 Missing helper 修复

G8 初次接入时，`workflow.py` 中缺少：

- `_as_dict`
- `_optional_text`
- `_merge_text_lists`

已通过 `scripts/fix_phase3ig_render_gate_missing_helpers.py` 修复。

### 6.2 Safety response 文案修复

G8 检查中，`GATE_RENDER_002` 已成功 safety blocked，但安全模板缺少：

- `不能直接给出确定性答复`

已通过 `scripts/fix_phase3ig_render_gate_safety_response_text.py` 修复，统一安全模板表述。

---

## 7. 本阶段新增文档

- `docs/backend/phase3ig_multimodule_answer_strategy_v0.1.md`
- `docs/backend/phase3ig_multimodule_answer_strategy_v0.1.json`
- `docs/backend/phase3ig_renderer_answer_strategy_gate_design_v0.1.md`
- `docs/backend/phase3ig_multimodule_answer_strategy_final_archive_v0.1.md`

---

## 8. 本阶段新增检查脚本

- `backend/scripts/check_phase3ig_multimodule_answer_baseline.py`
- `backend/scripts/check_phase3ig_answer_strategy_doc.py`
- `backend/scripts/check_phase3ig_answer_strategy_json.py`
- `backend/scripts/check_phase3ig_answer_strategy_helper.py`
- `backend/scripts/check_phase3ig_workflow_answer_strategy_metadata.py`
- `backend/scripts/check_phase3ig_answer_strategy_workflow_regression.py`
- `backend/scripts/check_phase3ig_renderer_answer_strategy_gate_design.py`
- `backend/scripts/inspect_phase3ig_renderer_entrypoints.py`
- `backend/scripts/check_phase3ig_answer_strategy_render_gate.py`
- `backend/scripts/check_phase3ig_renderer_gate_total_regression.py`

---

## 9. 阶段性补丁脚本

以下脚本已执行过，仅作历史记录，不应在不了解上下文时重复执行：

- `backend/scripts/patch_workflow_answer_strategy_metadata.py`
- `backend/scripts/patch_workflow_answer_strategy_render_gate.py`
- `backend/scripts/fix_phase3ig_render_gate_missing_helpers.py`
- `backend/scripts/fix_phase3ig_render_gate_safety_response_text.py`

---

## 10. 总回归结果

总回归脚本：

- `backend/scripts/check_phase3ig_renderer_gate_total_regression.py`

覆盖：

- Answer Strategy JSON
- Answer Strategy Helper
- Workflow answer strategy metadata
- Renderer gate design
- Renderer gate runtime
- Answer Strategy workflow regression
- Phase 3-I-F total regression

结果：

- `Phase 3-I-G renderer gate total regression passed`

---

## 11. 当前阶段状态

Phase 3-I-G：完成。

当前系统状态：

- 四类真实 KB 已完成统一路由。
- 多模块冲突已有机器化测试集。
- Workflow 已写入 answer strategy metadata。
- Renderer 已具备最小 answer strategy gate。
- 高风险多模块承诺可被 safety blocked。
- 主模块回答可追加边界说明。
- 历史 E2E 与总回归均通过。

建议下一阶段：

- Phase 3-I-H：多模块拆分提示与前端展示字段优化
- 或 Phase 3-J：前端管理台 / 可观测性 / 测试报告展示