# QuantaAlpha 持续挖掘设计 V2 评估与建议

评估日期: 2026-03-15
评估对象: `/docs/drafts/自主挖掘因子回测和因子管理/continuous mining/design/2026-03-15-quantaalpha-continuous-mining-design-v2.md`

---

## 一、总体评估

### 1.1 结论：V2 设计是合理且务实的

V2 设计相比 V1 做出了正确的收敛和聚焦，具体体现在：

| 维度 | V1 问题 | V2 修正 | 评估 |
|------|---------|---------|------|
| 架构定位 | "四层大平台" | "三层主链路 + 外部调度" | ✅ 降低复杂度 |
| 数据能力注册表 | 主 prompt 默认注入 | 保留但受控使用 | ✅ 避免上下文膨胀 |
| 多模型协作 | fanout + provider pool + repair chain | 任务级路由 + 兜底 | ✅ 渐进式增强 |
| 持续运行 | 内部 24h daemon | 外部定时触发 | ✅ 降低运维风险 |
| 因子库 | 向量库 + 检索 + guidance | JSON 为主事实源 | ✅ 稳妥起步 |

### 1.2 设计合理性评分

| 评估项 | 分数 | 说明 |
|--------|------|------|
| 目标清晰度 | 9/10 | 明确"最小闭环"而非"大而全平台" |
| 代码对齐度 | 8/10 | 已落地能力与设计描述基本一致 |
| 实施可行性 | 8/10 | Phase 划分合理，优先级清晰 |
| 风险识别 | 7/10 | 识别了关键风险，但缺少量化指标 |
| 可验收性 | 7/10 | 验收标准以问题形式给出，缺少具体指标 |

---

## 二、代码现状与 V2 设计对齐分析

### 2.1 已落地能力（与设计一致）

| V2 设计要求 | 代码位置 | 实现状态 |
|-------------|----------|----------|
| 统一股票池过滤 | `backtest/universe.py` | ✅ 完整实现 |
| 多周期验证 | `backtest/validation.py` | ✅ 完整实现，含稳定性评分 |
| 因子状态流转 | `factors/status_rules.py` | ✅ 完整实现，含 degraded/stale/deprecated |
| 因子库 schema 扩展 | `factors/library.py` | ✅ 包含 evaluation/data_requirements/evolution |
| 一致性检查 | `regulator/consistency_checker.py` | ✅ FactorConsistencyChecker + FactorQualityGate |
| 结果质量门控 | `runner.py` + 配置 | ✅ NaN/inf/常数列检查 |
| revalidate CLI | `cli.py` | ✅ 支持 dry_run/days/status/factor_ids |
| evolution 模式 | `pipeline/factor_mining.py` | ✅ Original → Mutation → Crossover 循环 |

### 2.2 部分实现/待完善

| V2 设计要求 | 当前状态 | 差距 |
|-------------|----------|------|
| 数据能力注册表 | `data_capability.py` 存在 | 未接入主 prompt，符合 V2 定位，但缺少"受控注入"机制 |
| 外部调度脚本 | CLI 已支持外部调用 | 缺少标准化触发脚本和错误处理 |
| 状态变更审计 | `library.py` 有 `_save()` | 缺少审计日志和变更原因记录 |

### 2.3 未实现

| V2 设计要求 | 当前状态 | 建议 |
|-------------|----------|------|
| 运行摘要输出 | 无 | 需补充：stale 数、active/degraded 分布、最近成功时间 |
| 回归测试覆盖 | 未验证 | 需验证是否覆盖 Phase A 四项内容 |

---

## 三、具体建议

### 3.1 架构层建议

#### 建议 1：补充外部调度标准脚本

V2 明确"不做内部 daemon"，但缺少标准化触发脚本。

**建议新增文件**：`scripts/continuous_mine.sh`

```bash
#!/bin/bash
# QuantaAlpha 持续挖掘触发脚本
# 用法: ./continuous_mine.sh [--dry-run]

set -e

PROJECT_ROOT="/home/quan/testdata/aspipe_v4/third_party/quantaalpha"
CONFIG_PATH="$PROJECT_ROOT/configs/experiment.yaml"
LIBRARY_PATH="$PROJECT_ROOT/data/factor_library.json"
LOG_DIR="/var/log/quantaalpha"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="$LOG_DIR/mine_$TIMESTAMP.log"

mkdir -p "$LOG_DIR"

echo "[$(date)] Starting mining run..." | tee -a "$LOG_FILE"

cd "$PROJECT_ROOT"

# 运行挖掘
python -m quantaalpha.cli mine \
    --config_path "$CONFIG_PATH" \
    2>&1 | tee -a "$LOG_FILE"

# 运行复验 (dry-run)
echo "[$(date)] Running revalidation check..." | tee -a "$LOG_FILE"
python -m quantaalpha.cli revalidate \
    --library_path "$LIBRARY_PATH" \
    --days 21 \
    --dry_run \
    2>&1 | tee -a "$LOG_FILE"

echo "[$(date)] Mining run complete" | tee -a "$LOG_FILE"
```

