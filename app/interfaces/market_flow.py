"""
资金流向接口实现
"""
from base import BaseDownloader
import pandas as pd


class MarketFlowDownloader(BaseDownloader):
    def __init__(self, pro_api, config_manager):
        super().__init__(pro_api, config_manager)

    def download_moneyflow(self, trade_date=None, ts_code=None, start_date=None, end_date=None):
        """下载个股资金流向"""
        # 检查积分要求
        if not self.check_points_requirement(2000):
            self.logger.warning("moneyflow requires 2000+ points, skipping download")
            return pd.DataFrame()

        api_func = getattr(self.pro, 'moneyflow')
        return self.safe_download(
            api_func,
            trade_date=trade_date,
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date
        )

    def download_moneyflow_ths(self, trade_date=None):
        """下载个股资金流向(同花顺)"""
        # 检查积分要求
        if not self.check_points_requirement(5000):
            self.logger.warning("moneyflow_ths requires 5000+ points, skipping download")
            return pd.DataFrame()

        api_func = getattr(self.pro, 'moneyflow_ths')
        return self.safe_download(
            api_func,
            trade_date=trade_date
        )

    def download_moneyflow_dc(self, trade_date=None):
        """下载个股资金流向(东财)"""
        # 检查积分要求
        if not self.check_points_requirement(5000):
            self.logger.warning("moneyflow_dc requires 5000+ points, skipping download")
            return pd.DataFrame()

        api_func = getattr(self.pro, 'moneyflow_dc')
        return self.safe_download(
            api_func,
            trade_date=trade_date
        )

    def download_moneyflow_ind_dc(self, trade_date=None):
        """下载行业/概念资金流向（东财）"""
        # 检查积分要求
        if not self.check_points_requirement(5000):
            self.logger.warning("moneyflow_ind_dc requires 5000+ points, skipping download")
            return pd.DataFrame()

        api_func = getattr(self.pro, 'moneyflow_ind_dc')
        return self.safe_download(
            api_func,
            trade_date=trade_date
        )

    def download_moneyflow_mkt_dc(self, trade_date=None):
        """下载大盘资金流向（东财）"""
        # 检查积分要求
        if not self.check_points_requirement(5000):
            self.logger.warning("moneyflow_mkt_dc requires 5000+ points, skipping download")
            return pd.DataFrame()

        api_func = getattr(self.pro, 'moneyflow_mkt_dc')
        return self.safe_download(
            api_func,
            trade_date=trade_date
        )

    def download_moneyflow_cnt_ths(self, trade_date=None):
        """下载概念板块资金流向（同花顺）"""
        # 检查积分要求
        if not self.check_points_requirement(5000):
            self.logger.warning("moneyflow_cnt_ths requires 5000+ points, skipping download")
            return pd.DataFrame()

        api_func = getattr(self.pro, 'moneyflow_cnt_ths')
        return self.safe_download(
            api_func,
            trade_date=trade_date
        )

    def download_moneyflow_ind_ths(self, trade_date=None):
        """下载行业板块资金流向（同花顺）"""
        # 检查积分要求
        if not self.check_points_requirement(5000):
            self.logger.warning("moneyflow_ind_ths requires 5000+ points, skipping download")
            return pd.DataFrame()

        api_func = getattr(self.pro, 'moneyflow_ind_ths')
        return self.safe_download(
            api_func,
            trade_date=trade_date
        )