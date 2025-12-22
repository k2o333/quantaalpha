"""
股东数据接口模块
包含top10_holders, stk_rewards等股东相关接口
"""
import pandas as pd
import logging
from typing import List
try:
    from ..config import TUSHARE_POINTS
except ImportError:
    from config import TUSHARE_POINTS
try:
    from ..error_handler import ErrorHandler, retry_on_failure
except ImportError:
    from error_handler import ErrorHandler, retry_on_failure


class HoldersDataDownloader:
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

    def download_top10_holders(self, ts_code: str, period: str = '20231231') -> pd.DataFrame:
        """
        Download top 10 shareholders
        Available to users with 2000+ points
        """
        if TUSHARE_POINTS < 2000:
            self.logger.warning("top10_holders requires 2000+ points, skipping download")
            return pd.DataFrame()

        try:
            result = self.download_with_retry(
                self.pro.top10_holders,
                ts_code=ts_code,
                period=period
            )
            self.logger.info(f"Successfully downloaded top10_holders for {ts_code}: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download top10_holders for {ts_code}: {e}")
            ErrorHandler.handle_api_error(e, f"download_top10_holders for {ts_code}")
            raise

    def download_stk_rewards(self, ts_code: str) -> pd.DataFrame:
        """
        Download management compensation and shareholding
        Available to users with 2000+ points
        """
        if TUSHARE_POINTS < 2000:
            self.logger.warning("stk_rewards requires 2000+ points, skipping download")
            return pd.DataFrame()

        try:
            result = self.download_with_retry(
                self.pro.stk_rewards,
                ts_code=ts_code
            )
            self.logger.info(f"Successfully downloaded stk_rewards for {ts_code}: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download stk_rewards for {ts_code}: {e}")
            ErrorHandler.handle_api_error(e, f"download_stk_rewards for {ts_code}")
            raise

    def download_stk_rewards_batch(self, ts_codes: List[str], group_size: int = 20) -> pd.DataFrame:
        """
        批量下载管理层薪酬数据
        将股票代码分组批量查询
        """
        if TUSHARE_POINTS < 2000:
            self.logger.warning("stk_rewards requires 2000+ points, skipping download")
            return pd.DataFrame()

        if not ts_codes:
            self.logger.warning("No stock codes provided")
            return pd.DataFrame()

        all_data = []
        # 将股票代码分组处理
        for i in range(0, len(ts_codes), group_size):
            batch_codes = ts_codes[i:i + group_size]
            self.logger.info(f"Processing batch {i//group_size + 1}: {len(batch_codes)} stock codes")

            for ts_code in batch_codes:
                try:
                    df = self.download_stk_rewards(ts_code)
                    if df is not None and not df.empty:
                        all_data.append(df)
                    else:
                        self.logger.debug(f"No stk_rewards data for {ts_code}")
                except Exception as e:
                    self.logger.warning(f"Failed to download stk_rewards for {ts_code}: {e}")
                    continue  # Continue with next stock even if one fails

        # Combine all data
        if all_data:
            result = pd.concat(all_data, ignore_index=True)
            self.logger.info(f"Successfully downloaded stk_rewards batch: {len(result)} total records")
            return result
        else:
            self.logger.warning("No stk_rewards data could be downloaded for any stock")
            return pd.DataFrame()

    def download_stk_managers(self, ts_code: str = None) -> pd.DataFrame:
        """
        Download company management information
        Available to users with 2000+ points
        """
        if TUSHARE_POINTS < 2000:
            self.logger.warning("stk_managers requires 2000+ points, skipping download")
            return pd.DataFrame()

        try:
            params = {}
            if ts_code:
                params['ts_code'] = ts_code

            result = self.download_with_retry(
                self.pro.stk_managers,
                **params
            )
            self.logger.info(f"Successfully downloaded stk_managers: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download stk_managers: {e}")
            ErrorHandler.handle_api_error(e, "download_stk_managers")
            raise

    def download_top10_floatholders(self, ts_code: str, period: str = '20231231') -> pd.DataFrame:
        """
        Download top 10 floating shareholders
        Available to users with 5000+ points
        """
        if TUSHARE_POINTS < 5000:
            self.logger.warning("top10_floatholders requires 5000+ points, skipping download")
            return pd.DataFrame()

        try:
            result = self.download_with_retry(
                self.pro.top10_floatholders,
                ts_code=ts_code,
                period=period
            )
            self.logger.info(f"Successfully downloaded top10_floatholders for {ts_code}: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download top10_floatholders for {ts_code}: {e}")
            ErrorHandler.handle_api_error(e, f"download_top10_floatholders for {ts_code}")
            raise

    def download_stk_holdertrade(self, start_date: str = '20230101', end_date: str = '20231231') -> pd.DataFrame:
        """
        下载股东增减持数据
        """
        if TUSHARE_POINTS < 5000:
            self.logger.warning("stk_holdertrade requires 5000+ points, skipping download")
            return pd.DataFrame()

        try:
            result = self.download_with_retry(
                self.pro.stk_holdertrade,
                start_date=start_date,
                end_date=end_date
            )
            self.logger.info(f"Successfully downloaded stk_holdertrade: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download stk_holdertrade: {e}")
            ErrorHandler.handle_api_error(e, "download_stk_holdertrade")
            raise

    def download_pledge_detail(self, ts_code: str = None) -> pd.DataFrame:
        """
        Download pledge detail data
        Available to users with 5000+ points
        """
        if TUSHARE_POINTS < 5000:
            self.logger.warning("pledge_detail requires 5000+ points, skipping download")
            return pd.DataFrame()

        try:
            params = {}
            if ts_code:
                params['ts_code'] = ts_code

            result = self.download_with_retry(
                self.pro.pledge_detail,
                **params
            )
            self.logger.info(f"Successfully downloaded pledge_detail: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download pledge_detail: {e}")
            ErrorHandler.handle_api_error(e, "download_pledge_detail")
            raise

    def download_pledge_detail_batch(self, ts_codes: List[str], group_size: int = 20) -> pd.DataFrame:
        """
        批量下载股权质押明细数据
        将股票代码分组批量查询
        """
        if TUSHARE_POINTS < 5000:
            self.logger.warning("pledge_detail requires 5000+ points, skipping download")
            return pd.DataFrame()

        if not ts_codes:
            self.logger.warning("No stock codes provided")
            return pd.DataFrame()

        all_data = []
        # 将股票代码分组处理
        for i in range(0, len(ts_codes), group_size):
            batch_codes = ts_codes[i:i + group_size]
            self.logger.info(f"Processing batch {i//group_size + 1}: {len(batch_codes)} stock codes")

            for ts_code in batch_codes:
                try:
                    df = self.download_pledge_detail(ts_code)
                    if df is not None and not df.empty:
                        all_data.append(df)
                    else:
                        self.logger.debug(f"No pledge_detail data for {ts_code}")
                except Exception as e:
                    self.logger.warning(f"Failed to download pledge_detail for {ts_code}: {e}")
                    continue  # Continue with next stock even if one fails

        # Combine all data
        if all_data:
            result = pd.concat(all_data, ignore_index=True)
            self.logger.info(f"Successfully downloaded pledge_detail batch: {len(result)} total records")
            return result
        else:
            self.logger.warning("No pledge_detail data could be downloaded for any stock")
            return pd.DataFrame()