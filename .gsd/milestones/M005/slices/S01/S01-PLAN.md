# S01: 移除 rdagent.log 硬依赖

**Goal:** 移除 `quantaalpha.log` 对 `rdagent.log` 的硬依赖，实现本地 fallback logger。
**Problem:** rdagent 包能正常导入，但 `rdagent.log` 模块不存在，导致依赖 `from rdagent.log import ...` 的导入链失败。
**Demo:** 在 `rdagent.log` 缺失或不可用的环境中，`from quantaalpha.log import logger, LogColors` 能成功导入并工作。

## Must-Haves
- `quantaalpha/log/__init__.py` 和 `third_party/quantaalpha/quantaalpha/log/__init__.py` 不会因为 `rdagent.log` 不存在而抛出 ImportError。
- `logger.info`, `logger.warning`, `logger.error`, `logger.exception`, `logger.log_trace_path`, `logger.set_trace_path` 接口必须存在。

## Tasks

- [x] **T01: 实现 fallback logger**
  在抛出 ImportError 时使用标准库 logging 构造一个具有相同接口的后备 logger。

## Files Likely Touched
- `third_party/quantaalpha/quantaalpha/log/__init__.py`
- `quantaalpha/log/__init__.py`
