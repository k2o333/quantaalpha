# QuantaAlpha 持续挖掘设计 V2 评估与建议

Status: review
Created: 2026-03-15
Reviewer: iFlow CLI

---

## 1. 总体评价

V2 设计文档是对 V1 的**务实修正**，与代码实现现状高度吻合。

### 1.1 核心修正的正确性

| 修正点 | 评价 | 理由 |
|--------|------|------|
| 数据能力注册表降级为"受控注入" | ✅ 正确 | 代码中 `data_capability.py` 从未接入主 prompt |
| 多模型层从"大协作平台"收缩为任务级路由 | ✅ 正确 | 只有 `task_model_map`，无 fanout/provider pool |
| 不做常驻 24h daemon | ✅ 正确 | 只有 CLI，无调度器/队列 |
| 稳定性约束写入主线 | ✅ 必要 | consistency_checker + planning 约束已落地 |

### 1.2 设计与代码的一致性

```
V2 设计声明                    代码实现状态
─────────────────────────────────────────────
统一股票池过滤                  ✅ universe.py 完整
多周期验证                      ✅ validation.py 完整
因子库 schema + 状态流转        ✅ library.py + status_rules.py
任务级 LLM 路由                 ✅ llm/client.py
一致性检查                      ✅ consistency_checker.py
revalidate CLI                  ✅ cli.py
外部定时触发                    ⚠️ 需外部 cron
```

---

## 2. 建议改进点

### 2.1 revalidate 命令不完整

**问题**：当前 `revalidate` 只是复用已有的 `period_results`，没有真正运行回测。

**代码证据**（`cli.py`）：
```python
validation_result = {
    "status": "success",
    "period_results": evaluation.get("period_results", []),  # 复用旧数据
    "summary": summary,
}
```

**建议**：
1. 增加 `--real-backtest` 参数，触发真正的 `BacktestRunner.run()`
2. 或者明确文档说明当前 revalidate 只更新状态时间戳，不重新计算

### 2.2 测试覆盖不足

**问题**：`test_continuous_factor_features.py` 只覆盖单元测试，缺少：
- 端到端回测验证
- 状态流转集成测试
- planning 约束的真实场景测试

**建议**：
```
tests/
├── test_continuous_factor_features.py  (现有)
├── test_backtest_e2e.py                (新增：端到端)
├── test_status_transition.py           (新增：状态流转)
└── test_planning_constraints.py        (新增：方向约束)
```

### 2.3 "只重试失败因子"未明确实现

**问题**：V2 文档提到"debug 后续轮次更偏向只处理失败因子"，但代码中未看到明确的过滤逻辑。

**建议**：
1. 在 `loop.py` 的 `factor_calculate` 阶段增加失败因子筛选
2. 或在 `factor_propose` 阶段基于上一轮 feedback 过滤

### 2.4 缺少运行时监控指标

**问题**：V2 提到"运行日志与状态变更可观测"，但没有定义具体的监控指标。

**建议**增加以下指标采集：
```python
MONITORING_METRICS = {
    "mine_last_success": "timestamp",
    "mine_total_factors": "count",
    "mine_success_rate": "percentage",
    "revalidate_last_run": "timestamp",
    "library_status_distribution": {
        "active": "count",
        "degraded": "count",
        "stale": "count",
        "deprecated": "count",
    },
    "llm_call_success_rate": "percentage",
    "backtest_failure_count": "count",
}
```

---

## 3. 架构层面的建议

### 3.1 外部调度标准化

当前 V2 建议用 cron/外部调度，但没有提供标准化的调用脚本。

**建议**提供：
```bash
# scripts/continuous_mine.sh
#!/bin/bash
# 每日挖掘 + 复验的标准化脚本

quantaalpha mine --direction "momentum reversal"
quantaalpha revalidate --days 21 --status stale
```

### 3.2 因子库锁机制

多进程并发写入 `all_factors_library.json` 可能导致数据损坏。

**建议**：
1. 增加文件锁（`fcntl.flock`）
2. 或迁移到 SQLite 作为底层存储

### 3.3 质量门控的阈值可配置化

当前 `consistency_checker.py` 的阈值是硬编码的：
```python
symbol_length_threshold: int = 250,
base_features_threshold: int = 6,
```

**建议**移到配置文件：
```yaml
quality_gate:
  complexity:
    symbol_length_threshold: 250
    base_features_threshold: 6
  redundancy:
    duplication_threshold: 5
```

---

## 4. 实施优先级建议

按 V2 的 Phase A/B/C 框架，建议调整优先级：

### Phase A：稳定主链路（高优先级）

| 任务 | 优先级 | 预估工作量 |
|------|--------|-----------|
| 补充端到端测试 | P0 | 2-3 天 |
| revalidate 真正运行回测 | P0 | 1-2 天 |
| "只重试失败因子"实现 | P1 | 1 天 |
| 因子库文件锁 | P1 | 0.5 天 |

### Phase B：最小持续维护（中优先级）

| 任务 | 优先级 | 预估工作量 |
|------|--------|-----------|
| 标准化调度脚本 | P1 | 0.5 天 |
| 监控指标采集 | P2 | 1 天 |
| 质量门控配置化 | P2 | 0.5 天 |

### Phase C：受控增强（低优先级）

| 任务 | 优先级 | 备注 |
|------|--------|------|
| 数据能力注册表受控注入 | P3 | 仅在特定任务启用 |
| 单次 fallback 模型 | P3 | 等成本数据充分后再决定 |

---

## 5. 结论

**V2 设计是合理的**，它正确识别了：
1. 哪些能力已经落地且稳定
2. 哪些能力从未落地需要降级
3. 下一阶段应该做什么

**关键行动项**：
1. 补充端到端测试（Phase A 最重要的遗漏）
2. 完善 revalidate 命令
3. 提供标准化的外部调度脚本

**风险提示**：
- 因子库 JSON 并发写入风险
- 测试覆盖不足可能隐藏回归问题

---

## 附录：代码与设计对照检查清单

| V2 设计声明 | 对应代码位置 | 验证结果 |
|-------------|-------------|----------|
| planning 边界约束 | `planning.py:FORBIDDEN_DIRECTION_TERMS` | ✅ 已实现 |
| consistency gate | `consistency_checker.py` | ✅ 已实现 |
| 结果质量门控 | `loop.py:quality_gate_config` | ✅ 已实现 |
| 多周期验证 | `validation.py:aggregate_period_metrics` | ✅ 已实现 |
| 因子状态流转 | `status_rules.py:update_factor_status` | ✅ 已实现 |
| revalidate CLI | `cli.py:revalidate` | ⚠️ 不完整 |
| 外部调度支持 | 无 | ❌ 需补充脚本 |
| 监控指标 | 无 | ❌ 需补充 |
