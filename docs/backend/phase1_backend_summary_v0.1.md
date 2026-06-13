# Phase 1 后端模块总归档文档 v0.1

## 1. 阶段状态

Phase 1 后端模块已完成四个垂直问答能力的本地闭环：

```text
Spec 模块
Price 模块
Logistics 模块
Quality 模块
```

当前已完成：

```text
产品规格问答
价格意图识别与受控转人工
物流问答
质量问答
四模块 API 路由统一挂载
四模块统一路由检查
```

## 2. 当前 API 路由

当前 FastAPI 应用已注册以下 Phase 1 路由：

```text
POST /api/v1/spec/query
POST /api/v1/price/query
POST /api/v1/logistics/query
POST /api/v1/quality/query
```

路由挂载规则：

```text
spec.py 内部自带 prefix="/spec"
price.py 内部自带 prefix="/price"
logistics.py 内部自带 prefix="/logistics"
quality.py 内部不自带 prefix，由 router.py 外层挂载 prefix="/quality"
```

因此 `router.py` 中应保持：

```python
api_router.include_router(spec_router)
api_router.include_router(price_router)
api_router.include_router(logistics_router)
api_router.include_router(quality_router, prefix="/quality", tags=["quality"])
```

不得再给 spec / price / logistics 额外添加外层 prefix，否则会变成：

```text
/api/v1/spec/spec/query
/api/v1/price/price/query
/api/v1/logistics/logistics/query
```

## 3. 模块清单

### 3.1 Spec 模块

接口：

```text
POST /api/v1/spec/query
```

核心能力：

```text
识别 SKU
识别规格查询
查询 products 表
返回产品规格字段
返回受控规格回答
```

当前特点：

```text
可以直接回答结构化产品规格
可返回螺纹规格、材质、表面处理、OEM 对照号、起订量、库存、发货周期等登记信息
```

### 3.2 Price 模块

接口：

```text
POST /api/v1/price/query
```

核心能力：

```text
识别价格意图
识别 SKU
识别数量
识别价格相关问题类型
在没有正式价格表时受控转人工
```

当前特点：

```text
当前未接入正式价格表
不能自动报价
不能承诺折扣
不能承诺最低价
不能承诺含税、含运费或付款条件
价格相关问题统一进入受控 handoff
```

### 3.3 Logistics 模块

接口：

```text
POST /api/v1/logistics/query
```

核心能力：

```text
识别物流意图
识别 SKU
查询库存状态
查询发货周期
返回受控物流回答
```

当前可自动回答：

```text
shipping_time
stock_status
```

当前必须转人工：

```text
fee
free_shipping
delivery_time
carrier
tracking
expedite
```

当前禁止：

```text
承诺到货时间
承诺包邮
承诺具体承运商
承诺加急
承诺当天一定发货
```

### 3.4 Quality 模块

接口：

```text
POST /api/v1/quality/query
```

核心能力：

```text
识别质量意图
识别 SKU / OEM / 螺纹规格
查询 products 表中的材质与表面处理
返回受控质量回答
对质量承诺、售后责任、质保、退换、赔付统一转人工
```

当前可自动回答：

```text
material
surface_treatment
```

当前必须转人工：

