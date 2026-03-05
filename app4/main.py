#!/usr/bin/env python3
"""
aspipe_v4 融合重构版 (App4) - 配置驱动架构
统一CLI入口，保持与原版的参数兼容性
"""

import argparse
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 加载环境变量
from dotenv import load_dotenv

# 使用相对路径加载.env文件
env_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"
)
load_dotenv(env_path)

from core.config_loader import ConfigLoader
from core.downloader import GenericDownloader
from core.scheduler import TaskScheduler
from core.storage import StorageManager
from core.processor import DataProcessor
from core.dedup import deduplicate_against_existing
from core.cache_warmer import CacheWarmer
from core.params_builder import ParamsBuilder
from core.constants import DEFAULT_START_DATE, HISTORICAL_START_DATE
from update.update_manager import UpdateManager
from update.models import UpdateOptions
from update.interface_selector import InterfaceSelector
import polars as pl
import glob


def cleanup_old_stock_basic_files(storage_dir: str, keep_latest: int = 1):
    """
    清理旧的 stock_basic 文件，只保留最新的几个

    Args:
        storage_dir: 存储目录路径
        keep_latest: 保留最新的文件数量，默认为1
    """
    try:
        stock_basic_dir = os.path.join(storage_dir, "stock_basic")
        if not os.path.exists(stock_basic_dir):
            return

        # 获取所有 stock_basic 文件，按修改时间排序
        pattern = os.path.join(stock_basic_dir, "stock_basic_*.parquet")
        files = glob.glob(pattern)

        if len(files) <= keep_latest:
            return

        # 按修改时间排序（最新的在前）
        files.sort(key=os.path.getmtime, reverse=True)

        # 删除旧的文件
        files_to_delete = files[keep_latest:]
        for file_path in files_to_delete:
            try:
                os.remove(file_path)
                logging.info(
                    f"删除旧的 stock_basic 文件: {os.path.basename(file_path)}"
                )
            except Exception as e:
                logging.warning(f"无法删除文件 {file_path}: {e}")

        if files_to_delete:
            logging.info(f"已清理 {len(files_to_delete)} 个旧的 stock_basic 文件")

    except Exception as e:
        logging.warning(f"清理 stock_basic 文件时出错: {e}")


import re


@dataclass
class AppComponents:
    config_loader: ConfigLoader
    storage_manager: StorageManager
    downloader: GenericDownloader
    scheduler: TaskScheduler
    processor: DataProcessor
    cache_warmer: CacheWarmer
    trade_cal_cache: Any
    stock_list_cache: Any


def create_app_components(config_loader: ConfigLoader, args) -> AppComponents:
    """创建并初始化所有核心组件（共享工厂函数）

    main() 和 run_update_mode() 都可以调用此函数，消除初始化代码重复。

    Args:
        args: 命令行参数对象

    Returns:
        AppComponents: 包含所有初始化组件的命名元组
    """
    processor = DataProcessor()
    storage_config = config_loader.global_config.get("storage", {})
    storage_manager = StorageManager(
        processor=processor,
        config_loader=config_loader,
        storage_dir=storage_config.get("base_dir", "../data"),
        format=storage_config.get("format", "parquet"),
        batch_size=storage_config.get("batch_size", 10000),
    )

    cache_warmer = CacheWarmer(storage_config.get("base_dir", "../data"))
    trade_cal_cache = cache_warmer.preload_trade_calendar()
    stock_list_cache = cache_warmer.preload_stock_list()

    downloader = GenericDownloader(
        config_loader=config_loader,
        storage_manager=storage_manager,
        trade_calendar_cache=trade_cal_cache,
        stock_list_cache=stock_list_cache,
    )

    concurrency_config = config_loader.global_config.get("concurrency", {})
    scheduler = TaskScheduler(
        max_workers=concurrency_config.get("max_workers", 4),
        max_queue_size=concurrency_config.get("max_queue_size", 1000),
    )

    return AppComponents(
        config_loader=config_loader,
        storage_manager=storage_manager,
        downloader=downloader,
        scheduler=scheduler,
        processor=processor,
        cache_warmer=cache_warmer,
        trade_cal_cache=trade_cal_cache,
        stock_list_cache=stock_list_cache,
    )


DATE_PATTERN = re.compile(r"^\d{8}$")


