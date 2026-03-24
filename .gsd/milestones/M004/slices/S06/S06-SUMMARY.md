---
id: S06
parent: M004
milestone: M004
provides:
  - vector_store.py: ChromaDB-backed FactorVectorStore
  - fewshot.py: RAG-enhanced few-shot prompt generation
  - prompts.yaml: Pattern synthesis templates
  - test_vector_store.py: 34 test cases
requires:
  - slice: S03
    provides: Factor classification tags (tags field in library.py)
affects:
  - S08: RAG vector retrieval (知新流程)
key_files:
  - quantaalpha/factors/vector_store.py
  - quantaalpha/factors/fewshot.py
  - quantaalpha/factors/prompts/prompts.yaml
  - quantaalpha/tests/test_vector_store.py
key_decisions:
  - ChromaDB optional (fallback to Jaccard when unavailable)
  - Text normalization removes special chars for matching
  - Cosine distance for ChromaDB collection
  - Singleton pattern for vector store instance
patterns_established:
  - Optional dependency pattern: CHROMADB_AVAILABLE guard
  - Normalized Jaccard fallback with re.sub
  - Singleton vector store with reset function
observability_surfaces:
  - CHROMADB_AVAILABLE constant
  - store.count() for vector store size
  - Test results via pytest
drill_down_paths:
  - S06/tasks/T01-SUMMARY.md
  - S06/tasks/T02-SUMMARY.md
  - S06/tasks/T03-SUMMARY.md
duration: ~120m
verification_result: passed
completed_at: 2026-03-24T01:58:00+08:00
---

# S06: RAG 向量检索

**向量检索替代 Jaccard 文本重叠，ChromaDB 可选降级**

## What Happened

实现了一个完整的 RAG 向量检索系统，替代原有的 Jaccard 文本重叠匹配。核心组件：

1. **FactorVectorStore**: 基于 ChromaDB 的向量数据库封装
   - 支持 in-memory 和持久化模式
   - 自动 fallback 到 normalized Jaccard（ChromaDB 不可用时）
   - 因子 embedding 包含表达式 + 标签 + 元数据

2. **fewshot.py**: RAG 增强的 few-shot 模块
   - `query_active_factors_RAG()`: 向量检索 + Jaccard 降级
   - `build_fewshot_context()`: 格式化因子用于 prompts
   - `summarize_common_patterns()`: 提取共性模式

3. **prompts.yaml**: 新增模板
   - `common_patterns_summary`: 共性分析模板
   - `factor_context_template`: 相似因子展示

## Verification

| Check | Result |
|-------|--------|
| `python -m py_compile vector_store.py` | ✓ |
| `python -m py_compile fewshot.py` | ✓ |
| `grep "ChromaDB" vector_store.py` | ✓ |
| `grep "chromadb" requirements.txt` | ✓ |
| `pytest tests/test_vector_store.py -v` | 34 passed |

## New Requirements Surfaced

(none)

## Deviations

1. **Text Normalization**: 原计划直接比较字符串，实际实现使用正则去除特殊字符 (`$`, `(`, `)` 等) 后再匹配，提高匹配率

## Known Limitations

1. **ChromaDB not installed**: 当前环境无 ChromaDB，运行在 Jaccard fallback 模式
2. **Embedding quality**: 使用默认 sentence-transformers 模型，未针对金融领域微调
3. **No hybrid search**: 当前仅支持向量或文本，暂未实现混合搜索

## Follow-ups

1. 安装 ChromaDB 并测试真实向量检索性能
2. 考虑使用金融领域预训练 embedding 模型
3. 实现 hybrid search 结合向量和关键词匹配

## Files Created/Modified

- `quantaalpha/factors/vector_store.py` — FactorVectorStore 类 (new)
- `quantaalpha/factors/fewshot.py` — RAG 增强模块 (new)
- `quantaalpha/factors/prompts/prompts.yaml` — RAG 模板 (modified)
- `quantaalpha/requirements.txt` — 添加 chromadb 依赖 (modified)
- `quantaalpha/tests/test_vector_store.py` — 34 项测试 (new)

## Forward Intelligence

### What the next slice should know

- **S08 (24H 调度中心)**: RAG 模块已就绪，可通过 `query_active_factors_RAG()` 获取相似因子用于"知新"流程
- **依赖 S03**: 因子必须带有 tags 字段才能获得完整的 embedding 语义
- **Optional ChromaDB**: 代码设计已考虑降级，实际部署时需要 `pip install chromadb sentence-transformers`

### What's fragile

- **Jaccard fallback 匹配精度**: 当前 normalization 可能过度简化，对于短表达式效果较差
- **Singleton 模式**: `reset_vector_store()` 需要在测试间调用，否则可能状态污染
