# S04: 停止对不可恢复 BadRequest 重试 — Slice Summary

**Milestone:** M005 (Mining Pipeline 关键 Bug 修复)
**Slice Goal:** 让 `client.py` 遇到不可恢复的 BadRequestError（如 invalid model）时快速抛出
**Task:** T01 — 实现 BadRequest 快速失败守卫
**Status:** ✅ Complete
**Completed:** 2026-03-24T18:42:00+08:00

---

## What This Slice Delivered

### Problem
`_try_create_chat_completion_or_embedding()` 对所有 `openai.BadRequestError` 无差别重试，包括不可恢复的配置错误（如无效模型名）。这导致：
- 浪费 10 × `retry_wait_seconds` 等待时间
- 真实错误（模型名错误）被掩盖，最终只抛出通用 `RuntimeError`

### Solution
在 `BadRequestError` 异常处理入口处增加 `"Invalid model" in str(e)` 守卫，检测到不可恢复错误后立即 `raise`。

### Implementation

```python
except openai.BadRequestError as e:
    error_str = str(e)
    logger.warning(e)
    # Unrecoverable: invalid model name — fail fast, no retry
    if "Invalid model" in error_str:
        failing_model = self.embedding_model if embedding else self.chat_model
        logger.error(f"Unrecoverable BadRequest: invalid model '{failing_model}'. Check model configuration.")
        raise
    # ... 现有可恢复错误处理逻辑不变 ...
```

**关键设计决策：**
- `error_str = str(e)` 替代 `e.message` — 更健壮，兼容任何异常类型转换
- `raise`（裸 raise）保留原始 traceback，不吞异常
- 日志包含实际失败的模型名（chat 或 embedding 路径）
- 可恢复错误的现有处理逻辑（`'json' in some form` / `maximum context length`）完全不受影响

### Files Changed

| File | Action | Commit |
|------|--------|--------|
| `quantaalpha/llm/client.py` | Modified (+8/-2 lines) | submodule: `7b15e5d` |
| Parent `.gsd/REQUIREMENTS.md` | Updated R018 → validated | parent: `f3812eb` |

`quantaalpha/` 是 symlink → `third_party/quantaalpha/quantaalpha/`（submodule）。

---

## Verification Results

| Check | Result |
|-------|--------|
| `python -m py_compile quantaalpha/llm/client.py` | ✅ Syntax OK |
| `grep -n "Invalid model" quantaalpha/llm/client.py` | ✅ line 808 |
| Diff scope | ✅ 仅 +8/-2 行，逻辑干净 |
| Submodule push | ✅ `7b15e5d → main` |
| Parent push | ✅ `a669349 → f3812eb → main` |

---

## Patterns Established

### 1. Fail-Fast for Unrecoverable Errors
```python
if "Invalid model" in str(e):
    failing_model = self.embedding_model if embedding else self.chat_model
    logger.error(f"Unrecoverable BadRequest: invalid model '{failing_model}'. Check model configuration.")
    raise
```
This pattern should be applied to any API error that is provably unrecoverable:
- Invalid credentials → 401
- Invalid model name → 400 with "Invalid model"
- Invalid endpoint → 404
Retrying these wastes time and masks the real problem.

### 2. `str(e)` Over `e.message`
Using `str(e)` is more reliable than `e.message` because:
- Works regardless of whether the exception class has a `message` attribute
- The string representation includes the full exception context

---

## Relationship to Requirements

- **R018** (P1 — 无效模型名等 BadRequest 错误不区分可恢复性) → ✅ **Validated**

---

## Known Limitations

- No unit test coverage for this code path (no test file exists for `_try_create_chat_completion_or_embedding`)
- Only catches "Invalid model" — other unrecoverable 400 errors (e.g., invalid API key format) still retry
- This is a pragmatic fix: the pattern can be extended to other specific error strings as they are discovered

## Downstream Contract

S04 is an independent slice. No other slices in M005 depend on its output. Future slices that extend API error handling should preserve the fast-fail pattern for clearly unrecoverable errors.
