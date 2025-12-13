"""
股东数据接口实现
"""
from base import BaseDownloader
import pandas as pd


class HoldersDataDownloader(BaseDownloader):
    def __init__(self, pro_api, config_manager):
        super().__init__(pro_api, config_manager)

    def download_top10_holders(self, ts_code=None, period='20231231'):
        """下载前十大股东"""
        # 检查积分要求
        if not self.check_points_requirement(2000):
            self.logger.warning("top10_holders requires 2000+ points, skipping download")
            return pd.DataFrame()

        api_func = getattr(self.pro, 'top10_holders')
        return self.safe_download(
            api_func,
            ts_code=ts_code,
            period=period
        )

    def download_stk_rewards(self, ts_code=None):
        """下载管理层薪酬和持股"""
        # 检查积分要求
        if not self.check_points_requirement(2000):
            self.logger.warning("stk_rewards requires 2000+ points, skipping download")
            return pd.DataFrame()

        api_func = getattr(self.pro, 'stk_rewards')
        return self.safe_download(
            api_func,
            ts_code=ts_code
        )

    def download_stk_managers(self, ts_code=None):
        """下载上市公司管理层"""
        # 检查积分要求
        if not self.check_points_requirement(2000):
            self.logger.warning("stk_managers requires 2000+ points, skipping download")
            return pd.DataFrame()

        api_func = getattr(self.pro, 'stk_managers')
        return self.safe_download(
            api_func,
            ts_code=ts_code
        )

    def download_top10_floatholders(self, ts_code=None, period='20231231'):
        """下载前十大流通股东"""
        # 检查积分要求
        if not self.check_points_requirement(5000):
            self.logger.warning("top10_floatholders requires 5000+ points, skipping download")
            return pd.DataFrame()

        api_func = getattr(self.pro, 'top10_floatholders')
        return self.safe_download(
            api_func,
            ts_code=ts_code,
            period=period
        )

    def download_stk_holdertrade(self, start_date='20230101', end_date='20231231'):
        """下载股东增减持"""
        # 检查积分要求
        if not self.check_points_requirement(5000):
            self.logger.warning("stk_holdertrade requires 5000+ points, skipping download")
            return pd.DataFrame()

        api_func = getattr(self.pro, 'stk_holdertrade')
        return self.safe_download(
            api_func,
            start_date=start_date,
            end_date=end_date
        )