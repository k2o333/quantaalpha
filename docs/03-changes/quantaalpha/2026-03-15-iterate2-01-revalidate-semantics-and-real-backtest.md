---
doc_type: change
module: quantaalpha
status: planned
owner: quan
created: 2026-03-15
updated: 2026-03-15
summary: Iterate 2.1: revalidate 语义澄清与真实复验链路
priority: P0
depends_on: []
---

---

## 一、目标

解决当前 `revalidate` 的核心歧义：

- 现在的 `revalidate` 只是复用历史 `period_results`
- 但设计上容易被理解成“重新回测了一次”

本迭代要么把它明确收敛为“状态维护 CLI”，要么补一条真实复验链路，但不能继续保持语义模糊。

推荐落地方式：

- 保留当前轻量 `revalidate`，明确重命名语义为“状态维护”
- 新增 `--real-backtest` 或等价子命令，显式触发真实复验

---

## 二、范围

包含：

- CLI 参数与帮助文案调整
- `revalidate` 返回结构调整
- 真实复验链路接入点设计
- 新旧两种模式的自动化测试

不包含：

- 调度脚本
- 状态审计
- 文件锁

### 2.1 Downstream Consumer

- `quantaalpha.backtest.factor_loader.FactorLoader` 负责读取临时 factor JSON
- `quantaalpha.backtest.runner.BacktestRunner.run()` 返回真实回测结果
- `FactorLibraryManager.apply_validation_result()` 负责消费回测结果并更新因子库

### 2.2 Write Target / Source of Truth

- 因子库真实写入目标是 `third_party/quantaalpha/data/factorlib/all_factors_library.json`
- `revalidate --real-backtest` 的临时 JSON 只用于调用真实 loader，不得演化成另一套私有格式

### 2.3 Failure Semantics

- `status_refresh` 模式不得伪装成真实回测
- 单因子真实回测失败不得污染旧 `period_results`
- 缺少 `backtest_config` 或下游无法执行时，调用方必须能看见明确失败，而不是只在 report 里埋字段

### 2.4 Caller Contract

- Python 调用方：`revalidate()` 应保持可消费的返回结构，不应为了 CLI 退出码要求破坏库函数契约
- CLI 调用方：命令行入口必须能区分成功与失败，并在需要时返回非零退出码
- 调度或 operator：只能看到进程退出码和命令输出，因此失败语义必须在真实入口层可见

### 2.5 What Does Not Count As Done

- 只改 CLI help 或 report 字段，不算真实复验链路完成
- 只让 loader 能读取输入，不核对 runner 返回结构，不算集成完成
- 只做 mock helper 测试，不算主链路验收
- 为了满足 CLI 失败退出而直接改变库函数契约，不算正确完成

---

## 三、代码落点

- `third_party/quantaalpha/quantaalpha/cli.py`
- `third_party/quantaalpha/quantaalpha/factors/library.py`
- `third_party/quantaalpha/quantaalpha/factors/status_rules.py`
- 如需真实回测接入，再补：
  - `third_party/quantaalpha/quantaalpha/backtest/runner.py`
  - `third_party/quantaalpha/quantaalpha/pipeline/factor_backtest.py`

建议新增测试：

- `third_party/quantaalpha/tests/test_revalidate_cli.py`

---

## 四、开发方案

### 4.1 先做语义切分

把当前模式定义为：

- `revalidate` 默认模式：基于历史验证结果刷新状态
- `revalidate --dry-run`：只输出候选列表
- `revalidate --real-backtest`：真正重跑回测并写回新结果

如果本迭代时间不足以落真实回测，最低要求是：

- CLI help 和返回字段必须显式说明当前模式为 `mode=status_refresh`
- 返回结果中增加 `used_existing_results=true`
- 文档和日志里不能出现“重新回测”“重新验证完成”这类误导性字样

### 4.2 返回结构标准化

建议返回字段至少包括：

- `mode`
- `total_candidates`
- `success`
- `failed`
- `skipped`
- `used_existing_results`
- `details`

其中 `details` 每项建议包含：

- `factor_id`
- `before_status`
- `after_status`
- `stability_score`
- `revalidation_source`

### 4.3 真实复验模式接入

