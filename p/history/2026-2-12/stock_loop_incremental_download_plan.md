# Stock Loop 模式智能增量下载方案

## 一、核心问题分析

根据 Tushare 文档和现有代码分析，不同接口的参数要求差异很大：

| 接口类型 | 日期参数 | 示例接口 |
|---------|---------|---------|
| 日线数据 | `ts_code` + `start_date`/`end_date` | `daily`, `daily_basic` |
| 交易日期 | `ts_code` + `trade_date` | `moneyflow`, `block_trade` |
| 财报数据 | `ts_code` + `period`/`end_date` | `income_vip`, `balancesheet_vip` |
| 日期锚定 | `ts_code` + 锚定日期参数 | `disclosure_date` (end_date 是锚定参数) |
| 无日期参数 | 仅 `ts_code` | `stock_company`, `stock_basic` |

---

## 二、方案架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    StockLoopDownloadPlanner                      │
│                     (股票级下载计划生成器)                        │
├─────────────────────────────────────────────────────────────────┤
│  1. 检测数据存在性                                               │
│     └─> 检查该股票是否已有数据                                    │
│                                                                         │
│  2. 分析接口参数模式                                             │
│     └─> 从 YAML 配置解析参数要求                                  │
│                                                                         │
│  3. 生成下载策略                                                 │
│     ├─> 完全无数据 → 全历史下载                                   │
│     ├─> 有数据但缺失 → 计算缺口并生成参数                         │
│     └─> 数据完整 → 跳过                                          │
│                                                                         │
│  4. 执行下载任务                                                 │
│     └─> 按生成的参数列表逐个下载                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 三、关键实现步骤

### 1. 增强接口配置 (YAML)

每个接口配置需要明确定义：

```yaml
# 示例：income_vip.yaml
api_name: income_vip
# ... 其他配置 ...

# 重复检测配置
duplicate_detection:
  enabled: true
  # 用于检测数据是否已存在的字段组合
  key_columns: [ts_code, end_date]  # 或 key_column: period

# 日期参数配置（新增）
date_params:
  # 模式1: 标准 start_date + end_date
  mode: "date_range"  # date_range | trade_date | period | date_anchor | none

  # 数据中的日期字段（用于检测缺失）
  data_date_column: "end_date"

  # 输入参数映射
  input_mapping:
    start_date: "start_date"  # 参数名: 接口参数名
    end_date: "end_date"

  # 日期锚定参数（用于 disclosure_date 这类接口）
  anchor_param: "end_date"

  # 是否需要遍历所有可能的日期值
  enumerate_dates: false

  # 日期格式
  date_format: "%Y%m%d"

# 分页配置
pagination:
  enabled: true
  mode: stock_loop
```

---

### 2. 创建 StockLoopPlanner 类

