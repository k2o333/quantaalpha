---
doc_type: change
module: quantaalpha
status: planned
owner: Codex
created: 2026-03-18
updated: 2026-03-18
summary: Parallel Slice 2: Real Backtest And Library Operations
parallel_mode: true
parallel_group: quantaalpha-iterate2-pilot
slice_id: slice_2
priority: P0
parent_source_docs:
  - 2026-03-15-iterate2-01-revalidate-semantics-and-real-backtest.md
  - 2026-03-15-iterate2-04-external-scheduler-summary-and-audit.md
  - 2026-03-15-iterate2-05-factor-library-write-lock.md
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
test_targets:
  - third_party/quantaalpha/tests/test_revalidate_real_backtest.py
  - third_party/quantaalpha/tests/test_scheduler_summary.py
  - third_party/quantaalpha/tests/test_factor_library_locking.py
disproof_command: /root/miniforge3/envs/mining/bin/python -m pytest third_party/quantaalpha/tests/test_revalidate_real_backtest.py third_party/quantaalpha/tests/test_scheduler_summary.py third_party/quantaalpha/tests/test_factor_library_locking.py -q
---

# Parallel Slice 2: Real Backtest And Library Operations

## 目标

把真实复验的内部执行路径、因子库写边界和调度侧最小可观测性一起固定下来。

这个切片负责：

- 真实回测内部接入和结果消费
- 因子库 summary 与状态审计
- 因子库最小写锁和原子写
- 标准调度脚本

它不负责 CLI 模式语义本身，那是 slice 1 的职责。

## 输入契约

- CLI 已经或将会以稳定参数调用真实复验模式
- `FactorLibraryManager` 仍是因子库真实写入口
- 调度器只能消费脚本退出码和标准输出

## 输出契约

本切片必须保证：

1. 真实复验失败不会污染旧 `period_results`。
2. 因子库写入失败不会破坏原 JSON。
3. 脚本层能提供稳定 summary，并在失败时返回非零退出码。
4. 状态变化有最小审计记录，且只围绕真实因子库路径。

## 必须做的事

1. 在真实回测内部路径中接住输入并安全消费结果。
2. 为 `FactorLibraryManager` 增加 summary 和最小审计能力。
3. 为真实因子库 JSON 增加最小写锁和原子写。
4. 新增 `scripts/continuous_mine.sh` 作为调度入口。
5. 补齐 3 组测试：真实复验、summary/audit、写保护。

## 明确不做

1. 不改 `cli.py` 的模式路由和帮助文案。
2. 不改 debug 轮次失败因子筛选。
3. 不改质量门控或状态阈值规则。

## 测试要求

自动化测试至少覆盖：

1. 真实复验成功时，结果能被正确消费并回写。
2. 真实复验失败时，旧 `period_results` 保持不变。
3. library summary 能正确统计多状态分布。
4. 审计只在状态发生变化时追加。
5. 写入失败时原文件仍保持有效 JSON。
6. 并发或连续写入后 JSON 不会截断。
7. `continuous_mine.sh` 在下游失败时返回非零退出码。

## 通过标准

必须同时满足：

1. 3 个目标测试文件能一起独立通过。
2. 没有通过修改 `cli.py` 来规避脚本层失败语义。
3. 默认写路径与真实因子库路径一致。
4. 若并发验证受环境限制，必须在报告中明确标注边界，不能写成“全部验证完毕”。

