"""
增量更新模块数据模型
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Optional, List, Dict, Any

# 从 core 导入 DateRange
from core.date_utils import DateRange


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

    # 缺口检测配置
    gap_detection_enabled: bool = True   # 是否启用缺口检测
    min_gap_days: int = 1                # 最小缺口天数（小于此值的缺口忽略）
    max_gaps: int = 50                   # 最大缺口数量（超过则全量下载）

    # 报告配置
    report_format: ReportFormat = ReportFormat.MARKDOWN
    report_file: Optional[str] = None

    # 并发配置
    max_workers: int = 1

    # 其他
    log_level: str = "INFO"

    # 指定股票代码（用于股票级别缺口检测）
    ts_code: Optional[str] = None


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
    success_rate: float = 0.0
    
    def __post_init__(self):
        if self.total > 0:
            self.success_rate = (self.success + self.skipped) / self.total
        else:
            self.success_rate = 0.0
