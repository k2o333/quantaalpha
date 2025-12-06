"""
TuShare API integration for aspipe_v4
"""
import tushare as ts
import time
import logging
from typing import Optional
from config import TUSHARE_TOKEN, API_LIMITS
import pandas as pd
from error_handler import ErrorHandler, retry_on_failure


class TuShareDownloader:
    def __init__(self):
        """
        Initialize the TuShare API downloader with token authentication and rate limiting
        """
        self.pro = ts.pro_api(TUSHARE_TOKEN)
        self.api_limits = API_LIMITS
        self.last_call_times = {}

        self.logger = logging.getLogger(__name__)

    def _rate_limit(self, api_name: str) -> None:
        """
        Implement rate limiting for API calls to avoid exceeding limits
        """
        current_time = time.time()

        # Get the rate limit for this API (default to 200 calls per minute)
        calls_per_minute = self.api_limits.get(api_name, {}).get('calls_per_minute', 200)
        min_interval = 60.0 / calls_per_minute

        # Check if we've called this API recently
        if api_name in self.last_call_times:
            elapsed = current_time - self.last_call_times[api_name]
            if elapsed < min_interval:
                sleep_time = min_interval - elapsed
                self.logger.debug(f"Rate limiting {api_name}, sleeping for {sleep_time:.2f}s")
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
        """
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

    def download_daily_data(self, ts_code: str, start_date: str = '20100101', end_date: str = '20231231') -> pd.DataFrame:
        """
        Download daily data for a specific stock
        """
        try:
            result = self.download_with_retry(
                self.pro.daily,
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date
            )
            self.logger.info(f"Successfully downloaded daily data for {ts_code}: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download daily data for {ts_code}: {e}")
            ErrorHandler.handle_api_error(e, f"download_daily_data for {ts_code}")
            raise


# Example usage
if __name__ == "__main__":
    downloader = TuShareDownloader()
    # Example calls - these would be used by the main system
    # basic_info = downloader.download_stock_basic()
    # daily_data = downloader.download_daily_data('000001.SZ')