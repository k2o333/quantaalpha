"""
日度数据接口实现
"""
from base import BaseDownloader
import pandas as pd


class DailyDataDownloader(BaseDownloader):
    def __init__(self, pro_api, config_manager):
        super().__init__(pro_api, config_manager)

    def download_daily_data(self, ts_code=None, start_date=None, end_date=None):
        """下载日线数据"""
        api_func = getattr(self.pro, 'daily')
        return self.safe_download(
            api_func,
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date
        )

    def download_daily_basic(self, trade_date=None, ts_code=None, start_date=None, end_date=None):
        """下载每日指标数据"""
        api_func = getattr(self.pro, 'daily_basic')
        return self.safe_download(
            api_func,
            trade_date=trade_date,
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date
        )