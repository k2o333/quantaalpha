# S01: 数据能力注入最后一公里 (S1)

**Goal:** LLM prompt auto-injects Parquet data schema and time-lag constraints from dynamically scanned data directories.
**Demo:** Running factor mining with a data-aware prompt produces hypotheses that reference only fields from the discovered parquet schemas.

## Must-Haves

- `auto_discover_capabilities()` scans `/home/quan/testdata/aspipe_v4/data/*/` directories with Polars, infers `freq`/`lag_days` from schema, and returns a typed registry dict.
- `AlphaAgentHypothesisGen.prepare_context()` calls `render_data_capabilities()` and adds `data_capabilities` to the `context_dict` returned to the LLM.
- `prompts.yaml`'s `hypothesis_gen.system_prompt` template renders the `data_capabilities` text via a Jinja2 conditional block.
- Existing hardcoded `DATA_CAPABILITIES` dict is preserved as fallback when dynamic discovery fails.
- Unit tests verify `auto_discover_capabilities()` returns ≥ 20 data sources and renders correctly.

## Proof Level

- This slice proves: contract verification (Python syntax, unit tests) + integration (end-to-end render pipeline).
- Real runtime required: no — discovery is exercised via a standalone test script using the real data directory.
- Human/UAT required: no.

## Verification

- `python -m py_compile third_party/quantaalpha/quantaalpha/factors/data_capability.py` — zero syntax errors
- `python -m py_compile third_party/quantaalpha/quantaalpha/factors/proposal.py` — zero syntax errors
- `python -m pytest third_party/quantaalpha/tests/test_data_capability_registry.py -v` — all existing tests pass
- `python scripts/verify_s01_discovery.py` — discovers ≥ 20 sources, renders non-empty text, writes `data_capability_registry.json`
- `grep -c "data_capabilities" third_party/quantaalpha/quantaalpha/factors/proposals/prompts/prompts.yaml` ≥ 1 — placeholder exists
- `grep -c "data_capabilities" third_party/quantaalpha/quantaalpha/factors/proposal.py` ≥ 1 — injection call exists

## Observability / Diagnostics

- **Runtime signals:** `data_capability.py` logs (INFO) the number of sources discovered and any directory skipped due to missing parquet files.
- **Inspection surfaces:** `~/.cache/quantaalpha/data_capability_registry.json` — human-readable JSON cache written by `auto_discover_capabilities()`. Contains all discovered sources with schema field counts.
- **Failure visibility:** On any directory scan error, the function falls back to the hardcoded `DATA_CAPABILITIES` dict and logs a warning. The JSON cache preserves the last successful scan.
- **Redaction constraints:** None — parquet schema field names are not secrets.

## Integration Closure

- **Upstream surfaces consumed:** `/home/quan/testdata/aspipe_v4/data/*/` parquet directories (24 subdirectories), `polars` library.
- **New wiring introduced in this slice:** `data_capability.py: auto_discover_capabilities()` → `proposal.py: prepare_context()` → `prompts.yaml: hypothesis_gen.system_prompt`.
- **What remains before the milestone is truly usable end-to-end:** S04 (ProviderPool) consumes this registry for config validation. S07 (PIT alignment) uses the `ann_date` lag inference for financial data alignment.

## Tasks

- [x] **T01: 实现 auto_discover_capabilities() 动态扫描函数** `est:1h`
  - Why: 现有 `data_capability.py` 只有硬编码的 2 个数据源（price_volume/financial），无法反映实际 Parquet 目录的 24 个数据源。这是整个注入链的基础。
  - Files: `third_party/quantaalpha/quantaalpha/factors/data_capability.py`, `scripts/verify_s01_discovery.py`
  - Do: 在 `data_capability.py` 添加 `auto_discover_capabilities()` 函数，扫描 `/home/quan/testdata/aspipe_v4/data/*/` 下每个子目录的第一个 `.parquet` 文件，使用 `polars.scan_parquet()` 读取 schema，检测字段列表，根据 `ann_date` 存在性推断 `freq`（quarterly vs daily）和 `lag_days`（45 vs 0）。生成 `factor_hints` 基于目录名。写入 JSON 缓存到 `~/.cache/quantaalpha/data_capability_registry.json`。保留现有硬编码 `DATA_CAPABILITIES` 作为 fallback。
  - Verify: `python scripts/verify_s01_discovery.py` — discovers ≥ 20 sources, renders non-empty text
  - Done when: `auto_discover_capabilities()` returns ≥ 20 entries, `render_data_capabilities()` produces non-empty text, JSON cache written to disk
- [x] **T02: 在 proposal.py 的 prepare_context() 中注入 data_capabilities** `est:30m`
  - Why: `render_data_capabilities()` 函数已存在但从未被 `prepare_context()` 调用，导致 LLM 无法感知可用数据。这是注入路径的关键断点。
  - Files: `third_party/quantaalpha/quantaalpha/factors/proposal.py`
  - Do: 在 `AlphaAgentHypothesisGen.prepare_context()` 的 `context_dict` 构建代码块中，导入 `render_data_capabilities` 和 `get_data_capabilities`，调用 `render_data_capabilities(get_data_capabilities())` 并将结果添加到 `context_dict["data_capabilities"]`。如果 `auto_discover_capabilities()` 导入失败则静默降级到现有 `DATA_CAPABILITIES`。
  - Verify: `python -m py_compile third_party/quantaalpha/quantaalpha/factors/proposal.py` — zero syntax errors; `grep -c "data_capabilities" third_party/quantaalpha/quantaalpha/factors/proposal.py` ≥ 1
  - Done when: `context_dict` contains `data_capabilities` key when passed to Jinja2 renderer
- [x] **T03: 在 prompts.yaml 添加 Jinja2 占位符** `est:15m`
  - Why: 即使 `context_dict` 包含 `data_capabilities`，如果 `prompts.yaml` 的 `hypothesis_gen.system_prompt` 没有对应的 Jinja2 变量占位符，LLM 仍无法接收数据能力描述。这是"最后一公里"。
  - Files: `third_party/quantaalpha/quantaalpha/factors/prompts/prompts.yaml`
  - Do: 在 `hypothesis_gen.system_prompt` 模板的 `{% if hypothesis_specification %}...{% endif %}` 块之后、`Allowed operators and functions:` 之前，添加 `{% if data_capabilities %}` 条件块，渲染 `{{ data_capabilities }}`。使用 Jinja2 `{% if data_capabilities %}{% raw %}` guard 防止 StrictUndefined 错误。
  - Verify: `grep -c "data_capabilities" third_party/quantaalpha/quantaalpha/factors/prompts/prompts.yaml` ≥ 1; existing pytest tests pass
  - Done when: Jinja2 template contains the conditional block and existing unit tests still pass

## Files Likely Touched

- `third_party/quantaalpha/quantaalpha/factors/data_capability.py`
- `third_party/quantaalpha/quantaalpha/factors/proposal.py`
- `third_party/quantaalpha/quantaalpha/factors/prompts/prompts.yaml`
- `scripts/verify_s01_discovery.py` (new file)
- `third_party/quantaalpha/tests/test_data_capability_registry.py` (existing, unmodified)

---
estimated_steps: 9
estimated_files: 5
skills_used:
  - python-best-practices
  - lint
  - test
