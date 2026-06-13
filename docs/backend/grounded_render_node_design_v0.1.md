# Phase 3-H Grounded RenderNode 设计文档 v0.1

## 1. 文档目的

本文档用于固定 Phase 3-H 中 Grounded RenderNode 的设计目标、组件边界、输入输出契约、证据引用策略、风控策略、LLM 使用边界、降级策略和回归检查范围。

Phase 3-H 的核心目标是：让最终回答不再只是简单复用 `answer_text`，而是基于结构化事实、RAG 证据、业务规则和安全 LLM 改写结果，生成可审计的 grounded final_response。

统一原则：

```text
结构化事实优先。
业务规则优先。
人工确认优先。
RAG 只能作为证据补充。
LLM 只能辅助表达。
LLM 不是事实来源。
RAG 不是承诺来源。
最终回答必须可审计、可追踪、可降级、可拒答。
```

## 2. 当前系统基础

截至 Phase 3-G，系统已具备：

```text
FastAPI backend
PostgreSQL
Qdrant
LangGraph Workflow
AgentState
UnifiedIntentRouter
UnifiedTextQAService
Manual Handoff
Conversation / Session
knowledge_chunks metadata
QdrantRetriever
RAGEvidenceFilter
LLMRequest / LLMResponse
RuleBasedLLMClient
LLMSafetyGuard
Workflow LLMNode
Phase 3-G total regression
```

当前 Workflow 拓扑：

```text
START
  ↓
context
  ↓
intent
  ↓
route
  ↓
handler
  ↓
retrieval
  ↓
llm
  ↓
risk_control
  ↓
render
  ↓
END
```

当前 RenderNode 主要职责是把已有 `answer_text` 写入 `final_response`。Phase 3-H 将升级为 Grounded RenderNode。

## 3. 阶段边界

Phase 3-H v0.1 做：

```text
定义 GroundedRenderInput / GroundedRenderOutput
实现 RenderContextBuilder
提取 structured_facts
提取 RAG evidence references
注入 business_rules
使用 LLM safe rewrite 作为可选表达增强
生成 grounded final_response
生成 response_sources
生成 response_warnings
生成 render metadata
执行最终禁止承诺二次拦截
支持 grounded render fallback
```

Phase 3-H v0.1 不做：

```text
不接真实 LLM API
不实现 streaming
不实现 checkpoint
不实现复杂引用 UI
不实现多轮引用压缩
不实现 hybrid rerank
不实现真实模板后台配置
不让 LLM 独立生成事实
不让 RAG 独立生成承诺
```

## 4. 目标架构

目标数据流：

```text
AgentState
  ↓
RenderContextBuilder
  ↓
GroundedRenderInput
  ↓
GroundedRenderNode
  ↓
LLMSafetyGuard
  ↓
GroundedRenderOutput
  ↓
AgentState.final_response
  ↓
AgentState.source_references / metadata
```

Grounded RenderNode 的定位：

```text
最终回答组织器
引用聚合器
结构化事实渲染器
RAG 证据摘要器
业务规则边界注入器
LLM 安全改写使用者
最终风控拦截器
```

## 5. GroundedRenderInput 设计

建议新增文件：

```text
backend/app/agent/rendering/schemas.py
backend/app/agent/rendering/context.py
backend/app/agent/rendering/grounded_renderer.py
backend/app/agent/rendering/__init__.py
```

GroundedRenderInput 字段：

```text
session_id
user_text
selected_module
handler_status
parse_status
route_status
handoff_required
answer_text
structured_facts
retrieved_chunks
source_references
llm_output
llm_response
business_rules
risk_reasons
warnings
metadata
```

字段来源：

```text
answer_text 来自 UnifiedTextQAService
structured_facts 来自 module_payload
retrieved_chunks 来自 QdrantRetriever + EvidenceFilter
source_references 来自 structured module + RAG
llm_output 来自 LLMNode guarded response
business_rules 来自渲染层内置规则
risk_reasons / warnings 来自前序节点
```

## 6. GroundedRenderOutput 设计

GroundedRenderOutput 字段：

```text
final_response
response_sources
response_warnings
risk_flags
risk_reasons
is_grounded
used_llm_output
needs_handoff
metadata
```

约束：

```text
final_response 必须来自结构化事实、业务规则、RAG 安全证据或安全模板
response_sources 必须可追踪
used_llm_output 只能在 LLMResponse.is_safe = true 时为 true
needs_handoff 不得被 Grounded RenderNode 删除
is_grounded = false 时必须 fallback 或转人工
```

## 7. RenderContextBuilder 设计

RenderContextBuilder 负责从 AgentState 提取 GroundedRenderInput。

核心职责：

