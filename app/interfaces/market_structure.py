"""
市场结构接口模块
包含suspend_d, block_trade等市场结构相关接口
"""
import pandas as pd
import logging
from datetime import datetime, timedelta
from typing import List
try:
    from ..config import TUSHARE_POINTS
except ImportError:
    from config import TUSHARE_POINTS
try:
    from ..error_handler import ErrorHandler, retry_on_failure
except ImportError:
    from error_handler import ErrorHandler, retry_on_failure


class MarketStructureDownloader:
    def __init__(self, pro_api):
        self.pro = pro_api
        self.logger = logging.getLogger(__name__)

    @retry_on_failure(max_retries=3, delay=1.0, backoff=2.0)
    def download_with_retry(self, api_func, *args, max_retries: int = 3, **kwargs):
        """
        Download data with retry mechanism and rate limiting
        """
        api_name = api_func.__name__ if hasattr(api_func, '__name__') else 'unknown_api'

        for attempt in range(max_retries + 1):
            try:
                # Log the API call
                self.logger.info(f"Calling {api_name} API attempt {attempt + 1}")

                # Make the API call
                result = api_func(*args, **kwargs)

                self.logger.info(f"Successfully called {api_name}, got {len(result) if hasattr(result, '__len__') else 'unknown'} records")
                return result

            except Exception as e:
                self.logger.warning(f"Attempt {attempt + 1} failed for {api_name}: {str(e)}")

                if attempt == max_retries:
                    self.logger.error(f"All {max_retries + 1} attempts failed for {api_name}")
                    ErrorHandler.handle_api_error(e, f"API call {api_name}")

    def download_suspend_d_range(self, start_date: str, end_date: str) -> pd.DataFrame:
        """
        按日期范围下载停复牌信息
        按周批量处理
        """
        if TUSHARE_POINTS < 500:
            self.logger.warning("suspend_d requires 500+ points, skipping download")
            return pd.DataFrame()

        try:
            result = self.download_with_retry(
                self.pro.suspend_d,
                start_date=start_date,
                end_date=end_date
            )
            self.logger.info(f"Successfully downloaded suspend_d range ({start_date} to {end_date}): {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download suspend_d range ({start_date} to {end_date}): {e}")
            ErrorHandler.handle_api_error(e, f"download_suspend_d_range")
            raise

    def download_block_trade(self, start_date: str = '20230101', end_date: str = '20231231') -> pd.DataFrame:
        """
        Download block trade data
        Available to users with 500+ points
        """
        if TUSHARE_POINTS < 500:
            self.logger.warning("block_trade requires 500+ points, skipping download")
            return pd.DataFrame()

        try:
            result = self.download_with_retry(
                self.pro.block_trade,
                start_date=start_date,
                end_date=end_date
            )
            self.logger.info(f"Successfully downloaded block_trade: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download block_trade: {e}")
            ErrorHandler.handle_api_error(e, "download_block_trade")
            raise

    def download_share_float(self, start_date: str = '20230101', end_date: str = '20231231') -> pd.DataFrame:
        """
        Download restricted stock unlock data
        Available to users with 500+ points
        """
        if TUSHARE_POINTS < 500:
            self.logger.warning("share_float requires 500+ points, skipping download")
            return pd.DataFrame()

        try:
            result = self.download_with_retry(
                self.pro.share_float,
                start_date=start_date,
                end_date=end_date
            )
            self.logger.info(f"Successfully downloaded share_float: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download share_float: {e}")
            ErrorHandler.handle_api_error(e, "download_share_float")
            raise

    def create_adaptive_batches(self, start_date: str, end_date: str, max_items_per_batch: int):
        """
        根据日期范围长度和数据密度智能分批
        """
        from datetime import datetime, timedelta

        start = datetime.strptime(start_date, '%Y%m%d')
        end = datetime.strptime(end_date, '%Y%m%d')
        total_days = (end - start).days + 1

        if total_days <= 7:  # 一周内，单批处理
            return [(start_date, end_date)]
        elif total_days <= 30:  # 一个月内，按周分批
            return self.create_weekly_batches(start_date, end_date)
        elif total_days <= 90:  # 三个月内，按双周分批
            return self.create_biweekly_batches(start_date, end_date)
        elif total_days <= 180:  # 半年内，按月分批
            return self.create_monthly_batches(start_date, end_date)
        else:  # 超过半年，按双月分批
            return self.create_bimonthly_batches(start_date, end_date)

    def create_trading_day_batches(self, start_date: str, end_date: str, max_trading_days: int = 30):
        """
        基于交易日历的分批处理
        """
        from .basic_data import BasicDataDownloader
        basic_downloader = BasicDataDownloader(self.pro)

        # 获取交易日历
        trade_cal = basic_downloader.download_trade_cal(start_date=start_date, end_date=end_date)
        trading_days = trade_cal[trade_cal['is_open'] == 1]['cal_date'].tolist()
        trading_days.sort()

        # 按交易日数量分批
        batches = []
        for i in range(0, len(trading_days), max_trading_days):
            batch_days = trading_days[i:i + max_trading_days]
            batch_start = batch_days[0]
            batch_end = batch_days[-1]
            batches.append((batch_start, batch_end))

        return batches

    def create_weekly_batches(self, start_date: str, end_date: str):
        """按周创建批次"""
        from datetime import datetime, timedelta

        start = datetime.strptime(start_date, '%Y%m%d')
        end = datetime.strptime(end_date, '%Y%m%d')

        batches = []
        current_start = start
        while current_start <= end:
            current_end = min(current_start + timedelta(days=6), end)
            batches.append((current_start.strftime('%Y%m%d'), current_end.strftime('%Y%m%d')))
            current_start = current_end + timedelta(days=1)

        return batches

    def create_biweekly_batches(self, start_date: str, end_date: str):
        """按双周创建批次"""
        from datetime import datetime, timedelta

        start = datetime.strptime(start_date, '%Y%m%d')
        end = datetime.strptime(end_date, '%Y%m%d')

        batches = []
        current_start = start
        while current_start <= end:
            current_end = min(current_start + timedelta(days=13), end)
            batches.append((current_start.strftime('%Y%m%d'), current_end.strftime('%Y%m%d')))
            current_start = current_end + timedelta(days=1)

        return batches

    def create_monthly_batches(self, start_date: str, end_date: str):
        """按月创建批次"""
        from datetime import datetime, timedelta

        start = datetime.strptime(start_date, '%Y%m%d')
        end = datetime.strptime(end_date, '%Y%m%d')

        batches = []
        current_start = start
        while current_start <= end:
            # 找到当前月的最后一天
            if current_start.month == 12:
                next_month = current_start.replace(year=current_start.year + 1, month=1, day=1)
            else:
                next_month = current_start.replace(month=current_start.month + 1, day=1)
            current_end = next_month - timedelta(days=1)
            current_end = min(current_end, end)

            batches.append((current_start.strftime('%Y%m%d'), current_end.strftime('%Y%m%d')))
            current_start = current_end + timedelta(days=1)

        return batches

    def create_bimonthly_batches(self, start_date: str, end_date: str):
        """按双月创建批次"""
        from datetime import datetime, timedelta

        start = datetime.strptime(start_date, '%Y%m%d')
        end = datetime.strptime(end_date, '%Y%m%d')

        batches = []
        current_start = start
        while current_start <= end:
            # 找到两个月后的最后一天
            if current_start.month in [11, 12]:
                next_month = current_start.replace(year=current_start.year + 1, month=(current_start.month + 2) % 12, day=1)
            else:
                next_month = current_start.replace(month=current_start.month + 2, day=1)
            current_end = next_month - timedelta(days=1)
            current_end = min(current_end, end)

            batches.append((current_start.strftime('%Y%m%d'), current_end.strftime('%Y%m%d')))
            current_start = current_end + timedelta(days=1)

        return batches