# Phase 3-H Grounded RenderNode 最终归档文档 v0.1

## 1. 阶段结论

Phase 3-H 已完成 Grounded RenderNode 接入，并通过总回归检查。

当前系统已经从：

```text
结构化 Agent + Qdrant RAG + 可控 LLMClient
```

升级为：

```text
结构化 Agent + Qdrant RAG + 可控 LLMClient + Grounded Final Response
```

Phase 3-H 的核心价值是：最终回答不再只是 `answer_text` 直出，而是经过结构化事实、RAG 安全证据、业务规则、LLM 安全表达与最终风控拦截的统一渲染层。

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

## 2. 阶段边界

Phase 3-H 已完成：

```text
GroundedRenderInput / GroundedRenderOutput
RenderContextBuilder
GroundedRenderer
Workflow RenderNode 接入 GroundedRenderer
response_sources
response_warnings
render_risk_flags
render metadata
final_response 二次安全拦截
render fallback
Phase 3-H total regression
```

Phase 3-H 未做：

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

## 3. 已实现文件

```text
backend/app/agent/rendering/__init__.py
backend/app/agent/rendering/schemas.py
backend/app/agent/rendering/context.py
backend/app/agent/rendering/grounded_renderer.py
backend/app/agent/state.py
backend/app/agent/workflow.py

backend/scripts/check_grounded_render_schemas.py
backend/scripts/check_render_context_builder.py
backend/scripts/check_grounded_renderer.py
backend/scripts/check_workflow_grounded_render_node.py
backend/scripts/check_phase3h_total_regression.py
```

## 4. GroundedRenderInput

核心字段：

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
retrieved_chunks 来自 QdrantRetriever + RAGEvidenceFilter
source_references 来自结构化模块和 RAG
llm_output 来自 LLMNode guarded response
business_rules 来自 GroundedRenderer 内置边界规则
risk_reasons / warnings 来自前序节点
```

## 5. GroundedRenderOutput

核心字段：

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
final_response 必须来自结构化事实、业务规则、安全 RAG 证据或安全模板
response_sources 必须可追踪
used_llm_output 只能在 LLMResponse.is_safe = true 时为 true
needs_handoff 不得被 GroundedRenderer 删除
is_grounded = false 时必须 fallback 或转人工
```

## 6. RenderContextBuilder

实现位置：

```text
backend/app/agent/rendering/context.py
```

核心职责：

```text
从 AgentState 提取 answer_text
从 module_payload 提取 structured_facts
从 retrieved_chunks 提取安全 RAG 证据
从 source_references 提取引用
从 llm_response / llm_output 提取安全表达支持
补充 business_rules
阻止 LLM 成为 fact_source
阻止 LLM 成为 commitment_source
```

已验证：

```text
可提取结构化事实
可过滤 inactive chunk
可过滤 allow_answer_reference = false 的 chunk
可标记 products 为 structured_fact
可标记 rag_chunk 为 supplementary_explanation
可阻止 unsafe LLM output
不会把 llm_output 写入 structured_facts
```

## 7. GroundedRenderer

实现位置：

```text
backend/app/agent/rendering/grounded_renderer.py
```

核心职责：

```text
组织 grounded final_response
保留结构化 answer_text
追加 RAG 补充说明
追加业务边界说明
可选使用安全 LLM 表达支持
生成 response_sources
生成 response_warnings
执行最终二次安全扫描
提供 fallback 输出
```

当前 response_sources 类型：

```text
products
rag_chunk
business_rule
llm_safe_rewrite
```

当前 used_for 类型：

```text
structured_fact
supplementary_explanation
business_boundary
expression_support
```

## 8. Workflow RenderNode 接入

实现位置：

```text
backend/app/agent/workflow.py
```

当前拓扑保持不变：

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

RenderNode 已从：

```text
final_response = answer_text
```

升级为：

```text
RenderContextBuilder.from_state(state)
  ↓
GroundedRenderer.render(render_input)
  ↓
final_response = render_output.final_response
```

RenderNode 写入 AgentState：

```text
render_input
render_output
final_response
response_sources
response_warnings
render_risk_flags
render_used_llm_output
is_grounded_response
```

RenderNode 写入 metadata：

```text
render_mode
render_is_grounded
render_used_llm_output
render_source_count
render_warning_count
render_safety_blocked
render_fallback_reason
```

## 9. 安全策略

GroundedRenderer 会对最终回答进行二次安全扫描。

拦截范围：

```text
明确禁止承诺片段
未授权价格承诺
物流确定性承诺
质量绝对化承诺
售后退换赔付承诺
```

命中风险时：

```text
final_response 替换为安全降级文案
needs_handoff = true
is_grounded = false
metadata.render_safety_blocked = true
risk_flags 写入风险类别
risk_reasons 写入原因
```

