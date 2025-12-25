"""
日线数据接口模块
包含daily, daily_basic等接口
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


class DailyDataDownloader:
    def __init__(self, pro_api):
        self.pro = pro_api
        self.logger = logging.getLogger(__name__)

    @retry_on_failure(max_retries=3, delay=1.0, backoff=2.0)
    def download_with_retry(self, api_func, *args, max_retries: int = 3, **kwargs):
        """
        Download data with retry mechanism and rate limiting
        """
        # Extract the correct API name by getting it from various attributes of the function
        api_name = 'unknown_api'
        if hasattr(api_func, '__name__'):
            api_name = api_func.__name__
        elif hasattr(api_func, '__func__') and hasattr(api_func.__func__, '__name__'):
            api_name = api_func.__func__.__name__
        elif hasattr(api_func, '__self__') and hasattr(api_func, '__name__'):
            # For bound methods, try to get the method name
            api_name = api_func.__name__
        else:
            # Handle TuShare dynamic API methods
            api_name = str(api_func).split('.')[-1].replace('>', '').strip()

        # Special handling for certain API names that might need adjustment
        if 'pro_bar' in api_name.lower():
            api_name = 'pro_bar'
        elif 'adj_factor' in api_name.lower():
            api_name = 'adj_factor'

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

    def download_daily_data(self, ts_code: str, start_date: str = '20100101', end_date: str = '20231231') -> pd.DataFrame:
        """
        Download daily data for a specific stock
        Available to all users
        """
        try:
            # Use daily interface (no VIP version exists for daily interface)
            api_func = self.pro.daily
            result = self.download_with_retry(
                api_func,
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date
            )
            self.logger.info(f"Successfully downloaded daily data for {ts_code} using daily: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download daily data for {ts_code}: {e}")
            ErrorHandler.handle_api_error(e, f"download_daily_data for {ts_code}")
            raise

    def download_daily_data_for_date_range(self, start_date: str = '20100101', end_date: str = '20231231') -> pd.DataFrame:
        """
        Download daily data for all stocks in a date range by iterating through trading days
        Since daily interface doesn't have a VIP version, we'll get data day by day
        """
        try:
            # Get trading calendar for the date range
            trade_cal = self.download_with_retry(
                self.pro.trade_cal,
                exchange='SSE',
                start_date=start_date,
                end_date=end_date,
                is_open=1
            )

            if trade_cal.empty:
                self.logger.warning("No trading days found in the specified range")
                return pd.DataFrame()

            all_data = []
            trading_days = trade_cal['cal_date'].tolist()
            trading_days.sort()

            self.logger.info(f"Starting to download daily data for {len(trading_days)} trading days")

            for i, trade_date in enumerate(trading_days):
                if (i + 1) % 10 == 0:  # Log progress every 10 days
                    self.logger.info(f"Processed {i + 1}/{len(trading_days)} trading days...")

                try:
                    df = self.download_with_retry(
                        self.pro.daily,
                        trade_date=trade_date
                    )
                    if df is not None and not df.empty:
                        all_data.append(df)
                    else:
                        self.logger.debug(f"No daily data for {trade_date}")
                except Exception as e:
                    self.logger.warning(f"Failed to download daily data for {trade_date}: {e}")
                    continue  # Continue with next day even if one fails

            # Combine all data
            if all_data:
                result = pd.concat(all_data, ignore_index=True)
                self.logger.info(f"Successfully downloaded daily data for date range: {len(result)} records")
                return result
            else:
                self.logger.warning("No daily data could be downloaded for the date range")
                return pd.DataFrame()

        except Exception as e:
            self.logger.error(f"Failed to download daily data for date range: {e}")
            ErrorHandler.handle_api_error(e, "download_daily_data_for_date_range")
            raise

    def download_daily_basic(self, trade_date: str = '20231201') -> pd.DataFrame:
        """
        Download daily basic metrics for all stocks on a specific date
        Available to users with 2000+ points
        """
        if TUSHARE_POINTS < 2000:
            self.logger.warning("daily_basic requires 2000+ points, skipping download")
            return pd.DataFrame()

        try:
            result = self.download_with_retry(
                self.pro.daily_basic,
                trade_date=trade_date
            )
            self.logger.info(f"Successfully downloaded daily basic: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download daily basic: {e}")
            ErrorHandler.handle_api_error(e, "download_daily_basic")
            raise

    def download_daily_basic_range(self, start_date: str, end_date: str) -> pd.DataFrame:
        """
        按日期范围批量下载daily_basic数据
        由于该接口不支持日期范围参数，需要按日循环下载
        """
        if TUSHARE_POINTS < 2000:
            self.logger.warning("daily_basic requires 2000+ points, skipping download")
            return pd.DataFrame()

        try:
            # 获取交易日历
            trade_cal = self.download_with_retry(
                self.pro.trade_cal,
                start_date=start_date,
                end_date=end_date,
                is_open=1
            )

            if trade_cal.empty:
                self.logger.warning("No trading days found in the specified range")
                return pd.DataFrame()

            all_data = []
            trading_days = trade_cal['cal_date'].tolist()
            trading_days.sort()

            self.logger.info(f"Starting to download daily_basic for {len(trading_days)} trading days")

            for i, trade_date in enumerate(trading_days):
                if (i + 1) % 10 == 0:  # Log progress every 10 days
                    self.logger.info(f"Processed {i + 1}/{len(trading_days)} trading days...")

                try:
                    df = self.download_daily_basic(trade_date=trade_date)
                    if df is not None and not df.empty:
                        all_data.append(df)
                    else:
                        self.logger.debug(f"No daily_basic data for {trade_date}")
                except Exception as e:
                    self.logger.warning(f"Failed to download daily_basic for {trade_date}: {e}")
                    continue  # Continue with next day even if one fails

            # Combine all data
            if all_data:
                result = pd.concat(all_data, ignore_index=True)
                self.logger.info(f"Successfully downloaded daily_basic for date range: {len(result)} records")
                return result
            else:
                self.logger.warning("No daily_basic data could be downloaded for the date range")
                return pd.DataFrame()

        except Exception as e:
            self.logger.error(f"Failed to download daily_basic for date range: {e}")
            ErrorHandler.handle_api_error(e, "download_daily_basic_range")
            raise

    def download_pro_bar(self, ts_code: str, start_date: str = None, end_date: str = None, adj: str = 'qfq', freq: str = 'D') -> pd.DataFrame:
        """
        Download复权行情数据
        Available to users with 5000+ points
        """
        if TUSHARE_POINTS < 5000:
            self.logger.warning("pro_bar requires 5000+ points, skipping download")
            return pd.DataFrame()

        try:
            params = {
                'ts_code': ts_code,
                'adj': adj,
                'freq': freq
            }
            if start_date:
                params['start_date'] = start_date
            if end_date:
                params['end_date'] = end_date

            result = self.download_with_retry(
                self.pro.pro_bar,
                **params
            )
            self.logger.info(f"Successfully downloaded pro_bar for {ts_code}: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download pro_bar for {ts_code}: {e}")
            ErrorHandler.handle_api_error(e, f"download_pro_bar for {ts_code}")
            raise

    def download_pro_bar_range(self, ts_code: str, start_date: str, end_date: str, adj: str = 'qfq', freq: str = 'D') -> pd.DataFrame:
        """
        Download复权行情数据（指定日期范围）
        Available to users with 5000+ points
        """
        if TUSHARE_POINTS < 5000:
            self.logger.warning("pro_bar requires 5000+ points, skipping download")
            return pd.DataFrame()

        try:
            result = self.download_with_retry(
                self.pro.pro_bar,
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
                adj=adj,
                freq=freq
            )
            self.logger.info(f"Successfully downloaded pro_bar for {ts_code} from {start_date} to {end_date}: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download pro_bar for {ts_code} from {start_date} to {end_date}: {e}")
            ErrorHandler.handle_api_error(e, f"download_pro_bar_range for {ts_code}")
            raise

    def download_pro_bar_full_history(self, ts_code: str, adj: str = 'qfq', freq: str = 'D') -> pd.DataFrame:
        """
        Download full history复权行情数据（从上市日到今天）
        Available to users with 5000+ points
        """
        if TUSHARE_POINTS < 5000:
            self.logger.warning("pro_bar requires 5000+ points, skipping download")
            return pd.DataFrame()

        try:
            # 获取股票基本信息以确定上市日期
            from .basic_data import BasicDataDownloader
            basic_downloader = BasicDataDownloader(self.pro)
            stock_info = basic_downloader.download_stock_basic()

            # 查找该股票的上市日期
            stock_row = stock_info[stock_info['ts_code'] == ts_code]
            if stock_row.empty:
                self.logger.warning(f"Stock {ts_code} not found in stock basic info")
                return pd.DataFrame()

            list_date = stock_row.iloc[0]['list_date']
            end_date = pd.Timestamp.now().strftime('%Y%m%d')

            # 下载从上市日到今天的全部历史数据
            result = self.download_with_retry(
                self.pro.pro_bar,
                ts_code=ts_code,
                start_date=list_date,
                end_date=end_date,
                adj=adj,
                freq=freq
            )
            self.logger.info(f"Successfully downloaded full history pro_bar for {ts_code} from {list_date} to {end_date}: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download full history pro_bar for {ts_code}: {e}")
            ErrorHandler.handle_api_error(e, f"download_pro_bar_full_history for {ts_code}")
            raise