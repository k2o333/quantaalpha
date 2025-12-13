"""
基础接口类
"""
import logging
from typing import Optional


class BaseDownloader:
    def __init__(self, pro_api, config_manager):
        self.pro = pro_api
        self.config = config_manager
        self.logger = logging.getLogger(self.__class__.__module__)

    def check_points_requirement(self, required_points: int) -> bool:
        """
        检查积分是否满足接口要求
        """
        return self.config.tushare_points >= required_points

    def safe_download(self, api_func, *args, **kwargs):
        """
        为API调用添加安全包装，处理空数据和异常情况
        """
        try:
            data = api_func(*args, **kwargs)
            if data is None or len(data) == 0:
                self.logger.warning(f"接口 {api_func.__name__} 返回空数据")
                return None
            return data
        except Exception as e:
            self.logger.error(f"接口 {api_func.__name__} 调用失败: {e}")
            return None