"""
下载策略基类
定义策略接口，考虑不同参数需求，实现基础策略类
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union
import pandas as pd
import logging
from datetime import datetime
import time
import random

from tushare_api import TuShareDownloader
from config_adapter import ConfigAdapter
from parameter_adapters import ParameterAdapterManager
from data_storage import save_to_parquet
from error_handler import ErrorHandler
from score_config import get_available_data_types


class DownloadStrategy(ABC):
    """
    下载策略抽象基类
    定义所有下载策略的通用接口
    """

    def __init__(self, interface_name: str, downloader: TuShareDownloader = None):
        self.interface_name = interface_name
        self.downloader = downloader or TuShareDownloader()
        self.config_adapter = ConfigAdapter()
        self.param_adapter = ParameterAdapterManager()
        self.logger = logging.getLogger(f"{__name__}.{interface_name}")
        self.max_retries = self.config_adapter.get_max_retries(interface_name)
        self.rate_limit = self.config_adapter.get_rate_limit(interface_name)
        self.batch_size = self.config_adapter.get_batch_size(interface_name)

    @abstractmethod
    def download(self, **kwargs) -> pd.DataFrame:
        """
        执行下载操作，返回DataFrame
        """
        pass

    @abstractmethod
    def get_required_params(self) -> List[str]:
        """
        获取此策略必需的参数列表
        """
        pass

    def apply_rate_limit(self):
        """
        应用速率限制
        """
        # 添加随机延迟以避免API检测
        delay = random.uniform(0.5, 1.5) / self.rate_limit
        time.sleep(delay)

    def handle_error(self, error: Exception, attempt: int, **kwargs) -> bool:
        """
        处理下载错误，返回是否应该重试
        """
        try:
            ErrorHandler.handle_api_error(error, f"{self.interface_name} download attempt {attempt}")
            return True  # If no exception was raised, we can continue
        except Exception:
            # If an exception was raised in the error handler, we should stop retrying
            return attempt < self.max_retries

    def validate_and_adapt_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证并适配参数
        """
        adapted_params = self.param_adapter.adapt_parameters(self.interface_name, params)
        return adapted_params

    def save_data(self, df: pd.DataFrame, filename: str, subdir: str = None) -> str:
        """
        保存数据到Parquet文件
        """
        return save_to_parquet(df, filename, subdir=subdir)


