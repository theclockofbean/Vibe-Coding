# Phase 3-I-F Unified KB Routing Final Archive v0.1

## 1. 阶段结论

Phase 3-I-F 已完成。

本阶段完成 Quality / Logistics / Price / Spec 四类真实 KB 的统一路由、冲突治理、Workflow 接入、跨模块 E2E 验证和总回归。

最终结论：

- 四类 KB 接入基线审计通过
- 统一路由设计文档通过
- 跨模块冲突测试集文档通过
- 跨模块冲突测试集 JSON 机器化通过
- `route_query_to_kb()` 统一路由辅助函数通过
- Workflow 已接入统一 KB Router
- 跨模块冲突 Workflow E2E 通过
- 四类 KB 总回归通过
- Spec / Price / Logistics / Quality 历史链路均通过

---

## 2. 当前四类真实 KB Collection

| Module | Collection | Source |
|---|---|---|
| quality | `quality_kb_v1` | `real_quality_kb` |
| logistics | `logistics_kb_v1` | `real_logistics_kb` |
| price | `price_kb_v1` | `real_price_kb` |
| spec | `spec_kb_v1` | `real_spec_kb` |

---

## 3. 本阶段新增核心文件

### 3.1 路由模块

- `backend/app/agent/routing/__init__.py`
- `backend/app/agent/routing/unified_kb_router.py`

核心对象：

- `KBRoutingDecision`
- `route_query_to_kb()`

### 3.2 Workflow 接入

- `backend/app/agent/workflow.py`

新增或接入：

- `_apply_unified_kb_routing`
- `_state_current_query_for_unified_kb_routing`
- legacy logistics/spec route override guard

### 3.3 设计与测试集文档

- `docs/backend/phase3if_unified_kb_routing_design_v0.1.md`
- `docs/backend/phase3if_cross_module_conflict_cases_v0.1.md`
- `docs/backend/phase3if_cross_module_conflict_cases_v0.1.json`

### 3.4 检查脚本

- `backend/scripts/check_phase3if_four_kb_baseline.py`
- `backend/scripts/check_phase3if_routing_design_doc.py`
- `backend/scripts/check_phase3if_conflict_cases_doc.py`
- `backend/scripts/check_phase3if_conflict_cases_json.py`
- `backend/scripts/check_phase3if_unified_kb_router.py`
- `backend/scripts/check_phase3if_workflow_unified_router_integration.py`
- `backend/scripts/check_phase3if_conflict_workflow_e2e.py`
- `backend/scripts/check_phase3if_total_regression.py`

### 3.5 阶段性补丁脚本

以下脚本已执行过，仅作历史记录，不应在不了解上下文时重复执行：

- `backend/scripts/patch_workflow_unified_kb_router.py`
- `backend/scripts/fix_phase3if_unified_kb_router_conflict_type.py`
- `backend/scripts/fix_phase3if_unified_kb_router_fitment_priority.py`
- `backend/scripts/fix_phase3if_router_identifier_only_quality_priority.py`
- `backend/scripts/fix_phase3if_router_logistics_delivery_time_signals.py`

---

## 4. 统一路由原则

统一路由遵循：

1. LLM 不是事实来源。
2. RAG 不是承诺来源。
3. 业务承诺只能来自结构化规则、人工确认或明确授权的数据表。
4. 多模块冲突时，优先处理高风险承诺边界。
5. SKU / OEM 单独出现时仅作为 identifier，不应天然压过 Quality / Logistics / Price。
6. 适配、车型、兼容等 fitment 信号优先 Spec。
7. 价格、优惠、报价等风险信号优先 Price。
8. 发货、到货、运费、包邮、赔付、补发等履约信号优先 Logistics。
9. 材质、表面处理、质量、耐用性等说明信号优先 Quality，除非被更高风险承诺覆盖。

---

## 5. 已验证跨模块冲突用例

共 15 个冲突用例，覆盖：

- price + spec
- spec + logistics
- spec + quality
- price + logistics
- logistics + quality
- price + quality
- logistics + spec
- spec + price

已验证：

- `selected_module`
- `conflict_type`
- `retrieval_source`
- `retrieval_collection_name`
- `retrieval_selected_module`
- `retrieval_hit_count`
- top retrieved chunk module / collection

---

## 6. 关键兼容性修复记录

### 6.1 conflict_type 二级模块选择

问题：

- `SKU001` 作为 identifier 时，会把 secondary conflict 错判成 spec。

修复：

- 新增 secondary conflict selection。
- SKU/OEM-only spec signal 被视为 identifier noise。

### 6.2 Fitment 优先级

问题：

- `SKU001适配我的车型吗？今天能发吗？` 曾被 logistics 抢走。

修复：

- 新增 `SPEC_FITMENT_SIGNALS`。
- 命中适配/车型/兼容/装车等信号时，Spec 优先于 Logistics。

### 6.3 Quality 回归兼容

问题：

- Quality 回归用例曾因 `SKU001` 被误路由到 Spec。

修复：

- 当 spec 信号仅为 SKU/OEM identifier，且存在 Quality 信号时，Quality 优先。

### 6.4 Logistics 回归兼容

问题：

- `SKU001发浙江大概几天能到？` 曾因物流时效信号不足被误路由到 Spec。

修复：

- 补充 logistics delivery-time / destination-shipping signals：
  - `几天能到`
  - `几天到`
  - `大概几天`
  - `发到`
  - `发浙江`
  - 其他常见发货目的地信号

---

## 7. 总回归结果

总回归脚本：

- `backend/scripts/check_phase3if_total_regression.py`

覆盖：

- F1 baseline
- F2 routing design doc
- F3 conflict cases doc
- F4 conflict cases JSON
- F5 unified router
- F6 workflow unified router integration
- F7 conflict Workflow E2E
- Spec total regression
- Price total regression
- Logistics total regression
- Quality regression via Logistics / historical checks

结果：

- `Phase 3-I-F total regression passed`

---

## 8. 当前状态

Phase 3-I-F：完成。

当前系统状态：

- 四类真实 KB 已全部接入 Qdrant。
- Workflow 已接入统一路由辅助函数。
- 跨模块冲突有机器化测试集。
- 历史 Spec / Price / Logistics / Quality 链路均回归通过。

建议下一阶段：

- Phase 3-I-G：统一 KB 回答融合策略与多模块拆分提示优化
- 或 Phase 3-J：前端管理台 / 可观测性 / 测试报告展示