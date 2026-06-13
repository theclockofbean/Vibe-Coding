# Target LangGraph Agent Architecture v0.1

## 1. 文档目的

本文档用于固定 AI Knowledge Agent Platform 的最终目标架构。

该架构的核心目标是：在现有 Phase 1 / Phase 2 已完成的受控业务问答能力之上，逐步引入 LangGraph Agent 工作流、LLM 意图理解、RAG 检索链路、上下文管理、人工转接工单和多渠道接入能力。

本文档用于指导后续开发阶段：

```text
Phase 3：人工转接、会话上下文、AgentState、LangGraph 工作流骨架、RAG 激活
Phase 4：微信 / 企业微信、阿里巴巴 IM、淘宝开放平台等外部渠道接入
```

## 2. 当前系统基线

当前已完成：

```text
Phase 1：四个垂直业务模块
- spec
- price
- logistics
- quality

Phase 2：统一入口
- UnifiedIntentRouter
- UnifiedTextQAService
- POST /api/v1/agent/query
- Unified Agent API 边界检查
- Phase 2 总回归检查
```

当前统一入口：

```text
POST /api/v1/agent/query
```

当前四个垂直模块入口：

```text
POST /api/v1/spec/query
POST /api/v1/price/query
POST /api/v1/logistics/query
POST /api/v1/quality/query
```

说明：

```text
当前 /api/v1/agent/query 是内部 FastAPI 版本化接口。
目标架构图中的 /agent/query 可视为对外网关层或最终简化路径。
后续不要求立即修改现有 API 路径。
```

## 3. 最终目标架构总览

最终系统分为五层：

```text
接入层
API 层
Agent 层
AI 能力层
数据层
```

整体链路：

```text
微信 / 企业微信 / 阿里巴巴 IM / 淘宝开放平台 / 本地测试工具
→ HTTP API 层
→ LangGraph Agent 工作流
→ LLM API + RAG 检索链路
→ PostgreSQL + Qdrant
→ 风控校验
→ 最终回答 / 人工转接
```

## 4. 接入层

目标接入渠道：

```text
微信 / 企业微信
阿里巴巴 IM
淘宝开放平台
本地测试工具
```

阶段规划：

```text
本地测试工具：当前已有
微信 / 企业微信：Phase 4
阿里巴巴 IM：Phase 4
淘宝开放平台：Phase 4
```

接入层只负责：

```text
接收外部消息
转换为统一请求格式
传递 session_id / user_id / channel
调用 HTTP API 层
返回最终回答
```

接入层不负责：

```text
不直接调用 LLM
不直接查数据库
不直接调用业务 Handler
不绕过风控
不生成业务承诺
```

## 5. API 层

API 层需要保持稳定，避免因内部 Agent 架构升级而频繁变更外部调用方式。

当前已有：

```text
POST /api/v1/agent/query
```

目标新增：

```text
POST /api/v1/agent/conversation
GET /api/v1/handoff/tickets
```

目标图中的简化路径：

```text
POST /agent/query
POST /agent/conversation
GET /handoff/tickets
```

可作为后续 API Gateway 或前端代理层路径，不要求当前 FastAPI 立即改名。

API 层职责：

```text
HTTP 请求校验
构建数据库 Session
构建 ProductRepository / ConversationRepository / HandoffRepository
调用 Agent Workflow 或 UnifiedTextQAService 兼容层
返回统一 JSON
```

API 层不负责：

```text
不直接解析业务意图
不直接生成回答
不直接调用 LLM
不直接调用 RAG
不直接做业务承诺
不绕过风控
```

## 6. Agent 层目标

最终 Agent 层使用 LangGraph 工作流替代现有 UnifiedTextQAService 内部逻辑。

目标工作流：

```text
ContextNode
→ IntentNode
→ RouteNode
→ HandlerNode
→ RiskCtrlNode
→ FinalResponse
```

其中 RAG 与 LLM 不是独立主流程，而是被不同节点按需调用。

## 7. LangGraph 工作流节点设计

### 7.1 ContextNode

职责：

```text
加载 session_id
加载 conversation_history
加载用户最近消息
加载渠道信息
加载可用上下文
初始化 AgentState
```

数据来源：

```text
PostgreSQL conversations
PostgreSQL conversation_messages
HTTP request
```

不负责：

```text
不做意图分类
不生成回答
不调用业务模块
```

### 7.2 IntentNode

职责：

```text
识别用户意图
输出 intent
输出 candidate_modules
输出 matched_sku
输出 confidence
识别 ambiguous / unknown / invalid_request
```

