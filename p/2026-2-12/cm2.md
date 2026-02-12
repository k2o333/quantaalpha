# Stock Loop 智能增量下载方案 - 二次评估报告

**评估对象**: `/home/quan/testdata/aspipe_v4/p/2026-2-12/complete_solution.md`
**目标项目**: `app4/`
**评估日期**: 2026-02-12
**评估人**: Plan Agent

---

## 一、评估结论

| 评估维度 | 评分 | 说明 |
|---------|------|------|
| 架构兼容性 | 3.5/5 | 存在中等程度兼容性问题 |
| 方案完整性 | 5/5 | 代码实现完整，文档详尽 |
| 集成难度 | 2.5/5 | 需要较大改动，侵入性较强 |
| 向后兼容 | 4/5 | 有回退机制，但配置需全面修改 |
| **综合** | **3.5/5** | **有条件推荐，需修改后采用** |

---

## 二、与 app4 现有架构对比

### 2.1 现有模块与方案功能对照

| 现有模块 | 现有功能 | 方案新增功能 | 冲突程度 |
|---------|---------|-------------|---------|
| `CoverageManager` | 范围级覆盖率检测 | 股票级缺口检测 | ⚠️ 中等 |
| `DateCalculator` | 日期范围计算 | 日期参数模式识别 | ⚠️ 中等 |
| `PaginationComposer` | 股票循环处理 | 智能参数生成 | ⚠️ 中等 |
| `PaginationExecutor` | 分页执行 | 分页执行 | ✅ 兼容 |
| `StorageManager` | 数据读写 | 数据过滤读取 | ❌ 需修改 |

### 2.2 核心兼容性问题

#### 问题 1：StorageManager 接口不兼容（严重）

**方案代码（第 448-453 行）**：
```python
df = self.coverage_manager.storage_manager.read_interface_data(
    interface_name,
    filters={'ts_code': ts_code},  # ❌ 不支持
    columns=[date_column]
)
```

**现有接口（storage.py:365-400）**：
```python
def read_interface_data(
    self,
    interface_name: str,
    start_date: str = None,
    end_date: str = None,
    columns: Optional[List[str]] = None
) -> pl.DataFrame:
    # ❌ 不支持 filters 参数
```

**影响**：方案无法直接读取单只股票的数据，需修改 StorageManager 或在读取后过滤。

#### 问题 2：新增配置块与现有配置重复（中等）

**方案新增配置**：
```yaml
date_params:
  mode: "date_range"
  data_date_column: "trade_date"
  default_start_date: "20000101"
```

**现有配置（已存在）**：
```yaml
duplicate_detection:
  date_column: "trade_date"  # ✅ 已存在
```

**影响**：需要修改 40+ 个 YAML 配置文件，增加维护负担。

#### 问题 3：分页模式不匹配（中等）

| 接口 | 现有模式 | 方案目标模式 | 状态 |
|-----|---------|-------------|------|
| daily_basic | reverse_date_range | stock_loop | ❌ 冲突 |
| moneyflow | reverse_date_range | stock_loop | ❌ 冲突 |
| income_vip | stock_loop | stock_loop | ✅ 兼容 |

**影响**：方案核心功能（股票级增量下载）仅对 stock_loop 模式有效，但高频接口使用 reverse_date_range。

#### 问题 4：职责边界模糊（中等）

方案建议新增独立的 `StockLoopPlanner` 类，但 app4 倾向于：
- CoverageManager 负责覆盖率检测
- PaginationComposer 负责参数组合
- PaginationExecutor 负责执行

**影响**：新增模块与现有模块职责重叠，增加代码理解成本。

---

## 三、方案优点

### 3.1 核心价值

1. **参数模式识别**：自动识别 5 种接口参数模式（date_range、trade_date、period、date_anchor、none）
2. **精确缺口检测**：基于实际数据日期检测缺失，而非简单判断股票是否存在
3. **配置驱动**：通过 YAML 配置支持各种接口类型
4. **向后兼容**：有异常回退机制

### 3.2 代码质量

- 实现完整，包含边界处理
- 文档详尽，有配置示例
- 测试指导清晰

---

## 四、修改建议

### 4.1 推荐方案：扩展现有模块

**不**建议新增独立的 `StockLoopPlanner`，而是：

1. **扩展 CoverageManager**：
   - 添加 `get_stock_existing_dates()` 方法
   - 添加 `detect_stock_date_gaps()` 方法

2. **扩展 PaginationComposer**：
   - 在 `_apply_stock_loop()` 中集成缺口检测逻辑

3. **配置复用**：
   - 复用 `duplicate_detection` 配置块
   - 新增可选字段 `stock_level_detection: true`

### 4.2 具体修改步骤

#### 步骤 1：扩展 CoverageManager

在 `app4/core/coverage_manager.py` 中添加：

