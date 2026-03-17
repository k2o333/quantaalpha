# Iterate 2.2: 失败因子重试过滤

Status: planned
Priority: P0
Depends-on: 2026-03-15-iterate2-01-revalidate-semantics-and-real-backtest.md

---

## 一、目标

把设计稿中的“debug 后续轮次只优先处理失败因子”落成明确实现，而不是停留在经验性描述。

本迭代要解决两个问题：

- 什么叫失败因子
- 下一轮 debug 如何只处理失败项

---

## 二、范围

包含：

- 失败因子判定规则
- 批次内成功项短路
- 后续轮次失败项筛选
- 对应自动化测试

不包含：

- LLM 路由策略调整
- 多模型 fanout
- 质量门控阈值配置化

### 2.1 Downstream Consumer

- `AlphaAgentLoop` 的后续 debug 轮次是这个功能的真实消费者
- 验收重点不是日志里出现了 `failed_factor_ids`，而是下一轮实际处理集合变了

### 2.2 Failure Semantics

- 成功因子不得再次进入 coder/backtest
- 全部成功时应提前结束 debug
- 全部失败时仍受最大轮次保护，不能无限重试

### 2.3 What Does Not Count As Done

- 只新增 `successful_factor_ids` / `failed_factor_ids` 字段不算完成
- 只打印 round summary 不算完成
- 只暴露 getter，但没有任何执行路径消费它，不算完成

---

## 三、代码落点

- `third_party/quantaalpha/quantaalpha/pipeline/loop.py`
- 如有需要，关联：
  - `third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py`
  - `third_party/quantaalpha/quantaalpha/factors/library.py`

建议新增测试：

- `third_party/quantaalpha/tests/test_debug_failure_filter.py`

---

## 四、开发方案

### 4.1 固定失败因子定义

本迭代先用规则定义失败，不引入模型判断。

失败因子至少包括：

- expression parse 失败
- coder 阶段未产出 workspace
- 质量门控失败
- backtest 返回空结果
- backtest 抛异常

成功因子定义为：

- 已通过 coder
- 已通过质量门控
- 已得到有效 backtest 结果

### 4.2 引入失败筛选结果

建议在 `loop.py` 中引入明确的数据结构，例如：

- `successful_factor_ids`
- `failed_factor_ids`
- `failed_reasons`

每轮结束后只把 `failed_factor_ids` 送入下一轮 debug。

### 4.3 避免整批重复打磨

要求：

- 已成功的因子不应再次进入 coder/backtest
- 批次中若全部成功，debug 轮次直接提前退出
- 如果全部失败，仍保留现有退出保护，避免无限重试

### 4.4 日志输出

每轮至少输出：

- 总因子数
- 成功数
- 失败数
- 下一轮待重试数
- 每类失败原因计数

---

## 五、测试方案

### 5.1 单元测试

新增 `test_debug_failure_filter.py`，覆盖：

1. 混合成功/失败时，只失败因子进入下一轮
2. 全部成功时，debug 提前退出
3. 全部失败时，仍遵守最大轮次限制
4. 失败原因能被记录并聚合
5. 成功因子不会再次调用 coder/backtest

### 5.2 集成测试

使用 stub/mocks 构造三类因子：

- 可正常回测
- coder 失败
- backtest 失败

验证每轮处理集合变化是否符合预期。

### 5.3 手工验收

运行一轮最小挖掘任务，观察日志应出现：

- `success_count`
- `failed_count`
- `retry_count`

并且第二轮开始时处理数量小于第一轮。

### 5.4 Required Boundary Test

必须至少有 1 个测试直接断言：

- 第二轮传给 coder/backtest 的集合只包含失败因子
- 成功因子不会再次进入高成本步骤

### 5.5 Disproof Command

下面命令只要出现 collection error、关键断言失败，或无法证明第二轮集合缩减，就应视为未完成：

```bash
cd /home/quan/testdata/aspipe_v4
/root/miniforge3/envs/mining/bin/python -m pytest third_party/quantaalpha/tests/test_debug_failure_filter.py -q
```

---

## 六、验收标准

1. 成功因子不会重复进入 debug 后续轮次
2. 失败因子定义在代码和测试中一致
3. 日志能说明每轮缩减了多少待处理对象
4. 不引入新的无限循环或整批重复回测
5. 自动化测试能覆盖混合成功/失败的主路径
6. 至少有一个断言证明“失败集合被真实消费”

---

## 七、交付产物

- 更新后的 `loop.py`
- 新增 `test_debug_failure_filter.py`
- 失败因子日志样例
