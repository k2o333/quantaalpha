"""
基础数据接口模块
包含stock_basic, trade_cal, new_share等接口
"""
import tushare as ts
import pandas as pd
import time
import logging
from typing import Optional
try:
    from ..config import TUSHARE_TOKEN, TUSHARE_POINTS
except ImportError:
    from config import TUSHARE_TOKEN, TUSHARE_POINTS
try:
    from ..error_handler import ErrorHandler, retry_on_failure
except ImportError:
    from error_handler import ErrorHandler, retry_on_failure


class BasicDataDownloader:
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

                # Exponential backoff: wait longer between each attempt
                wait_time = 2 ** attempt
                self.logger.info(f"Waiting {wait_time}s before next attempt...")
                time.sleep(wait_time)

    def download_stock_basic(self) -> pd.DataFrame:
        """
        Download stock basic information
        Available to users with 2000+ points
        """
        if TUSHARE_POINTS < 2000:
            self.logger.warning("stock_basic requires 2000+ points, skipping download")
            return pd.DataFrame()

        try:
            result = self.download_with_retry(
                self.pro.stock_basic,
                exchange='',
                list_status='L',
                fields='ts_code,symbol,name,area,industry,fullname,enname,market,exchange,curr_type,list_status,list_date,delist_date,is_hs,act_name,act_ent_type'
            )
            self.logger.info(f"Successfully downloaded stock basic info: {len(result)} stocks")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download stock basic info: {e}")
            ErrorHandler.handle_api_error(e, "download_stock_basic")
            raise

    def download_trade_cal(self, exchange: str = 'SSE', start_date: str = '20100101', end_date: str = '20251231') -> pd.DataFrame:
        """
        Download trade calendar data
        Available to users with 2000+ points
        """
        if TUSHARE_POINTS < 2000:
            self.logger.warning("trade_cal requires 2000+ points, skipping download")
            return pd.DataFrame()

        try:
            result = self.download_with_retry(
                self.pro.trade_cal,
                exchange=exchange,
                start_date=start_date,
                end_date=end_date,
                api_name='trade_cal'
            )
            self.logger.info(f"Successfully downloaded trade calendar: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download trade calendar: {e}")
            ErrorHandler.handle_api_error(e, "download_trade_cal")
            raise

    def download_new_share(self, start_date: str = '20230101', end_date: str = '20231231') -> pd.DataFrame:
        """
        Download new share listing data
        Available to users with 120+ points
        """
        if TUSHARE_POINTS < 120:
            self.logger.warning("new_share requires 120+ points, skipping download")
            return pd.DataFrame()

        try:
            result = self.download_with_retry(
                self.pro.new_share,
                start_date=start_date,
                end_date=end_date
            )
            self.logger.info(f"Successfully downloaded new share data: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download new share data: {e}")
            ErrorHandler.handle_api_error(e, "download_new_share")
            raise

    def download_stock_company(self, exchange: str = None) -> pd.DataFrame:
        """
        Download company information for listed stocks
        Available to users with 120+ points
        """
        if TUSHARE_POINTS < 120:
            self.logger.warning("stock_company requires 120+ points, skipping download")
            return pd.DataFrame()

        try:
            params = {}
            if exchange:
                params['exchange'] = exchange

            result = self.download_with_retry(
                self.pro.stock_company,
                **params
            )
            self.logger.info(f"Successfully downloaded stock company info: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download stock company info: {e}")
            ErrorHandler.handle_api_error(e, "download_stock_company")
            raise

    def download_namechange(self, ts_code: str = None) -> pd.DataFrame:
        """
        Download stock name change history
        Available to all users (no points required)
        """
        try:
            params = {}
            if ts_code:
                params['ts_code'] = ts_code

            result = self.download_with_retry(
                self.pro.namechange,
                **params
            )
            self.logger.info(f"Successfully downloaded name change data: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download name change data: {e}")
            ErrorHandler.handle_api_error(e, "download_namechange")
            raise

    def download_dividend(self, ts_code: str = None) -> pd.DataFrame:
        """
        Download dividend information
        Available to users with 2000+ points
        """
        if TUSHARE_POINTS < 2000:
            self.logger.warning("dividend requires 2000+ points, skipping download")
            return pd.DataFrame()

        try:
            params = {}
            if ts_code:
                params['ts_code'] = ts_code

            result = self.download_with_retry(
                self.pro.dividend,
                **params
            )
            self.logger.info(f"Successfully downloaded dividend data: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download dividend data: {e}")
            ErrorHandler.handle_api_error(e, "download_dividend")
            raise

    def download_stock_st(self, trade_date: str = '20231201') -> pd.DataFrame:
        """
        Download ST stock list
        Available to users with 3000+ points
        """
        if TUSHARE_POINTS < 3000:
            self.logger.warning("stock_st requires 3000+ points, skipping download")
            return pd.DataFrame()

        try:
            result = self.download_with_retry(
                self.pro.stock_st,
                trade_date=trade_date
            )
            self.logger.info(f"Successfully downloaded stock_st: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download stock_st: {e}")
            ErrorHandler.handle_api_error(e, "download_stock_st")
            raise

    def download_bak_basic(self) -> pd.DataFrame:
        """
        Download backup basic data
        Available to users with 5000+ points
        """
        if TUSHARE_POINTS < 5000:
            self.logger.warning("bak_basic requires 5000+ points, skipping download")
            return pd.DataFrame()

        try:
            result = self.download_with_retry(
                self.pro.bak_basic
            )
            self.logger.info(f"Successfully downloaded bak_basic: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download bak_basic: {e}")
            ErrorHandler.handle_api_error(e, "download_bak_basic")
            raise