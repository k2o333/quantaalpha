#!/usr/bin/env python3
"""
aspipe_v4 融合重构版 (App4) - 配置驱动架构
统一CLI入口，保持与原版的参数兼容性
"""
import argparse
import logging
import os
import sys
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
import polars as pl


def validate_and_adjust_date(start_date, end_date):
    """
    验证并调整日期，确保不使用未来日期
    """
    from datetime import datetime
    today = datetime.now().strftime('%Y%m%d')

    if end_date > today:
        print(f"警告: 结束日期 {end_date} 超过当前日期，已调整为 {today}")
        end_date = today

    if start_date > today:
        print(f"警告: 开始日期 {start_date} 超过当前日期，已调整为 {today}")
        start_date = today

    return start_date, end_date


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
    # [新增] 添加移除历史标记的命令行选项
    parser.add_argument('--remove-historical-markers', action='store_true',
                        help='移除所有历史下载标记文件')

    args = parser.parse_args()

    # 初始化配置加载器（需要在设置日志之前）
    import os
    config_dir_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
    config_loader = ConfigLoader(config_dir=config_dir_path)

    # [新增] 如果指定了移除历史标记选项，执行移除并退出
    if args.remove_historical_markers:
        # 临时创建必要的组件
        storage_manager = StorageManager(
            storage_dir=config_loader.global_config.get('storage', {}).get('base_dir', '../data'),
            format=config_loader.global_config.get('storage', {}).get('format', 'parquet'),
            batch_size=config_loader.global_config.get('storage', {}).get('batch_size', 10000)
        )
        from core.coverage_manager import CoverageManager
        coverage_manager = CoverageManager(storage_manager, config_loader, None)  # 使用最小化的组件
        if coverage_manager.remove_all_historical_download_markers():
            print("已成功移除所有历史下载标记文件")
        else:
            print("未找到历史下载标记文件")
        storage_manager.stop_writer()
        return 0

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

    # 初始化其他组件
    scheduler = TaskScheduler(
        max_workers=config_loader.global_config.get('concurrency', {}).get('max_workers', 4),
        max_queue_size=config_loader.global_config.get('concurrency', {}).get('max_queue_size', 1000)
    )

    storage_manager = StorageManager(
        storage_dir=config_loader.global_config.get('storage', {}).get('base_dir', '../data'),
        format=config_loader.global_config.get('storage', {}).get('format', 'parquet'),
        batch_size=config_loader.global_config.get('storage', {}).get('batch_size', 10000)  # [优化] 增大 batch_size
    )

    processor = DataProcessor()
    downloader = GenericDownloader(config_loader, storage_manager)

    from core.downloader import performance_monitor

    # [修改] 预加载全局交易日历 - 不再依赖 CacheManager
    def preload_global_trade_calendar(downloader, start_date='19900101', end_date=None):
        """预加载全局交易日历，优先从Data目录读取，然后从API获取"""
        if end_date is None:
            from datetime import datetime
            end_date = datetime.now().strftime('%Y%m%d')

        logger.info(f"Preloading global trade calendar: {start_date} - {end_date}")

        # 使用 downloader.get_trade_calendar 统一方法
        # 这会自动处理 Mem -> Disk -> API 的回退，并且如果从Disk读取会自动更新Mem
        # 但我们需要确保如果从API获取，也会保存到Disk
        
        # 1. 尝试通过标准路径获取（Mem -> Disk -> API）
        # 这里直接调用 downloader.get_trade_calendar 会自动处理大部分逻辑
        # 但 downloader 的 save 逻辑可能还没完善，所以我们手动处理一下以确保万无一失
        
        # 检查本地是否有数据
        trade_calendar = downloader._get_trade_calendar_from_data_dir(start_date, end_date)
        
        if trade_calendar:
             logger.info(f"Global trade calendar loaded from data directory: {len(trade_calendar)} trade days")
             # 手动填充内存缓存
             cache_key = (start_date, end_date)
             with downloader._cache_lock:
                 downloader._memory_cache['trade_cal'][cache_key] = trade_calendar
             return trade_calendar

        # Data目录未命中，请求 API
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
        
        # 添加调试信息
        import sys
        print(f"Debug: performance_monitor id: {id(performance_monitor)}", file=sys.stderr)
        
        avg_request_time = performance_monitor.get_average_metric('request_time')
        avg_data_size = performance_monitor.get_average_metric('data_size')
        avg_retry_count = performance_monitor.get_average_metric('retry_count')

        print(f"平均请求时间: {avg_request_time:.2f}s")
        print(f"平均单窗口条数: {avg_data_size:.2f} 条")
        print(f"平均重试次数: {avg_retry_count:.2f} 次")
        
        # 打印更详细的指标信息
        print(f"Debug: request_time指标数量: {len(performance_monitor._metrics['request_time']) if 'request_time' in performance_monitor._metrics else 0}", file=sys.stderr)
        print(f"Debug: data_size指标数量: {len(performance_monitor._metrics['data_size']) if 'data_size' in performance_monitor._metrics else 0}", file=sys.stderr)

        if avg_request_time > 30:
            print("⚠️ 警告: 平均请求时间过长")
        if avg_retry_count > 0.5:
            print("⚠️ 警告: 重试频率较高，请检查 API 限制或网络状况")
        if avg_data_size >= 5800:
            print("⚠️ 警告: 数据量接近 API 限制，建议减小窗口大小")
        print("="*30 + "\n")


    # 预加载全局交易日历
    global_trade_calendar = preload_global_trade_calendar(downloader)

    # 创建全局速率限制器（优先使用接口配置，否则使用全局默认）
    global_rate_limit = config_loader.global_config.get('request', {}).get('rate_limit', 60)
    global_rate_limiter = RateLimiter(global_rate_limit)

    # [新增] 在启动下载前移除所有历史下载标记文件
    from core.coverage_manager import CoverageManager
    coverage_manager = CoverageManager(storage_manager, config_loader, downloader)  # 使用现有的组件
    coverage_manager.remove_all_historical_download_markers()

    # 启动各组件
    scheduler.start()
    storage_manager.start_writer()

    def process_and_save_data(data, interface_name, interface_config, processor, storage_manager):
        """处理并保存数据的通用函数 - 重构后"""
        if not data:
            logger.warning(f"No data to process for {interface_name}")
            return None

        # 处理数据
        df = processor.process_data(data, interface_config)
        validation_result = processor.validate_data(df, interface_config)

        # 从接口配置获取去重配置
        dedup_config = interface_config.get('dedup', {})

        # 保存数据（内部处理去重逻辑）
        storage_manager.save_data_with_dedup(interface_name, df.to_dicts(), dedup_config, async_write=True)

        logger.info(f"Saved {len(df)} processed records for {interface_name}")
        if validation_result['duplicate_records'] > 0:
            logger.info(f"Found {validation_result['duplicate_records']} duplicate records for {interface_name}")

        return df

    def run_concurrent_stock_download(downloader, scheduler, interface_name, interface_config, base_params, stock_list, rate_limiter, storage_manager, processor):
        """运行并发股票下载 - 优化批处理"""
        logger.info(f"Starting concurrent download for {interface_name} with {len(stock_list)} stocks")

        # 创建包装函数，包含限流逻辑
        def download_single_stock_with_rate_limit(interface_config, stock, params):
            # 在工作线程中等待令牌
            rate_limiter.wait_for_tokens(1)
            return downloader.download_single_stock(interface_config, stock, params)

        # [优化] 增大 batch_size 避免小文件爆炸
        batch_size = 10000
        all_data = []

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

                # 收集结果
                for result in results:
                    if result:
                        all_data.extend(result)

                logger.info(f"Completed batch, got {len(all_data)} records")

                # [优化] 每 batch_size 条数据处理一次
                if len(all_data) >= batch_size:
                    process_and_save_data(all_data, interface_name, interface_config, processor, storage_manager)
                    all_data = []

                tasks = []

        # 提交剩余任务
        if tasks:
            logger.info(f"Submitting final batch of {len(tasks)} tasks")
            results = scheduler.submit_tasks(tasks)

            for result in results:
                if result:
                    all_data.extend(result)

            logger.info(f"Completed final batch, got {len(all_data)} records")

        # 处理剩余数据
        if all_data:
            process_and_save_data(all_data, interface_name, interface_config, processor, storage_manager)

        return all_data

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
                interface_config = config_loader.get_interface_config(interface_name)

                # 检查积分要求
                min_points = interface_config.get('permissions', {}).get('min_points', 0)
                actual_points = int(os.getenv('tushare_points', '120'))
                if min_points > actual_points:  # 直接比较实际积分要求
                    logger.warning(f"Insufficient points for interface {interface_name} (required: {min_points}, available: {actual_points})")
                    continue

                # [新增] 检查是否是 tscode_historical 接口
                tscode_historical_group = config_loader.global_config.get('groups', {}).get('tscode_historical', [])
                is_tscode_historical_interface = interface_name in tscode_historical_group

                # [新增] 对于 tscode_historical 接口，如果用户使用默认日期，则改为 1990年1月1日
                if is_tscode_historical_interface:
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
                        else:
                            logger.warning("未能从API获取股票列表")
                            continue

                    # 如果参数中指定了股票代码，则只下载该股票
                    if 'ts_code' in params:
                        target_code = params['ts_code']
                        stock_list = [stock for stock in stock_list if stock['ts_code'] == target_code]
                        logger.info(f"Filtered to specific stock: {target_code}, {len(stock_list)} stocks remaining")

                    # 使用并发下载
                    all_data = run_concurrent_stock_download(downloader, scheduler, interface_name, interface_config, params, stock_list, global_rate_limiter, storage_manager, processor)

                    if all_data:
                        logger.info(f"Successfully downloaded {len(all_data)} total records for {interface_name}")
                        process_and_save_data(all_data, interface_name, interface_config, processor, storage_manager)
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

                    # 如果是股票循环模式，使用并发下载
                    if pagination_mode == 'stock_loop':
                        logger.info(f"Using concurrent download for stock_loop mode")

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
                            else:
                                logger.warning("未能从API获取股票列表")
                                continue

                        # 为测试目的，可以限制股票数量
                        # 如果参数中指定了股票代码，则只下载该股票
                        if 'ts_code' in params:
                            target_code = params['ts_code']
                            stock_list = [stock for stock in stock_list if stock['ts_code'] == target_code]
                            logger.info(f"Filtered to specific stock: {target_code}, {len(stock_list)} stocks remaining")

                        # 使用并发下载
                        all_data = run_concurrent_stock_download(downloader, scheduler, interface_name, interface_config, params, stock_list, global_rate_limiter, storage_manager, processor)

                        if all_data:
                            logger.info(f"Successfully downloaded {len(all_data)} total records for {interface_name}")
                            process_and_save_data(all_data, interface_name, interface_config, processor, storage_manager)
                        else:
                            logger.warning(f"No data downloaded for {interface_name}")
                    else:
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

        logger.info("正在关闭存储写入...")
        if 'storage_manager' in locals(): storage_manager.stop_writer()

        # 打印性能报告
        if 'print_performance_report' in locals():
            print_performance_report()

        logger.info("资源清理完毕，程序退出。")


if __name__ == "__main__":
    sys.exit(main())