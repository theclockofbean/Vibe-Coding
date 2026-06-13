\# AI知识运营智能体平台数据文件到数据库映射规范



> 文档版本：v0.1

> 文档状态：Draft

> 适用阶段：Phase 1｜数据层搭建

> 关联文档：`docs/data/database\_schema\_v0.1.md`

> 更新时间：2026-06-10



\---



\## 1. 文档目的



本文档用于固定 Phase 0 数据文件到 Phase 1 数据库结构之间的映射关系，包括：



\* 文件位置；

\* 工作表名称；

\* 字段映射；

\* 数据类型转换；

\* 空值处理；

\* 多值字段解析；

\* 行级校验；

\* 导入批次记录；

\* 错误处理；

\* 数据追溯；

\* 各文件是否允许进入正式知识库。



后续 SQLAlchemy 模型、Pydantic Schema、Alembic 迁移和数据导入脚本必须遵守本文档。



\---



\# 2. 数据源清单



\## 2.1 SKU主数据



项目路径：



```text

data/uploads/specs/sku\_master.xlsx

```



目标数据库表：



```text

products

```



导入类型：



```text

sku\_master

```



导入策略：



```text

全量校验

整体事务

任一关键记录失败则全部回滚

```



\---



\## 2.2 四类问答文件



项目路径：



```text

data/uploads/conversations/qa\_pairs\_raw/spec\_questions.xlsx

data/uploads/conversations/qa\_pairs\_raw/quality\_questions.xlsx

data/uploads/conversations/qa\_pairs\_raw/price\_questions.xlsx

data/uploads/conversations/qa\_pairs\_raw/logistics\_questions.xlsx

```



用途：



| 文件                         | Phase 1用途                     |

| -------------------------- | ----------------------------- |

| `spec\_questions.xlsx`      | 意图分类few-shot、规格Handler测试、规则验证 |

| `quality\_questions.xlsx`   | 品质知识分片来源、Qdrant品质知识库来源        |

| `price\_questions.xlsx`     | 价格规则验证、价格风控测试，不进入向量库          |

| `logistics\_questions.xlsx` | 物流知识分片来源、Qdrant物流知识库来源        |



质量和物流问答可映射至：



```text

knowledge\_chunks

```



规格和价格问答在 v0.1 阶段不直接导入业务表，继续以审核后的文件形式作为输入数据源。



\---



\## 2.3 业务规则文件



项目路径：



```text

data/uploads/conversations/business\_rules.md

```



当前版本：



```text

v1.0-draft

```



当前状态：



```text

pending

```



该文件不直接写入 PostgreSQL。



Phase 1 后续由规则解析流程生成：



```text

data/parsed/pricing/business\_rules.json

data/parsed/logistics/logistics\_rules.json

```



未核验金额必须满足：



```text

enabled=false

amount=null

verification\_status=pending

customer\_visible=false

```



\---



\## 2.4 测试用例



项目路径：



```text

data/evaluation/test\_cases\_draft.xlsx

```



目标数据库表：



```text

evaluation\_cases

```



导入类型：



```text

evaluation\_cases

```



当前数据量：



```text

50条

```



当前核验状态：



```text

pending

```



\---



\# 3. 通用读取规范



\## 3.1 文件读取



导入程序必须：



1\. 使用文件绝对路径读取；

2\. 在读取前检查文件是否存在；

3\. 计算 SHA256；

4\. 检查同类型文件是否已经成功导入；

5\. 使用文件内容而不是文件名判断重复；

6\. 不修改原始文件；

7\. 不在导入过程中覆盖原始文件。



\---



\## 3.2 Excel工作表读取



数据脚本必须读取明确指定的工作表，不得默认使用第一个工作表。



当前工作表：



| 文件                      | 工作表                             |

| ----------------------- | ------------------------------- |

| `sku\_master.xlsx`       | `Sheet1`                        |

| 四类问答文件                  | `qa\_pairs`、`label\_dictionary`   |

| `test\_cases\_draft.xlsx` | `test\_cases`、`字段详细说明`、`评测指标与门控` |



导入业务数据时只读取：



```text

Sheet1

qa\_pairs

test\_cases

```