```text
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

当前禁止：

```text
承诺产品寿命
承诺不会坏
承诺不生锈
承诺不掉漆
承诺质保期限
承诺退换货
承诺赔付
判断质量责任
判断安装责任
```

## 4. 已完成核心文件

### 4.1 API 文件

```text
backend/app/api/v1/spec.py
backend/app/api/v1/price.py
backend/app/api/v1/logistics.py
backend/app/api/v1/quality.py
backend/app/api/v1/router.py
backend/app/main.py
```

### 4.2 Parser 文件

```text
backend/app/agent/parsers/spec_parameter_parser.py
backend/app/agent/parsers/price_parameter_parser.py
backend/app/agent/parsers/logistics_parameter_parser.py
backend/app/agent/parsers/quality_parameter_parser.py
```

### 4.3 Handler 文件

```text
backend/app/agent/handlers/spec_handler.py
backend/app/agent/handlers/price_handler.py
backend/app/agent/handlers/logistics_handler.py
backend/app/agent/handlers/quality_handler.py
```

### 4.4 Renderer 文件

```text
backend/app/agent/renderers/spec_answer_renderer.py
backend/app/agent/renderers/price_answer_renderer.py
backend/app/agent/renderers/logistics_answer_renderer.py
backend/app/agent/renderers/quality_answer_renderer.py
```

### 4.5 Service 文件

```text
backend/app/agent/services/spec_text_qa_service.py
backend/app/agent/services/price_text_qa_service.py
backend/app/agent/services/logistics_text_qa_service.py
backend/app/agent/services/quality_text_qa_service.py
```

## 5. 已完成测试脚本

```text
backend/scripts/check_quality_parameter_parser.py
backend/scripts/check_quality_handler.py
backend/scripts/check_quality_answer_renderer.py
backend/scripts/check_quality_text_qa_service.py
backend/scripts/check_quality_api.py
backend/scripts/check_quality_api_boundaries.py
backend/scripts/check_phase1_api_routes.py
```

建议后续补齐或统一整理：

```text
backend/scripts/check_spec_api.py
backend/scripts/check_price_api.py
backend/scripts/check_logistics_api.py
backend/scripts/check_phase1_regression.py
```

## 6. Phase 1 总检查命令

### 6.1 静态检查

```powershell
python -m ruff check app scripts
python -m mypy app scripts
```

如需局部检查：

```powershell
python -m ruff check `
  app\api\v1\router.py `
  app\main.py `
  scripts\check_phase1_api_routes.py

python -m mypy `
  app\api\v1\router.py `
  app\main.py `
  scripts\check_phase1_api_routes.py
```

### 6.2 四模块路由检查

```powershell
python scripts\check_phase1_api_routes.py
```

预期：

```text
phase1 API route check passed
```

### 6.3 Quality 模块完整检查

```powershell
python scripts\check_quality_parameter_parser.py
python scripts\check_quality_handler.py
python scripts\check_quality_answer_renderer.py
python scripts\check_quality_text_qa_service.py
python scripts\check_quality_api.py
python scripts\check_quality_api_boundaries.py
```

预期：

```text
quality parameter parser check passed
quality handler check passed
quality answer renderer check passed
quality text QA service check passed
quality API check passed
quality API boundary check passed
```

## 7. 当前统一边界原则

Phase 1 的核心原则：

```text
只回答结构化数据能支撑的问题
没有正式规则表时必须转人工
不得让 LLM 或模板生成业务承诺
不得捏造 SKU、价格、库存、物流、质量、售后信息
不得把产品名称、材质、表面处理推断成质量承诺
```

各模块统一禁止：

```text
禁止虚构 SKU
禁止虚构价格
禁止虚构库存
禁止虚构物流承诺
禁止虚构质保
禁止虚构退换货
禁止虚构赔付
禁止主观推荐
禁止夸大产品性能
```

## 8. 当前限制

Phase 1 当前仍有以下限制：

```text
尚未实现统一意图入口
尚未实现跨模块 Router Agent
尚未实现多轮上下文
尚未实现用户会话记忆
尚未实现人工工单系统
尚未接入正式价格表
尚未接入正式物流规则表
尚未接入正式质检报告
尚未接入质保、退换、赔付规则表
尚未接入前端页面
```

## 9. Phase 2 建议方向

建议 Phase 2 从“统一入口层”开始，而不是继续扩展单模块。

优先级建议：

```text
1. UnifiedIntentRouter：统一识别 spec / price / logistics / quality
2. UnifiedTextQAService：统一调度四个模块
3. Unified API：POST /api/v1/agent/query
4. 统一 Response Schema
5. 跨模块回归测试集
6. 人工转接队列 manual_handoff_queue
7. 前端联调页面
```

## 10. 建议新增统一接口

建议 Phase 2 新增：

```text
POST /api/v1/agent/query
```

请求：

```json
{
  "text": "SKU001 什么材质",
  "limit": 5
}
```

响应：

```json
{
  "selected_module": "quality",
  "parse_status": "parsed",
  "handler_status": "success",
  "answer_text": "...",
  "handoff_required": false,
  "source_references": []
}
```

该接口不替代现有四个模块接口，而是在上层做统一调度。

## 11. 当前结论

Phase 1 已完成后端基础能力闭环。

当前系统已经具备：

```text
产品规格受控问答
价格问题受控转人工
物流发货与库存受控问答
质量材质与表面处理受控问答
四模块 API 路由统一挂载
四模块基础隔离验证
```

当前系统还不应对外承诺：

```text
最终报价
折扣
含税含运
到货时间
包邮
承运商
产品寿命
防锈能力
不掉漆
质保期限
退换货
赔付
```

Phase 1 可以归档，后续进入 Phase 2：统一入口与跨模块调度。