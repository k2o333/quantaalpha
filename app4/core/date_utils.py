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

    def __repr__(self) -> str:
        return f"DateRange({self.start_date}, {self.end_date})"

    def __eq__(self, other) -> bool:
        if not isinstance(other, DateRange):
            return False
        return self.start_date == other.start_date and self.end_date == other.end_date

    def days_between(self) -> int:
        """计算两个日期之间的天数（不包含结束日）"""
        start = datetime.strptime(self.start_date, '%Y%m%d')
        end = datetime.strptime(self.end_date, '%Y%m%d')
        return (end - start).days

    def contains(self, date_str: str) -> bool:
        """检查日期是否在范围内"""
        return self.start_date <= date_str <= self.end_date

    def is_empty(self) -> bool:
        """是否为空范围"""
        return self.start_date > self.end_date


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
    
    return None


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


def days_between(start_date: str, end_date: str) -> int:
    """
    计算两个日期之间的天数（包含首尾）
    
    Args:
        start_date: 起始日期（YYYYMMDD）
        end_date: 结束日期（YYYYMMDD）
        
    Returns:
        int: 天数（包含首尾）
    """
    try:
        start = datetime.strptime(start_date, '%Y%m%d')
        end = datetime.strptime(end_date, '%Y%m%d')
        return (end - start).days + 1
    except (ValueError, TypeError):
        return 0


def is_next_trade_day(current: str, next_date: str) -> bool:
    """
    检查是否是连续的交易日（考虑周末和节假日）
    
    Args:
        current: 当前日期（YYYYMMDD）
        next_date: 下一个日期（YYYYMMDD）
        
    Returns:
        bool: 是否是连续的交易日
    """
    try:
        current_dt = datetime.strptime(current, '%Y%m%d')
        next_dt = datetime.strptime(next_date, '%Y%m%d')

        # 计算日期差
        delta = (next_dt - current_dt).days

        # 如果是连续的（相差1天）
        if delta == 1:
            return True

        return False

    except (ValueError, TypeError):
        return False
