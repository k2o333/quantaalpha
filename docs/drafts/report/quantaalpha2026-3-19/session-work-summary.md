# QuantaAlpha 2026-03-19 Session Work Summary

## 1. 这份报告的范围

这份文档只记录**本次 session 明确做过的事情**，不把工作区里原本就存在的其它改动混进来。

本次 session 的主题是两部分：

1. 围绕 `ADR-003` 的 `Continuous Orchestrator` 写 `planned` 文档并细拆 task
2. 在 `third_party/quantaalpha/` 内落一个最小可运行的 `continuous orchestrator` 骨架，并补对应测试

注意：

- `docs/drafts/` 不是 source of truth，这份文档只是 session 记录
- 当前工作区是脏的，仓库里存在很多不是这次 session 产生的改动
- 本次 session **没有**实现完整的调度系统，只实现了“最小骨架”

---

## 2. 本次 session 做了什么

### 2.1 先读治理和模块文档

在开始写文档和代码之前，先读了这些文档来定边界：

- `docs/00-governance/agent.md`
- `docs/00-governance/rules.md`
- `docs/02-modules/quantaalpha.md`
- `docs/07-technical/quantaalpha-factor-mining-flow.md`
- `docs/04-decisions/ADR-003-external-continuous-factor-research-modules.md`
- `docs/05-playbooks/planned-doc-hardening-playbook.md`

目的：

- 确认 `quantaalpha` 的真实入口是 `third_party/quantaalpha/quantaalpha/cli.py`
- 确认这次工作属于高风险持续运行边界，不应该直接改成“大而全 orchestrator”
- 确认 planned 文档应强调 `Failure Semantics`、`Disproof Command` 和 `Move-to-tested gate`

### 2.2 写了 Continuous Orchestrator 的 planned 文档

新增了：

- `docs/03-changes/quantaalpha/planned/2026-03-18-continuous-orchestrator-minimal-skeleton.md`

这个文档做了两件事：

1. 把 `ADR-003` 中 `3.1 Continuous Orchestrator` 展开成一个真正可执行的 `planned` 文档
2. 把大块任务继续细拆成更原子的 task

文档里明确写了：

- 目标和非目标
- `Downstream Consumer`
- `Write Target / Source of Truth`
- `Failure Semantics`
- `Required Boundary Test`
- `Disproof Command`
- `What Does Not Count As Done`
- `Move Blockers / Move-to-Tested Conditions`

后面又继续把它原子化成：

- `Task 1A-1D`：模块骨架、枚举、数据契约、trigger 转 job
- `Task 2A-2D`：统一 runner 和不同 job 类型接线
- `Task 3A-3E`：队列、并发限制、重试、summary
- `Task 4A-4D`：Python facade、CLI、event 提交、CLI 输出
- `Task 5A-5B`：边界测试与 disproof/reviewer 复跑路径

### 2.3 用 TDD 落了最小 continuous orchestrator 骨架

在 `third_party/quantaalpha` 子仓库里，先写了 failing test，再补最小实现。

本次实际落下的骨架能力是：

- `quantaalpha.continuous` 模块入口
- `JobType` / `JobStatus` / `TriggerType`
- `JobSpec` / `JobResult` / `RunSummary` / `TriggerEvent`
- `ContinuousOrchestrator.build_jobs_for_trigger()`
- `ContinuousOrchestrator.run_once()`
- `quantaalpha.cli` 下的最小 `continuous run_once` CLI 入口

这个骨架当前的语义是：

- `schedule` trigger 会生成一个 `mining` job
- `event` trigger 会生成一个 `revalidation` job
- 默认 runner 不执行业务主链，只返回 `deferred`
- CLI 能跑通并输出结构化 summary

这意味着：

- 已经有“最小可运行入口”
- 但**还没有**真实 job runner、队列、并发限制、重试、失败阶段归因

---

## 3. 这次 session 明确改过哪些文件

下面这些文件是本次 session 明确动过的。

### 3.1 新增 / 更新的文档

#### `docs/03-changes/quantaalpha/planned/2026-03-18-continuous-orchestrator-minimal-skeleton.md`

类型：

- 新增

改了什么：

- 写了 `Continuous Orchestrator` 的完整 `planned` 文档
- 补了高风险边界需要的完成判据和反假完成约束
- 后续又在文档里追加了更细的原子任务拆分

### 3.2 新增的代码文件

#### `third_party/quantaalpha/quantaalpha/continuous/__init__.py`

