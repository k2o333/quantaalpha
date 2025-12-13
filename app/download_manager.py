"""
统一下载管理器
"""
import logging
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
from typing import List, Dict, Optional, Tuple

# Add paths for modules to find each other
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
sys.path.insert(0, os.path.join(current_dir, 'utils'))
sys.path.insert(0, os.path.join(current_dir, 'interfaces'))

from api_manager import TuShareAPIManager
from config_manager import ConfigManager
from utils.date_processor import DateRangeProcessor
from utils.score_selector import ScoreBasedSelector
from utils.parallel_downloader import ParallelDownloader
from error_handler import ErrorHandler
from data_storage import save_to_parquet, get_cache_path, is_data_cached, is_data_fresh


class DownloadManager:
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager
        self.api_manager = TuShareAPIManager(config_manager)
        self.date_processor = DateRangeProcessor()
        self.score_selector = ScoreBasedSelector(config_manager)
        self.parallel_downloader = ParallelDownloader(config_manager)
        # 从配置文件获取存储管理类
        self.error_handler = ErrorHandler()

        self.logger = logging.getLogger(__name__)
        self.available_types = self.score_selector.get_available_data_types()

    def download_all_available_data(self, start_date: str, end_date: str = None) -> Dict[str, any]:
        """下载所有可用数据"""
        if end_date is None:
            end_date = datetime.now().strftime('%Y%m%d')

        self.logger.info(f"开始下载日期范围 {start_date} 到 {end_date} 的所有可用数据")

        # 创建下载任务列表
        download_tasks = self._create_download_task_list(start_date, end_date)

        # 跟踪失败尝试和已完成任务
        failed_attempts = {}
        completed_tasks = set()
        original_task_count = len(download_tasks)

        # 智能下载循环
        while len(completed_tasks) < original_task_count and download_tasks:
            # 检查是否所有任务都已达到最大重试次数
            all_max_retries_reached = True
            for task_name, _, max_retries in download_tasks:
                if failed_attempts.get(task_name, 0) < max_retries:
                    all_max_retries_reached = False
                    break

            if all_max_retries_reached:
                self.logger.info("所有剩余任务都已达到最大重试次数，退出。")
                break

            if not download_tasks:  # 确保任务队列不为空
                break

            task_name, download_func, max_retries = download_tasks[0]

            # 检查此任务是否已达到最大重试次数
            if failed_attempts.get(task_name, 0) >= max_retries:
                self.logger.info(f"{task_name} 已达到最大重试次数 {max_retries}，跳过任务")
                download_tasks.pop(0)  # 直接移除不再尝试
                continue

            task_completed = False

            try:
                self.logger.info(f"开始下载数据类型: {task_name}")
                result = download_func()

                if result is not None:  # 空dict或0也算成功
                    yield {task_name: result}  # 返回结果，可能需要根据实际需求调整
                    task_completed = True
                    self.logger.info(f"✅ {task_name} 下载成功")
                else:
                    self.logger.warning(f"{task_name} 返回空结果")
                    task_completed = True  # 空结果也视为完成，不是失败

            except Exception as e:
                failed_attempts[task_name] = failed_attempts.get(task_name, 0) + 1
                self.logger.error(f"❌ {task_name} 下载失败 (尝试 {failed_attempts[task_name]}/{max_retries}): {e}")
                self.error_handler.handle_api_error(e, f"Download task {task_name}")

                if failed_attempts[task_name] >= max_retries:
                    self.logger.warning(f"{task_name} 达到最大重试次数 {max_retries}，不再重试")
                    download_tasks.pop(0)  # 达到重试上限，直接移除任务
                else:
                    # 任务失败但仍需重试，移到队列末尾
                    download_tasks.append(download_tasks.pop(0))

            finally:
                if task_completed:
                    completed_tasks.add(task_name)
                    if download_tasks:  # 确保列表不为空
                        download_tasks.pop(0)  # 移除已完成的任务

        self.logger.info("日期范围数据下载完成")

    def _create_download_task_list(self, start_date: str, end_date: str) -> List[Tuple[str, callable, int]]:
        """创建下载任务列表"""
        tasks = []

        # 日度数据 - 高优先级
        daily_types = self._get_daily_types()
        for data_type in daily_types:
            if self._is_data_type_available(data_type):
                tasks.append((data_type,
                             lambda dt=data_type: self._download_daily_type_for_range(dt, start_date, end_date),
                             3))

        # 静态数据 - 高优先级
        static_types = self._get_static_types()
        for data_type in static_types:
            if self._is_data_type_available(data_type):
                tasks.append((data_type,
                             lambda dt=data_type: self._download_static_type(dt),
                             3))

        # 财务数据 - 中等优先级
        financial_types = self._get_financial_types()
        for data_type in financial_types:
            if self._is_data_type_available(data_type):
                tasks.append((data_type,
                             lambda dt=data_type: self._download_financial_type_for_range(dt, start_date, end_date),
                             3))

        return tasks

    def _is_data_type_available(self, data_type: str) -> bool:
        """检查数据类型是否在用户积分范围内可用"""
        for category_types in self.available_types.values():
            if data_type in category_types:
                return True
        return False

    def _get_daily_types(self) -> List[str]:
        """获取所有日度数据类型"""
        # 根据积分情况返回相应的日度数据类型
        daily_types = ['daily', 'daily_basic', 'moneyflow']

        if self.config.tushare_points >= 5000:
            daily_types.extend(['moneyflow_dc', 'moneyflow_ths', 'moneyflow_ind_dc', 'moneyflow_mkt_dc',
                               'moneyflow_cnt_ths', 'moneyflow_ind_ths'])

        if self.config.tushare_points >= 5000:
            daily_types.extend(['stk_factor', 'stk_factor_pro', 'cyq_perf', 'cyq_chips'])

        return daily_types

    def _get_static_types(self) -> List[str]:
        """获取所有静态数据类型"""
        static_types = ['stock_basic', 'trade_cal', 'new_share', 'stock_company']

        if self.config.tushare_points >= 3000:
            static_types.append('stock_st')
        if self.config.tushare_points >= 5000:
            static_types.append('bak_basic')

        return static_types

    def _get_financial_types(self) -> List[str]:
        """获取所有财务数据类型"""
        return ['income', 'balancesheet', 'cashflow', 'fina_indicator']

    def _download_daily_type_for_range(self, data_type: str, start_date: str, end_date: str) -> Dict[str, int]:
        """
        优化后的下载特定日度数据类型的日期范围数据，并发处理和内存控制
        """
        results = {}
        trading_days = self.date_processor.get_trading_days(start_date, end_date, self.api_manager)

        self.logger.info(f"开始下载 {data_type} 数据，共 {len(trading_days)} 个交易日")

        # 使用并行下载器进行并行下载
        return self.parallel_downloader.download_daily_type_parallel(data_type, trading_days)

    def _download_static_type(self, data_type: str) -> int:
        """
        下载特定静态数据类型
        """
        self.logger.info(f"开始下载静态数据 {data_type}")

        try:
            if data_type == 'stock_basic':
                df = self.api_manager.basic_data.download_stock_basic()
            elif data_type == 'stock_company':
                sse_data = self.api_manager.basic_data.download_stock_company(exchange='SSE')
                szse_data = self.api_manager.basic_data.download_stock_company(exchange='SZSE')
                df = pd.concat([sse_data, szse_data], ignore_index=True) if not sse_data.empty and not szse_data.empty else pd.DataFrame()
            elif data_type == 'trade_cal':
                df = self.api_manager.basic_data.download_trade_cal(start_date=self.config.default_start_date, end_date=self.config.default_end_date)
            elif data_type == 'new_share':
                df = self.api_manager.basic_data.download_new_share(start_date=self.config.default_start_date, end_date=self.config.default_end_date)
            elif data_type == 'stock_st':
                df = self.api_manager.basic_data.download_stock_st(trade_date=self.config.default_start_date)
            elif data_type == 'bak_basic':
                df = self.api_manager.basic_data.download_bak_basic()
            else:
                self.logger.warning(f"未知的静态数据类型: {data_type}")
                return 0

            if not df.empty:
                file_path = save_to_parquet(df, data_type, subdir="basic")
                count = len(df)
                self.logger.info(f"成功保存 {data_type}: {count} 条记录")
                return count
            else:
                self.logger.warning(f"{data_type} 无数据")
                return 0

        except Exception as e:
            self.logger.error(f"下载静态数据 {data_type} 失败: {e}")
            return 0

    def _download_financial_type_for_range(self, data_type: str, start_date: str, end_date: str) -> Dict[str, int]:
        """
        下载特定财务数据类型的日期范围数据
        """
        results = {}

        self.logger.info(f"开始下载 {data_type} 财务数据")

        # 获取日期范围内的财务报告期
        periods = self._get_financial_periods_in_range(start_date, end_date)

        for period in periods:
            try:
                self.logger.info(f"正在下载 {data_type} - {period}")

                if data_type == 'income':
                    df = self.api_manager.financial_data.download_income(period=period, ts_code='000001.SZ')
                elif data_type == 'balancesheet':
                    df = self.api_manager.financial_data.download_balancesheet(period=period, ts_code='000001.SZ')
                elif data_type == 'cashflow':
                    df = self.api_manager.financial_data.download_cashflow(period=period, ts_code='000001.SZ')
                elif data_type == 'fina_indicator':
                    df = self.api_manager.financial_data.download_fina_indicator(period=period, ts_code='000001.SZ')
                else:
                    self.logger.warning(f"未知的财务数据类型: {data_type}")
                    continue

                if not df.empty:
                    filename = f"{data_type}_{period}"
                    file_path = save_to_parquet(df, filename, subdir="financial")
                    results[period] = len(df)

                    self.logger.info(f"成功保存 {data_type}_{period}: {len(df)} 条记录")
                else:
                    self.logger.warning(f"{data_type} - {period} 无数据")

            except Exception as e:
                self.logger.error(f"下载 {data_type} - {period} 失败: {e}")
                continue

        return results

    def _get_financial_periods_in_range(self, start_date: str, end_date: str) -> List[str]:
        """
        获取日期范围内的财务报告期
        """
        # 简化实现：返回常见的报告期
        # 在实际应用中，需要根据财务报告发布规律确定

        periods = []
        start_year = int(start_date[:4])
        end_year = int(end_date[:4])

        # 按年度和季度生成报告期
        for year in range(start_year, end_year + 1):
            periods.extend([
                f"{year}0331",  # Q1
                f"{year}0630",  # Q2
                f"{year}0930",  # Q3
                f"{year}1231"   # Q4
            ])

        # Filter to ensure only periods in the range
        valid_periods = []
        for period in periods:
            if start_date <= period <= end_date:
                valid_periods.append(period)

        return valid_periods

    def download_all_score_appropriate_data(self) -> Dict[str, int]:
        """
        下载所有适合用户积分的数据
        """
        results = {}
        self.logger.info("开始下载所有匹配积分的数据...")

        # 基础数据优先下载
        basic_types = self.available_types.get('basic', [])
        for data_type in basic_types:
            if self.config.download_config.get(data_type, True):
                try:
                    result = self._download_basic_data_type(data_type)
                    results[data_type] = result
                except Exception as e:
                    self.logger.error(f"下载基础数据 {data_type} 失败: {e}")

        # 其他类型数据随后下载
        # 此处为简化实现，实际应该包含更多的数据类型处理
        self.logger.info(f"积分匹配下载完成: {results}")
        return results

    def _download_basic_data_type(self, data_type: str) -> int:
        """
        下载基础数据类型
        """
        if data_type == 'stock_basic':
            df = self.api_manager.basic_data.download_stock_basic()
        elif data_type == 'trade_cal':
            df = self.api_manager.basic_data.download_trade_cal()
        elif data_type == 'new_share':
            df = self.api_manager.basic_data.download_new_share()
        else:
            # 尝试通过getattr动态调用接口
            try:
                df = getattr(self.api_manager.basic_data, f'download_{data_type}')()
            except AttributeError:
                self.logger.warning(f"未知的基础数据类型: {data_type}")
                return 0

        if not df.empty:
            file_path = save_to_parquet(df, data_type, subdir="basic")
            count = len(df)
            self.logger.info(f"成功保存 {data_type}: {count} 条记录")
            return count
        else:
            self.logger.warning(f"{data_type} 无数据")
            return 0