```text
提取 answer_text
提取 module_payload 中的结构化事实
提取 retrieved_chunks
提取 source_references
提取 llm_response / llm_output
提取 risk_reasons / warnings
补充 business_rules
判断是否允许使用 llm_output
```

structured_facts 提取策略：

```text
优先使用 module_payload
保留 sku_id / product_reference_value / query_value
保留 parse_status / handler_status
保留 source_references
过滤 None 和空字符串
不把 llm_output 放入 structured_facts
```

RAG evidence 提取策略：

```text
只使用 retrieved_chunks
只使用 allow_answer_reference = true 的 chunk
只显示 doc_title / summary / reference_id
不把 allow_commitment_reference = false 的内容用于承诺
不把高风险 RAG 内容用于承诺
```

## 8. Business Rules 注入

Grounded RenderNode 内置基础规则：

```text
价格类：不能直接报价，需正式价格表或人工确认。
物流类：不能承诺发货、到货、包邮，需结合库存、地址、承运商和人工确认。
质量类：不能承诺不坏、不生锈、不掉漆、耐久年限，需以结构化资料、检测记录或人工确认为准。
售后类：不能承诺退换、质保、赔付、补发，需以正式售后规则或人工确认为准。
RAG：只能作为补充说明来源，不作为业务承诺来源。
LLM：只能辅助表达，不作为事实来源。
```

业务规则输出方式：

```text
高风险场景必须显式提示需人工确认
边界说明应简短，不堆砌
不得泄露内部策略细节
不得输出未授权价格或承诺
```

## 9. LLM safe rewrite 使用策略

LLMNode 当前输出来自 RuleBasedLLMClient + LLMSafetyGuard。

Grounded RenderNode 使用 LLM 输出的条件：

```text
llm_response.is_safe = true
llm_response.error is None
llm_response.metadata.final_response_allowed = false
llm_output 不包含禁止承诺片段
llm_output 只作为表达补充
```

LLM 输出不得：

```text
覆盖 answer_text
覆盖 structured_facts
覆盖 handoff_required
覆盖 risk_reasons
生成新 SKU 信息
生成新价格
生成物流承诺
生成质量承诺
生成售后承诺
```

LLM 输出可以：

```text
辅助总结 RAG 证据
辅助解释为什么需要人工确认
辅助把结构化事实表达得更自然
辅助生成非承诺性说明
```

## 10. Final Response 生成策略

### 10.1 spec 场景

若结构化模块已成功返回规格：

```text
先输出 answer_text
如有 RAG 证据，追加“补充说明”
如有引用，追加“参考来源”
不改变结构化规格事实
```

示例：

```text
查到 SKU001：铝合金竞技换挡球头。螺纹规格为 M8×1.25，杆长 45.00 mm，球径 50.00 mm，锥度为无锥度。材质为铝合金6061，表面处理为阳极氧化黑色。OEM 对照号为 43330-39585。起订量 1 个，备货状态为现货，发货周期约 2 天。

补充说明：铝合金 6061 通常用于轻量化零件，阳极氧化属于常见金属表面处理方式。具体适配、外观和质量结论仍以结构化商品资料、检测记录或人工确认为准。

参考来源：products；RAG: seed_quality_material_6061, seed_quality_anodized_surface。
```

### 10.2 price 场景

若 handler 已要求 handoff：

```text
保留价格模块安全答复
追加人工确认边界
不得输出任何金额
不得使用 RAG 生成价格
```

示例：

```text
这类问题涉及报价。已识别到 SKU：SKU001。当前系统尚未接入正式价格表，不能直接给出报价。请补充采购数量、定制要求和收货地区后转人工确认。

补充说明：价格、折扣、成交价和有效期必须以正式价格表、授权报价或人工确认为准。
```

### 10.3 logistics 场景

若物流问题可解析：

```text
输出结构化物流结果
若无法确认地址、库存或承运商，提示需人工确认
不得承诺今天发、一定到、包邮
```

### 10.4 quality 场景

质量类回答：

```text
只基于结构化资料和 RAG 一般说明
不得输出“质量很好”“放心用”“保证不生锈”等
检测记录缺失时必须提示不能形成质量承诺
```

### 10.5 fallback 场景

若缺少结构化事实且 RAG 证据不足：

```text
不编造答案
返回证据不足说明
必要时 handoff_required = true
```

## 11. Source References 设计

Grounded RenderNode 应保留并增强 source_references。

来源类型：

```text
products
rag_chunk
business_rule
llm_safe_rewrite
```

response_sources 推荐结构：

```text
reference_id
source_type
source_name
doc_title
module
score
used_for
```

used_for 可选值：

```text
structured_fact
supplementary_explanation
business_boundary
safe_rewrite
```

