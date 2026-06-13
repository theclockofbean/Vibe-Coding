# Quality 模块归档文档 v0.1

## 1. 模块状态

当前质量模块 v0.1 已完成本地核心闭环：

```text
QualityParameterParser
→ QualityHandler
→ QualityAnswerRenderer
→ QualityTextQAService
→ POST /api/v1/quality/query
```

该模块已经完成：

```text
质量意图识别
产品引用提取
产品基础质量字段查询
受控质量回答渲染
文本问答服务封装
HTTP API 接口
API 正常场景测试
API 边界场景测试
```

## 2. 模块目标

Quality 模块 v0.1 的目标不是自动承诺产品质量、寿命、质保、退换或赔付，而是：

```text
识别质量相关问题
提取 SKU / OEM / 螺纹规格
查询 products 表中已有的质量基础字段
仅回答可被结构化数据支撑的材质和表面处理
对质量承诺、售后责任、质保、退换、赔付等问题统一转人工
输出结构化 JSON
```

## 3. 已实现能力

### 3.1 支持识别的问题类型

```text
material
surface_treatment
durability
rust_resistance
scratch_resistance
fitment_risk
defect_issue
warranty
return_exchange
compensation
general_quality
```

### 3.2 可自动回答的问题

当前仅允许自动回答低风险、结构化字段明确存在的问题：

```text
material：材质
surface_treatment：表面处理
```

前提：

```text
产品引用唯一
products 表匹配成功
对应字段有值
```

### 3.3 必须转人工的问题

以下问题必须转人工：

```text
durability：耐用性 / 使用寿命 / 是否容易坏
rust_resistance：是否生锈 / 防锈能力
scratch_resistance：是否掉漆 / 是否耐刮 / 是否磨损
fitment_risk：适配风险 / 装不上 / 买错
defect_issue：瑕疵 / 破损 / 异响 / 松动 / 划痕
warranty：质保 / 保修
return_exchange：退货 / 换货 / 退换
compensation：赔付 / 补偿 / 补发
general_quality：泛质量评价 / 品质 / 做工 / 靠谱
missing_product_reference：缺少 SKU、OEM 或螺纹规格
not_found：产品引用未匹配
```

## 4. 数据来源

当前质量模块只读取数据库中的 `products` 表。

允许读取字段：

```text
sku_id
product_name
thread_spec
oem_reference_number
material
surface_treatment
```

字段含义：

```text
material：产品登记材质
surface_treatment：产品登记表面处理
thread_spec：螺纹规格，仅作为产品定位字段
oem_reference_number：OEM 对照号，仅作为产品定位字段
```

## 5. 明确不支持的数据

当前系统没有正式接入以下数据：

```text
质检报告
检测标准
盐雾测试数据
耐磨测试数据
寿命测试数据
质保期限
退换货规则
赔付规则
安装责任规则
适配责任规则
客户投诉记录
批次质量记录
```

因此系统不得推断或生成上述内容。

## 6. 文件清单

### 6.1 文档文件

```text
docs/backend/quality_module_boundary_v0.1.md
docs/backend/quality_parameter_parser_design_v0.1.md
docs/backend/quality_handler_design_v0.1.md
docs/backend/quality_answer_renderer_design_v0.1.md
docs/backend/quality_api_design_v0.1.md
docs/backend/quality_module_v0.1.md
```

### 6.2 Parser

```text
backend/app/agent/parsers/quality_parameter_parser.py
```

核心对象：

```text
QualityParameterParser
ParsedQualityQuery
QualityParseStatus
QualityQueryType
ProductReferenceType
```

### 6.3 Handler

```text
backend/app/agent/handlers/quality_handler.py
```

核心对象：

```text
QualityHandler
QualityHandlerResult
```

### 6.4 Renderer

```text
backend/app/agent/renderers/quality_answer_renderer.py
```

核心对象：

```text
QualityAnswerRenderer
```

### 6.5 TextQAService

```text
backend/app/agent/services/quality_text_qa_service.py
```

核心对象：

```text
QualityTextQAService
QualityTextQAResult
```

### 6.6 API

```text
backend/app/api/v1/quality.py
backend/app/api/v1/router.py
```

接口：

```text
POST /api/v1/quality/query
```

### 6.7 测试与 Demo 脚本

```text
backend/scripts/check_quality_parameter_parser.py
backend/scripts/check_quality_handler.py
backend/scripts/check_quality_answer_renderer.py
backend/scripts/check_quality_text_qa_service.py
backend/scripts/demo_quality_text_qa.py
backend/scripts/check_quality_api.py
backend/scripts/check_quality_api_boundaries.py
```

