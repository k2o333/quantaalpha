---
doc_type: change
module: app4
status: archived
owner: quan
created: 2026-03-02
updated: 2026-03-02
summary: 去重逻辑简化方案
---

# 去重逻辑简化方案

## 背景

当前系统在多个层面实现了去重逻辑，存在冗余。本方案旨在简化去重流程，提升下载效率。

## 当前去重机制分析

### 1. 现有去重层级

| 层级 | 位置 | 作用 | 开销 |
|------|------|------|------|
| 下载前 | `CoverageManager.should_skip()` | 跳过已覆盖的日期/报告期 | 低（查询元数据） |
| 存储前 | `main.py:392` `process_data_with_dedup()` | 与已有数据去重 | 高（读取全量主键） |
| 存储时 | `storage.py:632` | 与已有数据去重 | 高（读取全量主键） |

### 2. 冗余分析

```
下载流程：

第一次下载（无 --update）：
  └── 全量下载，无需与已有数据去重（数据本就不存在）

后续下载（--update）：
  ├── CoverageManager.should_skip() → 跳过已覆盖数据
  └── 存储前去重 → 几乎不会遇到重复数据
```

### 3. 两种下载模式的重复概率

**reverse_date_range 模式**：
- 每个日期锚点只遍历一次
- `--update` 模式通过 CoverageManager 检测已下载日期
- 重复概率：极低

**period_range 模式**：
- 每个报告期只遍历一次
- `--update` 模式检测已存在的报告期
- 重复概率：极低

## 简化方案

### 核心思路

1. **保留**：批次内去重（防御性措施）
2. **移除**：与已有数据的去重（依赖 CoverageManager + 存储层主键约束）

### 方案优势

| 优势 | 说明 |
|------|------|
| 减少IO | 不需要每次下载都读取已有数据的主键列 |
| 提升速度 | 省去除临时文件和数据比对的开销 |
| 内存友好 | 避免加载大量主键数据到内存 |
| 逻辑清晰 | 单一职责，CoverageManager 负责跳过，存储层负责去重 |

### 需要修改的代码

#### 1. main.py（约第 375 行）

```python
# 修改前
if dedup_config.get('dedup_enabled', True) and primary_keys:
    # 读取已有数据去重...

# 修改后
if False:  # 禁用与已有数据的去重
    ...
```

或者通过配置控制：

```yaml
# 接口配置文件
dedup:
  dedup_enabled: false  # 禁用与已有数据去重
  batch_dedup: true     # 保留批次内去重
```

#### 2. storage.py（约第 618 行）

```python
# 修改前
if dedup_config.get('dedup_enabled', True) and primary_keys:
    # 读取已有数据去重...

# 修改后
if False:  # 禁用与已有数据的去重
    ...
```

### 保留的保护机制

1. **CoverageManager**：`--update` 模式下的覆盖率检测
2. **存储层主键约束**：Parquet 数据集按主键分区或去重写入
3. **批次内去重**：同一次下载循环中的重复数据过滤

## 后置去重方案（可选）

如果担心极端情况下的重复数据，可以在下载完成后统一执行去重：

```bash
# 示例：按主键去重 parquet 文件
python scripts/dedup_all_data.py --interface income_vip
```

## 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| CoverageManager 失效导致重复下载 | 低 | 中 | 存储层主键去重 |
| 配置错误导致重复参数 | 低 | 低 | 保留批次内去重 |
| 数据质量问题 | 低 | 低 | 后置去重脚本 |

## 实施建议

1. **先测试**：在小规模接口上禁用去重，观察是否有重复数据
2. **保留开关**：通过配置项控制，而非硬编码移除
3. **监控日志**：观察 `dedup_rate` 指标，确认去重率确实很低

## 总结

当前的去重机制在 `--update` 模式下是冗余的，移除与已有数据的去重逻辑可以显著提升下载效率，同时通过 CoverageManager 和存储层保护机制确保数据完整性。
