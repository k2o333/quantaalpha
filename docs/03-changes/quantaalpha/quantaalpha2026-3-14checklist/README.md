# QuantaAlpha 持续因子研究变更清单

Status: draft
Owner: QuantaAlpha team
Created: 2026-03-14
Outcome: pending
Related-to: /home/quan/testdata/aspipe_v4/docs/drafts/自主挖掘因子回测和因子管理/2026-03-14-quantaalpha-continuous-factor-implementation-checklist.md

## 目的

本目录把持续因子研究能力拆成 8 份单变更文档，供逐项评审、逐项实施、逐项验收。

每份文档都要求回答 5 个问题：

1. 为什么要做。
2. 具体改哪里。
3. 第一版怎么控范围。
4. 如何测试。
5. 出问题怎么回退。

## 交付原则

- 一份文档只覆盖一个变更主题。
- 文档中的模块路径必须和 `third_party/quantaalpha` 当前代码结构对齐。
- 依赖关系要显式声明，避免 Phase 2 设计偷跑到 Phase 1。
- `Final Result`、`Validation Evidence`、`Lessons Learned` 在实现完成后回填，不在设计阶段伪造结果。

## 推荐实施顺序

### Phase 1

1. [统一股票池过滤入口](/home/quan/testdata/aspipe_v4/docs/03-changes/quantaalpha/quantaalpha2026-3-14checklist/2026-03-14-unified-stock-universe-filter.md)
2. [多周期验证](/home/quan/testdata/aspipe_v4/docs/03-changes/quantaalpha/quantaalpha2026-3-14checklist/2026-03-14-multi-period-validation.md)
3. [因子库状态与验证字段扩展](/home/quan/testdata/aspipe_v4/docs/03-changes/quantaalpha/quantaalpha2026-3-14checklist/2026-03-14-factor-library-schema-extension.md)
4. [最小版数据能力注册表](/home/quan/testdata/aspipe_v4/docs/03-changes/quantaalpha/quantaalpha2026-3-14checklist/2026-03-14-data-capability-registry.md)

### Phase 2

1. [手动 Revalidate CLI](/home/quan/testdata/aspipe_v4/docs/03-changes/quantaalpha/quantaalpha2026-3-14checklist/2026-03-14-revalidate-cli.md)
2. [因子状态流转规则](/home/quan/testdata/aspipe_v4/docs/03-changes/quantaalpha/quantaalpha2026-3-14checklist/2026-03-14-factor-status-transition-rules.md)
3. [多周期稳定性结果接入 Evolution](/home/quan/testdata/aspipe_v4/docs/03-changes/quantaalpha/quantaalpha2026-3-14checklist/2026-03-14-stability-results-in-evolution.md)
4. [任务级 LLM 路由](/home/quan/testdata/aspipe_v4/docs/03-changes/quantaalpha/quantaalpha2026-3-14checklist/2026-03-14-task-level-llm-routing.md)

## 文档索引

| 文档 | 关注点 | 核心依赖 |
|------|--------|----------|
| `2026-03-14-unified-stock-universe-filter.md` | 统一训练/验证/回测股票池 | 无 |
| `2026-03-14-multi-period-validation.md` | 多窗口验证与稳定性聚合 | 股票池过滤入口 |
| `2026-03-14-factor-library-schema-extension.md` | 因子库结构升级与兼容 | 多周期验证 |
| `2026-03-14-data-capability-registry.md` | 结构化数据能力描述 | 无 |
| `2026-03-14-revalidate-cli.md` | 手动批量复验入口 | 多周期验证、因子库扩展 |
| `2026-03-14-factor-status-transition-rules.md` | 状态自动流转与阈值 | 因子库扩展、Revalidate CLI |
| `2026-03-14-stability-results-in-evolution.md` | 稳定性反馈到演化策略 | 多周期验证、因子库扩展 |
| `2026-03-14-task-level-llm-routing.md` | 任务级模型路由 | 无 |

## 质量门禁

文档进入“可实施”状态前，至少满足以下条件：

1. 所有绝对路径链接都指向当前目录，不再指向旧的 `docs/drafts/.../quantaalpha2026-3-14checklist`。
2. 每份文档都包含 `Acceptance Criteria`、`Implementation Plan`、`Test Plan`、`Rollback Plan`。
3. 每份文档都明确首版不做什么，防止范围膨胀。
4. Phase 2 文档的 `Depends-on` 指向实际存在的 Phase 1 文档。

## 使用方式

- 评审时：优先看 `Goal`、`Non-goals`、`Acceptance Criteria`。
- 开发时：按 `Implementation Plan` 的顺序拆任务。
- 测试时：先跑文档内的单文档检查，再跑目录级整体检查。
- 落地后：把结果补回 `Final Result` 和 `Validation Evidence`，再决定是否提升到正式变更目录。

## 备注

- 这些文档当前仍是设计文档，不代表功能已经实现。
- 如果代码结构发生变化，应先修正文档里的模块映射，再继续实施。
