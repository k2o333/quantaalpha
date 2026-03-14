# QuantaAlpha Continuous Factor Checklist Index

Status: draft
Owner: QuantaAlpha team
Created: 2026-03-14
Outcome: pending
Related-to: /home/quan/testdata/aspipe_v4/docs/drafts/自主挖掘因子回测和因子管理/2026-03-14-quantaalpha-continuous-factor-implementation-checklist.md

## Purpose

This directory decomposes the implementation checklist into one concrete change doc per change.

These documents are still in `draft` state, but they are structured so they can be promoted into `docs/03-changes/quantaalpha` after approval.

## Recommended Execution Order

### Phase 1

1. [统一股票池过滤入口](/home/quan/testdata/aspipe_v4/docs/drafts/自主挖掘因子回测和因子管理/quantaalpha2026-3-14checklist/2026-03-14-unified-stock-universe-filter.md)
2. [多周期验证](/home/quan/testdata/aspipe_v4/docs/drafts/自主挖掘因子回测和因子管理/quantaalpha2026-3-14checklist/2026-03-14-multi-period-validation.md)
3. [因子库状态与验证字段扩展](/home/quan/testdata/aspipe_v4/docs/drafts/自主挖掘因子回测和因子管理/quantaalpha2026-3-14checklist/2026-03-14-factor-library-schema-extension.md)
4. [最小版数据能力注册表](/home/quan/testdata/aspipe_v4/docs/drafts/自主挖掘因子回测和因子管理/quantaalpha2026-3-14checklist/2026-03-14-data-capability-registry.md)

### Phase 2

1. [手动 Revalidate CLI](/home/quan/testdata/aspipe_v4/docs/drafts/自主挖掘因子回测和因子管理/quantaalpha2026-3-14checklist/2026-03-14-revalidate-cli.md)
2. [因子状态流转规则](/home/quan/testdata/aspipe_v4/docs/drafts/自主挖掘因子回测和因子管理/quantaalpha2026-3-14checklist/2026-03-14-factor-status-transition-rules.md)
3. [多周期稳定性结果接入 Evolution](/home/quan/testdata/aspipe_v4/docs/drafts/自主挖掘因子回测和因子管理/quantaalpha2026-3-14checklist/2026-03-14-stability-results-in-evolution.md)
4. [任务级 LLM 路由](/home/quan/testdata/aspipe_v4/docs/drafts/自主挖掘因子回测和因子管理/quantaalpha2026-3-14checklist/2026-03-14-task-level-llm-routing.md)

## Promotion Criteria

This checklist set is ready to move into `docs/03-changes/quantaalpha` when:

1. The proposed changes are approved for implementation.
2. Each document remains scoped to one concrete change.
3. Ownership and execution order are accepted by the team.

## Notes

- `Final Result` and `Validation Evidence` remain intentionally empty until implementation.
- These documents should be updated in place once work starts or after promotion into formal change docs.
