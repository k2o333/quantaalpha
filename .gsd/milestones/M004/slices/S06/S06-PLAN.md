# S06: RAG 向量检索

**Goal:** 引入 ChromaDB 向量数据库，将因子表达式和元数据编码为 embedding，实现向量相似度检索替代 Jaccard 文本重叠。
**Demo:** 查询 "momentum reversal" 返回 embedding 最相似的 Top-K 因子，附带 IC/status 元数据。

## Must-Haves
- `vector_store.py` 新模块封装 ChromaDB 操作: `add_factor()`, `query_similar()`, `remove_factor()`, `sync_from_library()`
- 因子 embedding 包含: factor_expression + tags + data_requirements
- `fewshot.py` 新增 `query_active_factors_RAG()` 方法，使用向量检索替代 Jaccard
- `prompts.yaml` few-shot 模板支持 "总结共性，演绎新因子" 模式
- ChromaDB 作为可选依赖，fallback 到现有 Jaccard 方案
- 单元测试覆盖: 添加/查询/删除/同步/fallback

## Proof Level
- This slice proves: **contract + integration**
- Real runtime required: yes (ChromaDB in-memory mode)
- Human/UAT required: no

## Verification
- `python -m py_compile quantaalpha/factors/vector_store.py`
- `pytest quantaalpha/tests/test_vector_store.py -v`
- `grep "ChromaDB\|chromadb" quantaalpha/factors/vector_store.py` returns >= 1

## Tasks

- [x] **T01: vector_store.py 核心模块** `est:40m`
  - Why: ChromaDB 集成是本 Slice 的基础设施
  - Files: `quantaalpha/factors/vector_store.py`
  - Do: 创建 FactorVectorStore 类，实现 add_factor / query_similar / remove_factor / sync_from_library；使用 ChromaDB in-memory 模式；定义 embedding 输入格式
  - Verify: py_compile 通过
  - Done when: FactorVectorStore 类完整可用

- [x] **T02: fewshot.py 集成 + "共性总结" prompt 模板** `est:30m`
  - Why: 向量检索需要接入 LLM prompt 流程
  - Files: `quantaalpha/factors/fewshot.py`, `quantaalpha/factors/prompts/prompts.yaml`
  - Do: 新增 query_active_factors_RAG()；添加 fallback 逻辑；在 prompts.yaml 添加共性总结模板
  - Verify: py_compile 通过
  - Done when: RAG 查询可用，fallback 逻辑正常

- [x] **T03: 单元测试 + 集成测试** `est:25m`
  - Why: 验证完整的 add → query → fewshot 流程
  - Files: `quantaalpha/tests/test_vector_store.py`
  - Do: 测试各操作、fallback、同步、端到端 fewshot 流程
  - Verify: pytest 通过
  - Done when: 15+ 测试通过

## Files Likely Touched
- `quantaalpha/factors/vector_store.py` (new)
- `quantaalpha/factors/fewshot.py` (modify)
- `quantaalpha/factors/prompts/prompts.yaml` (modify)
- `quantaalpha/tests/test_vector_store.py` (new)
- `requirements.txt` 或 `pyproject.toml` (modify — 添加 chromadb 依赖)

---
estimated_steps: 14
estimated_files: 5