说明和字典工作表用于校验，不直接写入业务表。



\---



\## 3.3 表头规则



表头必须：



\* 去除首尾空格；

\* 保持字符大小写；

\* 与本文件定义的字段完全一致；

\* 不允许缺列；

\* 不允许重复列；

\* 不允许未登记的额外列静默进入数据库。



如果发现表头不一致，导入必须终止，不得猜测字段对应关系。



\---



\## 3.4 字符串处理



普通字符串字段统一执行：



```text

去除首尾空格

保留字符串内部空格

空字符串转换为NULL或空数组

不擅自修改业务文本

```



以下原始文本不得自动改写：



```text

question\_raw

answer\_raw

input\_message

```



标准化字段可以按照明确规则处理：



```text

question\_normalized

answer\_standard

expected\_answer

```



但导入脚本不能自行生成或重写这些内容。



\---



\## 3.5 数值处理



规格数值使用：



```text

Decimal

```



不得先转换为二进制浮点数再写入 PostgreSQL。



例如：



```text

1.25 → Decimal("1.25")

1.5  → Decimal("1.5")

```



整数列必须拒绝：



```text

1.5

三个

约5

5个

```



只能接受真正的整数值或可无歧义转换的整数字符串。



\---



\## 3.6 布尔值处理



允许的输入：



```text

TRUE

FALSE

true

false

```



转换结果：



```text

PostgreSQL true

PostgreSQL false

```



不得将以下值自动猜测为布尔值：



```text

是

否

1

0

Y

N

```



如后续需要支持，必须先修改映射规范。



\---



\## 3.7 多值字段处理



多值字段统一使用英文分号：



```text

;

```



处理步骤：



1\. 按英文分号拆分；

2\. 去除每个元素首尾空格；

3\. 删除空元素；

4\. 保留原有顺序；

5\. 在保留顺序的前提下去重；

6\. 写入 PostgreSQL `TEXT\[]`。



示例：



```text

SKU001;SKU002;SKU001

```



转换为：



```text

{"SKU001","SKU002"}

```



空单元格转换为：



```text

{}

```



不得转换为：



```text

NULL

{""}

```



\---



\# 4. SKU主数据映射



\## 4.1 来源与目标



来源：



```text

sku\_master.xlsx

Sheet1

```



目标：



```text

products

```



当前每一行代表一个 SKU。



\---



\## 4.2 字段映射



| Excel字段   | 数据库字段                  | 目标类型         | 转换规则        |

| --------- | ---------------------- | ------------ | ----------- |

| `SKU\_ID`  | `sku\_id`               | VARCHAR(32)  | 去除首尾空格，保持大写 |

| `产品名称`    | `product\_name`         | VARCHAR(255) | 去除首尾空格      |

| `螺纹规格`    | `thread\_spec`          | VARCHAR(32)  | 保留标准显示格式    |

| `螺纹规格`    | `thread\_type`          | VARCHAR(8)   | 从规格中解析，当前为M |

| `螺纹规格`    | `thread\_diameter\_mm`   | NUMERIC(6,2) | 解析M后的直径     |

| `螺纹规格`    | `thread\_pitch\_mm`      | NUMERIC(6,3) | 解析×后的牙距     |

| `杆长(mm)`  | `rod\_length\_mm`        | NUMERIC(8,2) | 必须大于0       |

| `球径(mm)`  | `ball\_diameter\_mm`     | NUMERIC(8,2) | 必须大于0       |

| `锥度比`     | `taper\_ratio`          | VARCHAR(32)  | `无`转换为NULL  |

| `材质`      | `material`             | VARCHAR(255) | 去除首尾空格      |

| `表面处理`    | `surface\_treatment`    | VARCHAR(255) | 去除首尾空格      |

| `OEM对照号`  | `oem\_reference\_number` | VARCHAR(128) | 强制按文本读取     |

| `起订量(个)`  | `min\_order\_qty`        | INTEGER      | 必须为正整数      |

| `备货状态`    | `stock\_status`         | VARCHAR(32)  | 保留标准状态值     |

| `发货周期(天)` | `lead\_time\_days`       | INTEGER      | 必须大于等于0     |



系统生成字段：



