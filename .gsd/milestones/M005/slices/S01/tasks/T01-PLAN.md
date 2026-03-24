# T01: 实现 fallback logger

**Slice:** S01
**Milestone:** M005

## Goal
在 `rdagent.log` 不存在的情况下提供一组行为一致的 fallback logger API。

## Problem
rdagent 包能正常导入，但 `rdagent.log` 模块不存在，导致 `from rdagent.log import logger, LogColors` 失败。

## Must-Haves

### Truths (机械可验证)
1. `python -c "from quantaalpha.log import logger, LogColors; logger.info('test')"` 运行不报错
2. `python -c "from quantaalpha.factors.proposal import normalize_corrected_expression"` 导入成功（验证传递导入链）
3. 主包：`python -c "import quantaalpha.log; print('OK')"` 成功；vendored copy：`python -c "import sys; sys.path.insert(0, 'third_party/quantaalpha'); import quantaalpha.log; print('OK')"` 成功
4. `python -c "from quantaalpha.log import logger; logger.set_trace_path('/tmp'); print(logger.log_trace_path)"` 能正确输出路径

### Artifacts
- `third_party/quantaalpha/quantaalpha/log/__init__.py`
- `quantaalpha/log/__init__.py`

### Key Links
- 需要包含 `logger`（实现了 info, warning, error, exception, log_trace_path, set_trace_path）
- 包含 `LogColors` 枚举兼容

## Steps
1. 在 log/__init__.py 中，使用 try-except 包裹 `from rdagent.log import ...`
2. 在 except 块中实现 DummyLogColors 或提取 LogColors 的基本功能。
3. 实现 FallbackLogger 类，包装 `logging.Logger` 并提供同名函数。
4. 为 vendor 目录和主包目录做同样的修改。

## Context
没有 `rdagent` 依赖的纯本地运行场景十分关键。
