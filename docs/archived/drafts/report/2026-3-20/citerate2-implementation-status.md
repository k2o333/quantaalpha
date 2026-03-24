# Iterate 2 规划文档实施状态报告

日期：2026-03-20

---

## 总览

对 Iterate 2 的 5 份规划文档逐一进行代码审查和 Disproof Command 验证，结论如下：

| 编号 | 文档 | 评估 | Disproof 测试 |
|------|------|------|---------------|
| 01 | revalidate 语义澄清与真实复验链路 | **已完成** | 20/20 通过 |
| 02 | 失败因子重试过滤 | **未完成** | 42/42 通过（测试本身通过，但未覆盖验收要求） |
| 03 | 质量门控与状态流转回归测试 | **未完成** | 8/8 通过（测试本身通过，但未覆盖验收要求） |
| 04 | 外部调度脚本、运行摘要与状态审计 | **未完成** | 8/8 通过（测试本身通过，但未覆盖验收要求） |
| 05 | 因子库写入保护 | **未完成** | 4/5 通过，1 失败 |

---

## 01 - revalidate 语义澄清与真实复验链路

### 已完成项

- `--real-backtest` 标志已实现（`cli.py:36`），进入真实回测模式时构造临时 CSV 并调用 `backtest_main`
- `--dry-run` 标志已实现（`cli.py:35`），返回候选列表但不执行任何操作
- 三种模式互斥校验已实现（`cli.py:68-73`）
- `library.py` 中 `select_revalidation_candidates()` 和 `apply_validation_result()` 已实现
- `status_rules.py` 中 `update_factor_status()` 状态机已实现，阈值已固化（degraded=0.35, active=0.55, stale=30天）
- 测试文件 `test_revalidate_cli.py` 共 358 行、20 个测试，覆盖全部三种模式及边界情况

### 与规划的差异

| 规划要求 | 实际实现 | 影响 |
|----------|----------|------|
| 默认模式命名为 `status_refresh` | 实际为 `"default"` | 命名差异，不影响语义 |
| 顶层字段 `used_existing_results` | 仅有 per-factor 的 `validation_summary: "reused_existing"` | 信息粒度不同，功能等价 |

### Disproof Command

```bash
cd /home/quan/testdata/aspipe_v4
/root/miniforge3/envs/mining/bin/python -m pytest third_party/quantaalpha/tests/test_revalidate_cli.py -q
```

结果：**20 passed**，0 failed。

### 结论

核心功能完整实现，差异为命名和字段结构层面的微小偏离，不影响验收标准。**判定为已完成。**

---

## 02 - 失败因子重试过滤

### 已完成项

- `FactorFailureTracker` 数据模型已实现（`failure_tracker.py`），包含 `FactorStatus`、`DebugRoundSummary`、`FailureReason` 枚举
- `AlphaAgentLoop` 通过委托方法暴露 `get_successful_factor_ids()` / `get_failed_factor_ids()`（`loop.py:382-388`）
- `should_continue_debug()` 检测全部成功时返回 False（`failure_tracker.py:257-272`）
- 测试文件 `test_debug_failure_filter.py` 共 1446 行、42 个测试，覆盖状态判定、轮次摘要、集成场景

### 未完成项

| 验收标准 | 现状 | 说明 |
|----------|------|------|
| 成功因子不重复进入 coder/backtest | **未实现** | `factor_calculate()` 仍将完整 experiment 传给 coder，未过滤已成功因子 |
| 全部成功时提前退出 | **未实现** | `feedback()` 仅日志记录 `"All factors succeeded"`，未中断 `LoopBase` 循环 |

规划文档 6.1 节明确指出：

> 出现以下任一情况，文档不得移到 tested：失败集合被真实执行路径消费，而不是只被记录。

当前 `feedback()` 方法中的 `retry_factors` 计算和日志输出仅是"记录"，未被后续 pipeline 步骤消费。

### Disproof Command

```bash
cd /home/quan/testdata/aspipe_v4
/root/miniforge3/envs/mining/bin/python -m pytest third_party/quantaalpha/tests/test_debug_failure_filter.py -q
```

结果：**42 passed**，0 failed。测试本身全部通过，但 `TestControlFlowIntegration` 中的测试使用 mock 模拟过滤行为，未验证真实管线控制流。

### 结论

**判定为未完成。** 基础设施完备，但规划的核心验收标准（失败集合被真实执行路径消费、全部成功时提前退出）未满足。

---

## 03 - 质量门控与状态流转回归测试

### 已完成项

- `test_status_transition.py`（117 行）：覆盖 active->stale、active->degraded、degraded->active、degraded->deprecated
- `test_planning_constraints.py`（64 行）：覆盖状态约束下的 parent selection 和 RankIC 阈值
- `test_quality_gate.py`（111 行）：覆盖符号复杂度坏样本（过长表达式、过多基础特征、已知坏模式 `1/1`、`$close/$close`、`0*$volume`）
- `test_continuous_factor_features.py` 已重构为 6 个测试方法，使用 stub module 加载模式

### 未完成项

| 验收标准 | 现状 | 说明 |
|----------|------|------|
| NaN 比例过高的坏样本被拦截 | **未实现** | `status_rules.py` 和 `consistency_checker.py` 中无任何 NaN 相关检查 |
| inf 存在的坏样本被拦截 | **未实现** | 同上 |
| 常数列坏样本被拦截 | **未实现** | 同上 |
| 有效样本占比过低的坏样本被拦截 | **未实现** | 同上 |