```python
def get_stock_existing_dates(
    self,
    interface_name: str,
    ts_code: str,
    date_column: str = 'trade_date'
) -> set:
    """获取指定股票已存在的所有日期"""
    try:
        df = self.storage_manager.read_interface_data(
            interface_name,
            columns=[date_column, 'ts_code']
        )
        if df.is_empty():
            return set()
        
        # 按股票代码过滤（适配现有接口）
        filtered = df.filter(pl.col('ts_code') == ts_code)
        if filtered.is_empty():
            return set()
        
        dates = set()
        for date_val in filtered[date_column]:
            formatted = format_date(date_val)
            if formatted:
                dates.add(formatted)
        return dates
    except Exception as e:
        logger.warning(f"获取现有日期失败: {e}")
        return set()

def detect_stock_date_gaps(
    self,
    interface_name: str,
    ts_code: str,
    start_date: str,
    end_date: str,
    date_column: str = 'trade_date'
) -> List[tuple]:
    """检测指定股票的日期缺口"""
    existing_dates = self.get_stock_existing_dates(
        interface_name, ts_code, date_column
    )
    
    trade_calendar = self.downloader.get_trade_calendar(start_date, end_date)
    if not trade_calendar:
        return [(start_date, end_date)]
    
    trade_days = [
        d['cal_date'] for d in trade_calendar 
        if d.get('is_open', 0) == 1
    ]
    
    missing_days = [d for d in trade_days if d not in existing_dates]
    if not missing_days:
        return []
    
    return self._merge_to_ranges(missing_days)
```

#### 步骤 2：修改 PaginationComposer

在 `app4/core/pagination.py` 的 `_apply_stock_loop()` 方法中：

```python
# 在现有逻辑基础上添加缺口检测
stock_level_detection = self.interface_config.get(
    'duplicate_detection', {}
).get('stock_level_detection', False)

if stock_level_detection and self.context.coverage_manager:
    gaps = self.context.coverage_manager.detect_stock_date_gaps(
        interface_name,
        ts_code,
        params.get('start_date', '20000101'),
        params.get('end_date', datetime.now().strftime('%Y%m%d')),
        date_column
    )
    if not gaps:
        continue  # 数据完整，跳过
    
    for gap_start, gap_end in gaps:
        gap_params = params.copy()
        gap_params['ts_code'] = ts_code
        gap_params['start_date'] = gap_start
        gap_params['end_date'] = gap_end
        yield gap_params
else:
    # 原有逻辑
    ...
```

#### 步骤 3：配置扩展（可选）

在接口 YAML 配置中添加可选字段：

```yaml
# daily_basic.yaml
duplicate_detection:
  enabled: true
  date_column: "trade_date"
  threshold: 0.95
  stock_level_detection: true  # 新增：启用股票级检测
  lookback_days: 7             # 新增：回溯天数
```

---

## 五、与 cb.md 和 cm.md 的对比

| 评估维度 | cb.md | cm.md | 本报告 (cm2.md) |
|---------|-------|-------|----------------|
| 综合评分 | 4.8/5 | 未评分 | 3.5/5 |
| 核心观点 | 强烈推荐 | 不推荐直接采用 | 有条件推荐 |
| 架构兼容 | ✅ 完美 | ❌ 冲突 | ⚠️ 需修改 |
| 配置影响 | ✅ 简单 | ❌ 40+文件 | ⚠️ 需简化 |
| 接口兼容 | ✅ 兼容 | ❌ 需修改 | ❌ 需修改 |
| 实现方式 | 新增模块 | 扩展现有 | 扩展现有 |

**本报告观点更接近 cm.md**，认为直接采用原方案存在较大侵入性，建议修改后采用。

---

## 六、实施建议

### 6.1 优先级

| 优先级 | 任务 | 工作量 | 风险 |
|-------|-----|-------|-----|
| P0 | 扩展 CoverageManager | 2h | 低 |
| P1 | 修改 PaginationComposer | 3h | 中 |
| P2 | 优化 StorageManager（可选）| 3h | 中 |
| P3 | 配置字段标准化 | 2h | 低 |

### 6.2 验收标准

- [ ] CoverageManager.get_stock_existing_dates() 正确返回股票已有日期
- [ ] CoverageManager.detect_stock_date_gaps() 正确检测缺口
- [ ] PaginationComposer 正确生成缺口参数
- [ ] 向后兼容：无 date_params 配置时行为不变
- [ ] 性能：无明显退化

---

## 七、总结

1. **complete_solution.md** 的核心思想（智能增量下载、精确缺口检测）是有价值的
2. 但直接采用存在 **4 个关键兼容性问题**，侵入性较强
3. **推荐方案**：在现有 CoverageManager 基础上扩展，而非新增独立模块
4. **配置设计**：复用 duplicate_detection，避免新增配置块

**最终建议**：以 cm.md 的修改建议为基础，采用"最小侵入式扩展"方案实施。

---
]]
