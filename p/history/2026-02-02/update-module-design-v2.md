# App4 增量更新模块设计方案 V2

## 文档信息
- **版本**: 2.0
- **日期**: 2026-02-05
- **状态**: 设计阶段
- **作者**: AI Assistant + 工程团队评审

---

## 1. 设计目标与原则

### 1.1 核心目标
- 实现一键式全系统增量更新功能
- 智能计算每个接口的更新日期范围
- 自动检测并跳过已是最新的数据
- 提供清晰的更新报告和统计信息
- 保持与现有 App4 架构的兼容性

### 1.2 设计原则

| 原则 | 说明 |
|------|------|
| **单一职责** | 更新模块只负责协调更新流程，不处理具体下载逻辑 |
| **配置驱动** | 复用现有的接口配置，通过配置文件调整更新行为 |
| **容错性** | 单个接口失败不影响其他接口更新 |
| **可观测性** | 提供详细的日志和更新报告 |
| **渐进式** | 支持全量、增量、强制等多种更新模式 |
| **可测试性** | 模块设计便于单元测试和集成测试 |
| **复用优先** | 优先复用现有组件（CoverageManager、PaginationExecutor等） |
| **断点续传** | 支持更新中断后的断点续传 |

---

## 2. 架构设计

### 2.1 模块结构

```
app4/
├── main.py                          # 主入口，添加 --update 参数解析
├── core/                            # 现有核心模块（不修改）
│   ├── config_loader.py
│   ├── downloader.py
│   ├── coverage_manager.py
│   ├── pagination_executor.py
│   └── ...
├── update/                          # 新增更新模块目录
│   ├── __init__.py
│   ├── update_manager.py            # 更新管理器（核心协调器）
│   ├── date_calculator.py           # 日期范围计算器
│   ├── update_reporter.py           # 更新报告生成器
│   └── interface_selector.py        # 接口选择器
└── config/
    ├── settings.yaml                # 添加 update 配置段
    └── interfaces/                  # 现有接口配置（不修改）
        ├── *.yaml
```

### 2.2 组件职责

```
┌─────────────────────────────────────────────────────────────┐
│                        UpdateManager                        │
│  - 协调整个更新流程                                          │
│  - 管理更新生命周期                                          │
│  - 处理异常和回滚                                            │
└──────────────────┬──────────────────────────────────────────┘
                   │ 调用
    ┌──────────────┼──────────────┐
    ▼              ▼              ▼
┌─────────┐  ┌──────────┐  ┌──────────────┐
│ Date    │  │ Interface│  │ Update       │
│Calculator│  │ Selector │  │ Reporter     │
│         │  │          │  │              │
│计算日期  │  │选择接口  │  │生成报告      │
│范围      │  │          │  │              │
└────┬────┘  └────┬─────┘  └──────────────┘
     │            │
     ▼            ▼
┌──────────────────────────────────────┐
│         现有 App4 组件                │
│  ┌──────────┐  ┌──────────────────┐  │
│  │ Config   │  │ StorageManager   │  │
│  │ Loader   │  │                  │  │
│  └──────────┘  └──────────────────┘  │
│  ┌──────────┐  ┌──────────────────┐  │
│  │ Generic  │  │ CoverageManager  │  │
│  │ Downloader│  │                  │  │
│  └──────────┘  └──────────────────┘  │
└──────────────────────────────────────┘
```

---

## 3. 核心组件详细设计

### 3.1 UpdateManager（更新管理器）

**职责**：
- 初始化更新环境
- 协调更新流程（规划→执行→报告）
- 管理更新生命周期
- 处理异常和回滚
- **复用 CoverageManager 进行跳过检测**
- **复用 PaginationExecutor 执行分页下载**
- **管理断点续传状态**