| 数据库字段               | 生成方式              |

| ------------------- | ----------------- |

| `is\_active`         | 默认true            |

| `import\_batch\_id`   | 当前导入批次主键          |

| `source\_file`       | `sku\_master.xlsx` |

| `source\_row\_number` | Excel实际行号         |

| `created\_at`        | 当前时间              |

| `updated\_at`        | 当前时间              |



\---



\## 4.3 螺纹规格解析



允许的当前格式：



```text

M8×1.25

M10×1.5

M12×1.25

```



解析结果示例：



| 原始值      | thread\_type | thread\_diameter\_mm | thread\_pitch\_mm |

| -------- | ----------- | -----------------: | --------------: |

| M8×1.25  | M           |                  8 |            1.25 |

| M10×1.5  | M           |                 10 |             1.5 |

| M12×1.25 | M           |                 12 |            1.25 |



导入时允许将以下乘号形式规范为 `×`：



```text

x

X

\*

```



例如：



```text

M8x1.25 → M8×1.25

```



不得接受：



```text

M8

8×1.25

M8大概1.25

```



\---



\## 4.4 锥度比处理



Excel允许值：



```text

无

1:10

1:15

1:20

其他经业务核验的1:N格式

```



转换：



```text

无 → NULL

```



锥度比必须符合：



```regex

^1:\[1-9]\[0-9]\*$

```



不得转换为：



```text

0

0.0

"NULL"

空字符串文本

```



\---



\## 4.5 OEM编号处理



OEM编号必须：



\* 按文本读取；

\* 保留前导零；

\* 保留连字符；

\* 保留英文字母；

\* 去除首尾空格；

\* 不转换为数字；

\* 不依据车型自动生成。



例如：



```text

00123-45678

```



必须保持：



```text

00123-45678

```



不能写成：



```text

123-45678

```



\---



\## 4.6 SKU行级校验



每行必须满足：



```text

sku\_id非空且唯一

product\_name非空

thread\_spec可解析

rod\_length\_mm > 0

ball\_diameter\_mm > 0

min\_order\_qty > 0

lead\_time\_days >= 0

stock\_status非空

oem\_reference\_number非空

```



如果任意一行关键字段失败：



```text

整批SKU导入回滚

```



\---



\## 4.7 SKU更新策略



同一 `sku\_id` 已存在时，第一版导入策略使用：



```text

UPSERT

```



更新允许修改：



```text

product\_name

thread\_spec

thread\_type

thread\_diameter\_mm

thread\_pitch\_mm

rod\_length\_mm

ball\_diameter\_mm

taper\_ratio

material

surface\_treatment

oem\_reference\_number

min\_order\_qty

stock\_status

lead\_time\_days

is\_active

import\_batch\_id

source\_file

source\_row\_number

updated\_at

```



不修改：



```text

id

sku\_id

created\_at

```



\---



\# 5. 测试用例映射



\## 5.1 来源与目标



来源：



```text

test\_cases\_draft.xlsx

test\_cases

```



目标：



```text

evaluation\_cases

```



\---



\## 5.2 字段映射



| Excel字段               | 数据库字段                 | 目标类型         |

| --------------------- | --------------------- | ------------ |

| `case\_id`             | `case\_id`             | VARCHAR(32)  |

| `scenario\_type`       | `scenario\_type`       | VARCHAR(16)  |

| `category`            | `category`            | VARCHAR(16)  |

| `difficulty`          | `difficulty`          | VARCHAR(16)  |

| `source`              | `source`              | VARCHAR(16)  |

| `input\_message`       | `input\_message`       | TEXT         |

| `expected\_intent`     | `expected\_intent`     | VARCHAR(16)  |

| `expected\_handoff`    | `expected\_handoff`    | BOOLEAN      |

| `expected\_answer`     | `expected\_answer`     | TEXT         |

| `expected\_sku\_ids`    | `expected\_sku\_ids`    | TEXT\[]       |

| `must\_contain\_all`    | `must\_contain\_all`    | TEXT\[]       |

| `must\_contain\_any`    | `must\_contain\_any`    | TEXT\[]       |

| `must\_not\_contain`    | `must\_not\_contain`    | TEXT\[]       |

