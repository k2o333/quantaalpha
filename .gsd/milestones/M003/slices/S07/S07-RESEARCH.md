# S07: PIT 对齐执行层 (S6/D013) — Research

**Slice:** S07 | **Milestone:** M003 | **Status:** Research

## Research Goal

Understand the existing factor calculation pipeline, identify where PIT (Point-in-Time) alignment needs to be injected, and determine the integration points with S01's data capability registry.

---

## What Exists

### S01 Data Capability Registry (foundation)

`data_capability.py` already establishes the infrastructure S07 needs:

- **`auto_discover_capabilities()`** — scans all 24 Parquet subdirectories, infers `freq="quarterly"` and `lag_days=45` when `ann_date` is present in the schema, stores results in `~/.cache/quantaalpha/data_capability_registry.json` (24h TTL)
- **`get_data_capabilities()`** — returns normalized registry dict
- **`render_data_capabilities()`** — human-readable string
- **`_METADATA_FIELDS`** — includes `ann_date` as a known field to exclude from LLM-facing field lists
- **Hardcoded `DATA_CAPABILITIES`** fallback — `price_volume` (daily, lag_days=0) and `financial` (quarterly, lag_days=45)
- **Polars-optional** — wrapped inside `_scan_dir_schema()`, module compiles without Polars

The registry keys are the directory names (`income_vip`, `balancesheet_vip`, `daily_basic`, etc.). Quarterly sources with `ann_date`: `income_vip`, `balancesheet_vip`, `cashflow_vip`, `fina_indicator_vip`, `fina_audit`, `forecast_vip`, `fina_mainbz_vip`, `express_vip`.

### Factor Calculation Pipeline (two entry points)

**Entry 1 — `factor_calculator.py`:**
- `FactorCalculator.calculate_factors()` loops over factor dicts, calls `_calculate_with_parser()` then `_calculate_with_llm()`
- `_calculate_with_parser()` uses `parse_expression()` + `eval()` with `function_lib` functions
- Data comes from `QlibDataProvider.get_stock_data()` — only loads `$open/$close/$high/$low/$volume/$vwap/$return` from Qlib (daily, no PIT needed)
- **No financial Parquet integration here** — pure Qlib price/volume only

**Entry 2 — `custom_factor_calculator.py`:**
- `CustomFactorCalculator.calculate_factor()` — same expression parser + function lib pattern
- Data: `get_qlib_stock_data()` — also Qlib daily price/volume only
- **No financial Parquet integration either**

### The Gap

Both calculator entry points only handle daily price/volume data from Qlib. They don't touch the financial Parquet data at all. The `data_capability.py` registry identifies 8+ quarterly financial sources with `ann_date`, but nothing reads from them in the calculation pipeline.

The supplement plan describes a **dual-track engine**:
- **Pipeline Dump**: Write Parquet fields to Qlib Bin daily
- **Polars Engine**: Read Parquet directly with Polars, compute factors, emit single-value `.bin` files

S07 is scoped narrowly to **enforcing PIT alignment in the calculation layer** — it doesn't implement the dual-track data pipeline. Instead, it builds the mechanism that, once the financial Parquet data is loaded into a DataFrame, applies PIT filtering before factor computation.

---

## What Needs to Be Built

### Core: `pit_alignment.py`

A new module in `quantaalpha/factors/` that provides PIT alignment for DataFrames that contain financial data.

**Key function signatures:**

```python
def get_pit_sources(registry: dict | None = None) -> dict[str, dict]:
    """Return only the data sources that need PIT alignment (quarterly with ann_date)."""

def apply_pit_alignment(
    df: pd.DataFrame,
    data_source: str,
    pit_field: str = "ann_date",
    trade_date_field: str = "date",
) -> pd.DataFrame:
    """Filter df so that each (symbol, trade_date) only sees rows where
    pit_field <= trade_date - lag_days.
    For each (symbol, trade_date), keep the most recent qualifying row."""

def detect_pit_fields_in_factor_expression(
    factor_expr: str,
    registry: dict | None = None,
) -> list[str]:
    """Parse a factor expression and return the list of data sources used.
    E.g., '$roe / $revenue' -> ['income_vip']"""

def needs_pit_alignment(
    factor_expr: str,
    registry: dict | None = None,
) -> bool:
    """Return True if the expression uses any quarterly data source."""
```

