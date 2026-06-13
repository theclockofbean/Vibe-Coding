# Phase 3-G LLMClient 接入设计文档 v0.1

## 1. 文档目的

本文档用于固定 Phase 3-G 中 LLMClient 的设计目标、组件边界、调用契约、安全策略、降级策略、LangGraph 接入方式和回归检查范围。

Phase 3-G 的目标不是让 LLM 直接接管回答，而是建立一个可控的大模型调用层：

```text
AgentState
  ↓
LLMRequest
  ↓
LLMClient
  ↓
LLMResponse
  ↓
Safety Wrapper
  ↓
AgentState.llm_output / metadata
```

统一原则：

```text
LLM 是语言生成工具，不是事实来源。
LLM 不得替代结构化数据。
LLM 不得替代业务规则。
LLM 不得生成价格、库存、物流、质量、售后承诺。
RAG 是证据补充，不是承诺来源。
最终业务回答必须可审计、可降级、可拒答。
```

## 2. 当前系统基础

截至 Phase 3-F，系统已具备：

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
LocalKnowledgeChunkRetriever
QdrantRetriever
RAGEvidenceFilter
RetrievalNode qdrant mode
Phase 3-F total regression
```

Phase 3-G 在此基础上新增：

```text
LLMClient Protocol
LLMRequest / LLMResponse schema
RuleBasedLLMClient
EchoLLMClient
OpenAI-compatible client 预留
LLMSafetyGuard
LLM fallback 策略
LLMClient contract checks
Workflow LLM node 设计
Phase 3-G total regression
```

## 3. 阶段边界

Phase 3-G v0.1 做：

```text
定义 LLMClient 抽象接口
定义 LLMRequest / LLMResponse 数据结构
实现不联网的 RuleBasedLLMClient / EchoLLMClient
预留 OpenAI-compatible client 结构
实现 LLM safety wrapper
验证 LLM 不可成为事实源
验证 LLM 不可输出禁止承诺
验证 LLM 失败时可降级
为 LangGraph 增加可选 LLM node 设计
```

Phase 3-G v0.1 不做：

```text
不接真实 OpenAI / Claude / Qwen API
不把 LLM 输出直接作为 final_response
不让 LLM 生成价格
不让 LLM 承诺库存
不让 LLM 承诺发货
不让 LLM 承诺到货
不让 LLM 承诺包邮
不让 LLM 承诺质量
不让 LLM 承诺售后
不实现 Grounded RenderNode
不实现流式输出
不实现 checkpoint
```

## 4. 目标架构

Phase 3-G 目标架构：

```text
LangGraph Workflow
  ↓
AgentState
  ↓
LLMNode
  ↓
LLMRequestBuilder
  ↓
LLMClient
  ↓
LLMSafetyGuard
  ↓
AgentState.llm_output
  ↓
RenderNode / future GroundedRenderNode
```

LLM 的定位：

```text
辅助表达
辅助归纳
辅助改写
辅助生成结构化草稿
不负责事实判断
不负责业务承诺
不负责最终权威结论
```

## 5. LLMClient Protocol 设计

建议新增文件：

```text
backend/app/agent/llm/schemas.py
backend/app/agent/llm/client.py
backend/app/agent/llm/safety.py
backend/app/agent/llm/__init__.py
```

核心接口：

```python
class LLMClient(Protocol):
    def generate(
        self,
        request: LLMRequest,
    ) -> LLMResponse:
        ...
