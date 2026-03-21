---
doc_type: change
module: quantaalpha
status: planned
owner: quan
created: 2026-03-18
updated: 2026-03-18
summary: Continuous Orchestrator 最小持续编排骨架
priority: P1
depends_on:
  - docs/04-decisions/ADR-003-external-continuous-factor-research-modules.md
---

---

## 一、目标

为 `ADR-003` 中 `### 3.1 Continuous Orchestrator` 落地一个**最小可运行、可验证、可回退**的外插编排骨架，使持续研究系统第一次具备以下能力：

- 用统一入口编排 `Mining`、`Validation`、`Revalidation`、`Library Maintenance` 等独立作业
- 同时支持 `schedule` 与 `event` 两类触发源
- 在编排层承担排队、并发限制、重试和失败归因
- 通过稳定结构化结果把运行语义暴露给后续 `observability-and-alerting` 与 `continuous-test-harness`

本迭代解决的问题不是“上生产级分布式调度平台”，而是先把 `quantaalpha` 外层的持续运行控制面从散乱脚本和口头约定，收敛成一套最小但真实可消费的 orchestrator 骨架。

---

## 二、范围

包含：

- 一个统一的 orchestrator 模块入口
- 一个标准 job 定义与 job result 结构
- 一个最小事件/计划触发适配层
- 一个本地队列或队列化执行模型
- 并发限制、重试次数、失败阶段归因
- 通过 CLI 或 Python facade 调用 `quantaalpha` 主链
- 自动化测试与最小边界验收命令

不包含：

- 分布式消息队列
- 常驻 daemon / service manager
- 复杂优先级调度算法
- 抢占式资源调度
- observability 平台接入
- trigger 的上游发现逻辑
- 在 orchestrator 中复制回测、状态流转或因子库写逻辑

### 2.1 Downstream Consumer

- `observability-and-alerting`：消费结构化 job 结果、失败阶段、重试摘要
- `continuous-test-harness`：通过稳定 orchestrator 入口做黑盒系统测试
- 后续 `data-update-trigger`：把标准事件交给 orchestrator，而不是直连主链
- operator / scheduler：通过 orchestrator 的退出码和结构化输出判断本轮是否成功

### 2.2 Write Target / Source of Truth

- orchestrator 自身的 source-of-truth 应是：
  - 标准 job spec
  - 标准 job result
  - 队列状态或运行态记录
- `quantaalpha` 因子库仍然是主链 source-of-truth：
  - orchestrator 不得直接绕过 `quantaalpha` 写因子库 JSON
  - orchestrator 不得重新维护一份平行状态库来解释因子状态

### 2.3 Failure Semantics

- 单个 job 在主链调用失败时必须返回明确失败状态，而不是只打印日志
- 超过最大重试次数时必须返回终态失败，并保留失败阶段归因
- 被限流、延后或拒绝执行的 job 必须有可区分的结构化状态，不能与“运行失败”混淆
- 批量执行中某一项失败时，外层调用方必须能判断：
  - 哪个 job 失败
  - 失败发生在哪个阶段
  - 是否已经发生过重试

### 2.4 Caller Contract

- CLI 调用方：通过退出码和结构化输出消费 orchestrator 结果
- Python 调用方：通过 facade 拿到稳定 `JobResult` / `RunSummary`
- reviewer：必须能从真实 orchestrator 入口验证主链是被统一调度，而不是只看到几个 helper 函数

### 2.5 What Does Not Count As Done

- 只新增 orchestrator 目录或类定义，不算完成
- 只把多个 CLI 调用串起来，不做 job/result 契约，不算完成
- 只做日志汇总，不提供失败阶段和重试语义，不算完成
- 只做内存里的队列演示，不验证真实主链调用路径，不算完成
- 只证明 orchestrator 能“调起命令”，不核对并发限制、失败归因和重试边界，不算完成

---

## 三、代码落点

建议新增：

- `third_party/quantaalpha/quantaalpha/continuous/orchestrator.py`
- `third_party/quantaalpha/quantaalpha/continuous/job_models.py`
- `third_party/quantaalpha/quantaalpha/continuous/job_runner.py`
- `third_party/quantaalpha/quantaalpha/continuous/trigger_models.py`
- `third_party/quantaalpha/quantaalpha/continuous/__init__.py`
- `third_party/quantaalpha/tests/test_continuous_orchestrator.py`