def validate_and_adjust_date(
    start_date: str, end_date: Optional[str]
) -> Tuple[str, str]:
    """
    Enhanced date validation with format and range checking.

    Args:
        start_date: Start date in YYYYMMDD format
        end_date: End date in YYYYMMDD format, can be None

    Returns:
        Tuple of validated (start_date, end_date)

    Raises:
        ValueError: If date format is invalid or range is incorrect
    """
    # 处理 end_date 为 None 的情况
    if end_date is None:
        end_date = datetime.now().strftime("%Y%m%d")

    # 格式验证
    if not DATE_PATTERN.match(start_date):
        raise ValueError(f"Invalid start_date format: {start_date}, expected YYYYMMDD")
    if not DATE_PATTERN.match(end_date):
        raise ValueError(f"Invalid end_date format: {end_date}, expected YYYYMMDD")

    # 日期有效性验证
    try:
        start_dt = datetime.strptime(start_date, "%Y%m%d")
        end_dt = datetime.strptime(end_date, "%Y%m%d")
    except ValueError as e:
        raise ValueError(f"Invalid date: {e}")

    # start_date <= end_date 检查
    if start_dt > end_dt:
        raise ValueError(f"start_date ({start_date}) must be <= end_date ({end_date})")

    # 调整未来日期
    today = datetime.now()
    if end_dt > today:
        end_date = today.strftime("%Y%m%d")

    return start_date, end_date


def _prepare_stock_list(downloader, args, params, storage_manager, logger):
    """统一的股票列表准备方法"""
    # 获取股票列表 - 从Data目录或API获取
    stock_list = downloader._get_stock_list_from_data_dir()
    if stock_list is None:
        logger.info("Data目录中未找到股票列表，正在从API获取...")
        stock_params = {"list_status": "L"}
        stock_list = downloader.download("stock_basic", stock_params)
        if stock_list:
            logger.info(f"从API获取到 {len(stock_list)} 只股票")
            # 保存到Data目录
            storage_manager.save_data("stock_basic", stock_list, async_write=False)
            # 清理旧的 stock_basic 文件
            cleanup_old_stock_basic_files(storage_manager.storage_dir, keep_latest=1)
        else:
            logger.warning("未能从API获取股票列表")
            return None

    # 如果参数中指定了股票代码，则只下载该股票
    if "ts_code" in params:
        target_code = params["ts_code"]
        stock_list = [stock for stock in stock_list if stock["ts_code"] == target_code]
        logger.info(
            f"Filtered to specific stock: {target_code}, {len(stock_list)} stocks remaining"
        )

    return stock_list


def run_concurrent_stock_download(
    downloader,
    scheduler,
    interface_name,
    interface_config,
    params_list,
    stock_list,
    storage_manager,
    processor,
    logger,
    context=None,
):
    """运行并发股票下载 - 统一使用buffer机制"""
    logger.info(
        f"Starting concurrent download for {interface_name} with {len(params_list)} tasks"
    )

    # 统一使用buffer机制，不再在主线程批量处理
    total_records = 0

    # 构建任务列表
    stock_map = {
        stock.get("ts_code"): stock
        for stock in stock_list or []
        if stock.get("ts_code")
    }
    tasks = []
    for params in params_list:
        ts_code = params.get("ts_code")
        stock = stock_map.get(ts_code, {"ts_code": ts_code} if ts_code else {})
        task = {
            "func": downloader.download_single_stock,
            "args": (interface_config, stock, params),
            "kwargs": {"context": context},
        }
        tasks.append(task)

        # 每批提交一定数量的任务，避免内存溢出
        if len(tasks) >= 100:
            logger.info(f"Submitting batch of {len(tasks)} tasks")
            results = scheduler.submit_tasks(tasks)

            # buffer机制会自动处理数据，不再累积到all_data
            for result in results:
                if result:
                    total_records += result

            logger.info(f"Completed batch, total records: {total_records}")
            tasks = []

    # 提交剩余任务
    if tasks:
        logger.info(f"Submitting final batch of {len(tasks)} tasks")
        results = scheduler.submit_tasks(tasks)

        for result in results:
            if result:
                total_records += result

        logger.info(f"Completed final batch, total records: {total_records}")

    # 等待buffer机制处理完成
    # buffer机制会自动处理数据的累积和写入

    return total_records