| `allowed\_phrases`     | `allowed\_phrases`     | TEXT\[]       |

| `expected\_source`     | `expected\_source`     | TEXT\[]       |

| `is\_critical`         | `is\_critical`         | BOOLEAN      |

| `human\_score\_target`  | `human\_score\_target`  | NUMERIC(3,1) |

| `verification\_status` | `verification\_status` | VARCHAR(16)  |

| `notes`               | `notes`               | TEXT         |



系统生成：



| 数据库字段             | 生成方式     |

| ----------------- | -------- |

| `import\_batch\_id` | 当前导入批次主键 |

| `created\_at`      | 当前时间     |

| `updated\_at`      | 当前时间     |



\---



\## 5.3 用例枚举校验



`scenario\_type`：



```text

core

boundary

risk

```



`category`：



```text

spec

quality

price

logistics

escalation

```



`expected\_intent`：



```text

spec

quality

price

logistics

escalation

unknown

```



`difficulty`：



```text

easy

medium

hard

```



`source`：



```text

manual

real\_chat

```



`verification\_status`：



```text

pending

verified

rejected

```



\---



\## 5.4 SKU关联校验



`expected\_sku\_ids` 中的每个SKU必须：



1\. 符合 `SKU` 加三位数字格式；

2\. 存在于 `products.sku\_id`；

3\. 当前为有效产品，或测试说明中明确允许历史SKU。



当前默认要求：



```text

products.is\_active=true

```



如果存在无效SKU：



```text

测试用例整批导入失败

```



\---



\## 5.5 判定短语规则



评测脚本执行顺序：



```text

1\. 读取actual\_answer

2\. 暂时屏蔽allowed\_phrases中的完整短语

3\. 检查must\_not\_contain

4\. 恢复原始actual\_answer

5\. 检查must\_contain\_all

6\. 检查must\_contain\_any

```



`must\_contain\_all`：



```text

数组为空 → 自动通过

数组非空 → 每一项都必须命中

```



`must\_contain\_any`：



```text

数组为空 → 自动通过

数组非空 → 至少一项命中

```



`must\_not\_contain`：



```text

数组为空 → 自动通过

数组非空 → 任意一项命中即失败

```



`allowed\_phrases` 只用于减少否定表达误判，不代表该短语一定正确。



\---



\## 5.6 测试用例更新策略



同一 `case\_id` 已存在时使用：



```text

UPSERT

```



允许更新除以下字段外的其他业务字段：



```text

id

case\_id

created\_at

```



当前 `pending` 用例允许导入数据库用于本地评测开发。



但正式门控评测默认只统计：



```text

verification\_status=verified

```



如果开发阶段需要运行 pending 用例，评测运行必须在配置快照中记录：



```text

include\_pending=true

```



\---



\# 6. 四类问答文件映射



\## 6.1 公共字段



四类问答统一使用：



```text

qa\_id

source\_group\_id

primary\_intent

secondary\_intents

intent\_subtype

question\_raw

question\_normalized

answer\_raw

answer\_standard

related\_sku\_ids

required\_fields

answer\_source

handoff\_required

risk\_flags

verification\_status

review\_notes

```



多值字段：



```text

secondary\_intents

related\_sku\_ids

required\_fields

answer\_source

risk\_flags

```



统一按英文分号拆分。



\---



\## 6.2 规格问答



来源：



```text

spec\_questions.xlsx

```



v0.1阶段不写入独立数据库表。



用途：



\* 意图分类few-shot；

\* 规格Handler测试；

\* Prompt示例；

\* 业务规则核验。



不得将规格问答作为产品参数事实来源。



产品参数必须来自：



```text

PostgreSQL products

```



\---



\## 6.3 价格问答



来源：



```text

price\_questions.xlsx

```



v0.1阶段不写入向量库，也不写入正式价格表。



用途：



\* 价格意图识别；

\* 价格风控测试；

\* 人工转接测试；

\* 价格话术模板验证。



价格类记录必须满足：



```text

handoff\_required=true

```



任何原始具体价格只能保留在：



```text

answer\_raw

```



不得进入：



