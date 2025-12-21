"""
TuShare API integration for aspipe_v4 with automatic token switching
"""
import tushare as ts
import time
import random
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
    from .interfaces.cyq_chips import CyqChipsDownloader
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
    from interfaces.cyq_chips import CyqChipsDownloader
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
        self.cyq_chips = CyqChipsDownloader(self.pro)
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
        # Use the advanced rate limiting method
        self._advanced_rate_limit(api_name)

    @retry_on_failure(max_retries=3, delay=1.0, backoff=2.0)
    def download_with_retry(self, api_func, *args, max_retries: int = 3, api_name: str = None, **kwargs):
        """
        Download data with retry mechanism and rate limiting
        """
        # Improved method to identify the API name, handling tushare's dynamic functions
        actual_api_name = api_name
        if actual_api_name is None:
            actual_api_name = getattr(api_func, '__name__', getattr(api_func, 'func', lambda: None).__name__ if hasattr(api_func, 'func') else None)
            if actual_api_name is None or actual_api_name == '<lambda>':
                # Try to get name from function's class or use the function's representation
                func_str = str(api_func)
                # Look for known tushare function patterns
                if 'trade_cal' in func_str:
                    actual_api_name = 'trade_cal'
                elif 'daily' in func_str:
                    actual_api_name = 'daily'
                elif 'stock_basic' in func_str:
                    actual_api_name = 'stock_basic'
                elif 'income' in func_str:
                    actual_api_name = 'income'
                elif 'balancesheet' in func_str:
                    actual_api_name = 'balancesheet'
                elif 'cashflow' in func_str:
                    actual_api_name = 'cashflow'
                elif 'fina_indicator' in func_str:
                    actual_api_name = 'fina_indicator'
                elif 'dividend' in func_str:
                    actual_api_name = 'dividend'
                elif 'forecast' in func_str:
                    actual_api_name = 'forecast'
                elif 'express' in func_str:
                    actual_api_name = 'express'
                elif 'moneyflow' in func_str:
                    actual_api_name = 'moneyflow'
                elif 'cyq' in func_str:
                    actual_api_name = 'cyq_chips' if 'cyq_chips' in func_str or 'chips' in func_str else 'cyq_perf'
                elif 'stk_factor' in func_str:
                    actual_api_name = 'stk_factor'
                elif 'top10' in func_str:
                    actual_api_name = 'top10_holders' if 'holders' in func_str else 'top10_floatholders'
                else:
                    actual_api_name = 'unknown_api'

        for attempt in range(max_retries + 1):
            try:
                # Implement rate limiting
                self._rate_limit(actual_api_name)

                # Log the API call
                self.logger.info(f"Calling {actual_api_name} API attempt {attempt + 1}")

                # Make the API call
                result = api_func(*args, **kwargs)

                self.logger.info(f"Successfully called {actual_api_name}, got {len(result) if hasattr(result, '__len__') else 'unknown'} records")
                return result

            except Exception as e:
                self.logger.warning(f"Attempt {attempt + 1} failed for {actual_api_name}: {str(e)}")

                # Check if the error is related to token authentication
                error_msg = str(e).lower()
                if "token" in error_msg or "auth" in error_msg:
                    # Try switching to the other token
                    if self.primary_token and self.secondary_token:
                        self.switch_token()
                        self.logger.info(f"Switched token due to authentication error. Retrying {actual_api_name}...")
                        # Retry immediately with the new token
                        try:
                            result = api_func(*args, **kwargs)
                            self.logger.info(f"Successfully called {actual_api_name} after token switch, got {len(result) if hasattr(result, '__len__') else 'unknown'} records")
                            return result
                        except Exception as retry_e:
                            self.logger.warning(f"Retry with switched token failed for {actual_api_name}: {str(retry_e)}")

                if attempt == max_retries:
                    self.logger.error(f"All {max_retries + 1} attempts failed for {actual_api_name}")
                    ErrorHandler.handle_api_error(e, f"API call {actual_api_name}")

                # Exponential backoff: wait longer between each attempt
                wait_time = 2 ** attempt
                self.logger.info(f"Waiting {wait_time}s before next attempt...")
                time.sleep(wait_time)

    def download_with_pagination(self, api_func, limit_per_call=2000, **base_kwargs):
        """
        分页下载数据的通用函数，改进错误处理
        """
        all_data = []
        offset = 0
        max_retries = 3  # 仅对网络错误重试
        retry_count = 0

        while True:
            # 添加分页参数
            kwargs = base_kwargs.copy()
            kwargs['offset'] = offset
            kwargs['limit'] = limit_per_call

            try:
                # 实现API调用前的频率限制
                api_name = getattr(api_func, '__name__', 'unknown_api')
                self._rate_limit(api_name)
                data = api_func(**kwargs)
                retry_count = 0  # 成功则重置重试计数
            except Exception as e:
                error_msg = str(e).lower()
                self.logger.error(f"分页下载失败, offset={offset}: {e}")

                # 检查错误类型并决定是否重试
                if "指定数据不存在" in str(e) or "data does not exist" in error_msg:
                    # 数据不存在错误，不应该重试，直接结束
                    self.logger.info(f"数据不存在，结束下载: {e}")
                    break
                elif any(keyword in error_msg for keyword in ["timeout", "connection", "tushare.xyz", "network"]):
                    # 网络相关错误，可以重试
                    retry_count += 1
                    if retry_count <= max_retries:
                        wait_time = min(10 * retry_count, 60)  # 指数退避，最大60秒
                        self.logger.warning(f"网络错误，等待 {wait_time:.2f} 秒后重试 (第{retry_count}/{max_retries}次)")
                        time.sleep(wait_time)
                        continue
                    else:
                        self.logger.error(f"网络错误超过最大重试次数，跳过当前分页")
                        break
                else:
                    # 其他错误，不重试
                    self.logger.error(f"非网络错误，停止下载: {e}")
                    break

            if data is None or len(data) == 0:
                break

            # 将DataFrame添加到列表中
            all_data.append(data)

            # 如果返回数据少于限制数量，说明已到最后一页
            if len(data) < limit_per_call:
                break

            # 更新offset
            offset += limit_per_call

            # 在每次API调用之间添加延迟
            time.sleep(random.uniform(0.5, 1.0))

        # 合并所有数据
        if all_data:
            return pd.concat(all_data, ignore_index=True)
        else:
            return pd.DataFrame()

    def download_stk_factor_paginated(self, trade_date: str = None, ts_code: str = None):
        """
        分页下载stk_factor数据
        """
        try:
            # 使用分页下载方法
            kwargs = {}
            if trade_date:
                kwargs['trade_date'] = trade_date
            if ts_code:
                kwargs['ts_code'] = ts_code

            # 使用最大支持的limit值
            return self.download_with_pagination(
                self.pro.stk_factor,
                limit_per_call=10000,  # stk_factor单次最大10000条
                **kwargs
            )
        except Exception as e:
            self.logger.error(f"分页下载stk_factor失败: {e}")
            # 回退到普通下载方法
            return self.pro.stk_factor(trade_date=trade_date, ts_code=ts_code)

    def download_cyq_perf_paginated(self, trade_date: str = None, ts_code: str = None):
        """
        分页下载cyq_perf数据
        """
        try:
            # 使用分页下载方法
            kwargs = {}
            if trade_date:
                kwargs['trade_date'] = trade_date
            if ts_code:
                kwargs['ts_code'] = ts_code

            # 使用最大支持的limit值
            return self.download_with_pagination(
                self.pro.cyq_perf,
                limit_per_call=5000,  # cyq_perf单次最大5000条
                **kwargs
            )
        except Exception as e:
            self.logger.error(f"分页下载cyq_perf失败: {e}")
            # 回退到普通下载方法
            return self.pro.cyq_perf(trade_date=trade_date, ts_code=ts_code)

    def download_cyq_chips_paginated(self, trade_date: str = None, ts_code: str = None):
        """
        分页下载cyq_chips数据，改进错误处理
        """
        try:
            kwargs = {}
            if trade_date:
                kwargs['trade_date'] = trade_date
            if ts_code:
                kwargs['ts_code'] = ts_code
            else:
                # 如果没有提供ts_code但提供了trade_date，则需要获取股票列表
                if trade_date and not ts_code:
                    # 需要先获取股票列表
                    from stock_list_manager import StockListManager
                    stock_manager = StockListManager()
                    stock_list = stock_manager.get_stock_basic()
                    if not stock_list.empty:
                        # 返回所有股票的数据，通过循环调用
                        all_data = []
                        for _, stock in stock_list.iterrows():
                            stock_code = stock['ts_code']
                            try:
                                # 对每个股票单独进行分页下载，避免API限制
                                stock_data = self.download_with_pagination(
                                    self.pro.cyq_chips,
                                    limit_per_call=1000,  # 减小每次调用的数据量，降低超时风险
                                    ts_code=stock_code,
                                    trade_date=trade_date
                                )
                                if not stock_data.empty:
                                    all_data.append(stock_data)
                                # 在循环中添加延迟，避免超出API限制
                                time.sleep(random.uniform(0.5, 1.0))
                            except Exception as e:
                                self.logger.warning(f"分页下载股票 {stock_code} 的cyq_chips失败: {e}")
                                continue
                        if all_data:
                            return pd.concat(all_data, ignore_index=True)
                        else:
                            return pd.DataFrame()

            # 减小每次调用的数据量，降低超时风险
            return self.download_with_pagination(
                self.pro.cyq_chips,
                limit_per_call=1000,  # 从2000减少到1000
                **kwargs
            )
        except Exception as e:
            self.logger.error(f"分页下载cyq_chips失败: {e}")

            # 对于cyq_chips特有的错误处理
            if "指定数据不存在" in str(e):
                self.logger.info("cyq_chips: 指定日期无数据，返回空DataFrame")
                return pd.DataFrame()
            else:
                # 其他错误重新抛出
                raise e

    def _advanced_rate_limit(self, api_name: str) -> None:
        """
        更精细的速率限制管理
        包括随机抖动避免API检测和令牌切换，针对不同数据类型实施差异化限制
        """
        current_time = time.perf_counter()

        # 特殊处理特色数据接口
        special_apis = ['cyq_chips', 'cyq_perf', 'stk_factor', 'moneyflow', 'daily_basic']
        if api_name in special_apis:
            # 对于特色数据接口，使用更严格的限制
            if 'cyq' in api_name:
                # cyq_chips接口有特殊限制，可能需要更长的间隔
                calls_per_minute = 200  # 特色数据接口的限制
            else:
                calls_per_minute = min(200, self.api_limits.get(api_name, {'calls_per_minute': 200})['calls_per_minute'])
        else:
            # 标准接口使用账户默认限制
            calls_per_minute = self.api_limits.get(api_name, {'calls_per_minute': 500})['calls_per_minute']

        # 添加随机性以避免被识别为自动化脚本
        min_interval = (60.0 / calls_per_minute) * random.uniform(0.8, 1.2)

        # 检查是否最近调用过此API
        if api_name in self.last_call_times:
            elapsed = current_time - self.last_call_times[api_name]
            if elapsed < min_interval:
                sleep_time = min_interval - elapsed
                self.logger.debug(f"Rate limiting {api_name}, sleeping for {sleep_time:.2f}s")
                # 使用更长的随机延迟避免API检测
                actual_sleep = max(sleep_time, random.uniform(0.5, 1.5))
                time.sleep(actual_sleep)
            else:
                # 为防止突发请求，再添加一个较短的随机延迟
                time.sleep(random.uniform(0.1, 0.3))
        else:
            # 对于首次调用，添加一个初始延迟
            time.sleep(random.uniform(0.1, 0.5))

        self.last_call_times[api_name] = current_time

    def smart_token_switch(self, api_name: str):
        """
        基于使用频率和剩余配额智能切换令牌
        """
        # 在每次API调用时检查令牌使用情况
        if self._should_switch_token(api_name):
            self.switch_token()

    def _should_switch_token(self, api_name: str) -> bool:
        """
        根据API限制和调用频率决定是否切换令牌
        """
        # 实现智能令牌切换逻辑
        current_api_limits = get_api_limits_for_score(self.current_points)
        if api_name in current_api_limits:
            # 监控当前令牌的使用情况
            pass
        # 逻辑：如果当前令牌的配额接近用完，则切换到另一个
        return False

    def download_daily_moneyflow_range(self, start_date: str, end_date: str, ts_code: str = None):
        """
        按日期范围批量下载资金流数据
        """
        try:
            # 使用日期范围参数批量下载
            return self.pro.moneyflow(start_date=start_date, end_date=end_date, ts_code=ts_code)
        except Exception as e:
            self.logger.error(f"批量下载资金流数据失败: {e}")
            # 回退到按日下载
            return pd.DataFrame()

    def download_stk_factor_range(self, start_date: str, end_date: str, ts_code: str = None):
        """
        按日期范围批量下载stk_factor数据
        """
        try:
            # 使用日期范围参数批量下载
            return self.pro.stk_factor(start_date=start_date, end_date=end_date, ts_code=ts_code)
        except Exception as e:
            self.logger.error(f"批量下载stk_factor数据失败: {e}")
            # 回退到按日下载
            return pd.DataFrame()

    def download_cyq_perf_range(self, start_date: str, end_date: str, ts_code: str = None):
        """
        按日期范围批量下载cyq_perf数据
        """
        try:
            # 使用日期范围参数批量下载
            return self.pro.cyq_perf(start_date=start_date, end_date=end_date, ts_code=ts_code)
        except Exception as e:
            self.logger.error(f"批量下载cyq_perf数据失败: {e}")
            # 回退到按日下载
            return pd.DataFrame()

    def download_cyq_chips_range(self, start_date: str, end_date: str, ts_code: str = None):
        """
        按日期范围批量下载cyq_chips数据
        """
        try:
            # 使用日期范围参数批量下载
            return self.pro.cyq_chips(start_date=start_date, end_date=end_date, ts_code=ts_code)
        except Exception as e:
            self.logger.error(f"批量下载cyq_chips数据失败: {e}")
            # 回退到按日下载
            return pd.DataFrame()

    def download_daily_data_range(self, start_date: str = '20100101', end_date: str = '20231231') -> pd.DataFrame:
        """
        按日期范围下载所有股票的日线数据
        智能选择使用VIP接口或批量下载
        """
        try:
            from .config import TUSHARE_POINTS
        except ImportError:
            from config import TUSHARE_POINTS

        if TUSHARE_POINTS >= 5000:
            # 使用VIP接口，可以直接按日期范围下载所有股票数据
            try:
                return self.daily_data.download_daily_data_vip(start_date=start_date, end_date=end_date)
            except Exception as e:
                self.logger.warning(f"VIP接口下载失败，尝试股票列表循环下载: {e}")

        # 否则，获取股票列表并循环下载
        try:
            from .stock_list_manager import StockListManager
        except ImportError:
            from stock_list_manager import StockListManager

        stock_manager = StockListManager(self)
        stock_list = stock_manager.get_stock_basic()

        if not stock_list.empty:
            all_data = []
            for _, stock in stock_list.iterrows():
                try:
                    ts_code = stock['ts_code']
                    result = self.daily_data.download_daily_data(
                        ts_code=ts_code,
                        start_date=start_date,
                        end_date=end_date
                    )
                    if not result.empty:
                        all_data.append(result)
                    time.sleep(random.uniform(0.5, 1.0))  # 避免频率限制
                except Exception as e:
                    self.logger.warning(f"下载股票 {ts_code} 日线数据失败: {e}")
                    continue
            return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()

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

    def download_trade_cal(self, exchange: str = 'SSE', start_date: str = '20100101', end_date: str = '20251231') -> pd.DataFrame:
        """
        Download trade calendar data - direct access method
        Available to users with 2000+ points
        """
        try:
            from .config import TUSHARE_POINTS
        except ImportError:
            from config import TUSHARE_POINTS

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
            try:
                from .error_handler import ErrorHandler
                ErrorHandler.handle_api_error(e, "download_trade_cal")
            except ImportError:
                from error_handler import ErrorHandler
                ErrorHandler.handle_api_error(e, "download_trade_cal")
            raise

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

        # 对于moneyflow，尝试映射到正确的实现
        if name == 'download_moneyflow':
            return self.download_moneyflow_fallback

        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    def download_moneyflow_fallback(self, trade_date: str = None, ts_code: str = None) -> pd.DataFrame:
        """
        Fallback function for moneyflow download when the main method is not available
        """
        try:
            # 如果有trade_date参数，使用TuShare原生的moneyflow接口
            if trade_date:
                return self.pro.moneyflow(trade_date=trade_date)
            else:
                # 否则返回空DataFrame
                return pd.DataFrame()
        except Exception as e:
            self.logger.error(f"Error in fallback moneyflow download: {e}")
            return pd.DataFrame()

# Example usage
if __name__ == "__main__":
    downloader = TuShareDownloader()
    # Example calls - these would be used by the main system
    # basic_info = downloader.download_stock_basic()
    # daily_data = downloader.download_daily_data('000001.SZ')