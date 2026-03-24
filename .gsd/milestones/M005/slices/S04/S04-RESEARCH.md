# S04 Research: Stop Retrying Unrecoverable BadRequest Errors

**Slice:** S04 — 停止对不可恢复 BadRequest 重试
**Milestone:** M005 (Mining Pipeline 关键 Bug 修复)
**Depth:** Light research — targeted code change, known pattern

---

## Bug-3 Summary

**Location:** `quantaalpha/llm/client.py:804-815` (`_try_create_chat_completion_or_embedding`)

**Problem:** `openai.BadRequestError` is caught broadly and retried for all error messages. Errors like "Invalid model name" or "Invalid model" are configuration errors that are unrecoverable — retrying wastes 10 × `retry_wait_seconds` and hides the real issue.

**Current code:**
```python
except openai.BadRequestError as e:  # noqa: PERF203
    logger.warning(e)
    logger.warning(f"Retrying {i+1}th time...")
    if "'messages' must contain the word 'json' in some form" in e.message:
        kwargs["add_json_in_prompt"] = True
    elif embedding and "maximum context length" in e.message:
        kwargs["input_content_list"] = [...]
    if i < max_retry - 1:
        time.sleep(self.retry_wait_seconds)
```

---

## Implementation Plan

**Single edit** — add an early guard in the `BadRequestError` handler:

```python
except openai.BadRequestError as e:  # noqa: PERF203
    error_str = str(e)
    logger.warning(e)
    # Unrecoverable: invalid model name — fail fast, no retry
    if "Invalid model" in error_str:
        failing_model = self.embedding_model if embedding else self.chat_model
        logger.error(f"Unrecoverable BadRequest: invalid model '{failing_model}'. Check model configuration.")
        raise
    logger.warning(f"Retrying {i+1}th time...")
    # ... rest of existing recoverable-error handling unchanged ...
```

**Key decisions:**
- Use `str(e)` instead of `e.message` — both work, but `str(e)` is more robust (covers exception-to-string conversion regardless of attribute existence)
- `self.chat_model` and `self.embedding_model` are confirmed instance attributes on `APIClient` (lines 493-560)
- Re-raise via bare `raise` (preserves traceback, no new exception type)
- Log the failing model name for actionable error output
- Only the BadRequestError branch is modified; the generic `Exception` branch (rate limits, timeouts, etc.) is unchanged

---

## Files

| File | Action |
|------|--------|
| `quantaalpha/llm/client.py` | Modify — add `Invalid model` guard in `_try_create_chat_completion_or_embedding` |

No `third_party` copy exists (`third_party/quantaalpha/quantaalpha/llm/` does not exist), so no sync needed.

---

## Verification

```bash
# Syntax check
python -m py_compile quantaalpha/llm/client.py

# Verify guard text exists
grep -n "Invalid model" quantaalpha/llm/client.py

# Verify no unintended changes — show diff
git diff quantaalpha/llm/client.py
```

**Expected diff:** only the 5-line guard block added inside the `except openai.BadRequestError` handler, before the existing recoverable-error logic.

---

## Risk Assessment

- **Very low.** The change adds a conditional early-exit; it does not remove or modify any existing retry logic.
- No new imports needed (all names already in scope).
- No test file exists for this function — no regression risk to existing tests.
