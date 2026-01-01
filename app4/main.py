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
from core.cache_manager import CacheManager
from core.scheduler import TaskScheduler, RateLimiter
from core.storage import StorageManager
from core.processor import DataProcessor


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

    args = parser.parse_args()

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

    # 初始化其他组件
    cache_manager = CacheManager(
        cache_dir=config_loader.global_config.get('cache', {}).get('base_dir', '../cache'),
        default_ttl=config_loader.global_config.get('cache', {}).get('default_ttl', 86400)
    )

    scheduler = TaskScheduler(
        max_workers=config_loader.global_config.get('concurrency', {}).get('max_workers', 4),
        max_queue_size=config_loader.global_config.get('concurrency', {}).get('max_queue_size', 1000)
    )

    storage_manager = StorageManager(
        storage_dir=config_loader.global_config.get('storage', {}).get('base_dir', '../data'),
        format=config_loader.global_config.get('storage', {}).get('format', 'parquet'),
        batch_size=config_loader.global_config.get('storage', {}).get('batch_size', 100)
    )

    processor = DataProcessor()
    downloader = GenericDownloader(config_loader, cache_manager)

    from core.downloader import performance_monitor

    # [新增] 预加载全局交易日历，并优化缓存策略
    def preload_global_trade_calendar(downloader, start_date='19900101', end_date=None):
        """预加载全局交易日历，并预缓存常用子范围以提高命中率"""
        if end_date is None:
            from datetime import datetime
            end_date = datetime.now().strftime('%Y%m%d')

        logger.info(f"Preloading global trade calendar: {start_date} - {end_date}")

        # 使用最广泛的日期范围
        full_range_key = f"calendar_{start_date}_{end_date}"
        # 也可以使用硬编码的固定大范围键，配合 CacheManager 中的逻辑
        full_calendar_key = "calendar_19900101_20251231"
        
        trade_calendar = downloader.cache_manager.get(full_calendar_key)
        if trade_calendar is not None:
            logger.info(f"Global trade calendar already cached: {len(trade_calendar)} trade days")
            return trade_calendar

        # 缓存未命中，请求 API
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
            # 过滤出交易日并缓存
            trade_days = [day for day in trade_calendar if day.get('is_open', 0) == 1]
            trade_days = sorted(trade_days, key=lambda x: x['cal_date'])
            
            # 缓存完整范围
            downloader.cache_manager.set(full_calendar_key, trade_days)
            downloader.cache_manager.set(full_range_key, trade_days)

            # 预缓存一些常见的子范围以提高后续请求的命中率
            common_sub_ranges = [
                ('20050101', '20251231'),
                ('20100101', '20251231'),
                ('20150101', '20251231'),
                ('20200101', '20251231'),
            ]

            for sub_start, sub_end in common_sub_ranges:
                if sub_start >= start_date and sub_end <= end_date:
                    sub_calendar = [
                        day for day in trade_days
                        if sub_start <= day['cal_date'] <= sub_end
                    ]
                    if sub_calendar:
                        sub_key = f"calendar_{sub_start}_{sub_end}"
                        downloader.cache_manager.set(sub_key, sub_calendar)
                        logger.debug(f"Pre-cached common range {sub_start}-{sub_end}")

            logger.info(f"Preloaded {len(trade_days)} trade days with enhanced caching")
            return trade_days
        else:
            logger.warning("Failed to preload trade calendar")
            return None

    def print_performance_report():
        """打印性能监控报告"""
        print("\n" + "="*30)
        print("      性能监控报告")
        print("="*30)
        
        avg_request_time = performance_monitor.get_average_metric('request_time')
        avg_data_size = performance_monitor.get_average_metric('data_size')
        avg_retry_count = performance_monitor.get_average_metric('retry_count')

        print(f"平均请求时间: {avg_request_time:.2f}s")
        print(f"平均单窗口条数: {avg_data_size:.2f} 条")
        print(f"平均重试次数: {avg_retry_count:.2f} 次")

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

    # 启动各组件
    scheduler.start()
    storage_manager.start_writer()

    def process_and_save_data(data, interface_name, interface_config, processor, storage_manager):
        """处理并保存数据的通用函数

        Args:
            data: 原始数据列表
            interface_name: 接口名称
            interface_config: 接口配置
            processor: 数据处理器
            storage_manager: 存储管理器

        Returns:
            处理后的 DataFrame，如果处理失败则返回 None
        """
        if not data:
            logger.warning(f"No data to process for {interface_name}")
            return None

        # 处理数据
        df = processor.process_data(data, interface_config)
        validation_result = processor.validate_data(df, interface_config)

        # 保存数据
        storage_manager.save_data(interface_name, df.to_dict('records'), async_write=True)

        logger.info(f"Saved {len(df)} processed records for {interface_name}")
        if validation_result['duplicate_records'] > 0:
            logger.info(f"Found {validation_result['duplicate_records']} duplicate records for {interface_name}")

        return df

    def run_concurrent_stock_download(downloader, scheduler, interface_name, interface_config, base_params, stock_list, rate_limiter):
        """运行并发股票下载"""
        logger.info(f"Starting concurrent download for {interface_name} with {len(stock_list)} stocks")

        # 创建包装函数，包含限流逻辑
        def download_single_stock_with_rate_limit(interface_config, stock, params):
            # 在工作线程中等待令牌
            rate_limiter.wait_for_tokens(1)
            return downloader.download_single_stock(interface_config, stock, params)

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
                all_data = []
                for result in results:
                    if result:
                        all_data.extend(result)

                logger.info(f"Completed batch, got {len(all_data)} records")
                tasks = []

        # 提交剩余任务
        if tasks:
            logger.info(f"Submitting final batch of {len(tasks)} tasks")
            results = scheduler.submit_tasks(tasks)

            all_data = []
            for result in results:
                if result:
                    all_data.extend(result)

            logger.info(f"Completed final batch, got {len(all_data)} records")
            return all_data

        return []

    # [新增] try...finally 结构
    try:
        # 确定要执行的接口
        interfaces_to_run = []

        # 参数映射逻辑（改为累加模式）
        if args.tscode_historical:
            # tscode-historical 模式：只下载那4个需要 ts_code 的接口
            interfaces_to_run.extend(['stk_rewards', 'top10_holders', 'pledge_detail', 'fina_audit'])

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
            interfaces_to_run = [iface for iface in available_interfaces if iface not in ['stk_rewards', 'top10_holders', 'pledge_detail', 'fina_audit', 'pro_bar']]

        logger.info(f"Interfaces to run: {interfaces_to_run}")

        # 执行下载任务
        for interface_name in interfaces_to_run:
            try:
                # 获取接口配置
                interface_config = config_loader.get_interface_config(interface_name)

                # 检查积分要求
                min_points = interface_config.get('permissions', {}).get('min_points', 0)
                if min_points > 5000:  # 这里应该从环境变量中读取实际积分
                    import os
                    actual_points = int(os.getenv('tushare_points', '120'))
                    if min_points > actual_points:
                        logger.warning(f"Insufficient points for interface {interface_name} (required: {min_points}, available: {actual_points})")
                        continue

                # 准备请求参数
                params = {
                    'start_date': args.start_date,
                    'end_date': args.end_date or datetime.now().strftime('%Y%m%d')
                }

                # 如果指定了股票代码，添加到参数中
                if args.ts_code:
                    params['ts_code'] = args.ts_code

                # 对于需要ts_code的接口，根据下载模式处理
                if args.tscode_historical and 'ts_code' in interface_config.get('parameters', {}):
                    logger.info(f"Running historical download for {interface_name}")
                    # 这里可以实现获取股票列表并逐个下载的逻辑
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

                        # 获取股票列表
                        stock_list = cache_manager.get_stock_list()
                        if stock_list is None:
                            logger.info("缓存中未找到股票列表，正在从API获取...")
                            stock_params = {'list_status': 'L'}
                            stock_list = downloader.download('stock_basic', stock_params)
                            if stock_list:
                                logger.info(f"从API获取到 {len(stock_list)} 只股票")
                                cache_manager.set_stock_list(stock_list)
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
                        all_data = run_concurrent_stock_download(downloader, scheduler, interface_name, interface_config, params, stock_list, global_rate_limiter)

                        if all_data:
                            logger.info(f"Successfully downloaded {len(all_data)} total records for {interface_name}")
                            process_and_save_data(all_data, interface_name, interface_config, processor, storage_manager)
                        else:
                            logger.warning(f"No data downloaded for {interface_name}")
                    else:
                        # 普通模式，使用同步下载
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
                logger.error(f"Error processing interface {interface_name}: {str(e)}")

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