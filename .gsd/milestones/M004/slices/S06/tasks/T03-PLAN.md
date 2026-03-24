# T03: 单元测试 + 集成测试

**Slice:** S06
**Milestone:** M004

## Goal
为 vector_store.py 和 fewshot RAG 集成编写完整测试，覆盖 add/query/remove/sync 和 fallback 场景。

## Must-Haves

### Truths
- 测试覆盖所有 vector_store 操作
- 测试覆盖 fallback 逻辑
- 端到端测试覆盖 fewshot → vector_store → result
- 15+ 测试用例

### Artifacts
- `third_party/quantaalpha/tests/test_vector_store.py` — 完整测试套件

### Key Links
- 依赖 S06/T01 和 T02 完成

## Steps
1. 创建 `test_vector_store.py`。
2. Mock ChromaDB client 和 embedding 模型。
3. 编写测试用例:
   - `test_add_factor`: 添加因子并验证存储
   - `test_query_similar`: 查询并验证返回顺序
   - `test_remove_factor`: 删除后查询返回空
   - `test_sync_from_library`: 同步测试
   - `test_fallback_on_missing_chromadb`: fallback 逻辑
   - `test_empty_library_sync`: 空库同步
   - `test_duplicate_factor_handling`: 重复因子处理
   - `test_fewshot_rag_integration`: 端到端集成
4. 运行 pytest，确认 15+ 测试通过。

## Context
- 本任务依赖 T01 和 T02 完成
- 使用 mock 避免 ChromaDB 真实连接
