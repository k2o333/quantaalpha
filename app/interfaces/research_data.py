"""
研究数据接口实现
"""
from base import BaseDownloader
import pandas as pd


class ResearchDataDownloader(BaseDownloader):
    def __init__(self, pro_api, config_manager):
        super().__init__(pro_api, config_manager)

    def download_report_rc(self, period=None, ts_code=None):
        """下载卖方盈利预测数据"""
        # 检查积分要求
        if not self.check_points_requirement(5000):
            self.logger.warning("report_rc requires 5000+ points, skipping download")
            return pd.DataFrame()

        api_func = getattr(self.pro, 'report_rc')
        return self.safe_download(
            api_func,
            period=period,
            ts_code=ts_code
        )

    def download_stk_surv(self, period=None, ts_code=None):
        """下载机构调研表"""
        # 检查积分要求
        if not self.check_points_requirement(5000):
            self.logger.warning("stk_surv requires 5000+ points, skipping download")
            return pd.DataFrame()

        api_func = getattr(self.pro, 'stk_surv')
        return self.safe_download(
            api_func,
            period=period,
            ts_code=ts_code
        )

    def download_broker_recommend(self, month=None):
        """下载券商每月荐股"""
        # 检查积分要求
        if not self.check_points_requirement(2000):
            self.logger.warning("broker_recommend requires 2000+ points, skipping download")
            return pd.DataFrame()

        api_func = getattr(self.pro, 'broker_recommend')
        return self.safe_download(
            api_func,
            month=month
        )