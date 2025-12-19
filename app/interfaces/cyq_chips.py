"""
Cyq Chips接口模块
包含每日筹码分布相关接口
"""
import pandas as pd
import logging
import time
try:
    from ..config import TUSHARE_POINTS
except ImportError:
    from config import TUSHARE_POINTS
try:
    from ..error_handler import ErrorHandler, retry_on_failure
except ImportError:
    from error_handler import ErrorHandler, retry_on_failure


class CyqChipsDownloader:
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

    def download_cyq_chips_optimized(self, start_date: str, end_date: str) -> pd.DataFrame:
        """
        优化后的cyq_chips下载方法，按股票批量下载而非按日期-股票双重循环
        这是解决API调用量过高问题的关键优化

        Args:
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)

        Returns:
            包含所有股票在指定日期范围内筹码分布数据的DataFrame
        """
        if TUSHARE_POINTS < 5000:
            self.logger.warning("cyq_chips requires 5000+ points, skipping download")
            return pd.DataFrame()

        try:
            # 获取股票列表
            from .basic_data import BasicDataDownloader
            basic_downloader = BasicDataDownloader(self.pro)
            stock_df = basic_downloader.download_stock_basic()
            if stock_df.empty:
                self.logger.warning("No stock data available, cannot download cyq_chips")
                return pd.DataFrame()

            all_data = []
            self.logger.info(f"Starting to download cyq_chips for {len(stock_df)} stocks from {start_date} to {end_date}")

            for i, stock in stock_df.iterrows():
                ts_code = stock['ts_code']

                if (i + 1) % 50 == 0:  # Log progress every 50 stocks
                    self.logger.info(f"Processed {i + 1}/{len(stock_df)} stocks...")

                try:
                    # 一次性获取该股票在指定日期范围内的所有数据
                    df = self.download_with_retry(
                        self.pro.cyq_chips,
                        ts_code=ts_code,
                        start_date=start_date,
                        end_date=end_date
                    )

                    if df is not None and not df.empty:
                        all_data.append(df)
                        self.logger.debug(f"Downloaded {len(df)} records for {ts_code}")
                    else:
                        self.logger.debug(f"No cyq_chips data for stock {ts_code} from {start_date} to {end_date}")

                    # 遵循API频率限制
                    time.sleep(0.1)

                except Exception as e:
                    self.logger.warning(f"Failed to download cyq_chips for {ts_code} from {start_date} to {end_date}: {e}")
                    # 继续处理下一个股票，即使当前股票失败
                    continue

            # 合并所有数据
            if all_data:
                result = pd.concat(all_data, ignore_index=True)
                self.logger.info(f"Successfully downloaded cyq_chips for date range: {len(result)} records")
                return result
            else:
                self.logger.warning("No cyq_chips data could be downloaded for any stock")
                return pd.DataFrame()

        except Exception as e:
            self.logger.error(f"Failed to download cyq_chips for date range: {e}")
            ErrorHandler.handle_api_error(e, "download_cyq_chips_optimized")
            raise