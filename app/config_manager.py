"""
统一配置管理器
"""
import os
import logging
from dotenv import load_dotenv
from pathlib import Path
import json
from typing import Dict, Any
from score_config import SCORE_REQUIREMENTS, get_available_data_types, get_api_limits_for_score


class ConfigManager:
    def __init__(self, config_file: str = None):
        """初始化配置管理器"""
        load_dotenv('/home/quan/testdata/aspipe_v4/.env')

        # 基础配置
        self.tushare_token = self._get_token()
        self.primary_token = os.getenv('tushare_token')
        self.secondary_token = os.getenv('tushare2_token')

        # 积分相关配置
        self.tushare_points = self._get_points()
        self.proxy_url = self._get_proxy_url()

        # API限制配置
        self.api_limits = self._get_api_limits()

        # 数据目录配置
        self.data_dir = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / 'data'
        self.data_dir.mkdir(exist_ok=True)

        # 默认参数配置
        self.default_start_date = os.getenv('DEFAULT_START_DATE', '20100101')
        self.default_end_date = os.getenv('DEFAULT_END_DATE', '20231231')
        self.stock_limit = int(os.getenv('STOCK_LIMIT', '50'))

        # 下载配置
        self.download_config = self._get_download_config()

        # 评分配置
        self.score_requirements = self._get_score_requirements()

    def _get_token(self):
        """获取当前使用的token"""
        token = os.getenv('tushare_token')
        secondary_token = os.getenv('tushare2_token')

        if not token:
            if secondary_token:
                return secondary_token
            else:
                raise ValueError("No TUSHARE_TOKEN found in environment variables")

        return token

    def _get_points(self):
        """获取当前积分"""
        token = os.getenv('tushare_token')
        secondary_token = os.getenv('tushare2_token')

        if token and token == os.getenv('tushare_token'):
            return int(os.getenv('tushare_points', '120'))
        elif secondary_token:
            return int(os.getenv('tushare2_points', '2000'))

        return 120  # 默认积分

    def _get_proxy_url(self):
        """获取代理URL"""
        return os.getenv('PROXY_URL', '')

    def _get_api_limits(self):
        """获取API限制配置"""
        return get_api_limits_for_score(self.tushare_points)

    def _get_download_config(self):
        """获取下载配置"""
        # 默认下载配置，因为我们已经移除了download_config.py
        return {
            'daily': True,
            'daily_basic': True,
            'moneyflow': True,
            'stock_basic': True,
            'trade_cal': True,
            'new_share': True,
        }

    def _get_score_requirements(self):
        """获取评分要求"""
        # 从评分配置文件加载
        return SCORE_REQUIREMENTS

    def get_available_data_types(self):
        """获取当前积分下可用的数据类型"""
        return get_available_data_types(self.tushare_points)