class DailyDataStrategy(DownloadStrategy):
    """
    日度数据下载策略
    适用于 daily, daily_basic, moneyflow 等接口
    """

    def __init__(self, interface_name: str = 'daily', downloader: TuShareDownloader = None):
        super().__init__(interface_name, downloader)

    def download(self, **kwargs) -> pd.DataFrame:
        """
        下载日度数据
        """
        # 验证并适配参数
        adapted_params = self.validate_and_adapt_params(kwargs)

        max_retries = self.max_retries
        for attempt in range(max_retries + 1):
            try:
                self.apply_rate_limit()

                # 根据接口名称调用相应的下载方法
                if self.interface_name == 'daily':
                    start_date = adapted_params.get('start_date')
                    end_date = adapted_params.get('end_date')
                    if start_date and end_date:
                        result = self.downloader.download_daily_data_range(start_date=start_date, end_date=end_date)
                    else:
                        self.logger.error("daily 接口需要 start_date 和 end_date 参数")
                        return pd.DataFrame()
                elif self.interface_name == 'daily_basic':
                    # daily_basic 接口使用 trade_date 参数
                    trade_date = adapted_params.get('trade_date', adapted_params.get('start_date'))
                    if not trade_date:
                        self.logger.error("daily_basic 接口需要 trade_date 或 start_date 参数")
                        return pd.DataFrame()
                    result = self.downloader.download_daily_basic(trade_date=trade_date)
                elif self.interface_name == 'trade_cal':
                    # trade_cal 接口使用 start_date 和 end_date 参数
                    start_date = adapted_params.get('start_date')
                    end_date = adapted_params.get('end_date')
                    if start_date and end_date:
                        result = self.downloader.download_trade_cal(start_date=start_date, end_date=end_date)
                    else:
                        self.logger.error("trade_cal 接口需要 start_date 和 end_date 参数")
                        return pd.DataFrame()
                elif self.interface_name == 'moneyflow':
                    trade_date = adapted_params.get('trade_date', adapted_params.get('start_date'))
                    if trade_date:
                        result = self.downloader.download_moneyflow(trade_date=trade_date)
                    else:
                        start_date = adapted_params.get('start_date')
                        end_date = adapted_params.get('end_date')
                        if start_date and end_date:
                            result = self.downloader.download_daily_moneyflow_range(start_date, end_date)
                        else:
                            self.logger.error("moneyflow 接口需要 trade_date 或 start_date+end_date 参数")
                            return pd.DataFrame()
                elif self.interface_name == 'moneyflow_dc':
                    trade_date = adapted_params.get('trade_date', adapted_params.get('start_date'))
                    if trade_date:
                        result = self.downloader.download_moneyflow_dc(trade_date=trade_date)
                    else:
                        self.logger.error("moneyflow_dc 接口需要 trade_date 参数")
                        return pd.DataFrame()
                elif self.interface_name == 'moneyflow_ths':
                    trade_date = adapted_params.get('trade_date', adapted_params.get('start_date'))
                    if trade_date:
                        result = self.downloader.download_moneyflow_ths(trade_date=trade_date)
                    else:
                        self.logger.error("moneyflow_ths 接口需要 trade_date 参数")
                        return pd.DataFrame()
                elif self.interface_name == 'moneyflow_ind_dc':
                    trade_date = adapted_params.get('trade_date', adapted_params.get('start_date'))
                    if trade_date:
                        result = self.downloader.download_moneyflow_ind_dc(trade_date=trade_date)
                    else:
                        self.logger.error("moneyflow_ind_dc 接口需要 trade_date 参数")
                        return pd.DataFrame()
                elif self.interface_name == 'moneyflow_mkt_dc':
                    trade_date = adapted_params.get('trade_date', adapted_params.get('start_date'))
                    if trade_date:
                        result = self.downloader.download_moneyflow_mkt_dc(trade_date=trade_date)
                    else:
                        self.logger.error("moneyflow_mkt_dc 接口需要 trade_date 参数")
                        return pd.DataFrame()
                elif self.interface_name == 'moneyflow_cnt_ths':
                    trade_date = adapted_params.get('trade_date', adapted_params.get('start_date'))
                    if trade_date:
                        result = self.downloader.download_moneyflow_cnt_ths(trade_date=trade_date)
                    else:
                        self.logger.error("moneyflow_cnt_ths 接口需要 trade_date 参数")
                        return pd.DataFrame()
                elif self.interface_name == 'moneyflow_ind_ths':
                    trade_date = adapted_params.get('trade_date', adapted_params.get('start_date'))
                    if trade_date:
                        result = self.downloader.download_moneyflow_ind_ths(trade_date=trade_date)
                    else:
                        self.logger.error("moneyflow_ind_ths 接口需要 trade_date 参数")
                        return pd.DataFrame()
                elif self.interface_name == 'stk_factor':
                    trade_date = adapted_params.get('trade_date', adapted_params.get('start_date'))
                    if trade_date:
                        result = self.downloader.download_stk_factor_paginated(trade_date=trade_date)
                    else:
                        self.logger.error("stk_factor 接口需要 trade_date 参数")
                        return pd.DataFrame()
                elif self.interface_name == 'stk_factor_pro':
                    trade_date = adapted_params.get('trade_date', adapted_params.get('start_date'))
                    if trade_date:
                        result = self.downloader.download_stk_factor_pro(trade_date=trade_date)
                    else:
                        self.logger.error("stk_factor_pro 接口需要 trade_date 参数")
                        return pd.DataFrame()
                elif self.interface_name == 'cyq_perf':
                    trade_date = adapted_params.get('trade_date', adapted_params.get('start_date'))
                    if trade_date:
                        result = self.downloader.download_cyq_perf_paginated(trade_date=trade_date)
                    else:
                        self.logger.error("cyq_perf 接口需要 trade_date 参数")
                        return pd.DataFrame()
                elif self.interface_name == 'cyq_chips':
                    trade_date = adapted_params.get('trade_date', adapted_params.get('start_date'))
                    if trade_date:
                        result = self.downloader.download_cyq_chips_paginated(trade_date=trade_date)
                    else:
                        self.logger.error("cyq_chips 接口需要 trade_date 参数")
                        return pd.DataFrame()
                else:
                    self.logger.error(f"未知的日度数据接口: {self.interface_name}")
                    return pd.DataFrame()

                self.logger.info(f"成功下载 {self.interface_name} 数据，共 {len(result)} 条记录")
                return result

            except Exception as e:
                if not self.handle_error(e, attempt, **adapted_params):
                    self.logger.error(f"下载 {self.interface_name} 失败，已达到最大重试次数: {e}")
                    break
                else:
                    self.logger.warning(f"下载 {self.interface_name} 失败，第 {attempt + 1} 次尝试: {e}")
                    time.sleep(2 ** attempt)  # 指数退避

        return pd.DataFrame()

    def get_required_params(self) -> List[str]:
        """
        日度数据策略必需的参数
        """
        if self.interface_name in ['daily_basic', 'moneyflow', 'moneyflow_dc', 'moneyflow_ths',
                                  'moneyflow_ind_dc', 'moneyflow_mkt_dc', 'moneyflow_cnt_ths',
                                  'moneyflow_ind_ths', 'stk_factor', 'stk_factor_pro', 'cyq_perf', 'cyq_chips']:
            return ['trade_date']  # 这些接口通常需要交易日期
        else:
            return []


