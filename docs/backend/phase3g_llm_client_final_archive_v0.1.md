# Phase 3-G LLMClient 接入最终归档文档 v0.1

## 1. 阶段结论

Phase 3-G 已完成 LLMClient 接入基础层，并通过总回归检查。

当前系统已经从：

```text
结构化 Agent + Qdrant RAG
```

升级为：

```text
结构化 Agent + Qdrant RAG + 可控 LLMClient
```

Phase 3-G 的核心目标不是让 LLM 接管回答，而是建立一个可替换、可测试、可降级、不可越权成为事实源或承诺源的大模型调用层。

统一原则：

```text
LLM 是语言生成工具，不是事实来源。
LLM 不得替代结构化数据。
LLM 不得替代业务规则。
LLM 不得生成价格、库存、物流、质量、售后承诺。
RAG 是证据补充，不是承诺来源。
最终业务回答必须可审计、可降级、可拒答。
```

## 2. 阶段边界

Phase 3-G 已完成：

```text
LLMRequest / LLMResponse schema
LLMClient Protocol
EchoLLMClient
RuleBasedLLMClient
LLMSafetyGuard
Workflow LLMNode
LLMNode enabled / disabled 分支
LLMNode error fallback
Phase 3-G total regression
```

Phase 3-G 明确未做：

```text
不接真实 OpenAI / Claude / Qwen API
不读取 API key
不调用外部 LLM 服务
不让 LLM 输出直接成为 final_response
不实现 Grounded RenderNode
不实现流式输出
不实现 checkpoint
不实现真实模型路由
```

## 3. 已实现文件

### 3.1 LLM 包

```text
backend/app/agent/llm/__init__.py
backend/app/agent/llm/schemas.py
backend/app/agent/llm/client.py
backend/app/agent/llm/safety.py
```

### 3.2 AgentState / Workflow

```text
backend/app/agent/state.py
backend/app/agent/workflow.py
```

### 3.3 检查脚本

```text
backend/scripts/check_llm_client_contract.py
backend/scripts/check_rule_based_llm_client.py
backend/scripts/check_llm_safety_guard.py
backend/scripts/check_workflow_llm_node.py
backend/scripts/check_phase3g_total_regression.py
```

## 4. LLM schema

### 4.1 LLMRequest

核心字段：

```text
request_id
task_type
user_text
system_instruction
developer_instruction
context_blocks
retrieved_chunks
structured_facts
business_rules
forbidden_commitments
temperature
max_tokens
metadata
```

LLMRequest 负责把 LLM 调用输入结构化，并显式注入安全边界。

支持的 task_type：

```text
rewrite_safe_answer
summarize_evidence
draft_handoff_note
classify_answer_risk
echo_test
rule_based_test
```

禁止的 task_type：

```text
freeform_final_answer
price_generation
logistics_commitment_generation
quality_guarantee_generation
aftersale_commitment_generation
```

禁止这些 task_type 的原因是：当前阶段不允许 LLM 自由生成最终答案，也不允许 LLM 生成任何价格、物流、质量、售后承诺。

### 4.2 LLMResponse

核心字段：

```text
request_id
provider
model
content
finish_reason
usage
latency_ms
safety_flags
is_safe
needs_handoff
metadata
error
```

约束：

```text
content 不是 final_response
is_safe = false 时不得进入最终渲染
needs_handoff = true 时应进入人工接管或拒答链路
error 非空时 workflow 应安全降级
```

## 5. LLMClient Protocol

核心接口：

```text
generate(request: LLMRequest) -> LLMResponse
```

设计要求：

```text
输入必须结构化
输出必须结构化
异常必须可捕获
响应必须带 provider / model / latency metadata
不得直接写数据库
不得直接修改 AgentState
不得直接生成 final_response
```

## 6. EchoLLMClient

实现位置：

```text
backend/app/agent/llm/client.py
```

用途：

```text
验证 LLMClient contract
验证 request / response schema
验证 workflow 接线
验证安全拒绝链路
```

默认标识：

```text
provider = local
model = echo-llm-v1
```

行为：

```text
安全输入：返回 echo 内容
命中禁止承诺：返回 is_safe = false, needs_handoff = true
```

## 7. RuleBasedLLMClient

实现位置：

```text
backend/app/agent/llm/client.py
```

用途：

```text
离线验证 LLMClient 行为
离线验证安全规则
离线验证 fallback
离线验证不可成为事实源
```

默认标识：

```text
provider = local
model = rule-based-llm-v1
```

已支持任务：

```text
echo_test
rewrite_safe_answer
summarize_evidence
draft_handoff_note
classify_answer_risk
rule_based_test
```

关键约束：

```text
final_response_allowed = false
fact_source_allowed = false
commitment_source_allowed = false
```

## 8. LLMSafetyGuard

实现位置：

```text
backend/app/agent/llm/safety.py
```

核心对象：

```text
LLMSafetyGuard
LLMSafetyResult
```

核心能力：

```text
evaluate_text()
evaluate_response()
guard_response()
```

检查范围：

```text
明确禁止承诺片段
未授权价格承诺
物流确定性承诺
质量绝对化承诺
售后退换赔付承诺
LLMClient 自身 unsafe 标记
LLMClient needs_handoff 标记
LLMResponse error
```

禁止承诺片段：

```text
保证最低价
最低价给你
一定包邮
保证到货
今天一定发
保证不坏
保证不生锈
保证不掉漆
保证耐用
能用几年
一年质保
终身质保
七天无理由
一定能退
一定能换
一定赔
一定补发
质量很好
放心用
完全没问题
```

风险类别：

