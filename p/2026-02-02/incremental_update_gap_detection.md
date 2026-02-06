# 增量更新缺口检测功能需求文档

## 文档信息
- 创建日期: 2026-02-06
- 更新日期: 2026-02-06
- 需求类型: 功能改进
- 影响范围: app4/update 模块
- 触发条件: `main.py --update` 参数
- 综合评分: 7.5/10

---

## 1. 背景与问题

### 1.1 当前行为
目前 `--update` 模式的逻辑是：
- **覆盖率高** → 跳过整个日期范围
- **覆盖率低** → 下载整个日期范围

### 1.2 存在的问题
这种"全有或全无"的方式效率低下：
- 即使只缺失几天数据，也会重新下载整个大范围
- 浪费 API 调用次数和网络带宽
- 增加数据重复处理的开销

### 1.3 期望行为
实现精细化增量更新：
- **检测已有数据中的缺失日期段（gaps）**
- **只下载那些缺失的部分**

---

## 2. 功能需求

### 2.1 核心需求

当使用 `python app4/main.py --update` 时：

1. **缺口检测**
   - 读取目标日期范围内已有数据的日期列表
   - 对比期望的交易日历，识别缺失的日期
   - 将连续的缺失日期合并为"缺口段"

2. **分段下载**
   - 对每个缺口段执行独立下载
   - 保持原有的分页逻辑（window_size_days 等）
   - 合并所有下载结果

3. **数据合并**
   - 新下载数据与已有数据合并
   - 处理重复数据（去重）
   - 保存最终结果

### 2.2 边界条件

| 场景 | 处理方式 |
|------|----------|
| 完全无数据 | 下载整个范围 |
| 完全有数据 | 跳过该接口 |
| 部分缺失（连续） | 下载缺失段 |
| 部分缺失（分散） | 下载多个缺失段 |
| 缺失段很小（<1天） | 按最小窗口下载 |

---

## 3. 技术方案（改进版）

### 3.1 架构调整

**原方案问题**: `GapDetector` 与 `CoverageManager` 职责重叠

**改进方案**: 将缺口检测功能整合到 `CoverageManager`，避免重复代码

```
┌─────────────────────────────────────────────────────────────┐
│                     CoverageManager                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ should_skip  │  │ detect_gaps  │  │ get_coverage_status│  │
│  │  (原有)      │  │  (新增)      │  │    (原有)        │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │           _existing_dates_cache (LRU缓存)             │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    UpdateManager                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              update_interface()                      │  │
│  │  1. 获取目标日期范围                                  │  │
│  │  2. 调用 coverage_manager.detect_gaps()              │  │
│  │  3. 如果有缺口，逐个下载                              │  │
│  │  4. 合并并保存结果                                    │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 文件结构

```
app4/core/
├── coverage_manager.py    # 新增 detect_gaps() 方法，整合缺口检测
└── gap_detector.py        # 删除：功能合并到 CoverageManager

