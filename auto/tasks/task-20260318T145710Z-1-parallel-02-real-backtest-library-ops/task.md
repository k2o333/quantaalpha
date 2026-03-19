---
source_slice_doc: docs/03-changes/quantaalpha/planned/parrelell/2026-03-18-parallel-02-real-backtest-library-ops.md
parallel_group: quantaalpha-iterate2-pilot
task_kind: headless_dev
task_scope: single_agent_single_task
priority: P0
goal: 落真实复验内部链路、因子库 summary/audit 和最小写入保护，并给外部调度提供稳定脚本入口
allowed_code_paths:
  - third_party/quantaalpha/quantaalpha/factors/library.py
  - third_party/quantaalpha/quantaalpha/backtest/runner.py
  - third_party/quantaalpha/quantaalpha/pipeline/factor_backtest.py
  - third_party/quantaalpha/scripts/continuous_mine.sh
  - third_party/quantaalpha/tests/test_revalidate_real_backtest.py
  - third_party/quantaalpha/tests/test_scheduler_summary.py
  - third_party/quantaalpha/tests/test_factor_library_locking.py
forbidden_code_paths:
  - third_party/quantaalpha/quantaalpha/cli.py
  - third_party/quantaalpha/quantaalpha/pipeline/loop.py
  - third_party/quantaalpha/quantaalpha/factors/status_rules.py
audit_required: true
---

# Task

单个 coding agent 负责真实复验内部链路、因子库 summary/audit、最小写入保护和调度脚本入口，不负责 CLI 模式语义。

## 开发目标

1. 落真实回测内部接入和结果消费。
2. 为因子库增加 summary 和最小审计能力。
3. 增加最小写锁和原子写保护。
4. 提供 `third_party/quantaalpha/scripts/continuous_mine.sh` 作为稳定调度入口。
5. 补齐 3 组开发侧测试文件。

## 只允许修改

- `third_party/quantaalpha/quantaalpha/factors/library.py`
- `third_party/quantaalpha/quantaalpha/backtest/runner.py`
- `third_party/quantaalpha/quantaalpha/pipeline/factor_backtest.py`
- `third_party/quantaalpha/scripts/continuous_mine.sh`
- `third_party/quantaalpha/tests/test_revalidate_real_backtest.py`
- `third_party/quantaalpha/tests/test_scheduler_summary.py`
- `third_party/quantaalpha/tests/test_factor_library_locking.py`

## 禁止修改

- `third_party/quantaalpha/quantaalpha/cli.py`
- `third_party/quantaalpha/quantaalpha/pipeline/loop.py`
- `third_party/quantaalpha/quantaalpha/factors/status_rules.py`

## 需要保留的审计材料

agent 必须在最终回答中明确给出：

1. 实际修改文件。
2. 每个文件的修改摘要。
3. 实际执行命令。
4. 哪些并发/环境相关验证未做。
5. 仍然存在的风险或未覆盖边界。

## 完成标准

1. 不通过修改 `cli.py` 规避脚本层失败语义。
2. 默认写路径仍对齐真实因子库路径。
3. 若并发验证受限，必须明说，不能伪造“已全部验证”。

