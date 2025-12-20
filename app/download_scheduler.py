"""
完整下载调度器
整合所有组件，实现生产者-消费者模式和任务调度
"""
import threading
import time
import logging
import queue
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
import pandas as pd

from tushare_api import TuShareDownloader
# Import inside the functions to avoid circular import issues
from config_adapter import get_all_available_interfaces, get_interface_strategy, get_interface_concurrency, get_interface_priority
from task_queue_manager import DownloadTaskQueueManager, TaskPriority, TaskStatus
from storage_worker import StorageWorker, submit_data_to_storage
from global_rate_limiter import acquire_tokens
from parallel_downloader import ParallelDownloader
from data_storage import save_to_parquet


class DownloadScheduler:
    """
    完整下载调度器，整合所有下载优化功能
    """

    def __init__(self, start_date: str, end_date: str, max_workers: int = 4):
        """
        初始化下载调度器

        Args:
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)
            max_workers: 最大工作线程数
        """
        self.start_date = start_date
        self.end_date = end_date
        self.max_workers = max_workers
        self.downloader = TuShareDownloader()
        self.parallel_downloader = ParallelDownloader(max_workers=max_workers)
        self.task_manager = DownloadTaskQueueManager()
        self.storage_worker = StorageWorker(max_workers=2)
        self.logger = logging.getLogger(__name__)

        # 交易日缓存
        self._trading_days_cache = None
        self._trading_days_lock = threading.Lock()

        # 调度器状态
        self.is_running = False
        self.shutdown_event = threading.Event()
        self.main_thread = None

        # 统计信息
        self.stats = {
            'total_downloaded': 0,
            'total_stored': 0,
            'start_time': time.time(),
            'active_downloads': 0,
            'active_storages': 0
        }
        self.stats_lock = threading.Lock()

    def get_available_interfaces(self) -> Dict[str, Any]:
        """
        获取当前用户可用的所有接口
        """
        return get_all_available_interfaces()

    def _get_trading_days(self) -> List[str]:
        """
        获取指定日期范围内的交易日 (带缓存)
        """
        # 检查缓存
        with self._trading_days_lock:
            if self._trading_days_cache is not None:
                return self._trading_days_cache

        try:
            # 先下载交易日历数据
            trade_cal = self.downloader.download_trade_cal(
                exchange='SSE',  # 默认上交所
                start_date=self.start_date,
                end_date=self.end_date
            )

            # 过滤出交易日（is_open=1）
            if not trade_cal.empty:
                trading_days = trade_cal[trade_cal['is_open'] == 1]['cal_date'].tolist()
                trading_days.sort()
            else:
                trading_days = []

            self.logger.info(f"获取到 {len(trading_days)} 个交易日")

            # 缓存结果
            with self._trading_days_lock:
                self._trading_days_cache = trading_days

            return trading_days

        except Exception as e:
            self.logger.error(f"获取交易日历失败: {e}")
            # 如果无法获取交易日历，返回日期范围内的所有日期作为备选
            fallback_days = self._generate_date_range()
            # 缓存备选结果
            with self._trading_days_lock:
                self._trading_days_cache = fallback_days
            return fallback_days

    def _generate_date_range(self) -> List[str]:
        """
        生成日期范围内的所有日期（作为备选方案）
        """
        start = datetime.strptime(self.start_date, '%Y%m%d')
        end = datetime.strptime(self.end_date, '%Y%m%d')

        date_list = []
        current = start
        while current <= end:
            date_list.append(current.strftime('%Y%m%d'))
            current += timedelta(days=1)

        return date_list

    def schedule_download_tasks(self, interfaces: List[str] = None) -> List[str]:
        """
        为指定接口调度下载任务

        Args:
            interfaces: 要下载的接口列表，如果为None则下载所有可用接口

        Returns:
            任务ID列表
        """
        if interfaces is None:
            available_interfaces = get_all_available_interfaces()
            interfaces = list(available_interfaces.keys())

        task_ids = []

        for interface_name in interfaces:
            # 获取接口策略和优先级
            from config_adapter import get_interface_priority as get_config_priority
            priority = get_config_priority(interface_name)

            # 根据接口类型选择合适的调度策略
            if interface_name in ['daily', 'daily_basic', 'moneyflow', 'moneyflow_dc', 'moneyflow_ths',
                                 'moneyflow_ind_dc', 'moneyflow_mkt_dc', 'moneyflow_cnt_ths',
                                 'moneyflow_ind_ths', 'stk_factor', 'stk_factor_pro', 'cyq_perf', 'cyq_chips']:
                # 日度数据接口，按日期分批调度
                task_id = self._schedule_daily_interface(interface_name, priority)
            elif interface_name in ['income', 'balancesheet', 'cashflow', 'fina_indicator',
                                   'dividend', 'forecast', 'express', 'top10_holders',
                                   'top10_floatholders', 'stk_surv']:
                # 财务数据接口，按报告期调度
                task_id = self._schedule_financial_interface(interface_name, priority)
            elif interface_name in ['stock_basic', 'trade_cal', 'new_share', 'stock_company',
                                   'stock_st', 'bak_basic', 'namechange', 'stk_rewards',
                                   'stk_managers', 'broker_recommend']:
                # 静态数据接口，单次调度
                task_id = self._schedule_static_interface(interface_name, priority)
            else:
                # 未知类型接口，按日度数据处理
                task_id = self._schedule_daily_interface(interface_name, priority)

            if task_id:
                task_ids.append(task_id)

        self.logger.info(f"调度了 {len(task_ids)} 个下载任务")
        return task_ids

    def _schedule_daily_interface(self, interface_name: str, priority: TaskPriority) -> str:
        """
        调度日度数据接口下载任务
        """
        # 获取交易日列表
        trading_days = self._get_trading_days()

        # 将交易日列表分批，每批处理一段时间范围
        batch_size = 30  # 每批处理30个交易日
        task_ids = []

        for i in range(0, len(trading_days), batch_size):
            batch_days = trading_days[i:i + batch_size]
            batch_start = batch_days[0]
            batch_end = batch_days[-1]

            # 创建任务参数
            task_params = {
                'interface_name': interface_name,
                'start_date': batch_start,
                'end_date': batch_end,
                'trading_days': batch_days
            }

            # 提交任务
            task_id = self.task_manager.add_task(
                task_type='download',
                target_func=self._execute_daily_download,
                priority=priority,
                kwargs=task_params,
                max_retries=3,
                metadata={
                    'interface': interface_name,
                    'date_range': f"{batch_start} to {batch_end}"
                }
            )
            if task_id:
                task_ids.append(task_id)

        # 对于有多个批次的接口，创建一个聚合任务ID
        if len(task_ids) == 1:
            return task_ids[0]
        elif len(task_ids) > 1:
            # 返回第一个任务ID作为代表
            return task_ids[0]
        else:
            return None

    def _execute_daily_download(self, **kwargs) -> pd.DataFrame:
        """
        执行日度数据下载
        """
        interface_name = kwargs.get('interface_name')
        start_date = kwargs.get('start_date')
        end_date = kwargs.get('end_date')
        trading_days = kwargs.get('trading_days', [])

        self.logger.info(f"开始下载日度数据: {interface_name}, 日期范围: {start_date} - {end_date}")

        try:
            # 获取下载策略（延迟导入避免循环依赖）
            from download_strategies import get_strategy
            strategy = get_strategy(interface_name, downloader=self.downloader)

            # 申请速率限制令牌
            if not acquire_tokens(interface_name, 1.0, timeout=300):
                raise Exception(f"无法获取 {interface_name} 的速率限制令牌")

            # 根据接口类型执行不同的下载逻辑
            if interface_name in ['daily', 'daily_basic', 'moneyflow']:
                # 对于支持日期范围的接口，直接下载
                if interface_name == 'daily':
                    result = strategy.download(start_date=start_date, end_date=end_date)
                elif interface_name == 'daily_basic':
                    # daily_basic 按单日下载并合并
                    all_data = []
                    for trade_date in trading_days:
                        day_result = strategy.download(trade_date=trade_date)
                        if not day_result.empty:
                            all_data.append(day_result)
                        # 应用速率限制
                        time.sleep(0.5)
                    result = pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()
                elif interface_name == 'moneyflow':
                    result = strategy.download(start_date=start_date, end_date=end_date)
                else:
                    result = strategy.download(start_date=start_date, end_date=end_date)
            else:
                # 对于其他接口，根据支持的参数类型下载
                result = strategy.download(start_date=start_date, end_date=end_date)

            with self.stats_lock:
                self.stats['total_downloaded'] += len(result) if result is not None else 0

            self.logger.info(f"完成下载 {interface_name}，获得 {len(result) if result is not None else 0} 条记录")

            # 提交存储任务
            if result is not None and not result.empty:
                filename = f"{interface_name}_{start_date}_{end_date}"
                subdir = f"daily/{start_date[:4]}/{start_date[4:6]}"

                self.task_manager.add_storage_task(
                    data=result,
                    filename=filename,
                    subdir=subdir,
                    priority=TaskPriority.MEDIUM
                )

            return result

        except Exception as e:
            self.logger.error(f"下载日度数据 {interface_name} 失败: {e}")
            raise

    def _schedule_financial_interface(self, interface_name: str, priority: TaskPriority) -> str:
        """
        调度财务数据接口下载任务
        """
        # 获取财务报告期
        periods = self._get_financial_periods()

        # 为每个报告期创建下载任务
        task_ids = []
        for period in periods:
            task_params = {
                'interface_name': interface_name,
                'period': period
            }

            task_id = self.task_manager.add_task(
                task_type='download',
                target_func=self._execute_financial_download,
                priority=priority,
                kwargs=task_params,
                max_retries=3,
                metadata={
                    'interface': interface_name,
                    'period': period
                }
            )
            if task_id:
                task_ids.append(task_id)

        if task_ids:
            return task_ids[0]
        return None

    def _execute_financial_download(self, **kwargs) -> pd.DataFrame:
        """
        执行财务数据下载
        """
        interface_name = kwargs.get('interface_name')
        period = kwargs.get('period')

        self.logger.info(f"开始下载财务数据: {interface_name}, 报告期: {period}")

        try:
            # 获取下载策略（延迟导入避免循环依赖）
            from download_strategies import get_strategy
            strategy = get_strategy(interface_name, downloader=self.downloader)

            # 申请速率限制令牌
            if not acquire_tokens(interface_name, 1.0, timeout=300):
                raise Exception(f"无法获取 {interface_name} 的速率限制令牌")

            # 执行下载
            result = strategy.download(period=period)

            with self.stats_lock:
                self.stats['total_downloaded'] += len(result) if result is not None else 0

            self.logger.info(f"完成下载 {interface_name}，获得 {len(result) if result is not None else 0} 条记录")

            # 提交存储任务
            if result is not None and not result.empty:
                filename = f"{interface_name}_{period}"
                subdir = f"financial/{period[:4]}"

                self.task_manager.add_storage_task(
                    data=result,
                    filename=filename,
                    subdir=subdir,
                    priority=TaskPriority.MEDIUM
                )

            return result

        except Exception as e:
            self.logger.error(f"下载财务数据 {interface_name} 失败: {e}")
            raise

    def _schedule_static_interface(self, interface_name: str, priority: TaskPriority) -> str:
        """
        调度静态数据接口下载任务
        """
        task_params = {
            'interface_name': interface_name
        }

        task_id = self.task_manager.add_task(
            task_type='download',
            target_func=self._execute_static_download,
            priority=priority,
            kwargs=task_params,
            max_retries=3,
            metadata={
                'interface': interface_name
            }
        )
        return task_id

    def _execute_static_download(self, **kwargs) -> pd.DataFrame:
        """
        执行静态数据下载
        """
        interface_name = kwargs.get('interface_name')

        self.logger.info(f"开始下载静态数据: {interface_name}")

        try:
            # 获取下载策略（延迟导入避免循环依赖）
            from download_strategies import get_strategy
            strategy = get_strategy(interface_name, downloader=self.downloader)

            # 申请速率限制令牌
            if not acquire_tokens(interface_name, 1.0, timeout=300):
                raise Exception(f"无法获取 {interface_name} 的速率限制令牌")

            # 执行下载
            result = strategy.download()

            with self.stats_lock:
                self.stats['total_downloaded'] += len(result) if result is not None else 0

            self.logger.info(f"完成下载 {interface_name}，获得 {len(result) if result is not None else 0} 条记录")

            # 提交存储任务
            if result is not None and not result.empty:
                filename = f"{interface_name}_{self.start_date}_{self.end_date}"
                subdir = f"static"

                self.task_manager.add_storage_task(
                    data=result,
                    filename=filename,
                    subdir=subdir,
                    priority=TaskPriority.LOW
                )

            return result

        except Exception as e:
            self.logger.error(f"下载静态数据 {interface_name} 失败: {e}")
            raise

    def _get_financial_periods(self) -> List[str]:
        """
        获取日期范围内的财务报告期
        """
        start_year = int(self.start_date[:4])
        end_year = int(self.end_date[:4])

        periods = []
        for year in range(start_year, end_year + 1):
            periods.extend([
                f"{year}0331",  # Q1
                f"{year}0630",  # Q2
                f"{year}0930",  # Q3
                f"{year}1231"   # Q4
            ])

        # 过滤掉早于开始日期的报告期（财务报告期通常在季度结束后一段时间发布）
        filtered_periods = []
        for period in periods:
            # 简单判断：报告期月份的下一个月份
            report_year = int(period[:4])
            report_month = int(period[4:6])

            # 近似：季报在季度结束后的1-2个月内发布
            if report_year > start_year or (report_year == start_year and report_month >= int(self.start_date[4:6]) - 2):
                if report_year < end_year or (report_year == end_year and report_month <= int(self.end_date[4:6]) + 2):
                    filtered_periods.append(period)

        return filtered_periods

    def execute_scheduled_tasks(self, wait_for_completion: bool = True) -> Dict[str, Any]:
        """
        执行所有已调度的任务
        """
        if self.is_running:
            self.logger.warning("调度器已在运行中")
            return self.get_stats()

        self.logger.info(f"开始执行下载调度，日期范围: {self.start_date} - {self.end_date}")
        self.is_running = True
        self.main_thread = threading.current_thread()

        # 启动任务消费者线程
        consumer_threads = []
        for i in range(self.max_workers):
            consumer_thread = threading.Thread(
                target=self._task_consumer_loop,
                name=f"TaskConsumer-{i}",
                daemon=True
            )
            consumer_thread.start()
            consumer_threads.append(consumer_thread)

        # 启动监控线程
        monitor_thread = threading.Thread(target=self._monitor_progress, daemon=True)
        monitor_thread.start()

        try:
            if wait_for_completion:
                # 等待所有任务完成
                self.task_manager.wait_for_all_tasks()
                self.storage_worker.wait_for_completion()
            else:
                # 不等待，立即返回
                pass

            self.logger.info("下载调度完成")
            return self.get_stats()

        except KeyboardInterrupt:
            self.logger.info("接收到中断信号，正在关闭调度器...")
            self.shutdown()
        except Exception as e:
            self.logger.error(f"执行下载调度时出错: {e}")
            raise
        finally:
            self.is_running = False

    def _monitor_progress(self):
        """
        监控下载进度的后台线程
        """
        while self.is_running and not self.shutdown_event.is_set():
            stats = self.task_manager.get_stats()
            self.logger.info(
                f"任务监控 - 总任务: {stats['total_tasks']}, "
                f"已完成: {stats['completed_tasks']}, "
                f"失败: {stats['failed_tasks']}, "
                f"队列大小: {stats['queue_size']}"
            )
            time.sleep(30)  # 每30秒报告一次

    def _task_consumer_loop(self):
        """
        任务消费者循环 - 从队列中获取并执行任务
        """
        while self.is_running and not self.shutdown_event.is_set():
            try:
                # 从任务队列获取任务
                task = self.task_manager.get_next_task(timeout=1.0)

                if task is None:
                    # 无任务可执行，继续循环
                    continue

                try:
                    # 更新任务状态为处理中
                    task.status = TaskStatus.PROCESSING
                    task.started_at = datetime.now()

                    # 执行任务
                    self.logger.info(f"开始执行任务: {task.task_id}, 类型: {task.task_type}")

                    # 调用任务目标函数
                    result = task.target_func(*task.args, **task.kwargs)

                    # 标记任务完成
                    task.result = result
                    task.status = TaskStatus.COMPLETED
                    task.completed_at = datetime.now()

                    # 完成任务
                    self.task_manager.complete_task(task.task_id, result, success=True)

                    # 如果任务需要等待完成，需要额外处理
                    if task.wait_for_completion:
                        # 处理等待完成的逻辑
                        pass

                    self.logger.info(f"任务执行完成: {task.task_id}")

                except Exception as e:
                    task.error = e
                    task.status = TaskStatus.FAILED
                    task.completed_at = datetime.now()

                    self.logger.error(f"任务执行失败: {task.task_id}, 错误: {e}")

                    # 根据重试配置决定是否重试
                    if task.retry_count < task.max_retries:
                        if self.task_manager.retry_task(task):
                            self.logger.info(f"任务已安排重试: {task.task_id}")
                        else:
                            self.task_manager.complete_task(task.task_id, e, success=False)
                    else:
                        self.task_manager.complete_task(task.task_id, e, success=False)

            except queue.Empty:
                # 队列为空，继续循环
                continue
            except Exception as e:
                self.logger.error(f"任务消费者循环错误: {e}")
                # 短暂休眠避免过于频繁的错误
                time.sleep(1)

    def get_stats(self) -> Dict[str, Any]:
        """
        获取调度器统计信息
        """
        with self.stats_lock:
            stats_copy = self.stats.copy()
            stats_copy['uptime'] = time.time() - stats_copy['start_time']

        # 添加任务管理器的统计信息
        task_stats = self.task_manager.get_stats()
        storage_stats = self.storage_worker.get_stats()

        result = {**stats_copy, **task_stats, 'storage_stats': storage_stats}
        return result

    def shutdown(self):
        """
        关闭调度器
        """
        self.logger.info("正在关闭下载调度器...")
        self.is_running = False
        self.shutdown_event.set()

        # 关闭任务管理器
        self.task_manager.shutdown()

        # 关闭存储工作器
        self.storage_worker.shutdown()

        self.logger.info("下载调度器已关闭")

    def is_alive(self) -> bool:
        """
        检查调度器是否仍在运行
        """
        return self.is_running and not self.shutdown_event.is_set()


