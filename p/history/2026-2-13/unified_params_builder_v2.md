# App4 统一参数构建方案 V2（修订版）

## 一、问题诊断

### 1.1 当前参数注入位置汇总

| 位置 | 函数/行号 | 修改的参数 | 问题 |
|------|----------|-----------|------|
| `main.py` | `run_update_mode()` L333-393 | `start_date`, `end_date`, `ts_code`, `_date_anchor_param`, `_stock_full_history` | 场景判断 |
| `main.py` | `main()` L961-1040 | 同上 | **重复逻辑** |
| `main.py` | `main()` L1009-1020 | `pro_bar` 清空日期参数 | **特殊接口硬编码** |
| `main.py` | `main()` L1041-1068 | `broker_recommend` 月份循环 | **特殊接口硬编码** |
| `downloader.py` | `download_single_stock()` L416-450 | 从 `stock['list_date']` 填充 `start_date`，移除不支持的日期参数 | **隐形修改** |
| `pagination_executor.py` | `execute()` L50-95 | 根据 `_date_anchor_param` 生成参数列表 | **内部标记展开** |

### 1.2 核心问题

```
用户改了 main.py 的参数 → 被 downloader.py 覆盖 → 最终效果不可预测
```

**根本原因**：内部标记（`_date_anchor_param`, `_stock_full_history`）作为"隐式契约"在多个组件间传递，导致参数流不可追踪。

---

## 二、设计目标

### 2.1 核心原则

```
单一入口：所有参数构建逻辑集中到 ParamsBuilder
无内部标记：不使用 _ 前缀的隐式标记传递信息
下游只读：downloader.py 和 pagination_executor.py 不再修改参数
可预测性：输入 → 输出 完全确定
```

### 2.2 调用链重构

**重构前**：
```
main.py 构建初始 params（含内部标记）
    ↓
downloader.py 修改 params（添加 list_date 作为 start_date）
    ↓
pagination_executor.py 根据 _date_anchor_param/_stock_full_history 展开参数
```

**重构后**：
```
main.py 调用 ParamsBuilder.build() → BuildResult（场景 + 参数）
    ↓
ParamsBuilder.build_params_list() → List[Dict]（完整参数列表）
    ↓
downloader.py / pagination_executor.py 只读执行
```

---

## 三、详细设计

### 3.1 文件结构

```
app4/core/
  params_builder.py      # 唯一入口，包含所有参数构建逻辑
```

### 3.2 核心类设计

