from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional, List
from datetime import datetime
import polars as pl


class DownloadScenario(Enum):
    DIRECT = "direct"
    STOCK_LOOP_DATE_RANGE = "stock_loop_date"
    STOCK_LOOP_DATE_ANCHOR = "stock_loop_anchor"
    STOCK_LOOP_FULL_HISTORY = "stock_loop_full"
    SPECIAL_BROKER_RECOMMEND = "broker_recommend"
    SPECIAL_PRO_BAR = "pro_bar"


@dataclass
class BuildResult:
    params: Dict[str, Any]
    scenario: DownloadScenario
    requires_stock_loop: bool = False
    requires_month_loop: bool = False
    months: Optional[List[str]] = None
    date_anchor_param: Optional[str] = None
    interface_config: Dict[str, Any] = field(default_factory=dict, repr=False)
    stock_list: List[Dict[str, Any]] = field(default_factory=list, repr=False)
    user_provided_dates: bool = False  # 新增字段：标记用户是否显式提供日期


class ParamsBuilder:
    def __init__(self, interface_config: Dict[str, Any]):
        self.interface_config = interface_config
        self.api_name = interface_config.get('api_name', '')
        self.pagination_config = interface_config.get('pagination', {})
        self.parameter_config = interface_config.get('parameters', {})

    def build(
        self,
        args: Any,
        mode: str = 'normal',
        date_range: Optional[Dict[str, str]] = None,
        stock_list: Optional[List[Dict[str, Any]]] = None
    ) -> BuildResult:
        # 获取用户是否显式提供日期的标记（从args获取原始值）
        user_provided_dates = getattr(args, 'user_provided_dates', False)
        ts_code = getattr(args, 'ts_code', None)

        # 根据 date_range 是否存在来确定日期值
        if date_range is not None:
            # 用户提供了日期，使用传入的 date_range
            start_date = date_range.get('start_date', getattr(args, 'start_date', '20230101'))
            end_date = date_range.get('end_date', getattr(args, 'end_date', None))
        else:
            # 用户未提供日期，使用args中的值或默认值
            start_date = getattr(args, 'start_date', '20230101')
            end_date = getattr(args, 'end_date', None)

        scenario = self._detect_scenario(ts_code, user_provided_dates, start_date, end_date)

        if scenario == DownloadScenario.SPECIAL_BROKER_RECOMMEND:
            result = self._build_broker_recommend_params(start_date, end_date, ts_code)
        elif scenario == DownloadScenario.SPECIAL_PRO_BAR:
            result = self._build_pro_bar_params(ts_code)
        elif scenario == DownloadScenario.DIRECT:
            result = self._build_direct_params(start_date, end_date, ts_code)
        elif scenario == DownloadScenario.STOCK_LOOP_DATE_RANGE:
            result = self._build_stock_loop_date_params(start_date, end_date, ts_code)
        elif scenario == DownloadScenario.STOCK_LOOP_DATE_ANCHOR:
            result = self._build_stock_loop_anchor_params(start_date, end_date, ts_code)
        else:
            result = self._build_stock_loop_full_params(ts_code)

        result.interface_config = self.interface_config
        result.stock_list = stock_list or []
        result.user_provided_dates = user_provided_dates  # 保存用户日期标记
        return result

    def _detect_scenario(
        self,
        ts_code: Optional[str],
        user_provided_dates: bool,
        start_date: str,
        end_date: Optional[str]
    ) -> DownloadScenario:
        """
        检测下载场景

        场景决策逻辑：
        1. 特殊接口（broker_recommend, pro_bar）单独处理
        2. 非股票循环接口 -> DIRECT
        3. 有 start_date + end_date 参数 -> STOCK_LOOP_DATE_RANGE（Type A/B）
        4. 有日期锚定参数（is_date_anchor=true）：
           - 用户未提供日期 + 有ts_code -> STOCK_LOOP_FULL_HISTORY（全历史）
           - 用户未提供日期 + 无ts_code -> STOCK_LOOP_FULL_HISTORY（全股票轮询）
           - 用户提供日期 -> STOCK_LOOP_DATE_ANCHOR（按锚点遍历）
        5. 其他情况 -> STOCK_LOOP_FULL_HISTORY
        """
        if self.api_name == 'broker_recommend':
            return DownloadScenario.SPECIAL_BROKER_RECOMMEND

        if self.api_name == 'pro_bar':
            if start_date == '20230101' and end_date is None:
                return DownloadScenario.SPECIAL_PRO_BAR

        is_stock_loop = (
            self.pagination_config.get('enabled', False) and
            self.pagination_config.get('mode') == 'stock_loop'
        )

        if not is_stock_loop:
            return DownloadScenario.DIRECT

        has_start_end = (
            'start_date' in self.parameter_config and
            'end_date' in self.parameter_config
        )

        date_anchor_param = self._find_date_anchor_param()

        # Type A/B 接口：有 start_date + end_date 参数
        if has_start_end:
            return DownloadScenario.STOCK_LOOP_DATE_RANGE

        # Type C 接口：有日期锚定参数
        if date_anchor_param:
            # disclosure_date 特殊处理：无日期且无ts_code时全量轮询
            if self.api_name == 'disclosure_date' and not user_provided_dates and not ts_code:
                return DownloadScenario.STOCK_LOOP_FULL_HISTORY

            # 用户未提供日期 -> 全历史模式（只传ts_code，获取全历史）
            if not user_provided_dates:
                return DownloadScenario.STOCK_LOOP_FULL_HISTORY

            # 用户提供日期 -> 按锚点遍历模式
            return DownloadScenario.STOCK_LOOP_DATE_ANCHOR

        return DownloadScenario.STOCK_LOOP_FULL_HISTORY

    def _find_date_anchor_param(self) -> Optional[str]:
        for param_name, param_def in self.parameter_config.items():
            if param_def.get('is_date_anchor', False):
                return param_name
        return None

    def _build_direct_params(
        self,
        start_date: str,
        end_date: Optional[str],
        ts_code: Optional[str]
    ) -> BuildResult:
        params: Dict[str, Any] = {}
        if 'start_date' in self.parameter_config and start_date:
            params['start_date'] = start_date
        if 'end_date' in self.parameter_config and end_date:
            params['end_date'] = end_date
        if ts_code:
            params['ts_code'] = ts_code
        return BuildResult(params=params, scenario=DownloadScenario.DIRECT, requires_stock_loop=False)

    def _build_stock_loop_date_params(
        self,
        start_date: str,
        end_date: Optional[str],
        ts_code: Optional[str]
    ) -> BuildResult:
        params: Dict[str, Any] = {}
        if start_date:
            params['start_date'] = start_date
        if end_date:
            params['end_date'] = end_date
        if ts_code:
            params['ts_code'] = ts_code
        return BuildResult(params=params, scenario=DownloadScenario.STOCK_LOOP_DATE_RANGE, requires_stock_loop=True)

    def _build_stock_loop_anchor_params(
        self,
        start_date: str,
        end_date: Optional[str],
        ts_code: Optional[str]
    ) -> BuildResult:
        params: Dict[str, Any] = {}
        if start_date:
            params['start_date'] = start_date
        if end_date:
            params['end_date'] = end_date
        if ts_code:
            params['ts_code'] = ts_code
        date_anchor_param = self._find_date_anchor_param()
        return BuildResult(
            params=params,
            scenario=DownloadScenario.STOCK_LOOP_DATE_ANCHOR,
            requires_stock_loop=True,
            date_anchor_param=date_anchor_param
        )

    def _build_stock_loop_full_params(self, ts_code: Optional[str]) -> BuildResult:
        params: Dict[str, Any] = {}
        if ts_code:
            params['ts_code'] = ts_code
        return BuildResult(
            params=params,
            scenario=DownloadScenario.STOCK_LOOP_FULL_HISTORY,
            requires_stock_loop=True
        )

    def _build_broker_recommend_params(
        self,
        start_date: str,
        end_date: Optional[str],
        ts_code: Optional[str]
    ) -> BuildResult:
        params: Dict[str, Any] = {}
        if ts_code:
            params['ts_code'] = ts_code
        months = self._generate_months(start_date, end_date)
        return BuildResult(
            params=params,
            scenario=DownloadScenario.SPECIAL_BROKER_RECOMMEND,
            requires_stock_loop=False,
            requires_month_loop=True,
            months=months
        )

    def _build_pro_bar_params(self, ts_code: Optional[str]) -> BuildResult:
        params: Dict[str, Any] = {}
        if ts_code:
            params['ts_code'] = ts_code
        return BuildResult(
            params=params,
            scenario=DownloadScenario.SPECIAL_PRO_BAR,
            requires_stock_loop=True
        )

    def _generate_months(self, start_date: str, end_date: Optional[str]) -> List[str]:
        start = datetime.strptime(start_date, '%Y%m%d')
        end = datetime.strptime(end_date, '%Y%m%d') if end_date else datetime.now()
        return pl.date_range(start, end, '1mo', eager=True).dt.strftime('%Y%m').to_list()

    def build_params_list(
        self,
        result: BuildResult,
        stock_list: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        stock_list = stock_list or result.stock_list
        scenario = result.scenario

        if scenario == DownloadScenario.SPECIAL_BROKER_RECOMMEND:
            params_list = self._build_broker_recommend_params_list(result)
        elif scenario == DownloadScenario.DIRECT:
            params_list = [result.params]
        elif scenario == DownloadScenario.STOCK_LOOP_DATE_RANGE:
            params_list = self._build_stock_loop_date_params_list(result, stock_list)
        elif scenario == DownloadScenario.STOCK_LOOP_DATE_ANCHOR:
            params_list = self._build_stock_loop_anchor_params_list(result, stock_list)
        elif scenario == DownloadScenario.STOCK_LOOP_FULL_HISTORY:
            params_list = self._build_stock_loop_full_params_list(result, stock_list)
        elif scenario == DownloadScenario.SPECIAL_PRO_BAR:
            params_list = self._build_pro_bar_params_list(result, stock_list)
        else:
            params_list = []

        # 在每个参数中添加 user_provided_dates 标记，供下游使用
        for params in params_list:
            params['_user_provided_dates'] = result.user_provided_dates

        return params_list

    def _build_broker_recommend_params_list(self, result: BuildResult) -> List[Dict[str, Any]]:
        params_list = []
        for month in result.months or []:
            p = {'month': month}
            if result.params.get('ts_code'):
                p['ts_code'] = result.params['ts_code']
            params_list.append(p)
        return params_list

    def _build_stock_loop_date_params_list(
        self,
        result: BuildResult,
        stock_list: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        params_list = []
        for stock in stock_list:
            p = result.params.copy()
            p['ts_code'] = stock.get('ts_code', '')
            if 'start_date' not in p and 'start_date' in self.parameter_config:
                p['start_date'] = stock.get('list_date', '20050101')
            params_list.append(p)
        return params_list

    def _build_stock_loop_anchor_params_list(
        self,
        result: BuildResult,
        stock_list: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        params_list = []
        anchor_values = self._generate_date_anchor_values(
            result.params.get('start_date'),
            result.params.get('end_date'),
            result.date_anchor_param
        )
        for stock in stock_list:
            for anchor_value in anchor_values:
                p = {
                    'ts_code': stock.get('ts_code', ''),
                    result.date_anchor_param: anchor_value
                }
                params_list.append(p)
        return params_list

    def _build_stock_loop_full_params_list(
        self,
        result: BuildResult,
        stock_list: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        params_list = []
        for stock in stock_list:
            p = {'ts_code': stock.get('ts_code', '')}
            params_list.append(p)
        return params_list

    def _build_pro_bar_params_list(
        self,
        result: BuildResult,
        stock_list: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        params_list = []
        for stock in stock_list:
            p = {
                'ts_code': stock.get('ts_code', ''),
                'start_date': stock.get('list_date', '20050101')
            }
            params_list.append(p)
        return params_list

    def _generate_date_anchor_values(
        self,
        start_date: Optional[str],
        end_date: Optional[str],
        anchor_param: Optional[str]
    ) -> List[str]:
        if not anchor_param or not start_date:
            return []

        start = datetime.strptime(start_date, '%Y%m%d')
        end = datetime.strptime(end_date, '%Y%m%d') if end_date else datetime.now()

        periods: List[str] = []
        current_year = start.year
        current_quarter = (start.month - 1) // 3 + 1
        end_quarter = (end.month - 1) // 3 + 1

        while current_year < end.year or (current_year == end.year and current_quarter <= end_quarter):
            if anchor_param in ['ann_date', 'f_ann_date']:
                month = current_quarter * 3
                periods.append(f"{current_year}{month:02d}")
            elif anchor_param in ['end_date', 'period']:
                periods.append(f"{current_year}{current_quarter * 3:02d}30")
            else:
                periods.append(f"{current_year}{current_quarter * 3:02d}")

            current_quarter += 1
            if current_quarter > 4:
                current_quarter = 1
                current_year += 1

        return periods
