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
                        token = os.getenv('TUSHARE_TOKEN', '')
                        logger.debug("  TUSHARE_TOKEN: %s", token[:10] if token else 'NOT FOUND')

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
                    # 检查 enabled 字段，默认为 True
                    is_enabled = config.get('enabled', True)
                    if is_enabled:
                        configs[interface_name] = config
                        logger.debug(f"Loaded interface configuration: {interface_name}")
                    else:
                        logger.debug(f"Skipped disabled interface: {interface_name}")

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
            if 'primary_key' not in output_config or not output_config.get('primary_key', []):
                logger.error(f"Interface '{interface_name}' must have non-empty primary_key")
                return False

            # 验证 dedup_enabled 是否为布尔类型（如果存在）
            dedup_enabled = config.get('dedup_enabled')
            if dedup_enabled is not None and not isinstance(dedup_enabled, bool):
                logger.error(f"Interface '{interface_name}' dedup_enabled must be boolean, got {type(dedup_enabled).__name__}")
                return False

            # 验证日期锚定参数配置
            if not self._validate_date_anchor_parameters(config):
                return False

            # 验证 derived_fields 配置（新架构）或 columns 配置（旧架构）
            # 在新架构中，derived_fields 是可选的，不需要强制存在
            # 如果需要原始字段类型验证，则配置中可能仍包含其他验证逻辑
            # 新架构下 columns 已移除，使用 derived_fields 进行字段转换
            # 但不是所有接口都必须有 derived_fields
            pass  # 在新架构中不强制要求特定的字段配置

    def _validate_date_anchor_parameters(self, interface_config: Dict[str, Any]) -> bool:
        """
        验证日期锚定参数配置
        
        规则：
        1. 一个接口只能有一个日期锚定参数
        2. 日期锚定参数不能是 start_date 或 end_date
        """
        parameter_config = interface_config.get('parameters', {})
        date_anchor_params = []
        
        for param_name, param_def in parameter_config.items():
            if param_def.get('is_date_anchor', False):
                if param_name in ['start_date', 'end_date']:
                    logger.error(f"Invalid date anchor parameter '{param_name}' in interface {interface_config.get('name')}: start_date and end_date cannot be date anchors")
                    return False
                date_anchor_params.append(param_name)
        
        if len(date_anchor_params) > 1:
            logger.warning(f"Multiple date anchor parameters found in interface {interface_config.get('name')}: {date_anchor_params}. Only the first one will be used")
        
        return True