def preload_global_trade_calendar(
    downloader, storage_manager, logger, start_date=HISTORICAL_START_DATE, end_date=None
):
    """预加载全局交易日历，优先从内存缓存读取，然后Data目录，最后API获取

    Args:
        downloader: 下载器实例
        storage_manager: 存储管理器实例
        logger: 日志记录器
        start_date: 开始日期 (YYYYMMDD)
        end_date: 结束日期 (YYYYMMDD)，如果为None则使用当前日期

    Returns:
        List[Dict]: 交易日历列表，如果失败则返回 None
    """
    if end_date is None:
        end_date = datetime.now().strftime("%Y%m%d")

    logger.info(f"Preloading global trade calendar: {start_date} - {end_date}")

    # 1. 首先检查内存缓存（CacheWarmer 已预加载）
    cache_key = ("global",)
    with downloader._cache_lock:
        if cache_key in downloader._memory_cache["trade_cal"]:
            trade_calendar = downloader._memory_cache["trade_cal"][cache_key]
            # 过滤出指定日期范围内的交易日
            trade_days = [
                day
                for day in trade_calendar
                if start_date <= day.get("cal_date", "") <= end_date
                and day.get("is_open", 0) == 1
            ]
            if trade_days:
                logger.info(
                    f"Global trade calendar loaded from memory cache: {len(trade_days)} trade days"
                )
                return trade_days

    # 2. 检查本地磁盘数据
    trade_calendar = downloader._get_trade_calendar_from_data_dir(start_date, end_date)

    if trade_calendar:
        logger.info(
            f"Global trade calendar loaded from data directory: {len(trade_calendar)} trade days"
        )
        # 手动填充内存缓存
        cache_key = (start_date, end_date)
        with downloader._cache_lock:
            downloader._memory_cache["trade_cal"][cache_key] = trade_calendar
        return trade_calendar

    # 3. Data目录未命中，请求 API
    logger.info("Global trade calendar not found locally, fetching from API...")
    calendar_params = {
        "start_date": start_date,
        "end_date": end_date,
        "exchange": "SSE",
    }

    trade_calendar = downloader._make_request(
        downloader.config_loader.get_interface_config("trade_cal"), calendar_params
    )

    if trade_calendar:
        # 过滤出交易日
        trade_days = [day for day in trade_calendar if day.get("is_open", 0) == 1]
        trade_days = sorted(trade_days, key=lambda x: x["cal_date"])

        # 保存到存储
        logger.info(f"Saving {len(trade_days)} trade days to storage")
        storage_manager.save_data("trade_cal", trade_calendar, async_write=False)

        # 填充内存缓存
        cache_key = (start_date, end_date)
        with downloader._cache_lock:
            downloader._memory_cache["trade_cal"][cache_key] = trade_calendar

        logger.info(f"Preloaded {len(trade_days)} trade days from API")
        return trade_days
    else:
        logger.warning("Failed to preload trade calendar")
        return None


