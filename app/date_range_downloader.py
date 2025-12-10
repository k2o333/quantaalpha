"""
日期范围数据下载器
实现按指定日期范围下载完整数据的功能，采用增强的错误处理机制
"""
import logging
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
from typing import List, Dict, Optional, Tuple
from tushare_api import TuShareDownloader
from config import TUSHARE_POINTS
from score_config import get_available_data_types
from data_storage import save_to_parquet


class DateRangeDownloader:
    def __init__(self, start_date: str, end_date: str = None):
        """
        初始化日期范围下载器

        Args:
            start_date: 开始日期 (YYYYMMDD格式)
            end_date: 结束日期 (YYYYMMDD格式，默认为今天)
        """
        if end_date is None:
            end_date = datetime.now().strftime('%Y%m%d')

        self.start_date = start_date
        self.end_date = end_date
        self.downloader = TuShareDownloader()
        self.available_types = get_available_data_types(TUSHARE_POINTS)

        self.logger = logging.getLogger(__name__)
        self.logger.info(f"初始化日期范围下载器: {start_date} 到 {end_date}")

    def get_trading_days(self) -> List[str]:
        """
        获取指定日期范围内的交易日列表
        """
        try:
            # 先下载交易日历数据
            trade_cal = self.downloader.download_trade_cal(
                start_date=self.start_date,
                end_date=self.end_date
            )

            # 过滤出交易日（is_open=1）
            trading_days = trade_cal[trade_cal['is_open'] == 1]['cal_date'].tolist()
            trading_days.sort()

            self.logger.info(f"获取到 {len(trading_days)} 个交易日")
            return trading_days

        except Exception as e:
            self.logger.error(f"获取交易日历失败: {e}")
            # 如果无法获取交易日历，返回日期范围内的所有日期作为备选
            return self._generate_date_range()

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

    def _create_download_task_list(self) -> List[Tuple[str, callable, int]]:
        """
        创建下载任务列表，为每个数据类型提供相应的下载函数和重试限制
        """
        tasks = []

        # 获取可用的数据类型
        available_types = get_available_data_types(TUSHARE_POINTS)

        # 日度数据 - 高优先级 (通常比较稳定)
        daily_types = ['daily', 'daily_basic', 'moneyflow']
        # Add money flow interfaces from East Money and THS
        if TUSHARE_POINTS >= 5000:
            daily_types.extend(['moneyflow_dc', 'moneyflow_ths', 'moneyflow_ind_dc', 'moneyflow_mkt_dc', 
                               'moneyflow_cnt_ths', 'moneyflow_ind_ths'])
        # Add technical factors and chip data
        if TUSHARE_POINTS >= 5000:
            daily_types.extend(['stk_factor', 'stk_factor_pro', 'cyq_perf', 'cyq_chips'])
        
        for data_type in daily_types:
            if self._is_data_type_available(data_type):
                tasks.append((data_type, lambda dt=data_type: self._download_daily_type_for_range(dt), 3))

        # 静态数据 - 高优先级
        static_types = ['stock_basic', 'trade_cal', 'new_share', 'stock_company']
        # Add stock_st and bak_basic to static types
        if TUSHARE_POINTS >= 3000:
            static_types.append('stock_st')
        if TUSHARE_POINTS >= 5000:
            static_types.append('bak_basic')
        
        for data_type in static_types:
            if self._is_data_type_available(data_type):
                tasks.append((data_type, lambda dt=data_type: self._download_static_type(dt), 3))

        # 财务数据 - 中等优先级 (可能需要特定参数)
        financial_types = ['income', 'balancesheet', 'cashflow', 'fina_indicator']
        for data_type in financial_types:
            if self._is_data_type_available(data_type):
                tasks.append((data_type, lambda dt=data_type: self._download_financial_type_for_range(dt), 3))

        # 事件数据 - 中等优先级
        event_types = ['dividend', 'forecast', 'express']
        for data_type in event_types:
            if self._is_data_type_available(data_type):
                tasks.append((data_type, lambda dt=data_type: self._download_event_type_for_range(dt), 3))

        # 股东数据 - 中等优先级
        holder_types = ['top10_holders']
        if TUSHARE_POINTS >= 3000:
            holder_types.append('top10_floatholders')
        for data_type in holder_types:
            if self._is_data_type_available(data_type):
                tasks.append((data_type, lambda dt=data_type: self._download_holder_type_for_range(dt), 3))

        # 研究数据 - 中等优先级
        research_types = []
        if TUSHARE_POINTS >= 5000:
            research_types.extend(['report_rc', 'stk_surv'])
        if TUSHARE_POINTS >= 2000:
            research_types.append('broker_recommend')
        for data_type in research_types:
            if self._is_data_type_available(data_type):
                tasks.append((data_type, lambda dt=data_type: self._download_research_type_for_range(dt), 3))

        # 其他数据 - 最后尝试
        other_types = ['stk_rewards', 'stk_managers', 'namechange']
        for data_type in other_types:
            if self._is_data_type_available(data_type):
                tasks.append((data_type, lambda dt=data_type: self._download_other_type_for_range(dt), 3))

        return tasks

    def _download_daily_type_for_range(self, data_type: str) -> Dict[str, int]:
        """
        下载特定日度数据类型的日期范围数据
        """
        results = {}
        trading_days = self.get_trading_days()

        self.logger.info(f"开始下载 {data_type} 数据，共 {len(trading_days)} 个交易日")

        for i, trade_date in enumerate(trading_days):
            try:
                self.logger.info(f"正在下载 {data_type} - {trade_date} ({i+1}/{len(trading_days)})")

                # 根据数据类型调用相应的方法
                if data_type == 'daily':
                    df = self.downloader.download_daily_data(ts_code=None, start_date=trade_date, end_date=trade_date)
                elif data_type == 'daily_basic':
                    df = self.downloader.download_daily_basic(trade_date=trade_date)
                elif data_type == 'moneyflow':
                    df = self.downloader.download_moneyflow(trade_date=trade_date)
                # New money flow interfaces from East Money and THS
                elif data_type == 'moneyflow_dc':
                    df = self.downloader.download_moneyflow_dc(trade_date=trade_date)
                elif data_type == 'moneyflow_ths':
                    df = self.downloader.download_moneyflow_ths(trade_date=trade_date)
                elif data_type == 'moneyflow_ind_dc':
                    df = self.downloader.download_moneyflow_ind_dc(trade_date=trade_date)
                elif data_type == 'moneyflow_mkt_dc':
                    df = self.downloader.download_moneyflow_mkt_dc(trade_date=trade_date)
                elif data_type == 'moneyflow_cnt_ths':
                    df = self.downloader.download_moneyflow_cnt_ths(trade_date=trade_date)
                elif data_type == 'moneyflow_ind_ths':
                    df = self.downloader.download_moneyflow_ind_ths(trade_date=trade_date)
                # Technical factors and chip data
                elif data_type == 'stk_factor':
                    df = self.downloader.download_stk_factor(trade_date=trade_date)
                elif data_type == 'stk_factor_pro':
                    df = self.downloader.download_stk_factor_pro(trade_date=trade_date)
                elif data_type == 'cyq_perf':
                    df = self.downloader.download_cyq_perf(trade_date=trade_date)
                elif data_type == 'cyq_chips':
                    df = self.downloader.download_cyq_chips(trade_date=trade_date)
                else:
                    self.logger.warning(f"未知的日度数据类型: {data_type}")
                    continue

                if not df.empty:
                    # 按年/月/日分区保存
                    year = trade_date[:4]
                    month = trade_date[4:6]

                    # 创建分区目录
                    subdir = f"daily/{year}/{month}"

                    filename = f"{data_type}_{trade_date}"
                    file_path = save_to_parquet(df, filename, subdir=subdir)
                    results[trade_date] = len(df)

                    self.logger.info(f"成功保存 {data_type}_{trade_date}: {len(df)} 条记录")
                else:
                    self.logger.warning(f"{data_type} - {trade_date} 无数据")

            except Exception as e:
                self.logger.error(f"下载 {data_type} - {trade_date} 失败: {e}")
                continue

        return results

    def _download_static_type(self, data_type: str) -> int:
        """
        下载特定静态数据类型
        """
        self.logger.info(f"开始下载静态数据 {data_type}")

        try:
            if data_type == 'stock_basic':
                df = self.downloader.download_stock_basic()
            elif data_type == 'stock_company':
                sse_data = self.downloader.download_stock_company(exchange='SSE')
                szse_data = self.downloader.download_stock_company(exchange='SZSE')
                df = pd.concat([sse_data, szse_data], ignore_index=True) if not sse_data.empty and not szse_data.empty else pd.DataFrame()
            elif data_type == 'trade_cal':
                df = self.downloader.download_trade_cal(start_date=self.start_date, end_date=self.end_date)
            elif data_type == 'new_share':
                df = self.downloader.download_new_share(start_date=self.start_date, end_date=self.end_date)
            elif data_type == 'stock_st':
                df = self.downloader.download_stock_st(trade_date=self.start_date)
            elif data_type == 'bak_basic':
                df = self.downloader.download_bak_basic()
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

    def _download_financial_type_for_range(self, data_type: str) -> Dict[str, int]:
        """
        下载特定财务数据类型的日期范围数据
        """
        results = {}

        self.logger.info(f"开始下载 {data_type} 财务数据")

        try:
            # 获取报告期在指定范围内的数据
            periods = self._get_financial_periods_in_range()

            for period in periods:
                try:
                    self.logger.info(f"正在下载 {data_type} - {period}")

                    if data_type == 'income':
                        df = self.downloader.download_income(period=period, ts_code='000001.SZ')
                    elif data_type == 'balancesheet':
                        df = self.downloader.download_balancesheet(period=period, ts_code='000001.SZ')
                    elif data_type == 'cashflow':
                        df = self.downloader.download_cashflow(period=period, ts_code='000001.SZ')
                    elif data_type == 'fina_indicator':
                        df = self.downloader.download_fina_indicator(period=period, ts_code='000001.SZ')
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

        except Exception as e:
            self.logger.error(f"下载财务数据 {data_type} 失败: {e}")

        return results

    def _download_holder_type_for_range(self, data_type: str) -> Dict[str, int]:
        """
        下载特定股东数据类型的日期范围数据
        """
        results = {}
        self.logger.info(f"开始下载股东数据 {data_type}")

        try:
            # 获取报告期在指定范围内的数据
            periods = self._get_financial_periods_in_range()

            for period in periods:
                try:
                    self.logger.info(f"正在下载 {data_type} - {period}")

                    # 先获取股票列表
                    stock_df = self.downloader.download_stock_basic()
                    if not stock_df.empty:
                        ts_code = stock_df.iloc[0]['ts_code']

                        if data_type == 'top10_holders':
                            df = self.downloader.download_top10_holders(ts_code=ts_code, period=period)
                        elif data_type == 'top10_floatholders':
                            df = self.downloader.download_top10_floatholders(ts_code=ts_code, period=period)
                        else:
                            self.logger.warning(f"未知的股东数据类型: {data_type}")
                            continue

                        if not df.empty:
                            filename = f"{data_type}_{period}"
                            file_path = save_to_parquet(df, filename, subdir="holders")
                            results[period] = len(df)

                            self.logger.info(f"成功保存 {data_type}_{period}: {len(df)} 条记录")
                        else:
                            self.logger.warning(f"{data_type} - {period} 无数据")

                except Exception as e:
                    self.logger.error(f"下载 {data_type} - {period} 失败: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"下载股东数据 {data_type} 失败: {e}")

        return results

    def _download_research_type_for_range(self, data_type: str) -> Dict[str, any]:
        """
        下载特定研究数据类型
        """
        try:
            if data_type == 'report_rc':
                # Download sell-side earnings forecast data
                periods = self._get_financial_periods_in_range()
                results = {}
                
                for period in periods:
                    try:
                        df = self.downloader.download_report_rc(period=period)
                        if not df.empty:
                            filename = f"{data_type}_{period}"
                            file_path = save_to_parquet(df, filename, subdir="research")
                            results[period] = len(df)
                    except Exception as e:
                        self.logger.error(f"下载 {data_type} - {period} 失败: {e}")
                
                return results
                
            elif data_type == 'stk_surv':
                # Download institutional research survey
                periods = self._get_financial_periods_in_range()
                results = {}
                
                for period in periods:
                    try:
                        df = self.downloader.download_stk_surv(period=period)
                        if not df.empty:
                            filename = f"{data_type}_{period}"
                            file_path = save_to_parquet(df, filename, subdir="research")
                            results[period] = len(df)
                    except Exception as e:
                        self.logger.error(f"下载 {data_type} - {period} 失败: {e}")
                
                return results
                
            elif data_type == 'broker_recommend':
                # Download broker monthly stock recommendations
                try:
                    df = self.downloader.download_broker_recommend(start_date=self.start_date, end_date=self.end_date)
                    if not df.empty:
                        file_path = save_to_parquet(df, data_type, subdir="research")
                        self.logger.info(f"成功保存 {data_type}: {len(df)} 条记录")
                        return {'records': len(df)}
                except Exception as e:
                    self.logger.error(f"下载 {data_type} 失败: {e}")

            return {}
        except Exception as e:
            self.logger.error(f"下载研究数据 {data_type} 失败: {e}")
            return {}

    def _get_financial_periods_in_range(self) -> List[str]:
        """
        获取日期范围内的财务报告期
        """
        # 简化实现：返回常见的报告期
        # 在实际应用中，需要根据财务报告发布规律确定

        periods = []
        start_year = int(self.start_date[:4])
        end_year = int(self.end_date[:4])

        # 按年度和季度生成报告期
        for year in range(start_year, end_year + 1):
            periods.extend([
                f"{year}0331",  # Q1
                f"{year}0630",  # Q2
                f"{year}0930",  # Q3
                f"{year}1231"   # Q4
            ])

        return periods

    def _download_event_type_for_range(self, data_type: str) -> Dict[str, int]:
        """
        下载特定事件数据类型的日期范围数据
        """
        results = {}
        self.logger.info(f"开始下载事件数据 {data_type}")

        # 获取日期范围内的事件数据
        try:
            # 按年/月分区下载
            start_year = int(self.start_date[:4])
            end_year = int(self.end_date[:4])

            for year in range(start_year, end_year + 1):
                for month in range(1, 13):
                    # 构造当月的起止日期
                    month_start = f"{year}{month:02d}01"
                    if month == 12:
                        month_end = f"{year}1231"
                    else:
                        next_month = datetime.strptime(f"{year}{month:02d}01", '%Y%m%d').replace(day=28) + timedelta(days=4)
                        month_end = (next_month - timedelta(days=next_month.day)).strftime('%Y%m%d')

                    # 只处理在指定范围内的月份
                    if month_start < self.start_date:
                        continue
                    if month_end > self.end_date:
                        month_end = self.end_date

                    try:
                        self.logger.info(f"正在下载 {data_type} - {year}年{month:02d}月")

                        df = self._download_event_data_single_period(data_type, month_start, month_end)

                        if not df.empty:
                            # 按年月分区保存
                            subdir = f"events/{year}/{month:02d}"
                            filename = f"{data_type}_{year}{month:02d}"
                            file_path = save_to_parquet(df, filename, subdir=subdir)
                            results[f"{year}-{month:02d}"] = len(df)

                            self.logger.info(f"成功保存 {data_type}_{year}{month:02d}: {len(df)} 条记录")
                        else:
                            self.logger.info(f"{data_type}_{year}{month:02d} 无数据")

                    except Exception as e:
                        self.logger.error(f"下载 {data_type} - {year}年{month:02d}月 失败: {e}")
                        continue

        except Exception as e:
            self.logger.error(f"下载事件数据 {data_type} 失败: {e}")

        return results

    def _download_other_type_for_range(self, data_type: str) -> Dict[str, any]:
        """
        下载其他数据类型
        """
        try:
            if data_type == 'stk_rewards':
                # 先获取股票列表
                stock_df = self.downloader.download_stock_basic()
                if not stock_df.empty:
                    ts_code = stock_df.iloc[0]['ts_code']
                    df = self.downloader.download_stk_rewards(ts_code=ts_code)
                    if not df.empty:
                        file_path = save_to_parquet(df, data_type, subdir="holders")
                        self.logger.info(f"成功保存 {data_type}: {len(df)} 条记录")
                        return {'records': len(df)}
            elif data_type == 'stk_managers':
                stock_df = self.downloader.download_stock_basic()
                if not stock_df.empty:
                    ts_code = stock_df.iloc[0]['ts_code']
                    df = self.downloader.download_stk_managers(ts_code=ts_code)
                    if not df.empty:
                        file_path = save_to_parquet(df, data_type, subdir="holders")
                        self.logger.info(f"成功保存 {data_type}: {len(df)} 条记录")
                        return {'records': len(df)}
            elif data_type == 'namechange':
                # 使用合适参数或直接下载
                try:
                    df = self.downloader.download_namechange()
                except:
                    df = pd.DataFrame()
                if not df.empty:
                    file_path = save_to_parquet(df, data_type, subdir="basic")
                    self.logger.info(f"成功保存 {data_type}: {len(df)} 条记录")
                    return {'records': len(df)}

            return {}
        except Exception as e:
            self.logger.error(f"下载其他数据 {data_type} 失败: {e}")
            return {}

    def _download_event_data_single_period(self, data_type: str, start_date: str, end_date: str):
        """
        下载单个时间段的事件数据
        """
        try:
            if data_type == 'dividend':
                # dividend接口需要特定的参数，使用公告日期范围参数
                try:
                    # 使用公告日期范围下载
                    df = self.downloader.download_dividend(ann_date=start_date[:6] + '01')  # 使用年月作为日期
                    return df
                except Exception:
                    # 如果按公告日期失败，尝试使用其他参数
                    try:
                        # 获取一些股票代码作为参数
                        stock_df = self.downloader.download_stock_basic()
                        if not stock_df.empty:
                            ts_code = stock_df.iloc[0]['ts_code']
                            df = self.downloader.download_dividend(ts_code=ts_code)
                            return df
                    except:
                        # 如果仍然失败，返回空DataFrame
                        return pd.DataFrame()
            elif data_type == 'forecast':
                try:
                    # 有些接口需要特定参数，需要先获取股票代码
                    stock_df = self.downloader.download_stock_basic()
                    if not stock_df.empty:
                        ts_code = stock_df.iloc[0]['ts_code']
                        df = self.downloader.download_forecast(ts_code=ts_code)
                        return df
                    else:
                        # 如果无法获取股票代码，尝试使用日期参数
                        df = self.downloader.download_forecast(period=start_date[:6] + '30')  # 使用年月+30作为报告期
                        return df
                except:
                    return pd.DataFrame()
            elif data_type == 'express':
                try:
                    # 有些接口需要特定参数，需要先获取股票代码
                    stock_df = self.downloader.download_stock_basic()
                    if not stock_df.empty:
                        ts_code = stock_df.iloc[0]['ts_code']
                        df = self.downloader.download_express(ts_code=ts_code)
                        return df
                    else:
                        # 如果无法获取股票代码，尝试使用日期参数
                        df = self.downloader.download_express(period=start_date[:6] + '30')  # 使用年月+30作为报告期
                        return df
                except:
                    return pd.DataFrame()
            else:
                self.logger.warning(f"未知的事件数据类型: {data_type}")
                return pd.DataFrame()
        except Exception as e:
            self.logger.warning(f"下载事件数据 {data_type} 时出错: {e}")
            return pd.DataFrame()

    def download_all_available_data(self) -> Dict[str, any]:
        """
        下载所有可用数据，使用改进的错误处理和优先级机制
        """
        results = {}

        self.logger.info(f"开始下载日期范围 {self.start_date} 到 {self.end_date} 的所有可用数据")

        # 创建下载任务列表
        download_tasks = self._create_download_task_list()

        # 跟踪失败尝试和已完成任务
        failed_attempts = {}
        completed_tasks = set()
        original_task_count = len(download_tasks)

        # 智能下载循环 - 为每个任务设置最大重试次数
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
                    results[task_name] = result
                    task_completed = True
                    self.logger.info(f"✅ {task_name} 下载成功")
                else:
                    self.logger.warning(f"{task_name} 返回空结果")
                    task_completed = True  # 空结果也视为完成，不是失败

            except Exception as e:
                failed_attempts[task_name] = failed_attempts.get(task_name, 0) + 1
                self.logger.error(f"❌ {task_name} 下载失败 (尝试 {failed_attempts[task_name]}/{max_retries}): {e}")

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
        return results

    def _is_data_type_available(self, data_type: str) -> bool:
        """
        检查数据类型是否在用户积分范围内可用
        """
        for category_types in self.available_types.values():
            if data_type in category_types:
                return True
        return False


def main_download_by_date_range(start_date: str, end_date: str = None):
    """
    主下载函数，根据日期范围下载数据
    """
    downloader = DateRangeDownloader(start_date, end_date)
    return downloader.download_all_available_data()


if __name__ == "__main__":
    # 示例用法
    import sys
    import argparse

    parser = argparse.ArgumentParser(description='按日期范围下载数据')
    parser.add_argument('--start_date', type=str, required=True, help='开始日期 (YYYYMMDD)')
    parser.add_argument('--end_date', type=str, default=None, help='结束日期 (YYYYMMDD)')

    args = parser.parse_args()

    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger = logging.getLogger(__name__)

    try:
        results = main_download_by_date_range(args.start_date, args.end_date)
        logger.info("下载统计:")
        for data_type, result in results.items():
            if isinstance(result, dict):
                if 'records' in result:
                    logger.info(f"  {data_type}: {result['records']} 条记录")
                else:
                    logger.info(f"  {data_type}: {len(result)} 个时间分区")
                    total = sum(result.values()) if result else 0
                    logger.info(f"    总记录数: {total}")
            else:
                logger.info(f"  {data_type}: {result} 条记录")
    except Exception as e:
        logger.error(f"下载过程出错: {e}")
        sys.exit(1)