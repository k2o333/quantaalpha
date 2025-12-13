"""
技术因子接口模块
包含stk_factor, cyq系列等技术指标接口
"""
import pandas as pd
import logging
try:
    from ..config import TUSHARE_POINTS
except ImportError:
    from config import TUSHARE_POINTS
try:
    from ..error_handler import ErrorHandler, retry_on_failure
except ImportError:
    from error_handler import ErrorHandler, retry_on_failure


class TechnicalFactorsDownloader:
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
            from .basic_data import BasicDataDownloader
            basic_downloader = BasicDataDownloader(self.pro)
            stock_df = basic_downloader.download_stock_basic()
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

    def download_stk_factor_range(self, start_date: str, end_date: str) -> pd.DataFrame:
        """
        按日期范围下载技术因子数据
        实现分页和内存控制
        """
        if TUSHARE_POINTS < 5000:
            self.logger.warning("stk_factor requires 5000+ points, skipping download")
            return pd.DataFrame()

        # 获取交易日历
        from .basic_data import BasicDataDownloader
        basic_downloader = BasicDataDownloader(self.pro)

        try:
            trade_cal = basic_downloader.download_trade_cal(start_date=start_date, end_date=end_date)
            trading_days = trade_cal[trade_cal['is_open'] == 1]['cal_date'].tolist()
            trading_days.sort()

            all_data = []
            self.logger.info(f"Starting to download stk_factor for {len(trading_days)} trading days")

            for i, trade_date in enumerate(trading_days):
                if (i + 1) % 10 == 0:  # Log progress every 10 days
                    self.logger.info(f"Processed {i + 1}/{len(trading_days)} trading days...")

                try:
                    df = self.download_stk_factor(trade_date=trade_date)
                    if df is not None and not df.empty:
                        all_data.append(df)
                    else:
                        self.logger.debug(f"No stk_factor data for {trade_date}")
                except Exception as e:
                    self.logger.warning(f"Failed to download stk_factor for {trade_date}: {e}")
                    continue  # Continue with next day even if one fails

            # Combine all data
            if all_data:
                result = pd.concat(all_data, ignore_index=True)
                self.logger.info(f"Successfully downloaded stk_factor for date range: {len(result)} records")
                return result
            else:
                self.logger.warning("No stk_factor data could be downloaded for the date range")
                return pd.DataFrame()

        except Exception as e:
            self.logger.error(f"Failed to download stk_factor for date range: {e}")
            ErrorHandler.handle_api_error(e, "download_stk_factor_range")
            raise

    def download_cyq_chips_paginated(self, ts_code: str, start_date: str = None, end_date: str = None,
                                   limit_per_call: int = 2000) -> pd.DataFrame:
        """
        分页下载cyq_chips数据
        """
        return self.download_with_pagination(
            lambda **kwargs: self.pro.cyq_chips(**kwargs),
            limit_per_call=limit_per_call,
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date
        )

    def download_stk_factor_paginated(self, trade_date: str, limit_per_call: int = 10000) -> pd.DataFrame:
        """
        分页下载stk_factor数据
        """
        return self.download_with_pagination(
            lambda **kwargs: self.pro.stk_factor(**kwargs),
            limit_per_call=limit_per_call,
            trade_date=trade_date
        )

    def download_cyq_perf_paginated(self, trade_date: str, limit_per_call: int = 5000) -> pd.DataFrame:
        """
        分页下载cyq_perf数据
        """
        return self.download_with_pagination(
            lambda **kwargs: self.pro.cyq_perf(**kwargs),
            limit_per_call=limit_per_call,
            trade_date=trade_date
        )

    def download_with_pagination(self, api_func, limit_per_call=2000, **base_kwargs):
        """
        分页下载数据的通用函数
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