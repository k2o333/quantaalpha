"""
Score-based data download system for aspipe_v4
Handles downloading data based on user's tushare_points score
"""
import os
import logging
from typing import List, Dict, Any
from config import TUSHARE_TOKEN
from score_config import get_available_data_types, get_api_limits_for_score
import tushare as ts
import time
import pandas as pd
from data_storage import save_to_parquet
from error_handler import ErrorHandler, retry_on_failure

logger = logging.getLogger(__name__)


class ScoreBasedDownloader:
    def __init__(self, user_points: int = None):
        """
        Initialize downloader based on user's tushare points
        """
        if user_points is None:
            from config import TUSHARE_POINTS
            user_points = TUSHARE_POINTS
            
        self.user_points = user_points
        self.available_data_types = get_available_data_types(user_points)
        self.api_limits = get_api_limits_for_score(user_points)
        
        # Initialize tushare API
        self.pro = ts.pro_api(TUSHARE_TOKEN)
        self.last_call_times = {}
        
        logger.info(f"ScoreBasedDownloader initialized with {user_points} points")
        logger.info(f"Available data types: {self.available_data_types}")
        
    def _rate_limit(self, api_name: str) -> None:
        """
        Implement rate limiting for API calls to avoid exceeding limits
        """
        current_time = time.time()

        # Get the rate limit for this API
        calls_per_minute = self.api_limits.get(api_name, {}).get('calls_per_minute', 200)
        min_interval = 60.0 / calls_per_minute

        # Check if we've called this API recently
        if api_name in self.last_call_times:
            elapsed = current_time - self.last_call_times[api_name]
            if elapsed < min_interval:
                sleep_time = min_interval - elapsed
                logger.debug(f"Rate limiting {api_name}, sleeping for {sleep_time:.2f}s")
                time.sleep(sleep_time)

        self.last_call_times[api_name] = time.time()

    @retry_on_failure(max_retries=3, delay=1.0, backoff=2.0)
    def download_with_retry(self, api_func, *args, max_retries: int = 3, **kwargs):
        """
        Download data with retry mechanism and rate limiting
        """
        api_name = api_func.__name__ if hasattr(api_func, '__name__') else 'unknown_api'

        for attempt in range(max_retries + 1):
            try:
                # Implement rate limiting
                self._rate_limit(api_name)

                # Log the API call
                logger.info(f"Calling {api_name} API attempt {attempt + 1}")

                # Make the API call
                result = api_func(*args, **kwargs)

                logger.info(f"Successfully called {api_name}, got {len(result) if hasattr(result, '__len__') else 'unknown'} records")
                return result

            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed for {api_name}: {str(e)}")

                if attempt == max_retries:
                    logger.error(f"All {max_retries + 1} attempts failed for {api_name}")
                    ErrorHandler.handle_api_error(e, f"API call {api_name}")

                # Exponential backoff: wait longer between each attempt
                wait_time = 2 ** attempt
                logger.info(f"Waiting {wait_time}s before next attempt...")
                time.sleep(wait_time)

    def is_data_type_available(self, data_type: str) -> bool:
        """
        Check if a specific data type is available based on user's score
        """
        for category_types in self.available_data_types.values():
            if data_type in category_types:
                return True
        return False

    def get_available_data_types(self) -> Dict[str, List[str]]:
        """
        Get all available data types by category
        """
        return self.available_data_types

    def download_stock_basic(self) -> pd.DataFrame:
        """
        Download stock basic information (available at 2000+ points)
        """
        if not self.is_data_type_available('stock_basic'):
            logger.warning("stock_basic not available with current score, skipping")
            return pd.DataFrame()
            
        try:
            logger.info("Downloading stock basic info...")
            result = self.download_with_retry(
                self.pro.stock_basic,
                exchange='',
                list_status='L',
                fields='ts_code,symbol,name,area,industry,fullname,enname,market,exchange,curr_type,list_status,list_date,delist_date,is_hs,act_name,act_ent_type'
            )
            logger.info(f"Successfully downloaded stock basic info: {len(result)} stocks")
            return result
        except Exception as e:
            logger.error(f"Failed to download stock basic info: {e}")
            ErrorHandler.handle_api_error(e, "download_stock_basic")
            raise

    def download_trade_cal(self) -> pd.DataFrame:
        """
        Download trade calendar (available at 120+ points)
        """
        if not self.is_data_type_available('trade_cal'):
            logger.warning("trade_cal not available with current score, skipping")
            return pd.DataFrame()
            
        try:
            logger.info("Downloading trade calendar...")
            result = self.download_with_retry(
                self.pro.trade_cal,
                exchange='SSE',
                start_date='20100101',
                end_date='20251231',
                is_open='1'
            )
            logger.info(f"Successfully downloaded trade calendar: {len(result)} records")
            return result
        except Exception as e:
            logger.error(f"Failed to download trade calendar: {e}")
            ErrorHandler.handle_api_error(e, "download_trade_cal")
            raise

    def download_daily(self, ts_code: str = None, trade_date: str = None) -> pd.DataFrame:
        """
        Download daily data (available at basic level, but more data accessible with higher scores)
        """
        if not self.is_data_type_available('daily'):
            logger.warning("daily not available with current score, skipping")
            return pd.DataFrame()
            
        try:
            logger.info("Downloading daily data...")
            params = {}
            if ts_code:
                params['ts_code'] = ts_code
            if trade_date:
                params['trade_date'] = trade_date
            else:
                params['start_date'] = '20230101'
                params['end_date'] = '20231231'
            
            result = self.download_with_retry(self.pro.daily, **params)
            logger.info(f"Successfully downloaded daily data: {len(result)} records")
            return result
        except Exception as e:
            logger.error(f"Failed to download daily data: {e}")
            ErrorHandler.handle_api_error(e, "download_daily")
            raise

    def download_daily_basic(self, trade_date: str = '20231201') -> pd.DataFrame:
        """
        Download daily basic metrics (available at 2000+ points)
        """
        if not self.is_data_type_available('daily_basic'):
            logger.warning("daily_basic not available with current score, skipping")
            return pd.DataFrame()
            
        try:
            logger.info("Downloading daily basic metrics...")
            result = self.download_with_retry(
                self.pro.daily_basic,
                trade_date=trade_date
            )
            logger.info(f"Successfully downloaded daily basic: {len(result)} records")
            return result
        except Exception as e:
            logger.error(f"Failed to download daily basic: {e}")
            ErrorHandler.handle_api_error(e, "download_daily_basic")
            raise

    def download_income(self) -> pd.DataFrame:
        """
        Download income statement (available at 2000+ points)
        """
        if not self.is_data_type_available('income'):
            logger.warning("income not available with current score, skipping")
            return pd.DataFrame()
            
        try:
            logger.info("Downloading income statement...")
            # Use VIP version if available (5000+ points)
            if self.is_data_type_available('income_vip'):
                api_func = getattr(self.pro, 'income_vip', self.pro.income)
            else:
                api_func = self.pro.income
            
            result = self.download_with_retry(
                api_func,
                period='20231231'  # Latest quarter
            )
            logger.info(f"Successfully downloaded income statement: {len(result)} records")
            return result
        except Exception as e:
            logger.error(f"Failed to download income statement: {e}")
            ErrorHandler.handle_api_error(e, "download_income")
            raise

    def download_balancesheet(self) -> pd.DataFrame:
        """
        Download balance sheet (available at 2000+ points)
        """
        if not self.is_data_type_available('balancesheet'):
            logger.warning("balancesheet not available with current score, skipping")
            return pd.DataFrame()
            
        try:
            logger.info("Downloading balance sheet...")
            # Use VIP version if available (5000+ points)
            if self.is_data_type_available('balancesheet_vip'):
                api_func = getattr(self.pro, 'balancesheet_vip', self.pro.balancesheet)
            else:
                api_func = self.pro.balancesheet
            
            result = self.download_with_retry(
                api_func,
                period='20231231'  # Latest quarter
            )
            logger.info(f"Successfully downloaded balance sheet: {len(result)} records")
            return result
        except Exception as e:
            logger.error(f"Failed to download balance sheet: {e}")
            ErrorHandler.handle_api_error(e, "download_balancesheet")
            raise

    def download_cashflow(self) -> pd.DataFrame:
        """
        Download cash flow statement (available at 2000+ points)
        """
        if not self.is_data_type_available('cashflow'):
            logger.warning("cashflow not available with current score, skipping")
            return pd.DataFrame()
            
        try:
            logger.info("Downloading cash flow statement...")
            # Use VIP version if available (5000+ points)
            if self.is_data_type_available('cashflow_vip'):
                api_func = getattr(self.pro, 'cashflow_vip', self.pro.cashflow)
            else:
                api_func = self.pro.cashflow
            
            result = self.download_with_retry(
                api_func,
                period='20231231'  # Latest quarter
            )
            logger.info(f"Successfully downloaded cash flow: {len(result)} records")
            return result
        except Exception as e:
            logger.error(f"Failed to download cash flow: {e}")
            ErrorHandler.handle_api_error(e, "download_cashflow")
            raise

    def download_fina_indicator(self) -> pd.DataFrame:
        """
        Download financial indicators (available at 2000+ points)
        """
        if not self.is_data_type_available('fina_indicator'):
            logger.warning("fina_indicator not available with current score, skipping")
            return pd.DataFrame()
            
        try:
            logger.info("Downloading financial indicators...")
            # Use VIP version if available (5000+ points)
            if self.is_data_type_available('fina_indicator_vip'):
                api_func = getattr(self.pro, 'fina_indicator_vip', self.pro.fina_indicator)
            else:
                api_func = self.pro.fina_indicator
            
            result = self.download_with_retry(
                api_func,
                period='20231231'  # Latest quarter
            )
            logger.info(f"Successfully downloaded financial indicators: {len(result)} records")
            return result
        except Exception as e:
            logger.error(f"Failed to download financial indicators: {e}")
            ErrorHandler.handle_api_error(e, "download_fina_indicator")
            raise

    def download_all_available_data(self):
        """
        Download all data types available for the user's score level
        """
        logger.info(f"Starting download of all available data for {self.user_points} points...")
        
        results = {}
        
        # Download basic information
        if self.is_data_type_available('stock_basic'):
            try:
                df = self.download_stock_basic()
                if not df.empty:
                    save_to_parquet(df, 'stock_basic')
                    results['stock_basic'] = len(df)
            except Exception as e:
                logger.error(f"Error downloading stock_basic: {e}")
        
        # Download trade calendar
        if self.is_data_type_available('trade_cal'):
            try:
                df = self.download_trade_cal()
                if not df.empty:
                    save_to_parquet(df, 'trade_cal')
                    results['trade_cal'] = len(df)
            except Exception as e:
                logger.error(f"Error downloading trade_cal: {e}")
        
        # Download daily basic
        if self.is_data_type_available('daily_basic'):
            try:
                df = self.download_daily_basic()
                if not df.empty:
                    save_to_parquet(df, 'daily_basic_20231201')
                    results['daily_basic'] = len(df)
            except Exception as e:
                logger.error(f"Error downloading daily_basic: {e}")
        
        # Download financial data if available
        if self.is_data_type_available('income'):
            try:
                df = self.download_income()
                if not df.empty:
                    save_to_parquet(df, 'income_20231231')
                    results['income'] = len(df)
            except Exception as e:
                logger.error(f"Error downloading income: {e}")
        
        if self.is_data_type_available('balancesheet'):
            try:
                df = self.download_balancesheet()
                if not df.empty:
                    save_to_parquet(df, 'balancesheet_20231231')
                    results['balancesheet'] = len(df)
            except Exception as e:
                logger.error(f"Error downloading balancesheet: {e}")
        
        if self.is_data_type_available('cashflow'):
            try:
                df = self.download_cashflow()
                if not df.empty:
                    save_to_parquet(df, 'cashflow_20231231')
                    results['cashflow'] = len(df)
            except Exception as e:
                logger.error(f"Error downloading cashflow: {e}")
        
        if self.is_data_type_available('fina_indicator'):
            try:
                df = self.download_fina_indicator()
                if not df.empty:
                    save_to_parquet(df, 'fina_indicator_20231231')
                    results['fina_indicator'] = len(df)
            except Exception as e:
                logger.error(f"Error downloading fina_indicator: {e}")
        
        logger.info(f"Download completed. Results: {results}")
        return results


# Example usage:
if __name__ == "__main__":
    # Create downloader instance based on current user's score
    downloader = ScoreBasedDownloader()
    
    # Show what data types are available
    available = downloader.get_available_data_types()
    print("Available data types by category:")
    for category, types in available.items():
        if types:  # Only show categories that have available types
            print(f"  {category}: {types}")
    
    # Download all available data
    results = downloader.download_all_available_data()
    print(f"Download results: {results}")