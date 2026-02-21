"""
分页执行器 - 负责执行组合后的分页参数流
实现统一的分页执行逻辑，支持并发和顺序执行
"""

import logging
from typing import Dict, Any, List, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from .pagination import PaginationComposer, PaginationContext
from datetime import datetime

logger = logging.getLogger(__name__)


class PaginationExecutor:
    """
    分页执行器 - 专门负责执行分页请求，通过回调函数执行具体请求
    
    支持的执行模式：
    1. 单请求执行
    2. 顺序执行
    3. 并发执行
    
    执行逻辑：
    1. 使用 PaginationComposer 组合分页维度
    2. 根据参数数量和接口类型选择执行模式
    3. 执行请求并收集结果
    4. 处理错误和重试
    """

    # 非并发接口列表
    NON_CONCURRENT_INTERFACES = [
        'fina_audit', 'forecast_vip', 'express_vip', 'disclosure_date'
    ]
    
    # 低并发接口列表
    LOW_CONCURRENT_INTERFACES = [
        'top10_holders', 'top10_floatholders', 'pledge_detail', 'dividend'
    ]
    
    def __init__(self, max_workers: int = 4):
        """
        初始化分页执行器
        
        Args:
            max_workers: 最大并发数
        """
        self.max_workers = max_workers
    
    def execute(
        self,
        interface_config: Dict[str, Any],
        base_params: Dict[str, Any],
        context: PaginationContext,
        make_request: Callable[[Dict[str, Any], Dict[str, Any]], List[Dict[str, Any]]],
        coverage_manager: Optional[Any] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        save_callback: Optional[Callable[[str, List[Dict[str, Any]]], None]] = None
    ) -> List[Dict[str, Any]]:
        """
        执行分页请求（统一入口）
        
        Args:
            interface_config: 接口配置
            base_params: 基础请求参数
            context: 分页上下文
            make_request: 请求执行回调函数
            coverage_manager: 覆盖率管理器
            progress_callback: 进度回调函数
            save_callback: 保存回调函数，用于逐批次保存数据 (interface_name, data) -> None
            
        Returns:
            所有请求的数据结果
        """
        composer = PaginationComposer(context)
        params_list = list(composer.compose(base_params))
        
        # 检测 period_range 模式且 periods_per_batch=1，使用逐个保存模式
        periods_per_batch = None
        if params_list:
            periods_per_batch = params_list[0].get("_periods_per_batch")
        
        if periods_per_batch == 1 and save_callback:
            return self._execute_period_range_sequential(
                interface_config, params_list, make_request, 
                coverage_manager, progress_callback, save_callback
            )
        
        if len(params_list) <= 1:
            if params_list:
                # 新增：覆盖率检查
                if coverage_manager and self._should_skip_by_coverage(
                    interface_config, params_list[0], coverage_manager
                ):
                    logger.info(f"Skipping request due to coverage check")
                    return []
                return self._execute_single(interface_config, params_list[0], make_request)
            return []

        stop_on_empty = self._get_stop_on_empty_config(context.interface_config)
        if self._should_use_concurrency(interface_config):
            return self._execute_concurrent(
                interface_config, params_list, make_request, coverage_manager, progress_callback
            )
        else:
            return self._execute_sequential(
                interface_config, params_list, make_request, coverage_manager, progress_callback
            )
    
    def _execute_single(self, interface_config: Dict[str, Any], params: Dict[str, Any], make_request: Callable) -> List[Dict[str, Any]]:
        """
        执行单个请求
        
        Args:
            interface_config: 接口配置
            params: 请求参数
            make_request: 请求执行回调函数
            
        Returns:
            请求结果
        """
        return self._execute_single_request(interface_config, params, make_request)
    
    def _execute_sequential(self, interface_config: Dict[str, Any], params_list: List[Dict[str, Any]], 
                           make_request: Callable, coverage_manager: Optional[Any], 
                           progress_callback: Optional[Callable]) -> List[Dict[str, Any]]:
        """
        顺序执行多个请求
        
        Args:
            interface_config: 接口配置
            params_list: 请求参数列表
            make_request: 请求执行回调函数
            coverage_manager: 覆盖率管理器
            progress_callback: 进度回调函数
            
        Returns:
            所有请求的结果
        """
        all_data = []
        consecutive_empty = 0
        stop_on_empty = self._get_stop_on_empty_config(interface_config)
        
        for idx, params in enumerate(params_list):
            if progress_callback:
                progress_callback(idx + 1, len(params_list))
            
            if coverage_manager:
                if self._should_skip_by_coverage(interface_config, params, coverage_manager):
                    continue
            
            data = self._execute_single_request(interface_config, params, make_request)
            
            if data:
                all_data.extend(data)
                consecutive_empty = 0
            else:
                consecutive_empty += self._estimate_empty_days(params)
                if stop_on_empty > 0 and consecutive_empty >= stop_on_empty:
                    logger.info(f"Stopping after {consecutive_empty} consecutive empty days")
                    break
        
        return all_data
    
    def _execute_period_range_sequential(
        self,
        interface_config: Dict[str, Any],
        params_list: List[Dict[str, Any]],
        make_request: Callable,
        coverage_manager: Optional[Any],
        progress_callback: Optional[Callable],
        save_callback: Callable
    ) -> List[Dict[str, Any]]:
        """
        顺序执行 period_range 请求，每完成一个请求立即保存数据

        Args:
            interface_config: 接口配置
            params_list: 请求参数列表
            make_request: 请求执行回调函数
            coverage_manager: 覆盖率管理器
            progress_callback: 进度回调函数
            save_callback: 保存回调函数

        Returns:
            所有请求的结果
        """
        all_data = []
        interface_name = interface_config.get("name", "unknown")
        
        for idx, params in enumerate(params_list):
            if progress_callback:
                progress_callback(idx + 1, len(params_list))
            
            # 覆盖率检查
            if coverage_manager and self._should_skip_by_coverage(
                interface_config, params, coverage_manager
            ):
                period = params.get("period", "unknown")
                logger.info(f"[{interface_name}] Skipping period {period} - already covered")
                continue
            
            # 执行请求
            data = self._execute_single_request(interface_config, params, make_request)
            
            if data:
                all_data.extend(data)
                # 立即保存数据
                save_callback(interface_name, data)
                period = params.get("period", "unknown")
                logger.info(f"[{interface_name}] Saved {len(data)} records for period {period}")
        
        return all_data
    
    def _execute_concurrent(self, interface_config: Dict[str, Any], params_list: List[Dict[str, Any]], 
                           make_request: Callable, coverage_manager: Optional[Any], 
                           progress_callback: Optional[Callable]) -> List[Dict[str, Any]]:
        """
        并发执行多个请求
        
        Args:
            interface_config: 接口配置
            params_list: 请求参数列表
            make_request: 请求执行回调函数
            coverage_manager: 覆盖率管理器
            progress_callback: 进度回调函数
            
        Returns:
            所有请求的结果
        """
        all_data = []
        max_workers = self._get_max_workers(interface_config)
        
        filtered_params = [
            p for p in params_list
            if not (coverage_manager and
                    self._should_skip_by_coverage(interface_config, p, coverage_manager))
        ]
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_params = {
                executor.submit(self._execute_single_request, interface_config, p, make_request): p
                for p in filtered_params
            }
            
            completed = 0
            for future in as_completed(future_to_params):
                completed += 1
                if progress_callback:
                    progress_callback(completed, len(filtered_params))
                try:
                    data = future.result()
                    if data:
                        all_data.extend(data)
                except Exception as e:
                    logger.error(f"Task failed: {e}")
        
        return all_data
    
    def _execute_single_request(self, interface_config: Dict[str, Any], params: Dict[str, Any], 
                               make_request: Callable) -> List[Dict[str, Any]]:
        """
        执行单个请求，处理offset分页
        
        Args:
            interface_config: 接口配置
            params: 请求参数
            make_request: 请求执行回调函数
            
        Returns:
            请求结果
        """
        offset_config = params.get('_offset_pagination', {})
        
        if not offset_config.get('enabled'):
            clean_params = {k: v for k, v in params.items() if not k.startswith('_')}
            return make_request(interface_config, clean_params)
        
        # 执行offset分页
        all_data = []
        limit = offset_config['limit']
        offset = 0
        base_params = {k: v for k, v in params.items() if not k.startswith('_')}
        interface_name = interface_config.get('name', 'unknown')
        
        logger.info(f"[{interface_name}] Offset分页开始 - 配置限额: limit={limit}")
        page_num = 0
        
        while True:
            request_params = base_params.copy()
            request_params['limit'] = limit
            request_params['offset'] = offset
            
            data = make_request(interface_config, request_params)
            if not data:
                logger.info(f"[{interface_name}] 第{page_num + 1}页请求无数据 - offset={offset}, limit={limit}")
                break
            
            data_count = len(data)
            all_data.extend(data)
            page_num += 1
            
            logger.info(f"[{interface_name}] 第{page_num}页完成 - offset={offset}, 请求limit={limit}, 实际返回={data_count}条")
            
            if data_count < limit:
                logger.info(f"[{interface_name}] 分页完成 - 最后1页返回{data_count}条 < 限额{limit}，停止请求")
                break
            
            offset += limit
            if offset > limit * 10000:  # 安全限制
                logger.warning(f"[{interface_name}] Offset分页超过安全限制，停止请求")
                break
        
        logger.info(f"[{interface_name}] Offset分页结束 - 总页数={page_num}, 总记录数={len(all_data)}")
        return all_data
    
    def _should_use_concurrency(self, interface_config: Dict[str, Any]) -> bool:
        """
        判断是否应该使用并发执行
        
        Args:
            interface_config: 接口配置
            
        Returns:
            是否使用并发
        """
        pagination = interface_config.get('pagination', {})
        time_range = pagination.get('time_range', {})
        if time_range.get('reverse', False) and time_range.get('stop_on_empty', 0) > 0:
            return False
        return interface_config.get('name') not in self.NON_CONCURRENT_INTERFACES
    
    def _get_max_workers(self, interface_config: Dict[str, Any]) -> int:
        """
        获取最大并发数
        
        Args:
            interface_config: 接口配置
            
        Returns:
            最大并发数
        """
        name = interface_config.get('name', '')
        if name in self.NON_CONCURRENT_INTERFACES:
            return 1
        elif name in self.LOW_CONCURRENT_INTERFACES:
            return 2
        return self.max_workers

    
    def _get_stop_on_empty_config(self, interface_config: Dict[str, Any]) -> int:
        """
        获取连续无数据停止配置
        
        Args:
            interface_config: 接口配置
            
        Returns:
            连续无数据停止天数
        """
        time_range = interface_config.get('pagination', {}).get('time_range', {})
        if time_range.get('reverse', False):
            return time_range.get('stop_on_empty', 0)
        return 0
    
    def _should_skip_by_coverage(self, interface_config: Dict[str, Any], params: Dict[str, Any], 
                                coverage_manager: Any) -> bool:
        """
        根据覆盖率判断是否跳过请求
        
        Args:
            interface_config: 接口配置
            params: 请求参数
            coverage_manager: 覆盖率管理器
            
        Returns:
            是否跳过
        """
        api_name = interface_config.get('api_name', '')
        if '_time_window' in params:
            strategy = 'date_range'
        elif '_period_query' in params:  # 新增：检测 period_range 模式
            strategy = 'period'
        elif '_stock_info' in params:
            strategy = 'stock'
        elif '_type_value' in params:
            strategy = 'type'
        else:
            strategy = 'default'
        
        clean_params = {k: v for k, v in params.items() if not k.startswith('_')}
        try:
            # 如果接口定义了日期锚定参数且当前请求包含该参数，使用period策略
            param_defs = interface_config.get('parameters', {})
            date_anchor_param = None
            for p_name, p_def in param_defs.items():
                if p_def.get('is_date_anchor', False):
                    date_anchor_param = p_name
                    break
            if date_anchor_param:
                if date_anchor_param in clean_params:
                    return coverage_manager.should_skip(api_name, clean_params, strategy='period')
                return False
            return coverage_manager.should_skip(api_name, clean_params, strategy=strategy)
        except:
            return False
    
    def _estimate_empty_days(self, params: Dict[str, Any]) -> int:
        """
        估算空数据的天数
        
        Args:
            params: 请求参数
            
        Returns:
            估算的天数
        """
        if '_time_window' in params:
            try:
                start, end = params['_time_window']
                return (datetime.strptime(end, '%Y%m%d') - datetime.strptime(start, '%Y%m%d')).days + 1
            except:
                pass
        return 1
