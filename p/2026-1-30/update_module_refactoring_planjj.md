# Update 模块重构优化方案（精简版）

## 一、问题概述

当前 `app4/update` 和 `app4/core` 模块之间存在代码重复，核心问题是**日期处理逻辑分散**和 **DateRange 类重复定义**。

### 核心问题

1. **DateRange 类重复定义**
   - `core/coverage_manager.py:17-39` 定义了 `DateRange` 类
   - `update/models.py:26-43` 也定义了 `DateRange` 类
   - 两者 `days_between` 计算逻辑不同：
     - `coverage_manager`: `(end - start).days + 1` (包含首尾)
     - `models`: `(end - start).days` (不包含首尾)

2. **日期处理逻辑分散**
   - `DateCalculator._format_date` 实现了完整的日期格式化
   - `CoverageManager` 中多处重复实现日期格式化
   - `DateCalculator._get_interface_date_column` 和 `CoverageManager._detect_date_column` 逻辑相似

## 二、重构目标

### 设计原则

1. **消除重复** - 提取通用日期逻辑到 `core` 模块
2. **代码复用** - `update` 和 `core` 共用同一套日期工具
3. **向后兼容** - 保持现有 API 不变，仅内部实现调整

### 预期收益

- 消除 `DateRange` 类重复定义
- 统一日期处理逻辑，减少维护成本
- 代码量减少约 20%
- 实施周期短（3天）

## 三、详细优化方案

### 优化 1：创建统一的日期工具模块

**新建 `core/date_utils.py`：**

```python
"""
日期工具模块 - 统一日期处理逻辑
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


@dataclass
class DateRange:
    """日期范围数据类 - 统一版本（包含首尾）"""
    start_date: str  # YYYYMMDD
    end_date: str    # YYYYMMDD

    def __str__(self) -> str:
        return f"{self.start_date} ~ {self.end_date}"

    def days_between(self) -> int:
        """计算两个日期之间的天数（包含首尾）"""
        start = datetime.strptime(self.start_date, '%Y%m%d')
        end = datetime.strptime(self.end_date, '%Y%m%d')
        return (end - start).days + 1

    def contains(self, date_str: str) -> bool:
        """检查日期是否在范围内"""
        return self.start_date <= date_str <= self.end_date


def format_date(date_value) -> Optional[str]:
    """
    将日期值格式化为 YYYYMMDD 字符串
    
    Args:
        date_value: 日期值（可以是字符串、整数、日期对象等）
        
    Returns:
        Optional[str]: 格式化后的日期字符串
    """
    if date_value is None:
        return None
    
    try:
        # 如果已经是字符串且格式正确
        if isinstance(date_value, str):
            if len(date_value) == 8 and date_value.isdigit():
                return date_value
            for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%d/%m/%Y']:
                try:
                    dt = datetime.strptime(date_value, fmt)
                    return dt.strftime('%Y%m%d')
                except ValueError:
                    continue
        
        # 如果是整数（如 20230101）
        if isinstance(date_value, int):
            return str(date_value)
        
        # 如果是日期/时间对象
        if hasattr(date_value, 'strftime'):
            return date_value.strftime('%Y%m%d')
        
        return str(date_value)
        
    except Exception as e:
        logger.warning(f"日期格式化失败: {date_value}, 错误: {e}")
        return None


def detect_date_column(interface_config: Dict[str, Any]) -> Optional[str]:
    """
    智能检测接口的日期列名
    
    优先级：
    1. duplicate_detection.date_column
    2. output.date_column
    3. 接口名称推断
    4. 常见日期字段名匹配
    """
    # 1. 检查 duplicate_detection 配置
    detection_config = interface_config.get('duplicate_detection', {})
    if 'date_column' in detection_config:
        return detection_config['date_column']
    
    # 2. 检查 output 配置
    output_config = interface_config.get('output', {})
    if 'date_column' in output_config:
        return output_config['date_column']
    
    # 3. 根据接口名称推断
    interface_name = interface_config.get('api_name', '')
    if 'trade_cal' in interface_name:
        return 'cal_date'
    elif any(x in interface_name for x in ['income', 'balance', 'cashflow', 'fina_indicator']):
        return 'end_date'
    elif 'stock_basic' in interface_name:
        return 'list_date'
    elif 'disclosure_date' in interface_name:
        return 'disclosure_date'
    
    # 4. 从 fields 中查找常见日期字段
    fields = interface_config.get('fields', {})
    priority_fields = [
        'trade_date', 'report_date', 'ann_date', 'end_date',
        'cal_date', 'list_date', 'disclosure_date'
    ]
    for field in priority_fields:
        if field in fields:
            return field
    
    return 'trade_date'


def calculate_start_with_lookback(end_date: str, lookback_days: int) -> str:
    """
    计算带有回溯天数的起始日期
    
    Args:
        end_date: 结束日期（YYYYMMDD）
        lookback_days: 回溯天数
        
    Returns:
        str: 起始日期（YYYYMMDD）
    """
    try:
        end_dt = datetime.strptime(end_date, '%Y%m%d')
        start_dt = end_dt - timedelta(days=lookback_days)
        return start_dt.strftime('%Y%m%d')
    except (ValueError, TypeError):
        return end_date
```

