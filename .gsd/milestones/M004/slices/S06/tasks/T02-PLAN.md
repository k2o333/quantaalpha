# T02: fewshot.py 集成 + "共性总结" prompt 模板

**Slice:** S06
**Milestone:** M004

## Goal
在 fewshot.py 中新增 `query_active_factors_RAG()` 方法，使用向量检索替代 Jaccard，并在 prompts.yaml 添加共性总结模板。

## Must-Haves

### Truths
- `query_active_factors_RAG()` 方法存在，fallback 到 Jaccard 当 ChromaDB 不可用
- prompts.yaml 包含 "共性总结，演绎新因子" 模板
- LLM prompt 可注入 RAG 检索结果

### Artifacts
- `third_party/quantaalpha/quantaalpha/factors/fewshot.py` — RAG 检索方法
- `third_party/quantaalpha/quantaalpha/factors/prompts/prompts.yaml` — prompt 模板

### Key Links
- 依赖 S06/T01 完成的 vector_store.py
- S06/T03 测试依赖本任务完成

## Steps
1. 阅读 `fewshot.py`，找到 few-shot 检索入口。
2. 添加 `query_active_factors_RAG(query_text, top_k)` 方法:
   - 尝试调用 `vector_store.query_similar()`
   - ChromaDB 不可用时 fallback 到现有 Jaccard
3. 在 prompts.yaml 中添加新模板:
   ```yaml
   rag_commonality_template: |
     基于以下相似因子 {factors}，总结它们的共性模式，
     然后演绎出一个新的、与现有因子有差异的因子。
   ```
4. 在 `build_fewshot_prompt()` 中支持 RAG 模式。
5. 用 `py_compile` 验证语法。

## Context
- 本任务依赖 T01 完成的 vector_store.py
- fallback 机制确保在 ChromaDB 不可用时系统仍可运行