app4/update/
├── update_manager.py      # 修改 update_interface() 和 _execute_download()
├── update_options.py      # 添加 gap_detection 配置
└── date_calculator.py     # 可选：支持缺口段作为输入
```

### 3.3 关键组件

#### 3.3.1 CoverageManager 扩展（改进）

```python
class CoverageManager:
    """扩展 CoverageManager，整合缺口检测功能"""

    def __init__(self, storage_manager, cache_size=128):
        # 新增：已有日期缓存
        self._existing_dates_cache = {}
        self._cache_size = cache_size

    def detect_gaps(
        self,
        interface_name: str,
        target_range: DateRange,
        trade_calendar: List[str],
        min_gap_days: int = 1
    ) -> List[DateRange]:
        """
        检测缺失的日期段

        Args:
            interface_name: 接口名称
            target_range: 目标日期范围
            trade_calendar: 交易日历列表
            min_gap_days: 最小缺口天数（小于此值的缺口忽略）

        Returns:
            List[DateRange]: 缺失的日期段列表
        """
        # 1. 获取已有日期（带缓存）
        existing_dates = self._get_existing_dates_cached(interface_name)

        # 2. 计算期望日期集合
        expected = set(d for d in trade_calendar
                      if target_range.start_date <= d <= target_range.end_date)

        # 3. 找出缺失日期
        missing = expected - existing_dates

        if not missing:
            return []

        # 4. 合并连续缺失日期为段
        gaps = self._merge_continuous_dates(sorted(missing), min_gap_days)

        return gaps

    def _get_existing_dates_cached(self, interface_name: str) -> Set[str]:
        """获取已有日期（带LRU缓存）"""
        if interface_name in self._existing_dates_cache:
            return self._existing_dates_cache[interface_name]

        dates = self._get_existing_dates_from_storage(interface_name)

        # 简单LRU：缓存大小限制
        if len(self._existing_dates_cache) >= self._cache_size:
            self._existing_dates_cache.pop(next(iter(self._existing_dates_cache)))

        self._existing_dates_cache[interface_name] = dates
        return dates

    def _merge_continuous_dates(
        self,
        sorted_dates: List[str],
        min_gap_days: int
    ) -> List[DateRange]:
        """将连续日期合并为段"""
        if not sorted_dates:
            return []

        gaps = []
        gap_start = sorted_dates[0]
        gap_end = sorted_dates[0]

        for date in sorted_dates[1:]:
            if self._is_next_trade_day(gap_end, date):
                gap_end = date
            else:
                # 保存当前段（如果满足最小天数）
                if self._days_between(gap_start, gap_end) >= min_gap_days:
                    gaps.append(DateRange(gap_start, gap_end))
                gap_start = date
                gap_end = date

        # 保存最后一个段
        if self._days_between(gap_start, gap_end) >= min_gap_days:
            gaps.append(DateRange(gap_start, gap_end))

        return gaps

    def clear_cache(self, interface_name: str = None):
        """清除缓存"""
        if interface_name:
            self._existing_dates_cache.pop(interface_name, None)
        else:
            self._existing_dates_cache.clear()
```

#### 3.3.2 UpdateManager 修改

```python
def update_interface(
    self,
    interface_name: str,
    options: UpdateOptions
) -> InterfaceUpdateResult:
    """更新单个接口（支持缺口检测）"""

    # 1. 获取配置和日期范围
    interface_config = self.config_loader.get_interface_config(interface_name)
    date_range = self.date_calculator.calculate_update_range(...)

    # 2. 【新增】缺口检测
    if options.gap_detection_enabled and self.coverage_manager:
        gaps = self.coverage_manager.detect_gaps(
            interface_name=interface_name,
            target_range=date_range,
            trade_calendar=self.downloader.get_trade_calendar(...),
            min_gap_days=options.min_gap_days
        )

        if not gaps:
            logger.info(f"{interface_name}: 无缺失数据，跳过")
            return InterfaceUpdateResult(..., status=UpdateStatus.SKIPPED)

        logger.info(f"{interface_name}: 发现 {len(gaps)} 个缺失段")

        # 3. 【新增】逐个下载缺口
        total_records = 0
        for i, gap in enumerate(gaps):
            logger.info(f"下载缺口 [{i+1}/{len(gaps)}]: {gap}")
            records = self._execute_download(
                interface_name, interface_config, gap, options
            )
            total_records += records

        return InterfaceUpdateResult(..., record_count=total_records)

    # 4. 原有逻辑（缺口检测关闭时）
    else:
        return self._update_interface_legacy(interface_name, options)
```

### 3.4 修改点清单（改进版）

| 文件 | 修改内容 | 优先级 | 备注 |
|------|----------|--------|------|
| `app4/core/coverage_manager.py` | 新增 `detect_gaps()` 方法，添加日期缓存 | 高 | 整合原 GapDetector 功能 |
| `app4/update/update_manager.py` | 修改 `update_interface()` 支持缺口检测 | 高 | 保持向后兼容 |
| `app4/update/models.py` | 添加 `UpdateOptions.gap_detection_enabled` | 高 | 配置开关 |
| `app4/core/storage_manager.py` | 优化 `get_existing_dates()` 性能 | 中 | 添加索引支持 |
| `app4/update/date_calculator.py` | 支持缺口段列表作为输入 | 低 | Phase 2 实现 |

---

## 4. 详细设计

### 4.1 缺口检测算法（改进版）

```python
def detect_gaps(
    self,
    interface_name: str,
    target_range: DateRange,
    trade_calendar: List[str],
    min_gap_days: int = 1,
    max_gaps: int = 50
) -> List[DateRange]:
    """
    改进点：
    1. 使用缓存避免重复读取
    2. 支持最小缺口过滤
    3. 限制最大缺口数量（过多时合并）
    """
    # 1. 获取已有日期（带缓存）
    existing_dates = self._get_existing_dates_cached(interface_name)

    # 2. 计算期望日期集合
    expected = set(d for d in trade_calendar
                  if target_range.start_date <= d <= target_range.end_date)

    # 3. 快速路径：完全覆盖或完全缺失
    if existing_dates >= expected:
        return []  # 完全覆盖
    if not existing_dates:
        return [target_range]  # 完全缺失

    # 4. 找出缺失日期
    missing = expected - existing_dates

    # 5. 合并连续日期
    gaps = self._merge_continuous_dates(sorted(missing), min_gap_days)

    # 6. 如果缺口太多，合并为大范围
    if len(gaps) > max_gaps:
        logger.warning(f"缺口数量({len(gaps)})超过限制，合并为大范围下载")
        return [target_range]

    return gaps