```python
# app4/core/params_builder.py

"""
统一参数构建器 - 所有接口参数构建的唯一入口

设计原则：
1. 单一入口：所有参数构建逻辑集中在此
2. 无内部标记：不使用 _ 前缀的隐式标记
3. 下游只读：downloader.py 和 pagination_executor.py 不再修改参数
4. 可预测性：给定相同输入，输出完全确定
"""

from typing import Dict, Any, Optional, List, Generator
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class DownloadScenario(Enum):
    """下载场景类型"""
    DIRECT = "direct"                              # 直接下载，无股票循环
    STOCK_LOOP_DATE_RANGE = "stock_loop_date"      # 股票循环 + 日期范围
    STOCK_LOOP_DATE_ANCHOR = "stock_loop_anchor"   # 股票循环 + 日期锚点（按报告期）
    STOCK_LOOP_FULL_HISTORY = "stock_loop_full"    # 股票循环 + 全历史（无日期）
    SPECIAL_BROKER_RECOMMEND = "broker_recommend"  # 特殊：月份循环
    SPECIAL_PRO_BAR = "pro_bar"                    # 特殊：pro_bar 全历史


@dataclass
class BuildResult:
    """
    参数构建结果
    
    关键：不包含任何 _ 前缀的内部标记
    """
    # 基础请求参数
    params: Dict[str, Any]
    # 场景类型
    scenario: DownloadScenario
    # 是否需要股票循环
    requires_stock_loop: bool = False
    # 是否需要月份循环（broker_recommend 专用）
    requires_month_loop: bool = False
    # 月份列表（broker_recommend 专用）
    months: Optional[List[str]] = None
    # 日期锚点参数名（用于 STOCK_LOOP_DATE_ANCHOR 场景）
    date_anchor_param: Optional[str] = None
    # 接口配置引用（用于生成参数列表）
    interface_config: Dict[str, Any] = field(default_factory=dict, repr=False)
    # 股票列表引用（用于生成参数列表）
    stock_list: List[Dict[str, Any]] = field(default_factory=list, repr=False)


class ParamsBuilder:
    """
    统一参数构建器
    
    职责：
    1. 解析用户意图（命令行参数）
    2. 结合接口配置，确定下载场景
    3. 生成最终请求参数列表
    
    不负责：
    1. 实际执行下载
    2. 数据处理和存储
    """
    
    def __init__(self, interface_config: Dict[str, Any]):
        """
        初始化参数构建器
        
        Args:
            interface_config: 接口配置
        """
        self.interface_config = interface_config
        self.api_name = interface_config.get('api_name', '')
        self.pagination_config = interface_config.get('pagination', {})
        self.parameter_config = interface_config.get('parameters', {})
    
    # ============================================
    # 核心方法 1：构建基础参数和场景
    # ============================================
    
    def build(
        self,
        args: Any,
        mode: str = 'normal',
        date_range: Optional[Dict[str, str]] = None,
        stock_list: Optional[List[Dict[str, Any]]] = None
    ) -> BuildResult:
        """
        构建请求参数
        
        Args:
            args: 命令行参数对象
            mode: 运行模式 ('normal' 或 'update')
            date_range: 日期范围 {'start_date': '...', 'end_date': '...'}
            stock_list: 股票列表（用于股票循环场景）
            
        Returns:
            BuildResult: 构建结果
        """
        # 解析基本参数
        user_provided_dates = getattr(args, 'user_provided_dates', False)
        ts_code = getattr(args, 'ts_code', None)
        start_date = date_range.get('start_date') if date_range else getattr(args, 'start_date', '20230101')
        end_date = date_range.get('end_date') if date_range else getattr(args, 'end_date', None)
        
        # 检测场景
        scenario = self._detect_scenario(ts_code, user_provided_dates, start_date, end_date)
        
        # 根据场景构建参数
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
        else:  # STOCK_LOOP_FULL_HISTORY
            result = self._build_stock_loop_full_params(ts_code)
        
        # 附加引用信息（用于后续生成参数列表）
        result.interface_config = self.interface_config
        result.stock_list = stock_list or []
        
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
        
        优先级：特殊接口 > 股票循环模式 > 直接下载
        """
        # 1. 特殊接口检测
        
        # broker_recommend: 月份循环
        if self.api_name == 'broker_recommend':
            return DownloadScenario.SPECIAL_BROKER_RECOMMEND
        
        # pro_bar: 默认参数时全历史
        if self.api_name == 'pro_bar':
            # 如果用户使用默认参数（20230101 且无 end_date），则全历史
            if start_date == '20230101' and end_date is None:
                return DownloadScenario.SPECIAL_PRO_BAR
            # 否则按普通逻辑处理
        
        # 2. 是否为股票循环模式
        is_stock_loop = (
            self.pagination_config.get('enabled', False) and 
            self.pagination_config.get('mode') == 'stock_loop'
        )
        
        if not is_stock_loop:
            return DownloadScenario.DIRECT
        
        # 3. 股票循环模式的子场景检测
        
        has_start_end = (
            'start_date' in self.parameter_config and 
            'end_date' in self.parameter_config
        )
        
        date_anchor_param = self._find_date_anchor_param()
        
        if has_start_end:
            # 场景 A：接口支持 start_date/end_date
            return DownloadScenario.STOCK_LOOP_DATE_RANGE
        
        elif date_anchor_param:
            # 场景 B：接口使用日期锚点
            # disclosure_date 特殊处理：无日期且无 ts_code 时全历史
            if self.api_name == 'disclosure_date' and not user_provided_dates and not ts_code:
                return DownloadScenario.STOCK_LOOP_FULL_HISTORY
            # 单股票无日期时全历史
            if ts_code and not user_provided_dates:
                return DownloadScenario.STOCK_LOOP_FULL_HISTORY
            return DownloadScenario.STOCK_LOOP_DATE_ANCHOR
        
        else:
            # 场景 C：无日期参数
            return DownloadScenario.STOCK_LOOP_FULL_HISTORY
    
    def _find_date_anchor_param(self) -> Optional[str]:
        """查找日期锚点参数"""
        for param_name, param_def in self.parameter_config.items():
            if param_def.get('is_date_anchor', False):
                return param_name
        return None
    
    # ============================================
    # 场景构建方法
    # ============================================
    
    def _build_direct_params(
        self, 
        start_date: str, 
        end_date: Optional[str], 
        ts_code: Optional[str]
    ) -> BuildResult:
        """构建直接下载参数"""
        params = {}
        
        if 'start_date' in self.parameter_config and start_date:
            params['start_date'] = start_date
        if 'end_date' in self.parameter_config and end_date:
            params['end_date'] = end_date
        if ts_code:
            params['ts_code'] = ts_code
        
        return BuildResult(
            params=params,
            scenario=DownloadScenario.DIRECT,
            requires_stock_loop=False
        )
    
    def _build_stock_loop_date_params(
        self, 
        start_date: str, 
        end_date: Optional[str], 
        ts_code: Optional[str]
    ) -> BuildResult:
        """构建股票循环 + 日期范围参数"""
        params = {}
        
        if start_date:
            params['start_date'] = start_date
        if end_date:
            params['end_date'] = end_date
        if ts_code:
            params['ts_code'] = ts_code
        
        return BuildResult(
            params=params,
            scenario=DownloadScenario.STOCK_LOOP_DATE_RANGE,
            requires_stock_loop=True
        )
    
    def _build_stock_loop_anchor_params(
        self, 
        start_date: str, 
        end_date: Optional[str], 
        ts_code: Optional[str]
    ) -> BuildResult:
        """构建股票循环 + 日期锚点参数"""
        params = {}
        
        # 保留日期范围，用于生成日期锚点列表
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
        """构建股票循环 + 全历史参数（无日期参数）"""
        params = {}
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
        """构建 broker_recommend 专用参数"""
        params = {}
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
        """构建 pro_bar 全历史参数"""
        params = {}
        if ts_code:
            params['ts_code'] = ts_code
        
        return BuildResult(
            params=params,
            scenario=DownloadScenario.SPECIAL_PRO_BAR,
            requires_stock_loop=True  # pro_bar 需要股票循环
        )
    
    def _generate_months(self, start_date: str, end_date: Optional[str]) -> List[str]:
        """生成月份列表"""
        import polars as pl
        
        start = datetime.strptime(start_date, '%Y%m%d')
        if end_date:
            end = datetime.strptime(end_date, '%Y%m%d')
        else:
            end = datetime.now()
        
        return pl.date_range(start, end, '1mo', eager=True).dt.strftime('%Y%m').to_list()
    
    # ============================================
    # 核心方法 2：生成完整参数列表
    # ============================================
    
    def build_params_list(
        self,
        result: BuildResult,
        stock_list: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        根据构建结果生成完整的参数列表
        
        这是参数构建的最终出口，返回可直接用于 API 请求的参数列表。
        
        Args:
            result: build() 方法的返回结果
            stock_list: 股票列表（如果未在 build() 中提供）
            
        Returns:
            List[Dict[str, Any]]: 可直接用于 API 请求的参数列表
        """
        stock_list = stock_list or result.stock_list
        scenario = result.scenario
        
        if scenario == DownloadScenario.SPECIAL_BROKER_RECOMMEND:
            return self._build_broker_recommend_params_list(result)
        
        elif scenario == DownloadScenario.DIRECT:
            return [result.params]
        
        elif scenario == DownloadScenario.STOCK_LOOP_DATE_RANGE:
            return self._build_stock_loop_date_params_list(result, stock_list)
        
        elif scenario == DownloadScenario.STOCK_LOOP_DATE_ANCHOR:
            return self._build_stock_loop_anchor_params_list(result, stock_list)
        
        elif scenario == DownloadScenario.STOCK_LOOP_FULL_HISTORY:
            return self._build_stock_loop_full_params_list(result, stock_list)
        
        elif scenario == DownloadScenario.SPECIAL_PRO_BAR:
            return self._build_pro_bar_params_list(result, stock_list)
        
        return []
    
    def _build_broker_recommend_params_list(self, result: BuildResult) -> List[Dict[str, Any]]:
        """构建 broker_recommend 月份参数列表"""
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
        """
        构建股票循环 + 日期范围参数列表
        
        每个股票使用相同的日期范围。
        """
        params_list = []
        
        for stock in stock_list:
            p = result.params.copy()
            p['ts_code'] = stock.get('ts_code', '')
            
            # 如果未指定 start_date 且接口支持，使用 list_date
            if 'start_date' not in p and 'start_date' in self.parameter_config:
                p['start_date'] = stock.get('list_date', '20050101')
            
            params_list.append(p)
        
        return params_list
    
    def _build_stock_loop_anchor_params_list(
        self,
        result: BuildResult,
        stock_list: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        构建股票循环 + 日期锚点参数列表
        
        每个股票需要生成日期锚点列表（如报告期列表）。
        """
        params_list = []
        
        # 生成日期锚点值列表（如报告期列表）
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
        """
        构建股票循环 + 全历史参数列表
        
        每个股票一个请求，无日期参数。
        """
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
        """
        构建 pro_bar 全历史参数列表
        
        每个股票使用其 list_date 作为 start_date。
        """
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
        """
        生成日期锚点值列表
        
        根据锚点类型（ann_date, end_date 等）生成对应的值列表。
        """
        if not anchor_param or not start_date:
            return []
        
        # 默认实现：生成报告期列表
        # 实际实现需要根据 anchor_param 的类型来决定
        # 这里使用简单的季度报告期生成
        from datetime import datetime
        
        start = datetime.strptime(start_date, '%Y%m%d')
        end = datetime.strptime(end_date, datetime.now().strftime('%Y%m%d')) if end_date else datetime.now()
        
        # 生成报告期列表：每季度末
        periods = []
        current_year = start.year
        current_quarter = (start.month - 1) // 3 + 1
        
        while current_year < end.year or (current_year == end.year and current_quarter <= (end.month - 1) // 3 + 1):
            if anchor_param in ['ann_date', 'f_ann_date']:
                # 公告日期：季度末月份的最后一天
                month = current_quarter * 3
                periods.append(f"{current_year}{month:02d}")
            elif anchor_param in ['end_date', 'period']:
                # 报告期：季度末
                periods.append(f"{current_year}{current_quarter * 3:02d}30")  # 简化处理
            else:
                # 默认：月份
                periods.append(f"{current_year}{current_quarter * 3:02d}")
            
            current_quarter += 1
            if current_quarter > 4:
                current_quarter = 1
                current_year += 1
        
        return periods
```