def process_and_save_data(
    data, interface_name, interface_config, processor, storage_manager, logger
):
    """处理并保存数据的通用函数 - 使用异步处理模式

    Args:
        data: 原始数据列表
        interface_name: 接口名称
        interface_config: 接口配置
        processor: 数据处理器
        storage_manager: 存储管理器
        logger: 日志记录器

    Returns:
        处理后的 DataFrame，如果处理失败则返回 None
    """
    import polars as pl

    if not data:
        logger.warning(f"No data to process for {interface_name}")
        return None

    # 处理数据
    df = processor.process_data(data, interface_config)

    if df.is_empty():
        logger.warning(f"Processed empty DataFrame for {interface_name}")
        return None

    validation_result = processor.validate_data(df, interface_config)

    # 使用接口配置获取主键和去重配置
    output_config = interface_config.get("output", {})
    primary_keys = output_config.get("primary_key", [])
    dedup_config = interface_config.get("dedup", {"dedup_enabled": True})

    # 如果去重功能启用且存在主键定义
    # [简化] 禁用与已有数据的去重，依赖 CoverageManager + 存储层主键约束
    # 批次内去重已在 processor.process_data() 中完成
    if False:  # dedup_config.get('dedup_enabled', True) and primary_keys:
        # 读取该接口的所有现有数据文件（支持Parquet Dataset模式）
        try:
            existing_df = storage_manager.read_interface_data(
                interface_name, columns=primary_keys
            )
        except Exception as e:
            logger.warning(f"无法读取现有数据进行去重: {e}")
            existing_df = pl.DataFrame()

        if not existing_df.is_empty():
            # 使用临时文件进行去重
            import tempfile

            try:
                with tempfile.NamedTemporaryFile(
                    suffix=".parquet", delete=False
                ) as tmp_file:
                    existing_df.write_parquet(tmp_file.name)
                    temp_path = tmp_file.name

                # 使用统一的去重模块
                df, dedup_stats = deduplicate_against_existing(
                    new_data=df, existing_data_path=temp_path, primary_keys=primary_keys
                )

                logger.info(
                    f"Deduplication completed for {interface_name}: "
                    f"input={dedup_stats.input_rows}, "
                    f"compared={dedup_stats.compared_rows}, "
                    f"output={dedup_stats.output_rows}, "
                    f"removed={dedup_stats.removed_rows}, "
                    f"dedup_rate={dedup_stats.get_dedup_rate():.2f}%"
                )

                # 检查去重结果
                if dedup_stats.errors:
                    for error in dedup_stats.errors:
                        logger.error(
                            f"Deduplication error for {interface_name}: {error}"
                        )
                if dedup_stats.warnings:
                    for warning in dedup_stats.warnings:
                        logger.warning(
                            f"Deduplication warning for {interface_name}: {warning}"
                        )

                # 如果所有数据都被过滤掉了，则直接返回
                if len(df) == 0:
                    logger.info(
                        f"All records already exist for {interface_name}, skipping save"
                    )
                    return df
            finally:
                if "temp_path" in locals() and os.path.exists(temp_path):
                    os.unlink(temp_path)
        else:
            logger.info(
                f"No existing data found for {interface_name}, skipping deduplication"
            )

    logger.info(f"Processed {len(df)} records for {interface_name}")
    if validation_result["duplicate_records"] > 0:
        logger.info(
            f"Found {validation_result['duplicate_records']} duplicate records for {interface_name}"
        )

    # 使用异步保存模式，而不是直接调用 _write_interface_data
    # 这样数据会被放入队列，由 _process_worker 线程统一处理
    storage_manager.save_data(interface_name, df.to_dicts(), async_write=True)

    return df