```

### 4.2 多模式支持规划

#### 支持缺口检测的模式（有时间维度）

| 模式 | Phase 1 (MVP) | Phase 2 | Phase 3 | 说明 |
|------|---------------|---------|---------|------|
| `date_range` | ✅ 支持 | ✅ 优化 | ✅ 完善 | 按日期范围分批 |
| `reverse_date_range` | ✅ 支持 | ✅ 优化 | ✅ 完善 | 反向日期分批 |
| `period_range` | ❌ 不支持 | ✅ 支持 | ✅ 完善 | 按季度/月份分批 |
| `stock_loop` | ❌ 不支持 | ❌ 不支持 | ✅ 支持 | 按股票代码循环（需按股票检测缺失） |

#### 不支持缺口检测的模式（无时间维度）

| 模式 | 支持状态 | 原因 |
|------|----------|------|
| `offset` | ❌ 不支持 | 基于偏移量分页，无时间维度，无法定义"缺口" |
| `type_split` | ❌ 不支持 | 按类型字段分割（如 HK_SZ/SZ_HK），是分类维度而非时间维度 |

**说明**：
- `offset` 模式：通过 `limit/offset` 参数分页，每次请求指定数量的记录，不涉及日期范围，因此无法检测"哪些日期缺失"
- `type_split` 模式：将请求按类型字段（如市场类型）拆分为多个子请求，每个类型是独立的查询，没有时间连续性概念

### 4.3 数据合并策略（改进版）

```python
def merge_with_existing(
    self,
    interface_name: str,
    new_data_df: pl.DataFrame,
    chunk_size: int = 100000
):
    """
    改进点：
    1. 分块处理防止内存溢出
    2. 支持分区写入
    3. 保留 _update_time 字段
    """
    # 1. 获取主键配置
    primary_keys = self._get_primary_keys(interface_name)

    # 2. 添加更新时间戳
    new_data_df = new_data_df.with_columns([
        pl.lit(datetime.now().isoformat()).alias('_update_time')
    ])

    # 3. 检查数据大小，决定处理方式
    if len(new_data_df) < chunk_size:
        # 小数据量：直接合并
        return self._merge_small_data(interface_name, new_data_df, primary_keys)
    else:
        # 大数据量：分块合并
        return self._merge_large_data(interface_name, new_data_df, primary_keys, chunk_size)

def _merge_small_data(self, interface_name, new_df, primary_keys):
    """小数据量合并（内存中）"""
    existing_df = self.storage.read_interface_data(interface_name)

    # 合并并去重（保留新数据）
    combined = pl.concat([existing_df, new_df])
    deduplicated = combined.unique(subset=primary_keys, keep='last')

    # 覆盖写入
    self.storage.write_interface_data(
        interface_name, deduplicated, mode='overwrite'
    )

def _merge_large_data(self, interface_name, new_df, primary_keys, chunk_size):
    """大数据量合并（分块处理）"""
    # 1. 按日期分区保存新数据到临时目录
    temp_dir = f"data/{interface_name}/temp_{int(time.time())}"
    self._write_partitioned(new_df, temp_dir, chunk_size)

    # 2. 逐分区合并
    for partition in os.listdir(temp_dir):
        self._merge_partition(interface_name, partition, primary_keys)

    # 3. 清理临时文件
    shutil.rmtree(temp_dir)