安全降级文案：

```text
该问题涉及需要进一步确认的信息。为避免给出未经授权的业务承诺，请转人工结合正式数据和业务规则处理。
```

## 10. Fallback 策略

GroundedRenderer 内部失败时：

```text
不使 workflow 失败
优先保留 answer_text
metadata.render_fallback_reason 非空
render_mode = fallback_answer_text 或 fallback_safe_response
response_warnings 增加 grounded render fallback
```

若 answer_text 为空：

```text
当前信息不足，无法形成可靠答复。请补充 SKU、数量、收货地区或具体问题后转人工确认。
```

Workflow RenderNode 失败时：

```text
不使 workflow 失败
保留 answer_text
answer_text 为空时使用安全兜底文案
handoff_required = true
human_handoff = true
metadata.render_mode = workflow_render_fallback
```

## 11. 已验证场景

检查脚本：

```text
backend/scripts/check_grounded_render_schemas.py
backend/scripts/check_render_context_builder.py
backend/scripts/check_grounded_renderer.py
backend/scripts/check_workflow_grounded_render_node.py
```

已验证：

```text
GroundedRenderInput / GroundedRenderOutput 可序列化
RenderContextBuilder 可提取结构化事实
RenderContextBuilder 不把 LLM 当事实源
GroundedRenderer 可渲染 quality/spec 场景
GroundedRenderer 可渲染 price handoff 场景
价格场景不输出金额
不输出“保证最低价”等禁止承诺
unsafe final_response 会被拦截
空上下文会 fallback
Workflow RenderNode 生成 grounded final_response
Workflow RenderNode 生成 response_sources
Workflow RenderNode 不写 conversation_messages
Workflow RenderNode 不创建 handoff_tickets
Workflow RenderNode error fallback 不使 workflow 失败
```

## 12. 已修复问题

Phase 3-H 中已修复：

```text
GroundedRenderer quality 边界文案行过长导致 Ruff E501
LLMSafetyGuard 对价格安全边界说明误判为 unauthorized_price_commitment
GroundedRenderer price 场景被误拦截
Workflow RenderNode 接入后保持数据库无副作用
```

## 13. Phase 3-H 总回归

总回归脚本：

```text
backend/scripts/check_phase3h_total_regression.py
```

总回归项目：

```text
phase3f_total_regression_with_llm_disabled
llm_client_contract
rule_based_llm_client
llm_safety_guard
grounded_render_schemas
render_context_builder
grounded_renderer
workflow_grounded_render_node
```

最终结果：

```text
phase3-h total regression passed
```

## 14. 当前技术价值

Phase 3-H 已体现以下能力：

```text
Grounded rendering schema 设计
AgentState → RenderContextBuilder → GroundedRenderer 数据链路
结构化事实与 RAG 证据分层
LLM safe expression support
response_sources 可追踪
business_rule source 标记
final_response 二次风控
render fallback
Workflow RenderNode grounded 接入
```

系统当前具备：

```text
结构化业务模块
Qdrant RAG 检索
RAGEvidenceFilter
LLMClient 离线安全层
LLMSafetyGuard
Grounded Final Response
Manual Handoff
Conversation / Session
```

## 15. 当前限制

Phase 3-H v0.1 仍不支持：

```text
真实 LLM API
真实模型路由
OpenAI-compatible client
Prompt template 管理
token 预算管理
上下文裁剪
流式输出
checkpoint
前端引用 UI
复杂多轮引用压缩
Hybrid search / rerank
```

## 16. 后续建议

下一阶段建议二选一：

```text
Phase 3-I-A：真实 LLM API / OpenAI-compatible Client 接入
```

或：

```text
Phase 3-I-B：前端管理台接入 Agent Query + Conversation
```

如果目标是强化技术深度，优先 Phase 3-I-A。
如果目标是尽快形成可展示 Demo，优先 Phase 3-I-B。

推荐 Phase 3-I-B 的原因：

```text
当前后端核心链路已完整
已有 agent/query
已有 conversation/session
已有 handoff ticket
已有 Qdrant RAG
已有 LLMNode
已有 grounded final_response
接前端后能形成完整产品闭环
```

## 17. 最终结论

Phase 3-H 可以归档。

当前系统已完成：

```text
AgentState
LangGraph Workflow
UnifiedTextQAService
Manual Handoff
Conversation / Session
PostgreSQL metadata
QdrantRetriever
RAGEvidenceFilter
LLMClient
LLMSafetyGuard
Grounded RenderNode
Phase 3-H total regression
```

Phase 3-H 为后续真实 LLM API、前端管理台、多渠道客服接入、评测闭环和产品 Demo 打好了基础。