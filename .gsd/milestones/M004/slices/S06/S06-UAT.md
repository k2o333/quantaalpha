# S06 UAT: RAG 向量检索

## Preconditions

1. Python 3.10+ 环境
2. 可选: `pip install chromadb sentence-transformers` (测试降级模式可不安装)
3. 工作目录: `third_party/quantaalpha/`

## Test Cases

### TC01: 向量存储初始化

**Steps:**
1. `python -c "from quantaalpha.factors.vector_store import FactorVectorStore, CHROMADB_AVAILABLE; print(f'ChromaDB: {CHROMADB_AVAILABLE}'); store = FactorVectorStore(); print(f'Store ready, count: {store.count()}')"`

**Expected:**
- 无异常输出
- 显示 ChromaDB 可用状态
- Store count 为 0

---

### TC02: 添加因子

**Steps:**
1. 启动 Python REPL
2. 执行:
```python
from quantaalpha.factors.vector_store import FactorVectorStore

store = FactorVectorStore()
result = store.add_factor(
    factor_id="test_001",
    factor_expression="RANK(TS_MEAN($close, 20))",
    tags={"category": ["momentum"]},
    metadata={"status": "active", "ic": 0.05}
)
print(f"Added: {result}, Count: {store.count()}")
```

**Expected:**
- `Added: True, Count: 1`
- 无异常

---

### TC03: 查询相似因子

**Steps:**
1. 继续上一步 REPL
2. 执行:
```python
results = store.query_similar("momentum", top_k=5)
print(f"Results: {len(results)}")
for r in results:
    print(f"  - {r['factor_id']}: score={r['score']}")
```

**Expected:**
- 至少 1 个结果
- 结果包含 score (0-1)
- 结果按 score 降序排列

---

### TC04: 元数据过滤

**Steps:**
1. 添加不同状态的因子:
```python
store.add_factor("test_002", "DELTA($close, 1)", metadata={"status": "degraded"})
store.add_factor("test_003", "RANK($volume)", metadata={"status": "active"})
```

2. 查询仅 active 状态:
```python
results = store.query_similar("factor", top_k=10, filter_metadata={"status": "active"})
for r in results:
    print(f"{r['factor_id']}: {r['metadata']['status']}")
```

**Expected:**
- 仅返回 status="active" 的因子
- 不包含 test_002

---

### TC05: 从因子库同步

**Precondition:** 存在有效的 factor_library.json

**Steps:**
1. 准备测试库文件:
```python
import json
import tempfile
import os

temp_dir = tempfile.mkdtemp()
library_path = os.path.join(temp_dir, "test_lib.json")

library_data = {
    "metadata": {"version": "1.1", "total_factors": 1},
    "factors": {
        "sync_001": {
            "factor_id": "sync_001",
            "factor_expression": "RANK($close)",
            "factor_name": "Test Factor",
            "tags": {"category": ["momentum"]},
            "evaluation": {"status": "active"},
            "backtest_results": {"IC": 0.05}
        }
    }
}

with open(library_path, "w") as f:
    json.dump(library_data, f)
```

2. 同步:
```python
store.clear()
count = store.sync_from_library(library_path, filter_status="active")
print(f"Synced: {count} factors")
```

**Expected:**
- `Synced: 1 factors`
- store.count() == 1

---

### TC06: fewshot RAG 查询

**Steps:**
```python
from quantaalpha.factors.fewshot import query_active_factors_RAG, reset_vector_store

reset_vector_store()
factors = query_active_factors_RAG(
    query="momentum reversal",
    top_k=5,
    library_path=library_path,
    fallback_to_jaccard=True
)
print(f"Found: {len(factors)} factors")
```

**Expected:**
- 返回 0 或更多因子（取决于库内容）
- 无异常

---

### TC07: 共性模式总结

**Steps:**
```python
from quantaalpha.factors.fewshot import summarize_common_patterns

summary = summarize_common_patterns([
    {
        "factor_id": "f1",
        "factor_expression": "RANK(TS_MEAN($close, 20))",
        "tags": {"category": ["momentum"], "data_dependency": ["price_volume"]},
        "metadata": {"ic": 0.05}
    }
], "momentum")

print(summary)
```

**Expected:**
- 输出包含 "similar factors" 数量
- 输出包含标签统计
- 无异常

---

### TC08: Context 构建

**Steps:**
```python
from quantaalpha.factors.fewshot import build_fewshot_context

context = build_fewshot_context([
    {
        "factor_id": "f1",
        "factor_expression": "RANK($close)",
        "factor_name": "Price Rank",
        "score": 0.85,
        "tags": {"category": ["momentum"]},
        "metadata": {"ic": 0.05, "rank_ic": 0.04}
    }
])

print(context)
```

**Expected:**
- 包含 "Similar factors from the library"
- 包含因子名称、表达式、标签、IC
- 格式化为可读文本

---

### TC09: 删除因子

**Steps:**
```python
store.remove_factor("test_001")
print(f"After remove: {store.count()}")
```

**Expected:**
- count 减少 1
- 查询该因子无结果

---

### TC10: 清空存储

**Steps:**
```python
store.clear()
print(f"After clear: {store.count()}")
```

**Expected:**
- count == 0
- 所有因子被删除

---

### TC11: Jaccard 相似度计算

**Steps:**
```python
from quantaalpha.factors.fewshot import compute_jaccard_similarity

# 相同文本
score1 = compute_jaccard_similarity("momentum factor", "momentum factor")
print(f"Identical: {score1}")

# 部分重叠
score2 = compute_jaccard_similarity("momentum factor", "momentum reversal")
print(f"Partial: {score2}")

# 无重叠
score3 = compute_jaccard_similarity("momentum", "liquidity")
print(f"No overlap: {score3}")
```

**Expected:**
- Identical: 1.0
- Partial: 0.0 < score < 1.0
- No overlap: 0.0

---

### TC12: 单元测试执行

**Steps:**
```bash
cd third_party/quantaalpha
python -m pytest tests/test_vector_store.py -v
```

**Expected:**
- 34 passed
- 无 failed 或 error

---

## Edge Cases

### EC01: 空表达式添加

**Steps:**
```python
result = store.add_factor(factor_id="empty", factor_expression="")
```

**Expected:**
- 返回 False
- count 不增加

### EC02: 查询空存储

**Steps:**
```python
store.clear()
results = store.query_similar("test", top_k=5)
```

**Expected:**
- 返回空列表 []
- 无异常

### EC03: 从不存在文件同步

**Steps:**
```python
count = store.sync_from_library("/nonexistent/path.json")
```

**Expected:**
- 返回 0
- 无异常

## Success Criteria

All test cases pass with no exceptions. System gracefully degrades when ChromaDB unavailable.