### 3.3 下游改动

#### 3.3.1 downloader.py 改动

**删除** `download_single_stock()` 中的参数修改逻辑：

```python
# 删除前（L416-450）：
def download_single_stock(self, interface_config, stock, params):
    stock_params = params.copy()
    stock_params['ts_code'] = stock['ts_code']
    
    # 根据接口配置决定是否设置日期参数
    parameter_config = interface_config.get('parameters', {})
    if 'start_date' in parameter_config and 'start_date' not in stock_params:
        list_date = stock.get('list_date', '20050101')
        stock_params['start_date'] = list_date
    # ... 更多修改逻辑

# 删除后：
def download_single_stock(self, interface_config, stock, params):
    """
    下载单只股票的数据
    
    注意：params 已由 ParamsBuilder.build_params_list() 构建，不再修改。
    """
    logger.info(f"Downloading data for stock {stock['ts_code']}, params: {params}")
    # 直接使用 params，不再修改
    # ... 执行下载
```

**保留**覆盖率检查逻辑（L451-520），只是参数来源改变。

#### 3.3.2 pagination_executor.py 改动

**删除** `execute()` 中的参数展开逻辑：

```python
# 删除前（L50-95）：
def execute(self, interface_config, base_params, context, make_request, ...):
    if base_params.get('_date_anchor_param') and self._is_stock_loop_enabled(...):
        # ... 复杂展开
    elif base_params.get('_stock_full_history') and self._is_stock_loop_enabled(...):
        # ... 复杂展开
    else:
        # ... 另一种展开

# 删除后：
def execute(
    self,
    interface_config: Dict[str, Any],
    params_list: List[Dict[str, Any]],  # 直接接收参数列表
    make_request: Callable,
    coverage_manager: Optional[Any] = None
) -> List[Dict[str, Any]]:
    """
    执行分页请求
    
    Args:
        interface_config: 接口配置
        params_list: 已构建好的参数列表（由 ParamsBuilder.build_params_list() 生成）
        make_request: 请求执行回调函数
    """
    if not params_list:
        return []
    
    if len(params_list) == 1:
        return self._execute_single(interface_config, params_list[0], make_request)
    
    # 选择执行模式
    if self._should_use_concurrency(interface_config):
        return self._execute_concurrent(interface_config, params_list, make_request)
    else:
        return self._execute_sequential(interface_config, params_list, make_request)
```