## 7. API 说明

### 7.1 请求地址

```text
POST /api/v1/quality/query
```

### 7.2 请求体

```json
{
  "text": "SKU001 什么材质",
  "limit": 5
}
```

### 7.3 请求字段限制

```text
text：必填，1 到 500 字符
limit：可选，1 到 20，默认 5
```

### 7.4 响应字段

```json
{
  "parse_status": "parsed",
  "is_quality_intent": true,
  "quality_query_type": "material",
  "product_reference_type": "sku_id",
  "product_reference_value": "SKU001",
  "sku_ids": ["SKU001"],
  "oem_reference_numbers": [],
  "thread_specs": [],
  "warnings": [],
  "errors": [],
  "handler_status": "success",
  "matched_count": 1,
  "answer_text": "查到 SKU001：铝合金竞技换挡球头。该产品登记材质为铝合金。该回答仅基于当前已登记的产品信息，不代表额外质量承诺。",
  "handoff_required": false,
  "source_references": [
    {
      "source_type": "database_table",
      "source_name": "products",
      "reference_id": "SKU001"
    }
  ]
}
```

## 8. 状态规则

### 8.1 parse_status

```text
parsed：成功识别质量意图并提取唯一产品引用
not_quality_intent：不是质量问题
missing_product_reference：是质量问题，但缺少产品引用
ambiguous：存在多个 SKU / OEM / 螺纹规格等歧义
```

### 8.2 handler_status

```text
success：可自动回答
handoff：需要人工确认
not_found：产品引用未匹配
invalid_request：非质量问题或歧义输入
failed：异常状态
```

### 8.3 handoff_required

```text
false：系统可直接返回受控回答
true：需要人工进一步确认
```

## 9. 已验证场景

### 9.1 材质

输入：

```text
SKU001 什么材质
```

预期：

```text
parse_status = parsed
handler_status = success
handoff_required = false
answer_text 包含 “登记材质”
answer_text 包含 “不代表额外质量承诺”
```

### 9.2 表面处理

输入：

```text
SKU001 表面怎么处理
```

预期：

```text
parse_status = parsed
handler_status = success
handoff_required = false
answer_text 包含 “登记表面处理”
answer_text 包含 “不代表防锈、耐刮或不掉漆承诺”
```

### 9.3 耐用性

输入：

```text
SKU001 耐用吗
```

预期：

```text
handler_status = handoff
handoff_required = true
answer_text 包含 “不能自动承诺产品寿命”
```

### 9.4 防锈

输入：

```text
SKU001 会不会生锈
```

预期：

```text
handler_status = handoff
handoff_required = true
answer_text 包含 “不能自动承诺不生锈”
answer_text 不得包含 “保证不生锈”
```

### 9.5 掉漆 / 耐刮

输入：

```text
SKU001 会不会掉漆
```

预期：

```text
handler_status = handoff
handoff_required = true
answer_text 包含 “不能自动承诺不掉漆”
answer_text 不得包含 “保证不掉漆”
```

### 9.6 质保

输入：

```text
SKU001 质保多久
```

预期：

```text
handler_status = handoff
handoff_required = true
answer_text 包含 “不能自动承诺质保期限”
answer_text 不得包含具体质保期限
```

### 9.7 退换货

输入：

```text
SKU001 不合适能退吗
```

预期：

```text
handler_status = handoff
handoff_required = true
answer_text 包含 “不能自动承诺一定可退或一定可换”
```

### 9.8 赔付

输入：

```text
质量问题能赔吗
```

预期：

```text
parse_status = missing_product_reference
handler_status = handoff
handoff_required = true
answer_text 包含 “缺少产品引用”
answer_text 不得承诺赔付
```

### 9.9 疑似瑕疵

输入：

```text
SKU001 收到有划痕
```

预期：

```text
handler_status = handoff
handoff_required = true
answer_text 包含 “不能直接判断责任”
answer_text 包含 “请提供订单、图片、视频和安装信息”
```

### 9.10 产品不存在

输入：

```text
SKU999 什么材质
```

预期：

```text
handler_status = not_found
handoff_required = true
answer_text 包含 “暂未查到 SKU999 对应的质量基础信息”
```

### 9.11 多 SKU 歧义

输入：

```text
SKU001 和 SKU003 哪个质量更好
```

预期：

```text
parse_status = ambiguous
handler_status = invalid_request
handoff_required = false
answer_text 包含 “识别到多个 SKU”
```

### 9.12 非质量意图

输入：

