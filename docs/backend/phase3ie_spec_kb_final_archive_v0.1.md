# Phase 3-I-E Spec KB Final Archive v0.1

## 阶段结论

Phase 3-I-E 已完成。

本阶段完成 Spec KB 真实 Qdrant 集成闭环：

- Spec 源文件检查通过
- Spec KB Chunk Builder 检查通过
- Qdrant collection `spec_kb_v1` 创建并验证通过
- 23 条 Spec chunks 写入 PostgreSQL `knowledge_chunks`
- 23 条 Spec points 写入 Qdrant `spec_kb_v1`
- Spec KB Qdrant retrieval 检查通过
- `SpecKBQdrantRetriever` Adapter 检查通过
- Workflow 接入 Spec KB Retriever
- Workflow 级 Spec KB 检索集成检查通过
- Spec KB Grounded E2E 检查通过
- Phase 3-I-E Total Regression 通过，且 Price / Logistics / Quality 既有链路未被破坏

## Collection Baseline

- Collection: `spec_kb_v1`
- Vector size: `1024`
- Distance: `Cosine`
- Embedding model: `BAAI/bge-m3`
- Embedding endpoint: `http://127.0.0.1:8088/embed`
- Source file: `spec_questions.xlsx`
- Point count: `23`
- Module: `spec`

## 当前真实 KB Collection

- Quality: `quality_kb_v1`
- Logistics: `logistics_kb_v1`
- Price: `price_kb_v1`
- Spec: `spec_kb_v1`

## 关键代码文件

- `backend/app/agent/rag/spec_chunk_builder.py`
- `backend/app/agent/rag/spec_kb_retriever.py`
- `backend/app/agent/rag/__init__.py`
- `backend/app/agent/workflow.py`

## 关键检查脚本

- `backend/scripts/check_spec_questions_file.py`
- `backend/scripts/check_spec_kb_chunk_builder.py`
- `backend/scripts/create_spec_qdrant_collection.py`
- `backend/scripts/upsert_spec_kb_chunks_to_postgres.py`
- `backend/scripts/upsert_spec_kb_chunks_to_qdrant.py`
- `backend/scripts/check_spec_kb_qdrant_retrieval.py`
- `backend/scripts/check_spec_kb_retriever_adapter.py`
- `backend/scripts/check_workflow_spec_kb_retrieval_integration.py`
- `backend/scripts/check_spec_kb_grounded_e2e.py`
- `backend/scripts/check_phase3ie_spec_kb_total_regression.py`

## 已执行过的阶段性补丁脚本

以下脚本用于阶段修复或诊断，已执行过，不应在不了解上下文时重复执行：

- `backend/scripts/patch_workflow_spec_kb_retriever.py`
- `backend/scripts/fix_workflow_spec_e2e_metadata_and_route.py`
- `backend/scripts/fix_workflow_spec_metadata_final.py`
- `backend/scripts/create_spec_kb_grounded_e2e_from_price.py`
- `backend/scripts/inspect_workflow_price_kb_context.py`

## Embedding 服务修复记录

本阶段发现 TEI `/health` 与 `/info` 正常，但 `/embed` 返回 `Empty reply from server`。

判断为 TEI HTTP 服务存活但模型推理阶段异常。最终在：

- `infra/embedding/bge-m3/compose.yaml`

中加入：

- `--dtype float32`
- `--max-client-batch-size 8`
- `--max-batch-tokens 4096`

修复后 `/embed` 恢复，Spec KB Qdrant upsert 成功。

## Payload 修复记录

初次 Spec Qdrant retrieval 检查发现 payload 中 `answer_standard` / `question_normalized` 为空。

修复方式：

- 补齐 PostgreSQL upsert metadata 字段
- 重新 upsert PostgreSQL
- 重新 upsert Qdrant

## Workflow 修复记录

实际 Workflow 路径为：

- `backend/app/agent/workflow.py`

不是：

- `backend/app/agent/graph/workflow.py`

Spec KB 接入后补充了：

- `retrieval_selected_module=spec`
- `retrieval_hit_count`
- state extras 写入使用 `cast(dict[str, Any], new_state)` 避免 TypedDict 静态错误

## Spec Grounded E2E Cases

通过用例：

1. `SKU001是什么规格？`
2. `SKU001的螺纹规格是多少？`
3. `M10的球头有哪些？`
4. `杆长120mm有吗？`
5. `这个球头能通用适配吗？`

## Spec 安全边界

规格类回答不得承诺未经验证的适配关系。禁止输出倾向：

- 万能适配
- 百分百适配
- 一定适配
- 保证适配
- 全部车型都能用
- 不用核对直接能用

## Final Regression

总回归脚本：

- `backend/scripts/check_phase3ie_spec_kb_total_regression.py`

结果：

- Phase 3-I-E Spec KB total regression passed

## 状态

Phase 3-I-E：完成。