```

---

## 5. 配置选项（改进版）

### 5.1 配置优先级

```
命令行参数 > 接口配置 > 全局配置 > 默认值
```

### 5.2 全局配置（update.yaml）

```yaml
update:
  # 缺口检测主开关
  gap_detection:
    enabled: true           # 默认启用
    min_gap_days: 1         # 最小缺口天数
    max_gaps: 50            # 最大缺口数量（超过则全量下载）
    gap_merge_threshold: 3  # 缺口合并阈值（间隔小于此天数合并）
    cache_size: 128         # 日期缓存大小（接口数）
```

### 5.3 接口配置（report_rc.yaml）

```yaml
# 接口级配置可覆盖全局配置
pagination:
  mode: reverse_date_range
  window_size_days: 1

  # 缺口检测接口级配置
  gap_detection:
    enabled: true
    min_gap_days: 1
```

### 5.4 命令行参数

```bash
# 启用缺口检测（默认）
python app4/main.py --update --interface report_rc

# 禁用缺口检测（回退到旧逻辑）
python app4/main.py --update --interface report_rc --no-gap-detection

# 强制完整下载（忽略已有数据）
python app4/main.py --update --interface report_rc --force-full

# 指定最小缺口天数
python app4/main.py --update --interface report_rc --min-gap-days 3
```

---

## 6. 日志输出示例

### 6.1 发现多个缺口

```
2026-02-06 17:32:05,624 - update.update_manager - INFO - 开始更新 report_rc: 20250901 ~ 20260206
2026-02-06 17:32:05,700 - core.coverage_manager - INFO - 目标范围交易日: 85天
2026-02-06 17:32:05,750 - core.coverage_manager - INFO - 已有数据覆盖: 60天（缓存命中）
2026-02-06 17:32:05,800 - core.coverage_manager - INFO - 发现 3 个缺失段:
2026-02-06 17:32:05,801 - core.coverage_manager - INFO -   [1] 20250915 ~ 20250920 (6天)
2026-02-06 17:32:05,802 - core.coverage_manager - INFO -   [2] 20251001 ~ 20251007 (7天)
2026-02-06 17:32:05,803 - core.coverage_manager - INFO -   [3] 20260115 ~ 20260120 (6天)
2026-02-06 17:32:06,100 - update.update_manager - INFO - 下载缺口 [1/3]: 20250915 ~ 20250920
2026-02-06 17:32:08,200 - core.downloader - INFO - Downloaded 523 records for gap 1
2026-02-06 17:32:08,300 - update.update_manager - INFO - 下载缺口 [2/3]: 20251001 ~ 20251007
...
2026-02-06 17:32:40,000 - update.update_manager - INFO - 接口 report_rc 更新完成，共 20637 条记录
```

### 6.2 缓存命中

```
2026-02-06 17:35:10,100 - core.coverage_manager - INFO - report_rc: 从缓存读取已有日期（60天）
2026-02-06 17:35:10,150 - core.coverage_manager - INFO - 发现 1 个缺失段: 20260201 ~ 20260206
```

### 6.3 无缺口

```
2026-02-06 17:32:05,624 - update.update_manager - INFO - 开始更新 report_rc: 20250901 ~ 20260206
2026-02-06 17:32:05,700 - core.coverage_manager - INFO - 目标范围交易日: 85天
2026-02-06 17:32:05,750 - core.coverage_manager - INFO - 已有数据覆盖: 85天
2026-02-06 17:32:05,800 - core.coverage_manager - INFO - 数据已完整，无需下载
2026-02-06 17:32:05,801 - update.update_manager - INFO - 接口 report_rc 已是最新，跳过
```

---

## 7. 测试用例

### 7.1 单元测试

```python
class TestGapDetection:
    """缺口检测单元测试"""

    def test_no_gaps_complete_coverage(self):
        """完全覆盖，无缺口"""
        existing = {'20250901', '20250902', '20250903'}
        target = DateRange('20250901', '20250903')
        trade_calendar = ['20250901', '20250902', '20250903']

        gaps = self.coverage_manager.detect_gaps(
            'test', target, trade_calendar
        )
        assert gaps == []

    def test_single_gap(self):
        """单个缺口"""
        existing = {'20250901', '20250903'}
        target = DateRange('20250901', '20250903')
        trade_calendar = ['20250901', '20250902', '20250903']

        gaps = self.coverage_manager.detect_gaps(
            'test', target, trade_calendar
        )
        assert len(gaps) == 1
        assert gaps[0] == DateRange('20250902', '20250902')

    def test_multiple_gaps(self):
        """多个缺口"""
        existing = {'20250901', '20250905', '20250910'}
        target = DateRange('20250901', '20250910')
        trade_calendar = [f'2025090{i}' for i in range(1, 11)]

        gaps = self.coverage_manager.detect_gaps(
            'test', target, trade_calendar
        )
        assert len(gaps) == 2
        assert gaps[0] == DateRange('20250902', '20250904')
        assert gaps[1] == DateRange('20250906', '20250909')

    def test_min_gap_days_filter(self):
        """最小缺口天数过滤"""
        existing = {'20250901', '20250903', '20250905'}
        target = DateRange('20250901', '20250905')
        trade_calendar = ['20250901', '20250902', '20250903', '20250904', '20250905']

        # min_gap_days=2，过滤掉单日缺口
        gaps = self.coverage_manager.detect_gaps(
            'test', target, trade_calendar, min_gap_days=2
        )
        assert len(gaps) == 0  # 两个单日缺口都被过滤

    def test_cache_functionality(self):
        """缓存功能"""
        # 第一次调用，读取存储
        dates1 = self.coverage_manager._get_existing_dates_cached('test')

        # 第二次调用，使用缓存
        dates2 = self.coverage_manager._get_existing_dates_cached('test')

        # 验证缓存命中（没有再次读取存储）
        assert self.storage.read_interface_data.call_count == 1