```text
SKU001 几天发货
```

预期：

```text
parse_status = not_quality_intent
handler_status = invalid_request
handoff_required = false
answer_text 包含 “当前未识别为质量问题”
```

## 10. 测试命令

### 10.1 Parser 检查

```powershell
python scripts\check_quality_parameter_parser.py
```

预期：

```text
quality parameter parser check passed
```

### 10.2 Handler 检查

```powershell
python scripts\check_quality_handler.py
```

预期：

```text
quality handler check passed
```

### 10.3 Renderer 检查

```powershell
python scripts\check_quality_answer_renderer.py
```

预期：

```text
quality answer renderer check passed
```

### 10.4 TextQAService 检查

```powershell
python scripts\check_quality_text_qa_service.py
```

预期：

```text
quality text QA service check passed
```

### 10.5 Demo

```powershell
python scripts\demo_quality_text_qa.py
```

### 10.6 API 检查

```powershell
python scripts\check_quality_api.py
```

预期：

```text
quality API check passed
```

### 10.7 API 边界检查

```powershell
python scripts\check_quality_api_boundaries.py
```

预期：

```text
quality API boundary check passed
```

### 10.8 手动接口测试

启动服务：

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

请求：

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/api/v1/quality/query" `
  -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Body '{"text":"SKU001 什么材质","limit":5}' | ConvertTo-Json -Depth 8
```

## 11. 禁止行为

质量模块 v0.1 禁止：

```text
禁止调用 LLM 生成质量承诺
禁止承诺产品寿命
禁止承诺不会坏
禁止承诺不生锈
禁止承诺不掉漆
禁止承诺耐刮等级
禁止承诺质保期限
禁止承诺退货
禁止承诺换货
禁止承诺赔付
禁止承诺补发
禁止判断质量责任
禁止判断安装责任
禁止根据 material 推断防锈结果
禁止根据 surface_treatment 推断耐刮或防锈等级
禁止根据产品名称泛化判断质量好坏
```

## 12. 禁止输出片段

API 返回的 `answer_text` 不得包含：

```text
绝对不会坏
保证不会坏
保证不生锈
绝对不生锈
保证不掉漆
绝对不掉漆
保证耐用
保证耐用几年
终身质保
一年质保
两年质保
三年质保
七天无理由
一定能退
一定能换
一定赔
一定补发
质量问题一定赔
装不上一定负责
质量很好
放心用
完全没问题
```

允许出现：

```text
不能自动承诺产品寿命
不能自动承诺不生锈
不能自动承诺不掉漆
不能自动承诺质保期限
不能自动承诺一定可退
不能自动承诺一定可换
不能自动承诺处理结果
不代表额外质量承诺
不代表防锈、耐刮或不掉漆承诺
请转人工进一步确认
```

## 13. 当前限制

当前质量模块仍有以下限制：

```text
没有正式质检报告表
没有检测标准表
没有质量等级规则
没有盐雾测试数据
没有耐磨测试数据
没有寿命测试数据
没有质保规则表
没有退换货规则表
没有赔付规则表
没有客户投诉记录
没有批次质量记录
没有人工处理队列
```

因此当前只能作为受控质量基础问答模块，不能作为完整质量承诺或售后处理模块。

## 14. 后续升级建议

后续可新增：

```text
quality_rules 表
inspection_reports 表
warranty_policies 表
return_exchange_policies 表
compensation_rules 表
quality_issue_tickets 表
manual_handoff_queue 表
```

后续可升级能力：

```text
按产品读取正式质检报告
按 SKU 返回已验证检测标准
按规则返回质保范围
按订单状态判断是否进入售后流程
按图片/视频材料进入人工质检队列
按规则生成更细的转人工原因
接入前端管理后台
```

升级前提：

```text
所有质量规则必须结构化入库
所有质量规则必须有 verification_status
所有质保、退换、赔付规则必须经过人工业务确认
未确认规则不得进入自动回答
```

## 15. 当前结论

Quality 模块 v0.1 已完成 Phase 1 的本地核心闭环。

它当前具备：

```text
稳定解析质量问题
稳定查询产品材质与表面处理
稳定拒绝质量承诺
稳定拒绝质保、退换、赔付承诺
稳定输出受控客服回复
稳定提供 HTTP API
```

它当前不具备：

```text
自动承诺产品寿命
自动承诺防锈或不掉漆
自动承诺质保期限
自动承诺退换货
自动承诺赔付或补发
自动判断质量责任
自动处理售后流程
```

因此，Quality v0.1 可作为后续渠道接入和前端联调的基础能力。