#### 建议 2：增加运行摘要输出

在每次挖掘结束后，输出结构化摘要，便于监控和告警。

**建议在 `FactorLibraryManager` 中新增方法**：

```python
def get_library_summary(self) -> dict:
    """返回因子库运行摘要"""
    factors = self.data.get("factors", {})
    status_counts = Counter(
        f.get("evaluation", {}).get("status", "unknown")
        for f in factors.values()
    )
    stale_count = status_counts.get("stale", 0)
    active_count = status_counts.get("active", 0)
    degraded_count = status_counts.get("degraded", 0)

    last_validated_list = [
        f.get("evaluation", {}).get("last_validated")
        for f in factors.values()
        if f.get("evaluation", {}).get("last_validated")
    ]
    last_validated = max(last_validated_list) if last_validated_list else None

    return {
        "total_factors": len(factors),
        "status_distribution": dict(status_counts),
        "stale_count": stale_count,
        "active_count": active_count,
        "degraded_count": degraded_count,
        "last_validated": last_validated,
        "library_path": str(self.library_path),
        "last_updated": self.data.get("metadata", {}).get("last_updated"),
    }
```

#### 建议 3：增加状态变更审计日志

当前因子状态变更无审计记录，难以追溯"为什么状态变了"。

**建议扩展 `apply_validation_result`**：

```python
def apply_validation_result(
    self,
    factor_entry: dict,
    validation_result: dict,
    *,
    now: datetime | None = None,
    config: dict | None = None,
    persist: bool = True,
    reason: str = "",  # 新增：变更原因
) -> dict:
    old_status = factor_entry.get("evaluation", {}).get("status")
    updated = update_factor_status(...)
    new_status = updated.get("evaluation", {}).get("status")

    if old_status != new_status:
        audit_entry = {
            "timestamp": datetime.now().isoformat(),
            "factor_id": updated.get("factor_id"),
            "old_status": old_status,
            "new_status": new_status,
            "reason": reason,
            "trigger": "validation_result",
        }
        self._append_audit_log(audit_entry)

    if persist:
        self._save()
    return updated

def _append_audit_log(self, entry: dict):
    """追加审计日志"""
    if "audit_log" not in self.data:
        self.data["audit_log"] = []
    self.data["audit_log"].append(entry)
    # 保留最近 1000 条
    if len(self.data["audit_log"]) > 1000:
        self.data["audit_log"] = self.data["audit_log"][-1000:]
```

### 3.2 验证与治理层建议

#### 建议 4：量化稳定性评分阈值

V2 设计提到"稳定性评分"，但未明确阈值。

**当前代码** (`status_rules.py`)：
- `active_stability_threshold`: 0.5
- `degraded_stability_threshold`: 0.3

**建议**：在 V2 设计中补充明确的阈值定义，并说明阈值来源（历史数据拟合或业务经验）。

#### 建议 5：增加因子"健康度"指标

当前稳定性评分只看 IC 和信息比，建议增加"健康度"综合指标：

```python
def compute_health_score(factor_entry: dict) -> float:
    """计算因子健康度 (0-1)"""
    evaluation = factor_entry.get("evaluation", {})
    status = evaluation.get("status", "unknown")

    # 基础分数
    status_scores = {
        "active": 1.0,
        "degraded": 0.6,
        "stale": 0.4,
        "pending_validation": 0.3,
        "pending_revalidation": 0.5,
        "deprecated": 0.0,
    }
    base = status_scores.get(status, 0.3)

    # 稳定性调整
    stability = evaluation.get("stability_score")
    if stability is not None:
        base = base * 0.6 + stability * 0.4

    # 时效性调整
    last_validated = evaluation.get("last_validated")
    if last_validated:
        days_since = (datetime.now() - datetime.fromisoformat(last_validated)).days
        freshness = max(0, 1 - days_since / 90)  # 90 天后时效性归零
        base = base * (0.7 + 0.3 * freshness)

    return round(base, 3)
```

### 3.3 研究主链路建议

#### 建议 6：明确 debug 策略的"失败因子"定义

V2 设计提到"debug 只重试失败因子"，但未明确"失败"的定义。

**建议补充**：

```yaml
debug_strategy:
  # 失败因子定义
  failure_criteria:
    - expression_parse_failed: true
    - calculation_nan_ratio: ">0.5"
    - backtest_failed: true
    - quality_gate_failed: true

  # 成功提前退出
  early_exit_on_success: true

  # 最大重试轮数
  max_debug_rounds: 10
```

#### 建议 7：增加 planning 边界约束的可测试性

V2 设计强调"方向受当前日频数据边界限制"，但缺少可测试的约束定义。

**建议新增**：`factors/planning_constraints.py`

