# S01: 移除 rdagent.log 硬依赖 — Slice Summary

**Milestone:** M005 (Mining Pipeline 关键 Bug 修复)
**Slice Goal:** 移除 `quantaalpha.log` 对 `rdagent.log` 的硬依赖，实现本地 fallback logger
**Task:** T01 — 实现 fallback logger
**Status:** ✅ Complete
**Completed:** 2026-03-24T18:34:59+08:00

---

## What This Slice Delivered

### Problem
`rdagent` 包可以导入，但 `rdagent.log` 模块不存在，导致 `from quantaalpha.log import logger` 在依赖链中抛出 `ImportError`，阻塞因子挖掘 pipeline。

### Solution
在 `quantaalpha/log/__init__.py` 和 `third_party/quantaalpha/quantaalpha/log/__init__.py` 两处使用 `try-except ImportError` 包装 `rdagent.log` 导入，在不可用时回退到标准库 `logging` 实现。

### Implementation

**FallbackLoggerWrapper** — 包装 stdlib `logging.Logger`，添加 AlphaAgent 扩展接口：
- `log_trace_path` property → 返回 `Path`
- `set_trace_path(path)` → 更新 trace path
- `storage` object → 含 `path` property 和 `truncate()` method
- `__getattr__` 代理 → 所有其他方法委托给内层 logger

**FallbackFileStorage** — 提供 `path` 和 `truncate()` 接口，truncate 为 no-op（fallback 模式不写文件）。

**LogColors** — Enum 类，9 种 ANSI 颜色码，与 `rdagent.log.utils.LogColors` 兼容。

### Files Changed

| File | Action |
|------|--------|
| `quantaalpha/log/__init__.py` | Modified — 添加 try-except fallback |
| `third_party/quantaalpha/quantaalpha/log/__init__.py` | Created — 与上一份对齐 |
| `third_party/quantaalpha/quantaalpha/__init__.py` | Created — 启用 vendored 包导入 |

两份 `log/__init__.py` 完全一致（MD5: `25bee61c6ed7c542112dee577c87f41a`）。

---

## Verification Results

| Check | Result |
|-------|--------|
| `from quantaalpha.log import logger, LogColors` | ✅ `FallbackLoggerWrapper` |
| vendored import | ✅ `FallbackLoggerWrapper` |
| `info`, `warning`, `error`, `exception` | ✅ 全部存在 |
| `log_trace_path` 返回 `Path` | ✅ |
| `set_trace_path()` 修改 path | ✅ |
| `logger.storage.path` / `truncate()` | ✅ |
| `LogColors.RED`, `GREEN`, ... | ✅ 9 色 |
| rdagent 模块不在 sys.modules | ✅ 零依赖 |
| 两份文件 MD5 一致 | ✅ |
| 日志输出格式正确 | ✅ |

---

## Patterns Established

### 1. Graceful Degradation via try-except ImportError
```python
try:
    from rdagent.log import rdagent_logger as _rdagent_logger
    from rdagent.log.utils import LogColors as _LogColors
    logger = _rdagent_logger
    if _LogColors is not None:
        LogColors = _LogColors
except ImportError:
    _fallback_logger = logging.getLogger("quantaalpha")
    logger = FallbackLoggerWrapper(_fallback_logger)
```
This pattern is **safe** because:
- `rdagent` IS installed in the mining conda env — the rdagent path still runs when available
- `FallbackLoggerWrapper` is used only when `rdagent.log` is absent
- Both paths produce the same public API surface

### 2. Private Attribute Guard Pattern
```python
def __setattr__(self, name: str, value) -> None:
    if name in ("_inner", "_storage"):
        object.__setattr__(self, name, value)
    else:
        setattr(self._inner, name, value)
```
Prevents shadowing internal `_inner`/`_storage` when delegating to wrapped logger.

### 3. File Synchronization via MD5 Check
Both `log/__init__.py` files must be byte-identical. Use `diff -q` or MD5 to verify after any edit.

---

## Downstream Contract

S01 is a **leaf node** — no downstream slices consume from it directly. However, all other slices in M005 depend on `from quantaalpha.log import logger` succeeding without rdagent installed. This slice establishes the invariant that all subsequent work assumes:

> `from quantaalpha.log import logger, LogColors` **always** succeeds.

Any future slice that introduces a new import from `rdagent` into the quantaalpha log chain must preserve this guarantee.

---

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Fallback vs. stub | Standard lib `logging.Logger` wrapper | Provides real functionality (output, levels), not a no-op stub |
| FileStorage truncate | no-op | Fallback mode doesn't write log files; truncate() has nowhere to operate |
| LogColors enum | Always present (fallback-only) | Both paths expose LogColors; rdagent's overrides if present |
| Default trace path | `$LOG_TRACE_PATH` env var → `/tmp/quantaalpha_logs` | Non-invasive; no hardcoded absolute paths |

---

## Known Limitations

- **Fallback mode console output only** — no file-based logging in fallback. `truncate()` is a no-op.
- **`rdagent.scenarios.qlib` import failures** are unrelated to this slice — they block `normalize_corrected_expression` transitive import testing but do not affect `quantaalpha.log` itself.
- **rdagent path still preferred** — when `rdagent.log` is available, the real logger is used. The fallback is transparent to callers.

---

## Relationship to Requirements

- **R015** (P0 — rdagent.log 缺失导致导入失败) → ✅ **Validated** by this slice