建议修改：

- `third_party/quantaalpha/quantaalpha/cli.py`
- 如已有持续研究入口或脚本，也应改为调用 orchestrator，而不是继续平铺控制流

如需补配置，优先新增轻量配置：

- `third_party/quantaalpha/configs/continuous_orchestrator.yaml`

---

## 四、开发方案

### 4.1 先固定最小编排对象模型

先收敛以下基础对象：

- `JobType`
  - `mining`
  - `validation`
  - `revalidation`
  - `library_maintenance`
- `TriggerType`
  - `schedule`
  - `event`
- `JobSpec`
- `JobResult`
- `RunSummary`

`JobSpec` 至少包含：

- `job_id`
- `job_type`
- `trigger_type`
- `payload`
- `max_retries`
- `priority` 或保守默认值
- `requested_at`

`JobResult` 至少包含：

- `job_id`
- `job_type`
- `status`
- `attempt_count`
- `failed_stage`
- `started_at`
- `finished_at`
- `error_message`
- `upstream_result_ref` 或结构化摘要

约束：

- 字段顺序和命名应稳定，便于测试和后续 observability 消费
- 首版不做复杂泛型体系，保持简单可读

### 4.2 统一主链调用边界

orchestrator 不应直接拼接私有内部控制流，而应通过稳定边界调用主链：

- 优先使用 Python facade
- 如果当前 facade 不足，再受控补一个最小 facade
- 若暂时只能走 CLI，也必须把 CLI 调用收敛到单一 runner，而不是到处 `subprocess`

建议新增一个统一 runner：

- `run_job(job_spec: JobSpec) -> JobResult`

它负责：

1. 根据 `job_type` 选择主链入口
2. 统一捕获异常
3. 统一生成结构化结果
4. 统一记录失败阶段

约束：

- 不在 runner 中重新解释因子状态规则
- 不在 runner 中直接读写因子库 JSON 以补业务逻辑

### 4.3 实现最小排队与并发限制

首版编排器不引入外部队列，采用仓库内可验证的最小模型即可：

- FIFO 队列或保守优先级队列
- `max_concurrent_jobs`
- `max_queue_size`
- 资源不足时延后或拒绝入队

建议暴露：

- `submit_job(job_spec: JobSpec) -> EnqueueResult`
- `drain_once() -> RunSummary`
- `run_once(trigger_input: TriggerEvent | None = None) -> RunSummary`

约束：

- 并发模型必须可测，不要求追求高吞吐
- 如果首版为了降低风险选择串行执行，也必须把并发限制字段和拒绝语义留出来
- 背压状态必须是结构化可见的，而不是只在日志里说“稍后重试”

### 4.4 定义重试和失败归因

重试语义是本迭代的核心约束之一。

至少需要：

- 同一 job 的最大重试次数
- 每次尝试结果记录
- 终态失败时保留 `failed_stage`
- 不可重试错误与可重试错误的最小区分

建议首版失败阶段至少区分：

- `enqueue`
- `dispatch`
- `invoke_mainline`
- `collect_result`

约束：

- 不允许“失败了但 summary 还是 success”
- 不允许丢失最后一次失败原因
- 不允许重试次数只体现在日志文本中

### 4.5 支持 schedule/event 两类触发入口

本迭代不负责上游 trigger 发现，但 orchestrator 必须能消费两类统一输入：

- `schedule`：例如 cron 或固定周期触发
- `event`：例如 manifest 更新或显式事件文件触发

建议新增：

- `TriggerEvent`

字段至少包括：

- `trigger_type`
- `event_type`
- `event_time`
- `scope`
- `version_hint`

约束：

- orchestrator 接收到 trigger 后，必须转成标准 `JobSpec`
- 首版不要求复杂规则引擎，只要求可稳定把触发转换成 job

### 4.6 暴露最小 CLI / facade

需要一个 reviewer 可直接调用的稳定入口。

建议两种方式至少完成一种，最好两种都具备：

1. `cli.py` 增加最小子命令，例如：
   - `continuous run-once`
   - `continuous submit-event`
2. Python facade：
   - `ContinuousOrchestrator.run_once(...)`

CLI 输出至少包含：

- 总 job 数
- 成功数
- 失败数
- 重试数
- 被限流/拒绝数
- 每类 job 的状态摘要

约束：