```python
ALLOWED_DATA_DIMENSIONS = ["price_volume"]
ALLOWED_FIELDS = ["$open", "$close", "$high", "$low", "$volume", "$amount"]
DISALLOWED_FIELDS = ["$pe", "$pb", "$roe", "$roa"]  # 基本面字段暂不可用

def validate_direction(direction: str) -> tuple[bool, str]:
    """验证研究方向是否在允许的数据边界内"""
    for field in DISALLOWED_FIELDS:
        if field.lower() in direction.lower():
            return False, f"Direction references unavailable field: {field}"
    return True, "OK"
```

### 3.4 测试与验收建议

#### 建议 8：补充回归测试检查清单

V2 的 Phase A 要求补充回归测试，建议明确检查清单：

| 测试项 | 测试文件 | 状态 |
|--------|----------|------|
| planning 边界约束 | `test_planning_constraints.py` | 待创建 |
| debug 只重试失败因子 | `test_debug_strategy.py` | 待创建 |
| 结果质量门控坏样本 | `test_quality_gate.py` | 待创建 |
| 状态流转端到端 | `test_factor_status_flow.py` | 待创建 |

#### 建议 9：增加验收指标

V2 的验收标准以问题形式给出，建议补充量化指标：

| 验收问题 | 量化指标 |
|----------|----------|
| 方向是否被限制在当前数据边界内 | 违规方向拦截率 = 100% |
| 坏因子是否会在回测前被挡掉 | 坏因子拦截率 ≥ 95% |
| 成功因子是否不再被重复 debug | 成功因子重复 debug 比例 = 0% |
| 因子库是否反映当前有效状态 | 状态更新延迟 ≤ 1 小时 |
| 多周期结果是否参与后续选择 | evolution 使用 stability_score 的比例 = 100% |
| 系统是否可外部调度持续运行 | 单次运行成功率 ≥ 90% |

---

## 四、V2 设计缺失项建议

### 4.1 缺失：错误恢复策略

V2 设计未明确错误恢复策略。当外部调度触发失败时，如何恢复？

**建议补充**：

```yaml
error_recovery:
  # LLM 调用失败
  llm_failure:
    max_retries: 3
    retry_delay: 60  # 秒
    fallback_model: "gpt-4o-mini"

  # 回测超时
  backtest_timeout:
    default_timeout: 800
    force_terminate_after: 1200
    on_timeout: "skip_factor"

  # 因子计算失败
  calculation_failure:
    max_nan_ratio: 0.3
    on_failure: "mark_degraded"
```

### 4.2 缺失：告警机制

V2 设计未包含告警机制。

**建议补充告警场景**：

| 场景 | 阈值 | 告警级别 |
|------|------|----------|
| 连续 3 次挖掘失败 | 3 次 | critical |
| stale 因子占比 > 50% | 50% | warning |
| deprecated 因子占比 > 30% | 30% | warning |
| 单次挖掘产出因子 = 0 | 0 | warning |
| LLM 调用失败率 > 20% | 20% | critical |

### 4.3 缺失：数据维度扩展路径

V2 设计提到"受控恢复数据能力注册表注入"，但未明确扩展路径。

**建议补充路线图**：

```
Phase 1 (当前): 日频价量数据
    ↓
Phase 2: 增加 stk_factor_pro 技术指标
    - MA, EMA, MACD, KDJ, RSI, BOLL, ATR, CCI
    - 需更新 data_capability.py 字段列表
    ↓
Phase 3: 增加资金流向数据
    - 需定义 freq/lag/join_mode
    - 需验证 as-of 对齐正确性
    ↓
Phase 4: 增加基本面数据
    - 需处理季频披露滞后
    - 需防止未来函数
```

---

## 五、总结

### 5.1 V2 设计的优点

1. **务实收敛**：从"四层大平台"收缩为"三层主链路 + 外部调度"
2. **反映真实**：已落地能力如实记录，未形成稳定主链路的能力明确降级
3. **明确优先级**：Phase A/B/C 划分合理，先稳定主链路再扩展
4. **风险意识**：把"系统稳定性约束"写进主线设计

### 5.2 V2 设计的不足

1. **缺少外部调度标准脚本**：设计说不做 daemon，但没给出替代方案
2. **缺少量化指标**：验收标准以问题形式给出，缺少可测量的阈值
3. **缺少错误恢复策略**：失败后如何处理未明确
4. **缺少告警机制**：持续运行需要监控告警支撑

### 5.3 优先级建议

| 优先级 | 建议 | 工作量 |
|--------|------|--------|
| P0 | 补充外部调度标准脚本 | 0.5 天 |
| P0 | 补充运行摘要输出 | 0.5 天 |
| P1 | 补充状态变更审计日志 | 0.5 天 |
| P1 | 补充量化验收指标 | 0.5 天 |
| P2 | 补充错误恢复策略 | 1 天 |
| P2 | 补充告警机制 | 1 天 |
| P3 | 补充回归测试 | 2 天 |
| P3 | 补充数据维度扩展路径 | 0.5 天 |
