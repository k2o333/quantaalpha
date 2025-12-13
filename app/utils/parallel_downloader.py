"""
并行下载管理器
"""
import logging
from typing import List, Dict
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data_storage import save_to_parquet, get_cache_path, is_data_cached


class ParallelDownloader:
    def __init__(self, config_manager):
        self.config = config_manager
        self.logger = logging.getLogger(__name__)
        self.download_lock = threading.Lock()

    def download_daily_type_parallel(self, data_type: str, trading_days: List[str]) -> Dict[str, int]:
        """
        并行下载特定日度数据类型
        """
        results = {}
        all_data = []

        # 为不同数据类型分配不同数量的线程
        if data_type == 'daily_basic':
            # daily_basic最慢，可用更多线程
            max_workers = min(8, len(trading_days))
        else:
            # 其他类型使用适度的线程数
            max_workers = min(4, len(trading_days))

        # 函数：下载单个日期的指定数据类型
        def download_single_day(trade_date):
            try:
                # 检查缓存
                cache_path = get_cache_path(data_type, trade_date)
                if is_data_cached(cache_path):
                    self.logger.info(f"使用缓存数据: {data_type} - {trade_date}")
                    df = pd.read_parquet(cache_path)
                    return (trade_date, df, len(df))

                # 真实API调用
                api_manager = self.config.api_manager  # 假设config中有api_manager
                if data_type == 'daily':
                    df = api_manager.daily_data.download_daily_data(ts_code=None, start_date=trade_date, end_date=trade_date)
                elif data_type == 'daily_basic':
                    df = api_manager.daily_data.download_daily_basic(trade_date=trade_date)
                elif data_type == 'moneyflow':
                    df = api_manager.market_flow.download_moneyflow(trade_date=trade_date)
                elif data_type == 'moneyflow_dc':
                    df = api_manager.market_flow.download_moneyflow_dc(trade_date=trade_date)
                elif data_type == 'moneyflow_ths':
                    df = api_manager.market_flow.download_moneyflow_ths(trade_date=trade_date)
                elif data_type == 'moneyflow_ind_dc':
                    df = api_manager.market_flow.download_moneyflow_ind_dc(trade_date=trade_date)
                elif data_type == 'moneyflow_mkt_dc':
                    df = api_manager.market_flow.download_moneyflow_mkt_dc(trade_date=trade_date)
                elif data_type == 'moneyflow_cnt_ths':
                    df = api_manager.market_flow.download_moneyflow_cnt_ths(trade_date=trade_date)
                elif data_type == 'moneyflow_ind_ths':
                    df = api_manager.market_flow.download_moneyflow_ind_ths(trade_date=trade_date)
                elif data_type == 'stk_factor':
                    # 使用分页下载
                    df = api_manager.technical_factors.download_stk_factor_paginated(trade_date=trade_date)
                elif data_type == 'stk_factor_pro':
                    df = api_manager.technical_factors.download_stk_factor_pro(trade_date=trade_date)
                elif data_type == 'cyq_perf':
                    # 使用分页下载
                    df = api_manager.market_structure.download_cyq_perf_paginated(trade_date=trade_date)
                elif data_type == 'cyq_chips':
                    # 使用分页下载
                    df = api_manager.market_structure.download_cyq_chips_paginated(trade_date=trade_date)
                else:
                    # 默认处理方式
                    # 尝试通过getattr动态调用接口
                    try:
                        # 使用api_manager的daily_data接口作为默认实现
                        df = getattr(api_manager.daily_data, f'download_{data_type}')(trade_date=trade_date)
                    except AttributeError:
                        self.logger.warning(f"未知的日度数据类型: {data_type}")
                        return (trade_date, pd.DataFrame(), 0)

                if not df.empty:
                    # 添加交易日期标记
                    df['trade_date'] = pd.to_datetime(trade_date)

                    # 保存到本地
                    year = trade_date[:4]
                    month = trade_date[4:6]
                    subdir = f"daily/{year}/{month}"
                    filename = f"{data_type}_{trade_date}"

                    with self.download_lock:
                        file_path = save_to_parquet(df, filename, subdir=subdir)

                    self.logger.debug(f"成功下载 {data_type} - {trade_date}: {len(df)} 条记录")
                    return (trade_date, df, len(df))
                else:
                    self.logger.warning(f"{data_type} - {trade_date} 无数据")
                    return (trade_date, pd.DataFrame(), 0)

            except Exception as e:
                self.logger.error(f"下载 {data_type} - {trade_date} 失败: {e}")
                return (trade_date, pd.DataFrame(), 0)

        # 并行下载所有日期的数据
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            futures = {
                executor.submit(download_single_day, day): day
                for day in trading_days
            }

            # 收集结果
            for future in as_completed(futures):
                trade_date, df, record_count = future.result()
                if not df.empty and record_count > 0:
                    all_data.append(df)
                    results[trade_date] = record_count

        # 合并结果
        final_result = {}
        if all_data:
            # 按月分组数据(如果需要进一步组织存储)
            combined_df = pd.concat(all_data, ignore_index=True)
            if 'trade_date' in combined_df.columns:
                date_groups = combined_df.groupby(combined_df['trade_date'].dt.strftime('%Y-%m'))
                for (year_month), group in date_groups:
                    year, month = year_month.split('-')
                    subdir = f"daily/{year}/{month}"
                    filename = f"{data_type}_{year_month}"
                    file_path = save_to_parquet(group, filename, subdir=subdir)
                    final_result[year_month] = len(group)

        return final_result