**Core alignment logic (per supplement §3.6):**

For a quarterly source with `lag_days=45`:
```
For each (symbol, trade_date):
  valid_rows = rows where ann_date <= trade_date - 45
  factor_value = most_recent(valid_rows)  # last() by ann_date
```

Implementation options:

**Option A — Pandas groupby (recommended):**
```python
def apply_pit_alignment(df, data_source, pit_field="ann_date", trade_date_field="date"):
    # Requires df with columns: symbol, trade_date_field, pit_field, value_field(s)
    # 1. Filter: pit_field <= trade_date_field - lag_days
    # 2. Sort by pit_field desc
    # 3. groupby(symbol, trade_date_field).first()
```

**Option B — Polars (higher performance for large data):**
```python
def apply_pit_alignment_polars(lf, ...):
    return (
        lf.filter(pl.col(pit_field) <= pl.col(trade_date_field) - pl.duration(days=lag_days))
          .sort([pit_field], descending=True)
          .group_by(["symbol", trade_date_field])
          .first()
    )
```

**Recommendation**: Implement both, use Polars if available, fall back to Pandas. Polars is already an optional dependency used in `data_capability.py` for schema scanning.

### Integration Point: `custom_factor_calculator.py`

The `calculate_factor()` method needs to:
1. Parse the factor expression to identify which data sources it references
2. If any quarterly source is used, load the corresponding Parquet data
3. Apply PIT alignment before passing to the expression evaluator
4. Inject aligned columns into the evaluation DataFrame as `$field_name` columns

The challenge: `calculate_factor()` currently only receives a `data_df` from Qlib (price/volume). Financial Parquet data isn't loaded at all. The integration needs to either:
- Expand `get_qlib_stock_data()` to also load financial Parquet and inject aligned columns
- Or add a new `calculate_factor_with_financial_data()` method that accepts additional Parquet DataFrames

### Configuration: `experiment.yaml`

Add a `pit_alignment:` section:
```yaml
pit_alignment:
  enabled: true
  default_lag_days: 45
  data_dir: "/home/quan/testdata/aspipe_v4/data"
  # Per-source overrides
  source_overrides:
    forecast_vip:
      lag_days: 15  # forecasts have shorter lag
```

---

## Key Design Decisions

### 1. Where to apply alignment: expression parser vs. calculator entry point

**Decision**: At the calculator entry point (`calculate_factor()` in `custom_factor_calculator.py`), not at the expression parser.

**Rationale**: The expression parser (`expr_parser.py`, `function_lib.py`) is stateless and shouldn't know about PIT semantics. The calculator is the right layer because it has access to both the expression and the data. This is consistent with how S01 injected data awareness — at the `prepare_context()` level, not inside the LLM prompt engine.

### 2. How to know which Parquet source a factor expression uses

**Decision**: The factor expression uses `$field_name` syntax (e.g., `$roe`). The data capability registry maps source directories to fields. We need a reverse mapping: `field_name -> source_name`.

The registry keys are source names. Each source has a `fields` list like `["$roe", "$revenue"]`. Build a reverse index at module load time:
```python
_FIELD_TO_SOURCE: dict[str, str] = {}  # e.g., "$roe" -> "income_vip"
```

### 3. PIT field names in the DataFrame

Quarterly Parquet files have columns like `ann_date`, `end_date`, `trade_date`, `symbol`/`code`. The alignment needs to know which field represents the announcement date and which represents the trading date.

From `data_capability.py` `_METADATA_FIELDS`: `ann_date` is the announcement date. `trade_date` or `date` is the trading date.

### 4. Polars dependency strategy

Same as S01: import Polars inside the function body, not at module level. Use Polars for PIT computation if available, fall back to Pandas.

### 5. D019 lessons: defensive checks

From D019 (M001 lessons), the code should:
- Check for empty DataFrames before alignment
- Validate that `pit_field` and `trade_date_field` exist in the DataFrame
- Handle the case where `trade_date - lag_days` results in a date before any announcement (no data → NaN)