短期实现：

```text
沿用当前 UnifiedIntentRouter 规则分类
```

中长期实现：

```text
LLM 意图分类
规则分类兜底
LLM 与规则结果冲突时进入风控或人工转接
```

可调用：

```text
LLMClient
UnifiedIntentRouter
```

不负责：

```text
不查询业务数据
不生成最终回答
不承诺任何业务结果
```

### 7.3 RouteNode

职责：

```text
根据 intent / selected_module 决定进入哪个业务模块
决定是否需要 RAG
决定是否需要人工转接
决定是否为 ambiguous
```

可路由模块：

```text
spec
price
logistics
quality
handoff
unknown
ambiguous
```

不负责：

```text
不直接生成回答
不直接调用 LLM 渲染结果
```

### 7.4 HandlerNode

职责：

```text
调用现有四个业务模块
调用结构化规则
调用必要的 RAG 检索链路
获得 module_payload
生成初步 answer_candidate
```

可调用：

```text
SpecTextQAService
PriceTextQAService
LogisticsTextQAService
QualityTextQAService
RAGRetriever
RuleService
```

关键原则：

```text
HandlerNode 必须优先复用 Phase 1 / Phase 2 已有受控业务模块。
不得重新写一套绕过现有边界的业务回答逻辑。
```

### 7.5 RiskCtrlNode

职责：

```text
检查最终回答是否包含禁止承诺
检查是否存在无来源事实
检查是否需要人工转接
检查价格 / 物流 / 质量 / 售后边界
记录 risk_triggered
记录风控日志
必要时覆盖 final_response 为转人工提示
```

禁止输出片段包括：

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

RiskCtrlNode 是最终出口前的强制节点。

任何 LLM 或 RAG 生成内容都必须经过 RiskCtrlNode。

## 8. AgentState 契约

目标 AgentState 字段：

```python
@dataclass
class AgentState:
    session_id: str | None
    channel: str | None
    user_id: str | None
    user_text: str
    conversation_history: list[dict[str, object]]

    intent: str | None
    selected_module: str | None
    candidate_modules: list[str]
    matched_signals: list[str]
    matched_sku: str | None

    retrieved_chunks: list[dict[str, object]]
    module_payload: dict[str, object] | None

    risk_triggered: bool
    risk_reasons: list[str]

    final_response: str | None
    human_handoff: bool
    handoff_ticket_id: str | None

    warnings: list[str]
    errors: list[str]
```

AgentState 必须满足：

```text
可追踪
可测试
可序列化
可记录日志
可用于后续多轮上下文
```

## 9. AI 能力层

AI 能力层包含两部分：

```text
LLM API
RAG 检索链路
```

### 9.1 LLM API

目标模型：

```text
DeepSeek-V3：意图分类 + 回答渲染
Qwen-Max：高质量兜底
```

统一封装：

```text
LLMClient
```

LLMClient 职责：

```text
统一模型调用
统一超时控制
统一重试策略
统一日志记录
统一 token 使用统计
统一异常处理
```

LLM 允许做：

```text
意图分类
用户问题改写
检索查询改写
回答语言润色
非承诺型解释
```

LLM 禁止做：

```text
凭空报价
凭空判断库存
凭空承诺到货时间
凭空承诺包邮
凭空承诺质保
凭空承诺退换
凭空承诺赔付
凭空判断质量责任
```

核心原则：

```text
LLM 可以参与理解和表达，但不能成为事实来源。
```

事实来源只能来自：

```text
PostgreSQL 结构化数据
Qdrant 检索结果
业务规则表
人工确认结果
```

### 9.2 RAG 检索链路

目标 RAG 流程：

```text
用户问题 / 改写查询
→ bge-m3 向量化
→ Qdrant 向量检索
→ BM25 关键词检索
→ RRF 混合融合
→ Top-3 chunks
→ 注入 AgentState.retrieved_chunks
```

RAG 用途：

```text
补充品质话术依据
补充物流 FAQ
补充材料说明
补充规则解释
辅助人工转接
辅助风控判断
```

RAG 不得直接决定：

```text
最终报价
最终库存
最终到货时间
是否包邮
是否赔付
是否质保
是否退换
```

## 10. 数据层

### 10.1 PostgreSQL

当前已有：

```text
products
```

目标新增：

```text
conversations
conversation_messages
handoff_tickets
shipping_rules
price_rules
aftersale_rules
risk_logs
llm_call_logs
```

