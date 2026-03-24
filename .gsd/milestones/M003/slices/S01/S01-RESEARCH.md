# S01: 数据能力注入最后一公里 (S1) — Research

**Date:** 2026-03-23  
**Slice:** M003-S01  
**Status:** Research Complete

---

## Summary

S01 aims to close the gap between `data_capability.py` (which exists but contains only hardcoded stubs) and the LLM prompts that generate factor expressions. The key finding is that **the entire injection path is broken**: `render_data_capabilities()` exists but is never called in `proposal.py`, and `prompts.yaml` has no placeholder for data capabilities. The fix requires three coordinated changes: (1) implement `auto_discover_capabilities()` to dynamically scan `/home/quan/testdata/aspipe_v4/data/*.parquet` directories using Polars, (2) inject the rendered capabilities into `AlphaAgentHypothesisGen.prepare_context()`, and (3) add a Jinja2 placeholder in `prompts.yaml`. This is a prerequisite for S04 (ProviderPool config validation) and S07 (PIT alignment).

---

## Recommendation

Implement in the order: **`data_capability.py` → `proposal.py` → `prompts.yaml`**. The `auto_discover_capabilities()` function should be the first deliverable because it unblocks testing and provides the data structure consumed by the other two files. Use Polars `scan_parquet()` for schema inspection (already used elsewhere in the codebase), cache results to a JSON registry file to avoid repeated filesystem scans, and infer `lag_days` automatically from the presence of `ann_date` in the schema.

---

## Implementation Landscape

### Key Files

| File | What It Does | What Needs to Change |
|------|-------------|---------------------|
| `third_party/quantaalpha/quantaalpha/factors/data_capability.py` | Contains hardcoded `DATA_CAPABILITIES` (only `price_volume` and `financial`). Has `render_data_capabilities()` but it is never called upstream. | Add `auto_discover_capabilities()` function to scan parquet directories dynamically |
| `third_party/quantaalpha/quantaalpha/factors/proposal.py` | `AlphaAgentHypothesisGen.prepare_context()` (line ~178) builds `context_dict` with `hypothesis_and_feedback`, `RAG`, `hypothesis_output_format`, `hypothesis_specification`, `function_lib_description`. **Missing: `data_capabilities`** | Call `render_data_capabilities()` and add `data_capabilities` to `context_dict` |
| `third_party/quantaalpha/quantaalpha/factors/prompts/prompts.yaml` | `hypothesis_gen.system_prompt` template. No reference to data capabilities. | Add `{% if data_capabilities %}...{{ data_capabilities }}...{% endif %}` block |

### Data Directory Structure

The actual parquet data lives at `/home/quan/testdata/aspipe_v4/data/` with **24 subdirectories** each containing `.parquet` files:

| Category | Directories | Characteristics |
|----------|-------------|-----------------|
| **Financial (quarterly, lag=45d)** | `balancesheet_vip`, `cashflow_vip`, `income_vip`, `fina_indicator_vip`, `forecast_vip`, `fina_audit` | Have `ann_date` field for PIT alignment |
| **Daily (daily, lag=0d)** | `daily_basic`, `stk_factor_pro`, `express_vip`, `moneyflow` | Standard OHLCV-style fields |
| **Ownership/Event** | `top10_holders`, `top10_floatholders`, `pledge_stat`, `repurchase`, `block_trade` | May have `ann_date` |
| **Reference** | `stock_basic`, `trade_cal`, `suspend_d`, `dividend` | Lookup/metadata tables |

### Build Order

1. **`data_capability.py` first** — Implement `auto_discover_capabilities()`. This is the foundation. It needs to:
   - Scan each subdirectory in `/home/quan/testdata/aspipe_v4/data/`
   - Read the schema of the first parquet file in each directory (using Polars)
   - Detect `ann_date` presence to infer `freq` (quarterly vs daily)
   - Set `lag_days=45` for quarterly (financial), `lag_days=0` for daily
   - Generate `factor_hints` based on directory name patterns
   - Optionally write cached registry to JSON for fast startup

2. **`proposal.py` second** — Modify `AlphaAgentHypothesisGen.prepare_context()`. Import `render_data_capabilities` and `get_data_capabilities`, then add `data_capabilities` to `context_dict`. The `render_data_capabilities()` function already exists and produces the correct text format.

