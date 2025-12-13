"""
财务数据接口实现
"""
from base import BaseDownloader
import pandas as pd


class FinancialDataDownloader(BaseDownloader):
    def __init__(self, pro_api, config_manager):
        super().__init__(pro_api, config_manager)

    def download_income(self, period=None, ts_code=None):
        """下载利润表数据"""
        # 检查积分要求
        if not self.check_points_requirement(2000):
            self.logger.warning("income requires 2000+ points, skipping download")
            return pd.DataFrame()

        # 根据积分选择接口
        if self.check_points_requirement(5000) and period is not None and ts_code is None:
            # 使用VIP接口
            api_func = getattr(self.pro, 'income_vip')
        else:
            # 使用普通接口
            api_func = getattr(self.pro, 'income')

        return self.safe_download(
            api_func,
            period=period,
            ts_code=ts_code
        )

    def download_balancesheet(self, period=None, ts_code=None):
        """下载资产负债表数据"""
        # 检查积分要求
        if not self.check_points_requirement(2000):
            self.logger.warning("balancesheet requires 2000+ points, skipping download")
            return pd.DataFrame()

        # 根据积分选择接口
        if self.check_points_requirement(5000) and period is not None and ts_code is None:
            # 使用VIP接口
            api_func = getattr(self.pro, 'balancesheet_vip')
        else:
            # 使用普通接口
            api_func = getattr(self.pro, 'balancesheet')

        return self.safe_download(
            api_func,
            period=period,
            ts_code=ts_code
        )

    def download_cashflow(self, period=None, ts_code=None):
        """下载现金流量表数据"""
        # 检查积分要求
        if not self.check_points_requirement(2000):
            self.logger.warning("cashflow requires 2000+ points, skipping download")
            return pd.DataFrame()

        # 根据积分选择接口
        if self.check_points_requirement(5000) and period is not None and ts_code is None:
            # 使用VIP接口
            api_func = getattr(self.pro, 'cashflow_vip')
        else:
            # 使用普通接口
            api_func = getattr(self.pro, 'cashflow')

        return self.safe_download(
            api_func,
            period=period,
            ts_code=ts_code
        )

    def download_fina_indicator(self, period=None, ts_code=None):
        """下载财务指标数据"""
        # 检查积分要求
        if not self.check_points_requirement(2000):
            self.logger.warning("fina_indicator requires 2000+ points, skipping download")
            return pd.DataFrame()

        # 根据积分选择接口
        if self.check_points_requirement(5000) and period is not None and ts_code is None:
            # 使用VIP接口
            api_func = getattr(self.pro, 'fina_indicator_vip')
        else:
            # 使用普通接口
            api_func = getattr(self.pro, 'fina_indicator')

        return self.safe_download(
            api_func,
            period=period,
            ts_code=ts_code
        )

    def download_forecast(self, period='20231231', ts_code=None):
        """下载业绩预告"""
        # 检查积分要求
        if not self.check_points_requirement(2000):
            self.logger.warning("forecast requires 2000+ points, skipping download")
            return pd.DataFrame()

        # 根据积分选择接口
        if self.check_points_requirement(5000) and ts_code is None:
            # 使用VIP接口
            api_func = getattr(self.pro, 'forecast_vip')
        else:
            # 使用普通接口
            api_func = getattr(self.pro, 'forecast')

        return self.safe_download(
            api_func,
            period=period,
            ts_code=ts_code
        )

    def download_express(self, period='20231231', ts_code=None):
        """下载业绩快报"""
        # 检查积分要求
        if not self.check_points_requirement(2000):
            self.logger.warning("express requires 2000+ points, skipping download")
            return pd.DataFrame()

        # 根据积分选择接口
        if self.check_points_requirement(5000) and ts_code is None:
            # 使用VIP接口
            api_func = getattr(self.pro, 'express_vip')
        else:
            # 使用普通接口
            api_func = getattr(self.pro, 'express')

        return self.safe_download(
            api_func,
            period=period,
            ts_code=ts_code
        )

    def download_fina_audit(self, period='20231231', ts_code=None):
        """下载财务审计意见"""
        # 检查积分要求
        if not self.check_points_requirement(500):
            self.logger.warning("fina_audit requires 500+ points, skipping download")
            return pd.DataFrame()

        api_func = getattr(self.pro, 'fina_audit')
        return self.safe_download(
            api_func,
            period=period,
            ts_code=ts_code
        )

    def download_fina_mainbz(self, period='20231231', ts_code=None, type_='P'):
        """下载主营业务构成"""
        # 检查积分要求
        if not self.check_points_requirement(2000):
            self.logger.warning("fina_mainbz requires 2000+ points, skipping download")
            return pd.DataFrame()

        # 根据积分选择接口
        if self.check_points_requirement(5000):
            # 使用VIP接口
            api_func = getattr(self.pro, 'fina_mainbz_vip')
        else:
            # 使用普通接口
            api_func = getattr(self.pro, 'fina_mainbz')

        return self.safe_download(
            api_func,
            period=period,
            ts_code=ts_code,
            type=type_
        )

    def download_disclosure_date(self, ann_date='20231201'):
        """下载财报披露计划"""
        # 检查积分要求
        if not self.check_points_requirement(500):
            self.logger.warning("disclosure_date requires 500+ points, skipping download")
            return pd.DataFrame()

        api_func = getattr(self.pro, 'disclosure_date')
        return self.safe_download(
            api_func,
            ann_date=ann_date
        )