当前 `FactorQualityGate`（`consistency_checker.py:374-464`）仅包含：
- `ConsistencyChecker`：表达式语法一致性
- `ComplexityChecker`：符号复杂度检查（表达式长度、基础特征数、自由参数比、已知坏模式）
- `RedundancyChecker`：冗余检测

所有检查都是符号/AST 级别的，不涉及计算后的因子值数据。

### Disproof Command

```bash
cd /home/quan/testdata/aspipe_v4
/root/miniforge3/envs/mining/bin/python -m pytest third_party/quantaalpha/tests/test_status_transition.py third_party/quantaalpha/tests/test_planning_constraints.py third_party/quantaalpha/tests/test_quality_gate.py -q
```

结果：**8 passed**，0 failed。

### 结论

**判定为未完成。** 测试文件已创建且全部通过，但规划要求的数据级质量门控（NaN/inf/常数列/低有效样本）完全缺失。按规划 6.1 节标准："坏样本会失败，但仍可能进入后续高成本步骤"——当前没有对数据级坏样本做任何拦截。

---

## 04 - 外部调度脚本、运行摘要与状态审计

### 已完成项

- `scripts/continuous_mine.sh`（86 行）：完整的循环调度脚本，支持环境变量配置、日志输出、退出码处理
- `FactorLibraryManager.get_summary()` 方法已实现（`library.py:544`），返回 total_factors、status_counts、evolution_counts、avg_stability_score、last_updated、version
- 测试文件 `test_scheduler_summary.py`（327 行）：8 个测试覆盖空库摘要、多状态分布、审计查询、upsert、列表过滤

### 未完成项

| 验收标准 | 现状 | 说明 |
|----------|------|------|
| `apply_validation_result()` 状态变更审计 | **未实现** | `update_factor_status()` 计算新状态但无任何审计写入；`get_audit_trail()` 仅从现有 metadata 时间戳重建，非实时记录 |
| `revalidate` 输出包含 `status_distribution` | **未实现** | revalidate 报告仅有 mode、total_candidates、success、failed、skipped、details |
| `revalidate` 输出包含 `stale_count` | **未实现** | 同上 |

按规划 2.4 节：

> 只打印摘要、不核对默认路径与真实写路径，不算完成。

脚本存在但缺失审计日志和 revalidate 摘要输出。规划要求的审计字段（timestamp、factor_id、old_status、new_status、reason、trigger）均未写入。

### Disproof Command

```bash
cd /home/quan/testdata/aspipe_v4
/root/miniforge3/envs/mining/bin/python -m pytest third_party/quantaalpha/tests/test_scheduler_summary.py -q
```

结果：**8 passed**，0 failed。

### 结论

**判定为未完成。** 脚本和摘要统计已实现，但状态审计日志和 revalidate CLI 摘要输出均缺失。

---

## 05 - 因子库写入保护

### 已完成项

- `library.py` 中 `_save()` 使用 `fcntl.flock(LOCK_EX)` 文件锁（`library.py:46-55`）
- 原子写策略：`tempfile.mkstemp()` + `Path.rename()`（`library.py:84-89`）
- 锁释放在 `finally` 块中（`library.py:93-94`）
- 测试文件 `test_factor_library_locking.py`：5 个测试

### 未通过项

并发写测试 `test_concurrent_save_from_multiple_managers` 失败：

```
AssertionError: 1 != 5
```

5 个线程各创建独立的 `FactorLibraryManager` 实例并发写入同一文件，最终文件中只有 1 条因子而非预期的 5 条。

**根因分析：** 每个 `FactorLibraryManager` 实例在初始化时加载了文件的完整副本到内存 `self.data`。文件锁只保护了 `_save()` 中的文件写入操作（最后一个写入者覆盖前一个），但不保护内存数据的合并。这是一个经典的"锁粒度不足"问题——锁应覆盖"读取-修改-写入"的完整事务，而非仅保护写入。

### Disproof Command

```bash
cd /home/quan/testdata/aspipe_v4
/root/miniforge3/envs/mining/bin/python -m pytest third_party/quantaalpha/tests/test_factor_library_locking.py -q
```

结果：**4 passed, 1 failed**。

### 结论

**判定为未完成。** 锁机制和原子写已实现，但并发测试失败暴露了锁粒度不足的问题。按规划 6.1 节标准："多进程验证在当前环境跑不通，却被写成全部通过"——测试已明确失败，可定位问题但需修复。

---

## 依赖关系与建议修复顺序

```
01 (已完成)
 └── 02 (未完成 - 控制流未接通)
 │    └── 03 (未完成 - 数据级质量门控缺失)
 └── 04 (未完成 - 审计日志和摘要输出缺失)
      └── 05 (未完成 - 并发测试失败)
```

建议按依赖关系自底向上修复：

1. **05（写锁）**：修复 `FactorFailureTracker` 并发问题——在 `_save()` 中加入"读取-修改-写入"事务锁，或改为加锁时重新读取最新数据
2. **02（失败因子过滤）**：在 `AlphaAgentLoop.factor_calculate()` 中消费 `get_factors_for_retry()` 的结果，实际跳过已成功因子；在 `feedback()` 中实现循环中断
3. **03（质量门控）**：在 `consistency_checker.py` 的 `FactorQualityGate` 中新增数据级检查（NaN/inf/常数列/有效样本比例），并在 `test_quality_gate.py` 中补充对应测试
4. **04（审计与摘要）**：在 `update_factor_status()` 或 `apply_validation_result()` 中写入审计记录；在 `revalidate` CLI 输出中加入 `status_distribution` 和 `stale_count`
