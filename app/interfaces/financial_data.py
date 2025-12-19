"""
财务数据接口模块
包含income, balancesheet, cashflow等财务接口
"""
import pandas as pd
import logging
try:
    from ..config import TUSHARE_POINTS
except ImportError:
    from config import TUSHARE_POINTS
try:
    from ..error_handler import ErrorHandler, retry_on_failure
except ImportError:
    from error_handler import ErrorHandler, retry_on_failure


class FinancialDataDownloader:
    def __init__(self, pro_api):
        self.pro = pro_api
        self.logger = logging.getLogger(__name__)

    @retry_on_failure(max_retries=3, delay=1.0, backoff=2.0)
    def download_with_retry(self, api_func, *args, max_retries: int = 3, **kwargs):
        """
        Download data with retry mechanism and rate limiting
        """
        api_name = api_func.__name__ if hasattr(api_func, '__name__') else 'unknown_api'

        for attempt in range(max_retries + 1):
            try:
                # Log the API call
                self.logger.info(f"Calling {api_name} API attempt {attempt + 1}")

                # Make the API call
                result = api_func(*args, **kwargs)

                self.logger.info(f"Successfully called {api_name}, got {len(result) if hasattr(result, '__len__') else 'unknown'} records")
                return result

            except Exception as e:
                self.logger.warning(f"Attempt {attempt + 1} failed for {api_name}: {str(e)}")

                if attempt == max_retries:
                    self.logger.error(f"All {max_retries + 1} attempts failed for {api_name}")
                    ErrorHandler.handle_api_error(e, f"API call {api_name}")

    def download_income(self, period: str = None, ts_code: str = None) -> pd.DataFrame:
        """
        下载利润表数据
        智能选择VIP或普通接口
        """
        if TUSHARE_POINTS < 2000:
            self.logger.warning("income requires 2000+ points, skipping download")
            return pd.DataFrame()

        try:
            if TUSHARE_POINTS >= 5000 and period is not None and ts_code is None:
                # 使用VIP接口获取全市场数据
                return self.download_income_vip(period)
            else:
                # 使用普通接口
                return self.download_income_normal(period, ts_code)
        except Exception as e:
            self.logger.error(f"Failed to download income statement: {e}")
            ErrorHandler.handle_api_error(e, "download_income")
            raise

    def download_income_normal(self, period: str = None, ts_code: str = None) -> pd.DataFrame:
        """
        使用普通接口下载利润表数据
        """
        params = {}
        if period:
            params['period'] = period
        if ts_code:
            params['ts_code'] = ts_code

        result = self.download_with_retry(
            self.pro.income,
            **params
        )
        self.logger.info(f"Successfully downloaded income statement: {len(result)} records")
        return result

    def download_income_vip(self, period: str) -> pd.DataFrame:
        """
        使用VIP接口下载全市场利润表数据
        """
        result = self.download_with_retry(
            self.pro.income_vip,
            period=period
        )
        self.logger.info(f"Successfully downloaded income statement VIP: {len(result)} records")
        return result

    def download_balancesheet(self, period: str = None, ts_code: str = None) -> pd.DataFrame:
        """
        下载资产负债表数据
        智能选择VIP或普通接口
        """
        if TUSHARE_POINTS < 2000:
            self.logger.warning("balancesheet requires 2000+ points, skipping download")
            return pd.DataFrame()

        try:
            if TUSHARE_POINTS >= 5000 and period is not None and ts_code is None:
                # 使用VIP接口获取全市场数据
                return self.download_balancesheet_vip(period)
            else:
                # 使用普通接口
                return self.download_balancesheet_normal(period, ts_code)
        except Exception as e:
            self.logger.error(f"Failed to download balance sheet: {e}")
            ErrorHandler.handle_api_error(e, "download_balancesheet")
            raise

    def download_balancesheet_normal(self, period: str = None, ts_code: str = None) -> pd.DataFrame:
        """
        使用普通接口下载资产负债表数据
        """
        params = {}
        if period:
            params['period'] = period
        if ts_code:
            params['ts_code'] = ts_code

        result = self.download_with_retry(
            self.pro.balancesheet,
            **params
        )
        self.logger.info(f"Successfully downloaded balance sheet: {len(result)} records")
        return result

    def download_balancesheet_vip(self, period: str) -> pd.DataFrame:
        """
        使用VIP接口下载全市场资产负债表数据
        """
        result = self.download_with_retry(
            self.pro.balancesheet_vip,
            period=period
        )
        self.logger.info(f"Successfully downloaded balance sheet VIP: {len(result)} records")
        return result

    def download_cashflow(self, period: str = None, ts_code: str = None) -> pd.DataFrame:
        """
        下载现金流量表数据
        智能选择VIP或普通接口
        """
        if TUSHARE_POINTS < 2000:
            self.logger.warning("cashflow requires 2000+ points, skipping download")
            return pd.DataFrame()

        try:
            if TUSHARE_POINTS >= 5000 and period is not None and ts_code is None:
                # 使用VIP接口获取全市场数据
                return self.download_cashflow_vip(period)
            else:
                # 使用普通接口
                return self.download_cashflow_normal(period, ts_code)
        except Exception as e:
            self.logger.error(f"Failed to download cash flow: {e}")
            ErrorHandler.handle_api_error(e, "download_cashflow")
            raise

    def download_cashflow_normal(self, period: str = None, ts_code: str = None) -> pd.DataFrame:
        """
        使用普通接口下载现金流量表数据
        """
        params = {}
        if period:
            params['period'] = period
        if ts_code:
            params['ts_code'] = ts_code

        result = self.download_with_retry(
            self.pro.cashflow,
            **params
        )
        self.logger.info(f"Successfully downloaded cash flow: {len(result)} records")
        return result

    def download_cashflow_vip(self, period: str) -> pd.DataFrame:
        """
        使用VIP接口下载全市场现金流量表数据
        """
        result = self.download_with_retry(
            self.pro.cashflow_vip,
            period=period
        )
        self.logger.info(f"Successfully downloaded cash flow VIP: {len(result)} records")
        return result

    def download_fina_indicator(self, period: str = None, ts_code: str = None) -> pd.DataFrame:
        """
        下载财务指标数据
        智能选择VIP或普通接口
        """
        if TUSHARE_POINTS < 2000:
            self.logger.warning("fina_indicator requires 2000+ points, skipping download")
            return pd.DataFrame()

        try:
            if TUSHARE_POINTS >= 5000 and period is not None and ts_code is None:
                # 使用VIP接口获取全市场数据
                return self.download_fina_indicator_vip(period)
            else:
                # 使用普通接口
                return self.download_fina_indicator_normal(period, ts_code)
        except Exception as e:
            self.logger.error(f"Failed to download financial indicators: {e}")
            ErrorHandler.handle_api_error(e, "download_fina_indicator")
            raise

    def download_fina_indicator_normal(self, period: str = None, ts_code: str = None) -> pd.DataFrame:
        """
        使用普通接口下载财务指标数据
        """
        params = {}
        if period:
            params['period'] = period
        if ts_code:
            params['ts_code'] = ts_code

        result = self.download_with_retry(
            self.pro.fina_indicator,
            **params
        )
        self.logger.info(f"Successfully downloaded financial indicators: {len(result)} records")
        return result

    def download_fina_indicator_vip(self, period: str) -> pd.DataFrame:
        """
        使用VIP接口下载全市场财务指标数据
        """
        result = self.download_with_retry(
            self.pro.fina_indicator_vip,
            period=period
        )
        self.logger.info(f"Successfully downloaded financial indicators VIP: {len(result)} records")
        return result

    def download_forecast(self, period: str = '20231231', ts_code: str = None) -> pd.DataFrame:
        """
        Download earnings forecast
        Available to users with 2000+ points
        Uses VIP version if user has 5000+ points, falls back to per-stock download if needed
        """
        if TUSHARE_POINTS < 2000:
            self.logger.warning("forecast requires 2000+ points, skipping download")
            return pd.DataFrame()

        try:
            # Use VIP version if available (5000+ points) for full market data
            if TUSHARE_POINTS >= 5000 and ts_code is None:
                # Use VIP interface to get full market data
                result = self.download_with_retry(
                    self.pro.forecast_vip,
                    period=period
                )
                self.logger.info(f"Successfully downloaded forecast_vip: {len(result)} records")
                return result
            else:
                # For users with lower points or specific stock request, use normal interface
                if ts_code:
                    # Download specific stock
                    result = self.download_with_retry(
                        self.pro.forecast,
                        ts_code=ts_code,
                        period=period
                    )
                    self.logger.info(f"Successfully downloaded forecast for {ts_code}: {len(result)} records")
                    return result
                else:
                    # Get stock list first and download for all stocks
                    from .basic_data import BasicDataDownloader
                    basic_downloader = BasicDataDownloader(self.pro)
                    stock_df = basic_downloader.download_stock_basic()
                    all_data = []
                    for _, stock in stock_df.iterrows():
                        ts_code = stock['ts_code']
                        try:
                            df = self.download_with_retry(
                                self.pro.forecast,
                                ts_code=ts_code,
                                period=period
                            )
                            if df is not None and not df.empty:
                                all_data.append(df)
                        except Exception as e:
                            self.logger.warning(f"Failed to download forecast for {ts_code}: {e}")
                            continue  # Continue with next stock even if one fails

                    # Combine all data
                    if all_data:
                        result = pd.concat(all_data, ignore_index=True)
                        self.logger.info(f"Successfully downloaded forecast for multiple stocks: {len(result)} records")
                        return result
                    else:
                        self.logger.warning("No forecast data could be downloaded for any stock")
                        return pd.DataFrame()
        except Exception as e:
            self.logger.error(f"Failed to download forecast: {e}")
            ErrorHandler.handle_api_error(e, "download_forecast")
            raise

    def download_express(self, period: str = '20231231') -> pd.DataFrame:
        """
        Download earnings express (fast report)
        Available to users with 2000+ points
        Uses VIP version if user has 5000+ points, falls back to per-stock download if needed
        """
        if TUSHARE_POINTS < 2000:
            self.logger.warning("express requires 2000+ points, skipping download")
            return pd.DataFrame()

        try:
            # Use VIP version if available (5000+ points) for full market data
            if TUSHARE_POINTS >= 5000:
                # Use VIP interface to get full market data
                result = self.download_with_retry(
                    self.pro.express_vip,
                    period=period
                )
                self.logger.info(f"Successfully downloaded express_vip: {len(result)} records")
                return result
            else:
                # For users with lower points, fall back to per-stock download
                # Get stock list first
                from .basic_data import BasicDataDownloader
                basic_downloader = BasicDataDownloader(self.pro)
                stock_df = basic_downloader.download_stock_basic()
                all_data = []
                for _, stock in stock_df.iterrows():
                    ts_code = stock['ts_code']
                    try:
                        df = self.download_with_retry(
                            self.pro.express,
                            ts_code=ts_code,
                            period=period
                        )
                        if df is not None and not df.empty:
                            all_data.append(df)
                    except Exception as e:
                        self.logger.warning(f"Failed to download express for {ts_code}: {e}")
                        continue  # Continue with next stock even if one fails

                # Combine all data
                if all_data:
                    result = pd.concat(all_data, ignore_index=True)
                    self.logger.info(f"Successfully downloaded express for multiple stocks: {len(result)} records")
                    return result
                else:
                    self.logger.warning("No express data could be downloaded for any stock")
                    return pd.DataFrame()
        except Exception as e:
            self.logger.error(f"Failed to download express: {e}")
            ErrorHandler.handle_api_error(e, "download_express")
            raise

    def download_fina_audit(self, period: str = '20231231', ts_code: str = None) -> pd.DataFrame:
        """
        Download financial audit opinions
        Available to users with 500+ points
        """
        if TUSHARE_POINTS < 500:
            self.logger.warning("fina_audit requires 500+ points, skipping download")
            return pd.DataFrame()

        try:
            params = {'period': period}
            if ts_code:
                params['ts_code'] = ts_code

            result = self.download_with_retry(
                self.pro.fina_audit,
                **params
            )
            self.logger.info(f"Successfully downloaded fina_audit: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download fina_audit: {e}")
            ErrorHandler.handle_api_error(e, "download_fina_audit")
            raise

    def download_fina_mainbz(self, period: str = '20231231', ts_code: str = None, type_: str = 'P') -> pd.DataFrame:
        """
        Download main business composition (by product or region)
        Available to users with 2000+ points
        Uses VIP version if user has 5000+ points
        """
        if TUSHARE_POINTS < 2000:
            self.logger.warning("fina_mainbz requires 2000+ points, skipping download")
            return pd.DataFrame()

        try:
            # Use VIP version if available (5000+ points) for full market data
            if TUSHARE_POINTS >= 5000 and ts_code is None:
                # Use VIP interface to get full market data
                result = self.download_with_retry(
                    self.pro.fina_mainbz_vip,
                    period=period,
                    type=type_
                )
                self.logger.info(f"Successfully downloaded fina_mainbz_vip: {len(result)} records")
                return result
            else:
                # For users with lower points or specific stock request, use normal interface
                params = {'period': period, 'type': type_}
                if ts_code:
                    params['ts_code'] = ts_code

                result = self.download_with_retry(
                    self.pro.fina_mainbz,
                    **params
                )
                self.logger.info(f"Successfully downloaded fina_mainbz: {len(result)} records")
                return result
        except Exception as e:
            self.logger.error(f"Failed to download fina_mainbz: {e}")
            ErrorHandler.handle_api_error(e, "download_fina_mainbz")
            raise

    def download_disclosure_date(self, ann_date: str = '20231201') -> pd.DataFrame:
        """
        Download financial report disclosure schedule
        Available to users with 500+ points
        """
        if TUSHARE_POINTS < 500:
            self.logger.warning("disclosure_date requires 500+ points, skipping download")
            return pd.DataFrame()

        try:
            result = self.download_with_retry(
                self.pro.disclosure_date,
                ann_date=ann_date
            )
            self.logger.info(f"Successfully downloaded disclosure_date: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download disclosure_date: {e}")
            ErrorHandler.handle_api_error(e, "download_disclosure_date")
            raise