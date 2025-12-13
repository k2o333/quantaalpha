"""
技术因子接口实现
"""
from base import BaseDownloader
import pandas as pd


class TechnicalFactorsDownloader(BaseDownloader):
    def __init__(self, pro_api, config_manager):
        super().__init__(pro_api, config_manager)

    def download_stk_factor(self, trade_date=None, ts_code=None):
        """下载股票技术因子"""
        # 检查积分要求
        if not self.check_points_requirement(5000):
            self.logger.warning("stk_factor requires 5000+ points, skipping download")
            return pd.DataFrame()

        api_func = getattr(self.pro, 'stk_factor')
        return self.safe_download(
            api_func,
            trade_date=trade_date,
            ts_code=ts_code
        )

    def download_stk_factor_pro(self, trade_date=None, ts_code=None):
        """下载股票技术面因子(专业版)"""
        # 检查积分要求
        if not self.check_points_requirement(5000):
            self.logger.warning("stk_factor_pro requires 5000+ points, skipping download")
            return pd.DataFrame()

        api_func = getattr(self.pro, 'stk_factor_pro')
        return self.safe_download(
            api_func,
            trade_date=trade_date,
            ts_code=ts_code
        )

    def download_cyq_perf_paginated(self, trade_date=None, ts_code=None):
        """下载每日筹码及胜率(分页)"""
        return self.download_cyq_perf(trade_date=trade_date, ts_code=ts_code)

    def download_cyq_chips_paginated(self, trade_date=None, ts_code=None):
        """下载每日筹码分布(分页)"""
        return self.download_cyq_chips(trade_date=trade_date, ts_code=ts_code)

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