```text
forbidden_commitment
unauthorized_price_commitment
logistics_commitment
quality_commitment
aftersale_commitment
client_marked_unsafe
client_needs_handoff
llm_error
```

LLMSafetyGuard 的输出永远不会授权 LLM 成为事实源或承诺源。

## 9. AgentState 扩展

Phase 3-G 为 AgentState 增加了 LLM 字段：

```text
llm_request
llm_response
llm_output
llm_safety_flags
llm_used
llm_error
```

这些字段用于记录 LLM 调用结果，但不影响结构化模块的主回答。

## 10. Workflow LLMNode

实现位置：

```text
backend/app/agent/workflow.py
```

当前拓扑：

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

LLMNode 当前行为：

```text
使用 RuleBasedLLMClient
使用 LLMSafetyGuard 包装响应
写入 AgentState.llm_request
写入 AgentState.llm_response
写入 AgentState.llm_output
写入 AgentState.llm_safety_flags
写入 metadata.llm_*
不修改 answer_text
不修改 final_response
不修改 handoff_required
不创建 handoff ticket
不写 conversation_messages
```

## 11. LLMNode 开关

环境变量：

```text
AGENT_LLM_NODE_ENABLED
```

含义：

```text
1 / true / yes / on：启用 LLMNode
0 / false / no / off：禁用 LLMNode
```

禁用时：

```text
metadata["llm_enabled"] = false
metadata["llm_used"] = false
metadata["llm_fallback_reason"] = "llm_node_disabled"
```

## 12. LLMNode 错误回归开关

环境变量：

```text
AGENT_LLM_FORCE_ERROR
```

含义：

```text
1：强制 LLMNode 抛出错误，用于验证 workflow 不失败
```

错误时：

```text
llm_used = false
llm_error 非空
metadata["llm_fallback_reason"] = "llm_node_error"
final_response 保持不变
```

## 13. Workflow LLMNode 已验证能力

检查脚本：

```text
backend/scripts/check_workflow_llm_node.py
```

验证项：

```text
LLMNode 成功路径
LLMNode handoff task 路径
LLMNode error fallback 路径
LLMNode disabled 路径
LLMNode 不写 conversation_messages
LLMNode 不创建 handoff_tickets
LLMNode 不改 final_response
LLMNode 输出不包含禁止承诺片段
```

典型 metadata：

```text
llm_enabled
llm_used
llm_provider
llm_model
llm_task_type
llm_latency_ms
llm_is_safe
llm_needs_handoff
llm_fallback_reason
llm_error
```

## 14. Phase 3-G 总回归

总回归脚本：

```text
backend/scripts/check_phase3g_total_regression.py
```

总回归顺序：

```text
phase3f_total_regression_with_llm_disabled
llm_client_contract
rule_based_llm_client
llm_safety_guard
workflow_llm_node
```

说明：

```text
Phase 3-F 总回归以 AGENT_LLM_NODE_ENABLED=0 运行，避免新增 LLMNode 干扰旧基线。
Phase 3-G Workflow LLMNode 检查以 AGENT_LLM_NODE_ENABLED=1 运行，单独验证新增能力。
```

最终结果：

```text
phase3-g total regression passed
```

## 15. 已修复问题归档

Phase 3-G 中已修复：

```text
mypy 对 app.agent.llm 聚合包 re-export 识别不稳定，改为显式 re-export 与脚本直连子模块导入
LLMSafetyGuard 初版价格承诺正则漏判“99 元包邮，可以直接成交”，已增强 unauthorized_price_commitment 规则
Workflow 新增 llm node 后保持 final_response 不变
Workflow LLMNode error fallback 已验证
```

## 16. 当前技术价值

Phase 3-G 已体现以下能力：

```text
LLM 抽象接口设计
结构化 LLM request / response 建模
离线 LLMClient 可回归测试
LLM 安全包装
LLM 输出风险识别
LLM 输出不可成为事实源
LLM 输出不可成为承诺源
LangGraph LLMNode 接入
LLMNode 可开关
LLMNode 失败降级
LLM 调用 metadata 审计
```

系统当前具备：

```text
结构化模块回答
Qdrant RAG evidence injection
LLM offline safe summarization
LLM safety guard
final_response 仍由结构化模块控制
```

## 17. 当前限制

Phase 3-G v0.1 仍不支持：

```text
真实 LLM API
真实模型路由
API key 管理
OpenAI-compatible client
Claude client
Qwen client
token 预算管理
上下文裁剪
prompt template 管理
Grounded final rendering
LLM streaming
LLM retry
LLM cache
checkpoint
```

## 18. 后续建议

下一阶段建议进入：

```text
Phase 3-H：Grounded RenderNode
```

Phase 3-H 目标：

```text
结构化 facts
RAG references
business rules
LLM safe rewrite
final_response grounded rendering
引用可追踪
禁止承诺可拦截
```

推荐顺序：

```text
1. GroundedRenderInput / GroundedRenderOutput schema
2. RenderContextBuilder
3. structured_facts 提取
4. RAG evidence 摘要
5. business_rules 注入
6. LLM safe rewrite 可选使用
7. final_response 引用增强
8. 禁止承诺二次拦截
9. Phase 3-H 总回归
```

## 19. 最终结论

Phase 3-G 可以归档。

当前系统已完成：

```text
LLMClient Protocol
LLMRequest / LLMResponse schema
EchoLLMClient
RuleBasedLLMClient
LLMSafetyGuard
Workflow LLMNode
LLMNode fallback
Phase 3-G total regression
```

Phase 3-G 为后续 Grounded RenderNode、真实 LLM API 接入、模型路由、流式输出与多渠道客服 Agent 打好了基础。