# pledge_stat 接口重复下载问题分析

## 问题概述

在使用 `--update --update-group period_range` 模式更新 pledge_stat 接口数据时，系统反复下载相同的数据（每次 3000 条），但去重后输出为 0，导致数据无法更新。

## 症状表现

日志显示：
1. 下载了 34 页数据，共 102000 条记录
2. 处理器检测到 5208 条重复记录
3. 去重后输出为 0 条：`input=96792, output=0, removed=96792`
4. 最终提示 "All records already exist for pledge_stat, skipping save"
5. 重复执行任务时，每次都下载相同数据，但永远无法保存

## 代码层面原因分析

### 1. 缺少 period_field 配置

**文件**: `app4/config/interfaces/pledge_stat.yaml`

```yaml
# 当前配置 (缺少 period_field)
pagination:
  enabled: true
  mode: period_range
  periods_per_batch: 1
  offset:
    enabled: true
    limit: 3000
```

**正确配置** (参考 disclosure_date.yaml):
```yaml
pagination:
  enabled: true
  mode: period_range
  period_field: end_date  # ← 缺少这个配置
  periods_per_batch: 1
  offset:
    enabled: true
    limit: 3000
```

### 2. 分页代码逻辑

**文件**: `app4/core/pagination.py:146-206`

```python
def _apply_period_range(self, params_stream):
    # 读取 period_field 配置，默认为 "period"
    period_field = self.config.get("period_field", "period")  # ← 默认使用 "period"
    
    for params in params_stream:
        # ...
        # 生成 period 参数
        if len(batch_periods) == 1:
            batch_params[period_field] = batch_periods[0]  # ← 写入 period=xxx 而非 end_date=xxx
```

由于没有配置 `period_field`，代码默认使用 `period` 作为参数名，导致 API 请求变成：
```python
{"ts_code": "000001.SZ", "period": "20100331"}  # 错误：应为 end_date
```

### 3. 覆盖率检测失效

**文件**: `app4/core/coverage_manager.py:415-468`

```python
def _check_period_existence(self, interface_name, params):
    period_field = params.get("_period_field", "period")  # ← 同样使用默认 "period"
    period = params.get(period_field)  # ← 获取 period=20100331
    
    # 检查数据库中是否存在 period=20100331 的数据
    return self._check_single_period_existence(interface_name, period)
```

由于查询参数错误 (`period` 而非 `end_date`)，API 返回的是**最新数据**而非指定 period 的数据。

### 4. 数据覆盖问题

**实际发生的情况**:
1. 系统请求: `{"ts_code": "000001.SZ", "period": "20100331"}` 
2. API 实际忽略未知参数 `period`，返回最新数据 (end_date=20250919)
3. 覆盖率检测检查 period=20100331 是否存在 → 不存在 → 需要下载
4. 下载到的数据 end_date=20250919，与已存在数据重复
5. 去重逻辑使用主键 `(ts_code, end_date, pledge_count, ...)` 判断
6. 新旧数据完全相同，全部被识别为重复并移除

### 5. 主键配置问题

**文件**: `app4/config/interfaces/pledge_stat.yaml`

```yaml
output:
  primary_key:
    - ts_code
    - end_date
    - pledge_count
    - unrest_pledge
    - rest_pledge
    - total_share
    - pledge_ratio
```

主键包含 `pledge_count` 等数据字段是不合理的，这些字段会随时间变化。应该只用 `ts_code` 和 `end_date` 作为主键。

## 修复方案

### 方案 1: 添加 period_field 配置 (推荐)

在 `app4/config/interfaces/pledge_stat.yaml` 中添加：

```yaml
pagination:
  enabled: true
  mode: period_range
  period_field: end_date  # 添加此行
  periods_per_batch: 1
  offset:
    enabled: true
    limit: 3000
```

### 方案 2: 修正主键配置

将主键简化为：

```yaml
output:
  primary_key:
    - ts_code
    - end_date
  sort_by:
    - end_date
    - ts_code
```

## 验证修复

修复后重新运行：
```bash
python app4/main.py --update --update-group period_range --interface pledge_stat
```

日志应该显示：
- 下载请求包含正确的 `end_date` 参数
- 覆盖率检测正确识别已存在的 period
- 去重后有有效数据输出