- CLI 退出码必须能被调度器直接消费
- 不能把内部 Python report 当作 CLI 成功语义替代品

### 4.7 实现顺序清单

#### Task 1: 固定 job/result/trigger 契约

**目标：** 先把 orchestrator 的输入输出结构锁定，避免后续实现分叉。

**修改文件：**

- `third_party/quantaalpha/quantaalpha/continuous/job_models.py`
- `third_party/quantaalpha/quantaalpha/continuous/trigger_models.py`
- `third_party/quantaalpha/tests/test_continuous_orchestrator.py`

**本任务完成判据：**

- `JobSpec`、`JobResult`、`RunSummary`、`TriggerEvent` 都有稳定字段
- 结构可序列化
- 测试能断言默认值、字段完整性和状态枚举

#### Task 2: 接上统一 job runner

**目标：** 让所有 job 类型都通过一个真实主链调用边界执行。

**修改文件：**

- `third_party/quantaalpha/quantaalpha/continuous/job_runner.py`
- `third_party/quantaalpha/quantaalpha/cli.py`

**本任务完成判据：**

- `mining` / `revalidation` / `library_maintenance` 至少有可映射的调用路径
- 异常会转成 `JobResult.failed`
- 失败阶段能被稳定断言

#### Task 3: 增加最小队列、并发限制和重试

**目标：** 把 orchestrator 变成真实控制面，而不是一个简单 for-loop。

**修改文件：**

- `third_party/quantaalpha/quantaalpha/continuous/orchestrator.py`
- `third_party/quantaalpha/tests/test_continuous_orchestrator.py`

**本任务完成判据：**

- 可提交多个 job
- 达到限制时会排队、延后或拒绝
- 可重试错误会按上限重试
- summary 能显示最终聚合结果

#### Task 4: 暴露最小 CLI / facade 并补边界验证

**目标：** 给后续 trigger、observability、test harness 和 reviewer 一个真实可复跑入口。

**修改文件：**

- `third_party/quantaalpha/quantaalpha/cli.py`
- `third_party/quantaalpha/tests/test_continuous_orchestrator.py`

**本任务完成判据：**

- CLI 能执行一次最小 orchestrator run
- CLI 输出结构稳定
- 失败时退出码非零
- reviewer 可通过单条命令看到结构化结果

### 4.8 更细的原子任务拆分

下面把上面的 4 个开发块继续拆成更适合单次实现和 review 的细任务。原则：

- 每个任务只收敛一个边界
- 每个任务都应有清晰允许修改文件
- 先锁契约，再接主链，再加控制流，最后补 CLI 和验收
- 任一细任务完成后，都不应声称整个 orchestrator 已完成

#### Task 1A: 建立 continuous 模块骨架

**目标：** 先把目录和最小导出边界固定下来，防止后面实现在散落文件中生长。

**只建议修改：**

- `third_party/quantaalpha/quantaalpha/continuous/__init__.py`
- 如不存在，可新增：
  - `third_party/quantaalpha/quantaalpha/continuous/job_models.py`
  - `third_party/quantaalpha/quantaalpha/continuous/trigger_models.py`

**完成标准：**

- `continuous/` 成为明确的最小模块入口
- 不把实现先塞进 `cli.py`
- 对外导出对象名初步固定

#### Task 1B: 固定 JobType / TriggerType / JobStatus

**目标：** 把枚举和状态名锁定，避免测试和输出字段来回改名。

**只建议修改：**

- `third_party/quantaalpha/quantaalpha/continuous/job_models.py`
- `third_party/quantaalpha/quantaalpha/continuous/trigger_models.py`
- `third_party/quantaalpha/tests/test_continuous_orchestrator.py`

**完成标准：**

- `JobType`、`TriggerType`、`JobStatus` 有稳定枚举值
- 至少覆盖 `success` / `failed` / `rejected` / `deferred`
- 测试能断言非法值不会静默混入

#### Task 1C: 固定 JobSpec / JobResult / RunSummary 字段

**目标：** 把结构化契约固定成可序列化数据模型。

**只建议修改：**

- `third_party/quantaalpha/quantaalpha/continuous/job_models.py`
- `third_party/quantaalpha/tests/test_continuous_orchestrator.py`

**完成标准：**

- `JobSpec` 字段覆盖 `job_id/job_type/trigger_type/payload/max_retries/requested_at`
- `JobResult` 字段覆盖 `status/attempt_count/failed_stage/error_message`
- `RunSummary` 字段覆盖 `total/success/failed/retried/rejected_or_deferred`
- 至少一个测试断言序列化输出字段稳定

