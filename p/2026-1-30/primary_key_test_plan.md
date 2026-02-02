# Primary Key有效性验证测试方案

## 1. 测试目标

验证以下16个接口的YAML配置中，`primary_key`是否能唯一标识记录：

```
balancesheet_vip, cashflow_vip, disclosure_date, dividend, express_vip,
fina_audit, fina_indicator_vip, fina_mainbz_vip, forecast_vip, income_vip,
pledge_detail, pledge_stat, stk_factor_pro, stk_rewards, top10_floatholders, top10_holders
```

**核心原则**：
- 不预设任何特定字段作为检查目标（如 update_flag）
- 对**所有非主键字段**进行全面检查
- 只要存在任何字段在重复组内有不同值，就说明 primary key 不完整

## 2. 核心问题

如果primary key定义不完整，会导致：
- 实际上不同的记录被错误去重
- 数据丢失且生产环境无法发现

**关键点**：
- 不能预设任何特定字段作为检查目标（如 update_flag）
- 必须对**所有非主键字段**进行全面检查
- 任何非主键字段在重复组内有不同值，都说明 primary key 不完整

## 3. 测试方法

### 3.1 原理

```
下载数据 → 按primary key分组 → 检查组内非主键字段是否一致
```

### 3.2 判定标准

| 情况 | 非主键字段 | 结论 |
|------|-----------|------|
| A | 完全相同 | 正常重复，可安全去重 |
| B | 存在差异 | **问题！** primary key定义不完整 |

### 3.3 示例

**问题示例**（balancesheet_vip）：

YAML配置：
```yaml
primary_key: [ts_code, ann_date, end_date]
```

实际数据：
| ts_code | ann_date | end_date | update_flag | report_type | total_assets |
|---------|----------|----------|-------------|-------------|--------------|
| 000001.SZ | 20240315 | 20231231 | 1 | A | 1000000 |
| 000001.SZ | 20240315 | 20231231 | 2 | A | 1000500 |
| 000001.SZ | 20240315 | 20231231 | 1 | B | 1000000 |

**全面检查结果**：
- `update_flag` 有不同值：[1, 2]
- `report_type` 有不同值：[A, B]
- `total_assets` 有不同值：[1000000, 1000500]

分析：**多个字段**在相同的 primary key 下有不同值，说明 primary_key 定义不完整。可能需要添加 `update_flag` 和 `report_type`，或者重新设计主键策略。

## 4. 数据获取策略

复用项目现有代码：

```python
from app4.core.config_loader import ConfigLoader
from app4.core.downloader import GenericDownloader

config_loader = ConfigLoader('/home/quan/testdata/aspipe_v4/app4/config')
downloader = GenericDownloader(config_loader)
```

| 接口模式 | 获取策略 |
|---------|---------|
| stock_loop | 前100只股票的全部历史数据 |
| date_range | 最近365天数据 |
| offset | 前10000条数据 |

## 5. 检测逻辑

```python
def test_primary_key_comprehensive(df, primary_key):
    """
    全面检查 primary key 的有效性

    检查所有非主键字段，不只是预设的某些字段
    """
    import pandas as pd

    # 1. 找出重复组（primary key 相同的记录）
    dup_counts = df.groupby(primary_key).size().reset_index(name='count')
    dup_groups = dup_counts[dup_counts['count'] > 1]

    all_issues = []
    non_key_fields = [f for f in df.columns if f not in primary_key]

    # 2. 检查每个重复组的所有非主键字段
    for _, group_info in dup_groups.iterrows():
        # 构建过滤条件，找到该 primary key 对应的所有记录
        mask = pd.Series(True, index=df.index)
        for pk_field in primary_key:
            mask = mask & (df[pk_field] == group_info[pk_field])

        group = df[mask]

        # 3. 检查所有非主键字段
        conflicts = []
        for field in non_key_fields:
            # 获取唯一值（排除NaN）
            unique_values = group[field].dropna().unique()

            # 如果有多个不同值，说明该字段导致数据不同
            if len(unique_values) > 1:
                conflicts.append({
                    'field': field,
                    'values': list(unique_values[:10])  # 限制显示数量
                })

        # 4. 如果有任何字段存在冲突，记录问题
        if conflicts:
            all_issues.append({
                'primary_key_value': {pk: group_info[pk] for pk in primary_key},
                'record_count': len(group),
                'conflict_fields': conflicts
            })

    return all_issues
```

## 6. 预期问题接口

**重要**：本测试方案不预设任何特定字段的问题，而是通过全面检查所有非主键字段来发现问题。

基于代码审查，以下接口的 primary key 定义可能需要验证：

| 接口 | 当前primary key | 备注 |
|------|----------------|------|
| balancesheet_vip | ts_code, ann_date, end_date | 可能缺少 update_flag 等字段 |
| cashflow_vip | ts_code, ann_date, end_date | 可能缺少 update_flag 等字段 |
| income_vip | ts_code, ann_date, end_date, update_flag | 已包含 update_flag |
| disclosure_date | ts_code, end_date | 可能缺少 ann_date 等字段 |
| fina_indicator_vip | ts_code, ann_date, end_date | 可能缺少 update_flag 等字段 |

**注意**：上述仅为基于经验的猜测，实际需要通过测试来确认哪些字段导致数据不重复。

## 7. 输出格式

```json
{
  "interface": "balancesheet_vip",
  "primary_key": ["ts_code", "ann_date", "end_date"],
  "total_records": 5000,
  "duplicate_groups": 200,
  "problematic_groups": 50,
  "samples": [
    {
      "primary_key_value": {
        "ts_code": "000001.SZ",
        "ann_date": "20240315",
        "end_date": "20231231"
      },
      "record_count": 3,
      "conflict_fields": [
        {"field": "update_flag", "values": ["1", "2"]},
        {"field": "report_type", "values": ["A", "B"]},
        {"field": "total_assets", "values": [1000000, 1000500]}
      ]
    }
  ]
}
```

## 8. 执行步骤

1. 使用ConfigLoader加载配置（自动读取.env中的TUSHARE_TOKEN）
2. 使用GenericDownloader下载数据
3. 对每个接口执行primary key检测
4. 生成测试报告

## 9. 修复建议

对于发现问题的接口，根据测试结果分析需要添加的字段：

```yaml
# 示例1：如果只有 update_flag 导致冲突
output:
  primary_key:
    - ts_code
    - ann_date
    - end_date
    - update_flag

# 示例2：如果多个字段都导致冲突
output:
  primary_key:
    - ts_code
    - ann_date
    - end_date
    - update_flag
    - report_type
```

**修复原则**：
- 根据测试报告中 `conflict_fields` 列出的所有字段来决定是否添加到 primary key
- 需要分析业务逻辑，确认哪些字段组合能唯一标识一条记录
- 有时可能需要重新设计 primary key 的组合方式
