---
status: planned
owner: Codex
created: 2026-03-18
parallel_mode: true
parallel_group: quantaalpha-iterate2-pilot
slice_id: slice_1
priority: P0
parent_source_docs:
  - docs/03-changes/quantaalpha/planned/2026-03-15-iterate2-01-revalidate-semantics-and-real-backtest.md
goal: 固定 revalidate 的 CLI 语义边界，让 dry-run、status-refresh、real-backtest 三种模式在命令入口和返回结构上可区分
allowed_code_paths:
  - third_party/quantaalpha/quantaalpha/cli.py
  - third_party/quantaalpha/tests/test_revalidate_cli.py
forbidden_code_paths:
  - third_party/quantaalpha/quantaalpha/factors/library.py
  - third_party/quantaalpha/quantaalpha/pipeline/loop.py
  - third_party/quantaalpha/quantaalpha/backtest/runner.py
  - third_party/quantaalpha/quantaalpha/pipeline/factor_backtest.py
test_targets:
  - third_party/quantaalpha/tests/test_revalidate_cli.py
disproof_command: /root/miniforge3/envs/mining/bin/python -m pytest third_party/quantaalpha/tests/test_revalidate_cli.py -q
---

# Parallel Slice 1: Revalidate CLI Modes

## 目标

把 `revalidate` 的 CLI 入口语义拆清楚：

- 默认模式是 `status_refresh`
- `--dry-run` 只输出候选和模式信息
- `--real-backtest` 显式声明要走真实复验链路

本切片只负责命令入口、参数路由、输出字段和失败可见性，不负责真实回测内部实现。

## 输入契约

- 真实复验的内部执行器可暂时视为一个既有能力，通过稳定调用接口消费
- 本切片必须保留 Python 调用方可消费的返回结构
- CLI 调用方必须能从退出码和标准输出分辨失败

## 输出契约

`revalidate` 返回结构至少包含：

- `mode`
- `total_candidates`
- `success`
- `failed`
- `skipped`
- `used_existing_results`
- `details`

其中：

- 默认模式必须返回 `mode=status_refresh`
- `--dry-run` 必须返回 `mode=dry_run`
- `--real-backtest` 必须返回 `mode=real_backtest`

## 必须做的事

1. 在 `cli.py` 中固定三种模式的命令入口语义和帮助文案。
2. 让 CLI 输出和返回结构明确区分三种模式。
3. 保证 CLI 失败场景可见，不把真实失败藏在内部 report 字段里。
4. 新增或补齐 `test_revalidate_cli.py`，覆盖三种模式的入口语义。

## 明确不做

1. 不在本切片中落真实回测内部链路。
2. 不改因子库写入逻辑。
3. 不改状态流转规则。
4. 不改调度脚本。

## 测试要求

自动化测试至少覆盖：

1. 默认模式返回 `mode=status_refresh`。
2. `--dry-run` 不写库，只返回候选。
3. `--real-backtest` 在入口层被正确识别，不会被伪装成状态刷新。
4. CLI 失败场景能返回非零退出码或显式失败结果。
5. Python 调用返回结构不因 CLI 失败语义而被破坏。

## 通过标准

必须同时满足：

1. `test_revalidate_cli.py` 能独立通过。
2. 三种模式在命令帮助和运行结果中都可区分。
3. 没有通过修改 `library.py` 或真实回测内部实现来“偷完成”本切片。