类型：

- 新增

改了什么：

- 暴露 `ContinuousOrchestrator`
- 暴露 `JobSpec` / `JobResult` / `RunSummary`
- 暴露 `JobType` / `JobStatus`
- 暴露 `TriggerEvent` / `TriggerType`

#### `third_party/quantaalpha/quantaalpha/continuous/job_models.py`

类型：

- 新增

改了什么：

- 定义 `JobType`
- 定义 `JobStatus`
- 定义 `JobSpec`
- 定义 `JobResult`
- 定义 `RunSummary`
- 给这些对象补了稳定的 `to_dict()` 序列化输出

重点设计：

- `JobSpec` 固定了 `job_id/job_type/trigger_type/payload/max_retries/priority/requested_at`
- `JobResult` 固定了 `status/attempt_count/failed_stage/error_message/upstream_result_ref`
- `RunSummary.from_results()` 负责聚合：
  - `total_jobs`
  - `success_jobs`
  - `failed_jobs`
  - `retried_jobs`
  - `throttled_or_rejected_jobs`
  - `status_counts`

#### `third_party/quantaalpha/quantaalpha/continuous/trigger_models.py`

类型：

- 新增

改了什么：

- 定义 `TriggerType`
- 定义 `TriggerEvent`
- 固定 `trigger_type/event_type/event_time/scope/version_hint` 的序列化结构

#### `third_party/quantaalpha/quantaalpha/continuous/orchestrator.py`

类型：

- 新增

改了什么：

- 新增 `ContinuousOrchestrator`
- 新增 `_default_runner()`，当前默认返回 `JobStatus.DEFERRED`
- 新增 `build_jobs_for_trigger()`
- 新增 `run_once()`

当前逻辑：

- `schedule` -> 生成一个 `mining` job
- `event` -> 生成一个 `revalidation` job
- `run_once()` 会对生成的 job 调 runner，再把结果聚合成 `RunSummary`

### 3.3 修改的代码文件

#### `third_party/quantaalpha/quantaalpha/cli.py`

类型：

- 修改

这次 session 明确加了什么：

- 新增从 `quantaalpha.continuous` 导入：
  - `ContinuousOrchestrator`
  - `TriggerEvent`
  - `TriggerType`
- 新增 `_ContinuousCLI` 类
- 新增 `run_once()` 方法：
  - 把 CLI 参数翻成 `TriggerEvent`
  - 调 `ContinuousOrchestrator.run_once()`
  - 返回 `RunSummary.to_dict()`
- 在 `fire.Fire(...)` 的命令字典里注册了：
  - `"continuous": _ContinuousCLI()`

结果：

- 现在可以执行：

```bash
PYTHONPATH=/home/quan/testdata/aspipe_v4/third_party/quantaalpha \
/root/miniforge3/envs/mining/bin/python -m quantaalpha.cli continuous run_once \
  --trigger_type schedule \
  --event_type daily_tick
```

需要特别说明：

- `cli.py` 里还有大量其它 diff，但从本次 session 的明确操作来看，和 `continuous orchestrator` 直接相关、可以确定是本 session 新加的是上面这组 `continuous` 入口
- `cli.py` 中其它 `revalidate` 相关大改动是否来自本 session，单靠当前工作区状态无法安全断言，所以这里不把它们算进本次结论

### 3.4 新增的测试文件

#### `third_party/quantaalpha/tests/test_continuous_orchestrator.py`

类型：

- 新增

改了什么：

- 先写 failing test，再补实现
- 覆盖了最小 continuous orchestrator 骨架

当前测试覆盖点：

1. `JobSpec` 的稳定字段序列化
2. `JobResult` 默认值和失败相关字段
3. `RunSummary` 的聚合统计
4. `TriggerEvent` 的序列化
5. `schedule` trigger -> `mining` job 的转换
6. `event` trigger -> `revalidation` job 的转换
7. `run_once()` 的 summary 聚合
8. subprocess 级别的 CLI 边界测试：
   - `quantaalpha.cli continuous run_once ...` 返回 0
   - 输出包含 `total_jobs` 和 `success_jobs`

---

## 4. 这个 session 的实现顺序

### 第一步：先写测试，让它失败

先新增了：

- `third_party/quantaalpha/tests/test_continuous_orchestrator.py`

先跑：

```bash
/root/miniforge3/envs/mining/bin/python -m pytest third_party/quantaalpha/tests/test_continuous_orchestrator.py -q
```