#### Task 1D: 固定 TriggerEvent 到 JobSpec 的转换规则

**目标：** 把 `schedule` / `event` 两类输入转换成统一 job 的规则单独固定。

**只建议修改：**

- `third_party/quantaalpha/quantaalpha/continuous/trigger_models.py`
- `third_party/quantaalpha/quantaalpha/continuous/orchestrator.py`
- `third_party/quantaalpha/tests/test_continuous_orchestrator.py`

**完成标准：**

- `schedule` 触发最少能生成一条标准 job
- `event` 触发最少能生成一条标准 job
- 转换逻辑不直接落在 CLI 参数解析里

#### Task 2A: 建立统一 runner 壳层

**目标：** 先把“如何调用主链”收口成一个函数，不急着把所有 job 都接完。

**只建议修改：**

- `third_party/quantaalpha/quantaalpha/continuous/job_runner.py`
- `third_party/quantaalpha/tests/test_continuous_orchestrator.py`

**完成标准：**

- 存在 `run_job(job_spec)` 统一入口
- 未支持的 `job_type` 会返回可识别失败，而不是静默跳过
- runner 不直接承担排队和重试

#### Task 2B: 接通 `mining` 调用路径

**目标：** 先打通一个真实主链 job，验证 runner 边界是可工作的。

**只建议修改：**

- `third_party/quantaalpha/quantaalpha/continuous/job_runner.py`
- `third_party/quantaalpha/quantaalpha/cli.py`
- `third_party/quantaalpha/tests/test_continuous_orchestrator.py`

**完成标准：**

- `mining` 能映射到真实主链入口
- 主链成功时返回 `JobResult.success`
- 主链异常时返回 `invoke_mainline` 失败归因

#### Task 2C: 接通 `revalidation` / `validation` 调用路径

**目标：** 把研究后续作业也纳入统一 runner，而不是留下专门分支。

**只建议修改：**

- `third_party/quantaalpha/quantaalpha/continuous/job_runner.py`
- `third_party/quantaalpha/quantaalpha/cli.py`
- `third_party/quantaalpha/tests/test_continuous_orchestrator.py`

**完成标准：**

- `revalidation` 至少有真实调用映射
- 如果 `validation` 当前无稳定入口，必须写清 fallback 或显式未支持语义
- 不能为了接通测试而绕过真实主链边界

#### Task 2D: 接通 `library_maintenance` 或定义显式未支持语义

**目标：** 避免 job type 列表里存在“名义支持、实际空实现”的状态。

**只建议修改：**

- `third_party/quantaalpha/quantaalpha/continuous/job_runner.py`
- `third_party/quantaalpha/tests/test_continuous_orchestrator.py`

**完成标准：**

- 要么有真实调用路径
- 要么返回稳定 `unsupported` / `failed` 语义并有测试覆盖

#### Task 3A: 建立最小队列容器

**目标：** 把 orchestrator 从“直接执行函数”升级成可提交 job 的控制面。

**只建议修改：**

- `third_party/quantaalpha/quantaalpha/continuous/orchestrator.py`
- `third_party/quantaalpha/tests/test_continuous_orchestrator.py`

**完成标准：**

- 存在 `submit_job()`
- job 会进入队列或明确被拒绝
- 队列状态可由测试断言

#### Task 3B: 固定 `max_queue_size` 和拒绝语义

**目标：** 先把背压入口做出来，避免队列无限增长。

**只建议修改：**

- `third_party/quantaalpha/quantaalpha/continuous/orchestrator.py`
- `third_party/quantaalpha/tests/test_continuous_orchestrator.py`

**完成标准：**

- 超过队列上限时不会继续接收 job
- 返回结构中能区分 `rejected`
- 不把拒绝语义只写进日志

#### Task 3C: 固定 `max_concurrent_jobs` 和 drain 行为

**目标：** 把并发限制做成真实控制流，而不是文档口径。

**只建议修改：**

- `third_party/quantaalpha/quantaalpha/continuous/orchestrator.py`
- `third_party/quantaalpha/tests/test_continuous_orchestrator.py`

**完成标准：**

- `drain_once()` 会按并发上限取 job
- 即使首版内部串行执行，也能体现上限控制语义
- summary 中可见被执行和未执行 job 的数量

