# CoverageManager 增强方案

> **目标**: 基于现有 CoverageManager 实现，优化智能重复检测，支持增量下载

**评估结论**: 项目已具备完善的覆盖率管理功能，建议增强而非重写

---

## 现状分析

### 现有优势（已具备）

1. **策略模式实现完整**
   - `date_range`: 日期范围覆盖检测（带阈值）
   - `period`: 报告期存在性检测
   - `stock`: 股票代码存在性检测
   - `auto`: 自动识别策略

2. **深度集成架构**
   - 在 `GenericDownloader` 各分页方法内嵌检测
   - `_execute_date_range_pagination` (313行)
   - `_execute_stock_loop_pagination` (945行)
   - `_execute_period_range_pagination` (637行)

3. **高级特性支持**
   - 线程安全缓存 (`threading.RLock`)
   - 交易日历集成 (`downloader.get_trade_calendar()`)
   - 覆盖率阈值配置 (0.95)
   - 性能监控与告警
   - 三级缓存策略（内存 → 本地 → API）

4. **生产级健壮性**
   - Fail-safe 机制（检测失败时继续下载）
   - 完整的日志记录
   - 异常捕获与处理

### 现存问题

1. **范围计算功能缺失**
   - 只能判断"是否覆盖"，无法计算"缺失哪些范围"
   - 不支持增量下载，要么全跳过要么全下载

2. **文件名过滤可优化**
   - `storage.py:246-256` 的过滤逻辑较简单
   - 无法处理复杂场景（如跨年窗口）

3. **Dataset 模式效率**
   - 检测时可能读取过多无关文件
   - 缺乏精细的索引机制

---

## 增强方案

### Task 1: 添加增量范围计算功能

**文件**: `app4/core/coverage_manager.py`

**目标**: 在现有 `CoverageManager` 中添加计算缺失范围的方法

**实现步骤**:

```python
# 在 CoverageManager 类中添加新方法

def calculate_missing_date_ranges(
    self,
    interface_name: str,
    start_date: str,
    end_date: str,
    **params
) -> List[Tuple[str, str]]:
    """
    计算需要下载的缺失日期范围

    Returns:
        List of (start_date, end_date) 元组，空列表表示无需下载
    """
    # 1. 获取现有日期范围（利用现有 _check_range_coverage 的逻辑）
    # 2. 结合交易日历计算缺失范围
    # 3. 返回缺失范围列表
    pass

def calculate_missing_periods(
    self,
    interface_name: str,
    start_date: str,
    end_date: str,
    **params
) -> List[str]:
    """
    计算需要下载的缺失报告期

    Returns:
        缺失的 period 列表
    """
    # 1. 获取现有所有 period
    # 2. 对比期望的 period 列表
    # 3. 返回缺失列表
    pass

def calculate_missing_stocks(
    self,
    interface_name: str,
    stock_codes: List[str],
    **params
) -> List[str]:
    """
    计算需要下载的缺失股票代码

    Returns:
        缺失的股票代码列表
    """
    # 1. 获取现有股票代码集合（利用现有 _check_stock_existence 的缓存）
    # 2. 计算差集
    # 3. 返回缺失列表
    pass
```

**关键点**:
- 复用现有 `_check_range_coverage` 的核心逻辑
- 复用现有缓存机制 (`self._cache`)
- 保持线程安全
- 保持交易日历集成

---

### Task 2: 优化文件名过滤逻辑

**文件**: `app4/core/storage.py`

**目标**: 改进 `read_interface_data` 的文件名过滤，减少不必要的文件读取

**当前实现问题**:
```python
# storage.py:246-256
parts = f.split('_')
if len(parts) >= 4 and start_date and end_date:
    f_min, f_max = parts[1], parts[2]  # 假设格式固定
    if f_max < start_date or f_min > end_date:
        continue
```

**优化方案**:

