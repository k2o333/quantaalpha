# Bug Report: RDAgentLog.warning() Argument Count Mismatch

## Bug Title

`RDAgentLog.warning() takes 2 positional arguments but 5 were given` - Multiple quantaalpha callers use old `logging.warning()` format-string style incompatible with `RDAgentLog.warning()` signature.

## Terminal Evidence

From `/home/quan/testdata/aspipe_v4/third_party/facotors/terminal/20260321_214610.txt`, line 25:
```
2026-03-21 21:46:13.886 | WARNING  | quantaalpha.pipeline.planning:generate_parallel_directions:142 - Planning LLM call failed (attempt 1): RDAgentLog.warning() takes 2 positional arguments but 5 were given
```

## Root Cause Analysis

This is a **caller error** (wrong number of positional arguments passed by quantaalpha code).

### How the call chain works:

1. `quantaalpha.pipeline.planning:generate_parallel_directions` (line 133) calls `APIBackend().build_messages_and_create_chat_completion(...)`.
2. `APIBackend.__init__()` (in `quantaalpha/llm/client.py`) runs, which may invoke `log_tokenizer_fallback_once()`.
3. `log_tokenizer_fallback_once()` calls `logger.warning()` with **4 positional arguments** (old `logging.warning()` format-string style).
4. `logger` is `_AlphaAgentLoggerWrapper(_rdagent_logger)`, which delegates via `__getattr__` to `RDAgentLog.warning()`.
5. `RDAgentLog.warning()` only accepts **1 positional argument** (`msg`), so Python raises `TypeError`.

### The mismatch:

| Method | Signature | Expected positional args (incl. self) |
|---|---|---|
| `RDAgentLog.warning()` | `warning(self, msg: str, *, tag: str = "", raw: bool = False) -> None` | 2 |
| Caller at line 69-74 | `logger.warning("Tokenizer lookup failed for model %s; falling back to %s. reason=%s", model, DEFAULT_FALLBACK_TOKENIZER, reason)` | 5 |

The quantaalpha code uses the old Python `logging.warning()` convention where a format string with `%s` placeholders is followed by separate arguments to fill them. `RDAgentLog.warning()` does **not** support this — it expects a single pre-formatted string.

## Code Locations

### Callee (RDAgentLog.warning)

- **File**: `/root/miniforge3/envs/mining/lib/python3.12/site-packages/rdagent/log/logger.py`
- **Line**: 132
- **Signature**: `def warning(self, msg: str, *, tag: str = "", raw: bool = False) -> None:`

### Callers (quantaalpha code passing too many positional arguments)

1. **Primary trigger for this bug**:
   - **File**: `/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/llm/client.py`
   - **Line**: 69-74
   - **Code**:
     ```python
     logger.warning(
         "Tokenizer lookup failed for model %s; falling back to %s. reason=%s",
         model,
         DEFAULT_FALLBACK_TOKENIZER,
         reason,
     )
     ```
   - **Argument count**: 4 positional (5 including self)

2. **Additional problematic calls**:
   - **File**: `/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/llm/client.py`
   - **Line**: 667
   - **Code**: `logger.warning("Unknown llm task_type=%s; falling back to default routing", task_type)`
   - **Argument count**: 2 positional (3 including self)

   - **File**: `/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/backtest/universe.py`
   - **Line**: 111
   - **Code**: `logger.warning("Failed to parse as_of_date=%s for stock universe filtering", value)`
   - **Argument count**: 2 positional (3 including self)

### Wrapper layer

- **File**: `/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/log/__init__.py`
- **Line**: 13-43
- `_AlphaAgentLoggerWrapper` delegates all attribute access to the inner `rdagent_logger` via `__getattr__`. This is correct and not the source of the bug.

## Actual vs Expected Argument Counts

| Location | Actual positional args | Expected positional args |
|---|---|---|
| `client.py:69-74` | 5 (self + 4) | 2 (self + msg) |
| `client.py:667` | 3 (self + 2) | 2 (self + msg) |
| `universe.py:111` | 3 (self + 2) | 2 (self + msg) |

## Suggested Fix

Convert all `logger.warning()` calls from old `logging.warning()` format-string style to f-string style. Each caller must pass a single pre-formatted string.

### Fix for `client.py:69-74`:

```python
# Before:
logger.warning(
    "Tokenizer lookup failed for model %s; falling back to %s. reason=%s",
    model,
    DEFAULT_FALLBACK_TOKENIZER,
    reason,
)

# After:
logger.warning(
    f"Tokenizer lookup failed for model {model}; "
    f"falling back to {DEFAULT_FALLBACK_TOKENIZER}. reason={reason}"
)
```

### Fix for `client.py:667`:

```python
# Before:
logger.warning("Unknown llm task_type=%s; falling back to default routing", task_type)

# After:
logger.warning(f"Unknown llm task_type={task_type}; falling back to default routing")
```

### Fix for `universe.py:111`:

```python
# Before:
logger.warning("Failed to parse as_of_date=%s for stock universe filtering", value)

# After:
logger.warning(f"Failed to parse as_of_date={value} for stock universe filtering")
```

## Summary

The bug is caused by quantaalpha code calling `logger.warning()` with multiple positional arguments (using the old `logging.warning()` `%s`-format convention), while `RDAgentLog.warning()` only accepts a single positional `msg` argument. The fix is to pre-format the message string using f-strings before passing it to `logger.warning()`.