### 3.4 main.py 改动

```python
# 改动前：~150行场景判断逻辑
pagination_config = interface_config.get('pagination', {})
if pagination_config.get('enabled', False) and pagination_config.get('mode') == 'stock_loop':
    parameter_config = interface_config.get('parameters', {})
    has_start_end = 'start_date' in parameter_config and 'end_date' in parameter_config
    # ... 更多判断

# 改动后：
from core.params_builder import ParamsBuilder, DownloadScenario

# 1. 创建参数构建器
params_builder = ParamsBuilder(interface_config)

# 2. 构建基础参数和场景
result = params_builder.build(
    args, 
    mode='update', 
    date_range={'start_date': start_date, 'end_date': end_date}
)

# 3. 根据场景执行
if result.scenario == DownloadScenario.SPECIAL_BROKER_RECOMMEND:
    # 月份循环
    for month in result.months:
        month_params = {'month': month}
        if result.params.get('ts_code'):
            month_params['ts_code'] = result.params['ts_code']
        data = downloader.download(interface_name, month_params)
        if data:
            process_and_save_data(data, interface_name, interface_config, processor, storage_manager)

elif result.requires_stock_loop:
    # 股票循环模式
    stock_list = _prepare_stock_list(downloader, args, result.params, storage_manager, logger)
    
    # 生成参数列表
    params_list = params_builder.build_params_list(result, stock_list)
    
    # 使用 pagination_executor 执行
    from core.pagination_executor import PaginationExecutor
    executor = PaginationExecutor()
    
    all_data = executor.execute(
        interface_config=interface_config,
        params_list=params_list,
        make_request=lambda p: downloader._make_request(interface_config, p),
        coverage_manager=coverage_manager
    )
    
    if all_data:
        process_and_save_data(all_data, interface_name, interface_config, processor, storage_manager)

else:
    # 直接下载
    data = downloader.download(interface_name, result.params)
    if data:
        process_and_save_data(data, interface_name, interface_config, processor, storage_manager)
```

