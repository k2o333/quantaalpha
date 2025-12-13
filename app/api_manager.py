"""
统一API管理器
"""
import tushare as ts
import time
import logging
import random
import sys
import os
from typing import Optional, Dict, Any
import pandas as pd

# Add paths for modules to find each other
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
sys.path.insert(0, os.path.join(current_dir, 'interfaces'))

from config_manager import ConfigManager
from error_handler import ErrorHandler, retry_on_failure
from interfaces.basic_data import BasicDataDownloader
from interfaces.daily_data import DailyDataDownloader
from interfaces.financial_data import FinancialDataDownloader
from interfaces.holders_data import HoldersDataDownloader
from interfaces.market_flow import MarketFlowDownloader
from interfaces.technical_factors import TechnicalFactorsDownloader
from interfaces.market_structure import MarketStructureDownloader
from interfaces.research_data import ResearchDataDownloader


class TuShareAPIManager:
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager
        self.primary_token = self.config.primary_token
        self.secondary_token = self.config.secondary_token
        self.current_token = self.config.tushare_token
        self.current_points = self.config.tushare_points
        self.current_proxy = self.config.proxy_url

        # 设置代理
        if self.current_proxy:
            import os
            os.environ["HTTP_PROXY"] = self.current_proxy
            os.environ["HTTPS_PROXY"] = self.current_proxy

        # 初始化API
        self.pro = ts.pro_api(self.current_token)

        # API限制和调用时间记录
        self.api_limits = self.config.api_limits
        self.last_call_times = {}

        self.logger = logging.getLogger(__name__)

        # 初始化各个接口模块
        self.basic_data = BasicDataDownloader(self.pro, self.config)
        self.daily_data = DailyDataDownloader(self.pro, self.config)
        self.financial_data = FinancialDataDownloader(self.pro, self.config)
        self.market_flow = MarketFlowDownloader(self.pro, self.config)
        self.holders_data = HoldersDataDownloader(self.pro, self.config)
        self.technical_factors = TechnicalFactorsDownloader(self.pro, self.config)
        self.market_structure = MarketStructureDownloader(self.pro, self.config)
        self.research_data = ResearchDataDownloader(self.pro, self.config)

        # 重试处理器
        self.retry_handler = ErrorHandler()

    def switch_token(self):
        """切换到备用token"""
        if self.primary_token and self.secondary_token:
            if self.current_token == self.primary_token:
                # 切换到备用token
                self.current_token = self.secondary_token
                self.current_points = int(__import__('os').environ.get('tushare2_points', '2000'))
                self.current_proxy = __import__('os').environ.get('PROXY_URL2', '')
                self.logger.info("Switching to secondary token")
            else:
                # 切换回主token
                self.current_token = self.primary_token
                self.current_points = int(__import__('os').environ.get('tushare_points', '120'))
                self.current_proxy = __import__('os').environ.get('PROXY_URL', '')
                self.logger.info("Switching to primary token")

            # 更新代理设置
            if self.current_proxy:
                import os
                os.environ["HTTP_PROXY"] = self.current_proxy
                os.environ["HTTPS_PROXY"] = self.current_proxy
            else:
                # 清除代理
                if "HTTP_PROXY" in __import__('os').environ:
                    del __import__('os').environ["HTTP_PROXY"]
                if "HTTPS_PROXY" in __import__('os').environ:
                    del __import__('os').environ["HTTPS_PROXY"]

            # 重新初始化API
            self.pro = ts.pro_api(self.current_token)
            # 更新API限制
            self.api_limits = self._get_updated_api_limits()

    def _get_updated_api_limits(self):
        """获取基于当前积分的API限制"""
        from score_config import get_api_limits_for_score
        return get_api_limits_for_score(self.current_points)

    def _rate_limit(self, api_name: str) -> None:
        """实现速率限制"""
        current_time = time.perf_counter()

        # 获取此API的速率限制
        api_config = self.api_limits.get(api_name, {'calls_per_minute': 200})
        calls_per_minute = api_config['calls_per_minute']

        # 添加随机性以避免被识别为自动化脚本
        min_interval = (60.0 / calls_per_minute) * random.uniform(0.8, 1.2)

        # 检查是否最近调用过此API
        if api_name in self.last_call_times:
            elapsed = current_time - self.last_call_times[api_name]
            if elapsed < min_interval:
                sleep_time = min_interval - elapsed
                self.logger.debug(f"Rate limiting {api_name}, sleeping for {sleep_time:.2f}s")
                time.sleep(min_interval)

        self.last_call_times[api_name] = current_time

    @retry_on_failure(max_retries=3, delay=1.0, backoff=2.0)
    def download_with_retry(self, api_func, *args, max_retries: int = 3, **kwargs):
        """
        下载数据带重试机制
        """
        api_name = api_func.__name__ if hasattr(api_func, '__name__') else 'unknown_api'

        for attempt in range(max_retries + 1):
            try:
                # 实现速率限制
                self._rate_limit(api_name)

                # 调用API
                result = api_func(*args, **kwargs)

                self.logger.info(f"Successfully called {api_name}, got {len(result) if hasattr(result, '__len__') else 'unknown'} records")
                return result

            except Exception as e:
                self.logger.warning(f"Attempt {attempt + 1} failed for {api_name}: {str(e)}")

                # 检查是否与token认证相关
                error_msg = str(e).lower()
                if "token" in error_msg or "auth" in error_msg:
                    # 尝试切换到另一个token
                    if self.primary_token and self.secondary_token:
                        self.switch_token()
                        self.logger.info(f"Switched token due to authentication error. Retrying {api_name}...")
                        # 用新token重试
                        try:
                            result = api_func(*args, **kwargs)
                            self.logger.info(f"Successfully called {api_name} after token switch, got {len(result) if hasattr(result, '__len__') else 'unknown'} records")
                            return result
                        except Exception as retry_e:
                            self.logger.warning(f"Retry with switched token failed for {api_name}: {str(retry_e)}")

                if attempt == max_retries:
                    self.logger.error(f"All {max_retries + 1} attempts failed for {api_name}")
                    self.retry_handler.handle_api_error(e, f"API call {api_name}")

                # 指数退避：每次重试等待更长时间
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
        分页下载cyq_chips数据
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
                self.pro.cyq_chips,
                limit_per_call=2000,  # cyq_chips单次最大2000条
                **kwargs
            )
        except Exception as e:
            self.logger.error(f"分页下载cyq_chips失败: {e}")
            # 回退到普通下载方法
            return self.pro.cyq_chips(trade_date=trade_date, ts_code=ts_code)

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