# 手动 Revalidate CLI

Status: completed
Owner: QuantaAlpha team
Created: 2026-03-14
Outcome: implemented
Phase: 2
Depends-on:
- /home/quan/testdata/aspipe_v4/docs/03-changes/quantaalpha/quantaalpha2026-3-14checklist/2026-03-14-multi-period-validation.md
- /home/quan/testdata/aspipe_v4/docs/03-changes/quantaalpha/quantaalpha2026-3-14checklist/2026-03-14-factor-library-schema-extension.md
Related-to: /home/quan/testdata/aspipe_v4/docs/drafts/自主挖掘因子回测和因子管理/2026-03-14-quantaalpha-continuous-factor-implementation-checklist.md

---

## Background

因子入库以后，当前系统缺少一个明确、低风险、人工可控的复验入口。结果是：

- 很难批量找出需要复验的因子
- 验证结果无法统一回写
- 状态管理只能依赖手工改 JSON 或临时脚本

自动调度可以以后再做，首版先提供一个人工触发的 CLI。

---

## Goal

新增手动 `revalidate` 命令行入口，支持：

- 选择候选因子
- 对候选因子执行复验
- 把结果回写到因子库
- 输出清晰的成功、失败、跳过统计

---

## Non-goals

- 不实现定时任务或自动调度。
- 不做多进程并行复验。
- 不做失败因子的自动修复或自动下线。

---

## Acceptance Criteria

1. 可按时间、状态或显式因子 ID 筛选候选因子。
2. 支持 `--dry-run` 只预览不执行。
3. 成功执行后，因子库的验证结果和状态字段会被正确更新。
4. 输出结果包含成功、失败、跳过数量与原因。

---

## Design Decision

### 命令形态

```bash
quantaalpha revalidate --days 30
quantaalpha revalidate --status stale
quantaalpha revalidate --status degraded
quantaalpha revalidate --factor-ids factor_001,factor_002
quantaalpha revalidate --days 30 --dry-run
quantaalpha revalidate --days 30 --no-write
```

### 执行流程

1. 读取因子库。
2. 根据筛选条件选出候选因子。
3. 对每个因子调用已有回测或多周期验证入口。
4. 生成新的 `evaluation` 结果。
5. 根据是否允许写回，更新 JSON 并输出报告。

### 输出示例

```text
Revalidation Report
===================
Total candidates: 15
Success: 12
Failed: 2
Skipped: 1

- factor_001: active (stability_score=0.82)
- factor_002: degraded (stability_score=0.41)
- factor_003: failed (reason=data not available)
```

---

## Affected Modules

- `third_party/quantaalpha/launcher.py`
- CLI 解析入口
- 因子库筛选和写回逻辑
- 多周期验证调用链

---

## Implementation Plan

1. 在 CLI 入口增加 `revalidate` 子命令及参数校验。
2. 在因子库层增加候选因子筛选函数，支持 days、status、factor_ids。
3. 将多周期验证封装成可复用函数，避免 CLI 直接拼接 runner 内部逻辑。
4. 将结果回写到 `evaluation`，并输出终端报告。
5. 增加 `--dry-run` 和 `--no-write`，保证手工操作安全。

---

## Test Plan

### 单元测试

1. `last_validated` 超过阈值时，会被 `--days` 正确选中。
2. `--status stale` 和 `--status degraded` 的筛选结果正确。
3. `--factor-ids` 对不存在的因子给出明确提示。
4. `--dry-run` 模式不会写文件。

### 集成测试

5. CLI 能读取因子库并筛出目标因子。
6. 复验完成后，`evaluation.last_validated`、`stability_score`、`status` 被正确更新。
7. 回写失败时，CLI 会返回非零退出码并保留失败原因。

### 手工验收

8. 选一个 `stale` 因子执行完整复验，确认报告输出、JSON 回写和最终状态一致。

---

## Risk Points

1. 批量复验耗时长，用户需要可预估的候选数量。
2. 若 CLI 直接修改原始 JSON，没有备份或 `--no-write` 会提高误操作风险。
3. 如果复验入口和主回测入口协议不一致，后续维护成本会很高。

---

## Rollback Plan

- 提供 `--dry-run` 和 `--no-write`。
- 写回前先生成备份文件或临时文件，再原子替换。
- 若 CLI 入口不稳定，可先只上线筛选和预览能力。

---

## Final Result

- 已新增最小可用的 `revalidate` CLI。
- 当前支持：
  - 选择候选因子
  - `--dry-run` 预览
  - 将复验结果回写到因子库
- 当前仍属于轻量入口，不是完整自动调度系统。

---

## Validation Evidence

- README 和模块文档已补充 `revalidate` 用法。
- 验收草案已把“对 30 天未更新因子库做复验预览”列为正常用户场景。
- 代码路径与因子库 schema 已打通，能够使用 `evaluation` 相关字段。

---

## Lessons Learned

- 首版 CLI 最重要的是可控和可预览，而不是并行化。
- `--dry-run` 是必要安全阀，否则人工复验很容易直接污染 JSON 资产。
