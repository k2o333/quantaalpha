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

# 导入各个接口模块
try:
    # 尝试相对导入，当作为包运行时
    from .interfaces.basic_data import BasicDataDownloader
    from .interfaces.daily_data import DailyDataDownloader
    from .interfaces.financial_data import FinancialDataDownloader
    from .interfaces.market_flow import MarketFlowDownloader
    from .interfaces.holders_data import HoldersDataDownloader
    from .interfaces.technical_factors import TechnicalFactorsDownloader
    from .interfaces.market_structure import MarketStructureDownloader
    from .interfaces.research_data import ResearchDataDownloader
except ImportError:
    # 当作为独立脚本运行时的回退导入
    from interfaces.basic_data import BasicDataDownloader
    from interfaces.daily_data import DailyDataDownloader
    from interfaces.financial_data import FinancialDataDownloader
    from interfaces.market_flow import MarketFlowDownloader
    from interfaces.holders_data import HoldersDataDownloader
    from interfaces.technical_factors import TechnicalFactorsDownloader
    from interfaces.market_structure import MarketStructureDownloader
    from interfaces.research_data import ResearchDataDownloader


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

        # 初始化各个接口模块
        self.basic_data = BasicDataDownloader(self.pro)
        self.daily_data = DailyDataDownloader(self.pro)
        self.financial_data = FinancialDataDownloader(self.pro)
        self.market_flow = MarketFlowDownloader(self.pro)
        self.holders_data = HoldersDataDownloader(self.pro)
        self.technical_factors = TechnicalFactorsDownloader(self.pro)
        self.market_structure = MarketStructureDownloader(self.pro)
        self.research_data = ResearchDataDownloader(self.pro)

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

    def __getattr__(self, name):
        """
        代理到各个子模块的方法
        保持向后兼容性
        """
        # 检查各个子模块是否包含该方法
        for module in [
            self.basic_data,
            self.daily_data,
            self.financial_data,
            self.market_flow,
            self.holders_data,
            self.technical_factors,
            self.market_structure,
            self.research_data
        ]:
            if hasattr(module, name):
                return getattr(module, name)

        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

# Example usage
if __name__ == "__main__":
    downloader = TuShareDownloader()
    # Example calls - these would be used by the main system
    # basic_info = downloader.download_stock_basic()
    # daily_data = downloader.download_daily_data('000001.SZ')