**类定义**：
```python
class UpdateManager:
    def __init__(
        self,
        config_loader: ConfigLoader,
        storage_manager: StorageManager,
        downloader: GenericDownloader,
        scheduler: TaskScheduler,
        processor: DataProcessor,
        global_rate_limiter: RateLimiter
    ):
        self.config_loader = config_loader
        self.storage_manager = storage_manager
        self.downloader = downloader
        self.scheduler = scheduler
        self.processor = processor
        self.global_rate_limiter = global_rate_limiter
        
        # 子组件
        self.date_calculator = DateCalculator(config_loader, storage_manager)
        self.interface_selector = InterfaceSelector(config_loader)
        self.reporter = UpdateReporter()
        
        # 复用现有的 CoverageManager（通过 downloader 获取）
        self.coverage_manager = downloader.coverage_manager
        
        # 复用现有的 PaginationExecutor（通过 downloader 获取）
        self.pagination_executor = downloader.pagination_executor
        
        # 断点续传管理器
        self.checkpoint_manager = CheckpointManager(
            config_loader.global_config.get('update', {}).get('checkpoint', {})
        )
    
    def run_update(self, options: UpdateOptions) -> UpdateResult:
        """
        执行增量更新
        
        流程：
        1. 初始化环境
        2. 加载断点（如有）
        3. 选择需要更新的接口
        4. 逐个接口执行更新
        5. 保存断点
        6. 生成更新报告
        """
        pass
    
    def update_interface(
        self, 
        interface_name: str, 
        options: UpdateOptions
    ) -> InterfaceUpdateResult:
        """
        更新单个接口
        
        实现：
        1. 获取接口配置
        2. 计算日期范围
        3. 使用 CoverageManager.should_skip() 检测是否需要更新
        4. 使用 PaginationExecutor 执行分页下载
        5. 返回更新结果
        """
        pass
    
    def should_update_interface(
        self, 
        interface_name: str, 
        date_range: DateRange,
        options: UpdateOptions
    ) -> Tuple[bool, Optional[str]]:
        """
        判断接口是否需要更新
        
        实现：
        1. 如果 force=True，直接返回需要更新
        2. 否则调用 CoverageManager.should_skip() 检测
        
        Returns:
            (是否需要更新, 跳过原因)
        """
        pass
```

**工作流程**：

```
开始更新
    │
    ▼
[初始化]
    ├── 加载配置
    ├── 初始化子组件
    └── 验证环境
    │
    ▼
[规划阶段]
    ├── 获取所有可用接口
    ├── 应用过滤条件
    ├── 确定更新顺序
    └── 生成更新计划
    │
    ▼
[执行阶段] ←────────────────────────┐
    │                                 │
    ├── 获取下一个待更新接口          │
    │                                 │
    ▼                                 │
[计算日期范围]                        │
    ├── 查询现有数据范围              │
    ├── 应用特殊接口规则              │
    └── 确定更新范围                  │
    │                                 │
    ▼                                 │
[检查是否需要更新]                    │
    ├── 否 → 记录跳过原因 ────────────┤
    │                                 │
    ▼                                 │
[执行接口更新]                        │
    ├── 调用现有下载逻辑              │
    ├── 监控进度                      │
    └── 记录结果                      │
    │                                 │
    ▼                                 │
[记录结果] ─────────────────────────┘
    │
    ▼
[报告阶段]
    ├── 汇总统计信息
    ├── 生成更新报告
    └── 输出报告
    │
    ▼
结束更新
```

### 3.2 DateCalculator（日期计算器）

**职责**：
- 智能计算每个接口的更新日期范围
- 处理特殊接口的日期规则
- 检测现有数据的边界

**类定义**：
```python
class DateCalculator:
    def __init__(
        self, 
        config_loader: ConfigLoader, 
        storage_manager: StorageManager
    ):
        self.config_loader = config_loader
        self.storage_manager = storage_manager
        
        # 特殊接口默认起始日期（从配置读取，可覆盖）
        self.special_start_dates = {
            'trade_cal': '19900101',
            'stock_basic': '19900101',
            'stock_company': '19900101',
            'daily': '20000101',
            'daily_basic': '20000101',
        }
    
    def calculate_update_range(
        self, 
        interface_name: str,
        forced_start: Optional[str] = None,
        forced_end: Optional[str] = None
    ) -> DateRange:
        """
        计算接口的更新日期范围
        
        策略：
        1. 如果指定了强制日期，使用强制日期
        2. 获取现有数据的最新日期作为起始
        3. 如果没有现有数据，使用默认起始日期
        4. 结束日期为今天
        """
        pass
    
    def get_existing_data_range(
        self, 
        interface_name: str
    ) -> Optional[DateRange]:
        """
        获取接口现有数据的日期范围
        
        实现：
        1. 从 storage_manager 读取接口数据
        2. 根据接口配置确定日期列
        3. 返回最小和最大日期
        """
        pass
    
    def get_interface_date_column(self, interface_name: str) -> str:
        """
        获取接口的日期列名
        
        优先级：
        1. 接口配置的 duplicate_detection.date_column
        2. 默认 'trade_date'
        """
        pass
    
    def is_update_needed(
        self, 
        existing_range: Optional[DateRange], 
        target_range: DateRange
    ) -> bool:
        """判断是否需要更新"""
        pass
```

**日期计算策略表**：

| 接口类型 | 起始日期策略 | 结束日期 | 说明 |
|----------|-------------|---------|------|
| 交易日历 | 1990-01-01 | 今天 | 固定起始日期 |
| 股票基础信息 | 1990-01-01 | 今天 | 固定起始日期 |
| 日线数据 | 现有最新日期或2000-01-01 | 今天 | 可配置 |
| 财务数据 | 现有最新日期 | 今天 | 增量更新 |
| 股东数据 | 现有最新日期 | 今天 | 增量更新 |
| 特色指标 | 现有最新日期 | 今天 | 增量更新 |

