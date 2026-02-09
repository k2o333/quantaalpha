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
from datetime import datetime
from typing import Dict, Any, List

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 加载环境变量
from dotenv import load_dotenv
import os
# 使用相对路径加载.env文件
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path)

from core.config_loader import ConfigLoader
from core.downloader import GenericDownloader
from core.scheduler import TaskScheduler, RateLimiter
from core.storage import StorageManager
from core.processor import DataProcessor
from core.dedup import deduplicate_against_existing
from core.cache_warmer import CacheWarmer
from update.date_calculator import DateCalculator
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
        stock_basic_dir = os.path.join(storage_dir, 'stock_basic')
        if not os.path.exists(stock_basic_dir):
            return

        # 获取所有 stock_basic 文件，按修改时间排序
        pattern = os.path.join(stock_basic_dir, 'stock_basic_*.parquet')
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
                logging.info(f"删除旧的 stock_basic 文件: {os.path.basename(file_path)}")
            except Exception as e:
                logging.warning(f"无法删除文件 {file_path}: {e}")

        if files_to_delete:
            logging.info(f"已清理 {len(files_to_delete)} 个旧的 stock_basic 文件")

    except Exception as e:
        logging.warning(f"清理 stock_basic 文件时出错: {e}")


import re
from datetime import datetime
from typing import Tuple, Optional

DATE_PATTERN = re.compile(r'^\d{8}$')

def validate_and_adjust_date(start_date: str, end_date: Optional[str]) -> Tuple[str, str]:
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
        end_date = datetime.now().strftime('%Y%m%d')

    # 格式验证
    if not DATE_PATTERN.match(start_date):
        raise ValueError(f"Invalid start_date format: {start_date}, expected YYYYMMDD")
    if not DATE_PATTERN.match(end_date):
        raise ValueError(f"Invalid end_date format: {end_date}, expected YYYYMMDD")

    # 日期有效性验证
    try:
        start_dt = datetime.strptime(start_date, '%Y%m%d')
        end_dt = datetime.strptime(end_date, '%Y%m%d')
    except ValueError as e:
        raise ValueError(f"Invalid date: {e}")

    # start_date <= end_date 检查
    if start_dt > end_dt:
        raise ValueError(f"start_date ({start_date}) must be <= end_date ({end_date})")

    # 调整未来日期
    today = datetime.now()
    if end_dt > today:
        end_date = today.strftime('%Y%m%d')

    return start_date, end_date


def _prepare_stock_list(downloader, args, params, storage_manager, logger):
    """统一的股票列表准备方法"""
    # 获取股票列表 - 从Data目录或API获取
    stock_list = downloader._get_stock_list_from_data_dir()
    if stock_list is None:
        logger.info("Data目录中未找到股票列表，正在从API获取...")
        stock_params = {'list_status': 'L'}
        stock_list = downloader.download('stock_basic', stock_params)
        if stock_list:
            logger.info(f"从API获取到 {len(stock_list)} 只股票")
            # 保存到Data目录
            storage_manager.save_data('stock_basic', stock_list, async_write=False)
            # 清理旧的 stock_basic 文件
            cleanup_old_stock_basic_files(storage_manager.storage_dir, keep_latest=1)
        else:
            logger.warning("未能从API获取股票列表")
            return None

    # 如果参数中指定了股票代码，则只下载该股票
    if 'ts_code' in params:
        target_code = params['ts_code']
        stock_list = [stock for stock in stock_list if stock['ts_code'] == target_code]
        logger.info(f"Filtered to specific stock: {target_code}, {len(stock_list)} stocks remaining")

    return stock_list


def run_concurrent_stock_download(downloader, scheduler, interface_name, interface_config, base_params, stock_list, rate_limiter, storage_manager, processor, logger):
    """运行并发股票下载 - 统一使用buffer机制"""
    logger.info(f"Starting concurrent download for {interface_name} with {len(stock_list)} stocks")

    # 创建包装函数，包含限流逻辑
    def download_single_stock_with_rate_limit(interface_config, stock, params):
        # 在工作线程中等待令牌
        rate_limiter.wait_for_tokens(1)
        return downloader.download_single_stock(interface_config, stock, params)

    # 统一使用buffer机制，不再在主线程批量处理
    total_records = 0

    # 构建任务列表
    tasks = []
    for stock in stock_list:
        task = {
            'func': download_single_stock_with_rate_limit,
            'args': (interface_config, stock, base_params),
            'kwargs': {}
        }
        tasks.append(task)

        # 每批提交一定数量的任务，避免内存溢出
        if len(tasks) >= 100:
            logger.info(f"Submitting batch of {len(tasks)} tasks")
            results = scheduler.submit_tasks(tasks)

            # buffer机制会自动处理数据，不再累积到all_data
            for result in results:
                if result:
                    total_records += len(result)

            logger.info(f"Completed batch, total records: {total_records}")
            tasks = []

    # 提交剩余任务
    if tasks:
        logger.info(f"Submitting final batch of {len(tasks)} tasks")
        results = scheduler.submit_tasks(tasks)

        for result in results:
            if result:
                total_records += len(result)

        logger.info(f"Completed final batch, total records: {total_records}")

    # 等待buffer机制处理完成
    # buffer机制会自动处理数据的累积和写入

    return total_records


