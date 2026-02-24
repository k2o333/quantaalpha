# 最小改动方案：为 date_anchor_range 模式添加 offset 支持

## 问题

当前 `compose()` 方法中，`reverse_date_range + is_date_anchor` 组合模式缺少 offset 分页支持：

```python
# pagination.py 第95-98行
if pagination_mode == "reverse_date_range" and is_date_anchor_interface:
    params_stream = list(self._apply_date_anchor_range(params_stream))
    yield from params_stream
    return  # 直接返回，跳过了 offset 检查
```

## 影响范围

**仅影响 `cyq_perf` 接口**：

| 接口 | mode | is_date_anchor | 受影响 |
|------|------|----------------|--------|
| cyq_perf | reverse_date_range | ✅ trade_date | ✅ |
| daily_basic | reverse_date_range | ❌ | ❌ |
| moneyflow | reverse_date_range | ❌ | ❌ |
| 其他15个 | reverse_date_range | ❌ | ❌ |

## 是否需要 offset？

`cyq_perf` 配置：
- `query_limit: 5000`
- `window_size_days: 1`（按天查询）
- A股约 5000 只股票

**需要验证**：单日所有股票数据是否超过 5000 条？如果不超过，则无需修复。

## 最小改动方案

仅修改 `app4/core/pagination.py` 第95-98行：

```python
# 修改前
if pagination_mode == "reverse_date_range" and is_date_anchor_interface:
    params_stream = list(self._apply_date_anchor_range(params_stream))
    yield from params_stream
    return

# 修改后
if pagination_mode == "reverse_date_range" and is_date_anchor_interface:
    params_stream = list(self._apply_date_anchor_range(params_stream))
    if self._is_enabled("offset"):
        params_stream = list(self._apply_offset(params_stream))
    yield from params_stream
    return
```

## 改动清单

| 文件 | 改动 |
|------|------|
| app4/core/pagination.py | 第97行后插入2行 |

## 优点

1. **改动最小**：仅新增2行代码
2. **零风险**：不影响其他17个 `reverse_date_range` 接口
3. **向后兼容**：不改变现有行为，仅添加功能
4. **可快速验证**：改完即可测试 `cyq_perf`

## 实施步骤

1. 验证 `cyq_perf` 单日数据量是否超过 5000 条
2. 如果需要，应用上述修改
3. 运行测试：`python -m pytest test/test_date_anchor_pagination.py -v`
4. 下载测试：`python app4/main.py --interface cyq_perf --start_date 20260220 --end_date 20260224`

## 与方案3对比

| 维度 | 最小改动方案 | 方案3（统一重构） |
|------|-------------|------------------|
| 改动行数 | +2 行 | ~100 行 |
| 影响接口 | 1 个 | 全部 |
| 风险等级 | 低 | 中高 |
| 实施时间 | 5 分钟 | 2-4 小时 |
| 回归测试 | 仅测 cyq_perf | 全量测试 |

## 后续建议

如果未来发现多个接口需要类似修复，再考虑方案3的统一重构。当前阶段，最小改动是最佳选择。
