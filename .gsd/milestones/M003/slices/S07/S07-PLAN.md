# S07: PIT 对齐执行层

**触发决策**: D013

**问题**: 仅靠 prompt 约束无法阻止 LLM 生成使用未来数据的因子表达式。

**参考文档**:
- `docs/drafts/factormining/structure/2026-03-22-continuous-mining-plan-supplement.md` 第 3.6 节
- D013: PIT 强约束

---

## 目标

在因子回测计算层强制执行 Point-in-Time (PIT) 对齐：
- T 日只能使用 ann_date <= T 的财务数据
- 按 lag_days 滞后

---

## 成功标准

- [ ] `pit_alignment.py:apply_pit_alignment()` 实现
- [ ] 财务数据按 ann_date 动态对齐
- [ ] 支持滞后 lag_days
- [ ] 集成到 custom_factor_calculator.py
- [ ] 消除未来函数导致的偏误

---

## 任务拆分

### T01: 实现 PIT 对齐函数
**文件**: `quantaalpha/factors/pit_alignment.py` (新建)
**估算**: 4h

```python
import polars as pl
from pathlib import Path

def apply_pit_alignment(
    factor_df: pl.LazyFrame,
    data_source: str,
    pit_field: str = "ann_date",
    trade_date_field: str = "date",
) -> pl.LazyFrame:
    """
    对财务数据应用 Point-in-Time 对齐。
    确保 T 日只能看到 ann_date <= T 的数据。
    """
    # 1. 获取数据能力注册表
    # 2. 检查是否为季度数据
    # 3. 获取 lag_days
    # 4. 过滤 ann_date <= date - lag_days
    # 5. 按 symbol 分组，取每组最后一条
```

**验收**:
- [ ] 正确识别季度数据
- [ ] 按 lag_days 滞后
- [ ] 按 symbol 分组取最新

### T02: 集成到 custom_factor_calculator.py
**文件**: `quantaalpha/backtest/custom_factor_calculator.py`
**估算**: 2h

在 `calculate_factor()` 中调用 `apply_pit_alignment()`。

**验收**:
- [ ] 财务数据自动 PIT 对齐
- [ ] 日频数据不触发对齐

### T03: 添加单元测试
**文件**: `tests/factors/test_pit_alignment.py` (新建)
**估算**: 2h

测试：
1. 正常 PIT 对齐
2. 滞后 lag_days
3. 日频数据不触发

**验收**:
- [ ] 所有测试通过
- [ ] 未来函数消除验证

---

## 依赖

- **S01**: 数据能力注册表（获取 lag_days）
- **D013**: PIT 对齐决策
