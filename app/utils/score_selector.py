"""
积分基础数据选择器
"""
import logging
from typing import Dict, List


class ScoreBasedSelector:
    def __init__(self, config_manager):
        self.config = config_manager
        self.logger = logging.getLogger(__name__)

    def get_available_data_types(self) -> Dict[str, List[str]]:
        """获取当前积分下可用的数据类型"""
        return self.config.get_available_data_types()