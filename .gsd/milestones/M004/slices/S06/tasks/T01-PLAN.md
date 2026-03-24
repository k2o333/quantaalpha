# T01: vector_store.py 核心模块

**Slice:** S06
**Milestone:** M004

## Goal
创建 FactorVectorStore 类，封装 ChromaDB 操作，实现因子 embedding 存储和向量相似度检索。

## Must-Haves

### Truths
- `FactorVectorStore` 类支持: `add_factor()`, `query_similar()`, `remove_factor()`, `sync_from_library()`
- 使用 ChromaDB in-memory 模式（开发便捷）
- embedding 输入包含: factor_expression + tags + data_requirements
- ChromaDB 作为可选依赖，缺失时明确报错

### Artifacts
- `third_party/quantaalpha/quantaalpha/factors/vector_store.py` — ChromaDB 封装
- `requirements.txt` 或 `pyproject.toml` — 添加 chromadb 依赖

### Key Links
- S06/T02 fewshot 集成依赖本任务完成
- S03 的 tags 字段作为 embedding 元数据

## Steps
1. 创建 `vector_store.py`，定义 `FactorVectorStore` 类。
2. 在 `__init__` 中初始化 ChromaDB client（in-memory 模式）。
3. 实现 `add_factor(factor_entry)`:
   - 构造 embedding 文本（expression + tags + data_requirements）
   - 调用 embedding 模型获取向量
   - 存入 ChromaDB
4. 实现 `query_similar(query_text, top_k)`:
   - 获取 query embedding
   - ChromaDB similarity search
   - 返回 Top-K 结果
5. 实现 `remove_factor(factor_id)` 和 `sync_from_library()`。
6. 添加 ChromaDB 可选导入检查，缺失时报错提示。
7. 用 `py_compile` 验证语法。

## Context
- 上游来源: `docs/drafts/mining/factor_mining_requirements.md §D.3.2`
- 向量模型可使用 sentence-transformers 或 OpenAI embeddings
- fallback 策略在 T02 实现