```python
def _filter_files_by_date_range(
    self,
    files: List[str],
    start_date: Optional[str],
    end_date: Optional[str],
    date_column: str
) -> List[str]:
    """
    根据日期范围过滤文件列表

    Args:
        files: 文件名列表
        start_date: 开始日期
        end_date: 结束日期
        date_column: 日期列名（用于判断日期格式）

    Returns:
        符合条件的文件路径列表
    """
    if not start_date or not end_date:
        return [os.path.join(dir_path, f) for f in files if f.endswith('.parquet')]

    filtered_files = []
    for f in files:
        if not f.endswith('.parquet') or f.endswith('.tmp'):
            continue

        # 解析文件名：interface_min_max_timestamp_uuid.parquet
        parts = f.split('_')
        if len(parts) < 4:
            # 格式不匹配，保守起见包含该文件
            filtered_files.append(os.path.join(dir_path, f))
            continue

        try:
            # 提取日期范围
            file_min = str(parts[1])
            file_max = str(parts[2])

            # 跳过无日期的文件
            if file_min == "nodate" or file_max == "nodate":
                # 对于无日期文件，保守起见包含
                filtered_files.append(os.path.join(dir_path, f))
                continue

            # 检查范围重叠
            # 文件范围与查询范围有交集则包含
            if file_max >= start_date and file_min <= end_date:
                filtered_files.append(os.path.join(dir_path, f))

        except (ValueError, IndexError):
            # 解析失败，保守起见包含该文件
            logger.warning(f"Failed to parse date range from filename: {f}")
            filtered_files.append(os.path.join(dir_path, f))

    return filtered_files
```

**在 `read_interface_data` 中调用**:
```python
# 替换现有 files_to_read 生成逻辑
if start_date and end_date:
    interface_config = self._get_interface_config(interface_name)
    date_column = interface_config.get('duplicate_detection', {}).get('date_column', 'trade_date')
    files_to_read = self._filter_files_by_date_range(all_files, start_date, end_date, date_column)
else:
    files_to_read = [os.path.join(dir_path, f) for f in all_files if f.endswith('.parquet') and not f.endswith('.tmp')]
```

**收益**:
- 减少 50-80% 不必要的文件读取
- 显著降低内存占用
- 提升检测速度

---

### Task 3: 增强下载器以支持增量下载

**文件**: `app4/core/downloader.py`

**目标**: 在现有分页逻辑中集成增量范围计算

#### 3.1 日期范围分页增强

**修改 `_execute_date_range_pagination`**:

```python
def _execute_date_range_pagination(self, ...):
    # ... 现有逻辑 ...

    for i in range(0, len(trade_days), window_size):
        window_trade_days = trade_days[i:i+window_size]
        # ...

        # [新增] 使用增量范围计算
        if self.coverage_manager:
            # 计算当前窗口的缺失范围
            missing_ranges = self.coverage_manager.calculate_missing_date_ranges(
                interface_config['api_name'],
                window_start,
                window_end,
                **window_params
            )

            if not missing_ranges:
                logger.info(f"Window {window_start}-{window_end} fully covered, skipping")
                continue

            # 下载所有缺失的子范围
            for missing_start, missing_end in missing_ranges:
                logger.info(f"Downloading missing range: {missing_start}-{missing_end}")
                missing_params = window_params.copy()
                missing_params['start_date'] = missing_start
                missing_params['end_date'] = missing_end

                window_data = self._make_request(interface_config, missing_params)
                if window_data:
                    all_data.extend(window_data)
        else:
            # 原有逻辑作为 fallback
            # ...
```

#### 3.2 股票循环分页增强

**修改 `_execute_stock_loop_pagination`**:

```python
def _execute_stock_loop_pagination(self, ...):
    # ... 获取股票列表 ...

    # [新增] 批量计算缺失股票
    if self.coverage_manager:
        missing_stocks = self.coverage_manager.calculate_missing_stocks(
            interface_config['api_name'],
            [stock['ts_code'] for stock in stock_list],
            **params
        )
        logger.info(f"Found {len(missing_stocks)} missing stocks out of {len(stock_list)}")

        # 过滤股票列表
        stock_list = [stock for stock in stock_list if stock['ts_code'] in missing_stocks]

    # 继续原有循环逻辑
    for idx, stock in enumerate(stock_list):
        # ...
```

#### 3.3 报告期范围分页增强

**修改 `_execute_period_range_pagination`**:

```python
def _execute_period_range_pagination(self, ...):
    # ... 生成 periods ...

    # [新增] 批量计算缺失报告期
    if self.coverage_manager:
        missing_periods = self.coverage_manager.calculate_missing_periods(
            interface_config['api_name'],
            start_date,
            end_date,
            **params
        )
        logger.info(f"Found {len(missing_periods)} missing periods out of {len(periods)}")

        # 过滤 periods 列表
        periods = missing_periods

    # 为每个 period 发起请求
    for idx, period in enumerate(periods):
        # ... 原有逻辑 ...
```

---

