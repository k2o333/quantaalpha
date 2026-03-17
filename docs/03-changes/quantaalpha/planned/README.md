# QuantaAlpha 持续挖掘 Iterate 2 原子化迭代清单

Status: planned
Owner: QuantaAlpha team
Created: 2026-03-15
Based-on: /home/quan/testdata/aspipe_v4/docs/drafts/自主挖掘因子回测和因子管理/continuous mining/design/2026-03-15-quantaalpha-continuous-mining-design-v2.md

---

## 一、目的

本目录将 V2 设计拆成可以独立开发、测试、验收的原子化迭代文档。

拆分原则：

- 每个迭代只解决一个明确问题
- 每个迭代都有清晰代码落点
- 每个迭代都能单独测试和验收
- 优先先稳主链路，再补持续维护层

---

## 二、迭代列表

1. `2026-03-15-iterate2-01-revalidate-semantics-and-real-backtest.md`
2. `2026-03-15-iterate2-02-failed-factor-debug-filter.md`
3. `2026-03-15-iterate2-03-quality-gate-and-state-regression.md`
4. `2026-03-15-iterate2-04-external-scheduler-summary-and-audit.md`
5. `2026-03-15-iterate2-05-factor-library-write-lock.md`

---

## 三、推荐顺序

### Step 1

先做 `01 revalidate`。

原因：

- 当前设计与实现最容易混淆的点就在这里
- 它直接影响 CLI 语义、调度文案和验收口径
- 后续调度脚本也依赖它的输出定义

### Step 2

再做 `02 failed factor debug filter`。

原因：

- 这是研究主链路最核心的稳定性改进
- 需要先把失败因子重试口径固定下来，后续测试才有明确对象

### Step 3

接着做 `03 quality gate and state regression`。

原因：

- 它主要补回归测试和状态流转验证
- 依赖前两个迭代把行为边界先定清楚

### Step 4

然后做 `04 external scheduler summary and audit`。

原因：

- 这是最小持续维护层
- 依赖前面 CLI 和状态更新行为稳定

### Step 5

最后做 `05 factor library write lock`。

原因：

- 它是治理增强项
- 与前面几个迭代耦合较低，可以单独收尾

---

## 四、统一约束

所有迭代默认基于以下代码路径：

- `third_party/quantaalpha/quantaalpha/cli.py`
- `third_party/quantaalpha/quantaalpha/pipeline/loop.py`
- `third_party/quantaalpha/quantaalpha/factors/library.py`
- `third_party/quantaalpha/quantaalpha/factors/status_rules.py`
- `third_party/quantaalpha/quantaalpha/backtest/validation.py`
- `third_party/quantaalpha/tests/test_continuous_factor_features.py`

统一测试基线：

```bash
cd /home/quan/testdata/aspipe_v4
/root/miniforge3/envs/mining/bin/python -m unittest -q third_party/quantaalpha/tests/test_continuous_factor_features.py
/root/miniforge3/envs/mining/bin/python -m compileall third_party/quantaalpha/quantaalpha
```

如需新增测试文件，优先新增：

- `third_party/quantaalpha/tests/test_revalidate_cli.py`
- `third_party/quantaalpha/tests/test_debug_failure_filter.py`
- `third_party/quantaalpha/tests/test_status_transition.py`
- `third_party/quantaalpha/tests/test_scheduler_summary.py`
- `third_party/quantaalpha/tests/test_factor_library_locking.py`

高风险任务在开始编码前，必须先写清 4 个 seam：

- downstream consumer
- write target 或 source-of-truth path
- operator / scheduler 可见的 failure surface
- 1 条能推翻“已经完成”说法的 disproof command

高风险任务至少包括：

- 新 CLI 模式
- 调度脚本
- 写路径或因子库持久化
- 状态流转
- 失败重试控制流

所有 `planned` 文档默认都应包含以下硬约束：

- `Downstream Consumer`
- `Write Target / Source of Truth`
- `Failure Semantics`
- `Required Boundary Test`
- `Disproof Command`
- `What Does Not Count As Done`

统一反假完成约束：

- 只新增 tracker / log / summary 不算行为完成
- 只修输入格式、不核对输出结构不算集成完成
- 只给测试数量、不提供可复跑命令不算验证完成
- 文档不得先于关键验证进入 `tested/`

---

## 五、完成定义

单个迭代完成，至少应满足：

1. 文档中列出的代码修改点已经落地
2. 自动化测试已经补齐，并且关键命令可由 reviewer 原样复跑
3. 命令行、结果文件或运行时控制流能直接体现改动效果
4. 下游输入契约和输出契约都已核对
5. `Disproof Command` 已执行且未推翻完成声明
6. 验收标准可由另一个工程师按文档复现