### 3.3 InterfaceSelector（接口选择器）

**职责**：
- 根据配置和用户选项选择需要更新的接口
- 支持包含/排除特定接口或组
- 根据积分权限过滤

**类定义**：
```python
class InterfaceSelector:
    def __init__(self, config_loader: ConfigLoader):
        self.config_loader = config_loader
        self.update_config = config_loader.global_config.get('update', {})
    
    def select_interfaces(
        self, 
        options: UpdateOptions
    ) -> List[str]:
        """
        选择需要更新的接口
        
        流程：
        1. 获取所有可用接口
        2. 应用包含/排除规则
        3. 按权限过滤
        4. 按配置顺序排序
        """
        pass
    
    def filter_by_permission(
        self, 
        interfaces: List[str], 
        available_points: int
    ) -> List[str]:
        """根据积分权限过滤接口"""
        pass
    
    def filter_by_group(
        self, 
        interfaces: List[str], 
        group_name: str
    ) -> List[str]:
        """根据组名过滤接口"""
        pass
    
    def apply_exclusions(
        self, 
        interfaces: List[str], 
        exclusions: List[str]
    ) -> List[str]:
        """应用排除规则"""
        pass
    
    def sort_by_update_order(
        self, 
        interfaces: List[str]
    ) -> List[str]:
        """
        按配置的更新顺序排序
        
        未在配置中指定的接口按字母顺序排在最后
        """
        pass
```

### 3.4 UpdateReporter（更新报告器）

**职责**：
- 收集更新过程中的统计信息
- 生成结构化的更新报告
- 支持多种输出格式

**类定义**：
```python
class UpdateReporter:
    def __init__(self):
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.interface_results: List[InterfaceUpdateResult] = []
    
    def record_update_start(self):
        """记录更新开始"""
        self.start_time = datetime.now()
    
    def record_update_end(self):
        """记录更新结束"""
        self.end_time = datetime.now()
    
    def record_interface_start(self, interface_name: str):
        """记录接口更新开始"""
        pass
    
    def record_interface_result(self, result: InterfaceUpdateResult):
        """记录接口更新结果"""
        self.interface_results.append(result)
    
    def generate_report(
        self, 
        format: ReportFormat = ReportFormat.MARKDOWN
    ) -> str:
        """
        生成更新报告
        
        支持格式：
        - MARKDOWN: 适合人工阅读
        - JSON: 适合程序处理
        - HTML: 适合网页展示
        """
        pass
    
    def get_summary(self) -> UpdateSummary:
        """获取更新摘要"""
        pass
    
    def save_report(
        self, 
        filepath: str, 
        format: ReportFormat = ReportFormat.MARKDOWN
    ):
        """保存报告到文件"""
        pass
```

**报告内容结构**：
```
更新报告
├── 概览
│   ├── 开始时间
│   ├── 结束时间
│   ├── 总耗时
│   ├── 总接口数
│   ├── 成功数
│   ├── 跳过数
│   ├── 失败数
│   └── 总记录数
├── 接口详情（列表）
│   ├── 接口名称
│   ├── 状态（成功/跳过/失败）
│   ├── 日期范围
│   ├── 记录数
│   ├── 耗时
│   └── 错误信息（如有）
└── 错误汇总（如有）
```

---

## 4. 数据模型

### 4.1 核心数据类