```

接口要求：

```text
输入必须结构化
输出必须结构化
异常必须可捕获
响应必须带 model / provider / latency metadata
不得直接写数据库
不得直接改 AgentState
不得直接生成 final_response
```

## 6. LLMRequest 设计

建议字段：

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

其中：

```text
structured_facts 来自 PostgreSQL / 业务模块
retrieved_chunks 来自 RAG
business_rules 来自规则层
forbidden_commitments 来自风控配置
```

LLMRequest 中必须显式声明：

```text
不得编造事实
不得生成业务承诺
不得输出未授权价格
不得输出未确认物流承诺
不得输出未确认质量保证
不得输出售后赔付承诺
引用不足时应返回 needs_handoff / insufficient_evidence
```

## 7. LLMResponse 设计

建议字段：

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

其中：

```text
content 不是 final_response
is_safe = false 时不得进入渲染
needs_handoff = true 时应进入人工接管或拒答链路
error 非空时 workflow 应降级
```

## 8. Task Type 设计

Phase 3-G v0.1 支持以下 task_type：

```text
rewrite_safe_answer
summarize_evidence
draft_handoff_note
classify_answer_risk
echo_test
rule_based_test
```

暂不支持：

```text
freeform_final_answer
price_generation
logistics_commitment_generation
quality_guarantee_generation
aftersale_commitment_generation
```

## 9. 测试 LLMClient

Phase 3-G v0.1 先实现两个离线 client：

```text
EchoLLMClient
RuleBasedLLMClient
```

### 9.1 EchoLLMClient

用途：

```text
验证 LLMClient contract
验证 request / response schema
验证 workflow 接线
不做真实语言生成
```

行为：

```text
返回固定 echo 内容
携带 provider = local
model = echo-llm-v1
is_safe = true
```

### 9.2 RuleBasedLLMClient

用途：

```text
验证安全规则
验证 forbidden commitments 拦截
验证 needs_handoff
验证不可成为事实源
```

行为：

```text
如果 task_type 合法，返回模板化安全内容
如果 user_text 命中禁止承诺，返回 needs_handoff = true
如果上下文不足，返回 insufficient_evidence
```

## 10. OpenAI-compatible client 预留

后续可新增：

```text
OpenAICompatibleLLMClient
```

但 Phase 3-G v0.1 只预留接口，不调用真实 API。

预留字段：

```text
base_url
api_key_env
model
timeout
max_retries
```

约束：

```text
API key 只能来自环境变量
不得写入代码
不得写入日志
不得写入归档文档
请求失败必须 fallback
```

## 11. LLMSafetyGuard 设计

新增：

```text
LLMSafetyGuard
```

职责：

```text
扫描 forbidden commitments
扫描未授权价格表达
扫描物流确定性承诺
扫描质量绝对化承诺
扫描售后赔付承诺
判断 LLMResponse 是否可进入后续节点
```

输出：

```text
is_safe
risk_flags
risk_reasons
sanitized_content
needs_handoff
```

禁止片段沿用系统级风险片段：

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

## 12. Workflow LLMNode 设计

Phase 3-G 建议新增可选节点：

```text
llm
```

目标拓扑：

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

但 Phase 3-G v0.1 中：

```text
LLMNode 默认 disabled
LLMNode 不改 final_response
LLMNode 只写入 AgentState.llm_output / metadata
RiskCtrlNode 仍检查最终输出
RenderNode 仍以结构化 handler answer 为主
```

## 13. AgentState 扩展建议

建议新增字段：

```text
llm_request
llm_response
llm_output
llm_safety_flags
llm_used
llm_error
```

metadata 新增：

```text
llm_provider
llm_model
llm_task_type
llm_latency_ms
llm_is_safe
llm_needs_handoff
llm_fallback_reason
```

## 14. Fallback 策略

LLM 失败时：

```text
不影响主流程
不影响结构化 answer_text
不影响 handoff 判断
不影响 conversation 写入
metadata 记录 llm_error
llm_used = false
```

Fallback 优先级：

```text
1. RuleBasedLLMClient
2. EchoLLMClient
3. disabled LLM
```

真实 API 后续接入时：

```text
1. OpenAICompatibleLLMClient
2. RuleBasedLLMClient
3. EchoLLMClient
4. disabled LLM
```

## 15. 安全边界

LLM 输出不得：

```text
生成价格
确认折扣
确认最低价
承诺库存
承诺发货
承诺到货
承诺包邮
承诺质量
承诺不生锈
承诺不掉漆
承诺质保
承诺退换
承诺赔付
覆盖结构化数据
覆盖业务规则
删除人工接管标记
```

LLM 可以：

```text
把结构化事实表达得更自然
把 RAG 证据总结成非承诺性说明
生成人工接管备注
生成安全拒答草稿
生成解释型补充说明
```

## 16. 检查脚本规划

建议新增：

```text
backend/scripts/check_llm_client_contract.py
backend/scripts/check_llm_safety_guard.py
backend/scripts/check_rule_based_llm_client.py
backend/scripts/check_workflow_llm_node.py
backend/scripts/check_phase3g_total_regression.py
```

## 17. 回归检查范围

### 17.1 LLMClient contract check

验证：

```text
EchoLLMClient 实现 LLMClient Protocol
RuleBasedLLMClient 实现 LLMClient Protocol
LLMRequest 字段完整
LLMResponse 字段完整
空 user_text 拒绝或安全降级
非法 task_type 拒绝或安全降级
```

### 17.2 LLM safety check

验证：

```text
禁止承诺片段会被拦截
价格承诺会被拦截
物流承诺会被拦截
质量绝对化承诺会被拦截
售后赔付承诺会被拦截
safe response 可通过
unsafe response needs_handoff = true
```

### 17.3 Workflow LLM node check

验证：

```text
LLMNode 可运行
LLMNode 写入 llm_output
LLMNode 不改 final_response
LLMNode 不写数据库
LLMNode 不创建 handoff ticket
LLM 失败时 workflow 不失败
```

## 18. Phase 3-G 交付目标

完成后应具备：

```text
LLMClient 抽象层
LLMRequest / LLMResponse schema
EchoLLMClient
RuleBasedLLMClient
LLMSafetyGuard
LLM fallback
Workflow LLMNode 初步接入
Phase 3-G total regression
```

## 19. 后续阶段

Phase 3-G 后建议进入：

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

## 20. 最终结论

Phase 3-G 的关键目标是让系统具备大模型调用能力，但不让大模型成为事实源或承诺源。

本阶段完成后，系统将从：

```text
结构化 Agent + Qdrant RAG
```

升级为：

```text
结构化 Agent + Qdrant RAG + 可控 LLMClient
```

为后续 Grounded RenderNode 打基础。