#### Task 3D: 加入重试计数与终态失败

**目标：** 让 orchestrator 对失败 job 有最小恢复能力。

**只建议修改：**

- `third_party/quantaalpha/quantaalpha/continuous/orchestrator.py`
- `third_party/quantaalpha/quantaalpha/continuous/job_runner.py`
- `third_party/quantaalpha/tests/test_continuous_orchestrator.py`

**完成标准：**

- 可重试错误按 `max_retries` 处理
- 超过重试次数后转为终态失败
- `attempt_count` 和最后失败原因可见

#### Task 3E: 聚合 RunSummary

**目标：** 让调用方消费聚合结果，而不是自己遍历内部 job list。

**只建议修改：**

- `third_party/quantaalpha/quantaalpha/continuous/orchestrator.py`
- `third_party/quantaalpha/quantaalpha/continuous/job_models.py`
- `third_party/quantaalpha/tests/test_continuous_orchestrator.py`

**完成标准：**

- `RunSummary` 会聚合成功、失败、重试、拒绝/延后数量
- 汇总结果字段名稳定
- 不把 summary 计算分散到 CLI 和 orchestrator 两处

#### Task 4A: 暴露 Python facade

**目标：** 先给系统内调用方一个稳定入口，再补 CLI。

**只建议修改：**

- `third_party/quantaalpha/quantaalpha/continuous/orchestrator.py`
- `third_party/quantaalpha/quantaalpha/continuous/__init__.py`
- `third_party/quantaalpha/tests/test_continuous_orchestrator.py`

**完成标准：**

- 可通过 `ContinuousOrchestrator.run_once(...)` 触发一次最小执行
- 返回值为稳定 `RunSummary`
- 不要求这一阶段就完成 CLI 参数设计

#### Task 4B: 暴露 `continuous run-once` CLI

**目标：** 给 scheduler / reviewer 一个真实可复跑入口。

**只建议修改：**

- `third_party/quantaalpha/quantaalpha/cli.py`
- `third_party/quantaalpha/tests/test_continuous_orchestrator.py`

**完成标准：**

- CLI 可执行一次最小 orchestrator run
- 正常成功时退出码为 0
- 主链失败时退出码非 0

#### Task 4C: 暴露 `continuous submit-event` CLI

**目标：** 为后续 `data-update-trigger` 接入保留统一投递口。

**只建议修改：**

- `third_party/quantaalpha/quantaalpha/cli.py`
- `third_party/quantaalpha/tests/test_continuous_orchestrator.py`

**完成标准：**

- CLI 能把 event 参数转换成 `TriggerEvent`
- event 输入校验失败时退出码非 0
- 不在 CLI 层直接改写主链控制流

#### Task 4D: 固定 CLI 输出字段和失败语义

**目标：** 把下游真正消费的输出面锁定下来。

**只建议修改：**

- `third_party/quantaalpha/quantaalpha/cli.py`
- `third_party/quantaalpha/tests/test_continuous_orchestrator.py`

**完成标准：**

- CLI 输出至少包含 `total_jobs/success_jobs/failed_jobs/retried_jobs/throttled_or_rejected_jobs`
- 失败阶段可在输出或结构化结果中看到
- 不允许“summary 有 failed 但退出码仍为 0”

#### Task 5A: 补 Required Boundary Test

**目标：** 把“真正完成”需要的边界证据单独落成测试，不和对象模型测试混在一起。

**只建议修改：**

- `third_party/quantaalpha/tests/test_continuous_orchestrator.py`

**完成标准：**

- 至少 1 个测试证明 orchestrator 通过统一 runner 调用主链
- 至少 1 个测试证明失败退出码对调用方可见

#### Task 5B: 固定 Disproof Command 与 reviewer 复跑路径

**目标：** 让 reviewer 可以用单条命令快速推翻过度完成声明。

**只建议修改：**

- 当前 planned 文档
- 如有必要，`third_party/quantaalpha/quantaalpha/cli.py`

**完成标准：**

- `pytest` 路径稳定
- CLI 示例命令稳定
- 文档中的命令可直接复跑

---

## 五、测试方案

### 5.1 单元测试

新增：

- `third_party/quantaalpha/tests/test_continuous_orchestrator.py`

至少覆盖：

