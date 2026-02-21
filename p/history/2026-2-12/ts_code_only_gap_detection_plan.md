# 股票无数据时只传 ts_code 方案

**文档版本**: v1.1  
**日期**: 2026-02-13  
**状态**: 已实施

---

## 一、问题描述

### 1.1 现象

当执行 `--update --interface disclosure_date --ts_code 000001.SZ` 时，API 返回 0 条记录，但直接调用 API 只传 `ts_code` 可以返回 104 条记录。

### 1.2 根因分析

**问题 1**: `detect_stock_gaps()` 返回带日期范围的任务
```python
return [{'ts_code': ts_code, 'start_date': '20000101', 'end_date': '20260213'}]
```

**问题 2**: 日期锚定接口（类型 C）的 YAML 配置中启用了 `time_range`：
```yaml
pagination:
  time_range:
    window: 9999d
```

这导致 `PaginationComposer.compose()` 会自动添加 `start_date` 和 `end_date` 参数到请求中。

**关键问题**: 日期锚定接口（如 disclosure_date）的 API **不支持** `start_date` 参数，只支持 `end_date`（作为日期锚定参数）。当收到不支持的 `start_date` 参数时，API 返回空数据。

---

## 二、解决方案

### 2.1 修改 1: coverage_manager.py

股票无数据时只返回 `{'ts_code': xxx}`：

**文件**: `/home/quan/testdata/aspipe_v4/app4/core/coverage_manager.py`

**修改位置**: `_detect_trade_date_gaps()`, `_detect_report_period_gaps()`, `_detect_date_anchor_gaps()` 三个方法

**修改内容**:
```python
# 修改前
if not existing_dates:
    return [{'ts_code': ts_code, 'start_date': start_date, 'end_date': end_date}]

# 修改后
if not existing_dates:
    logger.info(f"[{ts_code}] 股票无数据，使用单次全历史请求（只传 ts_code）")
    return [{'ts_code': ts_code}]
```

### 2.2 修改 2: pagination.py

日期锚定接口跳过 `time_range` 处理：

**文件**: `/home/quan/testdata/aspipe_v4/app4/core/pagination.py`

**修改位置**: `PaginationComposer.compose()` 方法

**修改内容**:
```python
def compose(self, base_params: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
    params_stream = [base_params]
    
    # 检查是否是日期锚定接口（类型 C）
    is_date_anchor_interface = self._is_date_anchor_interface()
    
    # 1. 时间维度 - 日期锚定接口跳过
    if self._is_enabled('time_range') and not is_date_anchor_interface:
        params_stream = list(self._apply_time_range(params_stream))
    
    # ... 其余逻辑不变

def _is_date_anchor_interface(self) -> bool:
    """检查是否是日期锚定接口"""
    parameters = self.interface_config.get('parameters', {})
    return any(p.get('is_date_anchor', False) for p in parameters.values())
```

---

## 三、修改后的行为

| 场景 | 传给 API 的参数 |
|------|----------------|
| 股票无数据 | `{'ts_code': 'xxx'}` |
| 股票有数据（类型 A/B） | `{'ts_code', 'start_date', 'end_date'}` |
| 股票有数据（类型 C） | `{'ts_code', anchor_param}` |
| 股票有数据（类型 D） | `[]` (跳过) |

---

## 四、验证结果

```
Downloaded 104 records for disclosure_date
Wrote 104 records to data/disclosure_date/disclosure_date_20020331_20260101_*.parquet
```

API 返回 104 条记录，数据正确保存。

---

## 五、涉及文件

| 文件 | 修改类型 |
|------|---------|
| `app4/core/coverage_manager.py` | 修改缺口检测返回值 |
| `app4/core/pagination.py` | 日期锚定接口跳过 time_range |

---

**文档结束**
