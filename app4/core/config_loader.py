import os
import yaml
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class ConfigLoader:
    """配置加载器 - 启动时加载 config/interfaces/*.yaml"""

    def __init__(self, config_dir: str = "../config"):
        self.config_dir = config_dir
        self.global_config = self._load_global_config()
        self.interface_configs = self._load_interface_configs()

    def _load_global_config(self) -> Dict[str, Any]:
        """加载全局配置"""
        global_config_path = os.path.join(self.config_dir, "settings.yaml")
        with open(global_config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        logger.info("Global configuration loaded successfully")
        return config

    def _load_interface_configs(self) -> Dict[str, Dict[str, Any]]:
        """加载接口配置"""
        interfaces_dir = os.path.join(self.config_dir, "interfaces")
        configs = {}

        for filename in os.listdir(interfaces_dir):
            if filename.endswith('.yaml') or filename.endswith('.yml'):
                interface_name = filename.replace('.yaml', '').replace('.yml', '')
                interface_path = os.path.join(interfaces_dir, filename)

                with open(interface_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    configs[interface_name] = config
                    logger.debug(f"Loaded interface configuration: {interface_name}")

        logger.info(f"Loaded {len(configs)} interface configurations")
        return configs

    def get_interface_config(self, interface_name: str) -> Dict[str, Any]:
        """获取特定接口的配置"""
        if interface_name not in self.interface_configs:
            raise ValueError(f"Interface '{interface_name}' not found in configuration")
        return self.interface_configs[interface_name]

    def get_global_config(self) -> Dict[str, Any]:
        """获取全局配置"""
        return self.global_config

    def get_available_interfaces(self) -> List[str]:
        """获取所有可用接口列表"""
        return list(self.interface_configs.keys())

    def validate_config(self) -> bool:
        """验证配置的完整性"""
        # 检查必填字段
        required_fields = ['name', 'api_name', 'description', 'output']
        for interface_name, config in self.interface_configs.items():
            for field in required_fields:
                if field not in config:
                    logger.error(f"Missing required field '{field}' in interface '{interface_name}'")
                    return False

            # 验证 output 配置
            output_config = config.get('output', {})
            if 'primary_key' not in output_config or not output_config['primary_key']:
                logger.error(f"Interface '{interface_name}' must have non-empty primary_key")
                return False

            # 验证 columns 配置
            if 'columns' not in output_config:
                logger.error(f"Interface '{interface_name}' must have columns configuration")
                return False

        logger.info("Configuration validation passed")
        return True