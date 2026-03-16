# Iterate 2.1: revalidate 语义澄清与真实复验链路

Status: planned
Priority: P0
Depends-on: none

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

---

## 六、验收标准

1. 默认 `revalidate` 不再被误解为真实回测
2. CLI 输出可区分 `dry_run`、状态维护、真实复验三种模式
3. 状态维护模式不会篡改旧 `period_results`
4. 真实复验模式失败时不会污染历史验证结果
5. 自动化测试覆盖上述核心分支

---

## 七、交付产物

- 更新后的 `cli.py`
- 如有需要，补充真实复验接入代码
- 新增 `test_revalidate_cli.py`
- 命令行帮助与示例输出
