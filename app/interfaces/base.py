"""
接口模块基类
提供通用的功能和方法
"""
import time
import logging
from typing import Optional
try:
    from ..config import TUSHARE_POINTS
except ImportError:
    from config import TUSHARE_POINTS
try:
    from ..error_handler import ErrorHandler, retry_on_failure
except ImportError:
    from error_handler import ErrorHandler, retry_on_failure


class BaseDownloader:
    def __init__(self, pro_api):
        self.pro = pro_api
        self.logger = logging.getLogger(self.__class__.__module__)

    def _rate_limit(self, api_name: str) -> None:
        """
        根据积分等级实现API调用限流
        """
        # 限流实现在主类中处理，这里留空或提供默认实现
        pass

    @retry_on_failure(max_retries=3, delay=1.0, backoff=2.0)
    def download_with_retry(self, api_func, *args, **kwargs):
        """
        带重试机制的下载函数
        """
        # 重试实现在主类中处理，这里提供接口
        pass

    def check_points_requirement(self, required_points: int) -> bool:
        """
        检查积分是否满足接口要求
        """
        return TUSHARE_POINTS >= required_points