```python
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Optional, List, Dict, Any


class UpdateStatus(Enum):
    """更新状态"""
    PENDING = auto()      # 等待更新
    RUNNING = auto()      # 更新中
    SUCCESS = auto()      # 更新成功
    SKIPPED = auto()      # 已跳过（已是最新）
    FAILED = auto()       # 更新失败


class ReportFormat(Enum):
    """报告格式"""
    MARKDOWN = "markdown"
    JSON = "json"
    HTML = "html"


@dataclass
class DateRange:
    """日期范围"""
    start_date: str  # YYYYMMDD
    end_date: str    # YYYYMMDD
    
    def is_empty(self) -> bool:
        """是否为空范围"""
        return self.start_date >= self.end_date
    
    def days_between(self) -> int:
        """计算天数差"""
        from datetime import datetime
        start = datetime.strptime(self.start_date, '%Y%m%d')
        end = datetime.strptime(self.end_date, '%Y%m%d')
        return (end - start).days


@dataclass
class UpdateOptions:
    """更新选项"""
    # 接口选择
    interfaces: Optional[List[str]] = None
    exclude: List[str] = field(default_factory=list)
    groups: List[str] = field(default_factory=list)
    
    # 日期范围（强制指定时覆盖智能计算）
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    
    # 更新模式
    force: bool = False           # 强制更新（忽略现有数据）
    dry_run: bool = False         # 预览模式（不实际执行）
    
    # 报告配置
    report_format: ReportFormat = ReportFormat.MARKDOWN
    report_file: Optional[str] = None
    
    # 并发配置
    max_workers: int = 1
    
    # 其他
    log_level: str = "INFO"


@dataclass
class InterfaceUpdateResult:
    """单个接口的更新结果"""
    interface_name: str
    status: UpdateStatus
    date_range: Optional[DateRange] = None
    record_count: int = 0
    duration_seconds: float = 0.0
    error_message: Optional[str] = None
    skip_reason: Optional[str] = None
    
    def __post_init__(self):
        if self.duration_seconds < 0:
            self.duration_seconds = 0


@dataclass
class UpdateResult:
    """整体更新结果"""
    start_time: datetime
    end_time: datetime
    interface_results: List[InterfaceUpdateResult]
    
    @property
    def total_interfaces(self) -> int:
        return len(self.interface_results)
    
    @property
    def success_count(self) -> int:
        return sum(1 for r in self.interface_results 
                   if r.status == UpdateStatus.SUCCESS)
    
    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.interface_results 
                   if r.status == UpdateStatus.FAILED)
    
    @property
    def skipped_count(self) -> int:
        return sum(1 for r in self.interface_results 
                   if r.status == UpdateStatus.SKIPPED)
    
    @property
    def total_records(self) -> int:
        return sum(r.record_count for r in self.interface_results)
    
    @property
    def duration_seconds(self) -> float:
        return (self.end_time - self.start_time).total_seconds()
    
    @property
    def is_success(self) -> bool:
        return self.failed_count == 0


@dataclass
class UpdateSummary:
    """更新摘要"""
    total: int
    success: int
    failed: int
    skipped: int
    total_records: int
    duration_seconds: float
    success_rate: float
    
    def __post_init__(self):
        if self.total > 0:
            self.success_rate = (self.success + self.skipped) / self.total
        else:
            self.success_rate = 0.0
```

---

## 5. 配置设计

### 5.1 settings.yaml 新增配置

```yaml
# 增量更新模块配置
update:
  enabled: true
  
  # 默认更新策略
  default_strategy:
    start_date: "20000101"      # 默认起始日期
    lookback_days: 7            # 回溯天数（处理数据延迟）
    end_date: "today"           # 结束日期，支持 "today" 或具体日期
  
  # 特殊接口配置
  special_interfaces:
    trade_cal:
      start_date: "19900101"
      update_frequency: "weekly"
      date_column: "cal_date"
    
    stock_basic:
      start_date: "19900101"
      update_frequency: "daily"
      date_column: "list_date"
    
    daily:
      start_date: "20000101"
      date_column: "trade_date"
    
    daily_basic:
      start_date: "20000101"
      date_column: "trade_date"
    
    # 财务数据类
    income_vip:
      date_column: "end_date"
    balancesheet_vip:
      date_column: "end_date"
    cashflow_vip:
      date_column: "end_date"
    fina_indicator_vip:
      date_column: "end_date"
    
    # 股东数据类
    top10_holders:
      date_column: "end_date"
    top10_floatholders:
      date_column: "end_date"
    stk_rewards:
      date_column: "end_date"
  
  # 排除接口（不自动更新）
  excluded_interfaces:
    - stock_basic      # 基础数据通常不需要频繁更新
    - trade_cal        # 交易日历更新频率低
  
  # 更新顺序（按依赖关系）
  # 未在此列表中的接口按字母顺序排在最后
  update_order:
    - trade_cal
    - stock_basic
    - daily
    - daily_basic
    - moneyflow
    - income_vip
    - balancesheet_vip
    - cashflow_vip
    - fina_indicator_vip
    - fina_mainbz_vip
    - express_vip
    - forecast_vip
    - fina_audit
    - disclosure_date
    - top10_holders
    - top10_floatholders
    - pledge_stat
    - pledge_detail
    - dividend
    - stk_rewards
  
  # 并发配置
  concurrency:
    max_parallel_interfaces: 1  # 同时更新的接口数
    retry_failed: true          # 失败时是否重试
    max_retries: 3
    retry_delay: 2.0            # 重试延迟（秒）
  
  # 报告配置
  reporting:
    enabled: true
    output_format: "markdown"
    save_report: true
    report_dir: "log/update_reports/"
    console_output: true
  
  # 容错配置
  fault_tolerance:
    skip_on_error: true         # 出错时跳过继续
    stop_on_storage_error: true # 存储错误时停止
    max_consecutive_errors: 5   # 最大连续错误数
  
  # 断点续传配置
  checkpoint:
    enabled: true               # 启用断点续传
    file: "data/.update_checkpoint.json"  # 断点文件路径
    interval: 10                # 每N个接口保存一次断点
    auto_resume: true           # 启动时自动检测并恢复断点
```