```python
# app4/core/stock_loop_planner.py

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging

from .date_utils import DateRange, detect_date_column, format_date
from .coverage_manager import CoverageManager

logger = logging.getLogger(__name__)


@dataclass
class DownloadTask:
    """单个下载任务"""
    ts_code: str
    params: Dict[str, Any]
    reason: str  # 下载原因：full_history | gap_fill | update


class StockLoopPlanner:
    """
    Stock Loop 模式下载计划生成器

    职责：
    1. 分析接口参数配置
    2. 检测现有数据覆盖情况
    3. 生成最优下载参数
    """

    def __init__(
        self,
        coverage_manager: CoverageManager,
        trade_calendar_provider,  # 获取交易日历的函数/对象
        config_loader
    ):
        self.coverage_manager = coverage_manager
        self.trade_calendar_provider = trade_calendar_provider
        self.config_loader = config_loader

    def plan_download(
        self,
        interface_name: str,
        ts_code: str,
        interface_config: Dict[str, Any],
        user_params: Optional[Dict[str, Any]] = None
    ) -> List[DownloadTask]:
        """
        生成单个股票的下载计划

        Args:
            interface_name: 接口名称
            ts_code: 股票代码
            interface_config: 接口配置
            user_params: 用户指定的参数（如 --start_date, --end_date）

        Returns:
            List[DownloadTask]: 下载任务列表
        """
        # 1. 获取接口日期参数配置
        date_config = self._get_date_config(interface_config)

        # 2. 检查现有数据
        existing_dates = self._get_existing_dates_for_stock(
            interface_name, ts_code, date_config['data_date_column']
        )

        # 3. 根据参数模式生成任务
        if date_config['mode'] == 'none':
            # 无日期参数，一次性下载
            return self._plan_no_date_params(ts_code, user_params)

        elif date_config['mode'] == 'date_range':
            # start_date + end_date 模式
            return self._plan_date_range_mode(
                interface_name, ts_code, interface_config,
                date_config, existing_dates, user_params
            )

        elif date_config['mode'] == 'trade_date':
            # 按单个交易日期查询
            return self._plan_trade_date_mode(
                interface_name, ts_code, date_config, existing_dates, user_params
            )

        elif date_config['mode'] == 'period':
            # 按报告期查询（季度）
            return self._plan_period_mode(
                interface_name, ts_code, date_config, existing_dates, user_params
            )

        elif date_config['mode'] == 'date_anchor':
            # 日期锚定模式（如 disclosure_date）
            return self._plan_date_anchor_mode(
                interface_name, ts_code, interface_config,
                date_config, existing_dates, user_params
            )

        else:
            logger.warning(f"未知的日期参数模式: {date_config['mode']}")
            return []

    def _get_date_config(self, interface_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        从接口配置中提取日期参数配置
        """
        date_params = interface_config.get('date_params', {})

        # 检测日期列（用于数据存在性检查）
        data_date_column = date_params.get('data_date_column') or \
                          detect_date_column(interface_config) or \
                          'trade_date'

        # 确定参数模式
        parameters = interface_config.get('parameters', {})

        # 自动推断模式
        if date_params.get('mode'):
            mode = date_params['mode']
        elif 'start_date' in parameters and 'end_date' in parameters:
            if date_params.get('anchor_param'):
                mode = 'date_anchor'
            else:
                mode = 'date_range'
        elif 'trade_date' in parameters:
            mode = 'trade_date'
        elif 'period' in parameters:
            mode = 'period'
        else:
            mode = 'none'

        return {
            'mode': mode,
            'data_date_column': data_date_column,
            'input_mapping': date_params.get('input_mapping', {}),
            'anchor_param': date_params.get('anchor_param'),
            'enumerate_dates': date_params.get('enumerate_dates', False),
            'date_format': date_params.get('date_format', '%Y%m%d')
        }

    def _plan_date_range_mode(
        self,
        interface_name: str,
        ts_code: str,
        interface_config: Dict[str, Any],
        date_config: Dict[str, Any],
        existing_dates: set,
        user_params: Optional[Dict[str, Any]]
    ) -> List[DownloadTask]:
        """
        处理 start_date + end_date 模式的下载计划
        """
        # 确定日期范围
        if user_params and 'start_date' in user_params:
            # 用户指定了日期范围
            start_date = user_params['start_date']
            end_date = user_params.get('end_date', datetime.now().strftime('%Y%m%d'))
        else:
            # 自动确定范围
            start_date, end_date = self._determine_date_range(
                interface_name, ts_code, existing_dates
            )

        # 如果没有现有数据，全历史下载
        if not existing_dates:
            return [DownloadTask(
                ts_code=ts_code,
                params={
                    'ts_code': ts_code,
                    'start_date': start_date,
                    'end_date': end_date
                },
                reason='full_history'
            )]

        # 检测缺失的日期段
        gaps = self._detect_date_gaps(
            interface_name, ts_code, start_date, end_date,
            existing_dates, date_config['data_date_column']
        )

        if not gaps:
            logger.info(f"{interface_name}/{ts_code}: 数据已完整覆盖")
            return []

        # 合并缺口，生成下载任务
        tasks = []
        for gap in gaps:
            tasks.append(DownloadTask(
                ts_code=ts_code,
                params={
                    'ts_code': ts_code,
                    'start_date': gap.start_date,
                    'end_date': gap.end_date
                },
                reason='gap_fill'
            ))

        return tasks

    def _plan_date_anchor_mode(
        self,
        interface_name: str,
        ts_code: str,
        interface_config: Dict[str, Any],
        date_config: Dict[str, Any],
        existing_dates: set,
        user_params: Optional[Dict[str, Any]]
    ) -> List[DownloadTask]:
        """
        处理日期锚定模式的下载计划（如 disclosure_date）

        这类接口特点：
        - 使用某个日期参数作为锚点（如 end_date）
        - 需要遍历所有可能的锚点值来获取完整数据
        """
        anchor_param = date_config['anchor_param']

        if user_params and 'start_date' in user_params:
            # 用户指定了范围
            start_date = user_params['start_date']
            end_date = user_params.get('end_date', datetime.now().strftime('%Y%m%d'))

            # 生成所有可能的锚点日期（如所有报告期）
            anchor_dates = self._generate_anchor_dates(
                interface_name, start_date, end_date
            )
        else:
            # 自动确定需要查询的锚点日期
            anchor_dates = self._determine_needed_anchors(
                interface_name, ts_code, existing_dates, date_config
            )

        # 过滤已存在的日期
        missing_anchors = [
            d for d in anchor_dates
            if d not in existing_dates
        ]

        if not missing_anchors:
            return []

        # 生成任务（可以批量或单个）
        tasks = []
        for anchor_date in missing_anchors:
            params = {'ts_code': ts_code, anchor_param: anchor_date}
            tasks.append(DownloadTask(
                ts_code=ts_code,
                params=params,
                reason='gap_fill'
            ))

        return tasks

    def _detect_date_gaps(
        self,
        interface_name: str,
        ts_code: str,
        start_date: str,
        end_date: str,
        existing_dates: set,
        date_column: str
    ) -> List[DateRange]:
        """
        检测指定股票在日期范围内的缺失段
        """
        # 获取期望的交易日列表
        trade_days = self._get_trade_days(start_date, end_date)

        # 找出缺失的交易日
        missing_days = [
            day for day in trade_days
            if day not in existing_dates
        ]

        if not missing_days:
            return []

        # 合并连续的缺失日期为范围
        return self._merge_to_ranges(missing_days)

    def _get_existing_dates_for_stock(
        self,
        interface_name: str,
        ts_code: str,
        date_column: str
    ) -> set:
        """
        获取指定股票已存在的所有日期
        """
        try:
            # 从 storage 读取该股票的数据
            df = self.coverage_manager.storage_manager.read_interface_data(
                interface_name,
                filters={'ts_code': ts_code},
                columns=[date_column]
            )

            if df.is_empty():
                return set()

            # 提取并格式化日期
            dates = set()
            for date_val in df[date_column]:
                formatted = format_date(date_val)
                if formatted:
                    dates.add(formatted)

            return dates

        except Exception as e:
            logger.warning(f"获取 {interface_name}/{ts_code} 的现有日期失败: {e}")
            return set()

    def _determine_date_range(
        self,
        interface_name: str,
        ts_code: str,
        existing_dates: set
    ) -> Tuple[str, str]:
        """
        自动确定下载的日期范围
        """
        # 结束日期：今天
        end_date = datetime.now().strftime('%Y%m%d')

        # 起始日期：根据接口配置或默认值
        if existing_dates:
            # 有数据，从最新数据日期开始（留一定回溯）
            latest = max(existing_dates)
            start_date = self._calculate_lookback(latest, interface_name)
        else:
            # 无数据，使用接口默认起始日期
            start_date = self._get_default_start_date(interface_name)

        return start_date, end_date

    def _merge_to_ranges(self, dates: List[str]) -> List[DateRange]:
        """将日期列表合并为连续的日期范围"""
        if not dates:
            return []

        sorted_dates = sorted(dates)
        ranges = []
        range_start = sorted_dates[0]
        range_end = sorted_dates[0]

        for date in sorted_dates[1:]:
            if self._is_next_day(range_end, date):
                range_end = date
            else:
                ranges.append(DateRange(range_start, range_end))
                range_start = date
                range_end = date

        ranges.append(DateRange(range_start, range_end))
        return ranges

    def _is_next_day(self, current: str, next_date: str) -> bool:
        """检查是否是连续的交易日"""
        from datetime import datetime, timedelta
        curr_dt = datetime.strptime(current, '%Y%m%d')
        next_dt = datetime.strptime(next_date, '%Y%m%d')
        # 简化处理：日期差 <= 7天认为是连续的（考虑周末）
        return (next_dt - curr_dt).days <= 7
```