---

## Risk Assessment

### Risk 1: Parquet data not loaded in calculation pipeline (HIGH)
The current calculators don't load financial Parquet data at all. The PIT alignment module is useless without data to align. The integration needs to extend `get_qlib_stock_data()` or create a new data loading path.

**Mitigation**: Design the integration to be additive — if financial Parquet data isn't available, skip PIT alignment gracefully. The `needs_pit_alignment()` function returns `False` if the expression only uses daily data.

### Risk 2: Field name collision (MEDIUM)
Financial Parquet fields like `$roe` might collide with Qlib fields. Need namespace separation or column renaming.

**Mitigation**: Use source-qualified names internally (e.g., `income_vip_roe`) or inject into the DataFrame with existing `$field` names, knowing that quarterly data only overlaps on metadata fields (date/symbol) not on financial ratios.

### Risk 3: Expression parsing for source detection (MEDIUM)
The `$field` syntax in factor expressions maps to Parquet fields. The registry stores fields as `$roe`, `$revenue`, etc. Need to correctly parse expressions like `RANK($roe / $revenue)` to extract `$roe` and `$revenue`.

**Mitigation**: Use simple regex `\$[a-zA-Z_][a-zA-Z0-9_]*` to extract field references from expressions. This is similar to what `parse_symbol()` in `expr_parser.py` already does.

### Risk 4: Quarterly data shape mismatch (MEDIUM)
Quarterly data has one row per (symbol, end_date) while price data has one row per (date, symbol). The join needs to align quarterly rows to trading days.

**Mitigation**: The supplement plan's approach of `forward_fill` join mode means: for each trading day `T`, use the most recent quarterly announcement with `ann_date <= T - lag_days`. This maps naturally to the groupby + last() pattern.

---

## Implementation Landscape

### New files
| File | Purpose |
|------|---------|
| `quantaalpha/factors/pit_alignment.py` | Core PIT alignment functions |
| `tests/factors/test_pit_alignment.py` | Unit tests (mock Parquet data) |

### Modified files
| File | Change |
|------|--------|
| `quantaalpha/backtest/custom_factor_calculator.py` | Inject PIT-aligned financial data before factor eval |
| `quantaalpha/backtest/factor_calculator.py` | Same integration, parallel path |
| `quantaalpha/factors/experiment.yaml` | Add `pit_alignment:` config section |

### Test data strategy
Mock Parquet data using `pandas.DataFrame` with `to_parquet()` from `pyarrow` — but `pyarrow` isn't installed. Use pre-built small CSV fixtures or create mock DataFrames directly in tests. The tests should use `pandas.DataFrame` with manually constructed quarterly data to avoid external Parquet dependencies.

---

## Verification Strategy

1. **Unit tests** (`test_pit_alignment.py`):
   - Test `get_pit_sources()` returns only quarterly sources
   - Test `apply_pit_alignment()` filters correctly
   - Test `needs_pit_alignment()` for expressions using daily vs. quarterly fields
   - Test that `detect_pit_fields_in_factor_expression()` extracts all `$field` references
   - Test lag_days delay is respected
   - Test that non-quarterly data passes through unchanged

2. **Integration tests**:
   - `calculate_factor()` with a `$roe`-based expression on mock quarterly data
   - Verify no future data leaks (assert all `ann_date <= trade_date - lag_days`)

3. **Syntax checks**:
   - `python -m py_compile pit_alignment.py`
   - `python -m py_compile custom_factor_calculator.py`

---

## Files to Read Before Implementation

1. `third_party/quantaalpha/quantaalpha/factors/data_capability.py` — S01 registry, `_METADATA_FIELDS`, `_FACTOR_HINT_MAP`
2. `third_party/quantaalpha/quantaalpha/backtest/custom_factor_calculator.py` — `calculate_factor()` integration point
3. `third_party/quantaalpha/quantaalpha/factors/coder/expr_parser.py` — existing `$field` parsing logic
4. `third_party/quantaalpha/quantaalpha/factors/prompts/experiment.yaml` — config structure
5. `docs/archived/drafts/factormining/structure/2026-03-22-continuous-mining-plan-supplement.md` §3.6 — supplement S6 design