### 5.2 命令行参数

```python
# main.py 中添加的参数
parser.add_argument('--update', 
                    action='store_true',
                    help='启用增量更新模式')

parser.add_argument('--update-interface', 
                    type=str, 
                    action='append',
                    dest='update_interfaces',
                    help='指定要更新的接口（可多次使用）')

parser.add_argument('--update-group', 
                    type=str, 
                    action='append',
                    dest='update_groups',
                    help='指定要更新的接口组（可多次使用）')

parser.add_argument('--update-exclude', 
                    type=str, 
                    action='append',
                    dest='update_exclusions',
                    help='排除特定接口（可多次使用）')

parser.add_argument('--update-force', 
                    action='store_true',
                    dest='update_force',
                    help='强制更新（忽略现有数据）')

parser.add_argument('--update-dry-run', 
                    action='store_true',
                    dest='update_dry_run',
                    help='预览模式（不实际执行）')

parser.add_argument('--update-report-format', 
                    type=str,
                    choices=['markdown', 'json', 'html'],
                    default='markdown',
                    dest='update_report_format',
                    help='报告格式')

parser.add_argument('--update-report-file', 
                    type=str,
                    dest='update_report_file',
                    help='报告输出文件路径')
```

### 5.3 使用示例

```bash
# 基础用法：更新所有接口
python app4/main.py --update

# 指定特定接口
python app4/main.py --update --update-interface daily_basic --update-interface moneyflow

# 指定接口组
python app4/main.py --update --update-group daily --update-group financial_vip

# 排除特定接口
python app4/main.py --update --update-exclude stock_basic --update-exclude trade_cal

# 强制更新（忽略现有数据）
python app4/main.py --update --update-force

# 预览模式
python app4/main.py --update --update-dry-run

# 生成JSON报告
python app4/main.py --update --update-report-format json --update-report-file update_result.json

# 组合使用
python app4/main.py --update \
    --update-group daily \
    --update-exclude daily_basic \
    --update-report-format markdown \
    --update-report-file reports/update_$(date +%Y%m%d).md
```

---

## 6. 与现有代码的集成

### 6.1 修改点清单

| 文件 | 修改类型 | 修改内容 |
|------|---------|---------|
| `main.py` | 新增 | 添加 `--update` 相关参数解析 |
| `main.py` | 新增 | 添加 `run_update_mode()` 函数 |
| `config/settings.yaml` | 新增 | 添加 `update:` 配置段 |
| `update/__init__.py` | 新增 | 模块初始化，导出公共接口 |
| `update/update_manager.py` | 新增 | UpdateManager 实现 |
| `update/date_calculator.py` | 新增 | DateCalculator 实现 |
| `update/update_reporter.py` | 新增 | UpdateReporter 实现 |
| `update/interface_selector.py` | 新增 | InterfaceSelector 实现 |

### 6.2 复用的现有组件

| 组件 | 复用方式 | 说明 |
|------|---------|------|
| `ConfigLoader` | 构造函数注入 | 获取接口配置和全局配置 |
| `StorageManager` | 构造函数注入 | 读取现有数据、保存新数据 |
| `GenericDownloader` | 构造函数注入 | 执行实际下载 |
| `TaskScheduler` | 构造函数注入 | 并发任务调度 |
| `DataProcessor` | 构造函数注入 | 数据处理 |
| `RateLimiter` | 构造函数注入 | 速率限制 |
| `CoverageManager` | 通过 downloader 获取 | **数据覆盖检测，使用 should_skip()** |
| `PaginationExecutor` | 通过 downloader 获取 | **执行分页下载逻辑** |

### 6.3 复用机制详细说明

#### CoverageManager 复用
```python
# UpdateManager 中复用 CoverageManager
class UpdateManager:
    def __init__(self, ..., downloader: GenericDownloader):
        # 直接复用 downloader 中的 coverage_manager
        self.coverage_manager = downloader.coverage_manager
    
    def should_update_interface(self, interface_name, date_range, options):
        if options.force:
            return True, None
        
        # 复用 CoverageManager.should_skip() 方法
        params = {
            'start_date': date_range.start_date,
            'end_date': date_range.end_date
        }
        should_skip = self.coverage_manager.should_skip(
            interface_name, 
            params, 
            strategy='auto'
        )
        
        if should_skip:
            return False, "数据已覆盖"
        return True, None
```