---

## 四、实施步骤

### Phase 1：创建 ParamsBuilder（低风险）

1. 创建 `app4/core/params_builder.py`
2. 实现 `ParamsBuilder` 类
3. 编写单元测试，覆盖所有场景

### Phase 2：修改 main.py（中风险）

1. 在 `run_update_mode()` 中使用 `ParamsBuilder`
2. 在 `main()` 中使用 `ParamsBuilder`
3. 删除重复的场景判断代码
4. 删除 `broker_recommend` 和 `pro_bar` 硬编码逻辑
5. 测试所有场景

### Phase 3：修改 downloader.py（中风险）

1. 删除 `download_single_stock()` 中的参数修改逻辑（L425-450）
2. 保留覆盖率检查逻辑
3. 测试股票循环场景

### Phase 4：修改 pagination_executor.py（低风险）

1. 删除 `execute()` 中的参数展开逻辑（L50-95）
2. 改为直接接收 `params_list` 参数
3. 删除 `_date_anchor_param` 和 `_stock_full_history` 相关代码
4. 测试分页场景

---

## 五、改动量评估

| 文件 | 改动类型 | 行数 |
|------|---------|------|
| `params_builder.py` | 新增 | +350 |
| `main.py` | 删除/修改 | -150 / +40 |
| `downloader.py` | 删除 | -40 |
| `pagination_executor.py` | 删除/修改 | -50 / +15 |

