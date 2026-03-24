# T01: 实现 auto_discover_capabilities() 动态扫描函数

**Slice:** S01 — 数据能力注入最后一公里 (S1)
**Milestone:** M003

## Description

在 `data_capability.py` 中实现 `auto_discover_capabilities()` 函数，使用 Polars 动态扫描 `/home/quan/testdata/aspipe_v4/data/*/` 目录下的 Parquet 文件，读取 schema，生成数据能力注册表。该函数是整个 S01 注入链的底层基础，也是 S04 ProviderPool 配置验证和 S07 PIT 对齐的前置依赖。

## Steps

1. **Read existing `data_capability.py`** to understand the current hardcoded `DATA_CAPABILITIES` dict, `normalize_capability_spec()`, `get_data_capabilities()`, and `render_data_capabilities()` functions. Do not modify any of these.
2. **Add imports** for `polars`, `json`, `Path`, and `logging` (standard library). Wrap polars import in a try/except so the module still loads if polars is unavailable.
3. **Define `DEFAULT_DATA_DIR`** as `/home/quan/testdata/aspipe_v4/data` as a module-level constant.
4. **Define `_METADATA_FIELDS`** as a frozenset of fields to exclude from discovered `fields` list: `{"date", "datetime", "symbol", "code", "ts_code", "ann_date", "trade_date", "end_date", "start_date"}`.
5. **Implement `_scan_dir_schema(dir_path: Path) -> dict | None`**: Find the first `.parquet` file in `dir_path`, scan it with polars, return a dict with keys `columns` (list of str) and `num_rows` (int). Return `None` if no parquet found or scan fails.
6. **Implement `_infer_freq_and_lag(columns: list[str]) -> tuple[str, int]`**: If `"ann_date"` in columns, return `("quarterly", 45)`. Otherwise return `("daily", 0)`.
7. **Implement `_generate_factor_hints(dir_name: str) -> list[str]`**: Map directory names to domain hints. E.g. `"income_vip"` → `["profitability", "revenue", "quality"]`, `"daily_basic"` → `["momentum", "volatility", "liquidity"]`, `"moneyflow"` → `["flow", "smart_money"]`. Fall back to `["general_research"]`.
8. **Implement `auto_discover_capabilities(data_dir: str | Path | None = None, use_cache: bool = True) -> dict[str, dict]`**:
   - Resolve `data_dir` to the default if None.
   - If `use_cache=True`, check `~/.cache/quantaalpha/data_capability_registry.json`. If exists and not older than 24h, load and return it.
   - Scan every subdirectory in `data_dir`. For each subdir, call `_scan_dir_schema()`.
   - Build a registry entry: `{dir_name: {"fields": [col for col in columns if col not in _METADATA_FIELDS], "freq": freq, "lag_days": lag_days, "join_mode": "forward_fill" if freq=="quarterly" else "same_day", "factor_hints": hints, "_num_rows": num_rows}}`.
   - Write the cache file (create parent dirs as needed).
   - Return the registry dict.
   - On any error, log a warning and fall back to the hardcoded `DATA_CAPABILITIES` dict.
9. **Add `__all__`** export list at the top of the module including `auto_discover_capabilities`.

## Must-Haves

- [ ] `auto_discover_capabilities()` exists as a public function in `data_capability.py` and is callable.
- [ ] Function scans ≥ 20 parquet subdirectories and returns a dict keyed by directory name.
- [ ] Each registry entry has `fields`, `freq`, `lag_days`, `join_mode`, and `factor_hints` keys.
- [ ] Metadata fields (date, symbol, ann_date, etc.) are excluded from the `fields` list.
- [ ] JSON cache is written to `~/.cache/quantaalpha/data_capability_registry.json` on successful scan.
- [ ] On polars import failure, the function returns the hardcoded `DATA_CAPABILITIES` dict without raising.
- [ ] `render_data_capabilities(auto_discover_capabilities())` produces a non-empty "Available data capabilities:" text block.

## Verification

```bash
# Syntax check
python -m py_compile third_party/quantaalpha/quantaalpha/factors/data_capability.py

# Functional test
cd /home/quan/testdata/aspipe_v4/.gsd/worktrees/M003
python scripts/verify_s01_discovery.py

# The script above should:
#   - Discover ≥ 20 data sources
#   - Print the rendered data_capabilities text
#   - Write ~/.cache/quantaalpha/data_capability_registry.json
```

## Observability Impact

- **Signals added/changed:** INFO log lines for each directory scanned, WARN log when skipping a directory or falling back.
- **How a future agent inspects:** Read `~/.cache/quantaalpha/data_capability_registry.json` to see the last successful discovery result without re-scanning.
- **Failure state exposed:** If discovery fails (no polars, empty data dir), the hardcoded `DATA_CAPABILITIES` dict is returned and a warning is logged — the system continues to operate with 2 sources instead of 24.

## Inputs

- `third_party/quantaalpha/quantaalpha/factors/data_capability.py` — existing module with hardcoded DATA_CAPABILITIES and render functions; new function is added here
- `/home/quan/testdata/aspipe_v4/data/` — the real 24-subdirectory parquet data root (read-only)
- `scripts/verify_s01_discovery.py` — the verification script (written in parallel by this task)

## Expected Output

- `third_party/quantaalpha/quantaalpha/factors/data_capability.py` — modified to add `auto_discover_capabilities()`, `_METADATA_FIELDS`, `_scan_dir_schema()`, `_infer_freq_and_lag()`, `_generate_factor_hints()`, and updated `__all__`
- `scripts/verify_s01_discovery.py` — new standalone verification script that imports and calls `auto_discover_capabilities()`, prints the rendered text, and asserts ≥ 20 sources discovered
- `~/.cache/quantaalpha/data_capability_registry.json` — written by the verification script (or by the function itself on first run)
