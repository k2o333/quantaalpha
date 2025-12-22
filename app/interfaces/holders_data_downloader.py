"""
股东数据全历史下载器
为必须传递股票代码参数的接口实现全历史下载功能
"""
import pandas as pd
import logging
from typing import List
from datetime import datetime
try:
    from ..config import TUSHARE_POINTS
except ImportError:
    from config import TUSHARE_POINTS
try:
    from ..error_handler import ErrorHandler, retry_on_failure
except ImportError:
    from error_handler import ErrorHandler, retry_on_failure
try:
    from ..data_storage import save_to_parquet
except ImportError:
    from data_storage import save_to_parquet


class HoldersDataFullHistoryDownloader:
    def __init__(self, pro_api, stock_list=None):
        self.pro = pro_api
        self.stock_list = stock_list
        self.logger = logging.getLogger(__name__)

    def get_all_stock_codes(self) -> List[str]:
        """
        获取所有股票代码列表
        """
        try:
            # 如果已经提供了股票列表，直接使用
            if self.stock_list is not None and not self.stock_list.empty:
                return self.stock_list['ts_code'].tolist()

            # 否则通过API获取股票列表
            from .basic_data import BasicDataDownloader
            basic_downloader = BasicDataDownloader(self.pro)
            stock_list = basic_downloader.download_stock_basic()

            if stock_list.empty:
                self.logger.warning("No stock list available")
                return []

            return stock_list['ts_code'].tolist()
        except Exception as e:
            self.logger.error(f"Failed to get stock list: {e}")
            return []

    def download_stk_rewards_full_history(self, save_to_disk: bool = True) -> pd.DataFrame:
        """
        下载所有股票的管理层薪酬和持股全历史数据
        """
        if TUSHARE_POINTS < 2000:
            self.logger.warning("stk_rewards requires 2000+ points, skipping download")
            return pd.DataFrame()

        try:
            # 获取所有股票代码
            stock_codes = self.get_all_stock_codes()
            if not stock_codes:
                self.logger.warning("No stock codes available for stk_rewards download")
                return pd.DataFrame()

            all_data = []
            self.logger.info(f"Starting to download stk_rewards for {len(stock_codes)} stocks")

            # 逐个下载每个股票的数据
            for i, ts_code in enumerate(stock_codes):
                if (i + 1) % 100 == 0:  # 每100个股票记录一次进度
                    self.logger.info(f"Processed {i + 1}/{len(stock_codes)} stocks for stk_rewards...")

                try:
                    # 从holders_data模块导入下载方法
                    from .holders_data import HoldersDataDownloader
                    downloader = HoldersDataDownloader(self.pro)
                    df = downloader.download_stk_rewards(ts_code)

                    if df is not None and not df.empty:
                        all_data.append(df)
                    else:
                        self.logger.debug(f"No stk_rewards data for {ts_code}")
                except Exception as e:
                    self.logger.warning(f"Failed to download stk_rewards for {ts_code}: {e}")
                    continue

            # 合并所有数据
            if all_data:
                result = pd.concat(all_data, ignore_index=True)
                self.logger.info(f"Successfully downloaded stk_rewards full history: {len(result)} records")

                # 保存到磁盘
                if save_to_disk:
                    try:
                        save_to_parquet(result, "stk_rewards_full_history", "holders")
                        self.logger.info("Successfully saved stk_rewards full history to disk")
                    except Exception as e:
                        self.logger.error(f"Failed to save stk_rewards full history to disk: {e}")

                return result
            else:
                self.logger.warning("No stk_rewards data could be downloaded for any stock")
                return pd.DataFrame()

        except Exception as e:
            self.logger.error(f"Failed to download stk_rewards full history: {e}")
            ErrorHandler.handle_api_error(e, "download_stk_rewards_full_history")
            raise

    def download_top10_holders_full_history(self, save_to_disk: bool = True) -> pd.DataFrame:
        """
        下载所有股票的前十大股东全历史数据（不传日期参数）
        """
        if TUSHARE_POINTS < 2000:
            self.logger.warning("top10_holders requires 2000+ points, skipping download")
            return pd.DataFrame()

        try:
            # 获取所有股票代码
            stock_codes = self.get_all_stock_codes()
            if not stock_codes:
                self.logger.warning("No stock codes available for top10_holders download")
                return pd.DataFrame()

            all_data = []
            self.logger.info(f"Starting to download top10_holders for {len(stock_codes)} stocks")

            # 逐个下载每个股票的数据
            for i, ts_code in enumerate(stock_codes):
                if (i + 1) % 100 == 0:  # 每100个股票记录一次进度
                    self.logger.info(f"Processed {i + 1}/{len(stock_codes)} stocks for top10_holders...")

                try:
                    # 从holders_data模块导入下载方法
                    from .holders_data import HoldersDataDownloader
                    downloader = HoldersDataDownloader(self.pro)
                    df = downloader.download_top10_holders(ts_code)  # 不传period参数

                    if df is not None and not df.empty:
                        all_data.append(df)
                    else:
                        self.logger.debug(f"No top10_holders data for {ts_code}")
                except Exception as e:
                    self.logger.warning(f"Failed to download top10_holders for {ts_code}: {e}")
                    continue

            # 合并所有数据
            if all_data:
                result = pd.concat(all_data, ignore_index=True)
                self.logger.info(f"Successfully downloaded top10_holders full history: {len(result)} records")

                # 保存到磁盘
                if save_to_disk:
                    try:
                        save_to_parquet(result, "top10_holders_full_history", "holders")
                        self.logger.info("Successfully saved top10_holders full history to disk")
                    except Exception as e:
                        self.logger.error(f"Failed to save top10_holders full history to disk: {e}")

                return result
            else:
                self.logger.warning("No top10_holders data could be downloaded for any stock")
                return pd.DataFrame()

        except Exception as e:
            self.logger.error(f"Failed to download top10_holders full history: {e}")
            ErrorHandler.handle_api_error(e, "download_top10_holders_full_history")
            raise

    def download_pledge_detail_full_history(self, save_to_disk: bool = True) -> pd.DataFrame:
        """
        下载所有股票的股权质押明细全历史数据（通过分页获取）
        """
        if TUSHARE_POINTS < 5000:
            self.logger.warning("pledge_detail requires 5000+ points, skipping download")
            return pd.DataFrame()

        try:
            # 获取所有股票代码
            stock_codes = self.get_all_stock_codes()
            if not stock_codes:
                self.logger.warning("No stock codes available for pledge_detail download")
                return pd.DataFrame()

            all_data = []
            self.logger.info(f"Starting to download pledge_detail for {len(stock_codes)} stocks")

            # 逐个下载每个股票的数据
            for i, ts_code in enumerate(stock_codes):
                if (i + 1) % 100 == 0:  # 每100个股票记录一次进度
                    self.logger.info(f"Processed {i + 1}/{len(stock_codes)} stocks for pledge_detail...")

                try:
                    # 从holders_data模块导入下载方法
                    from .holders_data import HoldersDataDownloader
                    downloader = HoldersDataDownloader(self.pro)
                    df = downloader.download_pledge_detail(ts_code)

                    if df is not None and not df.empty:
                        all_data.append(df)
                    else:
                        self.logger.debug(f"No pledge_detail data for {ts_code}")
                except Exception as e:
                    self.logger.warning(f"Failed to download pledge_detail for {ts_code}: {e}")
                    continue

            # 合并所有数据
            if all_data:
                result = pd.concat(all_data, ignore_index=True)
                self.logger.info(f"Successfully downloaded pledge_detail full history: {len(result)} records")

                # 保存到磁盘
                if save_to_disk:
                    try:
                        save_to_parquet(result, "pledge_detail_full_history", "holders")
                        self.logger.info("Successfully saved pledge_detail full history to disk")
                    except Exception as e:
                        self.logger.error(f"Failed to save pledge_detail full history to disk: {e}")

                return result
            else:
                self.logger.warning("No pledge_detail data could be downloaded for any stock")
                return pd.DataFrame()

        except Exception as e:
            self.logger.error(f"Failed to download pledge_detail full history: {e}")
            ErrorHandler.handle_api_error(e, "download_pledge_detail_full_history")
            raise

    def download_fina_audit_full_history(self, save_to_disk: bool = True) -> pd.DataFrame:
        """
        下载所有股票的财务审计意见全历史数据（不传日期参数）
        """
        if TUSHARE_POINTS < 500:
            self.logger.warning("fina_audit requires 500+ points, skipping download")
            return pd.DataFrame()

        try:
            # 获取所有股票代码
            stock_codes = self.get_all_stock_codes()
            if not stock_codes:
                self.logger.warning("No stock codes available for fina_audit download")
                return pd.DataFrame()

            all_data = []
            self.logger.info(f"Starting to download fina_audit for {len(stock_codes)} stocks")

            # 逐个下载每个股票的数据
            for i, ts_code in enumerate(stock_codes):
                if (i + 1) % 100 == 0:  # 每100个股票记录一次进度
                    self.logger.info(f"Processed {i + 1}/{len(stock_codes)} stocks for fina_audit...")

                try:
                    # 从financial_data模块导入下载方法
                    from .financial_data import FinancialDataDownloader
                    downloader = FinancialDataDownloader(self.pro)
                    df = downloader.download_fina_audit(ts_code=ts_code)  # 不传period参数

                    if df is not None and not df.empty:
                        all_data.append(df)
                    else:
                        self.logger.debug(f"No fina_audit data for {ts_code}")
                except Exception as e:
                    self.logger.warning(f"Failed to download fina_audit for {ts_code}: {e}")
                    continue

            # 合并所有数据
            if all_data:
                result = pd.concat(all_data, ignore_index=True)
                self.logger.info(f"Successfully downloaded fina_audit full history: {len(result)} records")

                # 保存到磁盘
                if save_to_disk:
                    try:
                        save_to_parquet(result, "fina_audit_full_history", "financial")
                        self.logger.info("Successfully saved fina_audit full history to disk")
                    except Exception as e:
                        self.logger.error(f"Failed to save fina_audit full history to disk: {e}")

                return result
            else:
                self.logger.warning("No fina_audit data could be downloaded for any stock")
                return pd.DataFrame()

        except Exception as e:
            self.logger.error(f"Failed to download fina_audit full history: {e}")
            ErrorHandler.handle_api_error(e, "download_fina_audit_full_history")
            raise

    def download_pro_bar_full_history_all_stocks(self, save_to_disk: bool = True) -> pd.DataFrame:
        """
        下载所有股票的复权行情全历史数据（从上市日到今天）
        """
        if TUSHARE_POINTS < 5000:
            self.logger.warning("pro_bar requires 5000+ points, skipping download")
            return pd.DataFrame()

        try:
            # 获取所有股票代码
            stock_codes = self.get_all_stock_codes()
            if not stock_codes:
                self.logger.warning("No stock codes available for pro_bar download")
                return pd.DataFrame()

            all_data = []
            self.logger.info(f"Starting to download pro_bar full history for {len(stock_codes)} stocks")

            # 逐个下载每个股票的数据
            for i, ts_code in enumerate(stock_codes):
                if (i + 1) % 100 == 0:  # 每100个股票记录一次进度
                    self.logger.info(f"Processed {i + 1}/{len(stock_codes)} stocks for pro_bar...")

                try:
                    # 从daily_data模块导入下载方法
                    from .daily_data import DailyDataDownloader
                    downloader = DailyDataDownloader(self.pro)
                    df = downloader.download_pro_bar_full_history(ts_code)

                    if df is not None and not df.empty:
                        all_data.append(df)
                    else:
                        self.logger.debug(f"No pro_bar data for {ts_code}")
                except Exception as e:
                    self.logger.warning(f"Failed to download pro_bar for {ts_code}: {e}")
                    continue

            # 合并所有数据
            if all_data:
                result = pd.concat(all_data, ignore_index=True)
                self.logger.info(f"Successfully downloaded pro_bar full history: {len(result)} records")

                # 保存到磁盘
                if save_to_disk:
                    try:
                        save_to_parquet(result, "pro_bar_full_history", "daily")
                        self.logger.info("Successfully saved pro_bar full history to disk")
                    except Exception as e:
                        self.logger.error(f"Failed to save pro_bar full history to disk: {e}")

                return result
            else:
                self.logger.warning("No pro_bar data could be downloaded for any stock")
                return pd.DataFrame()

        except Exception as e:
            self.logger.error(f"Failed to download pro_bar full history: {e}")
            ErrorHandler.handle_api_error(e, "download_pro_bar_full_history_all_stocks")
            raise