#### PaginationExecutor 复用
```python
# UpdateManager 中复用 PaginationExecutor
class UpdateManager:
    def update_interface(self, interface_name, options):
        interface_config = self.config_loader.get_interface_config(interface_name)
        date_range = self.date_calculator.calculate_update_range(interface_name)
        
        # 构建参数
        params = {
            'start_date': date_range.start_date,
            'end_date': date_range.end_date
        }
        
        # 复用 PaginationExecutor 执行分页
        pagination_config = interface_config.get('pagination', {})
        mode = pagination_config.get('mode', 'offset')
        
        if mode == 'date_range':
            return self.pagination_executor.execute_date_range_pagination(
                interface_config, params, context, 
                self.downloader._make_request,
                coverage_manager=self.coverage_manager,
                force_download=options.force,
                get_trade_calendar_callback=self.downloader.get_trade_calendar
            )
        elif mode == 'stock_loop':
            return self.pagination_executor.execute_stock_loop_pagination(
                interface_config, params, context,
                self.downloader._make_request,
                get_stock_list_callback=self.downloader._get_stock_list,
                coverage_manager=self.coverage_manager,
                force_download=options.force
            )
        # ... 其他模式
```

### 6.4 不修改的现有代码

以下文件保持原样，不做任何修改：
- `core/pagination_executor.py`
- `core/downloader.py`
- `core/coverage_manager.py`
- `core/storage.py`
- `core/processor.py`
- `core/scheduler.py`
- `config/interfaces/*.yaml`

### 6.5 与现有 `--incremental` 参数的关系

**决策**：`--update` 替代 `--incremental`，保持 `--incremental` 作为兼容别名

```python
# main.py 参数定义
def parse_arguments():
    parser = argparse.ArgumentParser()
    
    # 新的更新模式参数（推荐）
    parser.add_argument('--update', 
                        action='store_true',
                        help='启用增量更新模式（推荐）')
    
    # 现有参数（保持兼容，标记为弃用）
    parser.add_argument('--incremental', 
                        action='store_true',
                        help='[已弃用，请使用 --update] 增量模式')
    
    # ... 其他参数
    return parser.parse_args()

def main():
    args = parse_arguments()
    
    # 处理参数兼容性
    if args.incremental and not args.update:
        logger.warning("--incremental 已弃用，请使用 --update")
        args.update = True
    
    if args.update:
        return run_update_mode(args, ...)
```

**行为对比**：

| 参数 | 行为 | 状态 |
|------|------|------|
| `--update` | 智能增量更新，自动计算日期范围 | 推荐 |
| `--incremental` | 同 `--update`，但输出弃用警告 | 兼容保留 |

---

## 7. 错误处理策略

### 7.1 错误分类与处理

| 错误类型 | 示例 | 处理策略 | 是否继续 |
|----------|------|---------|---------|
| 配置错误 | 接口不存在 | 记录错误，跳过该接口 | 是 |
| 权限错误 | 积分不足 | 记录警告，跳过该接口 | 是 |
| 网络超时 | 请求超时 | 重试3次后跳过 | 是 |
| API限制 | 频率限制 | 等待后重试 | 是 |
| 数据解析错误 | 格式异常 | 记录错误，跳过该接口 | 是 |
| 存储错误 | 写入失败 | 记录错误，停止更新 | 否 |
| 连续错误 | 多次失败 | 记录错误，停止更新 | 否 |

### 7.2 重试机制

```python
class RetryPolicy:
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 2.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
    
    def calculate_delay(self, attempt: int) -> float:
        """计算重试延迟（指数退避）"""
        delay = self.base_delay * (self.exponential_base ** attempt)
        return min(delay, self.max_delay)
    
    def should_retry(self, error: Exception, attempt: int) -> bool:
        """判断是否应重试"""
        if attempt >= self.max_retries:
            return False
        
        # 某些错误不应重试
        if isinstance(error, (PermissionError, ConfigurationError)):
            return False
        
        return True
```

---

## 8. 测试策略

### 8.1 单元测试

| 测试目标 | 测试内容 | 测试文件 |
|----------|---------|---------|
| DateCalculator | 日期计算、边界条件、特殊接口 | `test_date_calculator.py` |
| UpdateReporter | 统计收集、报告生成 | `test_update_reporter.py` |
| InterfaceSelector | 过滤逻辑、权限检查 | `test_interface_selector.py` |
| UpdateManager | 流程协调、异常处理 | `test_update_manager.py` |

### 8.2 集成测试

| 测试场景 | 测试内容 | 测试文件 |
|----------|---------|---------|
| 完整更新流程 | 从规划到报告的全流程 | `test_integration.py` |
| 部分接口更新 | 指定接口或组的更新 | `test_integration.py` |
| 错误恢复 | 模拟接口失败后的处理 | `test_integration.py` |
| 并发更新 | 多个接口的并发处理 | `test_integration.py` |

### 8.3 手动测试清单

