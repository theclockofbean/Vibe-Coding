# Phase 3-I-A 真实 LLM API / OpenAI-compatible Client 接入设计文档 v0.1

## 1. 阶段目标

Phase 3-I-A 的目标是把当前离线 LLM 层升级为可调用真实大模型 API 的 LLMClient 体系。

当前系统已有：

```text
EchoLLMClient
RuleBasedLLMClient
LLMRequest / LLMResponse
LLMSafetyGuard
Workflow LLMNode
Grounded RenderNode
```

Phase 3-I-A 要新增：

```text
OpenAICompatibleLLMClient
LLMClientFactory
真实 API 环境变量配置
真实 API 调用错误降级
真实 LLM intent classifier 兜底能力
Quality 场景真实 LLM 表达增强
真实 LLM 冒烟测试
Phase 3-I-A 总回归
```

统一原则：

```text
真实 LLM 只能作为语言生成与辅助分类工具。
真实 LLM 不是事实来源。
真实 LLM 不是承诺来源。
真实 LLM 不得绕过 LLMSafetyGuard。
真实 LLM 不得直接写 final_response。
真实 LLM 失败时 workflow 必须降级，不得中断。
RuleBasedLLMClient 必须保留，作为离线回归与 fallback 基线。
```

## 2. 阶段边界

Phase 3-I-A 做：

```text
新增 OpenAICompatibleLLMClient
通过 httpx 调用 OpenAI-compatible chat completions API
支持 DeepSeek / OpenAI-compatible provider
支持 API timeout
支持 retry
支持 error response fallback
支持 env 配置
支持 LLMClientFactory
支持 Workflow LLMNode 切换真实 client
支持 intent classifier 低置信兜底
支持 Quality 场景真实 LLM 输出检查
支持 TC_QUAL_001 到 TC_QUAL_008 冒烟评测
```

Phase 3-I-A 不做：

```text
不删除 EchoLLMClient
不删除 RuleBasedLLMClient
不把真实 LLM 输出直接变成 final_response
不实现 streaming
不实现复杂模型路由
不实现前端配置页面
不实现完整 50 条评测框架
不写入真实 API key
不把 API key 打印到日志
```

## 3. 推荐文件结构

新增或修改文件：

```text
backend/app/agent/llm/openai_compatible.py
backend/app/agent/llm/factory.py
backend/app/agent/llm/prompts.py
backend/app/agent/llm/client.py
backend/app/agent/llm/__init__.py
backend/app/agent/workflow.py
```

新增检查脚本：

```text
backend/scripts/check_openai_compatible_llm_client_contract.py
backend/scripts/check_real_llm_api_smoke.py
backend/scripts/check_llm_intent_classifier_fallback.py
backend/scripts/check_quality_real_llm_rendering.py
backend/scripts/check_phase3ia_total_regression.py
```

后续评测脚本：

```text
backend/scripts/run_quality_llm_smoke_cases.py
```

## 4. 环境变量设计

推荐环境变量：

```text
LLM_ENABLE_REAL_API=0
LLM_PROVIDER=rule_based
LLM_BASE_URL=
LLM_API_KEY=
LLM_MODEL=
LLM_TIMEOUT_SECONDS=30
LLM_MAX_RETRIES=2
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=800
LLM_INTENT_CLASSIFIER_ENABLED=1
```

含义：

```text
LLM_ENABLE_REAL_API=0：默认关闭真实 API，使用 RuleBasedLLMClient。
LLM_ENABLE_REAL_API=1：允许调用真实 API。
LLM_PROVIDER：deepseek / openai_compatible / rule_based。
LLM_BASE_URL：OpenAI-compatible base URL。
LLM_API_KEY：只从环境变量读取，不写入代码，不写入日志。
LLM_MODEL：真实调用模型名称。
LLM_TIMEOUT_SECONDS：单次请求超时。
LLM_MAX_RETRIES：失败重试次数。
LLM_TEMPERATURE：默认低温，降低自由发挥。
LLM_MAX_TOKENS：限制输出长度。
```

安全要求：

```text
真实 API key 不得写入 Git。
真实 API key 不得写入归档文档。
真实 API key 不得写入日志。
真实 API key 不得进入 AgentState。
真实 API key 不得进入 metadata。
```

## 5. OpenAICompatibleLLMClient 设计

实现位置：

```text
backend/app/agent/llm/openai_compatible.py
```

核心类：

```text
OpenAICompatibleLLMClient
OpenAICompatibleLLMConfig
OpenAICompatibleLLMError
```

核心接口：

```text
generate(request: LLMRequest) -> LLMResponse
```

请求形式：

```text
POST {LLM_BASE_URL}/chat/completions
Authorization: Bearer {LLM_API_KEY}
Content-Type: application/json
```

请求体核心字段：

```text
model
messages
temperature
max_tokens
response_format 可选
```

messages 构造原则：

```text
system：固定安全边界与角色约束
developer：任务类型、输出格式、禁止事项
user：用户问题、结构化事实、RAG 证据、业务规则
```

输出要求：

```text
返回自然语言时必须简短
不能新增事实
不能新增价格
不能新增物流承诺
不能新增质量承诺
不能新增售后承诺
intent 分类时必须返回合法枚举
```

## 6. LLMClientFactory 设计

实现位置：

```text
backend/app/agent/llm/factory.py
```

核心职责：

```text
根据环境变量选择 LLMClient
默认返回 RuleBasedLLMClient
LLM_ENABLE_REAL_API=1 且配置完整时返回 OpenAICompatibleLLMClient
真实配置缺失时 fallback 到 RuleBasedLLMClient
```

选择逻辑：

