# T01: 因子条目 tags 字段定义 + library.py 集成

**Slice:** S03
**Milestone:** M004

## Goal
为因子条目新增完整的分类标签系统，支持 category / data_dependency / market_environment / time_horizon 四维标签，并在 library.py 中实现。

## Must-Haves

### Truths
- `_normalize_factor_entry()` 中新增 `tags` 字段，包含 4 个子标签列表
- 标签枚举定义完整: category, data_dependency, market_environment, time_horizon
- 新建因子条目时 `tags` 有默认值

### Artifacts
- `third_party/quantaalpha/quantaalpha/factors/library.py` — tags 字段和枚举定义
- `third_party/quantaalpha/quantaalpha/tests/test_factor_tags.py` — 16 tests covering tags initialization, migration, and persistence

## Expected Output
- `third_party/quantaalpha/quantaalpha/factors/library.py`
  - `CATEGORY_TAGS`, `DATA_DEPENDENCY_TAGS`, `MARKET_ENVIRONMENT_TAGS`, `TIME_HORIZON_TAGS` constants (module-level)
  - `TAG_DEFINITIONS` dict mapping tag key → list of valid values
  - `DEFAULT_TAGS` default empty structure
  - `tags` field added to `_normalize_factor_entry()` with migration-safe logic
- `third_party/quantaalpha/quantaalpha/tests/test_factor_tags.py` (new)

### Key Links
- S03/T02 fewshot 集成依赖本任务的 tags 字段定义
- S06 向量检索依赖 tags 作为 embedding 元数据

## Steps
1. 阅读 `library.py`，找到因子条目结构定义位置。
2. 定义标签枚举常量:
   ```python
   CATEGORY_TAGS = ["momentum", "reversal", "value", "quality", "liquidity"]
   DATA_DEPENDENCY_TAGS = ["price_volume", "financial", "alternative"]
   MARKET_ENVIRONMENT_TAGS = ["bull", "bear", "sideways", "high_vol"]
   TIME_HORIZON_TAGS = ["short_term", "intraday", "medium_term"]
   ```
3. 在因子条目 schema 中添加 `tags` 字段。
4. 在 `_normalize_factor_entry()` 中设置默认值（空列表）。
5. 用 `py_compile` 验证语法。

## Context
- 上游来源: `docs/drafts/mining/factor_mining_requirements.md §D.3.1`
- M003 S02 的 fewshot.py relatedness 评分逻辑可供参考
- 本任务不修改评分逻辑（留给 T02）

## Observability Impact
- **New signals:** `DEFAULT_TAGS` and `TAG_DEFINITIONS` are module-level exports, inspectable via `python -c "from quantaalpha.factors.library import DEFAULT_TAGS, TAG_DEFINITIONS; print(DEFAULT_TAGS)"`.
- **Runtime surface:** Every factor entry created/normalized via `FactorLibraryManager` will now contain a `tags` field. An agent can verify tag presence with `manager.get_factor(fid)["tags"]`.
- **Failure state visibility:** If an entry has a malformed `tags` value (non-dict), the `isinstance` guard in `_normalize_factor_entry()` prevents a crash and falls back to `DEFAULT_TAGS`, emitting no error. The entry will silently get the default tags structure.
- **Dependency for downstream:** T02's fewshot.py `relatedness` scoring reads `entry["tags"]` directly; missing tags would produce a `KeyError` at T02 runtime. T01 prevents that by guaranteeing the field always exists.