class FinancialDataStrategy(DownloadStrategy):
    """
    财务数据下载策略
    适用于 income, balancesheet, cashflow, fina_indicator 等接口
    """

    def __init__(self, interface_name: str = 'income', downloader: TuShareDownloader = None):
        super().__init__(interface_name, downloader)

    def download(self, **kwargs) -> pd.DataFrame:
        """
        下载财务数据
        """
        from stock_list_manager import StockListManager
        import time
        import itertools

        # 验证并适配参数
        adapted_params = self.validate_and_adapt_params(kwargs)

        max_retries = self.max_retries
        for attempt in range(max_retries + 1):
            try:
                self.apply_rate_limit()

                # 首先尝试使用用户积分判断是否可以使用VIP接口
                from config import TUSHARE_POINTS
                use_vip = TUSHARE_POINTS >= 5000

                # 根据接口名称调用相应的下载方法
                if self.interface_name in ['income', 'balancesheet', 'cashflow', 'fina_indicator']:
                    # 对于财务报表数据，需要特殊的处理逻辑
                    period = adapted_params.get('period')
                    ts_code = adapted_params.get('ts_code')

                    if use_vip and period:
                        # 如果是VIP用户且提供了报告期，优先使用VIP接口
                        try:
                            if self.interface_name == 'income':
                                result = self.downloader.download_income_vip(period=period)
                            elif self.interface_name == 'balancesheet':
                                result = self.downloader.download_balancesheet_vip(period=period)
                            elif self.interface_name == 'cashflow':
                                result = self.downloader.download_cashflow_vip(period=period)
                            elif self.interface_name == 'fina_indicator':
                                result = self.downloader.download_fina_indicator_vip(period=period)
                            else:
                                self.logger.error(f"未知的财务数据接口: {self.interface_name}")
                                return pd.DataFrame()
                        except Exception as vip_error:
                            self.logger.warning(f"VIP接口下载 {self.interface_name} 失败，尝试普通接口: {vip_error}")
                            # 如果VIP接口失败，则使用普通接口循环下载
                            result = self._download_financial_data_batch(ts_code, period)
                    else:
                        # 普通用户或没有报告期参数，使用批量下载
                        result = self._download_financial_data_batch(ts_code, period)
                elif self.interface_name == 'dividend':
                    result = self.downloader.download_dividend(**adapted_params)
                elif self.interface_name == 'forecast':
                    result = self.downloader.download_forecast(**adapted_params)
                elif self.interface_name == 'express':
                    result = self.downloader.download_express(**adapted_params)
                elif self.interface_name in ['top10_holders', 'top10_floatholders']:
                    # 股东数据也需要特殊处理
                    period = adapted_params.get('period')
                    ts_code = adapted_params.get('ts_code')

                    if period and ts_code:
                        if self.interface_name == 'top10_holders':
                            result = self.downloader.download_top10_holders(ts_code=ts_code, period=period)
                        elif self.interface_name == 'top10_floatholders':
                            result = self.downloader.download_top10_floatholders(ts_code=ts_code, period=period)
                    else:
                        # 如果没有特定参数，尝试使用所有股票
                        stock_list = StockListManager().get_stock_basic()
                        result = pd.DataFrame()
                        if not stock_list.empty:
                            for _, stock in stock_list.iterrows():
                                try:
                                    ts_code = stock['ts_code']
                                    if self.interface_name == 'top10_holders':
                                        df = self.downloader.download_top10_holders(ts_code=ts_code, period=period)
                                    elif self.interface_name == 'top10_floatholders':
                                        df = self.downloader.download_top10_floatholders(ts_code=ts_code, period=period)

                                    if not df.empty:
                                        result = pd.concat([result, df], ignore_index=True)
                                    # 应用速率限制
                                    self.apply_rate_limit()
                                except Exception as e:
                                    self.logger.warning(f"下载股票 {ts_code} 的 {self.interface_name} 数据失败: {e}")
                                    continue
                elif self.interface_name == 'stk_surv':
                    result = self.downloader.download_stk_surv(**adapted_params)
                else:
                    self.logger.error(f"未知的财务数据接口: {self.interface_name}")
                    return pd.DataFrame()

                self.logger.info(f"成功下载 {self.interface_name} 数据，共 {len(result)} 条记录")
                return result

            except Exception as e:
                if not self.handle_error(e, attempt, **adapted_params):
                    self.logger.error(f"下载 {self.interface_name} 失败，已达到最大重试次数: {e}")
                    break
                else:
                    self.logger.warning(f"下载 {self.interface_name} 失败，第 {attempt + 1} 次尝试: {e}")
                    time.sleep(2 ** attempt)  # 指数退避

        return pd.DataFrame()

    def _download_financial_data_batch(self, ts_code: str = None, period: str = None) -> pd.DataFrame:
        """
        批量下载财务数据（普通用户方式）
        """
        from stock_list_manager import StockListManager
        import pandas as pd

        result = pd.DataFrame()

        if ts_code:
            # 如果指定了股票代码，直接下载
            try:
                if self.interface_name == 'income':
                    result = self.downloader.download_income(ts_code=ts_code, period=period)
                elif self.interface_name == 'balancesheet':
                    result = self.downloader.download_balancesheet(ts_code=ts_code, period=period)
                elif self.interface_name == 'cashflow':
                    result = self.downloader.download_cashflow(ts_code=ts_code, period=period)
                elif self.interface_name == 'fina_indicator':
                    result = self.downloader.download_fina_indicator(ts_code=ts_code, period=period)
            except Exception as e:
                self.logger.error(f"下载股票 {ts_code} 的 {self.interface_name} 数据失败: {e}")
        else:
            # 如果没有指定股票代码，获取所有股票并批量下载
            stock_list = StockListManager().get_stock_basic()
            if not stock_list.empty:
                for _, stock in stock_list.iterrows():
                    try:
                        ts_code = stock['ts_code']
                        if self.interface_name == 'income':
                            df = self.downloader.download_income(ts_code=ts_code, period=period)
                        elif self.interface_name == 'balancesheet':
                            df = self.downloader.download_balancesheet(ts_code=ts_code, period=period)
                        elif self.interface_name == 'cashflow':
                            df = self.downloader.download_cashflow(ts_code=ts_code, period=period)
                        elif self.interface_name == 'fina_indicator':
                            df = self.downloader.download_fina_indicator(ts_code=ts_code, period=period)

                        if not df.empty:
                            result = pd.concat([result, df], ignore_index=True)
                        # 应用速率限制
                        self.apply_rate_limit()
                    except Exception as e:
                        self.logger.warning(f"下载股票 {ts_code} 的 {self.interface_name} 数据失败: {e}")
                        continue

        return result

    def get_required_params(self) -> List[str]:
        """
        财务数据策略必需的参数
        """
        if self.interface_name in ['income', 'balancesheet', 'cashflow', 'fina_indicator',
                                  'top10_holders', 'top10_floatholders']:
            return ['period']  # 财务数据通常需要报告期
        else:
            return []


