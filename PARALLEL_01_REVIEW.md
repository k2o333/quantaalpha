# Code Review: Parallel-01 Implementation

## Findings

### Critical Severity

1. **CLI Duplicates Pipeline Logic** - `quantaalpha/cli.py:64-340` contains comprehensive `revalidate()` function that reimplements backtest execution logic already present in `pipeline/factor_backtest.py:38-154`. The CLI creates temporary factor JSON files and calls `BacktestRunner` directly instead of using pipeline APIs.

2. **Boundary Violation - CLI Overreach** - `quantaalpha/cli.py:259` imports and directly instantiates `BacktestRunner`, `quantaalpha/cli.py:128` imports `FactorLibraryManager`. CLI should orchestrate, not implement business logic.

3. **Semantic Drift in Return Structures** - Duplicate return formats with inconsistent schemas:
   - CLI `revalidate()`: `{"mode": str, "total_candidates": int, "success": int, ...}` (`cli.py:341`)
   - Pipeline `run_real_backtest()`: `{"total_candidates": int, "success": int, ...}` (`factor_backtest.py:155`)

### High Severity

4. **Pseudo Failure Visibility** - Inconsistent error handling:
   - CLI catches broad exceptions and continues processing (`cli.py:195-338`)
   - Pipeline has sophisticated `_failure_tracker` in `AlphaAgentLoop` (`loop.py:45-89`) but CLI doesn't use it
   - Errors masked as generic "failed" counts without specific categorization

5. **Duplicate Backtest Execution Code** - `quantaalpha/cli.py:235-336` contains 101 lines of inline backtest logic duplicating `factor_backtest.py:run_real_backtest()` functionality.

### Medium Severity

6. **Inconsistent Terminology** - CLI uses "mode" concept (`REVALIDATE_MODE_*`) while pipeline uses boolean flags (`dry_run`, `persist`).

7. **Temporary File Management Issues** - CLI creates temp factor files (`cli.py:267-277`) without guaranteed cleanup on failure.

8. **Ambiguous Configuration Handling** - `factor_mining.py:368-369` accepts ambiguous threshold values (None, "", integer) without validation.

## Open Questions

1. What is the intended ownership boundary between CLI and pipeline layers? Should CLI be thin orchestrator or feature-rich interface?

2. Why does `cli.py` reimplement backtest logic instead of using `factor_backtest.py:run_real_backtest()`?

3. Is the semantic difference between "mode" (CLI) and boolean flags (pipeline) intentional or oversight?

4. Should failure tracking use pipeline's `_failure_tracker` consistently across all layers?

5. Are the temporary files in CLI revalidate necessary, or can pipeline accept factor objects directly?

## Files Checked

- `/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/cli.py` (lines 1-375)
- `/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/pipeline/factor_backtest.py` (lines 1-158)
- `/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/pipeline/factor_mining.py` (lines 1-703)  
- `/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/pipeline/loop.py` (lines 1-620)
- `/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/runner/backtest.py` (referenced but not examined)

## Residual Risks

1. **Maintenance Overhead** - Duplicated logic will diverge over time, causing inconsistent behavior between CLI and pipeline.

2. **Error Masking** - Pseudo failure visibility hides root causes, making debugging difficult.

3. **Tight Coupling** - Boundary violations make refactoring pipeline difficult without breaking CLI.

4. **Resource Leaks** - Temporary files may accumulate if CLI crashes during revalidate.

5. **Configuration Drift** - Inconsistent parameter handling between layers may cause silent failures.