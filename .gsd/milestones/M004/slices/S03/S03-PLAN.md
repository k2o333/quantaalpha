# S03: 因子分类标签系统

**Goal:** 为因子条目新增分类标签系统，支持 category / data_dependency / market_environment / time_horizon 四维标签。
**Demo:** 创建或更新因子时可附带标签，fewshot 导出时标签参与 relatedness 评分。

## Must-Haves
- `_normalize_factor_entry()` 新增 `tags` 字段，包含 4 个子标签列表
- 标签枚举定义: category (momentum/reversal/value/quality/liquidity), data_dependency (price_volume/financial/alternative), market_environment (bull/bear/sideways/high_vol), time_horizon (short_term/intraday/medium_term)
- `fewshot.py` 的 relatedness 评分新增标签匹配维度（如 40% Jaccard + 30% 共享字段 + 30% 标签匹配）
- 单元测试覆盖标签初始化、标签匹配评分

## Proof Level
- This slice proves: **contract**
- Real runtime required: no
- Human/UAT required: no

## Verification
> **Note:** 文件位于 `third_party/quantaalpha/quantaalpha/` 下。项目根目录已有符号链接 `quantaalpha -> third_party/quantaalpha/quantaalpha`，可直接从根目录运行验证命令。

- `python -m py_compile quantaalpha/factors/library.py` → exit 0
- `python -m py_compile quantaalpha/factors/fewshot.py` → exit 0 (T02 创建文件后方可通过)
- `pytest quantaalpha/tests/test_factor_tags.py -v` → 16 passed
- `grep "tags" quantaalpha/factors/library.py` returns >= 3 (actual: 8)

## Observability / Diagnostics
- **`quantaalpha.factors.library.DEFAULT_TAGS`** — module-level constant exposes the 4-dimension tag schema at runtime for inspection.
- **`quantaalpha.factors.library.TAG_DEFINITIONS`** — dict of `{tag_key: [valid_values]}` for validation/debugging.
- **Diagnostic check:** `python -c "from quantaalpha.factors.library import DEFAULT_TAGS; import json; print(json.dumps(DEFAULT_TAGS))"` → prints default structure.
- **Failure visibility:** If `_normalize_factor_entry()` receives a non-dict `tags` value (e.g., a string or tuple), the migration-safe guard `isinstance(entry["tags"], dict)` prevents a crash and falls back to `DEFAULT_TAGS`.
- **Logging:** `library.py` logs factor saves with tag presence via `logger.info(f"Saved {len(sub_tasks)} factors …")`.

## Tasks

- [x] **T01: 因子条目 tags 字段定义 + library.py 集成** `est:25m`
  - Why: 标签字段是后续标签匹配和状态机的基础
  - Files: `quantaalpha/factors/library.py`
  - Do: 在 _normalize_factor_entry() 添加 tags 字段及默认值；定义标签枚举常量
  - Verify: py_compile 通过
  - Done when: 新建因子条目包含完整 tags 结构

- [x] **T02: fewshot.py relatedness 评分增强 + 测试** `est:25m`
  - Why: 标签需要实际参与检索评分才有价值
  - Files: `quantaalpha/factors/fewshot.py`, `quantaalpha/tests/test_factor_tags.py`
  - Do: 修改 relatedness 评分公式加入标签匹配；编写测试
  - Verify: pytest 通过
  - Done when: 标签匹配影响 relatedness 评分，8+ 测试通过

## Files Likely Touched
- `quantaalpha/factors/library.py` (modify)
- `quantaalpha/factors/fewshot.py` (modify)
- `quantaalpha/tests/test_factor_tags.py` (new)

---
estimated_steps: 8
estimated_files: 3