**净效果**：代码量基本持平，但逻辑集中、可预测。

---

## 六、收益

| 维度 | 改善 |
|------|------|
| 可预测性 | 参数只在一个地方构建，效果完全可预测 |
| 无内部标记 | 不再依赖 `_date_anchor_param`、`_stock_full_history` 等隐式标记 |
| 可维护性 | 改参数只需改一处 |
| 可测试性 | ParamsBuilder 可独立测试 |
| 代码重复 | 消除 main.py 两处重复逻辑 |
| 职责清晰 | 参数构建与下载执行分离 |

---

## 七、特殊接口处理汇总

| 接口 | 场景 | 处理方式 |
|------|------|---------|
| `broker_recommend` | 月份循环 | `SPECIAL_BROKER_RECOMMEND`，生成月份列表 |
| `pro_bar` | 默认参数时全历史 | `SPECIAL_PRO_BAR`，每个股票用 list_date 作为 start_date |
| `disclosure_date` | 无日期且无 ts_code 时全历史 | 在 `_detect_scenario()` 中特殊判断 |
| 日期锚点接口 | 按报告期循环 | `STOCK_LOOP_DATE_ANCHOR`，生成锚点值列表 |

---

## 八、风险与缓解

| 风险 | 等级 | 缓解措施 |
|------|------|---------|
| 场景判断遗漏 | 中 | Phase 1 同步编写测试，覆盖所有现有分支 |
| 日期锚点生成逻辑 | 中 | 对比现有 `ParameterGenerator` 实现，确保一致 |
| coverage_manager 集成 | 低 | 保留现有覆盖率检查逻辑，只改参数来源 |

---

## 九、关键差异：V2 修订版 vs 原方案

| 维度 | 原方案 | V2 修订版 |
|------|--------|----------|
| 内部标记 | 仍依赖 `_date_anchor_param`、`_stock_full_history` | **完全移除** |
| `pro_bar` 处理 | 未提及 | **新增 `SPECIAL_PRO_BAR` 场景** |
| 参数列表生成 | 分散在 `pagination_executor.py` | **集中在 `build_params_list()`** |
| `build_stock_params` | 仍依赖内部标记判断场景 | **删除，改为 `build_params_list()`** |
| coverage_manager | 未明确 | **明确保留位置** |

---

*版本：V2 修订版*
*创建：2026-02-14*