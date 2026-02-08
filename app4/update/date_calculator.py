"""
日期范围计算器 - 重构后版本
智能计算每个接口的更新日期范围
"""
import logging
import os
from datetime import datetime, timedelta
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
    
    # 特殊接口默认起始日期
    DEFAULT_START_DATES = {
        'trade_cal': '19900101',
        'stock_basic': '19900101',
        'stock_company': '19900101',
        'daily': '20000101',
        'daily_basic': '20000101',
        'pro_bar': '20000101',
    }
    
    def __init__(
        self, 
        config_loader, 
        storage_manager
    ):
        self.config_loader = config_loader
        self.storage_manager = storage_manager
        
        # 加载更新配置
        self.update_config = config_loader.global_config.get('update', {})
        self.default_strategy = self.update_config.get('default_strategy', {})
        self.special_interfaces = self.update_config.get('special_interfaces', {})
        
        # 默认回溯天数（处理数据延迟）
        self.lookback_days = self.default_strategy.get('lookback_days', 7)
    
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
        
        Args:
            interface_name: 接口名称
            forced_start: 强制起始日期（YYYYMMDD）
            forced_end: 强制结束日期（YYYYMMDD）
            
        Returns:
            DateRange: 日期范围对象
        """
        # 如果强制指定了日期范围，直接使用
        if forced_start and forced_end:
            logger.info(f"[{interface_name}] 使用强制指定的日期范围: {forced_start} ~ {forced_end}")
            return DateRange(start_date=forced_start, end_date=forced_end)
        
        # 获取现有数据的日期范围
        existing_range = self._get_existing_data_range(interface_name)
        
        # 确定起始日期
        if forced_start:
            start_date = forced_start
        elif existing_range:
            # 从现有数据的最新日期开始，向前回溯一定天数
            start_date = self._calculate_start_with_lookback(
                existing_range.end_date, 
                interface_name
            )
            logger.info(f"[{interface_name}] 现有数据到 {existing_range.end_date}，回溯至 {start_date}")
        else:
            # 没有现有数据，使用默认起始日期
            start_date = self._get_default_start_date(interface_name)
            logger.info(f"[{interface_name}] 无现有数据，使用默认起始日期: {start_date}")
        
        # 确定结束日期
        if forced_end:
            end_date = forced_end
        else:
            end_date = datetime.now().strftime('%Y%m%d')
        
        # 验证日期范围
        if start_date > end_date:
            logger.warning(f"[{interface_name}] 计算的起始日期 {start_date} 大于结束日期 {end_date}，调整为相同")
            start_date = end_date
        
        return DateRange(start_date=start_date, end_date=end_date)
    
    def _get_existing_data_range(
        self,
        interface_name: str
    ) -> Optional[DateRange]:
        """获取接口现有数据的日期范围 - 使用统一的日期工具"""
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
    
    def _get_interface_date_column(self, interface_name: str) -> Optional[str]:
        """获取接口的日期列名 - 使用统一工具"""
        # 首先检查特殊接口配置
        special_config = self.special_interfaces.get(interface_name, {})
        if 'date_column' in special_config:
            return special_config['date_column']

        # 然后使用统一工具从接口配置中检测
        try:
            interface_config = self.config_loader.get_interface_config(interface_name)
            return detect_date_column(interface_config) or 'trade_date'
        except Exception:
            return 'trade_date'
    
    def _get_default_start_date(self, interface_name: str) -> str:
        """
        获取接口的默认起始日期
        
        Args:
            interface_name: 接口名称
            
        Returns:
            str: 默认起始日期（YYYYMMDD）
        """
        # 从特殊接口配置中查找
        special_config = self.special_interfaces.get(interface_name, {})
        if 'start_date' in special_config:
            return special_config['start_date']
        
        # 从默认配置中查找
        default_start = self.default_strategy.get('start_date')
        if default_start:
            return default_start
        
        # 使用预定义的默认值
        for key, value in self.DEFAULT_START_DATES.items():
            if key in interface_name:
                return value
        
        # 最终默认值
        return '20000101'
    
    def _calculate_start_with_lookback(
        self,
        end_date: str,
        interface_name: str
    ) -> str:
        """计算带有回溯天数的起始日期 - 使用统一工具"""
        special_config = self.special_interfaces.get(interface_name, {})
        lookback = special_config.get('lookback_days', self.lookback_days)
        return calculate_start_with_lookback(end_date, lookback)
    
    def _format_date(self, date_value) -> Optional[str]:
        """将日期值格式化为 YYYYMMDD 字符串 - 使用统一工具"""
        return format_date(date_value)
    
    def is_update_needed(
        self, 
        existing_range: Optional[DateRange], 
        target_range: DateRange
    ) -> bool:
        """
        判断是否需要更新
        
        Args:
            existing_range: 现有数据的日期范围
            target_range: 目标更新日期范围
            
        Returns:
            bool: 是否需要更新
        """
        if not existing_range:
            # 没有现有数据，需要更新
            return True
        
        # 如果目标结束日期大于现有结束日期，需要更新
        if target_range.end_date > existing_range.end_date:
            return True
        
        # 如果目标起始日期小于现有起始日期，可能需要回填数据
        if target_range.start_date < existing_range.start_date:
            return True
        
        return False