- [ ] 首次更新（无现有数据）
- [ ] 增量更新（有现有数据）
- [ ] 强制更新（覆盖现有数据）
- [ ] 预览模式（--dry-run）
- [ ] 指定接口更新
- [ ] 指定组更新
- [ ] 排除接口更新
- [ ] 失败接口处理
- [ ] 报告生成（各种格式）
- [ ] 配置加载验证
- [ ] 权限过滤验证
- [ ] 日期计算验证

---

## 9. 断点续传机制

### 9.1 CheckpointManager（断点管理器）

**职责**：
- 保存更新进度到文件
- 恢复更新进度
- 管理断点文件生命周期

**类定义**：
```python
class CheckpointManager:
    def __init__(self, config: Dict[str, Any]):
        self.enabled = config.get('enabled', True)
        self.filepath = config.get('file', 'data/.update_checkpoint.json')
        self.interval = config.get('interval', 10)
        self.auto_resume = config.get('auto_resume', True)
        
        self._checkpoint_data = {
            'version': '1.0',
            'created_at': None,
            'updated_at': None,
            'completed_interfaces': [],
            'failed_interfaces': {},
            'current_interface': None,
            'options': {}
        }
    
    def load_checkpoint(self) -> Optional[Dict[str, Any]]:
        """加载断点文件"""
        if not self.enabled or not os.path.exists(self.filepath):
            return None
        
        try:
            with open(self.filepath, 'r') as f:
                data = json.load(f)
            logger.info(f"加载断点文件: {self.filepath}")
            return data
        except Exception as e:
            logger.warning(f"加载断点文件失败: {e}")
            return None
    
    def save_checkpoint(self):
        """保存断点文件"""
        if not self.enabled:
            return
        
        self._checkpoint_data['updated_at'] = datetime.now().isoformat()
        
        try:
            os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
            with open(self.filepath, 'w') as f:
                json.dump(self._checkpoint_data, f, indent=2)
        except Exception as e:
            logger.warning(f"保存断点文件失败: {e}")
    
    def record_interface_start(self, interface_name: str):
        """记录接口开始"""
        self._checkpoint_data['current_interface'] = interface_name
    
    def record_interface_complete(self, interface_name: str, success: bool):
        """记录接口完成"""
        if success:
            self._checkpoint_data['completed_interfaces'].append(interface_name)
        else:
            self._checkpoint_data['failed_interfaces'][interface_name] = {
                'timestamp': datetime.now().isoformat()
            }
        self._checkpoint_data['current_interface'] = None
        
        # 按间隔保存
        total_completed = len(self._checkpoint_data['completed_interfaces'])
        if total_completed % self.interval == 0:
            self.save_checkpoint()
    
    def is_interface_completed(self, interface_name: str) -> bool:
        """检查接口是否已完成"""
        return interface_name in self._checkpoint_data['completed_interfaces']
    
    def clear_checkpoint(self):
        """清除断点文件"""
        if os.path.exists(self.filepath):
            os.remove(self.filepath)
            logger.info(f"清除断点文件: {self.filepath}")
    
    def get_resume_interfaces(self, all_interfaces: List[str]) -> List[str]:
        """获取需要恢复更新的接口列表"""
        completed = set(self._checkpoint_data['completed_interfaces'])
        return [i for i in all_interfaces if i not in completed]
```

### 9.2 断点续传流程

```
开始更新
    │
    ▼
[检查断点文件]
    │
    ├── 存在且 auto_resume=True
    │   ├── 加载断点
    │   ├── 提示用户恢复或重新开始
    │   └── 根据选择继续或清除
    │
    └── 不存在或 auto_resume=False
        └── 正常开始
    │
    ▼
[执行更新] ←────────────────────────┐
    │                                 │
    ├── 记录接口开始 ──→ 保存断点     │
    │                                 │
    ├── 执行更新                      │
    │                                 │
    └── 记录接口完成 ──→ 保存断点 ────┤
    │                                 │
    ▼                                 │
[检查中断] ──→ 是 ──→ 保存断点并退出 │
    │否                               │
    ▼                                 │
[继续下一个] ───────────────────────┘
    │
    ▼
[更新完成]
    ├── 清除断点文件
    └── 生成最终报告
```

### 9.3 使用示例

```bash
# 正常更新（自动支持断点续传）
python app4/main.py --update

# 如果中断了，再次运行会自动恢复
python app4/main.py --update
# 输出: "检测到未完成的更新，已恢复进度。已完成: 5/20 个接口"

# 强制重新开始（忽略断点）
python app4/main.py --update --update-force

# 禁用断点续传
# 在 settings.yaml 中设置:
# update:
#   checkpoint:
#     enabled: false
```

---

## 10. 扩展性设计

### 10.1 未来扩展点