class EnhancedDownloadScheduler(DownloadScheduler):
    """
    增强版下载调度器，提供更高级的调度功能
    """

    def __init__(self, start_date: str, end_date: str, max_workers: int = 4):
        super().__init__(start_date, end_date, max_workers)
        self.logger = logging.getLogger(f"{__name__}.enhanced")

    def schedule_by_priority(self) -> Dict[TaskPriority, List[str]]:
        """
        按优先级调度任务

        Returns:
            按优先级分组的任务ID字典
        """
        result = {
            TaskPriority.CRITICAL: [],
            TaskPriority.HIGH: [],
            TaskPriority.MEDIUM: [],
            TaskPriority.LOW: []
        }

        available_interfaces = get_all_available_interfaces()

        for interface_name, config in available_interfaces.items():
            priority = TaskPriority(config.priority.value)
            task_id = self._schedule_interface_by_type(interface_name, priority)
            if task_id:
                result[priority].append(task_id)

        return result

    def _schedule_interface_by_type(self, interface_name: str, priority: TaskPriority) -> Optional[str]:
        """
        根据接口类型调度任务
        """
        if interface_name in ['daily', 'daily_basic', 'moneyflow', 'moneyflow_dc', 'moneyflow_ths',
                             'moneyflow_ind_dc', 'moneyflow_mkt_dc', 'moneyflow_cnt_ths',
                             'moneyflow_ind_ths', 'stk_factor', 'stk_factor_pro', 'cyq_perf', 'cyq_chips']:
            return self._schedule_daily_interface(interface_name, priority)
        elif interface_name in ['income', 'balancesheet', 'cashflow', 'fina_indicator',
                               'dividend', 'forecast', 'express', 'top10_holders',
                               'top10_floatholders', 'stk_surv']:
            return self._schedule_financial_interface(interface_name, priority)
        elif interface_name in ['stock_basic', 'trade_cal', 'new_share', 'stock_company',
                               'stock_st', 'bak_basic', 'namechange', 'stk_rewards',
                               'stk_managers', 'broker_recommend']:
            return self._schedule_static_interface(interface_name, priority)
        else:
            # 未知类型，使用默认调度
            return self._schedule_daily_interface(interface_name, priority)

    def schedule_parallel_downloads(self, interface_list: List[str], date_ranges: List[tuple]) -> List[str]:
        """
        调度并行下载任务

        Args:
            interface_list: 接口列表
            date_ranges: 日期范围列表，每个元素为 (start_date, end_date) 元组

        Returns:
            任务ID列表
        """
        task_ids = []

        for start_date, end_date in date_ranges:
            for interface_name in interface_list:
                task_params = {
                    'interface_configs': {interface_name: {'start_date': start_date, 'end_date': end_date}},
                    'shared_params': {}
                }

                task_id = self.task_manager.add_task(
                    task_type='parallel_download',
                    target_func=self._execute_parallel_download,
                    priority=get_interface_priority(interface_name),
                    kwargs=task_params,
                    max_retries=2,
                    metadata={
                        'interfaces': interface_list,
                        'date_range': f"{start_date} to {end_date}"
                    }
                )
                if task_id:
                    task_ids.append(task_id)

        return task_ids

    def _execute_parallel_download(self, **kwargs):
        """
        执行并行下载
        """
        interface_configs = kwargs.get('interface_configs', {})
        shared_params = kwargs.get('shared_params', {})

        self.logger.info(f"开始并行下载: {list(interface_configs.keys())}")

        try:
            results = self.parallel_downloader.download_interfaces_parallel(
                interface_configs=interface_configs,
                shared_params=shared_params
            )

            # 为每个结果创建存储任务
            for interface_name, df in results.items():
                if df is not None and not df.empty:
                    filename = f"{interface_name}_{shared_params.get('start_date', self.start_date)}_{shared_params.get('end_date', self.end_date)}"
                    subdir = f"parallel/{shared_params.get('start_date', self.start_date)[:4]}"

                    self.task_manager.add_storage_task(
                        data=df,
                        filename=filename,
                        subdir=subdir,
                        priority=TaskPriority.MEDIUM
                    )

            self.logger.info(f"并行下载完成，接口数量: {len(results)}")
            return results

        except Exception as e:
            self.logger.error(f"并行下载失败: {e}")
            raise


# 全局调度器工厂函数
def create_download_scheduler(start_date: str, end_date: str, max_workers: int = 4) -> DownloadScheduler:
    """
    创建下载调度器实例
    """
    return DownloadScheduler(start_date, end_date, max_workers)


def create_enhanced_scheduler(start_date: str, end_date: str, max_workers: int = 4) -> EnhancedDownloadScheduler:
    """
    创建增强版下载调度器实例
    """
    return EnhancedDownloadScheduler(start_date, end_date, max_workers)


def run_download_schedule(start_date: str, end_date: str, interfaces: List[str] = None) -> Dict[str, Any]:
    """
    运行下载调度（便捷函数）

    Args:
        start_date: 开始日期 (YYYYMMDD)
        end_date: 结束日期 (YYYYMMDD)
        interfaces: 要下载的接口列表，如果为None则下载所有可用接口

    Returns:
        下载统计结果
    """
    scheduler = create_download_scheduler(start_date, end_date)

    try:
        # 调度下载任务
        scheduler.schedule_download_tasks(interfaces)

        # 执行所有任务
        results = scheduler.execute_scheduled_tasks(wait_for_completion=True)

        return results
    finally:
        scheduler.shutdown()