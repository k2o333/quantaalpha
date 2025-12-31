import os
import yaml
from typing import Dict, Any, List
import logging
from dotenv import load_dotenv

# 加载环境变量
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', '.env')
load_dotenv(env_path)

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

        # 处理环境变量替换
        logger.debug(f"Before env var replacement: {config.get('tushare', {}).get('token', 'NOT_FOUND')}")
        self._replace_env_vars(config)
        logger.debug(f"After env var replacement: {config.get('tushare', {}).get('token', 'NOT_FOUND')}")

        logger.info("Global configuration loaded successfully")
        return config

    def _replace_env_vars(self, obj, parent_key=''):
        """递归替换配置中的环境变量占位符"""
        logger.debug("_replace_env_vars called with obj type: %s, parent_key: %s", type(obj), parent_key)
        if isinstance(obj, dict):
            logger.debug("Processing dict with keys: %s", list(obj.keys()))
            for key, value in obj.items():
                current_path = "{}.{}".format(parent_key, key) if parent_key else key
                logger.debug("Processing key: %s, value type: %s, current_path: %s", key, type(value), current_path)
                logger.debug("Value: %s", value)
                logger.debug("isinstance(value, str): %s", isinstance(value, str))
                contains_dollar_brace = '${' in value if isinstance(value, str) else False
                contains_close_brace = '}' in value if isinstance(value, str) else False
                logger.debug("'${' in value: %s", contains_dollar_brace)
                logger.debug("'}' in value: %s", contains_close_brace)
                if isinstance(value, str) and contains_dollar_brace and contains_close_brace:
                    logger.debug("Found env var placeholder, will process it")
                    # 查找并替换环境变量
                    import re
                    pattern = r'\$\{([^}]+)\}'
                    def replacer(match):
                        env_var = match.group(1)
                        logger.debug("  Looking for env var: %s", env_var)

                        # 检查环境变量是否真的存在
                        logger.debug("  Checking if env vars are loaded:")
                        import os
                        logger.debug("  os.getenv('tushare_token'): %s", os.getenv('tushare_token', 'NOT FOUND')[:10] if os.getenv('tushare_token') else 'NOT FOUND')
                        logger.debug("  os.getenv('TUSHARE_TOKEN'): %s", os.getenv('TUSHARE_TOKEN', 'NOT FOUND')[:10] if os.getenv('TUSHARE_TOKEN') else 'NOT FOUND')

                        # 尝试直接查找环境变量
                        env_value = os.getenv(env_var)
                        logger.debug("  Direct lookup result: %s", env_value[:10] if env_value else env_value)
                        if env_value is not None:
                            return env_value

                        # 如果没找到，尝试常见的变体（如大小写变化）
                        # 例如：TUSHARE_TOKEN -> tushare_token
                        variants = [
                            env_var.lower(),
                            env_var.upper(),
                            '_'.join(word.lower() for word in re.findall(r'[A-Z][a-z]*', env_var))  # CamelCase to snake_case
                        ]

                        logger.debug("  variants: %s", variants)
                        for variant in variants:
                            env_value = os.getenv(variant)
                            logger.debug("  Trying variant %s: %s", variant, env_value[:10] if env_value else env_value)
                            if env_value is not None:
                                return env_value

                        # 如果找不到环境变量，保持原样
                        return match.group(0)

                    obj[key] = re.sub(pattern, replacer, value)
                    logger.debug("Replaced value: %s", obj[key])

                # 递归处理嵌套的字典和列表
                if isinstance(value, dict):
                    self._replace_env_vars(value, f"{parent_key}.{key}" if parent_key else key)
                elif isinstance(value, list):
                    self._replace_env_vars(value, f"{parent_key}.{key}" if parent_key else key)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                if isinstance(item, str) and '${' in item and '}' in item:
                    # 查找并替换环境变量
                    import re
                    pattern = r'\$\{([^}]+)\}'
                    def replacer(match):
                        env_var = match.group(1)
                        # 尝试直接查找环境变量
                        env_value = os.getenv(env_var)
                        if env_value is not None:
                            return env_value

                        # 如果没找到，尝试常见的变体（如大小写变化）
                        # 例如：TUSHARE_TOKEN -> tushare_token
                        variants = [
                            env_var.lower(),
                            env_var.upper(),
                            '_'.join(word.lower() for word in re.findall(r'[A-Z][a-z]*', env_var))  # CamelCase to snake_case
                        ]

                        for variant in variants:
                            env_value = os.getenv(variant)
                            if env_value is not None:
                                return env_value

                        # 如果找不到环境变量，保持原样
                        return match.group(0)

                    obj[i] = re.sub(pattern, replacer, item)
                elif isinstance(item, (dict, list)):
                    self._replace_env_vars(item, f"{parent_key}[{i}]")

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