---

### 3. 修改 download_single_stock 方法

```python
# 在 GenericDownloader 类中修改 download_single_stock 方法

def download_single_stock(
    self,
    interface_config: Dict[str, Any],
    stock: Dict[str, Any],
    params: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    下载单只股票的数据 - 智能增量版本
    """
    from .stock_loop_planner import StockLoopPlanner

    ts_code = stock['ts_code']
    interface_name = interface_config['api_name']

    # 创建计划生成器
    planner = StockLoopPlanner(
        coverage_manager=self.coverage_manager,
        trade_calendar_provider=self.get_trade_calendar,
        config_loader=self.config_loader
    )

    # 生成下载计划
    tasks = planner.plan_download(
        interface_name=interface_name,
        ts_code=ts_code,
        interface_config=interface_config,
        user_params=params
    )

    if not tasks:
        logger.info(f"{interface_name}/{ts_code}: 无需下载，数据已完整")
        return []

    # 执行下载任务
    all_data = []
    for task in tasks:
        logger.info(f"{interface_name}/{ts_code}: {task.reason} - {task.params}")

        # 使用现有分页逻辑执行下载
        data = self._execute_download_with_params(
            interface_config, task.params
        )

        if data:
            all_data.extend(data)

    # 保存数据
    if all_data and self.storage_manager:
        self.storage_manager.add_to_buffer(interface_name, all_data)

    return all_data
```