```text

自动对客回答

Qdrant正式知识库

LLM Prompt中的可引用事实

```



\---



\## 6.4 品质问答



来源：



```text

quality\_questions.xlsx

```



目标：



```text

knowledge\_chunks

Qdrant quality\_kb

```



每条审核后的问答对应一个知识分片。



\---



\## 6.5 物流问答



来源：



```text

logistics\_questions.xlsx

```



目标：



```text

knowledge\_chunks

Qdrant logistics\_kb

```



每条审核后的问答对应一个知识分片。



未核验金额、赔付、发票、退换货和承运商政策不得进入正式向量库。



\---



\# 7. 品质与物流知识分片映射



\## 7.1 数据库结构补充要求



为了完整保存问答来源和风险信息，`knowledge\_chunks` 应在 Alembic 实现前补充：



| 字段                | 类型     | 可空 | 说明                       |

| ----------------- | ------ | -: | ------------------------ |

| `import\_batch\_id` | BIGINT |  是 | 关联data\_import\_batches.id |

| `metadata`        | JSONB  |  否 | 默认空对象                    |



外键：



```text

knowledge\_chunks.import\_batch\_id

→ data\_import\_batches.id

ON DELETE SET NULL

```



必须同步修改：



```text

docs/data/database\_schema\_v0.1.md

```



\---



\## 7.2 knowledge\_chunks字段映射



| 来源字段                  | knowledge\_chunks字段    | 说明                      |

| --------------------- | --------------------- | ----------------------- |

| 系统生成                  | `chunk\_id`            | UUID                    |

| 文件类别                  | `knowledge\_type`      | quality或logistics       |

| 文件类别                  | `collection\_name`     | quality\_kb或logistics\_kb |

| 文件名                   | `source\_file`         | 原始文件名                   |

| `qa\_id`               | `source\_record\_id`    | 问答编号                    |

| 文件版本                  | `source\_version`      | 当前数据版本                  |

| 组合文本                  | `chunk\_text`          | 标准化分片文本                 |

| chunk\_text            | `content\_hash`        | SHA256                  |

| 系统生成                  | `qdrant\_point\_id`     | 写入Qdrant后填写             |

| `verification\_status` | `verification\_status` | 原样映射                    |

| 状态规则                  | `is\_active`           | rejected为false，其他默认true |

| 当前批次                  | `import\_batch\_id`     | 导入批次                    |

| 补充字段                  | `metadata`            | 风险、来源和业务信息              |

| 当前时间                  | `created\_at`          | 创建时间                    |

| 当前时间                  | `updated\_at`          | 更新时间                    |



\---



\## 7.3 chunk\_text生成规则



固定模板：



```text

标准问题：{question\_normalized}

原始问法：{question\_raw}

标准回答：{answer\_standard}

```



如果原始问法与标准问题完全相同，可以省略原始问法：



```text

标准问题：{question\_normalized}

标准回答：{answer\_standard}

```



不得写入：



```text

answer\_raw

```



原因是原始回答可能包含：



\* 错误SKU事实；

\* 过期政策；

\* 价格数字；

\* 未经核验的性能结论；

\* 不合规承诺。



\---



\## 7.4 metadata结构



建议保存：



```json

{

&#x20; "primary\_intent": "quality",

&#x20; "secondary\_intents": \[],

&#x20; "intent\_subtype": "material\_query",

&#x20; "related\_sku\_ids": \["SKU001"],

&#x20; "required\_fields": \["material", "surface\_treatment"],

&#x20; "answer\_source": \["sku\_master.xlsx", "business\_rules.md"],

&#x20; "handoff\_required": false,

&#x20; "risk\_flags": \[],

&#x20; "review\_notes": null

}

```



`metadata` 只保存结构化辅助信息，不保存Embedding向量。



\---



\## 7.5 chunk\_id生成



推荐使用确定性的 UUIDv5。



生成输入：



```text

source\_file|source\_record\_id|source\_version|content\_hash

```



优势：



\* 同一内容重复导入时ID稳定；

\* 内容变化后自动生成新ID；

\* 可以识别旧分片和新分片；

\* 方便PostgreSQL与Qdrant关联。



\---



\## 7.6 Qdrant Point ID