class StaticDataStrategy(DownloadStrategy):
    """
    静态数据下载策略
    适用于 stock_basic, trade_cal, namechange 等接口
    """

    def __init__(self, interface_name: str = 'stock_basic', downloader: TuShareDownloader = None):
        super().__init__(interface_name, downloader)

    def download(self, **kwargs) -> pd.DataFrame:
        """
        下载静态数据
        """
        # 验证并适配参数
        adapted_params = self.validate_and_adapt_params(kwargs)

        max_retries = self.max_retries
        for attempt in range(max_retries + 1):
            try:
                self.apply_rate_limit()

                # 根据接口名称调用相应的下载方法
                if self.interface_name == 'stock_basic':
                    result = self.downloader.download_stock_basic(**adapted_params)
                elif self.interface_name == 'trade_cal':
                    result = self.downloader.download_trade_cal(**adapted_params)
                elif self.interface_name == 'new_share':
                    result = self.downloader.download_new_share(**adapted_params)
                elif self.interface_name == 'stock_company':
                    result = self.downloader.download_stock_company(**adapted_params)
                elif self.interface_name == 'stock_st':
                    result = self.downloader.download_stock_st(**adapted_params)
                elif self.interface_name == 'bak_basic':
                    result = self.downloader.download_bak_basic(**adapted_params)
                elif self.interface_name == 'namechange':
                    result = self.downloader.download_namechange(**adapted_params)
                elif self.interface_name == 'stk_rewards':
                    result = self.downloader.download_stk_rewards(**adapted_params)
                elif self.interface_name == 'stk_managers':
                    result = self.downloader.download_stk_managers(**adapted_params)
                elif self.interface_name == 'broker_recommend':
                    result = self.downloader.download_broker_recommend(**adapted_params)
                else:
                    self.logger.error(f"未知的静态数据接口: {self.interface_name}")
                    return pd.DataFrame()

                self.logger.info(f"成功下载 {self.interface_name} 数据，共 {len(result)} 条记录")
                return result

            except Exception as e:
                if not self.handle_error(e, attempt, **adapted_params):
                    self.logger.error(f"下载 {self.interface_name} 失败，已达到最大重试次数: {e}")
                    break
                else:
                    self.logger.warning(f"下载 {self.interface_name} 失败，第 {attempt + 1} 次尝试: {e}")
                    time.sleep(2 ** attempt)  # 指数退避

        return pd.DataFrame()

    def get_required_params(self) -> List[str]:
        """
        静态数据策略必需的参数
        """
        # 大多数静态数据接口不需要必需参数
        return []


def get_strategy(interface_name: str, downloader: TuShareDownloader = None) -> DownloadStrategy:
    """
    获取指定接口的下载策略（延迟导入避免循环依赖）
    """
    from strategy_factory import get_strategy as get_strategy_from_factory
    return get_strategy_from_factory(interface_name, downloader=downloader)


def create_strategy(interface_name: str, downloader: TuShareDownloader = None) -> DownloadStrategy:
    """
    创建指定接口的下载策略（延迟导入避免循环依赖）
    """
    from strategy_factory import create_strategy as create_strategy_from_factory
    return create_strategy_from_factory(interface_name, downloader=downloader)


def get_available_strategies() -> List[str]:
    """
    获取所有可用策略列表（延迟导入避免循环依赖）
    """
    from strategy_factory import get_available_strategies as get_available_strategies_from_factory
    return get_available_strategies_from_factory()