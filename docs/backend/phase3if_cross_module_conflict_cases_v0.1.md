# Phase 3-I-F Cross Module Conflict Cases v0.1

## 1. 目标

本文件定义 Quality / Logistics / Price / Spec 四类真实 KB 的跨模块冲突测试集。

测试目标：

- 验证多意图问题能进入正确主模块；
- 验证高风险词能触发正确风控优先级；
- 验证回答不会输出未经授权承诺；
- 验证 metadata 中路由字段稳定写入。

---

## 2. 路由字段期望

每个通过真实 KB 的 case，应在 metadata 中产生：

- `retrieval_selected_module`
- `retrieval_source`
- `retrieval_collection_name`
- `retrieval_hit_count`

---

## 3. 冲突测试用例

| case_id | query | expected_module | conflict_type | reason |
|---|---|---|---|---|
| CONFLICT_001 | SKU001多少钱，螺纹是什么规格？ | price | price_spec | 涉及价格，Price 优先；规格只能作为补充信息 |
| CONFLICT_002 | SKU001适配我的车型吗？今天能发吗？ | spec | spec_logistics | 未确认适配前不应推进发货承诺 |
| CONFLICT_003 | 这个球头能通用适配吗？质量能保证吗？ | spec | spec_quality | 适配风险高于一般质量说明 |
| CONFLICT_004 | 便宜点能包邮吗？ | price | price_logistics | 优惠和包邮均可能构成价格承诺，Price 优先 |
| CONFLICT_005 | 如果质量有问题是不是一定赔？ | logistics | logistics_quality | 赔付/补发属于履约处置边界，Logistics 优先 |
| CONFLICT_006 | M10球头多少钱？ | price | price_spec | M10 是规格信号，但多少钱是价格强信号 |
| CONFLICT_007 | SKU001是不是不锈钢，能不能优惠？ | price | price_quality | 优惠是高风险价格信号，Price 优先 |
| CONFLICT_008 | SKU001表面处理是什么，多久能到？ | logistics | logistics_quality | 到货时效是履约信号，Logistics 优先 |
| CONFLICT_009 | 全网最低价的M12球头有吗？ | price | price_spec | 最低价为价格风险强信号 |
| CONFLICT_010 | 这个保证适配并且明天到吗？ | spec | spec_logistics | 保证适配风险最高，Spec 优先核对 |
| CONFLICT_011 | 会不会生锈，坏了能补发吗？ | logistics | logistics_quality | 补发属于履约处置边界 |
| CONFLICT_012 | 这个材质能用十万公里吗，多少钱？ | price | price_quality | 价格优先，同时质量寿命承诺需禁止 |
| CONFLICT_013 | OEM号能查吗？查到后能直接报价吗？ | price | price_spec | 直接报价为价格风险强信号 |
| CONFLICT_014 | 包邮的SKU001有现货规格吗？ | logistics | logistics_spec | 包邮为物流/运费承诺风险 |
| CONFLICT_015 | 万能适配的有没有便宜款？ | spec | spec_price | 万能适配为适配高风险，先进入 Spec 核对 |

---

## 4. 禁止输出片段

跨模块冲突回答中禁止出现：

- 最低价给你
- 全网最低
- 一定包邮
- 今天一定发
- 明天一定到
- 三天必到
- 万能适配
- 百分百适配
- 一定适配
- 保证适配
- 永不生锈
- 十万公里没问题
- 一定赔
- 一定补发

---

## 5. 当前阶段状态

本文件为 Phase 3-I-F3 测试集基线。

下一步应将该测试集转换为机器可执行检查脚本。