如果本迭代同时落真实复验，建议按下面方式实现：

1. 从因子库候选中取出 `factor_expression`
2. 构造最小 backtest 请求
3. 调用已有 backtest 入口，而不是单独复制一套复验逻辑
4. 把新的 `period_results` 和 `summary` 回写 `apply_validation_result`

约束：

- 真实复验失败不能覆盖旧结果
- 单因子失败只计入 `failed`，不打断整个批次
- `no_write=true` 时允许演练整个流程但不落库

---

## 五、测试方案

### 5.1 单元测试

新增 `test_revalidate_cli.py`，至少覆盖：

1. 默认模式返回 `mode=status_refresh`
2. `dry_run=true` 只返回候选，不写库
3. 默认模式会复用已有 `period_results`
4. `no_write=true` 时库文件内容不变
5. 真实复验模式下，成功结果会替换 `period_results`
6. 真实复验模式下，单因子失败不会中断整个批次

### 5.2 集成测试

准备一个最小 factor library fixture，包含：

- `active`
- `stale`
- `degraded`

分别执行：

```bash
/root/miniforge3/envs/mining/bin/python -m unittest -q third_party/quantaalpha.tests.test_revalidate_cli
```

如已接入真实回测，再增加一次 mock backtest 集成测试，校验：

- 调用次数
- 回写字段
- 失败保护

### 5.3 手工验收

执行：

```bash
cd /home/quan/testdata/aspipe_v4/third_party/quantaalpha
python -m quantaalpha.cli revalidate --library_path <path> --status active --no_write
```

检查输出是否明确标注：

- 当前模式
- 是否使用历史结果
- 是否真实回测

### 5.4 Required Boundary Test

必须至少有 1 个测试直接验证：

- 临时 JSON 能被真实 loader 读取
- `BacktestRunner.run()` 的真实返回结构能被 `revalidate` 正确消费
- 真实回测失败时旧 `period_results` 保持不变

### 5.5 Disproof Command

下面任一结果都应直接推翻“本迭代已完成”的说法：

```bash
cd /home/quan/testdata/aspipe_v4
/root/miniforge3/envs/mining/bin/python -m pytest third_party/quantaalpha/tests/test_revalidate_cli.py -q
```

```bash
cd /home/quan/testdata/aspipe_v4/third_party/quantaalpha
/root/miniforge3/envs/mining/bin/python -m quantaalpha.cli revalidate data/factorlib/all_factors_library.json --real-backtest --backtest-config configs/backtest.yaml
```

### 5.6 Primary Evidence / Secondary Evidence

Primary evidence:

- 真实 CLI 命令能区分三种模式
- 至少 1 条真实边界验证证明输入契约和输出契约都被满足
- 至少 1 条真实入口失败验证证明 failure semantics 对 CLI caller 可见

Secondary evidence:

- helper 级单元测试
- fallback harness
- mirrored logic 测试
- 只检查 report 字段的 mock 测试

Secondary evidence 可以辅助说明实现意图，但不能单独支撑 `tested`。

---

## 六、验收标准

1. 默认 `revalidate` 不再被误解为真实回测
2. CLI 输出可区分 `dry_run`、状态维护、真实复验三种模式
3. 状态维护模式不会篡改旧 `period_results`
4. 真实复验模式失败时不会污染历史验证结果
5. 自动化测试覆盖上述核心分支
6. 已同时验证输入契约和输出契约

### 6.1 Move Blockers / Move-to-Tested Conditions

出现以下任一情况，文档不得移到 `tested`：

- 真实 CLI 失败场景仍返回 0
- 输入契约已修，但输出契约仍靠推断而非真实边界验证
- 主要验收证据来自 fallback 或 mirrored logic
- 为满足 CLI 失败语义而破坏了 Python 调用方契约

仅当以下条件同时满足时，才允许移到 `tested`：

- `Disproof Command` 已执行
- `Primary Evidence` 已满足
- `Failure Semantics` 已在真实入口层验证
- Python 调用方契约与 CLI 调用方契约未被混淆

---

## 七、交付产物

- 更新后的 `cli.py`
- 如有需要，补充真实复验接入代码
- 新增 `test_revalidate_cli.py`
- 命令行帮助与示例输出
