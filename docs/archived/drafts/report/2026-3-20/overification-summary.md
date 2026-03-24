# Iterate 2 实施验证总结

**验证时间**: 2026-03-20
**验证对象**: `docs/03-changes/quantaalpha/planned/` 下 5 个 Iterate 2 计划

---

## 一、总览

| 计划 | 文档 | 状态标记 | 测试结果 | 实际状态 |
|------|------|---------|---------|---------|
| 2.1 revalidate 语义澄清 | `2026-03-15-iterate2-01-*.md` | planned | ✅ 20 passed | **已实施** |
| 2.2 失败因子重试过滤 | `2026-03-15-iterate2-02-*.md` | planned | ✅ 42 passed | **已实施** |
| 2.3 质量门控与状态流转 | `2026-03-15-iterate2-03-*.md` | planned | ✅ 全部通过 | **已实施** |
| 2.4 外部调度脚本与审计 | `2026-03-15-iterate2-04-*.md` | planned | ✅ 8 passed | **已实施** |
| 2.5 因子库写入保护 | `2026-03-15-iterate2-05-*.md` | planned | ⚠️ 4/5 passed | **部分实施** |

---

## 二、各计划详情

### 2.1 revalidate 语义澄清与真实复验链路

**测试文件**: `tests/test_revalidate_cli.py` (358 行)

| 测试命令 | 结果 |
|---------|------|
| `pytest test_revalidate_cli.py -q` | 20 passed, 4.19s |

**验收要点**:
- [x] 默认模式返回 `mode=status_refresh`
- [x] `dry_run=true` 只返回候选，不写库
- [x] 默认模式复用已有 `period_results`
- [x] `no_write=true` 时库文件内容不变
- [x] 真实复验模式失败不污染历史结果

**Disproof Command 验证**:
```bash
cd /home/quan/testdata/aspipe_v4
/root/miniforge3/envs/mining/bin/python -m pytest third_party/quantaalpha/tests/test_revalidate_cli.py -q
```
结果: 20 passed

**Primary Evidence**:
- 真实 CLI 命令能区分三种模式 (dry_run / status_refresh / real_backtest)
- 至少 1 条真实边界验证证明输入契约和输出契约都被满足
- 至少 1 条真实入口失败验证证明 failure semantics 对 CLI caller 可见

---

### 2.2 失败因子重试过滤

**测试文件**: `tests/test_debug_failure_filter.py` (1446 行)

| 测试命令 | 结果 |
|---------|------|
| `pytest test_debug_failure_filter.py -q` | 42 passed, 0.58s |

**验收要点**:
- [x] 混合成功/失败时，只失败因子进入下一轮
- [x] 全部成功时，debug 提前退出
- [x] 全部失败时，仍遵守最大轮次限制
- [x] 失败原因能被记录并聚合
- [x] 成功因子不会再次调用 coder/backtest

**Disproof Command 验证**:
```bash
cd /home/quan/testdata/aspipe_v4
/root/miniforge3/envs/mining/bin/python -m pytest third_party/quantaalpha/tests/test_debug_failure_filter.py -q
```
结果: 42 passed

**Primary Evidence**:
- 至少 1 个测试直接断言第二轮传给 coder/backtest 的集合只包含失败因子
- 至少 1 个测试直接断言成功因子不会再次进入高成本步骤

---

### 2.3 质量门控与状态流转回归测试

**测试文件**:
- `tests/test_status_transition.py` (116 行)
- `tests/test_planning_constraints.py` (64 行)
- `tests/test_quality_gate.py` (111 行)

| 测试命令 | 结果 |
|---------|------|
| `pytest test_status_transition.py -q` | 4 passed, 0.02s |
| `pytest test_planning_constraints.py -q` | 2 passed, 0.85s |
| `pytest test_quality_gate.py -q` | 2 passed, 0.42s |

**验收要点**:
- [x] 坏样本在 gate 被拦截
- [x] 状态流转阈值被显式断言 (active=0.5, degraded=0.3, stale=30天)
- [x] 测试不依赖外部 LLM
- [x] 明显越界方向被拦截

**Disproof Command 验证**:
```bash
cd /home/quan/testdata/aspipe_v4
/root/miniforge3/envs/mining/bin/python -m pytest \
  third_party/quantaalpha/tests/test_status_transition.py \
  third_party/quantaalpha/tests/test_planning_constraints.py \
  third_party/quantaalpha/tests/test_quality_gate.py -q
```
结果: 8 passed

**Primary Evidence**:
- 至少 1 个测试证明坏样本会阻止后续高成本步骤
- 至少 1 组阈值断言覆盖真实状态流转边界

---

### 2.4 外部调度脚本、运行摘要与状态审计

**产出物**:
- `scripts/continuous_mine.sh` (2500 bytes, 可执行)
- `tests/test_scheduler_summary.py` (326 行)

| 测试命令 | 结果 |
|---------|------|
| `pytest test_scheduler_summary.py -q` | 8 passed, 0.02s |

**验收要点**:
- [x] 空因子库摘要返回默认值
- [x] 多状态因子库能统计出正确分布
- [x] 状态变化时追加审计记录
- [x] 状态未变化时不追加审计
- [x] 审计条数超过上限时会裁剪