推荐：



```text

qdrant\_point\_id = chunk\_id

```



这样 PostgreSQL 和 Qdrant 使用同一个 UUID。



Qdrant payload 至少包含：



```json

{

&#x20; "chunk\_id": "<UUID>",

&#x20; "knowledge\_type": "quality",

&#x20; "source\_file": "quality\_questions.xlsx",

&#x20; "source\_record\_id": "QUAL0001",

&#x20; "verification\_status": "verified",

&#x20; "related\_sku\_ids": \["SKU001"],

&#x20; "content\_hash": "<SHA256>"

}

```



\---



\## 7.7 向量化资格



正式 Collection 只允许：



```text

verification\_status=verified

is\_active=true

handoff\_required=false

risk\_flags中不存在阻止自动回答的风险

```



当前 Phase 0 问答主要为：



```text

verification\_status=pending

```



因此可以：



1\. 先写入 PostgreSQL `knowledge\_chunks`；

2\. `qdrant\_point\_id` 保持NULL；

3\. 不进入正式 Collection；

4\. 或进入明确命名的测试 Collection。



禁止将 pending 和 verified 数据混入同一个正式 Collection。



\---



\# 8. 业务规则文件映射



\## 8.1 Markdown作为权威原始来源



原始规则：



```text

data/uploads/conversations/business\_rules.md

```



该文件负责：



\* 人工阅读；

\* 规则审批；

\* 版本记录；

\* 业务边界说明。



运行时 Handler 不直接反复解析 Markdown。



\---



\## 8.2 JSON作为运行时配置



后续解析目标：



```text

data/parsed/pricing/business\_rules.json

data/parsed/logistics/logistics\_rules.json

```



JSON配置必须包含：



```text

schema\_version

rule\_version

verification\_status

enabled

effective\_from

effective\_to

updated\_at

rules

```



未核验规则：



```json

{

&#x20; "verification\_status": "pending",

&#x20; "enabled": false,

&#x20; "amount": null,

&#x20; "currency": "CNY",

&#x20; "customer\_visible": false

}

```



\---



\# 9. 导入批次映射



每次导入前创建：



```text

data\_import\_batches

```



\## 9.1 SKU导入批次



```text

data\_type=sku\_master

source\_file=sku\_master.xlsx

record\_count=100

```



\## 9.2 测试用例导入批次



```text

data\_type=evaluation\_cases

source\_file=test\_cases\_draft.xlsx

record\_count=50

```



\## 9.3 品质问答导入批次



```text

data\_type=quality\_questions

source\_file=quality\_questions.xlsx

```



\## 9.4 物流问答导入批次



```text

data\_type=logistics\_questions

source\_file=logistics\_questions.xlsx

```



\---



\# 10. 导入错误分类



错误代码建议固定为：



| 错误代码                    | 含义         |

| ----------------------- | ---------- |

| `FILE\_NOT\_FOUND`        | 文件不存在      |

| `FILE\_ALREADY\_IMPORTED` | 相同文件已成功导入  |

| `SHEET\_NOT\_FOUND`       | 工作表不存在     |

| `HEADER\_MISMATCH`       | 表头不一致      |

| `EMPTY\_REQUIRED\_FIELD`  | 必填字段为空     |

| `INVALID\_ENUM`          | 枚举值不合法     |

| `INVALID\_NUMBER`        | 数值无法转换     |

| `INVALID\_BOOLEAN`       | 布尔值不合法     |

| `INVALID\_THREAD\_SPEC`   | 螺纹格式不合法    |

| `INVALID\_TAPER\_RATIO`   | 锥度比不合法     |

| `DUPLICATE\_BUSINESS\_ID` | SKU或用例编号重复 |

| `SKU\_NOT\_FOUND`         | 关联SKU不存在   |

| `UNVERIFIED\_CONTENT`    | 内容未核验      |

| `DATABASE\_ERROR`        | 数据库操作失败    |

| `UNEXPECTED\_ERROR`      | 未分类异常      |



`error\_summary` 应记录：



