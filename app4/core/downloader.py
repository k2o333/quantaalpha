import requests
import json
import time
import logging
from typing import Dict, Any, Optional, List
from .config_loader import ConfigLoader
from .cache_manager import CacheManager

logger = logging.getLogger(__name__)

class GenericDownloader:
    """通用下载器 - 原子化的执行引擎"""

    def __init__(self, config_loader: ConfigLoader, cache_manager: CacheManager):
        self.config_loader = config_loader
        self.cache_manager = cache_manager
        self.global_config = config_loader.get_global_config()
        self.session = requests.Session()
        # 设置默认请求头
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'aspipe_v4/4.0.0'
        })

    def download(self, interface_name: str, params: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """
        下载指定接口的数据

        Args:
            interface_name: 接口名称
            params: 请求参数

        Returns:
            下载的数据列表，如果出错则返回 None
        """
        try:
            # 1. 获取接口配置
            interface_config = self.config_loader.get_interface_config(interface_name)

            # 2. 检查缓存
            cache_key = self._generate_cache_key(interface_name, params)
            # 为了调试，跳过缓存
            cached_data = None
            if cached_data is not None:
                logger.info(f"Cache hit for {interface_name} with key: {cache_key}")
                return cached_data

            # 3. 校验参数
            validated_params = self._validate_parameters(interface_config, params)

            # 4. 执行分页/循环逻辑
            all_data = self._execute_pagination(interface_config, validated_params)

            # 5. 写入缓存
            if all_data:
                self.cache_manager.set(cache_key, all_data)

            return all_data

        except Exception as e:
            logger.error(f"Error downloading data from {interface_name}: {str(e)}")
            return None

    def _generate_cache_key(self, interface_name: str, params: Dict[str, Any]) -> str:
        """生成缓存键"""
        # 将参数排序并序列化为字符串
        sorted_params = sorted(params.items())
        param_str = "&".join([f"{k}={v}" for k, v in sorted_params])
        return f"{interface_name}_{param_str}"

    def _validate_parameters(self, interface_config: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        """校验并处理参数"""
        validated_params = {}
        parameter_config = interface_config.get('parameters', {})

        for param_name, param_value in params.items():
            if param_name in parameter_config:
                param_def = parameter_config[param_name]
                param_type = param_def.get('type')

                # 类型检查和转换
                if param_type == 'string':
                    validated_params[param_name] = str(param_value)
                elif param_type == 'int':
                    validated_params[param_name] = int(param_value)
                elif param_type == 'float':
                    validated_params[param_name] = float(param_value)
                else:
                    validated_params[param_name] = param_value
            else:
                # 如果参数未在配置中定义，仍然传递
                validated_params[param_name] = param_value

        # 添加默认值
        for param_name, param_def in parameter_config.items():
            if param_name not in validated_params and 'default' in param_def:
                validated_params[param_name] = param_def['default']

        return validated_params

    def _execute_pagination(self, interface_config: Dict[str, Any], params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """执行分页/循环逻辑"""
        pagination_config = interface_config.get('pagination', {})
        if not pagination_config.get('enabled', False):
            # 不分页，直接请求
            return self._make_request(interface_config, params)

        mode = pagination_config.get('mode', 'offset')
        all_data = []

        if mode == 'offset':
            all_data = self._execute_offset_pagination(interface_config, params, pagination_config)
        elif mode == 'date_range':
            all_data = self._execute_date_range_pagination(interface_config, params, pagination_config)
        elif mode == 'stock_loop':
            all_data = self._execute_stock_loop_pagination(interface_config, params)
        else:
            # 默认不分页
            all_data = self._make_request(interface_config, params)

        return all_data

    def _execute_offset_pagination(self, interface_config: Dict[str, Any], params: Dict[str, Any],
                                  pagination_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """执行 offset 分页"""
        all_data = []
        offset = 0
        limit_key = pagination_config.get('limit_key', 'limit')
        offset_key = pagination_config.get('offset_key', 'offset')
        default_limit = pagination_config.get('default_limit', 5000)

        while True:
            # 设置分页参数
            page_params = params.copy()
            page_params[limit_key] = default_limit
            page_params[offset_key] = offset

            # 发起请求
            page_data = self._make_request(interface_config, page_params)
            if not page_data:
                break

            all_data.extend(page_data)

            # 如果返回数据少于限制，说明已经到最后一页
            if len(page_data) < default_limit:
                break

            offset += default_limit
            # 添加延迟避免触发限流
            time.sleep(0.1)

        return all_data

    def _execute_date_range_pagination(self, interface_config: Dict[str, Any], params: Dict[str, Any],
                                      pagination_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """执行日期范围分页"""
        # 这里简化处理，实际应该根据 start_date 和 end_date 进行分割
        return self._make_request(interface_config, params)

    def _execute_stock_loop_pagination(self, interface_config: Dict[str, Any], params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """执行股票循环分页"""
        # 这里简化处理，实际应该获取股票列表然后循环
        return self._make_request(interface_config, params)

    def _make_request(self, interface_config: Dict[str, Any], params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """发起实际的 API 请求"""
        api_name = interface_config['api_name']
        request_config = interface_config.get('request', {})
        method = request_config.get('method', 'POST')
        timeout = request_config.get('timeout', 30)

        # 获取 API URL，优先使用代理 URL
        import os
        proxy_url = os.getenv('PROXY_URL', '')
        tushare_config = self.global_config.get('tushare', {})
        if proxy_url:
            api_url = proxy_url
        else:
            api_url = tushare_config.get('api_url', 'http://api.tushare.pro/api')

        # 在没有指定额外路径的情况下，使用 /api 作为默认路径
        if api_url.endswith('/api') or api_url.endswith('/dataapi'):
            pass  # URL 已经正确
        elif not request_config.get('extra_path', ''):
            # 如果没有额外路径，且 URL 不以 /api 或 /dataapi 结尾，则添加 /api
            if not api_url.endswith('/api') and not api_url.endswith('/dataapi'):
                if api_url.endswith('/'):
                    api_url += 'api'
                else:
                    api_url += '/api'

        # 添加额外路径（如果有）
        extra_path = request_config.get('extra_path', '')
        if extra_path:
            api_url += extra_path

        # 添加 token
        token_placeholder = tushare_config.get('token', '')
        if '${TUSHARE_TOKEN}' in token_placeholder:
            token = os.getenv('tushare_token', '')  # 注意这里使用小写
        else:
            token = token_placeholder

        # 调试信息
        logger.debug(f"Setting token: {token[:10] if token else 'None'}... (first 10 chars)")
        logger.debug(f"API URL: {api_url}")

        # 根据TuShare API格式构建请求体
        req_params = {
            'api_name': interface_config['api_name'],
            'token': token,
            'params': params,
            # 如果有字段需要，可以在这里添加fields参数
            'fields': ''  # 可以从配置中读取，这里暂时为空
        }

        # 创建新的params字典用于请求（保持api_name等参数）
        params = req_params

        try:
            if method.upper() == 'POST':
                response = self.session.post(api_url, json=params, timeout=timeout)
            else:
                response = self.session.get(api_url, params=params, timeout=timeout)

            response.raise_for_status()
            result = response.json()

            # 检查 API 返回是否成功
            if result.get('code') != 0:
                logger.error(f"API error: {result.get('msg', 'Unknown error')}")
                return []

            # 将TuShare的字段/数据分离格式转换为字典列表格式
            fields = result.get('data', {}).get('fields', [])
            items = result.get('data', {}).get('items', [])

            # 将二维数组转换为字典列表
            converted_data = []
            for item in items:
                row_dict = {}
                for i, field_name in enumerate(fields):
                    if i < len(item):
                        # 确保字段名是字符串类型
                        field_name = str(field_name) if field_name is not None else f"field_{i}"
                        row_value = item[i]
                        row_dict[field_name] = row_value
                converted_data.append(row_dict)

            return converted_data

        except requests.RequestException as e:
            logger.error(f"Request error: {str(e)}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}")
            return []