1. `JobSpec` / `JobResult` / `TriggerEvent` 的默认值与序列化
2. `schedule` 触发能转换成预期 `JobSpec`
3. `event` 触发能转换成预期 `JobSpec`
4. 主链 runner 成功时返回 `success`
5. 主链 runner 抛异常时返回失败并带 `failed_stage`
6. 达到并发或队列上限时返回结构化拒绝/延后结果
7. 可重试错误会重试，且 `attempt_count` 正确
8. 超过最大重试次数后返回终态失败
9. `RunSummary` 会正确聚合成功、失败、重试、拒绝数

### 5.2 CLI / 边界测试

至少包含：

1. 一个测试验证 CLI 入口真实调用 orchestrator，而不是绕过到散落 helper
2. 一个测试验证主链调用失败时 CLI 退出码非零
3. 一个测试验证 CLI 输出包含稳定字段：
   - `total_jobs`
   - `success_jobs`
   - `failed_jobs`
   - `retried_jobs`
   - `throttled_or_rejected_jobs`

### 5.3 手工验收

如 CLI 已落地，至少能复跑：

```bash
cd /home/quan/testdata/aspipe_v4
/root/miniforge3/envs/mining/bin/python -m pytest third_party/quantaalpha/tests/test_continuous_orchestrator.py -q
```

如提供 CLI 子命令，再补：

```bash
cd /home/quan/testdata/aspipe_v4
/root/miniforge3/envs/mining/bin/python third_party/quantaalpha/quantaalpha/cli.py continuous run-once --trigger-type schedule
```

### 5.4 Required Boundary Test

至少满足以下两项：

- 1 个测试证明 orchestrator 通过统一 runner 调主链，而不是在多个位置散落调用逻辑
- 1 个测试或真实命令证明主链失败时 CLI 最终退出码为非零，且能归因到失败阶段

### 5.5 Disproof Command

以下任一命令失败，都足以推翻“Continuous Orchestrator 最小骨架已经完成”的说法：

```bash
cd /home/quan/testdata/aspipe_v4
/root/miniforge3/envs/mining/bin/python -m pytest third_party/quantaalpha/tests/test_continuous_orchestrator.py -q
```

```bash
cd /home/quan/testdata/aspipe_v4
/root/miniforge3/envs/mining/bin/python third_party/quantaalpha/quantaalpha/cli.py continuous run-once --trigger-type schedule
```

### 5.6 Primary Evidence / Secondary Evidence

Primary evidence:

- CLI 或 facade 的真实 orchestrator 入口已存在
- 至少 1 个测试证明失败退出码和失败阶段可被调用方消费
- 至少 1 个测试证明并发限制/队列限制不是只写在配置里，而是真正生效

Secondary evidence:

- 纯对象模型测试
- 只验证 dataclass/default 值的测试
- 只验证日志内容的测试
- 只验证 mock helper 被调用的测试

---

## 六、验收标准

1. 仓库内存在最小但真实可调用的 `continuous-orchestrator` 入口
2. `schedule` 与 `event` 两类触发都能转成标准 job
3. orchestrator 通过统一边界调用主链，不复制主链业务逻辑
4. 已实现最小排队、并发限制或明确可测的限流/拒绝语义
5. 已实现最大重试次数和失败阶段归因
6. CLI 或 facade 能输出稳定结构化结果给下游消费
7. 至少一个边界测试证明失败语义对外可见，而不是只停留在日志

### 6.1 Move Blockers / Move-to-Tested Conditions

出现以下任一情况，文档不得移到 `tested`：

- orchestrator 仍只是若干脚本拼接，没有统一 job/result 契约
- 主链失败后 CLI 仍返回 0
- 并发限制或背压只停留在配置/注释里，没有真实行为验证
- 只有 helper/unit 测试，没有真实 orchestrator 入口验证
- orchestrator 通过私有文件写入或平行状态库补逻辑，绕过主链边界

仅当以下条件同时满足时，才允许移到 `tested`：

- `Disproof Command` 已执行
- `Primary Evidence` 已满足
- Required Boundary Test 已通过
- reviewer 能从真实入口确认 orchestrator 的失败语义和结构化输出

---

## 七、交付产物

- `continuous/orchestrator.py`
- `continuous/job_models.py`
- `continuous/job_runner.py`
- `continuous/trigger_models.py`
- `test_continuous_orchestrator.py`
- `cli.py` 中可复跑的 orchestrator 入口
