"""
TuShare API integration for aspipe_v4 with automatic token switching
"""
import tushare as ts
import time
import logging
from typing import Optional
try:
    from .config import TUSHARE_TOKEN, API_LIMITS, TUSHARE_POINTS, PRIMARY_TOKEN, SECONDARY_TOKEN, PROXY_URL
except ImportError:
    from config import TUSHARE_TOKEN, API_LIMITS, TUSHARE_POINTS, PRIMARY_TOKEN, SECONDARY_TOKEN, PROXY_URL
try:
    from .score_config import get_api_limits_for_score
except ImportError:
    from score_config import get_api_limits_for_score
import pandas as pd
try:
    from .error_handler import ErrorHandler, retry_on_failure
except ImportError:
    from error_handler import ErrorHandler, retry_on_failure


class TuShareDownloader:
    def __init__(self):
        """
        Initialize the TuShare API downloader with token authentication and rate limiting
        """
        # Store both tokens for switching
        self.primary_token = PRIMARY_TOKEN
        self.secondary_token = SECONDARY_TOKEN
        self.current_token = TUSHARE_TOKEN  # Use the default token initially
        self.current_points = TUSHARE_POINTS
        self.current_proxy = PROXY_URL

        # Set proxy if available
        if self.current_proxy:
            import os
            os.environ["HTTP_PROXY"] = self.current_proxy
            os.environ["HTTPS_PROXY"] = self.current_proxy

        # Initialize with current token
        self.pro = ts.pro_api(self.current_token)

        # Update API limits based on current user's points
        self.api_limits = get_api_limits_for_score(self.current_points)
        self.last_call_times = {}

        self.logger = logging.getLogger(__name__)

    def switch_token(self):
        """
        Switch to the secondary token if available, or back to primary
        """
        if self.primary_token and self.secondary_token:
            if self.current_token == self.primary_token:
                # Switch to secondary token
                self.current_token = self.secondary_token
                self.current_points = int(__import__('os').environ.get('tushare2_points', '2000'))
                self.current_proxy = __import__('os').environ.get('PROXY_URL2', '')
                self.logger.info("Switching to secondary token")
            else:
                # Switch back to primary token
                self.current_token = self.primary_token
                self.current_points = int(__import__('os').environ.get('tushare_points', '120'))
                self.current_proxy = __import__('os').environ.get('PROXY_URL', '')
                self.logger.info("Switching to primary token")

            # Update proxy settings
            if self.current_proxy:
                import os
                os.environ["HTTP_PROXY"] = self.current_proxy
                os.environ["HTTPS_PROXY"] = self.current_proxy
            else:
                # Clear proxy if empty
                if "HTTP_PROXY" in __import__('os').environ:
                    del __import__('os').environ["HTTP_PROXY"]
                if "HTTPS_PROXY" in __import__('os').environ:
                    del __import__('os').environ["HTTPS_PROXY"]

            # Reinitialize the API with the new token
            self.pro = ts.pro_api(self.current_token)
            # Update API limits based on new points
            self.api_limits = get_api_limits_for_score(self.current_points)
        else:
            self.logger.warning("Only one token available, cannot switch")

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

                # Check if the error is related to token authentication
                error_msg = str(e).lower()
                if "token" in error_msg or "auth" in error_msg:
                    # Try switching to the other token
                    if self.primary_token and self.secondary_token:
                        self.switch_token()
                        self.logger.info(f"Switched token due to authentication error. Retrying {api_name}...")
                        # Retry immediately with the new token
                        try:
                            result = api_func(*args, **kwargs)
                            self.logger.info(f"Successfully called {api_name} after token switch, got {len(result) if hasattr(result, '__len__') else 'unknown'} records")
                            return result
                        except Exception as retry_e:
                            self.logger.warning(f"Retry with switched token failed for {api_name}: {str(retry_e)}")

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

    def download_daily_data(self, ts_code: str, start_date: str = '20100101', end_date: str = '20231231') -> pd.DataFrame:
        """
        Download daily data for a specific stock
        Available to all users
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
                end_date=end_date
            )
            self.logger.info(f"Successfully downloaded trade calendar: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download trade calendar: {e}")
            ErrorHandler.handle_api_error(e, "download_trade_cal")
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

    def download_income(self, period: str = '20231231', ts_code: str = None) -> pd.DataFrame:
        """
        Download income statement data
        Available to users with 2000+ points
        Uses VIP version if user has 5000+ points
        """
        if TUSHARE_POINTS < 2000:
            self.logger.warning("income requires 2000+ points, skipping download")
            return pd.DataFrame()

        try:
            # Use VIP version if available (5000+ points)
            api_func = self.pro.income_vip if TUSHARE_POINTS >= 5000 else self.pro.income

            params = {'period': period}
            if ts_code:
                params['ts_code'] = ts_code
            else:
                # If no ts_code provided, just use period (for single quarter data)
                pass

            result = self.download_with_retry(api_func, **params)
            self.logger.info(f"Successfully downloaded income statement: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download income statement: {e}")
            ErrorHandler.handle_api_error(e, "download_income")
            raise

    def download_balancesheet(self, period: str = '20231231', ts_code: str = None) -> pd.DataFrame:
        """
        Download balance sheet data
        Available to users with 2000+ points
        Uses VIP version if user has 5000+ points
        """
        if TUSHARE_POINTS < 2000:
            self.logger.warning("balancesheet requires 2000+ points, skipping download")
            return pd.DataFrame()

        try:
            # Use VIP version if available (5000+ points)
            api_func = self.pro.balancesheet_vip if TUSHARE_POINTS >= 5000 else self.pro.balancesheet

            params = {'period': period}
            if ts_code:
                params['ts_code'] = ts_code
            else:
                # If no ts_code provided, just use period (for single quarter data)
                pass

            result = self.download_with_retry(api_func, **params)
            self.logger.info(f"Successfully downloaded balance sheet: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download balance sheet: {e}")
            ErrorHandler.handle_api_error(e, "download_balancesheet")
            raise

    def download_cashflow(self, period: str = '20231231', ts_code: str = None) -> pd.DataFrame:
        """
        Download cash flow statement data
        Available to users with 2000+ points
        Uses VIP version if user has 5000+ points
        """
        if TUSHARE_POINTS < 2000:
            self.logger.warning("cashflow requires 2000+ points, skipping download")
            return pd.DataFrame()

        try:
            # Use VIP version if available (5000+ points)
            api_func = self.pro.cashflow_vip if TUSHARE_POINTS >= 5000 else self.pro.cashflow

            params = {'period': period}
            if ts_code:
                params['ts_code'] = ts_code
            else:
                # If no ts_code provided, just use period (for single quarter data)
                pass

            result = self.download_with_retry(api_func, **params)
            self.logger.info(f"Successfully downloaded cash flow: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download cash flow: {e}")
            ErrorHandler.handle_api_error(e, "download_cashflow")
            raise

    def download_fina_indicator(self, period: str = '20231231', ts_code: str = None) -> pd.DataFrame:
        """
        Download financial indicators data
        Available to users with 2000+ points
        Uses VIP version if user has 5000+ points
        """
        if TUSHARE_POINTS < 2000:
            self.logger.warning("fina_indicator requires 2000+ points, skipping download")
            return pd.DataFrame()

        try:
            # Use VIP version if available (5000+ points)
            api_func = self.pro.fina_indicator_vip if TUSHARE_POINTS >= 5000 else self.pro.fina_indicator

            params = {'period': period}
            if ts_code:
                params['ts_code'] = ts_code
            else:
                # If no ts_code provided, just use period (for single quarter data)
                pass

            result = self.download_with_retry(api_func, **params)
            self.logger.info(f"Successfully downloaded financial indicators: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download financial indicators: {e}")
            ErrorHandler.handle_api_error(e, "download_fina_indicator")
            raise

    def download_moneyflow(self, trade_date: str = '20231201') -> pd.DataFrame:
        """
        Download individual stock money flow data
        Available to users with 2000+ points
        """
        if TUSHARE_POINTS < 2000:
            self.logger.warning("moneyflow requires 2000+ points, skipping download")
            return pd.DataFrame()

        try:
            result = self.download_with_retry(
                self.pro.moneyflow,
                trade_date=trade_date
            )
            self.logger.info(f"Successfully downloaded money flow: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download money flow: {e}")
            ErrorHandler.handle_api_error(e, "download_moneyflow")
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

    def download_namechange_with_period_split(self, start_date: str, end_date: str, ts_code: str = None) -> pd.DataFrame:
        """
        Download namechange data with automatic time period splitting
        When download period exceeds 30 days, automatically decompose into multiple segments
        of no more than 30 days each

        Args:
            start_date: Start date in format YYYYMMDD
            end_date: End date in format YYYYMMDD
            ts_code: Optional stock code

        Returns:
            DataFrame with combined data from all periods
        """
        from datetime import datetime, timedelta

        try:
            # Parse dates
            start = datetime.strptime(start_date, '%Y%m%d')
            end = datetime.strptime(end_date, '%Y%m%d')

            all_data = []
            current_start = start

            # Process in 30-day segments
            while current_start <= end:
                # Calculate end of current segment (max 30 days)
                current_end = min(current_start + timedelta(days=30), end)

                # Format date strings
                current_start_str = current_start.strftime('%Y%m%d')
                current_end_str = current_end.strftime('%Y%m%d')

                try:
                    # Download data for current segment
                    params = {
                        'start_date': current_start_str,
                        'end_date': current_end_str
                    }
                    if ts_code:
                        params['ts_code'] = ts_code

                    df = self.download_with_retry(
                        self.pro.namechange,
                        **params
                    )

                    if df is not None and not df.empty:
                        all_data.append(df)
                        self.logger.info(f"Successfully downloaded namechange data for {current_start_str} to {current_end_str}: {len(df)} records")
                    else:
                        self.logger.debug(f"No namechange data for {current_start_str} to {current_end_str}")

                except Exception as e:
                    self.logger.error(f"Failed to download namechange data for {current_start_str} to {current_end_str}: {e}")
                    # Continue with next segment even if one fails

                # Move to next segment
                current_start = current_end + timedelta(days=1)

            # Combine all data
            if all_data:
                result = pd.concat(all_data, ignore_index=True)
                self.logger.info(f"Successfully downloaded namechange data with period splitting: {len(result)} records total")
                return result
            else:
                self.logger.warning("No namechange data could be downloaded with period splitting")
                return pd.DataFrame()

        except Exception as e:
            self.logger.error(f"Failed to download namechange data with period splitting: {e}")
            ErrorHandler.handle_api_error(e, "download_namechange_with_period_split")
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

    def download_forecast(self, period: str = '20231231') -> pd.DataFrame:
        """
        Download earnings forecast
        Available to users with 2000+ points
        Uses VIP version if user has 5000+ points, falls back to per-stock download if needed
        """
        if TUSHARE_POINTS < 2000:
            self.logger.warning("forecast requires 2000+ points, skipping download")
            return pd.DataFrame()

        try:
            # Use VIP version if available (5000+ points) for full market data
            if TUSHARE_POINTS >= 5000:
                # Use VIP interface to get full market data
                result = self.download_with_retry(
                    self.pro.forecast_vip,
                    period=period
                )
                self.logger.info(f"Successfully downloaded forecast_vip: {len(result)} records")
                return result
            else:
                # For users with lower points, fall back to per-stock download
                # Get stock list first
                stock_df = self.download_stock_basic()
                all_data = []
                for _, stock in stock_df.iterrows():
                    ts_code = stock['ts_code']
                    try:
                        df = self.download_with_retry(
                            self.pro.forecast,
                            ts_code=ts_code,
                            period=period
                        )
                        if df is not None and not df.empty:
                            all_data.append(df)
                    except Exception as e:
                        self.logger.warning(f"Failed to download forecast for {ts_code}: {e}")
                        continue  # Continue with next stock even if one fails

                # Combine all data
                if all_data:
                    result = pd.concat(all_data, ignore_index=True)
                    self.logger.info(f"Successfully downloaded forecast for multiple stocks: {len(result)} records")
                    return result
                else:
                    self.logger.warning("No forecast data could be downloaded for any stock")
                    return pd.DataFrame()
        except Exception as e:
            self.logger.error(f"Failed to download forecast: {e}")
            ErrorHandler.handle_api_error(e, "download_forecast")
            raise

    def download_express(self, period: str = '20231231') -> pd.DataFrame:
        """
        Download earnings express (fast report)
        Available to users with 2000+ points
        Uses VIP version if user has 5000+ points, falls back to per-stock download if needed
        """
        if TUSHARE_POINTS < 2000:
            self.logger.warning("express requires 2000+ points, skipping download")
            return pd.DataFrame()

        try:
            # Use VIP version if available (5000+ points) for full market data
            if TUSHARE_POINTS >= 5000:
                # Use VIP interface to get full market data
                result = self.download_with_retry(
                    self.pro.express_vip,
                    period=period
                )
                self.logger.info(f"Successfully downloaded express_vip: {len(result)} records")
                return result
            else:
                # For users with lower points, fall back to per-stock download
                # Get stock list first
                stock_df = self.download_stock_basic()
                all_data = []
                for _, stock in stock_df.iterrows():
                    ts_code = stock['ts_code']
                    try:
                        df = self.download_with_retry(
                            self.pro.express,
                            ts_code=ts_code,
                            period=period
                        )
                        if df is not None and not df.empty:
                            all_data.append(df)
                    except Exception as e:
                        self.logger.warning(f"Failed to download express for {ts_code}: {e}")
                        continue  # Continue with next stock even if one fails

                # Combine all data
                if all_data:
                    result = pd.concat(all_data, ignore_index=True)
                    self.logger.info(f"Successfully downloaded express for multiple stocks: {len(result)} records")
                    return result
                else:
                    self.logger.warning("No express data could be downloaded for any stock")
                    return pd.DataFrame()
        except Exception as e:
            self.logger.error(f"Failed to download express: {e}")
            ErrorHandler.handle_api_error(e, "download_express")
            raise

    def download_fina_audit(self, period: str = '20231231', ts_code: str = None) -> pd.DataFrame:
        """
        Download financial audit opinions
        Available to users with 500+ points
        """
        if TUSHARE_POINTS < 500:
            self.logger.warning("fina_audit requires 500+ points, skipping download")
            return pd.DataFrame()

        try:
            params = {'period': period}
            if ts_code:
                params['ts_code'] = ts_code

            result = self.download_with_retry(
                self.pro.fina_audit,
                **params
            )
            self.logger.info(f"Successfully downloaded fina_audit: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download fina_audit: {e}")
            ErrorHandler.handle_api_error(e, "download_fina_audit")
            raise

    def download_fina_mainbz(self, period: str = '20231231', ts_code: str = None, type_: str = 'P') -> pd.DataFrame:
        """
        Download main business composition (by product or region)
        Available to users with 2000+ points
        Uses VIP version if user has 5000+ points
        """
        if TUSHARE_POINTS < 2000:
            self.logger.warning("fina_mainbz requires 2000+ points, skipping download")
            return pd.DataFrame()

        try:
            # Use VIP version if available (5000+ points)
            api_func = self.pro.fina_mainbz_vip if TUSHARE_POINTS >= 5000 else self.pro.fina_mainbz

            params = {'period': period, 'type': type_}
            if ts_code:
                params['ts_code'] = ts_code

            result = self.download_with_retry(
                api_func,
                **params
            )
            self.logger.info(f"Successfully downloaded fina_mainbz: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download fina_mainbz: {e}")
            ErrorHandler.handle_api_error(e, "download_fina_mainbz")
            raise

    def download_disclosure_date(self, ann_date: str = '20231201') -> pd.DataFrame:
        """
        Download financial report disclosure schedule
        Available to users with 500+ points
        """
        if TUSHARE_POINTS < 500:
            self.logger.warning("disclosure_date requires 500+ points, skipping download")
            return pd.DataFrame()

        try:
            result = self.download_with_retry(
                self.pro.disclosure_date,
                ann_date=ann_date
            )
            self.logger.info(f"Successfully downloaded disclosure_date: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download disclosure_date: {e}")
            ErrorHandler.handle_api_error(e, "download_disclosure_date")
            raise

    # ===== Missing Interfaces Added per Implementation Plan =====
    
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

    def download_moneyflow_dc(self, trade_date: str = '20231201') -> pd.DataFrame:
        """
        Download individual stock money flow (East Money)
        Available to users with 5000+ points
        """
        if TUSHARE_POINTS < 5000:
            self.logger.warning("moneyflow_dc requires 5000+ points, skipping download")
            return pd.DataFrame()

        try:
            result = self.download_with_retry(
                self.pro.moneyflow_dc,
                trade_date=trade_date
            )
            self.logger.info(f"Successfully downloaded moneyflow_dc: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download moneyflow_dc: {e}")
            ErrorHandler.handle_api_error(e, "download_moneyflow_dc")
            raise

    def download_moneyflow_ths(self, trade_date: str = '20231201') -> pd.DataFrame:
        """
        Download individual stock money flow (THS)
        Available to users with 5000+ points
        """
        if TUSHARE_POINTS < 5000:
            self.logger.warning("moneyflow_ths requires 5000+ points, skipping download")
            return pd.DataFrame()

        try:
            result = self.download_with_retry(
                self.pro.moneyflow_ths,
                trade_date=trade_date
            )
            self.logger.info(f"Successfully downloaded moneyflow_ths: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download moneyflow_ths: {e}")
            ErrorHandler.handle_api_error(e, "download_moneyflow_ths")
            raise

    def download_moneyflow_ind_dc(self, trade_date: str = '20231201') -> pd.DataFrame:
        """
        Download industry/concept money flow (East Money)
        Available to users with 5000+ points
        """
        if TUSHARE_POINTS < 5000:
            self.logger.warning("moneyflow_ind_dc requires 5000+ points, skipping download")
            return pd.DataFrame()

        try:
            result = self.download_with_retry(
                self.pro.moneyflow_ind_dc,
                trade_date=trade_date
            )
            self.logger.info(f"Successfully downloaded moneyflow_ind_dc: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download moneyflow_ind_dc: {e}")
            ErrorHandler.handle_api_error(e, "download_moneyflow_ind_dc")
            raise

    def download_moneyflow_mkt_dc(self, trade_date: str = '20231201') -> pd.DataFrame:
        """
        Download market money flow (East Money)
        Available to users with 5000+ points
        """
        if TUSHARE_POINTS < 5000:
            self.logger.warning("moneyflow_mkt_dc requires 5000+ points, skipping download")
            return pd.DataFrame()

        try:
            result = self.download_with_retry(
                self.pro.moneyflow_mkt_dc,
                trade_date=trade_date
            )
            self.logger.info(f"Successfully downloaded moneyflow_mkt_dc: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download moneyflow_mkt_dc: {e}")
            ErrorHandler.handle_api_error(e, "download_moneyflow_mkt_dc")
            raise

    def download_moneyflow_cnt_ths(self, trade_date: str = '20231201') -> pd.DataFrame:
        """
        Download concept sector money flow (THS)
        Available to users with 5000+ points
        """
        if TUSHARE_POINTS < 5000:
            self.logger.warning("moneyflow_cnt_ths requires 5000+ points, skipping download")
            return pd.DataFrame()

        try:
            result = self.download_with_retry(
                self.pro.moneyflow_cnt_ths,
                trade_date=trade_date
            )
            self.logger.info(f"Successfully downloaded moneyflow_cnt_ths: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download moneyflow_cnt_ths: {e}")
            ErrorHandler.handle_api_error(e, "download_moneyflow_cnt_ths")
            raise

    def download_moneyflow_ind_ths(self, trade_date: str = '20231201') -> pd.DataFrame:
        """
        Download industry sector money flow (THS)
        Available to users with 5000+ points
        """
        if TUSHARE_POINTS < 5000:
            self.logger.warning("moneyflow_ind_ths requires 5000+ points, skipping download")
            return pd.DataFrame()

        try:
            result = self.download_with_retry(
                self.pro.moneyflow_ind_ths,
                trade_date=trade_date
            )
            self.logger.info(f"Successfully downloaded moneyflow_ind_ths: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download moneyflow_ind_ths: {e}")
            ErrorHandler.handle_api_error(e, "download_moneyflow_ind_ths")
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

    def download_stk_factor(self, trade_date: str = '20231201') -> pd.DataFrame:
        """
        Download stock technical factors
        Available to users with 5000+ points
        """
        if TUSHARE_POINTS < 5000:
            self.logger.warning("stk_factor requires 5000+ points, skipping download")
            return pd.DataFrame()

        try:
            result = self.download_with_retry(
                self.pro.stk_factor,
                trade_date=trade_date
            )
            self.logger.info(f"Successfully downloaded stk_factor: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download stk_factor: {e}")
            ErrorHandler.handle_api_error(e, "download_stk_factor")
            raise

    def download_stk_factor_pro(self, trade_date: str = '20231201') -> pd.DataFrame:
        """
        Download stock technical factors (professional version)
        Available to users with 5000+ points
        """
        if TUSHARE_POINTS < 5000:
            self.logger.warning("stk_factor_pro requires 5000+ points, skipping download")
            return pd.DataFrame()

        try:
            result = self.download_with_retry(
                self.pro.stk_factor_pro,
                trade_date=trade_date
            )
            self.logger.info(f"Successfully downloaded stk_factor_pro: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download stk_factor_pro: {e}")
            ErrorHandler.handle_api_error(e, "download_stk_factor_pro")
            raise

    def download_cyq_perf(self, trade_date: str = '20231201') -> pd.DataFrame:
        """
        Download daily chip distribution and win rate
        Available to users with 5000+ points
        """
        if TUSHARE_POINTS < 5000:
            self.logger.warning("cyq_perf requires 5000+ points, skipping download")
            return pd.DataFrame()

        try:
            result = self.download_with_retry(
                self.pro.cyq_perf,
                trade_date=trade_date
            )
            self.logger.info(f"Successfully downloaded cyq_perf: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download cyq_perf: {e}")
            ErrorHandler.handle_api_error(e, "download_cyq_perf")
            raise

    def download_cyq_chips(self, ts_code: str, trade_date: str = None, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """
        Download daily chip distribution
        Available to users with 5000+ points
        Must provide ts_code parameter, and either trade_date or (start_date, end_date)
        """
        if TUSHARE_POINTS < 5000:
            self.logger.warning("cyq_chips requires 5000+ points, skipping download")
            return pd.DataFrame()

        try:
            # Build parameters based on what was provided
            params = {}
            if ts_code:
                params['ts_code'] = ts_code
            if trade_date:
                params['trade_date'] = trade_date
            elif start_date and end_date:
                params['start_date'] = start_date
                params['end_date'] = end_date

            result = self.download_with_retry(
                self.pro.cyq_chips,
                **params
            )
            self.logger.info(f"Successfully downloaded cyq_chips: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download cyq_chips: {e}")
            ErrorHandler.handle_api_error(e, "download_cyq_chips")
            raise

    def download_cyq_chips_for_all_stocks(self, trade_date: str = '20231201') -> pd.DataFrame:
        """
        Download cyq_chips data for all stocks by looping through each stock code
        Available to users with 5000+ points
        """
        if TUSHARE_POINTS < 5000:
            self.logger.warning("cyq_chips_for_all_stocks requires 5000+ points, skipping download")
            return pd.DataFrame()

        try:
            # Get stock list first
            stock_df = self.download_stock_basic()
            if stock_df.empty:
                self.logger.warning("No stock data available, cannot download cyq_chips for all stocks")
                return pd.DataFrame()

            all_data = []
            self.logger.info(f"Starting to download cyq_chips for {len(stock_df)} stocks on {trade_date}")

            for i, stock in stock_df.iterrows():
                ts_code = stock['ts_code']

                if (i + 1) % 50 == 0:  # Log progress every 50 stocks
                    self.logger.info(f"Processed {i + 1}/{len(stock_df)} stocks...")

                try:
                    df = self.download_with_retry(
                        self.pro.cyq_chips,
                        ts_code=ts_code,
                        trade_date=trade_date
                    )
                    if df is not None and not df.empty:
                        all_data.append(df)
                    else:
                        self.logger.debug(f"No cyq_chips data for stock {ts_code} on {trade_date}")

                except Exception as e:
                    self.logger.warning(f"Failed to download cyq_chips for {ts_code} on {trade_date}: {e}")
                    continue  # Continue with next stock even if one fails

            # Combine all data
            if all_data:
                result = pd.concat(all_data, ignore_index=True)
                self.logger.info(f"Successfully downloaded cyq_chips for all stocks: {len(result)} records")
                return result
            else:
                self.logger.warning("No cyq_chips data could be downloaded for any stock")
                return pd.DataFrame()

        except Exception as e:
            self.logger.error(f"Failed to download cyq_chips for all stocks: {e}")
            ErrorHandler.handle_api_error(e, "download_cyq_chips_for_all_stocks")
            raise

    def download_cyq_chips_with_date_range(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Download cyq_chips data for a specific stock over a date range
        Available to users with 5000+ points
        """
        if TUSHARE_POINTS < 5000:
            self.logger.warning("cyq_chips_with_date_range requires 5000+ points, skipping download")
            return pd.DataFrame()

        try:
            result = self.download_with_retry(
                self.pro.cyq_chips,
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date
            )
            self.logger.info(f"Successfully downloaded cyq_chips for {ts_code} ({start_date} to {end_date}): {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download cyq_chips for {ts_code} ({start_date} to {end_date}): {e}")
            ErrorHandler.handle_api_error(e, f"download_cyq_chips for {ts_code}")
            raise

    def download_report_rc(self, period: str = '20231231', ts_code: str = None) -> pd.DataFrame:
        """
        Download sell-side earnings forecast data
        Available to users with 5000+ points (8000+ for formal access)
        """
        if TUSHARE_POINTS < 5000:
            self.logger.warning("report_rc requires 5000+ points, skipping download")
            return pd.DataFrame()

        try:
            params = {'period': period}
            if ts_code:
                params['ts_code'] = ts_code

            result = self.download_with_retry(
                self.pro.report_rc,
                **params
            )
            self.logger.info(f"Successfully downloaded report_rc: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download report_rc: {e}")
            ErrorHandler.handle_api_error(e, "download_report_rc")
            raise

    def download_stk_surv(self, period: str = '20231231', ts_code: str = None) -> pd.DataFrame:
        """
        Download institutional research survey
        Available to users with 5000+ points
        """
        if TUSHARE_POINTS < 5000:
            self.logger.warning("stk_surv requires 5000+ points, skipping download")
            return pd.DataFrame()

        try:
            params = {'period': period}
            if ts_code:
                params['ts_code'] = ts_code

            result = self.download_with_retry(
                self.pro.stk_surv,
                **params
            )
            self.logger.info(f"Successfully downloaded stk_surv: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download stk_surv: {e}")
            ErrorHandler.handle_api_error(e, "download_stk_surv")
            raise

    def download_broker_recommend(self, month: str) -> pd.DataFrame:
        """
        Download broker monthly stock recommendations
        Available to users with 2000+ points
        Must provide month parameter in YYYYMM format
        """
        if TUSHARE_POINTS < 2000:
            self.logger.warning("broker_recommend requires 2000+ points, skipping download")
            return pd.DataFrame()

        try:
            result = self.download_with_retry(
                self.pro.broker_recommend,
                month=month
            )
            self.logger.info(f"Successfully downloaded broker_recommend: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download broker_recommend: {e}")
            ErrorHandler.handle_api_error(e, "download_broker_recommend")
            raise


    def download_with_pagination(self, api_func, limit_per_call=2000, **base_kwargs):
        """
        分页下载数据的通用函数

        Args:
            api_func: API调用函数
            limit_per_call: 每次调用的最大记录数
            **base_kwargs: 传递给API函数的基础参数

        Returns:
            pd.DataFrame: 合并后的所有数据
        """
        all_data = []
        offset = 0

        while True:
            # 添加分页参数
            kwargs = base_kwargs.copy()
            kwargs['offset'] = offset
            kwargs['limit'] = limit_per_call

            try:
                data = api_func(**kwargs)
            except Exception as e:
                self.logger.error(f"分页下载失败, offset={offset}: {e}")
                break

            if data is None or len(data) == 0:
                break

            # 将DataFrame添加到列表中，而不是扩展DataFrame
            all_data.append(data)

            # 如果返回数据少于限制数量，说明已到最后一页
            if len(data) < limit_per_call:
                break

            offset += limit_per_call

        # 将所有数据合并成一个DataFrame
        if all_data:
            return pd.concat(all_data, ignore_index=True)
        else:
            return pd.DataFrame()

    def download_cyq_chips_paginated(self, ts_code: str, start_date: str = None, end_date: str = None,
                                   limit_per_call: int = 2000) -> pd.DataFrame:
        """
        分页下载cyq_chips数据

        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            limit_per_call: 每次调用的最大记录数

        Returns:
            pd.DataFrame: 合并后的所有数据
        """
        if TUSHARE_POINTS < 5000:
            self.logger.warning("cyq_chips requires 5000+ points, skipping download")
            return pd.DataFrame()

        # 构建基础参数
        base_params = {'ts_code': ts_code}
        if start_date:
            base_params['start_date'] = start_date
        if end_date:
            base_params['end_date'] = end_date

        return self.download_with_pagination(
            lambda **kwargs: self.pro.cyq_chips(**kwargs),
            limit_per_call=limit_per_call,
            **base_params
        )

    def download_broker_recommend_paginated(self, month: str, limit_per_call: int = 1000) -> pd.DataFrame:
        """
        分页下载broker_recommend数据

        Args:
            month: 月份 (YYYYMM格式)
            limit_per_call: 每次调用的最大记录数

        Returns:
            pd.DataFrame: 合并后的所有数据
        """
        if TUSHARE_POINTS < 2000:
            self.logger.warning("broker_recommend requires 2000+ points, skipping download")
            return pd.DataFrame()

        return self.download_with_pagination(
            lambda **kwargs: self.pro.broker_recommend(**kwargs),
            limit_per_call=limit_per_call,
            month=month
        )

    def download_moneyflow_dc_paginated(self, trade_date: str, limit_per_call: int = 6000) -> pd.DataFrame:
        """
        分页下载moneyflow_dc数据

        Args:
            trade_date: 交易日期
            limit_per_call: 每次调用的最大记录数

        Returns:
            pd.DataFrame: 合并后的所有数据
        """
        if TUSHARE_POINTS < 5000:
            self.logger.warning("moneyflow_dc requires 5000+ points, skipping download")
            return pd.DataFrame()

        return self.download_with_pagination(
            lambda **kwargs: self.pro.moneyflow_dc(**kwargs),
            limit_per_call=limit_per_call,
            trade_date=trade_date
        )

    def download_stk_factor_paginated(self, trade_date: str, limit_per_call: int = 10000) -> pd.DataFrame:
        """
        分页下载stk_factor数据

        Args:
            trade_date: 交易日期
            limit_per_call: 每次调用的最大记录数

        Returns:
            pd.DataFrame: 合并后的所有数据
        """
        if TUSHARE_POINTS < 5000:
            self.logger.warning("stk_factor requires 5000+ points, skipping download")
            return pd.DataFrame()

        return self.download_with_pagination(
            lambda **kwargs: self.pro.stk_factor(**kwargs),
            limit_per_call=limit_per_call,
            trade_date=trade_date
        )

    def download_cyq_perf_paginated(self, trade_date: str, limit_per_call: int = 5000) -> pd.DataFrame:
        """
        分页下载cyq_perf数据

        Args:
            trade_date: 交易日期
            limit_per_call: 每次调用的最大记录数

        Returns:
            pd.DataFrame: 合并后的所有数据
        """
        if TUSHARE_POINTS < 5000:
            self.logger.warning("cyq_perf requires 5000+ points, skipping download")
            return pd.DataFrame()

        return self.download_with_pagination(
            lambda **kwargs: self.pro.cyq_perf(**kwargs),
            limit_per_call=limit_per_call,
            trade_date=trade_date
        )

    def download_report_rc_paginated(self, period: str, ts_code: str = None, limit_per_call: int = 3000) -> pd.DataFrame:
        """
        分页下载report_rc数据

        Args:
            period: 报告期
            ts_code: 股票代码(可选)
            limit_per_call: 每次调用的最大记录数

        Returns:
            pd.DataFrame: 合并后的所有数据
        """
        if TUSHARE_POINTS < 5000:
            self.logger.warning("report_rc requires 5000+ points, skipping download")
            return pd.DataFrame()

        base_params = {'period': period}
        if ts_code:
            base_params['ts_code'] = ts_code

        return self.download_with_pagination(
            lambda **kwargs: self.pro.report_rc(**kwargs),
            limit_per_call=limit_per_call,
            **base_params
        )

    def safe_download(self, api_func, **kwargs):
        """
        为API调用添加安全包装，处理空数据和异常情况
        """
        try:
            data = api_func(**kwargs)
            if data is None or len(data) == 0:
                self.logger.warning(f"接口 {api_func.__name__} 返回空数据")
                return None
            return data
        except Exception as e:
            self.logger.error(f"接口 {api_func.__name__} 调用失败: {e}")
            return None

    def download_moneyflow_ths_safe(self, trade_date: str = '20231201') -> pd.DataFrame:
        """
        安全下载moneyflow_ths数据，处理可能的空返回
        """
        try:
            result = self.safe_download(self.pro.moneyflow_ths, trade_date=trade_date)
            if result is not None:
                self.logger.info(f"Successfully downloaded moneyflow_ths: {len(result)} records")
                return result
            else:
                self.logger.info("moneyflow_ths returned no data or failed")
                return pd.DataFrame()
        except Exception as e:
            self.logger.error(f"Failed to download moneyflow_ths: {e}")
            return pd.DataFrame()

    def download_moneyflow_cnt_ths_safe(self, trade_date: str = '20231201') -> pd.DataFrame:
        """
        安全下载moneyflow_cnt_ths数据，处理可能的空返回
        """
        try:
            result = self.safe_download(self.pro.moneyflow_cnt_ths, trade_date=trade_date)
            if result is not None:
                self.logger.info(f"Successfully downloaded moneyflow_cnt_ths: {len(result)} records")
                return result
            else:
                self.logger.info("moneyflow_cnt_ths returned no data or failed")
                return pd.DataFrame()
        except Exception as e:
            self.logger.error(f"Failed to download moneyflow_cnt_ths: {e}")
            return pd.DataFrame()

    def download_moneyflow_ind_ths_safe(self, trade_date: str = '20231201') -> pd.DataFrame:
        """
        安全下载moneyflow_ind_ths数据，处理可能的空返回
        """
        try:
            result = self.safe_download(self.pro.moneyflow_ind_ths, trade_date=trade_date)
            if result is not None:
                self.logger.info(f"Successfully downloaded moneyflow_ind_ths: {len(result)} records")
                return result
            else:
                self.logger.info("moneyflow_ind_ths returned no data or failed")
                return pd.DataFrame()
        except Exception as e:
            self.logger.error(f"Failed to download moneyflow_ind_ths: {e}")
            return pd.DataFrame()

    def download_forecast_safe(self, period: str = '20231231') -> pd.DataFrame:
        """
        安全下载forecast数据，处理可能的空返回
        """
        try:
            # Use VIP version if available (5000+ points)
            api_func = self.pro.forecast_vip if TUSHARE_POINTS >= 5000 else self.pro.forecast
            result = self.safe_download(api_func, period=period)
            if result is not None:
                self.logger.info(f"Successfully downloaded forecast: {len(result)} records")
                return result
            else:
                self.logger.info("forecast returned no data or failed")
                return pd.DataFrame()
        except Exception as e:
            self.logger.error(f"Failed to download forecast: {e}")
            return pd.DataFrame()

    def download_express_safe(self, period: str = '20231231') -> pd.DataFrame:
        """
        安全下载express数据，处理可能的空返回
        """
        try:
            # Use VIP version if available (5000+ points)
            api_func = self.pro.express_vip if TUSHARE_POINTS >= 5000 else self.pro.express
            result = self.safe_download(api_func, period=period)
            if result is not None:
                self.logger.info(f"Successfully downloaded express: {len(result)} records")
                return result
            else:
                self.logger.info("express returned no data or failed")
                return pd.DataFrame()
        except Exception as e:
            self.logger.error(f"Failed to download express: {e}")
            return pd.DataFrame()

# Example usage
if __name__ == "__main__":
    downloader = TuShareDownloader()
    # Example calls - these would be used by the main system
    # basic_info = downloader.download_stock_basic()
    # daily_data = downloader.download_daily_data('000001.SZ')