第一次失败是因为：

- `ModuleNotFoundError: No module named 'quantaalpha.continuous'`

后面追加 CLI 测试后，再次失败是因为：

- `ERROR: Cannot find key: continuous`

这两个失败都是预期的红灯，分别证明：

- `continuous` 模块确实还不存在
- `continuous` CLI 命令也确实还没接上

### 第二步：补最小实现让测试变绿

补了：

- `quantaalpha/continuous/__init__.py`
- `quantaalpha/continuous/job_models.py`
- `quantaalpha/continuous/trigger_models.py`
- `quantaalpha/continuous/orchestrator.py`
- `quantaalpha/cli.py` 里的 `continuous` 命令入口

然后重新跑同一个测试文件，最后变成：

- `8 passed`

---

## 5. 这次 session 实际跑过哪些验证

### 5.1 测试

实际执行过：

```bash
/root/miniforge3/envs/mining/bin/python -m pytest third_party/quantaalpha/tests/test_continuous_orchestrator.py -q
```

最终结果：

- `8 passed`

### 5.2 真实 CLI 边界命令

实际执行过：

```bash
PYTHONPATH=/home/quan/testdata/aspipe_v4/third_party/quantaalpha \
/root/miniforge3/envs/mining/bin/python -m quantaalpha.cli continuous run_once \
  --trigger_type schedule \
  --event_type daily_tick
```

实际输出关键字段：

- `total_jobs: 1`
- `success_jobs: 0`
- `failed_jobs: 0`
- `retried_jobs: 0`
- `throttled_or_rejected_jobs: 1`
- `status_counts: {"deferred": 1}`

这说明：

- CLI 入口确实接通了
- 但默认 runner 目前只是 `deferred`
- 还没有真实接入主链执行

### 5.3 编译检查

实际执行过：

```bash
/root/miniforge3/envs/mining/bin/python -m compileall \
  /home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/continuous \
  /home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/cli.py
```

结果：

- 通过

---

## 6. 这次 session 没有做什么

为了避免误判，这里明确写清楚这次**没有**完成的部分。

本次没有完成：

- 真实 `job_runner`
- `mining/revalidation/library_maintenance` 的真实主链调用
- 队列
- 并发限制
- 重试
- 失败阶段归因
- `submit_event` CLI
- 可被 scheduler 直接消费的非零退出码策略

也就是说，本次只完成了：

- 文档
- 最小数据契约
- 最小 Python facade
- 最小 CLI 入口
- 最小测试护栏

---

## 7. 当前工作区里还有哪些不是这次 session 明确产生的改动

当前工作区明显不是干净的。

例如在 `third_party/quantaalpha/` 下，还能看到很多其它改动或新增文件：

- `configs/experiment.yaml`
- `quantaalpha/backtest/runner.py`
- `quantaalpha/backtest/validation.py`
- `quantaalpha/factors/data_capability.py`
- `quantaalpha/factors/experiment.py`
- `quantaalpha/factors/library.py`
- `quantaalpha/factors/status_rules.py`
- `tests/test_revalidate_cli.py`
- `tests/test_scheduler_summary.py`
- 等等

这些文件虽然当前处于修改或未跟踪状态，但**不能仅凭当前状态就断言都是这次 session 改的**。

因此，这份报告只把下面这些文件作为本 session 的明确产物：

- `docs/03-changes/quantaalpha/planned/2026-03-18-continuous-orchestrator-minimal-skeleton.md`
- `third_party/quantaalpha/quantaalpha/continuous/__init__.py`
- `third_party/quantaalpha/quantaalpha/continuous/job_models.py`
- `third_party/quantaalpha/quantaalpha/continuous/trigger_models.py`
- `third_party/quantaalpha/quantaalpha/continuous/orchestrator.py`
- `third_party/quantaalpha/quantaalpha/cli.py` 中的 `continuous` 相关入口
- `third_party/quantaalpha/tests/test_continuous_orchestrator.py`

---

## 8. 一句话结论

这个 session 到目前为止，核心产出是：

- 把 `ADR-003 / Continuous Orchestrator` 写成了一个高约束 `planned` 文档
- 在 `quantaalpha` 里落了一个**最小可运行但还未接主链的 continuous orchestrator 骨架**
- 用测试和真实 CLI 命令证明这个骨架已经能被调用，但当前还只是 `deferred` 骨架，不是完整调度实现
