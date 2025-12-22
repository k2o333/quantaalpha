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