---

### 4. 配置示例

为每个接口添加 `date_params` 配置：

#### income_vip.yaml

```yaml
api_name: income_vip
# ...

date_params:
  mode: "period"  # 按报告期查询
  data_date_column: "end_date"  # 数据中的日期字段
  input_mapping:
    period: "end_date"  # 输入period参数映射到end_date

duplicate_detection:
  enabled: true
  key_columns: [ts_code, end_date]  # 检测重复的组合键
```

#### disclosure_date.yaml

```yaml
api_name: disclosure_date
# ...

date_params:
  mode: "date_anchor"
  data_date_column: "end_date"
  anchor_param: "end_date"  # 使用end_date作为锚点
  enumerate_dates: true  # 需要遍历所有报告期

duplicate_detection:
  enabled: true
  key_columns: [ts_code, end_date]
```

#### daily_basic.yaml

```yaml
api_name: daily_basic
# ...

date_params:
  mode: "date_range"
  data_date_column: "trade_date"
  input_mapping:
    start_date: "start_date"
    end_date: "end_date"

duplicate_detection:
  enabled: true
  date_column: "trade_date"
```

---

## 四、执行流程图

```
用户执行: python app4/main.py --update --interface daily --ts_code 000001.SZ

    │
    ▼
┌─────────────────────────┐
│  1. 加载接口配置         │
│     (daily.yaml)        │
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│  2. 创建 StockLoopPlanner│
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│  3. 分析日期参数模式      │
│     mode = date_range   │
│     data_date_column =  │
│     trade_date          │
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│  4. 查询现有数据          │
│     SELECT trade_date   │
│     FROM daily          │
│     WHERE ts_code =     │
│     '000001.SZ'         │
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│  5. 检测缺失日期段        │
│     现有: 20240101-20240115│
│     期望: 20240101-20240201│
│     缺失: 20240116-20240201│
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│  6. 生成下载任务          │
│     Task 1:             │
│       start=20240116    │
│       end=20240201      │
│       reason=gap_fill   │
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│  7. 执行下载             │
│     API调用获取缺失数据   │
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│  8. 保存数据             │
│     写入Parquet文件      │
└─────────────────────────┘
```

---

## 五、关键优势

1. **智能参数生成**：根据接口配置自动生成正确的参数，无需硬编码
2. **精确缺口检测**：基于实际数据日期检测缺失，而非简单判断股票是否存在
3. **灵活配置**：通过 YAML 配置支持各种接口类型，无需修改代码
4. **向后兼容**：现有接口无需修改即可工作，新配置是可选的

---

## 六、实施建议

### 第一阶段：核心框架
1. 创建 `stock_loop_planner.py` 文件
2. 实现 `StockLoopPlanner` 类的核心方法
3. 修改 `download_single_stock` 方法集成新逻辑

### 第二阶段：接口配置
1. 为主要接口添加 `date_params` 配置
2. 优先处理高频使用的接口（daily, daily_basic, income_vip 等）
3. 测试各接口的增量下载行为

### 第三阶段：优化完善
1. 添加更多参数模式支持
2. 优化日期缺口合并算法
3. 添加详细的日志和监控