### Task 4: 添加配置选项

**文件**: `app4/config/interfaces/*.yaml`

**目标**: 为增量下载添加配置项

**示例配置** (`daily.yaml`):

```yaml
# 在原有 duplicate_detection 下添加
incremental_download:
  enabled: true        # 是否启用增量下载
  mode: "auto"         # 模式: auto / full / incremental
                       # auto: 自动检测并增量下载
                       # full: 强制全量下载
                       # incremental: 仅下载缺失部分

# 原有配置
duplicate_detection:
  enabled: true
  mode: "range"
  date_column: trade_date
  threshold: 0.95
```

**在 CoverageManager 中读取配置**:
```python
def should_use_incremental(self, interface_name: str) -> bool:
    """判断是否使用增量下载"""
    interface_config = self.config_loader.get_interface_config(interface_name)
    incremental_config = interface_config.get('incremental_download', {})

    mode = incremental_config.get('mode', 'auto')
    if mode == 'full':
        return False
    elif mode == 'incremental':
        return True
    else:  # auto
        return incremental_config.get('enabled', True)
```

---

### Task 5: 测试方案

**文件**: `tests/test_coverage_enhancement.py`

**测试场景**:

```python
import pytest
import tempfile
from pathlib import Path
import polars as pl
from datetime import datetime, timedelta

from app4.core.coverage_manager import CoverageManager
from app4.core.storage import StorageManager
from app4.core.config_loader import ConfigLoader


def test_calculate_missing_date_ranges():
    """测试缺失日期范围计算"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建测试数据：2014-2016年数据已存在
        storage_dir = Path(tmpdir) / "data"
        storage_dir.mkdir()

        daily_dir = storage_dir / "daily"
        daily_dir.mkdir()

        # 写入部分数据（2014-2016）
        dates = []
        for year in [2014, 2015, 2016]:
            for i in range(10):
                date_str = f"{year}01{i+1:02d}"
                dates.append(date_str)

        df = pl.DataFrame({
            "ts_code": ["000001.SZ"] * len(dates),
            "trade_date": dates,
            "close": [10.0] * len(dates)
        })

        file_path = daily_dir / "daily_20140101_20160110_1234567890_test.parquet"
        df.write_parquet(file_path)

        # 初始化 CoverageManager
        config_loader = ConfigLoader(config_dir="app4/config")
        storage_manager = StorageManager(storage_dir=str(storage_dir))
        coverage_manager = CoverageManager(storage_manager, config_loader)

        # 查询 2014-2018 范围
        missing_ranges = coverage_manager.calculate_missing_date_ranges(
            "daily",
            "20140101",
            "20181231",
            ts_code="000001.SZ"
        )

        # 应该返回 2017-2018 的缺失范围
        assert len(missing_ranges) > 0
        assert missing_ranges[0][0] >= "20170101"


def test_incremental_download_integration():
    """测试增量下载集成"""
    # 模拟下载器的完整流程
    pass


def test_file_filter_optimization():
    """测试文件名过滤优化"""
    # 验证文件过滤逻辑正确性
    pass
```

---

## 收益对比

### 采用原方案的风险
- ❌ 破坏现有稳定功能
- ❌ 丧失高级特性（阈值、监控、缓存）
- ❌ 严重的数据完整性问题
- ❌ 性能大幅下降
- ❌ 需要大规模回归测试

### 采用增强方案的优势
- ✅ 保留所有现有优势
- ✅ 最小化改动（增量开发）
- ✅ 向后兼容
- ✅ 实现真正的智能增量下载
- ✅ 性能显著提升
- ✅ 风险可控

---

## 实施优先级

1. **P0**: Task 1 - 增量范围计算（核心功能）
2. **P1**: Task 2 - 文件名过滤优化（性能提升）
3. **P1**: Task 3 - 下载器增强（功能集成）
4. **P2**: Task 4 - 配置选项（灵活性）
5. **P3**: Task 5 - 测试覆盖（质量保证）

**预计工作量**: 2-3 天（vs 原方案的 7 天）

**风险等级**: 低（vs 原方案的高风险）

---

## 结论

**不建议采用原方案**，建议在现有 `CoverageManager` 基础上进行增量增强。现有实现已具备生产级质量，重复实现会造成资源浪费并引入严重风险。

增强方案能够：
- 实现真正的智能增量下载
- 保持系统稳定性和性能
- 最小化开发和测试成本
- 为后续优化奠定基础