def run_update_mode(args):
    """运行增量更新模式（薄包装层）

    使用 UpdateManager 执行实际的更新逻辑，解锁断点续传、结构化报告等功能。

    Args:
        args: 命令行参数

    Returns:
        int: 退出码 (0=成功, 1=失败)
    """
    # 初始化配置加载器
    config_dir_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
    config_loader = ConfigLoader(config_dir=config_dir_path)

    # 验证配置
    if not config_loader.validate_config():
        print("Configuration validation failed")
        return 1

    # 设置日志
    logging_config = config_loader.global_config.get("logging", {})
    if args.log_level:
        logging_config["level"] = args.log_level
    setup_logging(logging_config)

    logger = logging.getLogger(__name__)
    logger.info("Starting aspipe_v4 App4 - Incremental Update Mode")

    components = create_app_components(
        config_loader=config_loader,
        args=args,
    )

    # 启动组件
    components.scheduler.start()
    components.storage_manager.start_writer()

    try:
        # 合并 --interface 和 --update-interface 参数
        interfaces_to_update = None
        if hasattr(args, "update_interfaces") and args.update_interfaces:
            interfaces_to_update = args.update_interfaces.copy()
        if hasattr(args, "interface") and args.interface:
            if interfaces_to_update is None:
                interfaces_to_update = (
                    args.interface
                    if isinstance(args.interface, list)
                    else [args.interface]
                )
            else:
                interfaces_to_update.extend(
                    args.interface
                    if isinstance(args.interface, list)
                    else [args.interface]
                )

        # 处理 --update-group 参数
        if hasattr(args, "update_groups") and args.update_groups:
            # 使用 interface_selector 来获取组内的接口
            interface_selector = InterfaceSelector(config_loader)
            group_interfaces = []
            for group_name in args.update_groups:
                group_interfaces.extend(
                    interface_selector._get_group_interfaces(group_name)
                )

            if interfaces_to_update is None:
                interfaces_to_update = group_interfaces
            else:
                interfaces_to_update.extend(group_interfaces)

        # 根据用户积分过滤接口
        actual_points = int(os.getenv("TUSHARE_POINTS", "120"))
        interface_selector = InterfaceSelector(config_loader)
        all_interfaces = config_loader.get_available_interfaces()

        if interfaces_to_update:
            # 验证接口是否存在
            valid_interfaces = [i for i in interfaces_to_update if i in all_interfaces]
            for iface in interfaces_to_update:
                if iface not in all_interfaces:
                    logger.warning(f"指定的接口 '{iface}' 不存在，已忽略")
        else:
            valid_interfaces = all_interfaces
            logger.info(
                f"No interfaces specified, updating all {len(valid_interfaces)} available interfaces"
            )

        # 根据积分权限过滤
        valid_interfaces = interface_selector.filter_by_permission(
            valid_interfaces, actual_points
        )
        logger.info(
            f"Interfaces to update (after permission filter): {valid_interfaces}"
        )

        # 构建 UpdateOptions
        user_provided_dates = getattr(args, "user_provided_dates", False)
        options = UpdateOptions(
            interfaces=valid_interfaces,
            start_date=args.start_date if user_provided_dates else None,
            end_date=args.end_date if user_provided_dates else None,
            force=getattr(args, "update_force", False),
            dry_run=getattr(args, "dry_run", False),
            gap_detection_enabled=True,
            ts_code=getattr(args, "ts_code", None),  # 新增：指定股票代码
        )

        # 创建 UpdateManager 并执行更新
        update_manager = UpdateManager(
            config_loader=config_loader,
            storage_manager=components.storage_manager,
            downloader=components.downloader,
            scheduler=components.scheduler,
            processor=components.processor,
        )

        result = update_manager.run_update(options)

        # 返回退出码
        if result.is_success:
            logger.info(
                f"\n更新成功完成: {result.success_count} 成功, {result.skipped_count} 跳过"
            )
            return 0
        else:
            logger.warning(
                f"\n更新完成但有失败: {result.success_count} 成功, {result.failed_count} 失败, {result.skipped_count} 跳过"
            )
            return 1

    except KeyboardInterrupt:
        logger.warning("\n用户手动中断执行 (Ctrl+C detected)")
        return 130  # 标准的中断退出码
    except Exception as e:
        logger.exception(f"更新过程中发生错误: {e}")
        return 1
    finally:
        # 清理资源
        logger.info("正在停止调度器...")
        components.scheduler.stop()

        logger.info("正在刷新并关闭存储写入...")
        components.storage_manager.stop_writer()

        if hasattr(components.downloader, "global_rate_limiter"):
            try:
                stats = components.downloader.global_rate_limiter.get_stats()
                logger.info(
                    f"限流统计: 总请求={stats['total_requests']}, "
                    f"总等待={stats['total_wait_time']}s, "
                    f"平均等待={stats['average_wait_time']}s, "
                    f"最大等待={stats['max_wait_time']}s"
                )
            except Exception as e:
                logger.warning(f"获取限流统计失败: {e}")

        logger.info("资源清理完毕，程序退出。")


def setup_logging(log_config: dict):
    """设置日志配置

    Args:
        log_config: 日志配置字典，包含 level, file, max_size_mb, backup_count
    """
    log_level = log_config.get("level")
    log_file = log_config.get("file")
    max_size_mb = log_config.get("max_size_mb")
    backup_count = log_config.get("backup_count")

    # 确保日志目录存在
    log_dir = os.path.dirname(log_file)
    os.makedirs(log_dir, exist_ok=True)

    # 创建日志格式器
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # 创建文件处理器（支持轮转）
    from logging.handlers import RotatingFileHandler

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_size_mb * 1024 * 1024,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(getattr(logging, log_level))
    file_handler.setFormatter(formatter)

    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level))
    console_handler.setFormatter(formatter)

    # 配置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