### 优化 2：重构 DateCalculator

**修改 `update/date_calculator.py`：**

```python
"""
日期范围计算器 - 重构后版本
"""
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from core.date_utils import (
    DateRange,
    format_date,
    detect_date_column,
    calculate_start_with_lookback
)

logger = logging.getLogger(__name__)


class DateCalculator:
    """日期计算器 - 智能计算接口的更新日期范围"""
    
    DEFAULT_START_DATES = {
        'trade_cal': '19900101',
        'stock_basic': '19900101',
        'stock_company': '19900101',
        'daily': '20000101',
        'daily_basic': '20000101',
        'pro_bar': '20000101',
    }
    
    def __init__(self, config_loader, storage_manager):
        self.config_loader = config_loader
        self.storage_manager = storage_manager
        
        self.update_config = config_loader.global_config.get('update', {})
        self.default_strategy = self.update_config.get('default_strategy', {})
        self.special_interfaces = self.update_config.get('special_interfaces', {})
        self.lookback_days = self.default_strategy.get('lookback_days', 7)
    
    def calculate_update_range(
        self, 
        interface_name: str,
        forced_start: Optional[str] = None,
        forced_end: Optional[str] = None
    ) -> DateRange:
        """计算接口的更新日期范围"""
        if forced_start and forced_end:
            logger.info(f"[{interface_name}] 使用强制指定的日期范围: {forced_start} ~ {forced_end}")
            return DateRange(start_date=forced_start, end_date=forced_end)
        
        existing_range = self._get_existing_data_range(interface_name)
        
        if forced_start:
            start_date = forced_start
        elif existing_range:
            start_date = calculate_start_with_lookback(
                existing_range.end_date,
                self._get_interface_lookback_days(interface_name)
            )
            logger.info(f"[{interface_name}] 现有数据到 {existing_range.end_date}，回溯至 {start_date}")
        else:
            start_date = self._get_default_start_date(interface_name)
            logger.info(f"[{interface_name}] 无现有数据，使用默认起始日期: {start_date}")
        
        end_date = forced_end or datetime.now().strftime('%Y%m%d')
        
        if start_date > end_date:
            logger.warning(f"[{interface_name}] 起始日期 {start_date} 大于结束日期 {end_date}，调整为相同")
            start_date = end_date
        
        return DateRange(start_date=start_date, end_date=end_date)
    
    def _get_existing_data_range(self, interface_name: str) -> Optional[DateRange]:
        """获取接口现有数据的日期范围"""
        try:
            interface_config = self.config_loader.get_interface_config(interface_name)
            date_column = detect_date_column(interface_config)
            
            if not date_column:
                return None
            
            df = self.storage_manager.read_interface_data(
                interface_name,
                columns=[date_column]
            )
            
            if df.is_empty():
                return None
            
            min_date = df[date_column].min()
            max_date = df[date_column].max()
            
            min_date_str = format_date(min_date)
            max_date_str = format_date(max_date)
            
            if min_date_str and max_date_str:
                return DateRange(start_date=min_date_str, end_date=max_date_str)
            
            return None
            
        except Exception as e:
            logger.warning(f"获取 {interface_name} 的现有数据范围失败: {e}")
            return None
    
    def _get_default_start_date(self, interface_name: str) -> str:
        """获取接口的默认起始日期"""
        special_config = self.special_interfaces.get(interface_name, {})
        if 'start_date' in special_config:
            return special_config['start_date']
        
        default_start = self.default_strategy.get('start_date')
        if default_start:
            return default_start
        
        for key, value in self.DEFAULT_START_DATES.items():
            if key in interface_name:
                return value
        
        return '20000101'
    
    def _get_interface_lookback_days(self, interface_name: str) -> int:
        """获取接口特定的回溯天数"""
        special_config = self.special_interfaces.get(interface_name, {})
        return special_config.get('lookback_days', self.lookback_days)
    
    def is_update_needed(
        self, 
        existing_range: Optional[DateRange], 
        target_range: DateRange
    ) -> bool:
        """判断是否需要更新"""
        if not existing_range:
            return True
        if target_range.end_date > existing_range.end_date:
            return True
        if target_range.start_date < existing_range.start_date:
            return True
        return False
```