3. **`prompts.yaml` third** — Add the Jinja2 conditional block to `hypothesis_gen.system_prompt`. This is the final "last mile" that ensures the LLM actually receives the capability description.

### Verification Approach

```bash
# 1. Syntax check
python -m py_compile third_party/quantaalpha/quantaalpha/factors/data_capability.py
python -m py_compile third_party/quantaalpha/quantaalpha/factors/proposal.py

# 2. Functional test (requires polars in quantaalpha environment)
cd third_party/quantaalpha
python -c "
from quantaalpha.factors.data_capability import auto_discover_capabilities, render_data_capabilities
registry = auto_discover_capabilities(
    data_dir='/home/quan/testdata/aspipe_v4/data'
)
print('Sources discovered:', list(registry.keys()))
print()
print(render_data_capabilities(registry))
"

# 3. Factor mining run — check prompt injection
./run.sh "挖掘日频横截面因子" 2>&1 | grep -A 5 "Available Data"
```

Expected outcomes after implementation:
- `auto_discover_capabilities()` returns 24+ data sources with correct `freq`/`lag_days`
- LLM prompt contains the rendered data capabilities text
- Factor expressions in generated hypotheses use only fields from the available sources

---

## Don't Hand-Roll

| Problem | Existing Solution | Why Use It |
|---------|------------------|------------|
| Parquet schema reading | `polars` (already used in `factors/runner.py` for saving combined_factors_df) | Avoids reimplementing parquet parsing; leverages the same library used in `to_parquet()` calls |
| Jinja2 template rendering | `jinja2.Environment` (already used throughout `proposal.py`) | Consistent with existing prompt rendering pattern |
| JSON caching | Standard `json.dump/load` (existing patterns in codebase) | Simple, no new dependencies |

---

## Constraints

- **Polars availability**: The mining conda environment must have polars installed. If unavailable, pyarrow can be used as fallback for schema reading only.
- **Data directory path**: Hardcoded `/home/quan/testdata/aspipe_v4/data/` should ideally come from an environment variable or config (`QLIB_PROVIDER_URI` or a new `DATA_DIR` env var).
- **Backward compatibility**: Existing hardcoded `DATA_CAPABILITIES` dict should remain as a fallback if `auto_discover_capabilities()` fails.

---

## Common Pitfalls

- **Scanning too many files**: Each parquet directory may contain thousands of files. Only scan the **first file** per directory to get the schema — do not iterate all files.
- **Schema fields to exclude**: Always exclude metadata fields (`date`, `datetime`, `symbol`, `code`, `ts_code`, `ann_date` when it appears in daily data) from the `fields` list since these are not factor inputs.
- **Financial data without ann_date**: Some financial data directories may not have `ann_date` (e.g., `fina_indicator_vip` might be daily-processed). Need to inspect actual schemas to determine correct `freq` and `lag_days`.
- **Jinja2 undefined variable**: Use `{% if data_capabilities %}` guard in prompts.yaml to avoid Jinja2 `StrictUndefined` errors when the variable is not provided.

---

## Open Risks

- **Polars import failure in quantaalpha environment**: If polars is not installed, `auto_discover_capabilities()` will fail. Need to verify polars availability in the mining conda env or provide a pyarrow fallback.
- **Schema inference accuracy**: Automatic inference of `freq` and `lag_days` based on `ann_date` presence may not be correct for all data sources. A manual override mechanism (config file) may be needed.
- **Token budget impact**: Injecting 24 data sources with all field names could significantly increase prompt size. May need to limit to top-N sources or summarize fields rather than listing all.

---

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| Polars parquet reading | Not in available_skills | Available via `pip install polars` |
| Jinja2 template conditional blocks | Not needed — standard Jinja2 | Already in use |
| JSON caching | Not needed — standard library | Already in use |

---

## Sources

- `data_capability.py` — Existing hardcoded implementation (current baseline)
- `proposal.py:178-210` — `AlphaAgentHypothesisGen.prepare_context()` (injection point)
- `prompts/prompts.yaml` — `hypothesis_gen.system_prompt` (placeholder location)
- `/home/quan/testdata/aspipe_v4/data/` — 24 parquet data directories
- `docs/archived/drafts/factormining/structure/2026-03-22-continuous-mining-plan-supplement.md` Section 3.1 — Detailed S1 implementation specification
- `docs/04-decisions/ADR-001-continuous-factor-research.md` — Data Capability Registry requirement