def run_update_mode(args):
    """运行增量更新模式
    
    Args:
        args: 命令行参数
        
    Returns:
        int: 退出码 (0=成功, 1=失败)
    """
    # 初始化配置加载器
    import os
    config_dir_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
    config_loader = ConfigLoader(config_dir=config_dir_path)
    
    # 验证配置
    if not config_loader.validate_config():
        print("Configuration validation failed")
        return 1
    
    # 设置日志
    logging_config = config_loader.global_config.get('logging', {})
    if args.log_level:
        logging_config['level'] = args.log_level
    setup_logging(logging_config)
    
    logger = logging.getLogger(__name__)
    logger.info("Starting aspipe_v4 App4 - Incremental Update Mode")
    
    # 初始化组件
    scheduler = TaskScheduler(
        max_workers=config_loader.global_config.get('concurrency', {}).get('max_workers', 4),
        max_queue_size=config_loader.global_config.get('concurrency', {}).get('max_queue_size', 1000)
    )
    
    processor = DataProcessor()
    storage_manager = StorageManager(
        processor=processor,
        config_loader=config_loader,
        storage_dir=config_loader.global_config.get('storage', {}).get('base_dir', '../data'),
        format=config_loader.global_config.get('storage', {}).get('format', 'parquet'),
        batch_size=config_loader.global_config.get('storage', {}).get('batch_size', 10000)
    )
    
    # 初始化缓存预热器
    data_dir = config_loader.get_global_config()['storage']['base_dir']
    cache_warmer = CacheWarmer(data_dir)
    
    # 预热缓存
    logger.info("预热全局缓存...")
    trade_cal_cache = cache_warmer.preload_trade_calendar()
    stock_list_cache = cache_warmer.preload_stock_list()
    
    # 创建下载器
    downloader = GenericDownloader(
        config_loader=config_loader,
        storage_manager=storage_manager,
        trade_calendar_cache=trade_cal_cache,
        stock_list_cache=stock_list_cache,
        force_download=args.update_force if hasattr(args, 'update_force') else False,
        incremental_mode=True
    )

    date_calculator = DateCalculator(config_loader, storage_manager)
    
    # 创建全局速率限制器
    global_rate_limit = config_loader.global_config.get('request', {}).get('rate_limit', 60)
    global_rate_limiter = RateLimiter(global_rate_limit)
    
    # 启动组件
    scheduler.start()
    storage_manager.start_writer()
    
    try:
        # 合并 --interface 和 --update-interface 参数
        interfaces_to_update = None
        if hasattr(args, 'update_interfaces') and args.update_interfaces:
            interfaces_to_update = args.update_interfaces.copy()
        if hasattr(args, 'interface') and args.interface:
            if interfaces_to_update is None:
                interfaces_to_update = [args.interface]
            else:
                interfaces_to_update.append(args.interface)

        # 如果没有指定接口，则使用所有可用接口
        if not interfaces_to_update:
            available_interfaces = config_loader.get_available_interfaces()
            interfaces_to_update = available_interfaces
            logger.info(f"No interfaces specified, updating all {len(interfaces_to_update)} available interfaces")

        logger.info(f"Interfaces to update: {interfaces_to_update}")

        # 统计结果
        success_count = 0
        failed_count = 0
        skipped_count = 0

        # 使用核心下载逻辑处理每个接口
        for interface_name in interfaces_to_update:
            try:
                logger.info(f"\n{'='*60}")
                logger.info(f"Processing interface: {interface_name}")
                logger.info(f"{'='*60}")

                # 获取接口配置
                try:
                    interface_config = config_loader.get_interface_config(interface_name)
                except ValueError:
                    logger.error(f"Interface '{interface_name}' not found in configuration, skipping...")
                    failed_count += 1
                    continue

                # 检查积分要求
                min_points = interface_config.get('permissions', {}).get('min_points', 0)
                actual_points = int(os.getenv('TUSHARE_POINTS', '120'))
                if min_points > actual_points:
                    logger.warning(f"Insufficient points for interface {interface_name} (required: {min_points}, available: {actual_points}), skipping...")
                    skipped_count += 1
                    continue

                user_provided_dates = getattr(args, 'user_provided_dates', False)
                if user_provided_dates:
                    start_date, end_date = validate_and_adjust_date(
                        args.start_date,
                        args.end_date
                    )
                else:
                    date_range = date_calculator.calculate_update_range(interface_name)
                    start_date, end_date = date_range.start_date, date_range.end_date

                params = {
                    'start_date': start_date,
                    'end_date': end_date
                }

                # 如果指定了股票代码，添加到参数中
                if args.ts_code:
                    params['ts_code'] = args.ts_code

                # 检查是否使用股票循环模式
                pagination_config = interface_config.get('pagination', {})
                if pagination_config.get('enabled', False) and pagination_config.get('mode') == 'stock_loop':
                    logger.info(f"Using stock_loop mode for {interface_name}")

                    # 检查接口参数配置
                    parameter_config = interface_config.get('parameters', {})
                    has_start_end = 'start_date' in parameter_config and 'end_date' in parameter_config

                    # 检查是否有日期锚定参数
                    date_anchor_param = None
                    for param_name, param_def in parameter_config.items():
                        if param_def.get('is_date_anchor', False):
                            if date_anchor_param:
                                logger.warning(f"Multiple date anchor parameters found for {interface_name}: {date_anchor_param}, {param_name}. Using first: {date_anchor_param}")
                            else:
                                date_anchor_param = param_name

                    if has_start_end:
                        # 场景 1：接口支持 start_date/end_date，直接透传命令行参数
                        params = {
                            'start_date': start_date,
                            'end_date': end_date
                        }
                        if args.ts_code:
                            params['ts_code'] = args.ts_code
                        logger.info(f"Using start_date/end_date for {interface_name}: {start_date} - {end_date}")
                    elif date_anchor_param:
                        # 场景 2：接口使用日期锚定参数
                        # 如果用户未显式提供日期范围且指定了ts_code，则进行“单次全历史”请求（不设置日期锚点）
                        if args.ts_code and not user_provided_dates:
                            params = {'ts_code': args.ts_code}
                            logger.info(f"Fetching full history for {interface_name} (single request by ts_code)")
                        elif interface_name == 'disclosure_date' and not user_provided_dates and not args.ts_code:
                            params = {'_stock_full_history': True}
                            logger.info(f"Fetching full history per stock for {interface_name} (single request per stock)")
                        else:
                            # 传递范围供遍历（按报告期锚点）
                            params = {
                                'start_date': start_date,
                                'end_date': end_date,
                                '_date_anchor_param': date_anchor_param  # 内部标记，用于分页执行器
                            }
                            if args.ts_code:
                                params['ts_code'] = args.ts_code
                            logger.info(f"Using date anchor parameter '{date_anchor_param}' for {interface_name}: {start_date} - {end_date}")
                    else:
                        # 场景 3：没有日期参数，获取全历史
                        params = {}
                        if args.ts_code:
                            params['ts_code'] = args.ts_code
                        logger.info(f"Using stock_loop mode for {interface_name}, fetching full history (no date parameters)")

                    # 使用统一的股票列表准备方法
                    stock_list = _prepare_stock_list(downloader, args, params, storage_manager, logger)
                    if stock_list is None:
                        logger.warning(f"Failed to get stock list for {interface_name}, skipping...")
                        skipped_count += 1
                        continue

                    # 使用并发下载
                    downloaded_count = run_concurrent_stock_download(
                        downloader, scheduler, interface_name, interface_config,
                        params, stock_list, global_rate_limiter, storage_manager, processor, logger
                    )

                    if downloaded_count > 0:
                        logger.info(f"Successfully downloaded {downloaded_count} total records for {interface_name}")
                        success_count += 1
                    else:
                        logger.warning(f"No data downloaded for {interface_name}")
                        skipped_count += 1

                else:
                    # 非 stock_loop 模式，直接使用 downloader.download
                    logger.info(f"Using direct download for {interface_name}")

                    # 清理内部标记参数
                    clean_params = {k: v for k, v in params.items() if not k.startswith('_')}

                    if downloader.coverage_manager and not args.update_force:
                        try:
                            if downloader.coverage_manager.should_skip(
                                interface_name,
                                clean_params,
                                strategy='auto'
                            ):
                                logger.info(f"Skipping {interface_name} (already covered)")
                                skipped_count += 1
                                continue
                        except Exception:
                            pass

                    data = downloader.download(interface_name, clean_params)

                    if data and len(data) > 0:
                        logger.info(f"Successfully downloaded {len(data)} records for {interface_name}")
                        success_count += 1
                    else:
                        logger.warning(f"No data downloaded for {interface_name}")
                        skipped_count += 1

            except Exception as e:
                logger.error(f"Error processing interface {interface_name}: {e}")
                import traceback
                traceback.print_exc()
                failed_count += 1

        # 返回退出码
        if failed_count == 0:
            logger.info(f"\n更新成功完成: {success_count} 成功, {skipped_count} 跳过")
            return 0
        else:
            logger.warning(f"\n更新完成但有失败: {success_count} 成功, {failed_count} 失败, {skipped_count} 跳过")
            return 1
        
        # 返回退出码
        if result.failed_count == 0:
            logger.info(f"更新成功完成: {result.success_count} 成功, {result.skipped_count} 跳过")
            return 0
        else:
            logger.warning(f"更新完成但有失败: {result.success_count} 成功, {result.failed_count} 失败, {result.skipped_count} 跳过")
            return 1
            
    except KeyboardInterrupt:
        logger.warning("\n用户手动中断执行 (Ctrl+C detected)")
        return 130  # 标准的中断退出码
    except Exception as e:
        logger.error(f"更新过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        # 清理资源
        logger.info("正在停止调度器...")
        scheduler.stop()
        
        logger.info("正在刷新并关闭存储写入...")
        storage_manager.stop_writer()
        
        logger.info("资源清理完毕，程序退出。")


def setup_logging(log_config: dict):
    """设置日志配置

    Args:
        log_config: 日志配置字典，包含 level, file, max_size_mb, backup_count
    """
    log_level = log_config.get('level')
    log_file = log_config.get('file')
    max_size_mb = log_config.get('max_size_mb')
    backup_count = log_config.get('backup_count')

    # 确保日志目录存在
    log_dir = os.path.dirname(log_file)
    os.makedirs(log_dir, exist_ok=True)

    # 创建日志格式器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 创建文件处理器（支持轮转）
    from logging.handlers import RotatingFileHandler
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_size_mb * 1024 * 1024,
        backupCount=backup_count,
        encoding='utf-8'
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
    global datetime  # 声明使用全局的datetime变量，避免局部变量冲突
    parser = argparse.ArgumentParser(description="aspipe_v4 融合重构版 - 配置驱动架构")

    # 保持与原版的参数兼容性
    parser.add_argument('--start_date', type=str, default='20230101',
                        help='起始日期 (YYYYMMDD)')
    parser.add_argument('--end_date', type=str, default=None,
                        help='结束日期 (YYYYMMDD)')
    parser.add_argument('--use_legacy', action='store_true',
                        help='传统下载方式 (已移除，保留向后兼容)')
    parser.add_argument('--holders-data', action='store_true',
                        help='下载股东数据')
    parser.add_argument('--pro-bar-only', action='store_true',
                        help='仅下载pro_bar数据')
    parser.add_argument('--tscode-historical', action='store_true',
                        help='全历史数据下载')

    # 新增通用参数
    parser.add_argument('--interface', type=str,
                        help='指定接口名称')
    parser.add_argument('--group', type=str,
                        help='指定接口组名称')
    parser.add_argument('--concurrency', type=int, default=4,  # [修改] 从 8 改为 4
                        help='并发数')
    parser.add_argument('--log-level', type=str, default='INFO',
                        help='日志级别')
    parser.add_argument('--ts_code', type=str,
                        help='指定股票代码 (如: 000001.SZ)')
    parser.add_argument('--force', action='store_true',
                        help='强制覆盖已存在的数据')
    parser.add_argument('--incremental', action='store_true',
                        help='增量模式 - 只下载缺失的时间段')
    
    # 新增增量更新模块参数
    parser.add_argument('--update', 
                        action='store_true',
                        help='启用增量更新模式（推荐）')
    parser.add_argument('--update-interface', 
                        type=str, 
                        action='append',
                        dest='update_interfaces',
                        help='指定要更新的接口（可多次使用）')
    parser.add_argument('--update-group', 
                        type=str, 
                        action='append',
                        dest='update_groups',
                        help='指定要更新的接口组（可多次使用）')
    parser.add_argument('--update-exclude', 
                        type=str, 
                        action='append',
                        dest='update_exclusions',
                        help='排除特定接口（可多次使用）')
    parser.add_argument('--update-force', 
                        action='store_true',
                        dest='update_force',
                        help='强制更新（忽略现有数据）')
    parser.add_argument('--update-dry-run', 
                        action='store_true',
                        dest='update_dry_run',
                        help='预览模式（不实际执行）')
    parser.add_argument('--update-report-format', 
                        type=str,
                        choices=['markdown', 'json', 'html'],
                        default='markdown',
                        dest='update_report_format',
                        help='报告格式')
    parser.add_argument('--update-report-file', 
                        type=str,
                        dest='update_report_file',
                        help='报告输出文件路径')
    
    parser.add_argument('--no-performance-report', action='store_true',
                        help='禁用性能报告生成')
    parser.add_argument('--performance-report-dir', type=str,
                        help='指定性能报告输出目录')

    args = parser.parse_args()
    user_provided_start_date = '--start_date' in sys.argv
    user_provided_end_date = '--end_date' in sys.argv
    user_provided_dates = user_provided_start_date or user_provided_end_date
    setattr(args, 'user_provided_dates', user_provided_dates)
    
    # 处理 --incremental 与 --update 的兼容性
    if args.incremental and not args.update:
        logger = logging.getLogger(__name__)
        logger.warning("--incremental 已弃用，请使用 --update")
        args.update = True
    
    # 如果是更新模式，执行增量更新
    if args.update:
        return run_update_mode(args)

    # 初始化配置加载器（需要在设置日志之前）
    import os
    config_dir_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
    config_loader = ConfigLoader(config_dir=config_dir_path)

    # 验证配置
    if not config_loader.validate_config():
        print("Configuration validation failed")
        return 1

    # 设置日志 - 从 settings.yaml 读取配置
    logging_config = config_loader.global_config.get('logging', {})
    # 如果命令行指定了日志级别，则覆盖配置文件中的设置
    if args.log_level:
        logging_config['level'] = args.log_level
    setup_logging(logging_config)

    logger = logging.getLogger(__name__)
    logger.info("Starting aspipe_v4 App4 - Configuration-driven architecture")

    # 初始化性能监控器配置
    performance_config = config_loader.global_config.get('performance', {})
    performance_enabled = performance_config.get('enabled', True)

    # 初始化其他组件
    scheduler = TaskScheduler(
        max_workers=config_loader.global_config.get('concurrency', {}).get('max_workers', 4),
        max_queue_size=config_loader.global_config.get('concurrency', {}).get('max_queue_size', 1000)
    )

    processor = DataProcessor()
    storage_manager = StorageManager(
        processor=processor,  # 新增参数
        config_loader=config_loader,  # 传递配置加载器
        storage_dir=config_loader.global_config.get('storage', {}).get('base_dir', '../data'),
        format=config_loader.global_config.get('storage', {}).get('format', 'parquet'),
        batch_size=config_loader.global_config.get('storage', {}).get('batch_size', 10000)  # [优化] 增大 batch_size
    )

    # 初始化缓存预热器
    data_dir = config_loader.get_global_config()['storage']['base_dir']
    cache_warmer = CacheWarmer(data_dir)

    # 预热缓存
    logger.info("预热全局缓存...")
    trade_cal_cache = cache_warmer.preload_trade_calendar()
    stock_list_cache = cache_warmer.preload_stock_list()

    # 传递缓存到Downloader
    downloader = GenericDownloader(
        config_loader=config_loader,
        storage_manager=storage_manager,
        trade_calendar_cache=trade_cal_cache,  # 传递交易日历缓存
        stock_list_cache=stock_list_cache,      # 传递股票列表缓存
        force_download=args.force,              # 传递强制下载标志
        incremental_mode=args.incremental       # 传递增量模式标志
    )

    # [修改] 预加载全局交易日历 - 不再依赖 CacheManager
    def preload_global_trade_calendar(downloader, start_date='19900101', end_date=None):
        """预加载全局交易日历，优先从内存缓存读取，然后Data目录，最后API获取"""
        if end_date is None:
            from datetime import datetime
            end_date = datetime.now().strftime('%Y%m%d')

        logger.info(f"Preloading global trade calendar: {start_date} - {end_date}")

        # [修复] 1. 首先检查内存缓存（CacheWarmer 已预加载）
        cache_key = ('global',)
        with downloader._cache_lock:
            if cache_key in downloader._memory_cache['trade_cal']:
                trade_calendar = downloader._memory_cache['trade_cal'][cache_key]
                # 过滤出指定日期范围内的交易日
                trade_days = [day for day in trade_calendar 
                             if start_date <= day.get('cal_date', '') <= end_date and day.get('is_open', 0) == 1]
                if trade_days:
                    logger.info(f"Global trade calendar loaded from memory cache: {len(trade_days)} trade days")
                    return trade_days

        # 2. 检查本地磁盘数据
        trade_calendar = downloader._get_trade_calendar_from_data_dir(start_date, end_date)
        
        if trade_calendar:
             logger.info(f"Global trade calendar loaded from data directory: {len(trade_calendar)} trade days")
             # 手动填充内存缓存
             cache_key = (start_date, end_date)
             with downloader._cache_lock:
                 downloader._memory_cache['trade_cal'][cache_key] = trade_calendar
             return trade_calendar

        # 3. Data目录未命中，请求 API
        logger.info("Global trade calendar not found locally, fetching from API...")
        calendar_params = {
            'start_date': start_date,
            'end_date': end_date,
            'exchange': 'SSE'
        }

        trade_calendar = downloader._make_request(
            downloader.config_loader.get_interface_config('trade_cal'),
            calendar_params
        )

        if trade_calendar:
            # 过滤出交易日
            trade_days = [day for day in trade_calendar if day.get('is_open', 0) == 1]
            trade_days = sorted(trade_days, key=lambda x: x['cal_date'])
            
            # [新增] 保存到存储
            logger.info(f"Saving {len(trade_days)} trade days to storage")
            storage_manager.save_data('trade_cal', trade_calendar, async_write=False)
            
            # [新增] 填充内存缓存
            cache_key = (start_date, end_date)
            with downloader._cache_lock:
                 downloader._memory_cache['trade_cal'][cache_key] = trade_calendar

            logger.info(f"Preloaded {len(trade_days)} trade days from API")
            return trade_days
        else:
            logger.warning("Failed to preload trade calendar")
            return None

    def print_performance_report():
        """打印性能监控报告"""
        print("\n" + "="*30)
        print("      性能监控报告")
        print("="*30)

        # 使用新的性能监控器
        if hasattr(downloader, 'performance_monitor') and downloader.performance_monitor:
            summary = downloader.performance_monitor.get_summary()

            print(f"总运行时间: {time.time() - downloader.performance_monitor.start_time:.2f}秒")
            print(f"总请求数: {len(downloader.performance_monitor.metrics)}")
            print(f"接口数量: {len(summary)}")
            print("-" * 30)

            for interface, stats in summary.items():
                print(f"接口: {interface}")
                print(f"  - 请求次数: {stats['total_requests']}")
                print(f"  - 总记录数: {stats['total_records']}")
                print(f"  - 成功率: {stats['success_rate']:.1f}%")
                print(f"  - 平均请求时间: {stats['avg_duration']:.2f}秒")
                print(f"  - P50/P90/P99: {stats['p50_duration']:.2f}/{stats['p90_duration']:.2f}/{stats['p99_duration']:.2f}秒")
                print(f"  - 平均记录数: {stats['avg_records']:.0f}条")
                print()
        else:
            print("未找到性能监控器")

        print("="*30 + "\n")


    # 预加载全局交易日历
    global_trade_calendar = preload_global_trade_calendar(downloader)

    # 创建全局速率限制器（优先使用接口配置，否则使用全局默认）
    global_rate_limit = config_loader.global_config.get('request', {}).get('rate_limit', 60)
    global_rate_limiter = RateLimiter(global_rate_limit)

    # 启动各组件
    scheduler.start()
    storage_manager.start_writer()

    def process_and_save_data(data, interface_name, interface_config, processor, storage_manager):
        """处理并保存数据的通用函数 - 使用异步处理模式

        Args:
            data: 原始数据列表
            interface_name: 接口名称
            interface_config: 接口配置
            processor: 数据处理器
            storage_manager: 存储管理器

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
        output_config = interface_config.get('output', {})
        primary_keys = output_config.get('primary_key', [])
        dedup_config = interface_config.get('dedup', {'dedup_enabled': True})

        # 如果去重功能启用且存在主键定义
        if dedup_config.get('dedup_enabled', True) and primary_keys:
            # 读取该接口的所有现有数据文件（支持Parquet Dataset模式）
            try:
                existing_df = storage_manager.read_interface_data(interface_name, columns=primary_keys)
            except Exception as e:
                logger.warning(f"无法读取现有数据进行去重: {e}")
                existing_df = pl.DataFrame()

            if not existing_df.is_empty():
                # 使用临时文件进行去重
                import tempfile
                try:
                    with tempfile.NamedTemporaryFile(suffix='.parquet', delete=False) as tmp_file:
                        existing_df.write_parquet(tmp_file.name)
                        temp_path = tmp_file.name

                    # 使用统一的去重模块
                    df, dedup_stats = deduplicate_against_existing(
                        new_data=df,
                        existing_data_path=temp_path,
                        primary_keys=primary_keys
                    )

                    logger.info(f"Deduplication completed for {interface_name}: "
                               f"input={dedup_stats.input_rows}, "
                               f"compared={dedup_stats.compared_rows}, "
                               f"output={dedup_stats.output_rows}, "
                               f"removed={dedup_stats.removed_rows}, "
                               f"dedup_rate={dedup_stats.get_dedup_rate():.2f}%")

                    # 检查去重结果
                    if dedup_stats.errors:
                        for error in dedup_stats.errors:
                            logger.error(f"Deduplication error for {interface_name}: {error}")
                    if dedup_stats.warnings:
                        for warning in dedup_stats.warnings:
                            logger.warning(f"Deduplication warning for {interface_name}: {warning}")

                    # 如果所有数据都被过滤掉了，则直接返回
                    if len(df) == 0:
                        logger.info(f"All records already exist for {interface_name}, skipping save")
                        return df
                finally:
                    if 'temp_path' in locals() and os.path.exists(temp_path):
                        os.unlink(temp_path)
            else:
                logger.info(f"No existing data found for {interface_name}, skipping deduplication")

        logger.info(f"Processed {len(df)} records for {interface_name}")
        if validation_result['duplicate_records'] > 0:
            logger.info(f"Found {validation_result['duplicate_records']} duplicate records for {interface_name}")

        # ✅ 修复：使用异步保存模式，而不是直接调用 _write_interface_data
        # 这样数据会被放入队列，由 _process_worker 线程统一处理
        storage_manager.save_data(interface_name, df.to_dicts(), async_write=True)

        return df

    # [新增] try...finally 结构
    try:
        # 确定要执行的接口
        interfaces_to_run = []

        # 参数映射逻辑（改为累加模式）
        if args.tscode_historical:
            # tscode-historical 模式：使用配置组，获取所有需要股票循环模式的接口
            tscode_historical_group = config_loader.global_config.get('groups', {}).get('tscode_historical', [])
            interfaces_to_run.extend(tscode_historical_group)

        if args.pro_bar_only:
            # pro_bar_only 模式：添加 pro_bar 接口
            interfaces_to_run.append('pro_bar')

        if args.holders_data:
            # holders_data 模式：添加 holders 组
            holders_group = config_loader.global_config.get('groups', {}).get('holders', [])
            interfaces_to_run.extend(holders_group)

        if args.interface:
            # 指定接口
            interfaces_to_run.append(args.interface)

        if args.group:
            # 指定组
            groups = config_loader.global_config.get('groups', {})
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
            tscode_historical_group = config_loader.global_config.get('groups', {}).get('tscode_historical', [])
            interfaces_to_run = [iface for iface in available_interfaces if iface not in tscode_historical_group and iface != 'pro_bar']

        logger.info(f"Interfaces to run: {interfaces_to_run}")

        # 执行下载任务
        for interface_name in interfaces_to_run:
            try:
                # 获取接口配置
                try:
                    interface_config = config_loader.get_interface_config(interface_name)
                except ValueError:
                    logger.error(f"Interface '{interface_name}' not found in configuration, skipping...")
                    continue  # 跳过此接口，继续处理下一个

                # 检查积分要求
                min_points = interface_config.get('permissions', {}).get('min_points', 0)
                actual_points = int(os.getenv('TUSHARE_POINTS', '120'))
                if min_points > actual_points:  # 直接比较实际积分要求
                    logger.warning(f"Insufficient points for interface {interface_name} (required: {min_points}, available: {actual_points})")
                    continue

                # [新增] 检查是否是 tscode_historical 接口
                tscode_historical_group = config_loader.global_config.get('groups', {}).get('tscode_historical', [])
                is_tscode_historical_interface = interface_name in tscode_historical_group

                # [新增] 对于 tscode_historical 接口，如果用户使用默认日期，则改为 1990年1月1日
                if is_tscode_historical_interface and not user_provided_dates and not args.ts_code and interface_name != 'disclosure_date':
                    if args.start_date == '20230101' and args.end_date is None:
                        logger.info(f"Using default date range for tscode_historical interface {interface_name}: 19900101 to today")
                        args.start_date = '19900101'
                        args.end_date = datetime.now().strftime('%Y%m%d')

                # 准备请求参数
                args.start_date, args.end_date = validate_and_adjust_date(
                    args.start_date,
                    args.end_date
                )

                params = {
                    'start_date': args.start_date,
                    'end_date': args.end_date
                }

                # 如果指定了股票代码，添加到参数中
                if args.ts_code:
                    params['ts_code'] = args.ts_code

                # 检查是否使用股票循环模式（根据配置文件中的 pagination.mode）
                pagination_config = interface_config.get('pagination', {})
                if pagination_config.get('enabled', False) and pagination_config.get('mode') == 'stock_loop':
                    logger.info(f"Using stock_loop mode for {interface_name}")
                    
                    # [增强] 检查接口是否支持 start_date/end_date 参数
                    parameter_config = interface_config.get('parameters', {})
                    has_start_end = 'start_date' in parameter_config and 'end_date' in parameter_config
                    
                    # 检查是否有日期锚定参数
                    date_anchor_param = None
                    for param_name, param_def in parameter_config.items():
                        if param_def.get('is_date_anchor', False):
                            if date_anchor_param:
                                logger.warning(f"Multiple date anchor parameters found for {interface_name}: {date_anchor_param}, {param_name}. Using first: {date_anchor_param}")
                            else:
                                date_anchor_param = param_name
                    
                    if has_start_end:
                        # 场景 1：接口支持 start_date/end_date，直接透传命令行参数
                        params = {
                            'start_date': args.start_date,
                            'end_date': args.end_date
                        }
                        if args.ts_code:
                            params['ts_code'] = args.ts_code
                        logger.info(f"Using start_date/end_date for {interface_name}: {args.start_date} - {args.end_date}")
                    elif date_anchor_param:
                        # 场景 2：接口使用日期锚定参数
                        if args.ts_code and not user_provided_dates:
                            params = {'ts_code': args.ts_code}
                            logger.info(f"Fetching full history for {interface_name} (single request by ts_code)")
                        elif interface_name == 'disclosure_date' and not user_provided_dates and not args.ts_code:
                            params = {'_stock_full_history': True}
                            logger.info(f"Fetching full history per stock for {interface_name} (single request per stock)")
                        else:
                            # 传递范围供遍历（按报告期锚点）
                            params = {
                                'start_date': args.start_date,
                                'end_date': args.end_date,
                                '_date_anchor_param': date_anchor_param  # 内部标记，用于分页执行器
                            }
                            if args.ts_code:
                                params['ts_code'] = args.ts_code
                            logger.info(f"Using date anchor parameter '{date_anchor_param}' for {interface_name}: {args.start_date} - {args.end_date}")
                    else:
                        # 原有逻辑：没有日期参数，获取全历史
                        params = {}
                        if args.ts_code:
                            params['ts_code'] = args.ts_code
                        logger.info(f"Using stock_loop mode for {interface_name}, fetching full history (no date parameters)")

                    # 使用统一的股票列表准备方法
                    stock_list = _prepare_stock_list(downloader, args, params, storage_manager, logger)
                    if stock_list is None:
                        logger.warning(f"Failed to get stock list for {interface_name}, skipping...")
                        continue

                    # 使用并发下载
                    downloaded_count = run_concurrent_stock_download(downloader, scheduler, interface_name, interface_config, params, stock_list, global_rate_limiter, storage_manager, processor, logger)

                    if downloaded_count > 0:
                        logger.info(f"Successfully downloaded {downloaded_count} total records for {interface_name}")
                    else:
                        logger.warning(f"No data downloaded for {interface_name}")
                    continue  # 继续处理下一个接口
                else:
                    # 对于pro_bar接口特殊处理
                    if interface_name == 'pro_bar' and args.pro_bar_only:
                        # pro_bar接口：如果用户没有指定日期参数，则不设置任何日期范围，让系统在股票循环中处理每个股票的完整历史
                        if args.start_date == '20230101' and args.end_date is None:
                            # 用户使用默认参数，不设置日期范围，让系统在股票循环中根据每只股票的上市日期自动处理
                            logger.info("Downloading pro_bar full history for all stocks (from each stock's list date)")
                            params = {}  # 清空日期参数，让系统自动处理
                        else:
                            # 用户指定了日期参数，使用用户指定的范围
                            if args.end_date is None:
                                params['end_date'] = datetime.now().strftime('%Y%m%d')
                            logger.info(f"Downloading pro_bar data with date range: {params['start_date']} to {params['end_date']}")

                    # 检查分页模式
                    pagination_config = interface_config.get('pagination', {})
                    pagination_mode = pagination_config.get('mode', 'offset') if pagination_config.get('enabled', False) else 'none'

                    logger.info(f"Downloading data for {interface_name}, pagination mode: {pagination_mode}")
                    # 普通模式，使用同步下载
                    # 特殊接口处理：broker_recommend需要month参数
                    if interface_name == 'broker_recommend':
                        import polars as pl
                        from datetime import datetime
                        # 转换日期范围为月份列表，循环调用
                        start = datetime.strptime(params['start_date'], '%Y%m%d')
                        end = datetime.strptime(params['end_date'], '%Y%m%d')
                        months = pl.date_range(start, end, '1mo', eager=True).dt.strftime('%Y%m').to_list()

                        all_data = []
                        for month in months:
                            month_params = {'month': month}
                            if 'ts_code' in params:
                                month_params['ts_code'] = params['ts_code']
                            data = downloader.download(interface_name, month_params)
                            if data:
                                all_data.extend(data)

                        if all_data:
                            logger.info(f"Successfully downloaded {len(all_data)} records for {interface_name}")
                            process_and_save_data(all_data, interface_name, interface_config, processor, storage_manager)
                        else:
                            logger.warning(f"No data downloaded for {interface_name}")
                        continue  # 跳过普通下载逻辑

                    # 使用接口配置的 rate_limit，如果没有则使用全局默认
                    interface_rate_limit = interface_config.get('permissions', {}).get('rate_limit', global_rate_limit)
                    interface_rate_limiter = RateLimiter(interface_rate_limit)

                    # 等待获取令牌
                    interface_rate_limiter.wait_for_tokens(1)

                    # 下载数据
                    data = downloader.download(interface_name, params)

                    if data:
                        logger.info(f"Successfully downloaded {len(data)} records for {interface_name}")
                        process_and_save_data(data, interface_name, interface_config, processor, storage_manager)
                    else:
                        logger.warning(f"No data downloaded for {interface_name}")

            except Exception as e:
                import traceback
                logger.error(f"Error processing interface {interface_name}: {str(e)}")
                traceback.print_exc()

    except KeyboardInterrupt:
        logger.warning("\n用户手动中断执行 (Ctrl+C detected)")
    except Exception as e:
        logger.error(f"发生未捕获异常: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # [关键] 无论成功、失败还是中断，都执行清理
        logger.info("正在停止调度器...")
        if 'scheduler' in locals(): scheduler.stop()

        logger.info("正在刷新并关闭存储写入...")
        if 'storage_manager' in locals():
            # 先显示缓存统计
            buffer_stats = storage_manager.get_buffer_stats()
            if buffer_stats['total_interfaces'] > 0:
                for iface, stats in buffer_stats['interface_stats'].items():
                    if stats['buffer_count'] > 0:
                        logger.info(f"  - 接口 {iface}: {stats['buffer_count']} 条记录待写入")

            storage_manager.stop_writer()

        # 生成性能报告
        perf_report_enabled = (
            performance_config.get('auto_generate_report', True) and
            not args.no_performance_report
        )

        if perf_report_enabled and performance_enabled:
            print_performance_report()

        # 保存性能报告到文件
        if (perf_report_enabled and performance_enabled and
            'downloader' in locals() and
            hasattr(downloader, 'performance_monitor') and
            downloader.performance_monitor):

            import os
            from datetime import datetime

            # 使用配置的输出目录，或命令行参数覆盖，或默认目录
            report_dir = getattr(args, 'performance_report_dir', None)
            if not report_dir:
                report_dir = performance_config.get('output_dir', 'log/')

            os.makedirs(report_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            filename_prefix = performance_config.get('report_filename_prefix', 'performance_report')
            output_format = performance_config.get('output_format', 'markdown')

            if output_format == 'json':
                performance_file = os.path.join(report_dir, f"{filename_prefix}_{timestamp}.json")
            else:
                performance_file = os.path.join(report_dir, f"{filename_prefix}_{timestamp}.md")

            downloader.performance_monitor.save_report(performance_file)
            logger.info(f"性能报告已生成: {performance_file}")

        logger.info("资源清理完毕，程序退出。")


if __name__ == "__main__":
    sys.exit(main())