用途：

```text
products：结构化商品数据
conversations：会话主表
conversation_messages：会话消息
handoff_tickets：人工转接工单
shipping_rules：物流规则
price_rules：价格规则
aftersale_rules：售后规则
risk_logs：风控日志
llm_call_logs：模型调用日志
```

### 10.2 Qdrant

目标激活 collections：

```text
quality_kb
logistics_kb
```

候选后续 collections：

```text
price_kb
aftersale_kb
product_manual_kb
```

当前目标：

```text
quality_kb：品质话术、材质说明、质量边界说明
logistics_kb：物流 FAQ、长尾物流问题、配送规则说明
```

## 11. 迁移策略

当前不推倒 Phase 1 / Phase 2。

迁移顺序：

```text
Step 1：保留 POST /api/v1/agent/query
Step 2：新增 Conversation / Handoff 数据表
Step 3：定义 AgentState
Step 4：新增 LangGraph Workflow 骨架
Step 5：让 LangGraph Workflow 先调用现有 UnifiedTextQAService 或四个 TextQAService
Step 6：激活 RAG 检索链路
Step 7：接入 LLMClient
Step 8：逐步将 UnifiedTextQAService 内部逻辑迁移为 LangGraph 节点
Step 9：接入外部 IM 渠道
```

关键原则：

```text
API 层保持稳定
业务模块边界保持稳定
LLM 和 RAG 逐步接入
风控必须先于对外开放
```

## 12. Phase 3 规划

### 12.1 Phase 3-A：Manual Handoff 工单表

目标：

```text
handoff_tickets 表
HandoffTicketRepository
转人工请求落库
GET /api/v1/handoff/tickets
```

优先级最高。

原因：

```text
当前 price / quality / 部分 logistics 已经稳定产生 handoff_required = true
但尚未形成可追踪工单
```

### 12.2 Phase 3-B：Conversation 上下文

目标：

```text
conversations 表
conversation_messages 表
session_id
conversation_history
```

对应：

```text
ContextNode
AgentState.session_id
AgentState.conversation_history
```

### 12.3 Phase 3-C：AgentState 契约

目标：

```text
定义 AgentState
定义节点输入输出
定义状态序列化
定义状态日志
```

### 12.4 Phase 3-D：LangGraph 工作流骨架

目标：

```text
ContextNode
IntentNode
RouteNode
HandlerNode
RiskCtrlNode
```

短期不强依赖 LLM。

先让 LangGraph 工作流调用现有规则模块，确保可测、可回归。

### 12.5 Phase 3-E：RAG 检索链路激活

目标：

```text
bge-m3 embedding
Qdrant quality_kb
Qdrant logistics_kb
BM25
RRF
Top-3 chunks
```

### 12.6 Phase 3-F：LLMClient 接入

目标：

```text
DeepSeek-V3
Qwen-Max
LLMClient
意图分类
回答渲染
高质量兜底
```

## 13. Phase 4 规划

Phase 4 进入外部渠道接入。

目标：

```text
微信 / 企业微信
阿里巴巴 IM
淘宝开放平台
```

接入前置条件：

```text
统一 API 稳定
会话上下文稳定
人工工单稳定
风控日志稳定
RAG 与 LLM 调用可观测
```

## 14. 当前非目标

当前阶段不做：

```text
不直接上线外部 IM
不直接让 LLM 接管回答
不跳过人工转接工单
不跳过风控节点
不跳过结构化规则表
不允许 RAG 直接生成承诺
不允许跨模块自由合并回答
```

## 15. 最终架构原则

最终系统必须遵守以下原则：

```text
API 稳定
模块边界清晰
状态可追踪
回答有来源
承诺有规则
风险可拦截
人工可接管
日志可审计
```

其中最重要的原则：

```text
LLM 不是事实来源。
RAG 不是承诺来源。
业务承诺只能来自结构化规则、人工确认或明确授权的数据表。
```

## 16. 当前结论

本项目最终目标不是简单的 FAQ 系统，也不是单纯的规则问答系统，而是一个具备以下能力的 Agent 系统：

```text
多渠道接入
统一 API
LangGraph 状态工作流
LLM 意图理解与表达增强
RAG 检索增强
结构化业务规则
人工转接工单
风控与日志审计
```

现有 Phase 1 / Phase 2 是最终架构的稳定基础。

后续开发应以本文档为目标框架，不再把 UnifiedTextQAService 视为最终形态，而是将其视为 LangGraph Agent Workflow 的过渡实现。