```text
LLM_ENABLE_REAL_API != 1
  → RuleBasedLLMClient

LLM_ENABLE_REAL_API = 1
  AND LLM_BASE_URL / LLM_API_KEY / LLM_MODEL 完整
  → OpenAICompatibleLLMClient

LLM_ENABLE_REAL_API = 1
  BUT 配置不完整
  → RuleBasedLLMClient + warning
```

## 7. Workflow LLMNode 接入策略

当前 LLMNode 使用 RuleBasedLLMClient。

Phase 3-I-A 改为：

```text
client = build_llm_client_from_env()
response = client.generate(request)
guarded_response = LLMSafetyGuard().guard_response(response)
```

约束：

```text
LLMNode 仍不写数据库
LLMNode 仍不直接改 final_response
LLMNode 仍只写 llm_request / llm_response / llm_output / llm metadata
LLMNode error 时 workflow fallback
```

metadata 新增或保留：

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
llm_real_api_enabled
```

## 8. Intent Classifier 兜底策略

不直接替换现有 rule-based intent router。

策略：

```text
rule-based router 高置信命中 → 使用 rule-based 结果
rule-based router 低置信 / ambiguous → 调用真实 LLM intent classifier
LLM 输出合法枚举 → 使用 LLM 结果
LLM 输出非法 / 超时 / 被安全拦截 → fallback 到 rule-based 或 escalation
```

合法 intent 枚举：

```text
spec
price
logistics
quality
general
escalation
```

LLM intent classifier 输出格式建议：

```json
{
  "intent": "quality",
  "confidence": 0.82,
  "reason": "用户询问产品质量表现"
}
```

安全要求：

```text
intent classifier 只做分类
不得生成业务回答
不得生成价格
不得生成承诺
非法 JSON 必须 fallback
非法 intent 必须 fallback
```

## 9. Quality 场景真实 LLM 渲染策略

Quality Handler 的结构化输出和 RAG 证据进入 LLMNode 后，真实 LLM 只能做：

```text
总结 RAG 证据
自然化表达
解释需要人工确认的边界
生成非承诺性说明
```

不得做：

```text
判断质量一定好
承诺不生锈
承诺不掉漆
承诺耐用年限
承诺质保
新增 SKU 事实
新增检测结论
```

GroundedRenderer 使用真实 LLM 输出的条件仍为：

```text
llm_response.is_safe = true
llm_response.error is None
LLMSafetyGuard 未拦截
fact_source_allowed = false
commitment_source_allowed = false
```

目标验证点：

```text
GroundedRenderer.used_llm_output = true
final_response 仍包含结构化 answer_text
final_response 仍包含 response_sources
final_response 不包含禁止承诺
```

## 10. 冒烟测试范围

第一批真实 LLM 冒烟测试：

```text
TC_QUAL_001
TC_QUAL_002
TC_QUAL_003
TC_QUAL_004
TC_QUAL_005
TC_QUAL_006
TC_QUAL_007
TC_QUAL_008
```

测试数据来源：

```text
data/uploads 或 test_cases_draft.xlsx
```

每条用例检查：

```text
系统可正常返回
intent 合法
handoff_required 符合预期
final_response 非空
response_sources 可追踪
used_llm_output 可为 true
expected_contains 命中
expected_excludes 不出现
LLMSafetyGuard 不误拦截安全边界说明
```

## 11. 错误与降级策略

真实 LLM 可能出现：

```text
API key 缺失
base_url 错误
网络超时
HTTP 401 / 429 / 500
返回空 content
返回非法 JSON
输出命中禁止承诺
输出超长
输出与 task_type 不匹配
```

统一降级：

```text
LLMResponse.error 非空
llm_used = false
llm_fallback_reason 非空
fallback 到 RuleBasedLLMClient 或保留原 answer_text
workflow 不失败
GroundedRenderer 不使用 unsafe llm_output
```

## 12. 安全门控

Phase 3-I-A 通过标准：

```text
离线回归全部通过
真实 API smoke check 通过
LLM intent classifier 输出合法枚举
Quality 真实 LLM 渲染不出现禁止承诺
LLMSafetyGuard 能拦截真实 LLM 高风险输出
GroundedRenderer final_response 不出现 expected_excludes
价格类安全边界不被误拦截
```

禁止通过标准：

```text
真实 LLM 输出直接成为 final_response
真实 LLM 可绕过 LLMSafetyGuard
真实 LLM 输出价格
真实 LLM 输出质量承诺
真实 LLM 输出物流承诺
真实 LLM 输出售后承诺
API 失败导致 workflow 中断
```

## 13. 实施顺序

推荐顺序：

```text
1. 新增 OpenAICompatibleLLMConfig
2. 新增 OpenAICompatibleLLMClient
3. 新增 LLMClientFactory
4. 写 openai-compatible client contract check
5. 写真实 API smoke check
6. Workflow LLMNode 改为通过 factory 获取 client
7. 写 intent classifier fallback check
8. 写 Quality real LLM rendering check
9. 跑 TC_QUAL_001 到 TC_QUAL_008
10. 写 Phase 3-I-A total regression
11. 归档 Phase 3-I-A
```

## 14. 最终结论

Phase 3-I-A 的目标不是让真实 LLM 接管系统，而是把真实 LLM 放进现有安全架构中。

完成后，系统应从：

```text
结构化 Agent + Qdrant RAG + 离线 LLMClient + Grounded Final Response
```

升级为：

```text
结构化 Agent + Qdrant RAG + 真实 OpenAI-compatible LLMClient + Grounded Final Response
```

并且保持：

```text
可回归
可降级
可审计
不生成未授权承诺
不破坏已有安全链路
```