def main():
    parser = argparse.ArgumentParser(description="aspipe_v4 融合重构版 - 配置驱动架构")

    # 保持与原版的参数兼容性
    parser.add_argument(
        "--start_date", type=str, default=DEFAULT_START_DATE, help="起始日期 (YYYYMMDD)"
    )
    parser.add_argument(
        "--end_date", type=str, default=None, help="结束日期 (YYYYMMDD)"
    )
    parser.add_argument("--holders-data", action="store_true", help="下载股东数据")
    parser.add_argument("--pro-bar-only", action="store_true", help="仅下载pro_bar数据")
    parser.add_argument(
        "--tscode-historical", action="store_true", help="全历史数据下载"
    )

    # 新增通用参数
    parser.add_argument(
        "--interface", type=str, nargs="+", help="指定接口名称（可指定多个，空格分隔）"
    )
    parser.add_argument("--group", type=str, help="指定接口组名称")
    parser.add_argument(
        "--concurrency",
        type=int,
        default=4,  # [修改] 从 8 改为 4
        help="并发数",
    )
    parser.add_argument("--log-level", type=str, default="INFO", help="日志级别")
    parser.add_argument("--ts_code", type=str, help="指定股票代码 (如: 000001.SZ)")

    # 新增增量更新模块参数
    parser.add_argument(
        "--update", action="store_true", help="启用增量更新模式（推荐）"
    )
    parser.add_argument(
        "--update-interface",
        type=str,
        action="append",
        dest="update_interfaces",
        help="指定要更新的接口（可多次使用）",
    )
    parser.add_argument(
        "--update-group",
        type=str,
        action="append",
        dest="update_groups",
        help="指定要更新的接口组（可多次使用）",
    )
    parser.add_argument(
        "--update-exclude",
        type=str,
        action="append",
        dest="update_exclusions",
        help="排除特定接口（可多次使用）",
    )
    parser.add_argument(
        "--update-force",
        action="store_true",
        dest="update_force",
        help="强制更新（忽略现有数据）",
    )
    parser.add_argument(
        "--update-dry-run",
        action="store_true",
        dest="update_dry_run",
        help="预览模式（不实际执行）",
    )
    parser.add_argument(
        "--update-report-format",
        type=str,
        choices=["markdown", "json", "html"],
        default="markdown",
        dest="update_report_format",
        help="报告格式",
    )
    parser.add_argument(
        "--update-report-file",
        type=str,
        dest="update_report_file",
        help="报告输出文件路径",
    )

    parser.add_argument(
        "--no-performance-report", action="store_true", help="禁用性能报告生成"
    )
    parser.add_argument(
        "--performance-report-dir", type=str, help="指定性能报告输出目录"
    )

    args = parser.parse_args()
    user_provided_start_date = "--start_date" in sys.argv
    user_provided_end_date = "--end_date" in sys.argv
    user_provided_dates = user_provided_start_date or user_provided_end_date
    setattr(args, "user_provided_dates", user_provided_dates)

    # 如果是更新模式，执行增量更新
    if args.update:
        return run_update_mode(args)

    # 初始化配置加载器（需要在设置日志之前）
    config_dir_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
    config_loader = ConfigLoader(config_dir=config_dir_path)

    # 验证配置
    if not config_loader.validate_config():
        print("Configuration validation failed")
        return 1

    # 设置日志 - 从 settings.yaml 读取配置
    logging_config = config_loader.global_config.get("logging", {})
    # 如果命令行指定了日志级别，则覆盖配置文件中的设置
    if args.log_level:
        logging_config["level"] = args.log_level
    setup_logging(logging_config)

    logger = logging.getLogger(__name__)
    logger.info("Starting aspipe_v4 App4 - Configuration-driven architecture")

    # 初始化性能监控器配置
    performance_config = config_loader.global_config.get("performance", {})
    performance_enabled = performance_config.get("enabled", True)

    components = create_app_components(
        config_loader=config_loader,
        args=args,
    )

    def print_performance_report():
        """打印性能监控报告"""
        print("\n" + "=" * 30)
        print("      性能监控报告")
        print("=" * 30)

        # 使用新的性能监控器
        if (
            hasattr(components.downloader, "performance_monitor")
            and components.downloader.performance_monitor
        ):
            summary = components.downloader.performance_monitor.get_summary()

            print(
                f"总运行时间: {time.time() - components.downloader.performance_monitor.start_time:.2f}秒"
            )
            print(f"总请求数: {len(components.downloader.performance_monitor.metrics)}")
            print(f"接口数量: {len(summary)}")
            print("-" * 30)

            for interface, stats in summary.items():
                print(f"接口: {interface}")
                print(f"  - 请求次数: {stats['total_requests']}")
                print(f"  - 总记录数: {stats['total_records']}")
                print(f"  - 成功率: {stats['success_rate']:.1f}%")
                print(f"  - 平均请求时间: {stats['avg_duration']:.2f}秒")
                print(
                    f"  - P50/P90/P99: {stats['p50_duration']:.2f}/{stats['p90_duration']:.2f}/{stats['p99_duration']:.2f}秒"
                )
                print(f"  - 平均记录数: {stats['avg_records']:.0f}条")
                print()
        else:
            print("未找到性能监控器")

        print("=" * 30 + "\n")

    # 预加载全局交易日历
    preload_global_trade_calendar(
        components.downloader, components.storage_manager, logger
    )

    # 启动各组件
    components.scheduler.start()
    components.storage_manager.start_writer()

    # [新增] try...finally 结构
    try:
        # 确定要执行的接口
        interfaces_to_run = []

        # 参数映射逻辑（改为累加模式）
        if args.tscode_historical:
            # tscode-historical 模式：使用配置组，获取所有需要股票循环模式的接口
            tscode_historical_group = config_loader.global_config.get("groups", {}).get(
                "tscode_historical", []
            )
            interfaces_to_run.extend(tscode_historical_group)

        if args.pro_bar_only:
            # pro_bar_only 模式：添加 pro_bar 接口
            interfaces_to_run.append("pro_bar")

        if args.holders_data:
            # holders_data 模式：添加 holders 组
            holders_group = config_loader.global_config.get("groups", {}).get(
                "holders", []
            )
            interfaces_to_run.extend(holders_group)

        if args.interface:
            # 指定接口（支持多个）
            interfaces_to_run.extend(args.interface)

        if args.group:
            # 指定组
            groups = config_loader.global_config.get("groups", {})
            if args.group in groups:
                interfaces_to_run.extend(groups[args.group])
            else:
                logger.error(f"Group '{args.group}' not found")
                return 1

        # 如果没有指定任何参数，使用默认行为
        if not interfaces_to_run:
            # 默认运行所有可用接口（可根据积分限制过滤）
            available_interfaces = config_loader.get_available_interfaces()
            # 过滤掉ts_code依赖的接口和pro_bar
            tscode_historical_group = config_loader.global_config.get("groups", {}).get(
                "tscode_historical", []
            )
            interfaces_to_run = [
                iface
                for iface in available_interfaces
                if iface not in tscode_historical_group and iface != "pro_bar"
            ]

        logger.info(f"Interfaces to run: {interfaces_to_run}")

        # 执行下载任务
        for interface_name in interfaces_to_run:
            try:
                # 获取接口配置
                try:
                    interface_config = config_loader.get_interface_config(
                        interface_name
                    )
                except ValueError:
                    logger.error(
                        f"Interface '{interface_name}' not found in configuration, skipping..."
                    )
                    continue  # 跳过此接口，继续处理下一个

                # 检查积分要求
                min_points = interface_config.get("permissions", {}).get(
                    "min_points", 0
                )
                actual_points = int(os.getenv("TUSHARE_POINTS", "120"))
                if min_points > actual_points:  # 直接比较实际积分要求
                    logger.warning(
                        f"Insufficient points for interface {interface_name} (required: {min_points}, available: {actual_points})"
                    )
                    continue

                # [新增] 检查是否是 tscode_historical 接口
                tscode_historical_group = config_loader.global_config.get(
                    "groups", {}
                ).get("tscode_historical", [])
                is_tscode_historical_interface = (
                    interface_name in tscode_historical_group
                )

                # [新增] 对于 tscode_historical 接口，如果用户使用默认日期，则改为 1990年1月1日
                # 使用局部变量，不修改共享的 args 对象
                loop_start_date = args.start_date
                loop_end_date = args.end_date

                if (
                    is_tscode_historical_interface
                    and not user_provided_dates
                    and interface_name != "disclosure_date"
                ):
                    if loop_start_date == DEFAULT_START_DATE and loop_end_date is None:
                        logger.info(
                            f"Using default date range for tscode_historical interface {interface_name}: {HISTORICAL_START_DATE} to today"
                        )
                        loop_start_date = HISTORICAL_START_DATE
                        loop_end_date = datetime.now().strftime("%Y%m%d")

                # 准备请求参数
                loop_start_date, loop_end_date = validate_and_adjust_date(
                    loop_start_date, loop_end_date
                )

                builder = ParamsBuilder(interface_config)
                # 使用 date_range 参数传递当前循环的日期，避免污染 args 对象
                result = builder.build(
                    args,
                    date_range={
                        "start_date": loop_start_date,
                        "end_date": loop_end_date,
                    },
                )

                if result.requires_stock_loop:
                    stock_list = _prepare_stock_list(
                        components.downloader,
                        args,
                        result.params,
                        components.storage_manager,
                        logger,
                    )
                    if stock_list is None:
                        logger.warning(
                            f"Failed to get stock list for {interface_name}, skipping..."
                        )
                        continue

                    params_list, context = builder.build_params_list(result, stock_list)
                    downloaded_count = run_concurrent_stock_download(
                        components.downloader,
                        components.scheduler,
                        interface_name,
                        interface_config,
                        params_list,
                        stock_list,
                        components.storage_manager,
                        components.processor,
                        logger,
                        context,
                    )

                    if downloaded_count > 0:
                        logger.info(
                            f"Successfully downloaded {downloaded_count} total records for {interface_name}"
                        )
                    else:
                        logger.warning(f"No data downloaded for {interface_name}")
                    continue

                if result.requires_month_loop:
                    params_list, _ = builder.build_params_list(result)
                    all_data = []
                    for params in params_list:
                        data = components.downloader.download(interface_name, params)
                        if data:
                            all_data.extend(data)

                    if all_data:
                        logger.info(
                            f"Successfully downloaded {len(all_data)} records for {interface_name}"
                        )
                        process_and_save_data(
                            all_data,
                            interface_name,
                            interface_config,
                            components.processor,
                            components.storage_manager,
                            logger,
                        )
                    else:
                        logger.warning(f"No data downloaded for {interface_name}")
                    continue

                pagination_config = interface_config.get("pagination", {})
                pagination_mode = (
                    pagination_config.get("mode", "offset")
                    if pagination_config.get("enabled", False)
                    else "none"
                )
                logger.info(
                    f"Downloading data for {interface_name}, pagination mode: {pagination_mode}"
                )

                data = components.downloader.download(interface_name, result.params)

                if data:
                    logger.info(
                        f"Successfully downloaded {len(data)} records for {interface_name}"
                    )
                    process_and_save_data(
                        data,
                        interface_name,
                        interface_config,
                        components.processor,
                        components.storage_manager,
                        logger,
                    )
                else:
                    logger.warning(f"No data downloaded for {interface_name}")

            except Exception as e:
                logger.exception(
                    f"Error processing interface {interface_name}: {str(e)}"
                )

    except KeyboardInterrupt:
        logger.warning("\n用户手动中断执行 (Ctrl+C detected)")
    except Exception as e:
        logger.exception(f"发生未捕获异常: {e}")
    finally:
        # [关键] 无论成功、失败还是中断，都执行清理
        logger.info("正在停止调度器...")
        if "components" in locals():
            components.scheduler.stop()

        logger.info("正在刷新并关闭存储写入...")
        if "components" in locals():
            # 先显示缓存统计
            buffer_stats = components.storage_manager.get_buffer_stats()
            if buffer_stats["total_interfaces"] > 0:
                for iface, stats in buffer_stats["interface_stats"].items():
                    if stats["buffer_count"] > 0:
                        logger.info(
                            f"  - 接口 {iface}: {stats['buffer_count']} 条记录待写入"
                        )

            components.storage_manager.stop_writer()

        # 生成性能报告
        perf_report_enabled = (
            performance_config.get("auto_generate_report", True)
            and not args.no_performance_report
        )

        if perf_report_enabled and performance_enabled:
            print_performance_report()

        # 保存性能报告到文件
        if (
            perf_report_enabled
            and performance_enabled
            and "components" in locals()
            and hasattr(components.downloader, "performance_monitor")
            and components.downloader.performance_monitor
        ):
            # 使用配置的输出目录，或命令行参数覆盖，或默认目录
            report_dir = getattr(args, "performance_report_dir", None)
            if not report_dir:
                report_dir = performance_config.get("output_dir", "log/")

            os.makedirs(report_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            filename_prefix = performance_config.get(
                "report_filename_prefix", "performance_report"
            )
            output_format = performance_config.get("output_format", "markdown")

            if output_format == "json":
                performance_file = os.path.join(
                    report_dir, f"{filename_prefix}_{timestamp}.json"
                )
            else:
                performance_file = os.path.join(
                    report_dir, f"{filename_prefix}_{timestamp}.md"
                )

            components.downloader.performance_monitor.save_report(performance_file)
            logger.info(f"性能报告已生成: {performance_file}")

        if "components" in locals() and hasattr(
            components.downloader, "global_rate_limiter"
        ):
            try:
                stats = components.downloader.global_rate_limiter.get_stats()
                logger.info(
                    f"限流统计: 总请求={stats['total_requests']}, "
                    f"总等待={stats['total_wait_time']}s, "
                    f"平均等待={stats['average_wait_time']}s, "
                    f"最大等待={stats['max_wait_time']}s"
                )
            except Exception as e:
                logger.warning(f"获取限流统计失败: {e}")

        logger.info("资源清理完毕，程序退出。")


if __name__ == "__main__":
    sys.exit(main())
