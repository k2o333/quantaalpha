"""
研究数据接口模块
包含report_rc, stk_surv等研究相关接口
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


class ResearchDataDownloader:
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

    def download_report_rc(self, period: str = '20231231', ts_code: str = None) -> pd.DataFrame:
        """
        Download sell-side earnings forecast data
        Available to users with 5000+ points (8000+ for formal access)
        """
        if TUSHARE_POINTS < 5000:
            self.logger.warning("report_rc requires 5000+ points, skipping download")
            return pd.DataFrame()

        try:
            params = {'period': period}
            if ts_code:
                params['ts_code'] = ts_code

            result = self.download_with_retry(
                self.pro.report_rc,
                **params
            )
            self.logger.info(f"Successfully downloaded report_rc: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download report_rc: {e}")
            ErrorHandler.handle_api_error(e, "download_report_rc")
            raise

    def download_stk_surv(self, period: str = '20231231', ts_code: str = None) -> pd.DataFrame:
        """
        Download institutional research survey
        Available to users with 5000+ points
        """
        if TUSHARE_POINTS < 5000:
            self.logger.warning("stk_surv requires 5000+ points, skipping download")
            return pd.DataFrame()

        try:
            params = {'period': period}
            if ts_code:
                params['ts_code'] = ts_code

            result = self.download_with_retry(
                self.pro.stk_surv,
                **params
            )
            self.logger.info(f"Successfully downloaded stk_surv: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download stk_surv: {e}")
            ErrorHandler.handle_api_error(e, "download_stk_surv")
            raise

    def download_broker_recommend(self, month: str) -> pd.DataFrame:
        """
        Download broker monthly stock recommendations
        Available to users with 2000+ points
        Must provide month parameter in YYYYMM format
        """
        if TUSHARE_POINTS < 2000:
            self.logger.warning("broker_recommend requires 2000+ points, skipping download")
            return pd.DataFrame()

        try:
            result = self.download_with_retry(
                self.pro.broker_recommend,
                month=month
            )
            self.logger.info(f"Successfully downloaded broker_recommend: {len(result)} records")
            return result
        except Exception as e:
            self.logger.error(f"Failed to download broker_recommend: {e}")
            ErrorHandler.handle_api_error(e, "download_broker_recommend")
            raise

    def download_report_rc_range(self, start_period: str, end_period: str) -> pd.DataFrame:
        """
        按报告期范围下载卖方盈利预测数据
        """
        if TUSHARE_POINTS < 5000:
            self.logger.warning("report_rc requires 5000+ points, skipping download")
            return pd.DataFrame()

        try:
            # 这里需要根据具体的报告期格式来处理，假设是季度格式
            # 实际实现应根据具体的报告期格式进行调整
            periods = self.get_quarter_periods(start_period, end_period)
            all_data = []

            self.logger.info(f"Starting to download report_rc for {len(periods)} periods")

            for i, period in enumerate(periods):
                if (i + 1) % 5 == 0:  # Log progress every 5 periods
                    self.logger.info(f"Processed {i + 1}/{len(periods)} periods...")

                try:
                    df = self.download_report_rc(period=period)
                    if df is not None and not df.empty:
                        all_data.append(df)
                    else:
                        self.logger.debug(f"No report_rc data for period {period}")
                except Exception as e:
                    self.logger.warning(f"Failed to download report_rc for period {period}: {e}")
                    continue  # Continue with next period even if one fails

            # Combine all data
            if all_data:
                result = pd.concat(all_data, ignore_index=True)
                self.logger.info(f"Successfully downloaded report_rc for period range: {len(result)} records")
                return result
            else:
                self.logger.warning("No report_rc data could be downloaded for the period range")
                return pd.DataFrame()

        except Exception as e:
            self.logger.error(f"Failed to download report_rc for period range: {e}")
            ErrorHandler.handle_api_error(e, "download_report_rc_range")
            raise

    def get_quarter_periods(self, start_period: str, end_period: str) -> list:
        """
        生成季度报告期列表
        """
        # 简化的季度生成逻辑，实际实现可能需要更复杂的处理
        periods = []
        current_year = int(start_period[:4])
        end_year = int(end_period[:4])

        for year in range(current_year, end_year + 1):
            for quarter in ['0331', '0630', '0930', '1231']:
                period = f"{year}{quarter}"
                if period >= start_period and period <= end_period:
                    periods.append(period)

        return periods

    def download_report_rc_paginated(self, period: str, ts_code: str = None, limit_per_call: int = 3000) -> pd.DataFrame:
        """
        分页下载report_rc数据
        """
        base_params = {'period': period}
        if ts_code:
            base_params['ts_code'] = ts_code

        return self.download_with_pagination(
            lambda **kwargs: self.pro.report_rc(**kwargs),
            limit_per_call=limit_per_call,
            **base_params
        )

    def download_broker_recommend_paginated(self, month: str, limit_per_call: int = 1000) -> pd.DataFrame:
        """
        分页下载broker_recommend数据
        """
        return self.download_with_pagination(
            lambda **kwargs: self.pro.broker_recommend(**kwargs),
            limit_per_call=limit_per_call,
            month=month
        )

    def download_with_pagination(self, api_func, limit_per_call=2000, **base_kwargs):
        """
        分页下载数据的通用函数
        """
        all_data = []
        offset = 0

        while True:
            # 添加分页参数
            kwargs = base_kwargs.copy()
            kwargs['offset'] = offset
            kwargs['limit'] = limit_per_call

            try:
                data = api_func(**kwargs)
            except Exception as e:
                self.logger.error(f"分页下载失败, offset={offset}: {e}")
                break

            if data is None or len(data) == 0:
                break

            # 将DataFrame添加到列表中，而不是扩展DataFrame
            all_data.append(data)

            # 如果返回数据少于限制数量，说明已到最后一页
            if len(data) < limit_per_call:
                break

            offset += limit_per_call

        # 将所有数据合并成一个DataFrame
        if all_data:
            return pd.concat(all_data, ignore_index=True)
        else:
            return pd.DataFrame()