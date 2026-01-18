"""
资金流向接口模块
包含各种资金流向接口
"""
import pandas as pd
import logging
from datetime import datetime
from typing import List
try:
    from ..config import TUSHARE_POINTS
except ImportError:
    from config import TUSHARE_POINTS
try:
    from ..error_handler import ErrorHandler, retry_on_failure
except ImportError:
    from error_handler import ErrorHandler, retry_on_failure
try:
    from ..cache_key_generator import CacheKeyGenerator
except ImportError:
    from cache_key_generator import CacheKeyGenerator
try:
    from ...data_storage import is_interface_data_cached, load_interface_cached_data, save_interface_data_to_cache
except ImportError:
    from data_storage import is_interface_data_cached, load_interface_cached_data, save_interface_data_to_cache


class MarketFlowDownloader:
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

    def download_moneyflow_range(self, start_date: str, end_date: str) -> pd.DataFrame:
        """
        按日期范围下载资金流向数据
        实现智能分批处理，支持缓存
        """
        if TUSHARE_POINTS < 2000:
            self.logger.warning("moneyflow requires 2000+ points, skipping download")
            return pd.DataFrame()

        cache_key = CacheKeyGenerator.generate_cache_key('moneyflow', start_date=start_date, end_date=end_date)

        if is_interface_data_cached('moneyflow', start_date=start_date, end_date=end_date):
            cached = load_interface_cached_data('moneyflow', start_date=start_date, end_date=end_date)
            if not cached.empty:
                self.logger.info(f"使用缓存: moneyflow {start_date} to {end_date}")
                return cached

        try:
            result = self.download_with_retry(
                self.pro.moneyflow,
                start_date=start_date,
                end_date=end_date
            )
            if not result.empty:
                save_interface_data_to_cache(result, 'moneyflow', start_date=start_date, end_date=end_date)
            self.logger.info(f"Successfully downloaded money flow range {start_date} to {end_date}: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download money flow range {start_date} to {end_date}: {e}")
            ErrorHandler.handle_api_error(e, "download_daily_moneyflow_range")
            raise

    def download_moneyflow_dc_paginated(self, trade_date: str, limit_per_call: int = 6000) -> pd.DataFrame:
        """
        分页下载moneyflow_dc数据 - 通过策略系统以支持缓存
        """
        from ..download_strategies import get_strategy
        strategy = get_strategy('moneyflow_dc', downloader=self)
        return strategy.download_with_cache(trade_date=trade_date)

    def download_moneyflow_ths(self, trade_date: str = '20231201') -> pd.DataFrame:
        """
        Download individual stock money flow (THS)
        Available to users with 5000+ points
        """
        if TUSHARE_POINTS < 5000:
            self.logger.warning("moneyflow_ths requires 5000+ points, skipping download")
            return pd.DataFrame()

        if is_interface_data_cached('moneyflow_ths', trade_date=trade_date):
            cached = load_interface_cached_data('moneyflow_ths', trade_date=trade_date)
            if not cached.empty:
                self.logger.info(f"使用缓存: moneyflow_ths {trade_date}")
                return cached

        try:
            result = self.download_with_retry(
                self.pro.moneyflow_ths,
                trade_date=trade_date
            )
            if not result.empty:
                save_interface_data_to_cache(result, 'moneyflow_ths', trade_date=trade_date)
            self.logger.info(f"Successfully downloaded moneyflow_ths: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download moneyflow_ths: {e}")
            ErrorHandler.handle_api_error(e, "download_moneyflow_ths")
            raise

    def download_moneyflow_dc(self, trade_date: str = '20231201') -> pd.DataFrame:
        """
        Download individual stock money flow (East Money)
        Available to users with 5000+ points
        """
        if TUSHARE_POINTS < 5000:
            self.logger.warning("moneyflow_dc requires 5000+ points, skipping download")
            return pd.DataFrame()

        if is_interface_data_cached('moneyflow_dc', trade_date=trade_date):
            cached = load_interface_cached_data('moneyflow_dc', trade_date=trade_date)
            if not cached.empty:
                self.logger.info(f"使用缓存: moneyflow_dc {trade_date}")
                return cached

        try:
            result = self.download_with_retry(
                self.pro.moneyflow_dc,
                trade_date=trade_date
            )
            if not result.empty:
                save_interface_data_to_cache(result, 'moneyflow_dc', trade_date=trade_date)
            self.logger.info(f"Successfully downloaded moneyflow_dc: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download moneyflow_dc: {e}")
            ErrorHandler.handle_api_error(e, "download_moneyflow_dc")
            raise

    def download_moneyflow_ind_dc(self, trade_date: str = '20231201') -> pd.DataFrame:
        """
        Download industry/concept money flow (East Money)
        Available to users with 5000+ points
        """
        if TUSHARE_POINTS < 5000:
            self.logger.warning("moneyflow_ind_dc requires 5000+ points, skipping download")
            return pd.DataFrame()

        if is_interface_data_cached('moneyflow_ind_dc', trade_date=trade_date):
            cached = load_interface_cached_data('moneyflow_ind_dc', trade_date=trade_date)
            if not cached.empty:
                self.logger.info(f"使用缓存: moneyflow_ind_dc {trade_date}")
                return cached

        try:
            result = self.download_with_retry(
                self.pro.moneyflow_ind_dc,
                trade_date=trade_date
            )
            if not result.empty:
                save_interface_data_to_cache(result, 'moneyflow_ind_dc', trade_date=trade_date)
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

        if is_interface_data_cached('moneyflow_mkt_dc', trade_date=trade_date):
            cached = load_interface_cached_data('moneyflow_mkt_dc', trade_date=trade_date)
            if not cached.empty:
                self.logger.info(f"使用缓存: moneyflow_mkt_dc {trade_date}")
                return cached

        try:
            result = self.download_with_retry(
                self.pro.moneyflow_mkt_dc,
                trade_date=trade_date
            )
            if not result.empty:
                save_interface_data_to_cache(result, 'moneyflow_mkt_dc', trade_date=trade_date)
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

        if is_interface_data_cached('moneyflow_cnt_ths', trade_date=trade_date):
            cached = load_interface_cached_data('moneyflow_cnt_ths', trade_date=trade_date)
            if not cached.empty:
                self.logger.info(f"使用缓存: moneyflow_cnt_ths {trade_date}")
                return cached

        try:
            result = self.download_with_retry(
                self.pro.moneyflow_cnt_ths,
                trade_date=trade_date
            )
            if not result.empty:
                save_interface_data_to_cache(result, 'moneyflow_cnt_ths', trade_date=trade_date)
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

        if is_interface_data_cached('moneyflow_ind_ths', trade_date=trade_date):
            cached = load_interface_cached_data('moneyflow_ind_ths', trade_date=trade_date)
            if not cached.empty:
                self.logger.info(f"使用缓存: moneyflow_ind_ths {trade_date}")
                return cached

        try:
            result = self.download_with_retry(
                self.pro.moneyflow_ind_ths,
                trade_date=trade_date
            )
            if not result.empty:
                save_interface_data_to_cache(result, 'moneyflow_ind_ths', trade_date=trade_date)
            self.logger.info(f"Successfully downloaded moneyflow_ind_ths: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download moneyflow_ind_ths: {e}")
            ErrorHandler.handle_api_error(e, "download_moneyflow_ind_ths")
            raise

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