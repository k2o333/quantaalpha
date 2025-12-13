"""
日期处理工具
"""
import pandas as pd
from datetime import datetime, timedelta
from typing import List
import logging


class DateRangeProcessor:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def get_trading_days(self, start_date: str, end_date: str, api_manager) -> List[str]:
        """获取指定日期范围内的交易日列表"""
        try:
            # 先下载交易日历数据
            trade_cal = api_manager.basic_data.download_trade_cal(
                start_date=start_date,
                end_date=end_date
            )

            # 过滤出交易日（is_open=1）
            trading_days = trade_cal[trade_cal['is_open'] == 1]['cal_date'].tolist()
            trading_days.sort()

            self.logger.info(f"获取到 {len(trading_days)} 个交易日")
            return trading_days

        except Exception as e:
            self.logger.error(f"获取交易日历失败: {e}")
            # 如果无法获取交易日历，返回日期范围内的所有日期作为备选
            return self._generate_date_range(start_date, end_date)

    def _generate_date_range(self, start_date: str, end_date: str) -> List[str]:
        """生成日期范围内的所有日期（作为备选方案）"""
        start = datetime.strptime(start_date, '%Y%m%d')
        end = datetime.strptime(end_date, '%Y%m%d')

        date_list = []
        current = start
        while current <= end:
            date_list.append(current.strftime('%Y%m%d'))
            current += timedelta(days=1)

        return date_list