```json

{

&#x20; "errors": \[

&#x20;   {

&#x20;     "code": "INVALID\_THREAD\_SPEC",

&#x20;     "sheet": "Sheet1",

&#x20;     "row": 12,

&#x20;     "column": "螺纹规格",

&#x20;     "value": "M8",

&#x20;     "message": "螺纹规格缺少牙距"

&#x20;   }

&#x20; ]

}

```



不得在错误日志中记录：



\* 数据库密码；

\* API Key；

\* 客户隐私信息。



\---



\# 11. 事务与回滚



\## 11.1 SKU和测试用例



采用严格模式：



```text

全部校验通过 → 整批提交

任一关键错误 → 整批回滚

```



\## 11.2 品质和物流分片



第一版同样采用整批事务。



PostgreSQL元数据提交成功后，才开始写入Qdrant。



如果Qdrant写入失败：



1\. PostgreSQL记录保留；

2\. `qdrant\_point\_id`保持NULL；

3\. 导入批次标记为`partial\_success`；

4\. 允许后续重试向量化；

5\. 不重复创建知识分片。



\---



\# 12. 数据导入顺序



Phase 1固定顺序：



```text

1\. sku\_master.xlsx

2\. test\_cases\_draft.xlsx

3\. quality\_questions.xlsx

4\. logistics\_questions.xlsx

5\. business\_rules.md解析

6\. Qdrant向量化

```



原因：



\* 测试用例需要校验SKU；

\* 品质和物流问答可能引用SKU；

\* Qdrant写入依赖PostgreSQL中的knowledge\_chunks；

\* 规则配置需要在Handler开发前完成。



\---



\# 13. 导入后验收



\## 13.1 products



必须满足：



```text

记录数=100

sku\_id唯一

无无效螺纹规格

OEM编号保留前导零

锥度“无”已转换为NULL

所有来源行可追溯

```



\## 13.2 evaluation\_cases



必须满足：



```text

记录数=50

case\_id唯一

scenario\_type分布=30/10/10

所有expected\_sku\_ids存在

数组字段无空字符串

所有状态仍为pending

```



\## 13.3 knowledge\_chunks



导入品质与物流后必须满足：



```text

每个qa\_id对应一个chunk

content\_hash存在

source\_record\_id可追溯

pending记录未进入正式Collection

rejected记录is\_active=false

```



\---



\# 14. 数据库设计同步修改



在创建 SQLAlchemy 模型和 Alembic 迁移前，需要在：



```text

docs/data/database\_schema\_v0.1.md

```



的 `knowledge\_chunks` 表中补充：



```text

import\_batch\_id BIGINT NULL

metadata JSONB NOT NULL DEFAULT '{}'

```



外键关系汇总中补充：



```text

knowledge\_chunks.import\_batch\_id

→ data\_import\_batches.id

ON DELETE SET NULL

```



索引建议补充：



```text

INDEX ON import\_batch\_id

GIN INDEX ON metadata

```



\---



\# 15. 验收清单



\* \[ ] 所有数据源项目路径已经固定；

\* \[ ] 所有工作表名称已经固定；

\* \[ ] SKU字段映射完整；

\* \[ ] 测试用例19个字段映射完整；

\* \[ ] 多值字段统一为英文分号；

\* \[ ] 数组空值统一转换为空数组；

\* \[ ] `锥度比=无`转换为NULL；

\* \[ ] OEM编号始终按文本读取；

\* \[ ] 品质和物流问答按一问一答生成chunk；

\* \[ ] 原始错误回答不进入chunk\_text；

\* \[ ] pending数据不进入正式Qdrant Collection；

\* \[ ] 价格问答不进入向量库；

\* \[ ] 文件SHA256写入导入批次；

\* \[ ] 导入失败可以回滚和追溯；

\* \[ ] `knowledge\_chunks`补充了导入批次和metadata字段；

\* \[ ] 所有导入过程不修改原始文件。



\---



\# 16. 版本变更要求



任何Excel字段、数据库字段或转换规则变化，必须同步更新：



```text

docs/data/excel\_to\_database\_mapping.md

docs/data/database\_schema\_v0.1.md

SQLAlchemy ORM模型

Pydantic Schema

Alembic迁移

导入脚本

单元测试

```



不得仅修改导入脚本而不更新映射文档。

