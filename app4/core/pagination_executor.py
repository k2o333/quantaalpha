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
        "fina_audit",
        "forecast_vip",
        "express_vip",
        "disclosure_date",
    ]

    # 低并发接口列表
    LOW_CONCURRENT_INTERFACES = [
        "top10_holders",
        "top10_floatholders",
        "pledge_detail",
        "dividend",
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
        save_callback: Optional[Callable[[str, List[Dict[str, Any]]], None]] = None,
        on_data_ready: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
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
            on_data_ready: 数据准备好的回调函数（流式处理，避免内存累积）

        Returns:
            所有请求的数据结果（如果无回调）或 总记录数（如果有回调）
        """
        composer = PaginationComposer(context)
        params_list = list(composer.compose(base_params))

        # 检测 period_range 模式且 periods_per_batch=1，使用逐个保存模式
        periods_per_batch = None
        if params_list:
            periods_per_batch = params_list[0].get("_periods_per_batch")
            if periods_per_batch is not None:
                periods_per_batch = int(periods_per_batch)

        if periods_per_batch == 1 and save_callback:
            return self._execute_period_range_sequential(
                interface_config,
                params_list,
                make_request,
                coverage_manager,
                progress_callback,
                save_callback,
                on_data_ready,
            )

        if len(params_list) <= 1:
            if params_list:
                # 新增：覆盖率检查
                if coverage_manager and self._should_skip_by_coverage(
                    interface_config, params_list[0], coverage_manager
                ):
                    logger.info(f"Skipping request due to coverage check")
                    return []
                return self._execute_single(
                    interface_config, params_list[0], make_request, on_data_ready
                )
            return []

        stop_on_empty = self._get_stop_on_empty_config(context.interface_config)
        # 当有 save_callback 时，强制使用顺序执行以保证逐次保存
        if save_callback or not self._should_use_concurrency(interface_config):
            return self._execute_sequential(
                interface_config,
                params_list,
                make_request,
                coverage_manager,
                progress_callback,
                on_data_ready,
                save_callback,
            )
        else:
            return self._execute_concurrent(
                interface_config,
                params_list,
                make_request,
                coverage_manager,
                progress_callback,
                on_data_ready,
            )

    def _execute_single(
        self,
        interface_config: Dict[str, Any],
        params: Dict[str, Any],
        make_request: Callable,
        on_data_ready: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
    ) -> List[Dict[str, Any]]:
        """
        执行单个请求

        Args:
            interface_config: 接口配置
            params: 请求参数
            make_request: 请求执行回调函数
            on_data_ready: 数据准备好的回调函数（流式处理）

        Returns:
            请求结果（如果无回调）或 记录数（如果有回调）
        """
        return self._execute_single_request(interface_config, params, make_request, on_data_ready)

    def _execute_sequential(
        self,
        interface_config: Dict[str, Any],
        params_list: List[Dict[str, Any]],
        make_request: Callable,
        coverage_manager: Optional[Any],
        progress_callback: Optional[Callable],
        on_data_ready: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
        save_callback: Optional[Callable[[str, List[Dict[str, Any]]], None]] = None,
    ) -> List[Dict[str, Any]]:
        """
        顺序执行多个请求

        Args:
            interface_config: 接口配置
            params_list: 请求参数列表
            make_request: 请求执行回调函数
            coverage_manager: 覆盖率管理器
            progress_callback: 进度回调函数
            on_data_ready: 数据准备好的回调函数（流式处理）
            save_callback: 保存回调函数，每次请求完成后立即保存 (interface_name, data) -> None

        Returns:
            所有请求的结果（如果无回调）或 总记录数（如果有回调）
        """
        all_data = []
        total_count = 0
        consecutive_empty = 0
        stop_on_empty = self._get_stop_on_empty_config(interface_config)
        interface_name = interface_config.get("name", "unknown")

        for idx, params in enumerate(params_list):
            if progress_callback:
                progress_callback(idx + 1, len(params_list))

            if coverage_manager:
                if self._should_skip_by_coverage(
                    interface_config, params, coverage_manager
                ):
                    continue

            result = self._execute_single_request(interface_config, params, make_request, on_data_ready)

            if result:
                if on_data_ready:
                    # 流式模式：result 是计数
                    total_count += result
                    consecutive_empty = 0
                else:
                    # 兼容模式：result 是数据列表
                    all_data.extend(result)
                    # 原子化保存：每次请求的分页完成后立即保存
                    if save_callback:
                        save_callback(interface_name, result)
                        logger.info(
                            f"[{interface_name}] 已保存 {len(result)} 条记录 (第{idx+1}/{len(params_list)}批)"
                        )
                    consecutive_empty = 0
            else:
                consecutive_empty += self._estimate_empty_days(params)
                if stop_on_empty > 0 and consecutive_empty >= stop_on_empty:
                    logger.info(
                        f"Stopping after {consecutive_empty} consecutive empty days"
                    )
                    break

        if on_data_ready:
            return total_count
        return all_data

    def _execute_period_range_sequential(
        self,
        interface_config: Dict[str, Any],
        params_list: List[Dict[str, Any]],
        make_request: Callable,
        coverage_manager: Optional[Any],
        progress_callback: Optional[Callable],
        save_callback: Callable,
        on_data_ready: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
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
            on_data_ready: 数据准备好的回调函数（流式处理，避免内存累积）

        Returns:
            所有请求的结果（如果无回调）或 总记录数（如果有回调）
        """
        all_data = []
        total_count = 0
        interface_name = interface_config.get("name", "unknown")

        for idx, params in enumerate(params_list):
            if progress_callback:
                progress_callback(idx + 1, len(params_list))

            # 覆盖率检查
            if coverage_manager and self._should_skip_by_coverage(
                interface_config, params, coverage_manager
            ):
                period_field = params.get("_period_field", "period")
                period = params.get(period_field, "unknown")
                logger.info(
                    f"[{interface_name}] Skipping period {period} - already covered"
                )
                continue

            # 执行请求（传递 on_data_ready 以启用流式处理）
            result = self._execute_single_request(
                interface_config, params, make_request, on_data_ready
            )

            if result:
                if on_data_ready:
                    # 流式模式：result 是计数，数据已通过回调处理
                    total_count += result
                    period_field = params.get("_period_field", "period")
                    period = params.get(period_field, "unknown")
                    logger.info(
                        f"[{interface_name}] Streamed {result} records for period {period}"
                    )
                else:
                    # 兼容模式：result 是数据列表
                    all_data.extend(result)
                    # 立即保存数据
                    save_callback(interface_name, result)
                    period_field = params.get("_period_field", "period")
                    period = params.get(period_field, "unknown")
                    logger.info(
                        f"[{interface_name}] Saved {len(result)} records for period {period}"
                    )

        if on_data_ready:
            return total_count
        return all_data

    def _execute_concurrent(
        self,
        interface_config: Dict[str, Any],
        params_list: List[Dict[str, Any]],
        make_request: Callable,
        coverage_manager: Optional[Any],
        progress_callback: Optional[Callable],
        on_data_ready: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
    ) -> List[Dict[str, Any]]:
        """
        并发执行多个请求

        Args:
            interface_config: 接口配置
            params_list: 请求参数列表
            make_request: 请求执行回调函数
            coverage_manager: 覆盖率管理器
            progress_callback: 进度回调函数
            on_data_ready: 数据准备好的回调函数（流式处理）

        Returns:
            所有请求的结果（如果无回调）或 总记录数（如果有回调）
        """
        all_data = []
        total_count = 0
        max_workers = self._get_max_workers(interface_config)

        filtered_params = [
            p
            for p in params_list
            if not (
                coverage_manager
                and self._should_skip_by_coverage(interface_config, p, coverage_manager)
            )
        ]

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_params = {
                executor.submit(
                    self._execute_single_request, interface_config, p, make_request, on_data_ready
                ): p
                for p in filtered_params
            }

            completed = 0
            for future in as_completed(future_to_params):
                completed += 1
                if progress_callback:
                    progress_callback(completed, len(filtered_params))
                try:
                    result = future.result()
                    if result:
                        if on_data_ready:
                            # 流式模式：result 是计数
                            total_count += result
                        else:
                            # 兼容模式：result 是数据列表
                            all_data.extend(result)
                except Exception as e:
                    logger.error(f"Task failed: {e}")

        if on_data_ready:
            return total_count
        return all_data

    def _execute_single_request(
        self,
        interface_config: Dict[str, Any],
        params: Dict[str, Any],
        make_request: Callable,
        on_data_ready: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
    ) -> List[Dict[str, Any]]:
        """
        执行单个请求，处理offset分页

        Args:
            interface_config: 接口配置
            params: 请求参数
            make_request: 请求执行回调函数
            on_data_ready: 数据准备好的回调函数（用于流式处理，避免内存累积）
                           如果提供，数据通过回调传递，返回计数

        Returns:
            请求结果（如果无回调）或 记录数（如果有回调）
        """
        offset_config = params.get("_offset_pagination", {})

        if not offset_config.get("enabled"):
            clean_params = {k: v for k, v in params.items() if not k.startswith("_")}
            data = make_request(interface_config, clean_params)
            if on_data_ready and data:
                on_data_ready(data)
                return len(data)
            return data

        # 执行offset分页
        all_data = []
        total_count = 0
        limit = offset_config["limit"]
        offset = 0
        base_params = {k: v for k, v in params.items() if not k.startswith("_")}
        interface_name = interface_config.get("name", "unknown")

        logger.info(f"[{interface_name}] Offset分页开始 - 配置限额: limit={limit}")
        page_num = 0

        while True:
            request_params = base_params.copy()
            request_params["limit"] = limit
            request_params["offset"] = offset

            data = make_request(interface_config, request_params)
            if not data:
                logger.info(
                    f"[{interface_name}] 第{page_num + 1}页请求无数据 - offset={offset}, limit={limit}"
                )
                break

            data_count = len(data)
            
            if on_data_ready:
                # 流式处理：每页数据立即回调，不累积
                on_data_ready(data)
                total_count += data_count
            else:
                # 兼容旧逻辑：累积数据
                all_data.extend(data)
            
            page_num += 1

            logger.info(
                f"[{interface_name}] 第{page_num}页完成 - offset={offset}, 请求limit={limit}, 实际返回={data_count}条"
            )

            if data_count < limit:
                logger.info(
                    f"[{interface_name}] 分页完成 - 最后1页返回{data_count}条 < 限额{limit}，停止请求"
                )
                break

            offset += limit
            if offset > limit * 10000:  # 安全限制
                logger.warning(f"[{interface_name}] Offset分页超过安全限制，停止请求")
                break

        if on_data_ready:
            logger.info(
                f"[{interface_name}] Offset分页结束 - 总页数={page_num}, 总记录数={total_count}"
            )
            return total_count
        else:
            logger.info(
                f"[{interface_name}] Offset分页结束 - 总页数={page_num}, 总记录数={len(all_data)}"
            )
            return all_data

    def _should_use_concurrency(self, interface_config: Dict[str, Any]) -> bool:
        """
        判断是否应该使用并发执行

        Args:
            interface_config: 接口配置

        Returns:
            是否使用并发
        """
        pagination = interface_config.get("pagination", {})
        time_range = pagination.get("time_range", {})
        if time_range.get("reverse", False) and time_range.get("stop_on_empty", 0) > 0:
            return False
        return interface_config.get("name") not in self.NON_CONCURRENT_INTERFACES

    def _get_max_workers(self, interface_config: Dict[str, Any]) -> int:
        """
        获取最大并发数

        Args:
            interface_config: 接口配置

        Returns:
            最大并发数
        """
        name = interface_config.get("name", "")
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
        time_range = interface_config.get("pagination", {}).get("time_range", {})
        if time_range.get("reverse", False):
            return time_range.get("stop_on_empty", 0)
        return 0

    def _should_skip_by_coverage(
        self,
        interface_config: Dict[str, Any],
        params: Dict[str, Any],
        coverage_manager: Any,
    ) -> bool:
        """
        根据覆盖率判断是否跳过请求

        修正版：复用 CoverageManager 的统一策略，避免重复逻辑
        """
        api_name = interface_config.get("api_name", "")

        # 仅在明确 stock_loop 场景下短路，避免跨股票误判
        if "ts_code" in params:
            return False

        param_defs = interface_config.get("parameters", {})
        for param_name, param_def in param_defs.items():
            if param_def.get("is_date_anchor", False) and param_name in params:
                clean_params = {
                    k: v for k, v in params.items() if not k.startswith("_")
                }
                try:
                    return coverage_manager.should_skip(
                        api_name, clean_params, strategy="auto"
                    )
                except:
                    return False

        # 【修复】先构建 clean_params，再根据 _time_window 更新日期范围
        # 注意：需要保留 _period_field 和 _period_query 参数，用于 period_range 模式的覆盖率检测
        clean_params = {k: v for k, v in params.items() if not k.startswith("_")}

        # 保留内部参数（用于 period_range 模式）
        if "_period_field" in params:
            clean_params["_period_field"] = params["_period_field"]
        if "_period_query" in params:
            clean_params["_period_query"] = params["_period_query"]

        # 如果有 _time_window，使用窗口日期替换原始 start_date/end_date
        # 这样覆盖率检查只检查当前窗口范围，而不是整个请求范围
        if "_time_window" in params:
            start, end = params["_time_window"]
            clean_params["start_date"] = start
            clean_params["end_date"] = end

        # 确定检测策略
        if "_time_window" in params:
            strategy = "date_range"
        elif "_period_query" in params:
            strategy = "period"
        elif "_stock_info" in params:
            strategy = "stock"
        elif "_type_value" in params:
            strategy = "type"
        else:
            strategy = "default"

        try:
            return coverage_manager.should_skip(
                api_name, clean_params, strategy=strategy
            )
        except:
            return False

        param_defs = interface_config.get("parameters", {})
        for param_name, param_def in param_defs.items():
            if param_def.get("is_date_anchor", False) and param_name in params:
                clean_params = {
                    k: v for k, v in params.items() if not k.startswith("_")
                }
                try:
                    return coverage_manager.should_skip(
                        api_name, clean_params, strategy="auto"
                    )
                except:
                    return False

        # 【修复】先构建 clean_params，再根据 _time_window 更新日期范围
        # 注意：需要保留 _period_field 和 _period_query 参数，用于 period_range 模式的覆盖率检测
        clean_params = {k: v for k, v in params.items() if not k.startswith("_")}

        # 保留内部参数（用于 period_range 模式）
        if "_period_field" in params:
            clean_params["_period_field"] = params["_period_field"]
        if "_period_query" in params:
            clean_params["_period_query"] = params["_period_query"]

        # 如果有 _time_window，使用窗口日期替换原始 start_date/end_date
        # 这样覆盖率检查只检查当前窗口范围，而不是整个请求范围
        if "_time_window" in params:
            start, end = params["_time_window"]
            clean_params["start_date"] = start
            clean_params["end_date"] = end
            logger.debug(
                f"[Coverage] Window dates applied: {start} ~ {end} for {api_name}"
            )
        else:
            logger.debug(
                f"[Coverage] No _time_window in params, using original dates for {api_name}"
            )

        # 确定检测策略
        logger.debug(
            f"[Coverage] Checking strategy, params keys: {list(params.keys())}"
        )
        if "_time_window" in params:
            strategy = "date_range"
        elif "_period_query" in params:
            strategy = "period"
        elif "_stock_info" in params:
            strategy = "stock"
        elif "_type_value" in params:
            strategy = "type"
        else:
            strategy = "default"

        logger.debug(f"[Coverage] Strategy: {strategy}, params: {clean_params}")

        try:
            return coverage_manager.should_skip(
                api_name, clean_params, strategy=strategy
            )
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
        if "_time_window" in params:
            try:
                start, end = params["_time_window"]
                return (
                    datetime.strptime(end, "%Y%m%d")
                    - datetime.strptime(start, "%Y%m%d")
                ).days + 1
            except:
                pass
        return 1