| 扩展方向 | 实现方式 | 优先级 |
|----------|---------|--------|
| 定时自动更新 | 添加 scheduler 集成点 | 中 |
| 增量更新策略定制 | 添加 UpdateStrategy 接口 | 低 |
| 多数据源支持 | 抽象 DataSource 接口 | 低 |
| 更新历史记录 | 添加 UpdateHistory 存储 | 中 |
| 增量更新API | 暴露 REST API 接口 | 低 |
| 并行接口更新 | 增强并发控制 | 中 |

### 10.2 插件机制（可选未来特性）

```python
class UpdatePlugin:
    """更新插件基类"""
    
    def before_update_start(self, options: UpdateOptions):
        """更新开始前调用"""
        pass
    
    def before_interface_update(
        self, 
        interface_name: str, 
        date_range: DateRange
    ):
        """接口更新前调用"""
        pass
    
    def after_interface_update(self, result: InterfaceUpdateResult):
        """接口更新后调用"""
        pass
    
    def after_update_complete(self, result: UpdateResult):
        """更新完成后调用"""
        pass
```

---

## 11. 实施计划

### 阶段一：基础框架（2天）

- [ ] 创建 `update/` 目录结构
- [ ] 实现 `DateCalculator` 类
- [ ] 实现 `UpdateReporter` 类
- [ ] 实现 `InterfaceSelector` 类
- [ ] 实现 `CheckpointManager` 类（断点续传）
- [ ] 编写单元测试

### 阶段二：核心逻辑（3天）

- [ ] 实现 `UpdateManager` 类（复用 CoverageManager 和 PaginationExecutor）
- [ ] 实现 `run_update_mode()` 函数
- [ ] 在 `main.py` 中添加参数解析（处理 --update 和 --incremental 关系）
- [ ] 在 `settings.yaml` 中添加配置（包含 checkpoint 配置）
- [ ] 编写集成测试

### 阶段三：测试与优化（2天）

- [ ] 执行手动测试清单
- [ ] 性能测试和优化
- [ ] 错误场景测试
- [ ] 边界条件测试
- [ ] 断点续传测试

### 阶段四：文档（1天）

- [ ] 使用文档
- [ ] 配置文档
- [ ] 故障排查指南
- [ ] API 文档（如有）

**总计：约 8 个工作日**
- [ ] 错误场景测试
- [ ] 边界条件测试

### 阶段四：文档（1天）

- [ ] 使用文档
- [ ] 配置文档
- [ ] 故障排查指南
- [ ] API 文档（如有）

**总计：约 8 个工作日**

---

## 11. 风险与缓解

| 风险 | 影响 | 可能性 | 缓解措施 |
|------|------|--------|---------|
| API 限制导致更新失败 | 高 | 中 | 实现重试机制、降低并发度、添加延迟 |
| 数据量过大导致内存溢出 | 中 | 低 | 使用流式处理、分批写入 |
| 配置错误导致更新错误数据 | 高 | 低 | 严格配置验证、预览模式 |
| 更新过程中断导致数据不一致 | 中 | 中 | 使用事务性写入、支持断点续传 |
| 接口变更导致解析失败 | 中 | 低 | 添加版本检查、优雅降级 |
| 并发冲突 | 中 | 低 | 使用锁机制、串行化处理 |

---

## 12. 附录

### 12.1 术语表

| 术语 | 说明 |
|------|------|
| 增量更新 | 只下载新增或变更的数据，避免重复下载 |
| 全量更新 | 下载指定范围内的全部数据 |
| 强制更新 | 忽略现有数据，重新下载 |
| 预览模式 | 只计算需要更新的内容，不实际执行 |
| 日期锚定 | 使用特定日期参数遍历数据的模式 |
| 覆盖率 | 已有数据占期望数据的比例 |

### 12.2 参考文档

- App4 现有架构文档
- Tushare Pro API 文档
- 现有接口配置说明

### 12.3 变更历史

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|---------|------|
| 1.0 | 2026-02-05 | 初始版本 | AI Assistant |
| 2.0 | 2026-02-05 | 整合工程团队建议，完善设计 | AI Assistant |

---

## 13. 总结

本方案设计了一个独立的增量更新模块，具有以下核心特点：

1. **完全独立**：新模块放在 `app4/update/` 目录下，不侵入现有核心代码
2. **组件化设计**：清晰的职责划分，便于测试和维护
3. **配置驱动**：通过 `settings.yaml` 灵活配置更新行为
4. **智能计算**：自动检测现有数据，智能计算更新范围
5. **完善报告**：支持多种格式的更新报告
6. **容错性强**：完善的错误处理和恢复机制
7. **可扩展**：预留扩展点，支持未来功能增强

该方案充分利用了 App4 现有的成熟组件，在其基础上构建更高层次的更新协调逻辑，实现真正的"一键智能增量更新"功能。
