# 因子库状态与验证字段扩展

Status: completed
Owner: QuantaAlpha team
Created: 2026-03-14
Outcome: implemented
Phase: 1
Depends-on: /home/quan/testdata/aspipe_v4/docs/03-changes/quantaalpha/quantaalpha2026-3-14checklist/2026-03-14-multi-period-validation.md
Related-to: /home/quan/testdata/aspipe_v4/docs/drafts/自主挖掘因子回测和因子管理/2026-03-14-quantaalpha-continuous-factor-implementation-checklist.md

---

## Background

当前 `quantaalpha/factors/library.py` 里的因子库更像归档文件：能记录因子表达式、回测结果和反馈，但缺少长期维护所需的验证信息、状态字段和数据依赖声明。

如果不先升级 schema，后续的复验、状态流转、前端筛选和演化控制都会被迫使用“临时字段”或额外 sidecar 文件，最终让系统更难维护。

---

## Goal

把因子库从“实验结果快照”扩展为“可持续维护的研究资产索引”，最小化新增两组字段：

- `evaluation`: 验证状态与稳定性信息
- `data_requirements`: 因子依赖的数据维度说明

---

## Non-goals

- 不把 JSON 因子库替换成数据库。
- 不实现完整版本控制、差异追踪或 lineage。
- 不在首版维护全量历史审计日志。

---

## Acceptance Criteria

1. 新旧因子库文件都能被同一套读取逻辑兼容处理。
2. 新写入因子默认具备最小 `evaluation` 和 `data_requirements` 结构。
3. 多周期验证结果可直接回写到 `evaluation.period_results` 和 `evaluation.stability_score`。
4. 旧文件缺少新字段时，不会破坏现有回测和读取流程。

---

## Design Decision

### 目标结构

```python
{
    "factor_id": "abcd1234",
    "factor_name": "volume_reversal",
    "factor_expression": "...",
    "metadata": {...},
    "backtest_results": {...},
    "feedback": {...},
    "evaluation": {
        "status": "pending_validation",
        "last_validated": None,
        "stability_score": None,
        "period_results": [],
        "validation_summary": "",
        "consecutive_failures": 0,
    },
    "data_requirements": {
        "dimensions": ["price_volume"],
        "fields": ["$close", "$volume"],
    }
}
```

### 兼容策略

- 读取时用 schema 补全函数填默认值，不要求一次性迁移全量 JSON。
- 写入时总是按新结构输出，逐步完成自然升级。
- `metadata.version` 从 `1.0` 升到 `1.1`，但读取逻辑继续兼容 `1.0`。

### 状态集合

| 状态 | 含义 |
|------|------|
| `pending_validation` | 新入库、尚未完成多周期验证 |
| `active` | 最近一次验证通过，允许被复用 |
| `degraded` | 最近验证显著下滑 |
| `stale` | 超过阈值未验证 |
| `deprecated` | 不再推荐使用 |

---

## Affected Modules

- `third_party/quantaalpha/quantaalpha/factors/library.py`
- `third_party/quantaalpha/quantaalpha/pipeline/loop.py`
- 因子回写调用链

---

## Implementation Plan

1. 在 `FactorLibraryManager` 中增加 schema 补全函数，例如 `_normalize_factor_entry()`。
2. 写入新因子时补全 `evaluation` 和 `data_requirements` 默认结构。
3. 从多周期验证模块接入 `period_results` 和 `stability_score` 回写。
4. 在保存时更新 `metadata.version`，但不强制迁移历史文件。
5. 为缺字段的旧数据保留兼容默认值，避免旧流程读取失败。

---

## Test Plan

### 单元测试

1. 新因子写入后包含完整 `evaluation` 和 `data_requirements`。
2. 旧因子缺少新字段时，schema 补全函数会返回兼容结构。
3. 写入多周期结果后，`last_validated`、`stability_score`、`period_results` 被正确更新。

### 集成测试

4. 历史 JSON 因子库能被正常加载并再次保存。
5. 新旧因子混合存在时，前端或 CLI 读取接口不报错。
6. 未提供验证结果时，新增字段保持默认值且不影响现有回测流程。

### 手工验收

7. 抽查一个旧因子和一个新因子，确认最终 JSON 结构一致且字段语义清晰。

---

## Risk Points

1. 如果把状态逻辑直接耦合进 schema 层，后续规则调整会很痛苦。
2. JSON 文件体积会增大，尤其是 `period_results` 过多时。
3. 若无兼容补全函数，旧因子库将成为上线阻塞项。

---

## Rollback Plan

- 新字段保持可选，读取时以默认值降级。
- 如果回写新结构出现问题，可暂时只在内存中补全，不落盘。
- 必要时保留 `metadata.version=1.0`，但内部先验证新字段流程。

---

## Final Result

- 因子库仍保持 JSON 作为存储介质，但 schema 已扩展为可维护结构。
- 当前新增并兼容的核心字段包括：
  - `evaluation`
  - `data_requirements`
- 新旧 JSON 都可被同一套读取逻辑兼容处理，旧条目会在读取或写回时补全默认结构。

---

## Validation Evidence

- 当前运行和 CLI 说明均已基于扩展后的 JSON schema。
- 实际运行中因子库仍以 `all_factors_library.json` 为主文件，不存在数据库替换。
- 连续因子特性测试已覆盖新 schema 的最小兼容逻辑。

---

## Lessons Learned

- 先做 schema 兼容补全，比先做“全量迁移脚本”更稳。
- 因子库升级后，后续复验、状态流转和 evolution 才能共用一套字段协议。
