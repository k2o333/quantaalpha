# 空查询重复请求问题 - 方案讨论记录

## 一、问题描述

### 现象
用户执行 `dividend` 接口的增量更新时发现：

```
第一次运行：
- 请求全部 30 个交易日
- 其中 18 天有数据返回，12 天返回 0 条记录

第二次运行：
- detect_gaps() 检测到 12 天"缺口"
- 重复请求这 12 天（全部返回 0 条）
```

### 根本原因
`coverage_manager.py` 的 `detect_gaps()` 方法只检查"已有数据的日期"：

```python
existing_dates = self._get_existing_dates_cached(interface_name)
missing_dates = expected_dates - existing_dates
```

`existing_dates` 只包含有数据的日期，**不包含"已查询但返回0条"的日期**。

### 影响范围

| 分页模式 | 场景 | 问题 |
|---------|------|------|
| `reverse_date_range` | 按日期窗口请求 | 空窗口重复请求 |
| `is_date_anchor` | 按日期锚点请求 | 空日期重复请求 |
| `period_range` | 按报告期请求 | 空报告期重复请求 |
| `stock_loop` | 按股票+日期请求 | 空组合重复请求 |

---

## 二、方案讨论

### 方案 1：完整查询历史记录（原方案）

**思路**：记录所有已执行的查询，无论是否有数据返回

**数据格式**：
```json
{
  "interface_name": "dividend",
  "records": {
    "date:20260112": {
      "query_type": "date",
      "date_value": "20260112",
      "queried_at": "2026-02-25T16:13:35",
      "result_count": 0
    },
    "anchor:ann_date:20260112": {...},
    "period:end_date:20260331": {...}
  }
}
```

**优点**：
- 信息完整，便于调试
- 支持所有模式

**缺点**：
- 存储较大
- 每次请求都写文件（性能问题）
- 缺少过期机制

---

### 方案 2：只记录空查询（推荐方案）

**思路**：只记录返回 0 条的查询，有数据的查询不需要记录

**数据格式**：
```json
{
  "anchor:ann_date:20260112": "2026-02-25T16:13:35",
  "date:20260114": "2026-02-25T16:13:36",
  "period:end_date:20260331": "2026-02-25T16:13:00"
}
```

**查询键格式**：

| 场景 | 查询键格式 | 示例 |
|-----|-----------|------|
| 日期锚点 | `anchor:{param}:{value}` | `anchor:ann_date:20260112` |
| 单日期 | `date:{date}` | `date:20260114` |
| 报告期 | `period:{field}:{value}` | `period:end_date:20260331` |
| 股票+日期 | `stock_date:{ts_code}:{date}` | `stock_date:000001.SZ:20260112` |
| 股票+报告期 | `stock_period:{ts_code}:{period}` | `stock_period:000001.SZ:20260331` |

**优点**：
- 存储小（只记录空查询）
- 支持过期检查（值是时间戳）
- 支持所有模式（保留查询键格式）

**缺点**：
- 需要处理日期展开（date_range）

---

### 方案 3：写入占位记录

**思路**：在 parquet 文件中写入占位记录

```
已下载但无数据 → 写入占位记录（如 n/a）
未下载 → 空值/无记录
```

**问题**：

1. **不知道该写入哪些记录**

```python
# API 返回空列表
result = []  # 没有任何记录

# 问题：应该写入什么？
# 我们不知道 5000 只股票中哪些应该标记为 n/a
```

2. **主键不完整**

`dividend` 的主键是 `(ts_code, end_date, ann_date, div_proc)`：
- 我们有 `ann_date=20260112`
- 但不知道 `ts_code`、`end_date`、`div_proc` 是什么

3. **存储膨胀**

如果每天写入 5000 只股票的占位记录：
- 30 天 × 5000 股 = 150,000 条空记录
- 数据文件变大，查询变慢

**结论**：❌ 不可行

---

### 方案 4：极简标记（讨论中）

**思路**：只用日期作为键，值固定为 1

```json
{
  "20260112": 1,
  "20260114": 1,
  "20260119": 1
}
```

**问题**：
- `period_range` 模式的空查询无法记录（报告期不是日期）
- `stock_loop` 模式会误判（A股票查过，B股票没查）

**改进**：保留查询键格式，但只记录空查询

```json
{
  "anchor:ann_date:20260112": "2026-02-25T16:13:35",
  "date:20260114": "2026-02-25T16:13:36"
}
```

**结论**：✅ 可行，等同于方案 2

---

## 三、一致性问题

### 问题场景

```
1. 用户下载 dividend 数据，部分日期返回 0 条
2. .query_history.json 记录了这些日期
3. 用户删除 data/dividend/*.parquet 文件
4. 用户再次运行程序
5. detect_gaps() 读取 .query_history.json，认为日期已查询
6. 跳过下载，但实际数据已丢失！
```

### 解决方案

#### 方案 A：数据文件校验（推荐）

启动时检查数据目录是否为空：

```python
def _validate_data_consistency(self, interface_name: str) -> None:
    data_dir = self.data_dir / interface_name
    parquet_files = list(data_dir.glob("*.parquet"))
    
    if not parquet_files:
        # 数据文件不存在，清空查询历史
        if self.query_history_manager:
            self.query_history_manager.clear_history(interface_name)
            logger.info(f"数据文件不存在，已清空查询历史: {interface_name}")
```

#### 方案 B：手动同步命令

```bash
# 清空指定接口的查询历史（重新下载）
python app4/main.py --reset-query-history --interface dividend

# 强制重新下载
python app4/main.py --update --interface dividend --force
```

#### 方案 C：校验和绑定

在 `.query_history.json` 中记录数据文件信息：

```json
{
  "interface_name": "dividend",
  "data_checksum": "abc123",
  "records": {...}
}
```

**推荐**：方案 A + 方案 B 结合

---

## 四、方案对比

| 对比项 | 方案1：完整记录 | 方案2：只记录空查询 | 方案3：占位记录 |
|--------|----------------|-------------------|----------------|
| 存储大小 | 大 | 小 | 很大 |
| 实现复杂度 | 中 | 低 | 高 |
| 过期检查 | 支持 | 支持 | 不支持 |
| 数据一致性 | 需处理 | 需处理 | 自动一致 |
| 可行性 | ✅ | ✅ | ❌ |

---

## 五、最终结论

**采用方案 2：只记录空查询**

数据格式：
```json
{
  "anchor:ann_date:20260112": "2026-02-25T16:13:35",
  "date:20260114": "2026-02-25T16:13:36",
  "period:end_date:20260331": "2026-02-25T16:13:00",
  "stock_date:000001.SZ:20260112": "2026-02-25T16:13:37"
}
```

特性：
- 只记录返回 0 条的查询
- 值为查询时间戳（支持 TTL 过期检查）
- 保留查询键格式（支持所有模式）
- 批量写入优化
- 数据文件校验（一致性保障）

---

## 六、相关文档

- [查询历史记录方案](./query-history-tracking-solution.md) - 完整实施方案
- [方案评审报告](./query-history-tracking-review.md) - 评审意见
- [最终简化方案](./empty-query-tracker-final.md) - 简化版实现
