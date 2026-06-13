# Phase 3-I-F Unified KB Routing Design v0.1

## 1. 目标

Phase 3-I-F 的目标是统一 Quality / Logistics / Price / Spec 四类真实 KB 的路由、冲突处理、优先级和回归验证。

当前四类 KB 已分别接入：

- Quality: `quality_kb_v1`
- Logistics: `logistics_kb_v1`
- Price: `price_kb_v1`
- Spec: `spec_kb_v1`

本阶段不改变四类 KB 的事实来源边界，只统一路由治理。

---

## 2. 总原则

统一路由必须遵守：

1. LLM 不是事实来源。
2. RAG 不是承诺来源。
3. 业务承诺只能来自结构化规则、人工确认或明确授权的数据表。
4. 当问题同时命中多个模块时，优先保证安全边界，再考虑回答完整度。
5. 当存在报价、赔付、适配承诺、质量承诺等高风险表达时，优先走风控更严格的模块或人工确认。

---

## 3. 模块职责边界

### 3.1 Spec

处理范围：

- SKU 规格查询
- 螺纹规格
- 杆长
- 球径
- 锥度
- 材质
- 表面处理
- OEM / SKU / 规格字段匹配
- 适配关系核对

禁止：

- 未核验车型适配
- 万能适配
- 百分百适配
- 相似规格直接推断确定兼容

### 3.2 Price

处理范围：

- 价格咨询
- 报价流程
- 是否优惠
- 批量采购报价
- 含税 / 发票相关价格确认

禁止：

- 直接报价
- 最低价承诺
- 保证优惠
- 包税承诺
- 未核算金额

### 3.3 Logistics

处理范围：

- 发货时间
- 到货时效
- 运费确认
- 包邮判断
- 物流破损 / 延误处理

禁止：

- 一定包邮
- 当天一定发
- 几天必到
- 固定运费承诺
- 一定赔付

### 3.4 Quality

处理范围：

- 材质说明
- 表面处理说明
- 品质检测
- 耐用性边界
- 售后质量问题说明

禁止：

- 寿命承诺
- 绝对耐用
- 永不生锈
- 未经验证性能承诺

---

## 4. 统一路由优先级

### 4.1 单一强信号

| 用户问题特征 | 目标模块 |
|---|---|
| 明确问规格、尺寸、螺纹、杆长、球径、OEM、适配 | Spec |
| 明确问价格、多少钱、优惠、折扣、含税、报价 | Price |
| 明确问发货、到货、运费、包邮、物流破损 | Logistics |
| 明确问材质、质量、检测、表面处理、耐用性 | Quality |

### 4.2 多意图冲突优先级

当一个问题同时命中多个模块：

| 冲突类型 | 优先模块 | 原因 |
|---|---|---|
| 价格 + 规格 | Price 优先，Spec 作为补充证据 | 防止先给规格后隐含报价承诺 |
| 物流 + 价格 | Price 优先，如涉及运费则 Logistics 补充 | 运费可能构成价格承诺 |
| 质量 + 价格 | Price 优先，Quality 补充边界 | 防止质量描述绑定价格承诺 |
| 适配 + 质量 | Spec 优先，Quality 补充材质边界 | 适配错误风险高于一般质量说明 |
| 适配 + 物流 | Spec 优先 | 未确认适配前不应推进发货承诺 |
| 赔付 + 物流 + 质量 | Logistics 优先，Quality 补充问题类型 | 赔付/补发属于履约处置边界 |
| 价格 + 物流 + 适配 | Spec 优先进入核对，Price/Logistics 不作承诺 | 未确认适配前不应报价或发货承诺 |

### 4.3 高风险词强制策略

出现下列词，应优先进入对应风控模块：

| 高风险词 | 强制模块 |
|---|---|
| 最低价、全网最低、便宜点、打折、包税 | Price |
| 包邮、今天发、明天到、必到、赔付、补发 | Logistics |
| 万能适配、一定适配、通用、全部车型 | Spec |
| 永不坏、永不生锈、10万公里、保证质量 | Quality |

---

## 5. 路由输出字段规范

统一路由后，Workflow metadata 至少应包含：

- `retrieval_selected_module`
- `retrieval_source`
- `retrieval_collection_name`
- `retrieval_hit_count`

四类真实 KB 对应值：

| Module | retrieval_source | retrieval_collection_name |
|---|---|---|
| quality | `real_quality_kb` | `quality_kb_v1` |
| logistics | `real_logistics_kb` | `logistics_kb_v1` |
| price | `real_price_kb` | `price_kb_v1` |
| spec | `real_spec_kb` | `spec_kb_v1` |

---

## 6. 当前设计状态

本文件为 Phase 3-I-F2 设计基线。

下一步应实现：

- 统一路由决策表检查脚本
- 跨模块冲突测试集
- Workflow 统一路由辅助函数
- 四类 KB Grounded E2E 总回归