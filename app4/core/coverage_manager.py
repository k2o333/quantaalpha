"""覆盖率管理器 - 实现重复数据检测功能

根据优化方案v4，实现策略模式+轻量级索引的重复数据检测
"""

import logging
import threading
from typing import Dict, Any, Optional, Set, List
from collections import defaultdict, OrderedDict
import polars as pl
from datetime import datetime, timedelta
from .storage import StorageManager
from .config_loader import ConfigLoader
from .date_utils import (
    DateRange,
    format_date,
    detect_date_column,
    days_between,
    is_next_trade_day,
)

logger = logging.getLogger(__name__)


class CoverageManager:
    """覆盖率管理器 - 实现重复数据检测功能"""

    def __init__(
        self,
        storage_manager: StorageManager,
        config_loader: ConfigLoader,
        downloader=None,
        cache_size: int = 128,
    ):
        self.storage_manager = storage_manager
        self.config_loader = config_loader
        self.downloader = downloader  # 添加downloader引用用于API请求
        # 简单的内存缓存 {(interface, key): result}
        self._cache = {}
        self._coverage_cache = {}  # 用于缓存覆盖率检测结果
        self._cache_lock = threading.RLock()  # [新增] 线程锁

        # [新增] 已有日期缓存（LRU实现）
        self._existing_dates_cache = OrderedDict()
        self._cache_size = cache_size
        self._existing_dates_lock = threading.RLock()

    def get_coverage_status(
        self, interface_name: str, start_date: str, end_date: str
    ) -> Dict[str, Any]:
        """
        Thread-safe method to get coverage status with proper locking.
        Uses double-checked locking pattern to minimize lock contention.
        """
        cache_key = f"{interface_name}:{start_date}:{end_date}"

        # First check without lock for performance
        if cache_key in self._coverage_cache:
            return self._coverage_cache[cache_key]

        # Double-check with lock to avoid duplicate computation
        with self._cache_lock:
            # Re-check after acquiring lock
            if cache_key in self._coverage_cache:
                return self._coverage_cache[cache_key]

            # Calculate coverage
            coverage_status = self._calculate_coverage_status(
                interface_name, start_date, end_date
            )

            # Store in cache
            self._coverage_cache[cache_key] = coverage_status

            return coverage_status

    def _calculate_coverage_status(
        self, interface_name: str, start_date: str, end_date: str
    ) -> Dict[str, Any]:
        """
        Calculate coverage status by checking existing data.
        This is the actual computation method that was previously called directly.
        """
        # 获取接口配置
        interface_config = self.config_loader.get_interface_config(interface_name)
        detection_config = interface_config.get("duplicate_detection", {})

        # 获取检测列，默认为trade_date
        date_column = detection_config.get("date_column", "trade_date")
        threshold = detection_config.get("threshold", 0.95)

        try:
            # [优化] 先获取交易日历，用于计算预期的交易日数
            if self.downloader:
                trade_calendar = self.downloader.get_trade_calendar(
                    start_date, end_date
                )
            else:
                logger.warning("Downloader not available for trade calendar check")
                return {
                    "covered": False,
                    "coverage_rate": 0,
                    "total_expected": 0,
                    "total_found": 0,
                }

            if not trade_calendar:
                logger.info(
                    f"Trade calendar not available for {interface_name}, using simple coverage check"
                )
                return {
                    "covered": False,
                    "coverage_rate": 0,
                    "total_expected": 0,
                    "total_found": 0,
                }

            # 过滤出交易日
            expected_dates = {
                day["cal_date"] for day in trade_calendar if day.get("is_open", 0) == 1
            }

            if not expected_dates:
                logger.warning(
                    f"No expected trade days in range {start_date}-{end_date}"
                )
                return {
                    "covered": False,
                    "coverage_rate": 0,
                    "total_expected": 0,
                    "total_found": 0,
                }

            # 读取接口数据，只读取日期列
            df = self.storage_manager.read_interface_data(
                interface_name,
                start_date=start_date,
                end_date=end_date,
                columns=[date_column],
            )

            # 获取实际存在的日期
            # 处理日期字段，支持原始字符串格式和日期格式
            actual_dates = set()
            if not df.is_empty():
                date_series = df[date_column]
                for date_val in date_series:
                    if isinstance(date_val, str):
                        actual_dates.add(date_val)  # 原始字符串格式
                    elif hasattr(date_val, "strftime"):
                        # 日期类型，转换为字符串格式
                        actual_dates.add(date_val.strftime("%Y%m%d"))
                    else:
                        actual_dates.add(str(date_val))
            else:
                logger.debug(
                    f"No existing data found for {interface_name} in range {start_date}-{end_date}"
                )

            # 计算覆盖率
            intersection = actual_dates & expected_dates
            coverage_rate = (
                len(intersection) / len(expected_dates) if expected_dates else 0
            )
            covered = coverage_rate >= threshold

            logger.info(
                f"Coverage for {interface_name} ({start_date}-{end_date}): {coverage_rate:.2%} ({len(intersection)}/{len(expected_dates)})"
            )

            return {
                "covered": covered,
                "coverage_rate": coverage_rate,
                "total_expected": len(expected_dates),
                "total_found": len(intersection),
            }

        except Exception as e:
            logger.warning(f"Range coverage check failed for {interface_name}: {e}")
            return {
                "covered": False,
                "coverage_rate": 0,
                "total_expected": 0,
                "total_found": 0,
            }

    def mark_as_completed(
        self, interface_name: str, start_date: str, end_date: str, ts_code: str = None
    ) -> None:
        """
        Thread-safe method to mark coverage as completed.
        """
        with self._cache_lock:
            cache_key = f"{interface_name}:{start_date}:{end_date}"

            # Update cache with new completion status
            if cache_key in self._coverage_cache:
                # Update existing status
                status = self._coverage_cache[cache_key]
                if ts_code:
                    if "completed_ts_codes" not in status:
                        status["completed_ts_codes"] = set()
                    status["completed_ts_codes"].add(ts_code)
                else:
                    status["covered"] = True
            else:
                # Create new status
                status = {
                    "covered": True if not ts_code else False,
                    "completed_ts_codes": {ts_code} if ts_code else set(),
                    "coverage_rate": 1.0,
                    "total_expected": 0,
                    "total_found": 0,
                }
                self._coverage_cache[cache_key] = status

    def should_skip(
        self, interface_name: str, params: Dict[str, Any], strategy: str = "auto"
    ) -> bool:
        """
        根据策略判断是否应该跳过下载

        修正版：添加 date_anchor 策略，统一处理日期锚点检测

        Args:
            interface_name: 接口名称
            params: 请求参数
            strategy: 检测策略 ('auto', 'date_range', 'period', 'stock', 'date_anchor')

        Returns:
            True表示应该跳过，False表示应该继续下载
        """
        try:
            # 生成缓存键
            # 确保 params 是可哈希的，处理列表等类型
            sorted_params = []
            for k, v in sorted(params.items()):
                if isinstance(v, list):
                    v = tuple(v)
                sorted_params.append((k, v))
            cache_key = (interface_name, tuple(sorted_params))

            # [优化] 先检查缓存 (带锁)
            with self._cache_lock:
                if cache_key in self._coverage_cache:
                    return self._coverage_cache[cache_key]

            # 获取接口配置
            interface_config = self.config_loader.get_interface_config(interface_name)
            detection_config = interface_config.get("duplicate_detection", {})

            # 检查是否启用重复检测
            if not detection_config.get("enabled", True):
                return False

            # 自动确定策略 - 添加 date_anchor 识别
            if strategy == "auto":
                pagination_config = interface_config.get("pagination", {})
                pagination_mode = (
                    pagination_config.get("mode", "offset")
                    if pagination_config.get("enabled", False)
                    else "none"
                )

                # 检测是否是日期锚点接口
                param_defs = interface_config.get("parameters", {})
                is_date_anchor_interface = any(
                    p.get("is_date_anchor", False) for p in param_defs.values()
                )

                # 检测参数中是否包含日期锚点
                date_anchor_param = None
                for param_name, param_def in param_defs.items():
                    if param_def.get("is_date_anchor", False) and param_name in params:
                        date_anchor_param = param_name
                        break

                # 如果是日期锚点接口且参数包含锚点值，使用 date_anchor 策略
                # 但要排除 stock_loop 场景（避免跨股票误判）
                if (
                    is_date_anchor_interface
                    and date_anchor_param
                    and "ts_code" not in params
                ):
                    strategy = "date_anchor"
                elif pagination_mode in ["date_range", "reverse_date_range"]:
                    strategy = "date_range"
                elif pagination_mode == "period_range":
                    strategy = "period"
                elif pagination_mode == "stock_loop":
                    strategy = "stock"
                else:
                    return False  # 不支持的模式，不跳过

            # 根据策略执行检测
            result = False
            if strategy == "date_range":
                result = self._check_range_coverage(interface_name, params)
            elif strategy == "period":
                result = self._check_period_existence(interface_name, params)
            elif strategy == "stock":
                result = self._check_stock_existence(interface_name, params)
            elif strategy == "date_anchor":
                # 日期锚点检测策略
                result = self._check_date_anchor_existence(
                    interface_name, params, interface_config
                )

            # [优化] 更新缓存 (带锁)
            with self._cache_lock:
                self._coverage_cache[cache_key] = result

            return result
        except Exception as e:
            logger.warning(f"Coverage check failed for {interface_name}: {e}")
            return False  # Fail-safe，检测失败时继续下载

    def _check_range_coverage(
        self, interface_name: str, params: Dict[str, Any]
    ) -> bool:
        """
        检查日期范围覆盖率

        Args:
            interface_name: 接口名称
            params: 请求参数，应包含start_date和end_date

        Returns:
            True表示已覆盖（应跳过），False表示未覆盖（应下载）
        """
        start_date = params.get("start_date")
        end_date = params.get("end_date")

        if not start_date or not end_date:
            logger.debug(
                f"Missing date range parameters for {interface_name}, skipping coverage check"
            )
            return False

        # 获取接口配置
        interface_config = self.config_loader.get_interface_config(interface_name)
        detection_config = interface_config.get("duplicate_detection", {})

        # 获取检测列，默认为trade_date
        date_column = detection_config.get("date_column", "trade_date")
        threshold = detection_config.get("threshold", 0.95)

        try:
            # 读取接口数据，只读取日期列
            df = self.storage_manager.read_interface_data(
                interface_name,
                start_date=start_date,
                end_date=end_date,
                columns=[date_column],
            )

            if df.is_empty():
                logger.debug(
                    f"No existing data found for {interface_name} in range {start_date}-{end_date}"
                )
                return False

            # 获取实际存在的日期
            # 处理日期字段，支持原始字符串格式和日期格式
            date_series = df[date_column]
            actual_dates = set()
            for date_val in date_series:
                if isinstance(date_val, str):
                    actual_dates.add(date_val)  # 原始字符串格式
                elif hasattr(date_val, "strftime"):
                    # 日期类型，转换为字符串格式
                    actual_dates.add(date_val.strftime("%Y%m%d"))
                else:
                    actual_dates.add(str(date_val))

            # [优化] 直接使用 downloader 的 get_trade_calendar 方法
            if self.downloader:
                trade_calendar = self.downloader.get_trade_calendar(
                    start_date, end_date
                )
            else:
                logger.warning("Downloader not available for trade calendar check")
                return not df.is_empty()

            if not trade_calendar:
                logger.info(
                    f"Trade calendar not available for {interface_name}, using simple coverage check"
                )
                return not df.is_empty()

            # 过滤出交易日
            expected_dates = {
                day["cal_date"] for day in trade_calendar if day.get("is_open", 0) == 1
            }

            if not expected_dates:
                logger.warning(
                    f"No expected trade days in range {start_date}-{end_date}"
                )
                return False

            # 计算覆盖率
            coverage = len(actual_dates & expected_dates) / len(expected_dates)
            logger.info(
                f"Coverage for {interface_name} ({start_date}-{end_date}): {coverage:.2%} ({len(actual_dates & expected_dates)}/{len(expected_dates)})"
            )

            result = coverage >= threshold
            return result

        except Exception as e:
            logger.warning(f"Range coverage check failed for {interface_name}: {e}")
            return False

    def _check_period_existence(
        self, interface_name: str, params: Dict[str, Any]
    ) -> bool:
        """
        检查报告期是否存在（全市场维度）

        对于 period_range 模式，检测的是整个报告期是否有数据
        而不是单只股票是否有数据

        Args:
            interface_name: 接口名称
            params: 请求参数，应包含 period 或 start_date/end_date

        Returns:
            True 表示已存在（应跳过），False 表示不存在（应下载）
        """
        # 支持自定义 period 字段（如 end_date）
        period_field = params.get("_period_field", "period")
        period = params.get(period_field)

        # 新增：如果没有 period 参数，但有 start_date/end_date，则计算报告期列表
        if not period:
            start_date = params.get("start_date")
            end_date = params.get("end_date")
            if start_date and end_date:
                # 计算日期范围内的所有报告期
                periods = self._convert_date_range_to_periods(start_date, end_date)
                if not periods:
                    logger.info(
                        f"No completed periods in range {start_date}-{end_date}, skipping"
                    )
                    return True

                # 检查所有报告期是否都已存在
                logger.debug(
                    f"Checking {len(periods)} periods for {interface_name}: {periods}"
                )
                for p in periods:
                    if not self._check_single_period_existence(interface_name, p):
                        logger.debug(f"Period {p} does not exist, need to download")
                        return False  # 有一个不存在就需要下载

                logger.info(
                    f"All {len(periods)} periods exist for {interface_name}, skipping"
                )
                return True  # 全部存在才跳过
            else:
                logger.debug(
                    f"Missing period parameter for {interface_name}, skipping period check"
                )
                return False

        # 原有逻辑：检查单个 period
        return self._check_single_period_existence(interface_name, period)

    def _check_single_period_existence(
        self, interface_name: str, period: str, date_column: str = None
    ) -> bool:
        """
        检查单个报告期是否存在

        Args:
            interface_name: 接口名称
            period: 报告期，如 '20260331'
            date_column: 日期列名（可选），如果不提供则从配置中获取

        Returns:
            True 表示已存在（应跳过），False 表示不存在（应下载）
        """
        interface_config = self.config_loader.get_interface_config(interface_name)
        detection_config = interface_config.get("duplicate_detection", {})
        if date_column is None:
            date_column = detection_config.get("date_column", "end_date")

        try:
            cache_key = f"{interface_name}_periods_{date_column}"

            with self._cache_lock:
                if cache_key not in self._cache:
                    logger.debug(
                        f"Loading all periods for {interface_name} using column {date_column}"
                    )
                    df = self.storage_manager.read_interface_data(
                        interface_name, columns=[date_column]
                    )

                    if not df.is_empty():
                        periods_set = set()
                        for date_val in df[date_column]:
                            if isinstance(date_val, str):
                                periods_set.add(date_val)
                            elif hasattr(date_val, "strftime"):
                                periods_set.add(date_val.strftime("%Y%m%d"))
                            else:
                                periods_set.add(str(date_val))
                        self._cache[cache_key] = periods_set
                        logger.info(
                            f"Loaded {len(self._cache[cache_key])} existing periods for {interface_name}"
                        )
                    else:
                        self._cache[cache_key] = set()
                        logger.debug(f"No existing periods found for {interface_name}")

                result = period in self._cache[cache_key]

            logger.debug(
                f"Period {period} {'exists' if result else 'does not exist'} for {interface_name}"
            )
            return result

        except Exception as e:
            logger.warning(f"Period existence check failed for {interface_name}: {e}")
            return False

    def _convert_date_range_to_periods(
        self, start_date: str, end_date: str
    ) -> List[str]:
        """
        将日期区间转换为报告期列表

        规则：只有当报告期日期在用户日期区间内时，才包含该报告期

        Args:
            start_date: 用户传入的开始日期，如 '20260212'
            end_date: 用户传入的结束日期，如 '20260221'

        Returns:
            报告期列表，如 ['20260331']
        """
        periods = []
        start_year = int(start_date[:4])
        end_year = int(end_date[:4])

        quarter_ends = ["0331", "0630", "0930", "1231"]

        for year in range(start_year, end_year + 1):
            for qe in quarter_ends:
                period = f"{year}{qe}"
                if start_date <= period <= end_date:
                    periods.append(period)

        return periods

    def _check_stock_existence(
        self, interface_name: str, params: Dict[str, Any]
    ) -> bool:
        """
        检查股票是否存在

        Args:
            interface_name: 接口名称
            params: 请求参数，应包含ts_code

        Returns:
            True表示已存在（应跳过），False表示不存在（应下载）
        """
        target_stock = params.get("ts_code")
        if not target_stock:
            logger.debug(
                f"Missing ts_code parameter for {interface_name}, skipping stock check"
            )
            return False

        # 获取接口配置
        interface_config = self.config_loader.get_interface_config(interface_name)
        detection_config = interface_config.get("duplicate_detection", {})

        # 获取检测列，默认为ts_code
        key_column = detection_config.get("key_column", "ts_code")

        try:
            # Lazy load all stocks for this interface
            cache_key = f"{interface_name}_stocks"

            # 使用锁保护缓存读写
            with self._cache_lock:
                if cache_key not in self._cache:
                    logger.debug(f"Loading all stocks for {interface_name}")
                    df = self.storage_manager.read_interface_data(
                        interface_name, columns=[key_column]
                    )

                    if not df.is_empty():
                        self._cache[cache_key] = set(df[key_column].to_list())
                        logger.info(
                            f"Loaded {len(self._cache[cache_key])} existing stocks for {interface_name}"
                        )
                    else:
                        self._cache[cache_key] = set()
                        logger.debug(f"No existing stocks found for {interface_name}")

                result = target_stock in self._cache[cache_key]

            logger.debug(
                f"Stock {target_stock} {'exists' if result else 'does not exist'} for {interface_name}"
            )
            return result

        except Exception as e:
            logger.warning(f"Stock existence check failed for {interface_name}: {e}")
            return False

    def _check_date_anchor_existence(
        self,
        interface_name: str,
        params: Dict[str, Any],
        interface_config: Dict[str, Any],
    ) -> bool:
        """
        检查日期锚定值是否存在（仅在非 stock_loop 场景下）

        Args:
            interface_name: 接口名称
            params: 请求参数
            interface_config: 接口配置

        Returns:
            True 表示已存在（应跳过），False 表示不存在（应下载）
        """
        # 获取接口配置中的日期锚定参数
        param_defs = interface_config.get("parameters", {})
        date_anchor_param = None
        for param_name, param_def in param_defs.items():
            if param_def.get("is_date_anchor", False):
                date_anchor_param = param_name
                break

        if not date_anchor_param or date_anchor_param not in params:
            return False

        anchor_value = params[date_anchor_param]
        detection_config = interface_config.get("duplicate_detection", {})
        date_column = detection_config.get("date_column", date_anchor_param)

        # 根据锚点类型选择适当的检测逻辑
        return self._check_single_period_existence(
            interface_name, anchor_value, date_column
        )

    # ============================================================================
    # 缺口检测功能（增量更新增强）
    # ============================================================================

    def detect_gaps(
        self,
        interface_name: str,
        target_range: DateRange,
        trade_calendar: List[Dict[str, Any]],
        min_gap_days: int = 1,
        max_gaps: int = 50,
    ) -> List[DateRange]:
        """
        检测缺失的日期段

        Args:
            interface_name: 接口名称
            target_range: 目标日期范围
            trade_calendar: 交易日历列表（包含is_open字段的dict列表）
            min_gap_days: 最小缺口天数（小于此值的缺口忽略）
            max_gaps: 最大缺口数量（超过则返回整个范围）

        Returns:
            List[DateRange]: 缺失的日期段列表
        """
        logger.info(f"检测缺口: {interface_name} ({target_range})")

        # 1. 获取已有日期（带缓存）
        existing_dates = self._get_existing_dates_cached(interface_name)
        logger.info(f"已有数据: {len(existing_dates)} 天")

        # 2. 计算期望日期集合（只包含交易日）
        expected_dates = set()
        for day in trade_calendar:
            cal_date = day.get("cal_date")
            is_open = day.get("is_open", 0)
            if cal_date and is_open == 1:
                if target_range.start_date <= cal_date <= target_range.end_date:
                    expected_dates.add(cal_date)

        logger.info(f"期望交易日: {len(expected_dates)} 天")

        # 3. 快速路径检查
        if not existing_dates:
            logger.info("无已有数据，需要完整下载")
            return [target_range]

        if existing_dates >= expected_dates:
            logger.info("数据已完整覆盖，无需下载")
            return []

        # 4. 找出缺失日期
        missing_dates = expected_dates - existing_dates

        if not missing_dates:
            logger.info("无缺失数据")
            return []

        logger.info(f"缺失日期: {len(missing_dates)} 天")

        # 5. 合并连续缺失日期为段
        gaps = self._merge_continuous_dates(sorted(missing_dates), min_gap_days)
        logger.info(f"合并为 {len(gaps)} 个缺口段")

        # 6. 如果缺口太多，合并为大范围
        if len(gaps) > max_gaps:
            logger.warning(
                f"缺口数量({len(gaps)})超过限制({max_gaps})，合并为完整范围下载"
            )
            return [target_range]

        # 7. 输出缺口详情
        for i, gap in enumerate(gaps):
            logger.info(f"  [{i + 1}] {gap} ({gap.days_between()} 天)")

        return gaps

    def _get_existing_dates_cached(self, interface_name: str) -> Set[str]:
        """获取已有日期（带LRU缓存）"""
        with self._existing_dates_lock:
            if interface_name in self._existing_dates_cache:
                # 移动到末尾表示最近使用
                dates = self._existing_dates_cache.pop(interface_name)
                self._existing_dates_cache[interface_name] = dates
                logger.debug(f"{interface_name}: 从缓存读取已有日期（{len(dates)} 天）")
                return dates

        # 缓存未命中，从存储读取
        dates = self._get_existing_dates_from_storage(interface_name)

        # 写入缓存（带锁）
        with self._existing_dates_lock:
            # LRU淘汰
            if len(self._existing_dates_cache) >= self._cache_size:
                oldest_key = next(iter(self._existing_dates_cache))
                self._existing_dates_cache.pop(oldest_key)
                logger.debug(f"LRU淘汰: {oldest_key}")

            self._existing_dates_cache[interface_name] = dates

        logger.debug(f"{interface_name}: 从存储读取已有日期（{len(dates)} 天）")
        return dates

    def _get_existing_dates_from_storage(self, interface_name: str) -> Set[str]:
        """从存储中读取已有日期 - 使用统一的日期工具"""
        try:
            interface_config = self.config_loader.get_interface_config(interface_name)
            date_column = detect_date_column(interface_config)

            if not date_column:
                logger.warning(f"{interface_name}: 无法检测到日期列")
                return set()

            df = self.storage_manager.read_interface_data(
                interface_name, columns=[date_column]
            )

            if df.is_empty():
                return set()

            # 使用统一的日期格式化
            dates = set()
            for date_val in df[date_column]:
                formatted = format_date(date_val)
                if formatted:
                    dates.add(formatted)

            return dates

        except Exception as e:
            logger.warning(f"读取已有日期失败 {interface_name}: {e}")
            return set()

    def _detect_date_column(self, interface_config: Dict[str, Any]) -> Optional[str]:
        """智能检测日期列名称 - 使用统一工具"""
        return detect_date_column(interface_config)

    def _merge_continuous_dates(
        self, sorted_dates: List[str], min_gap_days: int
    ) -> List[DateRange]:
        """将连续日期合并为段"""
        if not sorted_dates:
            return []

        gaps = []
        gap_start = sorted_dates[0]
        gap_end = sorted_dates[0]

        for date in sorted_dates[1:]:
            if self._is_next_trade_day(gap_end, date):
                # 连续日期，扩展当前段
                gap_end = date
            else:
                # 不连续，保存当前段（如果满足最小天数）
                if self._days_between(gap_start, gap_end) >= min_gap_days:
                    gaps.append(DateRange(gap_start, gap_end))
                # 开始新段
                gap_start = date
                gap_end = date

        # 保存最后一个段
        if self._days_between(gap_start, gap_end) >= min_gap_days:
            gaps.append(DateRange(gap_start, gap_end))

        return gaps

    def _is_next_trade_day(self, current: str, next_date: str) -> bool:
        """检查是否是连续的交易日 - 使用统一工具"""
        return is_next_trade_day(current, next_date)

    def _days_between(self, start_date: str, end_date: str) -> int:
        """计算两个日期之间的天数 - 使用统一工具"""
        return days_between(start_date, end_date)

    def clear_dates_cache(self, interface_name: str = None):
        """清除日期缓存

        Args:
            interface_name: 指定接口名称则清除该接口缓存，None则清除所有
        """
        with self._existing_dates_lock:
            if interface_name:
                self._existing_dates_cache.pop(interface_name, None)
                logger.debug(f"清除缓存: {interface_name}")
            else:
                self._existing_dates_cache.clear()
                logger.debug("清除所有日期缓存")

    def is_time_range_mode(self, interface_name: str) -> bool:
        """检查接口是否支持时间范围模式（可用于缺口检测）"""
        try:
            interface_config = self.config_loader.get_interface_config(interface_name)
            pagination_config = interface_config.get("pagination", {})

            if not pagination_config.get("enabled", False):
                return False

            mode = pagination_config.get("mode", "")
            if mode not in ["date_range", "reverse_date_range"]:
                return False

            # 额外检查：必须有可检测的日期列
            date_column = self._detect_date_column(interface_config)
            if not date_column:
                logger.debug(
                    f"{interface_name}: 支持时间范围模式但无日期列，跳过缺口检测"
                )
                return False

            return True

        except Exception as e:
            logger.warning(f"检查接口模式失败 {interface_name}: {e}")
            return False

    # ============================================================================
    # 股票级别日期缺口检测（新增功能 - Stock Loop 模式智能增量下载）
    # ============================================================================

    def get_stock_existing_dates(
        self, interface_name: str, ts_code: str, date_column: str = "trade_date"
    ) -> Set[str]:
        """
        获取指定股票已存在的所有日期

        Args:
            interface_name: 接口名称
            ts_code: 股票代码
            date_column: 日期列名

        Returns:
            已存在的日期集合（YYYYMMDD格式）
        """
        cache_key = f"{interface_name}:{ts_code}:dates"

        with self._cache_lock:
            if cache_key in self._cache:
                return self._cache[cache_key]

        try:
            df = self.storage_manager.read_interface_data(
                interface_name, columns=[date_column, "ts_code"]
            )

            if df.is_empty():
                return set()

            import polars as pl

            filtered = df.filter(pl.col("ts_code") == ts_code)

            if filtered.is_empty():
                return set()

            dates = set()
            for date_val in filtered[date_column]:
                formatted = format_date(date_val)
                if formatted:
                    dates.add(formatted)

            with self._cache_lock:
                self._cache[cache_key] = dates

            logger.debug(f"[{interface_name}/{ts_code}] 已有 {len(dates)} 条数据")
            return dates

        except Exception as e:
            logger.warning(f"获取 {interface_name}/{ts_code} 的现有日期失败: {e}")
            return set()

    def detect_stock_gaps(
        self,
        interface_name: str,
        ts_code: str,
        start_date: str,
        end_date: str,
        interface_config: Dict[str, Any],
        user_provided_dates: bool = False,
        stock_info: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        检测指定股票的数据缺口（统一入口）

        根据接口配置自动选择检测方式：
        - 类型 A：交易日历检测
        - 类型 B：报告期检测
        - 类型 C：日期锚定遍历
        - 类型 D：无日期过滤

        Args:
            interface_name: 接口名称
            ts_code: 股票代码
            start_date: 起始日期
            end_date: 结束日期
            interface_config: 接口配置
            user_provided_dates: 用户是否显式提供日期
            stock_info: 股票信息（用于获取上市日等）

        Returns:
            下载任务参数列表
        """
        detection_config = interface_config.get("duplicate_detection", {})
        date_column = detection_config.get("date_column", "trade_date")

        # 判断接口类型
        gap_mode = self._determine_gap_mode(interface_config)
        logger.info(
            f"[{interface_name}/{ts_code}] 缺口检测模式: {gap_mode}, 用户提供日期: {user_provided_dates}"
        )

        if gap_mode == "trade_date":
            # 类型 A：交易日历检测
            return self._detect_trade_date_gaps(
                interface_name,
                ts_code,
                start_date,
                end_date,
                date_column,
                user_provided_dates=user_provided_dates,
                stock_info=stock_info,
            )
        elif gap_mode == "report_period":
            # 类型 B：报告期检测
            return self._detect_report_period_gaps(
                interface_name,
                ts_code,
                start_date,
                end_date,
                date_column,
                user_provided_dates=user_provided_dates,
                stock_info=stock_info,
            )
        elif gap_mode == "date_anchor":
            # 类型 C：日期锚定遍历
            return self._detect_date_anchor_gaps(
                interface_name,
                ts_code,
                start_date,
                end_date,
                date_column,
                interface_config,
                user_provided_dates=user_provided_dates,
                stock_info=stock_info,
            )
        elif gap_mode == "no_date_filter":
            # 类型 D：无日期过滤
            return self._detect_no_date_filter_gaps(
                interface_name, ts_code, date_column
            )
        else:
            # 未知类型，返回完整范围
            return [
                {"ts_code": ts_code, "start_date": start_date, "end_date": end_date}
            ]

    def _determine_gap_mode(self, interface_config: Dict[str, Any]) -> str:
        """
        判断接口的缺口检测模式

        判断顺序：
        1. 有 is_date_anchor=true → 类型 C
        2. 有 start_date + end_date → 类型 A 或 B（根据 date_column 区分）
        3. 无任何日期参数 → 类型 D
        4. 其他情况 → 根据 date_column 判断

        Returns:
            'trade_date'    - 类型 A：交易日历模式
            'report_period' - 类型 B：报告期模式
            'date_anchor'   - 类型 C：日期锚定模式
            'no_date_filter' - 类型 D：无日期过滤模式
        """
        parameters = interface_config.get("parameters", {})
        detection_config = interface_config.get("duplicate_detection", {})
        date_column = detection_config.get("date_column", "trade_date")

        # 1. 检查是否有日期锚定参数（类型 C）
        if any(p.get("is_date_anchor", False) for p in parameters.values()):
            return "date_anchor"

        # 2. 检查是否有 start_date 和 end_date 参数（类型 A 或 B）
        #    既然第1步已确认没有 is_date_anchor=true，这里必然是类型 A 或 B
        if "start_date" in parameters and "end_date" in parameters:
            return "trade_date" if date_column == "trade_date" else "report_period"

        # 3. 检查是否有任何日期参数
        has_date_param = any(
            p in parameters
            for p in ["start_date", "end_date", "trade_date", "period", "ann_date"]
        )

        if not has_date_param:
            return "no_date_filter"  # 类型 D

        # 4. 有日期参数但没有 start_date + end_date，根据 date_column 判断
        return "trade_date" if date_column == "trade_date" else "report_period"

    def _detect_trade_date_gaps(
        self,
        interface_name: str,
        ts_code: str,
        start_date: str,
        end_date: str,
        date_column: str,
        user_provided_dates: bool = False,
        stock_info: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        类型 A：交易日历缺口检测

        适用于：cyq_chips, moneyflow_dc, stk_factor_pro

        逻辑：
        - 无已有数据 + 无用户日期 -> 只传 ts_code，从上市日下载到最新
        - 无已有数据 + 有用户日期 -> 按用户指定范围下载
        - 有已有数据 + 无用户日期 -> 检测现有数据之后的缺失日期（增量下载）
        - 有已有数据 + 有用户日期 -> 检测用户范围内的缺失日期
        """
        logger.info(
            f"[{interface_name}/{ts_code}] 交易日历缺口检测 ({start_date} ~ {end_date}), 用户提供日期: {user_provided_dates}"
        )

        existing_dates = self.get_stock_existing_dates(
            interface_name, ts_code, date_column
        )

        # 无已有数据的情况
        if not existing_dates:
            if user_provided_dates:
                # 用户提供了日期，按指定范围下载
                logger.info(
                    f"[{ts_code}] 股票无数据，按用户指定范围下载: {start_date} ~ {end_date}"
                )
                return [
                    {"ts_code": ts_code, "start_date": start_date, "end_date": end_date}
                ]
            else:
                # 用户未提供日期，只传 ts_code 获取全历史（从上市日到最新）
                logger.info(
                    f"[{ts_code}] 股票无数据，使用单次全历史请求（只传 ts_code）"
                )
                return [{"ts_code": ts_code}]

        # 有已有数据，需要检测缺口
        if not self.downloader:
            return [
                {"ts_code": ts_code, "start_date": start_date, "end_date": end_date}
            ]

        trade_calendar = self.downloader.get_trade_calendar(start_date, end_date)
        if not trade_calendar:
            return [
                {"ts_code": ts_code, "start_date": start_date, "end_date": end_date}
            ]

        trade_days = [
            d["cal_date"]
            for d in trade_calendar
            if d.get("is_open", 0) == 1 and start_date <= d["cal_date"] <= end_date
        ]

        if stock_info:
            list_date = stock_info.get("list_date")
            if list_date:
                trade_days = [d for d in trade_days if d >= list_date]
                logger.debug(f"[{ts_code}] 按上市日 {list_date} 过滤交易日")

            delist_date = stock_info.get("delist_date")
            if delist_date:
                trade_days = [d for d in trade_days if d <= delist_date]
                logger.debug(f"[{ts_code}] 按退市日 {delist_date} 过滤交易日")

        if not user_provided_dates:
            # 用户未提供日期，检测从上市日到现在的所有缺失日期
            # 不再限制为只检测现有数据之后，而是检测全部缺失
            if existing_dates:
                logger.info(
                    f"[{ts_code}] 检测从上市日到现在的所有缺失日期 (已有数据: {min(existing_dates)} ~ {max(existing_dates)}, 共{len(existing_dates)}条)"
                )
            else:
                logger.info(f"[{ts_code}] 无已有数据，检测从上市日到现在的所有日期")

        missing_days = [d for d in trade_days if d not in existing_dates]

        if not missing_days:
            logger.info(f"[{ts_code}] 交易日数据已完整")
            return []

        logger.info(f"[{ts_code}] 缺失 {len(missing_days)} 个交易日")

        ranges = self._merge_dates_to_ranges(
            missing_days, existing_dates, trade_days, min_gap_size=3
        )

        return [
            {"ts_code": ts_code, "start_date": r[0], "end_date": r[1]} for r in ranges
        ]

    def _detect_report_period_gaps(
        self,
        interface_name: str,
        ts_code: str,
        start_date: str,
        end_date: str,
        date_column: str,
        user_provided_dates: bool = False,
        stock_info: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        类型 B：报告期缺口检测（优化版）

        适用于：income_vip, balancesheet_vip, cashflow_vip 等

        逻辑：
        - 无已有数据 + 无用户日期 -> 只传 ts_code，从上市日下载到最新
        - 无已有数据 + 有用户日期 -> 按用户指定报告期范围下载
        - 有已有数据 + 无用户日期 -> 检测现有数据之后的缺失报告期（增量下载）
        - 有已有数据 + 有用户日期 -> 检测用户范围内的缺失报告期

        优化策略：
        1. 如果缺失报告期数量 <= MAX_PRECISE_QUERIES，生成精确查询任务
        2. 如果缺失报告期数量 > MAX_PRECISE_QUERIES，使用范围查询最小覆盖区间
        """
        logger.info(
            f"[{interface_name}/{ts_code}] 报告期缺口检测 ({start_date} ~ {end_date}), 用户提供日期: {user_provided_dates}"
        )

        existing_dates = self.get_stock_existing_dates(
            interface_name, ts_code, date_column
        )
        expected_periods = self._generate_report_periods(start_date, end_date)

        # 无已有数据的情况
        if not existing_dates:
            if user_provided_dates:
                # 用户提供了日期，按指定范围下载
                logger.info(
                    f"[{ts_code}] 股票无数据，按用户指定范围下载: {start_date} ~ {end_date}"
                )
                return [
                    {"ts_code": ts_code, "start_date": start_date, "end_date": end_date}
                ]
            else:
                # 用户未提供日期，只传 ts_code 获取全历史
                logger.info(
                    f"[{ts_code}] 股票无数据，使用单次全历史请求（只传 ts_code）"
                )
                return [{"ts_code": ts_code}]

        # 用户未提供日期时，只检测现有数据之后的缺失报告期
        if not user_provided_dates and existing_dates:
            max_existing_date = max(existing_dates)
            expected_periods = [p for p in expected_periods if p > max_existing_date]
            logger.info(
                f"[{ts_code}] 用户未提供日期，只检测 {max_existing_date} 之后的缺失报告期"
            )

        missing_periods = [p for p in expected_periods if p not in existing_dates]

        if not missing_periods:
            logger.info(f"[{ts_code}] 报告期数据已完整")
            return []

        logger.info(
            f"[{ts_code}] 缺失 {len(missing_periods)} 个报告期: {missing_periods}"
        )

        quarter_start_map = {
            "0331": "0101",
            "0630": "0401",
            "0930": "0701",
            "1231": "1001",
        }

        period_ranges = self._merge_periods_to_ranges(missing_periods)

        logger.info(f"[{ts_code}] 报告期分组结果: {len(period_ranges)} 个范围")

        tasks = []
        for range_start, range_end in period_ranges:
            start_year = range_start[:4]
            start_q = quarter_start_map.get(range_start[4:], "0101")
            task_start = f"{start_year}{start_q}"

            tasks.append(
                {"ts_code": ts_code, "start_date": task_start, "end_date": range_end}
            )
            logger.info(f"  - 范围查询: {task_start} ~ {range_end}")

        return tasks

    def _detect_date_anchor_gaps(
        self,
        interface_name: str,
        ts_code: str,
        start_date: str,
        end_date: str,
        date_column: str,
        interface_config: Dict[str, Any],
        user_provided_dates: bool = False,
        stock_info: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        类型 C：日期锚定缺口检测

        适用于：disclosure_date, top10_holders, dividend 等

        逻辑：
        - 无已有数据 + 无用户日期 -> 只传 ts_code，获取全历史
        - 无已有数据 + 有用户日期 -> 生成日期区间内的所有锚点值，逐个查询
        - 有已有数据 + 无用户日期 -> 检测现有数据之后的缺失锚点
        - 有已有数据 + 有用户日期 -> 生成日期区间内的锚点值，跳过已有的，下载缺失的
        """
        logger.info(
            f"[{interface_name}/{ts_code}] 日期锚定缺口检测 ({start_date} ~ {end_date}), 用户提供日期: {user_provided_dates}"
        )

        parameters = interface_config.get("parameters", {})
        anchor_param = None
        for param_name, param_def in parameters.items():
            if param_def.get("is_date_anchor", False):
                anchor_param = param_name
                break

        if not anchor_param:
            logger.warning(f"[{interface_name}] 未找到日期锚定参数")
            return [{"ts_code": ts_code}]

        existing_dates = self.get_stock_existing_dates(
            interface_name, ts_code, date_column
        )

        # 无已有数据的情况
        if not existing_dates:
            if user_provided_dates:
                # 用户提供了日期，生成日期区间内的所有锚点值
                logger.info(f"[{ts_code}] 股票无数据，按用户指定日期生成锚点值")
                anchor_values = self._generate_anchor_values(
                    start_date, end_date, anchor_param
                )
                if not anchor_values:
                    return []
                return [
                    {"ts_code": ts_code, anchor_param: anchor}
                    for anchor in anchor_values
                ]
            else:
                # 用户未提供日期，只传 ts_code 获取全历史
                logger.info(
                    f"[{ts_code}] 股票无数据，使用单次全历史请求（只传 ts_code）"
                )
                return [{"ts_code": ts_code}]

        # 有已有数据
        if user_provided_dates:
            # 用户提供了日期，生成日期区间内的锚点值，跳过已有的
            anchor_values = self._generate_anchor_values(
                start_date, end_date, anchor_param
            )
            missing_anchors = [a for a in anchor_values if a not in existing_dates]
        else:
            # 用户未提供日期，检测现有数据之后的缺失锚点
            max_existing_date = max(existing_dates) if existing_dates else None
            if max_existing_date:
                # 生成从最大已有日期到结束日期的锚点值
                anchor_values = self._generate_anchor_values(
                    max_existing_date, end_date, anchor_param
                )
                # 排除最大已有日期本身（已经存在）
                missing_anchors = [a for a in anchor_values if a > max_existing_date]
                logger.info(
                    f"[{ts_code}] 用户未提供日期，只检测 {max_existing_date} 之后的缺失锚点"
                )
            else:
                missing_anchors = []

        if not missing_anchors:
            logger.info(f"[{ts_code}] 锚点数据已完整")
            return []

        logger.info(f"[{ts_code}] 缺失 {len(missing_anchors)} 个锚点值")

        return [
            {"ts_code": ts_code, anchor_param: anchor} for anchor in missing_anchors
        ]

    def _detect_no_date_filter_gaps(
        self, interface_name: str, ts_code: str, date_column: str
    ) -> List[Dict[str, Any]]:
        """
        类型 D：无日期过滤缺口检测

        适用于：pledge_detail
        """
        logger.info(f"[{interface_name}/{ts_code}] 无日期过滤模式")

        existing_dates = self.get_stock_existing_dates(
            interface_name, ts_code, date_column
        )

        if existing_dates:
            logger.info(f"[{ts_code}] 已有数据，跳过")
            return []

        logger.info(f"[{ts_code}] 无数据，需要获取全量")
        return [{"ts_code": ts_code}]

    def _generate_report_periods(self, start_date: str, end_date: str) -> List[str]:
        """生成报告期列表（季度末）"""
        periods = []
        start_year = int(start_date[:4])
        end_year = int(end_date[:4])
        quarter_ends = ["0331", "0630", "0930", "1231"]

        for year in range(start_year - 1, end_year + 2):
            for qe in quarter_ends:
                period = f"{year}{qe}"
                if start_date <= period <= end_date:
                    periods.append(period)

        return sorted(periods)

    def _generate_daily_dates(self, start_date: str, end_date: str) -> List[str]:
        """生成每日日期列表"""
        start_dt = datetime.strptime(start_date, "%Y%m%d")
        end_dt = datetime.strptime(end_date, "%Y%m%d")
        delta = end_dt - start_dt
        return [
            (start_dt + timedelta(days=i)).strftime("%Y%m%d")
            for i in range(delta.days + 1)
        ]

    def _generate_anchor_values(
        self, start_date: str, end_date: str, anchor_param: str
    ) -> List[str]:
        """
        生成锚点值列表，根据锚点类型选择合适的生成策略

        修正版：正确处理不同类型的日期锚点
        """
        if anchor_param in ["end_date", "period"]:
            return self._generate_report_periods(start_date, end_date)
        if anchor_param in ["trade_date", "ann_date"]:
            trade_calendar = (
                self.downloader.get_trade_calendar(start_date, end_date)
                if self.downloader
                else None
            )
            if trade_calendar:
                return [
                    day["cal_date"]
                    for day in trade_calendar
                    if day.get("is_open", 0) == 1
                ]
            return self._generate_daily_dates(start_date, end_date)
        return self._generate_report_periods(start_date, end_date)

    def _merge_dates_to_ranges(
        self,
        dates: List[str],
        existing_dates: Optional[set] = None,
        trade_days: Optional[List[str]] = None,
        min_gap_size: int = 3,
    ) -> List[tuple]:
        """
        将缺失日期按空洞边界合并为连续区间

        Args:
            dates: 缺失的日期列表（需已排序）
            existing_dates: 已有数据日期集合，用于确定空洞边界
            trade_days: 交易日历列表，用于按空洞边界分段
            min_gap_size: 最小空洞大小（交易日数）
                          小于此阈值的空洞将被跳过，假设为停牌或数据质量问题

        Returns:
            连续区间列表，每个元素为 (start_date, end_date)

        注意：
            如果传入 existing_dates 和 trade_days，则按空洞边界分段
            如果不传入，则退化为原有逻辑（间隔>3天分段）
        """
        if not dates:
            return []

        sorted_dates = sorted(dates)

        if existing_dates is None or trade_days is None:
            return self._merge_by_interval(sorted_dates)

        ranges = []
        range_start = None
        range_end = None
        gap_count = 0

        for date in trade_days:
            if date not in existing_dates:
                if range_start is None:
                    range_start = date
                    range_end = date
                    gap_count = 1
                else:
                    range_end = date
                    gap_count += 1
            else:
                if range_start is not None:
                    if gap_count >= min_gap_size:
                        ranges.append((range_start, range_end))
                        logger.debug(
                            f"生成下载范围: {range_start} ~ {range_end} ({gap_count}天)"
                        )
                    else:
                        logger.debug(
                            f"跳过小空洞: {range_start} ~ {range_end} ({gap_count}天)"
                        )
                    range_start = None
                    range_end = None
                    gap_count = 0

        if range_start is not None:
            if gap_count >= min_gap_size:
                ranges.append((range_start, range_end))
                logger.debug(
                    f"生成下载范围: {range_start} ~ {range_end} ({gap_count}天)"
                )
            else:
                logger.debug(f"跳过小空洞: {range_start} ~ {range_end} ({gap_count}天)")

        return ranges

    def _merge_by_interval(self, sorted_dates: List[str]) -> List[tuple]:
        """原有逻辑：按间隔>3天分段（保留向后兼容）"""
        ranges = []
        range_start = sorted_dates[0]
        range_end = sorted_dates[0]

        for i in range(1, len(sorted_dates)):
            curr = sorted_dates[i]
            prev = sorted_dates[i - 1]

            curr_dt = datetime.strptime(curr, "%Y%m%d")
            prev_dt = datetime.strptime(prev, "%Y%m%d")

            if (curr_dt - prev_dt).days <= 3:
                range_end = curr
            else:
                ranges.append((range_start, range_end))
                range_start = curr
                range_end = curr

        ranges.append((range_start, range_end))
        return ranges

    def _merge_periods_to_ranges(self, periods: List[str]) -> List[tuple]:
        """
        将缺失报告期按连续性分组

        报告期连续性判断:
        - 同年相邻季度: 0331→0630, 0630→0930, 0930→1231
        - 跨年连续: 1231→次年0331

        Args:
            periods: 报告期列表，格式为 YYYYMMDD（季度末日期）

        Returns:
            连续报告期的范围列表，每个元素为 (range_start, range_end)
        """
        if not periods:
            return []

        sorted_periods = sorted(periods)
        ranges = []
        group_start = sorted_periods[0]
        group_end = sorted_periods[0]

        quarter_order = {"0331": 1, "0630": 2, "0930": 3, "1231": 4}

        for i in range(1, len(sorted_periods)):
            curr = sorted_periods[i]
            prev = sorted_periods[i - 1]

            curr_year = curr[:4]
            prev_year = prev[:4]
            curr_q = quarter_order.get(curr[4:], 0)
            prev_q = quarter_order.get(prev[4:], 0)

            is_continuous = (curr_year == prev_year and curr_q == prev_q + 1) or (
                int(curr_year) == int(prev_year) + 1 and curr_q == 1 and prev_q == 4
            )

            if is_continuous:
                group_end = curr
            else:
                ranges.append((group_start, group_end))
                group_start = curr
                group_end = curr

        ranges.append((group_start, group_end))
        return ranges
