# cyq_perf 下载问题修复方案

## 问题分析

### 问题：非交易日也发起请求
**现象**：日志显示多次 `Downloaded 0 records`

**原因**：`pagination.py:256` 的 `_apply_date_anchor_range` 方法调用 `_generate_daily_dates` 生成所有自然日，未过滤非交易日。

**代码位置**：
```python
# pagination.py:256
anchor_values = self._generate_daily_dates(start_date, end_date)  # 生成所有自然日
```

### 关于 trade_cal 不自动更新的澄清
经分析，`downloader.py` 的 `get_trade_calendar` 已经能处理日期范围不足的情况：
- 当请求范围超出本地数据时，`_get_trade_calendar_from_data_dir` 返回 `None`
- 这会自动触发 API 下载

**所以 trade_cal 自动更新不是问题**，问题仅在于 `_apply_date_anchor_range` 没有使用 trade_cal 过滤。

---

## 修复方案

**文件**：`app4/core/pagination.py`

**修改位置**：`_apply_date_anchor_range` 方法（约 255-256 行）

**修改内容**：
```python
# 修改前
anchor_values = self._generate_daily_dates(start_date, end_date)

# 修改后
anchor_values = [d["cal_date"] for d in self._get_trade_days(start_date, end_date)]
if not anchor_values:
    anchor_values = self._generate_daily_dates(start_date, end_date)  # 降级处理
```

---

## 影响范围

| 文件 | 影响接口 |
|------|---------|
| pagination.py | `reverse_date_range + is_date_anchor` 模式接口（如 cyq_perf） |

## 测试验证

```bash
# 测试非交易日过滤
python app4/main.py --update --interface cyq_perf --start_date 20260221 --end_date 20260223

# 验证日志中不再出现 "Downloaded 0 records"（除非是真的没有数据）
```