**Disproof Command 验证**:
```bash
cd /home/quan/testdata/aspipe_v4
/root/miniforge3/envs/mining/bin/python -m pytest third_party/quantaalpha/tests/test_scheduler_summary.py -q
```
结果: 8 passed

**Primary Evidence**:
- 至少 1 个测试验证脚本默认路径与真实写路径一致
- 至少 1 个测试或真实命令验证下游失败时脚本退出码非零

---

### 2.5 因子库写入保护

**测试文件**: `tests/test_factor_library_locking.py` (181 行)

| 测试命令 | 结果 |
|---------|------|
| `pytest test_factor_library_locking.py -q` | **4 passed, 1 failed** |

**通过用例**:
- [x] 正常写入仍可成功
- [x] 锁获取和释放正常
- [x] 锁在保存后自动释放
- [x] 写入失败时原文件保持有效 JSON

**失败用例**: `test_concurrent_save_from_multiple_managers` (第 110 行)

```
self.assertEqual(len(final["factors"]), 5)
AssertionError: 1 != 5
```

**失败详情**:

5 个线程各自创建独立 FactorLibraryManager 实例：
```python
def writer(manager_idx):
    mgr = library_mod.FactorLibraryManager(str(lib_path))
    mgr.data["factors"][f"concurrent_f{manager_idx}"] = { ... }
    mgr._save()

threads = [threading.Thread(target=writer, args=(i,)) for i in range(5)]
```

最终文件中只有 1 个 factor，其余 4 个被覆盖。

**根因分析**:
- 每个 Manager 实例独立调用 `_load()` 读取空文件
- 各自添加自己的 factor 到内存
- 并发调用 `_save()` 时，文件锁可能仅在单实例内有效
- 后写入的完整覆盖了先写入的内容，而非合并

**验收要点**:
- [x] 正常写入仍可成功
- [ ] 并发连续写入后 JSON 仍可解析 **(FAIL)**
- [x] 写入失败时原文件仍保持有效 JSON
- [x] 原子替换后字段仍正确

---

## 三、问题汇总

### 3.1 计划文件状态未更新

| 文件 | 当前状态 | 建议状态 |
|------|---------|---------|
| iterate2-01-revalidate-* | planned | tested |
| iterate2-02-failed-factor-* | planned | tested |
| iterate2-03-quality-gate-* | planned | tested |
| iterate2-04-external-scheduler-* | planned | tested |
| iterate2-05-factor-library-lock-* | planned | planned (保持) |

### 3.2 Iterate 2.5 并发写入失败

**严重程度**: 中
**影响范围**: 多进程调度场景下因子库数据丢失
**复现条件**: 多个 FactorLibraryManager 实例并发 `_save()`

**修复方案**:

方案 A - 跨进程文件锁:
```python
import fcntl

def _save(self):
    with open(self.library_path, 'r+') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            # 重新读取 + 合并 + 写入
            current = json.load(f)
            current['factors'].update(self.data['factors'])
            f.seek(0)
            json.dump(current, f)
            f.truncate()
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
```

方案 B - 使用 filelock 库:
```python
from filelock import FileLock

def _save(self):
    lock_path = str(self.library_path) + '.lock'
    with FileLock(lock_path):
        # 原有保存逻辑
```

---

## 四、建议操作

| 优先级 | 操作 | 涉及文件 |
|-------|------|---------|
| P0 | 修复 Iterate 2.5 并发写入问题 | `quantaalpha/factors/library.py` |
| P1 | 更新计划 2.1-2.4 状态为 `tested` | 4 个计划文件 |
| P2 | 修复后重跑 Disproof Command | `test_factor_library_locking.py` |

---

## 五、测试执行汇总

```bash
# 全部测试
cd /home/quan/testdata/aspipe_v4
/root/miniforge3/envs/mining/bin/python -m pytest \
  third_party/quantaalpha/tests/test_revalidate_cli.py \
  third_party/quantaalpha/tests/test_debug_failure_filter.py \
  third_party/quantaalpha/tests/test_status_transition.py \
  third_party/quantaalpha/tests/test_planning_constraints.py \
  third_party/quantaalpha/tests/test_quality_gate.py \
  third_party/quantaalpha/tests/test_scheduler_summary.py \
  third_party/quantaalpha/tests/test_factor_library_locking.py \
  -q

# 结果: 82 passed, 1 failed (6.69s)
```

---

## 六、附件

**产出物清单**:

| 类型 | 文件 | 行数 | 状态 |
|------|------|------|------|
| 测试 | `test_revalidate_cli.py` | 358 | ✅ |
| 测试 | `test_debug_failure_filter.py` | 1446 | ✅ |
| 测试 | `test_status_transition.py` | 116 | ✅ |
| 测试 | `test_planning_constraints.py` | 64 | ✅ |
| 测试 | `test_quality_gate.py` | 111 | ✅ |
| 测试 | `test_scheduler_summary.py` | 326 | ✅ |
| 测试 | `test_factor_library_locking.py` | 181 | ⚠️ |
| 脚本 | `continuous_mine.sh` | 85 | ✅ |
| **合计** | | **2687** | **82 passed, 1 failed** |

---

*报告生成时间: 2026-03-20 16:38*
