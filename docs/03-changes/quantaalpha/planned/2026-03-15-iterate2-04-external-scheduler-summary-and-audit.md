# Iterate 2.4: 外部调度脚本、运行摘要与状态审计

Status: planned
Priority: P1
Depends-on:
- 2026-03-15-iterate2-01-revalidate-semantics-and-real-backtest.md
- 2026-03-15-iterate2-03-quality-gate-and-state-regression.md

---

## 一、目标

把“外部定时触发”从一句建议落成一套最小可执行方案：

- 有标准触发脚本
- 有结构化运行摘要
- 有最小状态变更审计

这样调度侧不必自行拼装命令，也能直接消费核心结果。

---

## 二、范围

包含：

- 标准调度脚本
- 因子库运行摘要接口
- 状态变更审计日志
- 最小验收命令

不包含：

- 常驻 daemon
- 队列系统
- 告警平台接入

### 2.1 Write Target / Source of Truth

- 脚本默认操作路径必须与 `loop.py` 的真实因子库写路径一致
- 摘要和审计都必须围绕真实因子库，而不是另一份平行 JSON

### 2.2 Failure Semantics

- `mine` 失败时脚本必须返回非零
- `revalidate` 失败时脚本必须返回非零
- 不能把“report 里有 failed>0”包装成调度成功

### 2.3 Caller Contract

- 脚本调用方：通过退出码和标准输出消费结果
- scheduler/operator：只能看到脚本的最终退出语义和摘要输出
- Python 内部函数：可以返回结构化结果，但不能替代脚本层失败语义

### 2.4 What Does Not Count As Done

- 只新增脚本文件不算完成
- 只打印摘要、不核对默认路径与真实写路径，不算完成
- 只记录 audit，不验证何时应该退出非零，不算完成
- 只修 Python 内部 report，不修脚本层 failure semantics，不算完成

---

## 三、代码落点

- `third_party/quantaalpha/quantaalpha/factors/library.py`
- `third_party/quantaalpha/quantaalpha/cli.py`
- 建议新增：
  - `third_party/quantaalpha/scripts/continuous_mine.sh`
  - `third_party/quantaalpha/tests/test_scheduler_summary.py`

---

## 四、开发方案

### 4.1 标准调度脚本

新增脚本：

- `third_party/quantaalpha/scripts/continuous_mine.sh`

脚本职责：

1. 执行一次 `mine`
2. 执行一次 `revalidate --dry-run`
3. 输出本轮摘要
4. 非零退出码时给出清晰失败阶段

脚本约束：

- 不写死私有机器路径，支持环境变量覆盖
- 日志输出纯文本即可，但摘要部分应稳定可 grep
- 不在脚本里重新实现业务逻辑，只调用 CLI

### 4.2 library summary

在 `FactorLibraryManager` 中新增类似 `get_library_summary()` 的方法。

摘要字段至少包括：

- `total_factors`
- `status_distribution`
- `stale_count`
- `active_count`
- `degraded_count`
- `last_validated`
- `last_updated`

### 4.3 状态变更审计

在 `apply_validation_result()` 中增加最小审计记录。

建议记录：

- `timestamp`
- `factor_id`
- `old_status`
- `new_status`
- `reason`
- `trigger`

约束：

- 仅在状态发生变化时记审计
- 审计保留最近固定数量记录即可
- 不要为了审计改变现有状态流转逻辑

### 4.4 CLI 摘要输出

`revalidate` 结束后至少输出：

- `success`
- `failed`
- `skipped`
- `status_distribution`
- `stale_count`

如果 `mine` 当前不便改结构化返回，至少在脚本层拼出统一摘要。

---

## 五、测试方案

### 5.1 单元测试

新增 `test_scheduler_summary.py`，覆盖：

1. 空因子库摘要返回默认值
2. 多状态因子库能统计出正确分布
3. 状态变化时追加审计记录
4. 状态未变化时不追加审计
5. 审计条数超过上限时会裁剪

### 5.2 脚本测试

对 `continuous_mine.sh` 做最小 smoke test：

- mock `mine`
- mock `revalidate`
- 校验脚本退出码和摘要输出

### 5.3 手工验收

执行：

```bash
cd /home/quan/testdata/aspipe_v4/third_party/quantaalpha
bash scripts/continuous_mine.sh
```

检查输出应至少包含：

- mine 阶段是否成功
- revalidate 阶段是否成功
- 因子总数
- stale/degraded/active 分布

### 5.4 Required Boundary Test

至少包含：

- 1 个测试断言脚本默认路径与真实写路径一致
- 1 个测试断言下游失败时脚本退出码非零

### 5.5 Disproof Command

```bash
cd /home/quan/testdata/aspipe_v4
/root/miniforge3/envs/mining/bin/python -m pytest third_party/quantaalpha/tests/test_scheduler_summary.py -q
```

### 5.6 Primary Evidence / Secondary Evidence

Primary evidence:

- 至少 1 个测试验证脚本默认路径与真实写路径一致
- 至少 1 个测试或真实命令验证下游失败时脚本退出码非零

Secondary evidence:

- library summary 的纯统计测试
- audit 记录结构测试
- 只检查 report 字段的内部单元测试

---

## 六、验收标准

1. 仓库内存在可直接复用的标准调度脚本
2. 调度后能直接看到状态分布与待复验摘要
3. 状态变化可以追溯到最近一次触发原因
4. 不引入 daemon 或复杂调度器
5. 自动化测试覆盖 summary 与 audit 主路径
6. 已验证脚本默认路径与真实写路径一致
7. 已验证脚本退出码语义可被调度器正确消费

### 6.1 Move Blockers / Move-to-Tested Conditions

出现以下任一情况，文档不得移到 `tested`：

- 脚本默认路径仍与真实写路径脱节
- 失败信息只停留在内部 report，脚本退出码仍为 0
- 主要证据只有统计和 audit 测试，没有脚本层验证

仅当以下条件同时满足时，才允许移到 `tested`：

- `Disproof Command` 已执行
- `Primary Evidence` 已满足
- 脚本层 failure semantics 已验证

---

## 七、交付产物

- `scripts/continuous_mine.sh`
- `FactorLibraryManager.get_library_summary()`
- 状态审计字段或日志结构
- `test_scheduler_summary.py`
