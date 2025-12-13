"""
市场结构接口实现
"""
from base import BaseDownloader
import pandas as pd


class MarketStructureDownloader(BaseDownloader):
    def __init__(self, pro_api, config_manager):
        super().__init__(pro_api, config_manager)

    def download_cyq_perf(self, trade_date=None, ts_code=None):
        """下载每日筹码及胜率"""
        # 检查积分要求
        if not self.check_points_requirement(5000):
            self.logger.warning("cyq_perf requires 5000+ points, skipping download")
            return pd.DataFrame()

        api_func = getattr(self.pro, 'cyq_perf')
        return self.safe_download(
            api_func,
            trade_date=trade_date,
            ts_code=ts_code
        )

    def download_cyq_chips(self, trade_date=None, ts_code=None):
        """下载每日筹码分布"""
        # 检查积分要求
        if not self.check_points_requirement(5000):
            self.logger.warning("cyq_chips requires 5000+ points, skipping download")
            return pd.DataFrame()

        api_func = getattr(self.pro, 'cyq_chips')
        return self.safe_download(
            api_func,
            trade_date=trade_date,
            ts_code=ts_code
        )

    def download_suspend_d(self, start_date=None, end_date=None):
        """下载每日停复牌信息"""
        # 检查积分要求
        if not self.check_points_requirement(500):
            self.logger.warning("suspend_d requires 500+ points, skipping download")
            return pd.DataFrame()

        api_func = getattr(self.pro, 'suspend_d')
        return self.safe_download(
            api_func,
            start_date=start_date,
            end_date=end_date
        )

    def download_block_trade(self, start_date=None, end_date=None):
        """下载大宗交易"""
        # 检查积分要求
        if not self.check_points_requirement(500):
            self.logger.warning("block_trade requires 500+ points, skipping download")
            return pd.DataFrame()

        api_func = getattr(self.pro, 'block_trade')
        return self.safe_download(
            api_func,
            start_date=start_date,
            end_date=end_date
        )

    def download_share_float(self, start_date=None, end_date=None):
        """下载限售股解禁"""
        # 检查积分要求
        if not self.check_points_requirement(500):
            self.logger.warning("share_float requires 500+ points, skipping download")
            return pd.DataFrame()

        api_func = getattr(self.pro, 'share_float')
        return self.safe_download(
            api_func,
            start_date=start_date,
            end_date=end_date
        )