原则：

```text
结构化事实必须引用 products 或业务表
RAG 只能引用为 supplementary_explanation
business_rule 用于边界说明
llm_safe_rewrite 只能标记为 expression_support，不得标记为 fact_source
```

## 12. 风控策略

Grounded RenderNode 必须进行最终二次扫描：

```text
扫描 final_response
扫描 forbidden_commitments
扫描价格承诺
扫描物流确定性承诺
扫描质量绝对化承诺
扫描售后赔付承诺
```

如果命中风险：

```text
final_response 替换为安全降级文案
needs_handoff = true
metadata.render_safety_blocked = true
risk_flags 写入命中类型
risk_reasons 写入原因
```

安全降级模板：

```text
该问题涉及需要进一步确认的信息。为避免给出未经授权的业务承诺，请转人工结合正式数据和业务规则处理。
```

## 13. AgentState 扩展建议

建议新增字段：

```text
render_input
render_output
response_sources
response_warnings
render_risk_flags
render_used_llm_output
is_grounded_response
```

metadata 新增：

```text
render_mode
render_is_grounded
render_used_llm_output
render_source_count
render_warning_count
render_safety_blocked
render_fallback_reason
```

## 14. Workflow 接入策略

Phase 3-H 将替换当前 RenderNode 内部逻辑，不改变拓扑：

```text
START
  ↓
context
  ↓
intent
  ↓
route
  ↓
handler
  ↓
retrieval
  ↓
llm
  ↓
risk_control
  ↓
render
  ↓
END
```

RenderNode 内部从：

```text
final_response = answer_text
```

升级为：

```text
render_input = RenderContextBuilder.from_state(state)
render_output = GroundedRenderer.render(render_input)
final_response = render_output.final_response
```

## 15. 降级策略

Grounded Renderer 失败时：

```text
不使 workflow 失败
保留原 answer_text
metadata.render_fallback_reason 非空
render_mode = fallback_answer_text
response_warnings 增加 grounded render fallback
```

若 answer_text 也为空：

```text
返回安全兜底文案
handoff_required = true
```

兜底文案：

```text
当前信息不足，无法形成可靠答复。请补充 SKU、数量、收货地区或具体问题后转人工确认。
```

## 16. 检查脚本规划

建议新增：

```text
backend/scripts/check_grounded_render_schemas.py
backend/scripts/check_render_context_builder.py
backend/scripts/check_grounded_renderer.py
backend/scripts/check_workflow_grounded_render_node.py
backend/scripts/check_phase3h_total_regression.py
```

## 17. 回归检查范围

### 17.1 schema check

验证：

```text
GroundedRenderInput 字段完整
GroundedRenderOutput 字段完整
to_dict 可序列化
空字段安全降级
```

### 17.2 context builder check

验证：

```text
可从 AgentState 提取 answer_text
可提取 structured_facts
可提取 RAG chunks
可提取 source_references
可提取 llm_output
不会把 LLM 当成 fact_source
```

### 17.3 renderer check

验证：

```text
spec 场景保留结构化 answer_text
price 场景不输出金额
logistics 场景不输出确定性承诺
quality 场景不输出绝对化承诺
RAG 只作为补充说明
LLM 只作为表达辅助
引用来源可追踪
禁止承诺会被二次拦截
```

### 17.4 workflow check

验证：

```text
Workflow RenderNode 生成 grounded final_response
final_response 包含结构化 answer_text
response_sources 非空
render metadata 正确
LLMNode 输出不覆盖结构化事实
RenderNode 不写数据库
RenderNode 不创建 handoff ticket
出错时 fallback 不使 workflow 失败
```

## 18. Phase 3-H 交付目标

完成后应具备：

```text
GroundedRenderInput / GroundedRenderOutput
RenderContextBuilder
GroundedRenderer
Workflow RenderNode grounded rendering
response_sources
response_warnings
render safety guard
render fallback
Phase 3-H total regression
```

## 19. 后续阶段

Phase 3-H 后建议进入：

```text
Phase 3-I：真实 LLM API / OpenAI-compatible Client 接入
```

或者：

```text
Phase 3-I：前端管理台接入 Agent Query + Conversation
```

取决于下一阶段重心是模型能力还是产品 Demo。

## 20. 最终结论

Phase 3-H 的核心目标是让系统最终回答从“模块答复直出”升级为“结构化事实 + RAG 证据 + 业务规则 + LLM 安全表达”的 grounded rendering。

完成后，系统将从：

```text
结构化 Agent + Qdrant RAG + 可控 LLMClient
```

升级为：

```text
结构化 Agent + Qdrant RAG + 可控 LLMClient + Grounded Final Response
```