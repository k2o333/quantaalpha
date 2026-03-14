# 手动 Revalidate CLI

Status: draft
Owner: QuantaAlpha team
Created: 2026-03-14
Outcome: pending
Phase: 2
Depends-on:
- /home/quan/testdata/aspipe_v4/docs/drafts/自主挖掘因子回测和因子管理/quantaalpha2026-3-14checklist/2026-03-14-multi-period-validation.md
- /home/quan/testdata/aspipe_v4/docs/drafts/自主挖掘因子回测和因子管理/quantaalpha2026-3-14checklist/2026-03-14-factor-library-schema-extension.md
Related-to: /home/quan/testdata/aspipe_v4/docs/drafts/自主挖掘因子回测和因子管理/2026-03-14-quantaalpha-continuous-factor-implementation-checklist.md

---

## Background

因子入库后缺乏定期复验机制：
- 因子状态无法自动更新
- 无法批量筛选需要复验的因子
- 复验结果无法便捷回写因子库

---

## Goal

新增命令行入口，支持：
- 按时间条件筛选需要复验的因子
- 执行复验后回写因子库
- 更新因子状态

---

## Non-goals

- 不实现自动调度（Phase 3）
- 不支持并行复验（首版串行执行）
- 不实现复验失败后的自动修复

---

## Acceptance Criteria

1. 可以手动批量复验指定因子集
2. CLI 结果明确显示成功、失败、跳过数量
3. 因子库被正确更新

---

## Test Plan

### 单元测试

1. 因子筛选函数能正确识别 `last_validated` 超过阈值的因子
2. 状态筛选函数能正确识别 `stale` 或 `degraded` 因子

### 集成测试

3. 能筛选 `last_validated` 超过阈值的因子
4. 能仅复验 `stale` 或 `degraded` 因子
5. 复验后状态和验证信息被正确回写

### 手工验收

6. 一个 `stale` 因子的完整复验流程

---

## Implementation Plan

### 主要修改点

- CLI 入口
- 因子库筛选逻辑
- 回测调用逻辑
- 状态回写逻辑

### 命令设计

```bash
# 复验超过30天未验证的因子
quantaalpha revalidate --days 30

# 仅复验 stale 状态的因子
quantaalpha revalidate --status stale

# 仅复验 degraded 状态的因子
quantaalpha revalidate --status degraded

# 复验指定因子
quantaalpha revalidate --factor-ids factor_001,factor_002

# 干跑模式（不实际执行）
quantaalpha revalidate --days 30 --dry-run
```

### 输出格式

```
Revalidation Report
===================
Total candidates: 15
Success: 12
Failed: 2
Skipped: 1

Details:
  - factor_001: active (stability_score: 0.82)
  - factor_002: degraded (stability_score: 0.45)
  - factor_003: FAILED (error: data not available)
  ...
```

---

## Risk Points

1. 批量复验可能耗时较长
2. 复验期间数据源不可用可能导致批量失败
3. 状态回写失败需要重试机制

---

## Rollback Plan

- `--dry-run` 模式可预览而不执行
- 复验前自动备份因子库
- 提供 `--no-write` 选项仅输出结果不回写

---

## Final Result

> 待实施后填写

---

## Validation Evidence

> 待实施后填写

---

## Lessons Learned

> 待实施后填写