### 优化 3：重构 CoverageManager

**修改 `core/coverage_manager.py`：**

```python
"""覆盖率管理器 - 重构后版本"""
import logging
import threading
from typing import Dict, Any, Optional, Set, List
from collections import OrderedDict
import polars as pl

from .storage import StorageManager
from .config_loader import ConfigLoader
from .date_utils import (
    DateRange,
    format_date,
    detect_date_column
)

logger = logging.getLogger(__name__)


class CoverageManager:
    """覆盖率管理器 - 实现重复数据检测功能"""

    def __init__(self, storage_manager: StorageManager, config_loader: ConfigLoader, 
                 downloader=None, cache_size: int = 128):
        self.storage_manager = storage_manager
        self.config_loader = config_loader
        self.downloader = downloader
        
        self._cache = {}
        self._coverage_cache = {}
        self._cache_lock = threading.RLock()
        
        self._existing_dates_cache = OrderedDict()
        self._cache_size = cache_size
        self._existing_dates_lock = threading.RLock()

    # ... 其他方法保持不变，只修改日期相关方法 ...

    def _get_existing_dates_from_storage(self, interface_name: str) -> Set[str]:
        """从存储中读取已有日期 - 使用统一的日期工具"""
        try:
            interface_config = self.config_loader.get_interface_config(interface_name)
            date_column = detect_date_column(interface_config)

            if not date_column:
                logger.warning(f"{interface_name}: 无法检测到日期列")
                return set()

            df = self.storage_manager.read_interface_data(
                interface_name,
                columns=[date_column]
            )

            if df.is_empty():
                return set()

            # 使用统一的日期格式化
            dates = set()
            for date_val in df[date_column]:
                formatted = format_date(date_val)
                if formatted:
                    dates.add(formatted)

            return dates

        except Exception as e:
            logger.warning(f"读取已有日期失败 {interface_name}: {e}")
            return set()

    def _detect_date_column(self, interface_config: Dict[str, Any]) -> Optional[str]:
        """智能检测日期列名称 - 使用统一工具"""
        return detect_date_column(interface_config)
    
    # 移除重复的 _format_date 方法，使用 date_utils.format_date
```

### 优化 4：更新 models.py 导入

**修改 `update/models.py`：**

```python
"""
增量更新模块数据模型
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Optional, List, Dict, Any

# 从 core 导入 DateRange
from core.date_utils import DateRange

# ... 其他模型类保持不变 ...
```

## 四、实施步骤（3天）

### 第1天：创建 date_utils 模块

1. 创建 `core/date_utils.py`
2. 实现 `DateRange` 类（统一使用包含首尾的计算方式）
3. 实现日期工具函数
4. 编写单元测试

### 第2天：重构使用方

1. 修改 `update/date_calculator.py`，使用 `date_utils`
2. 修改 `core/coverage_manager.py`，使用 `date_utils`
3. 修改 `update/models.py`，从 `date_utils` 导入 `DateRange`
4. 确保所有导入正确

### 第3天：测试验证

1. **重点验证**：`days_between` 行为一致性（包含首尾）
2. 运行单元测试
3. 运行集成测试
4. 验证业务逻辑正确性

## 五、风险评估

| 风险项 | 等级 | 缓解措施 |
|--------|------|----------|
| days_between 行为变更 | 中 | 统一为包含首尾，检查所有使用处 |
| 日期格式化差异 | 低 | 使用 `DateCalculator` 的完整实现 |
| 导入路径变更 | 低 | 简单替换，风险可控 |

## 六、成功标准

1. `DateRange` 类只在一处定义（`core/date_utils.py`）
2. 日期处理逻辑只在一处实现
3. 所有测试通过
4. 业务逻辑行为一致

## 七、不做的优化（当前版本跳过）

以下优化在当前精简版中**不做**，因为收益有限或当前已实现：

1. **配置缓存优化** - `ConfigLoader` 已在内存中缓存所有配置
2. **Downloader 接口扩展** - 当前接口已足够清晰
3. **交易日历/股票列表统一获取** - `Downloader` 已提供公共方法

## 八、总结

本精简版方案通过**3个文件改动、3天实施周期**，解决核心问题：

1. **消除 DateRange 重复定义**
2. **统一日期处理逻辑**
3. **减少代码维护成本**

方案特点：**改动小、风险低、见效快**。
