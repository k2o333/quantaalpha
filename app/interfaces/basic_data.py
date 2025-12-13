"""
基础数据接口实现
"""
from base import BaseDownloader
import pandas as pd


class BasicDataDownloader(BaseDownloader):
    def __init__(self, pro_api, config_manager):
        super().__init__(pro_api, config_manager)

    def download_stock_basic(self, ts_code=None, exchange=None, list_status='L', fields=None):
        """下载股票基础信息"""
        # 检查积分要求
        if not self.check_points_requirement(2000):
            self.logger.warning("stock_basic requires 2000+ points, skipping download")
            return pd.DataFrame()

        api_func = getattr(self.pro, 'stock_basic')
        return self.safe_download(
            api_func,
            ts_code=ts_code,
            exchange=exchange,
            list_status=list_status,
            fields=fields
        )

    def download_trade_cal(self, exchange='SSE', start_date=None, end_date=None, is_open=None):
        """下载交易日历"""
        # 检查积分要求
        if not self.check_points_requirement(2000):
            self.logger.warning("trade_cal requires 2000+ points, skipping download")
            return pd.DataFrame()

        api_func = getattr(self.pro, 'trade_cal')
        return self.safe_download(
            api_func,
            exchange=exchange,
            start_date=start_date,
            end_date=end_date,
            is_open=is_open
        )

    def download_new_share(self, start_date=None, end_date=None):
        """下载新股列表"""
        # 检查积分要求
        if not self.check_points_requirement(120):
            self.logger.warning("new_share requires 120+ points, skipping download")
            return pd.DataFrame()

        api_func = getattr(self.pro, 'new_share')
        return self.safe_download(
            api_func,
            start_date=start_date,
            end_date=end_date
        )

    def download_stock_company(self, ts_code=None, exchange=None):
        """下载上市公司基本信息"""
        # 检查积分要求
        if not self.check_points_requirement(120):
            self.logger.warning("stock_company requires 120+ points, skipping download")
            return pd.DataFrame()

        api_func = getattr(self.pro, 'stock_company')
        return self.safe_download(
            api_func,
            ts_code=ts_code,
            exchange=exchange
        )

    def download_namechange(self, ts_code=None):
        """下载股票曾用名"""
        # 无积分要求
        api_func = getattr(self.pro, 'namechange')
        return self.safe_download(
            api_func,
            ts_code=ts_code
        )

    def download_dividend(self, ts_code=None):
        """下载分红信息"""
        # 检查积分要求
        if not self.check_points_requirement(2000):
            self.logger.warning("dividend requires 2000+ points, skipping download")
            return pd.DataFrame()

        api_func = getattr(self.pro, 'dividend')
        return self.safe_download(
            api_func,
            ts_code=ts_code
        )

    def download_stock_st(self, trade_date=None):
        """下载ST股票列表"""
        # 检查积分要求
        if not self.check_points_requirement(3000):
            self.logger.warning("stock_st requires 3000+ points, skipping download")
            return pd.DataFrame()

        api_func = getattr(self.pro, 'stock_st')
        return self.safe_download(
            api_func,
            trade_date=trade_date
        )

    def download_bak_basic(self):
        """下载备用基础数据"""
        # 检查积分要求
        if not self.check_points_requirement(5000):
            self.logger.warning("bak_basic requires 5000+ points, skipping download")
            return pd.DataFrame()

        api_func = getattr(self.pro, 'bak_basic')
        return self.safe_download(api_func)