```

### 7.2 集成测试

```python
def test_incremental_update_with_gaps():
    """增量更新集成测试"""
    # 1. 准备已有数据（2025-09-01 到 2025-09-10）
    seed_data('report_rc', '20250901', '20250910')

    # 2. 执行更新（目标 2025-09-01 到 2025-09-20）
    result = run_update(
        '--update',
        '--interface', 'report_rc',
        '--start_date', '20250901',
        '--end_date', '20250920'
    )

    # 3. 验证只下载了 2025-09-11 到 2025-09-20
    assert result.downloaded_ranges == [DateRange('20250911', '20250920')]
    assert result.total_records == expected_count

    # 4. 验证缓存生效
    assert 'report_rc' in coverage_manager._existing_dates_cache

def test_gap_detection_disabled():
    """禁用缺口检测时回退到旧逻辑"""
    seed_data('report_rc', '20250901', '20250910')

    result = run_update(
        '--update',
        '--interface', 'report_rc',
        '--start_date', '20250901',
        '--end_date', '20250920',
        '--no-gap-detection'
    )

    # 验证下载了整个范围
    assert result.downloaded_ranges == [DateRange('20250901', '20250920')]
```

---

## 8. 风险评估（改进版）

| 风险 | 影响 | 缓解措施 | 状态 |
|------|------|----------|------|
| 缺口检测性能差 | 大 | 使用LRU缓存已有日期 | 已解决 |
| 大量小缺口导致频繁API调用 | 中 | 设置min_gap_days，合并小缺口 | 已解决 |
| 数据合并时内存不足 | 中 | 分块处理，分区写入 | 已解决 |
| 时区/日期格式问题 | 小 | 统一使用YYYYMMDD格式 | 已规避 |
| 缓存数据不一致 | 中 | 提供clear_cache接口，支持强制刷新 | 已规划 |
| 多模式支持复杂 | 中 | 分Phase实现，MVP只支持date_range | 已规划 |
| offset/type_split误启用 | 小 | 通过time_range.enabled判断，自动跳过 | 已规避 |

---

## 9. 实施计划（改进版）

### Phase 1: MVP（2-3天）
**目标**: 支持 `date_range` 和 `reverse_date_range` 模式的基础缺口检测

**支持范围**：
- ✅ `date_range` / `reverse_date_range`：支持缺口检测
- ❌ `offset` / `type_split`：不涉及日期维度，保持原有逻辑

**实现步骤**：

1. **CoverageManager 扩展**
   - [ ] 添加 `detect_gaps()` 方法（仅对 time_range 模式生效）
   - [ ] 实现 LRU 日期缓存
   - [ ] 添加 `clear_cache()` 方法

2. **UpdateManager 修改**
   - [ ] 修改 `update_interface()` 支持缺口检测
   - [ ] 添加配置读取逻辑（检测 `pagination.time_range.enabled`）
   - [ ] 添加日志输出

3. **配置支持**
   - [ ] 添加 `UpdateOptions.gap_detection_enabled`
   - [ ] 支持全局配置和命令行参数

4. **测试**
   - [ ] 单元测试（GapDetector逻辑）
   - [ ] 集成测试（端到端流程）

### Phase 2: 扩展支持（3-5天）
**目标**: 支持 `period_range` 模式，优化性能

1. **多模式支持**
   - [ ] 支持 `period_range` 模式（季度缺口检测）
   - [ ] 支持 `periodic_range` 模式

2. **性能优化**
   - [ ] StorageManager 添加日期索引
   - [ ] 优化大数据量合并性能

3. **配置完善**
   - [ ] 接口级配置支持
   - [ ] 配置优先级实现

### Phase 3: 高级功能（5-7天）
**目标**: 支持 `stock_loop` 模式，完善功能

1. **股票循环模式**
   - [ ] 支持 `stock_loop` 缺口检测
   - [ ] 按股票代码检测缺失

2. **数据合并优化**
   - [ ] 分区写入支持
   - [ ] 增量合并（只合并变化的分区）

3. **监控与调试**
   - [ ] 添加详细统计信息
   - [ ] 缺口检测报告

---

## 10. 附录

### 10.1 相关文件

| 文件 | 说明 | 修改类型 |
|------|------|----------|
| `/home/quan/testdata/aspipe_v4/app4/core/coverage_manager.py` | 覆盖管理器 | 扩展 |
| `/home/quan/testdata/aspipe_v4/app4/update/update_manager.py` | 更新管理器 | 修改 |
| `/home/quan/testdata/aspipe_v4/app4/update/models.py` | 数据模型 | 扩展 |
| `/home/quan/testdata/aspipe_v4/app4/core/storage_manager.py` | 存储管理器 | 优化 |
| `/home/quan/testdata/aspipe_v4/app4/config/update.yaml` | 全局配置 | 新增 |

### 10.2 待办事项

#### Phase 1 (MVP)
- [ ] CoverageManager 添加 detect_gaps() 方法
- [ ] CoverageManager 添加日期缓存
- [ ] UpdateManager 修改 update_interface() 逻辑
- [ ] 添加 UpdateOptions.gap_detection_enabled
- [ ] 编写单元测试
- [ ] 编写集成测试
- [ ] 手动测试验证

#### Phase 2
- [ ] 支持 period_range 模式
- [ ] StorageManager 性能优化
- [ ] 接口级配置支持

#### Phase 3
- [ ] 支持 stock_loop 模式
- [ ] 分区写入支持
- [ ] 完善文档

### 10.3 改进记录

| 日期 | 改进内容 | 原因 |
|------|----------|------|
| 2026-02-06 | 整合 GapDetector 到 CoverageManager | 避免职责重叠 |
| 2026-02-06 | 添加 LRU 缓存设计 | 提升性能 |
| 2026-02-06 | 分块合并策略 | 防止内存溢出 |
| 2026-02-06 | 明确多模式支持路线图 | 分阶段降低复杂度 |
| 2026-02-06 | 配置优先级设计 | 提升灵活性 |

---

## 11. 评审意见

### 11.1 原方案问题
1. ✅ **职责重叠**: GapDetector 与 CoverageManager 功能重复
2. ✅ **算法局限**: 仅支持 date_range 模式
3. ✅ **性能问题**: 缺少缓存设计
4. ✅ **合并策略**: 缺少分块处理

### 11.2 改进方案优势
1. ✅ **架构清晰**: 整合到 CoverageManager，职责单一
2. ✅ **性能优化**: LRU 缓存避免重复读取
3. ✅ **可扩展**: 分 Phase 支持多模式
4. ✅ **健壮性**: 分块合并防止内存溢出
5. ✅ **灵活性**: 配置优先级支持

### 11.3 推荐实施顺序
1. **Phase 1 (MVP)**: 先验证核心逻辑可行性
2. **POC 验证**: 选择 1-2 个接口进行测试
3. **代码审查**: 确保向后兼容
4. **合并主干**: 通过测试后合并

---

*文档结束*
