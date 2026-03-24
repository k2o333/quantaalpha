# Iterate 2 Deferred Follow-ups

Status: implemented
Owner: QuantaAlpha team
Created: 2026-03-20
Outcome: deferred-followups-recorded
Phase: 2
Depends-on:
- docs/03-changes/quantaalpha/2026-03-15-iterate2-01-revalidate-semantics-and-real-backtest.md
- docs/03-changes/quantaalpha/2026-03-15-iterate2-02-failed-factor-debug-filter.md
- docs/03-changes/quantaalpha/2026-03-15-iterate2-03-quality-gate-and-state-regression.md
- docs/03-changes/quantaalpha/2026-03-15-iterate2-04-external-scheduler-summary-and-audit.md
- docs/03-changes/quantaalpha/2026-03-15-iterate2-05-factor-library-write-lock.md
Related-to:
- /home/quan/testdata/aspipe_v4/docs/drafts/report/2026-3-20/iterate2_test_report.md

---

## Background

Iterate 2 的主链路缺口已经补齐并通过当前回归测试，但审查中仍有一批低优先级或条件性问题。

按仓库规则，这些项不能口头忽略，也不能继续写成“已完成”。因此把它们单独记录为 deferred follow-ups，供后续批次继续处理。

---

## Current Decision

本清单中的事项：

- 当前批次不阻塞 Iterate 2 主验收
- 不应写成“已完成”
- 只有在触发条件出现或进入下一轮硬化时才提升优先级

---

## Deferred Items

### 1. Scheduler failure policy for non-dry-run revalidate

Status: deferred
Priority: low
Code:
- `third_party/quantaalpha/quantaalpha/cli.py`
- `third_party/quantaalpha/scripts/continuous_mine.sh`

Current state:
- `continuous_mine.sh` 当前调用 `revalidate --dry_run True --no_write True`
- 因此单个坏因子不会因为 `status_refresh` 失败而中断调度循环

Why deferred:
- 这是未来脚本切换到非 dry-run 模式时才会暴露的调度策略问题
- 当前不是实际运行路径上的缺陷

Trigger to revisit:
- 调度脚本改为调用 `status_refresh` 或 `real_backtest`
- 需要为批量复验定义容错阈值或部分失败策略

---

### 2. pending_validation under status_refresh

Status: deferred
Priority: low
Code:
- `third_party/quantaalpha/quantaalpha/cli.py`
- `third_party/quantaalpha/quantaalpha/factors/status_rules.py`

Current state:
- `status_refresh` 复用历史 evaluation 结果
- 当因子仍是 `pending_validation` 且没有 `stability_score` 时，状态不会被推进

Why deferred:
- 这是语义选择，不是明确 bug
- 当前实现偏保守，避免在无新验证结果时伪造状态推进

Trigger to revisit:
- 产品层明确要求 `status_refresh` 也要推进 `pending_validation`
- 或者补充新的状态推进规则与验收测试

---

### 3. Retry filter observability

Status: deferred
Priority: low
Code:
- `third_party/quantaalpha/quantaalpha/pipeline/loop.py`

Current state:
- 第二轮开始时，retry filter 会过滤到失败因子集合
- 但没有记录过滤前后数量差异

Why deferred:
- 当前行为正确，问题在于可观测性不够

Trigger to revisit:
- 调试上游 experiment 输入不稳定
- 需要做 round-level 运维排障或调度统计

---

### 4. Defensive length checks in coder tracking

Status: deferred
Priority: low
Code:
- `third_party/quantaalpha/quantaalpha/pipeline/loop.py`

Current state:
- `_track_coder_result()` 依赖 `sub_tasks`、`sub_workspace_list` 与 `_current_round_factors` 的长度对齐

Why deferred:
- 当前路径下没有复现错位
- 属于防御性加固，不是已知主链路故障

Trigger to revisit:
- coder 输出开始支持部分结果或增量返回
- 出现长度错配类异常

---

### 5. Explicit comment for degraded fallthrough

Status: deferred
Priority: low
Code:
- `third_party/quantaalpha/quantaalpha/factors/status_rules.py`

Current state:
- `degraded` 状态在 stability 落在 `[degraded_threshold, active_threshold)` 时通过 fallthrough 维持原状态

Why deferred:
- 行为正确，只是代码可读性还有提升空间

Trigger to revisit:
- 下次修改状态机逻辑
- 或者需要补状态机说明注释时一并处理

---

### 6. Inline Python raw string style in scheduler

Status: deferred
Priority: low
Code:
- `third_party/quantaalpha/scripts/continuous_mine.sh`

Current state:
- 脚本内嵌 Python 使用 `r"${LIBRARY_PATH}"` 读取路径
- 在当前 Linux 路径语义下可正常工作

Why deferred:
- 这是风格与可移植性建议，不是当前缺陷

Trigger to revisit:
- 脚本需要跨平台运行
- 或者统一清理脚本风格

---

### 7. Hard dependency on .env in scheduler

Status: deferred
Priority: low
Code:
- `third_party/quantaalpha/scripts/continuous_mine.sh`

Current state:
- `.env` 缺失时脚本直接退出

Why deferred:
- 这代表当前脚本的环境约束，而不是实现错误
- 只有在要支持纯环境变量注入部署时，这条才会升级

Trigger to revisit:
- 容器化部署
- CI 调度直接注入 envvar
- 无 `.env` 的运维场景

---

### 8. Lock acquisition cleanup on flock exception

Status: deferred
Priority: low
Code:
- `third_party/quantaalpha/quantaalpha/factors/library.py`

Current state:
- `_acquire_lock()` 在极少数 `flock()` 异常路径上存在 fd 未关闭窗口

Why deferred:
- 风险很低，且当前并发主问题已经由锁内 merge + atomic replace 解决

Trigger to revisit:
- 下次修改文件锁实现
- 或者统一收口资源释放路径

---

### 9. Multiprocess coverage for factor-library locking

Status: deferred
Priority: low
Code:
- `third_party/quantaalpha/tests/test_factor_library_locking.py`

Current state:
- 当前并发验证主要覆盖线程级竞争
- 已能证明这轮修复解决了已复现的丢写问题

Why deferred:
- 属于进一步增强验证深度，不阻塞当前收口

Trigger to revisit:
- 需要声明多进程级并发保障
- 因子库写入模型再次调整

---

## What This Document Does Not Claim

- 不代表这些项已实现
- 不代表这些项已经被测试覆盖
- 不代表这些项在当前批次被接受为“已关闭”

---

## Recommended Next Use

后续如果继续 Iterate 2 硬化，建议按下面顺序处理：

1. 调度脚本在非 dry-run 模式下的失败策略
2. 锁实现与多进程验证
3. retry / status 相关的防御性与可观测性增强
