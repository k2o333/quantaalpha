# 可组合式分页架构设计方案

## 1. 设计背景

### 1.1 现有问题

当前 `app4` 的分页系统存在以下问题：

1. **模式互斥**：9种分页模式（offset, date_range, stock_loop, period_range, quarterly_range, periodic_range, date_range_daily, reverse_date_range, type_split）只能选其一
2. **代码重复**：每个模式都有独立的生成器和执行器方法，大量重复逻辑
3. **扩展困难**：新增模式需要修改多处代码
4. **组合受限**：无法实现复杂场景（如：每个股票 + 每30天 + 按类型分类 + 倒序 + 每页1000条）

### 1.2 设计目标

- 将分页逻辑拆分为独立的**可组合维度**
- 支持任意维度的自由组合
- 大幅减少代码量（目标减少60-70%）
- 保持向后兼容

---

## 2. 核心设计

### 2.1 分页维度抽象

将分页抽象为4个独立维度：

| 维度 | 功能 | 配置项 |
|------|------|--------|
| `time_range` | 时间窗口递归 | window, reverse, stop_on_empty |
| `stock_loop` | 股票代码遍历 | skip_existing |
| `type_split` | 字段分类分割 | field, values |
| `offset` | 记录偏移分页 | limit |

**执行顺序**（从内到外）：time → stock → type → offset

### 2.2 新配置格式

#### 2.2.1 完整配置示例

```yaml
pagination:
  enabled: true
  
  # 1. 时间维度（可选）
  time_range:
    enabled: true
    window: 30d        # 支持: 1d, 7d, 30d, 1m, 1q, 1y
    reverse: false     # true=倒序(从新到旧), false=正序
    stop_on_empty: 90  # 连续无数据多少天停止（仅reverse时有效）
  
  # 2. 股票维度（可选）
  stock_loop:
    enabled: true
    skip_existing: true  # 跳过已存在的股票
  
  # 3. 分类维度（可选）
  type_split:
    enabled: true
    field: type          # 要分割的字段名
    values: ['HK_SZ', 'SZ_HK', 'HK_SH', 'SH_HK']
  
  # 4. 偏移量维度（可选）
  offset:
    enabled: true
    limit: 1000          # 每页记录数
```

#### 2.2.2 简化配置示例

```yaml
# 仅时间范围分页（原date_range）
pagination:
  time_range:
    window: 365d

# 仅股票循环（原stock_loop）
pagination:
  stock_loop:
    enabled: true
  time_range:
    window: 3650d  # 股票循环通常需要配合时间范围

# 仅类型分割（原type_split）
pagination:
  type_split:
    field: type
    values: ['A', 'B', 'C']

# 仅偏移分页（原offset）
pagination:
  offset:
    limit: 5000
```

#### 2.2.3 复杂组合示例

```yaml
# 场景：每个股票 + 每30天 + 按市场类型分类 + 倒序 + 每页1000条
pagination:
  time_range:
    enabled: true
    window: 30d
    reverse: true
    stop_on_empty: 90
  
  stock_loop:
    enabled: true
    skip_existing: true
  
  type_split:
    enabled: true
    field: market_type
    values: ['主板', '创业板', '科创板', '北交所']
  
  offset:
    enabled: true
    limit: 1000
```

---

## 3. 核心类实现

### 3.1 PaginationComposer（参数组合器）

```python
"""分页参数组合器 - 将多个分页维度组合成一个参数流"""

import logging
from typing import Dict, Any, List, Iterator, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class PaginationContext:
    """分页上下文 - 传递必要的配置和数据"""
    interface_config: Dict[str, Any]
    trade_calendar: Optional[List[Dict[str, Any]]] = None
    stock_list: Optional[List[Dict[str, Any]]] = None
    coverage_manager: Optional[Any] = None
    force_download: bool = False
    
    @property
    def pagination_config(self) -> Dict[str, Any]:
        return self.interface_config.get('pagination', {})
    
    @property
    def interface_name(self) -> str:
        return self.interface_config.get('name', '')


class PaginationComposer:
    """分页组合器 - 将多个分页维度组合成一个参数流"""
    
    # 窗口大小单位映射（转换为天数）
    WINDOW_UNITS = {
        'd': 1, 'w': 7, 'm': 30, 'q': 90, 'y': 365
    }
    
    def __init__(self, context: PaginationContext):
        self.context = context
        self.config = context.pagination_config
        self.interface_config = context.interface_config
    
    def compose(self, base_params: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        """组合所有启用的分页维度"""
        params_stream = [base_params]
        
        # 1. 时间维度（最内层）
        if self._is_enabled('time_range'):
            params_stream = list(self._apply_time_range(params_stream))
        
        # 2. 股票维度
        if self._is_enabled('stock_loop'):
            params_stream = list(self._apply_stock_loop(params_stream))
        
        # 3. 分类维度
        if self._is_enabled('type_split'):
            params_stream = list(self._apply_type_split(params_stream))
        
        # 4. 偏移量维度（最外层）
        if self._is_enabled('offset'):
            params_stream = list(self._apply_offset(params_stream))
        
        yield from params_stream
    
    def _is_enabled(self, dimension: str) -> bool:
        """检查某个维度是否启用"""
        dim_config = self.config.get(dimension, {})
        return dim_config.get('enabled', False) if dim_config else False
    
    def _apply_time_range(self, params_stream: List[Dict[str, Any]]) -> Iterator[Dict[str, Any]]:
        """应用时间范围维度"""
        time_config = self.config['time_range']
        window_str = time_config.get('window', '365d')
        reverse = time_config.get('reverse', False)
        window_days = self._parse_window(window_str)
        
        for params in params_stream:
            start_date = params.get('start_date', '20050101')
            end_date = params.get('end_date', datetime.now().strftime('%Y%m%d'))
            trade_days = self._get_trade_days(start_date, end_date)
            
            if not trade_days:
                yield params
                continue
            
            trade_days.sort(key=lambda x: x['cal_date'], reverse=reverse)
            
            for i in range(0, len(trade_days), window_days):
                window_days_list = trade_days[i:i + window_days]
                window_dates = [d['cal_date'] for d in window_days_list]
                window_start, window_end = min(window_dates), max(window_dates)
                
                window_params = params.copy()
                window_params['start_date'] = window_start
                window_params['end_date'] = window_end
                window_params['_time_window'] = (window_start, window_end)
                yield window_params
    
    def _apply_stock_loop(self, params_stream: List[Dict[str, Any]]) -> Iterator[Dict[str, Any]]:
        """应用股票循环维度"""
        stock_list = self.context.stock_list
        if not stock_list:
            logger.error("Stock list not provided")
            return
        
        skip_existing = self.config['stock_loop'].get('skip_existing', False)
        parameter_config = self.interface_config.get('parameters', {})
        
        for params in params_stream:
            for stock in stock_list:
                ts_code = stock.get('ts_code')
                if not ts_code:
                    continue
                
                if skip_existing and not self.context.force_download:
                    if self._stock_data_exists(ts_code):
                        continue
                
                stock_params = params.copy()
                stock_params['ts_code'] = ts_code
                stock_params['_stock_info'] = stock
                
                if 'start_date' in parameter_config and 'start_date' not in stock_params:
                    stock_params['start_date'] = stock.get('list_date', '20050101')
                
                if 'start_date' not in parameter_config:
                    stock_params.pop('start_date', None)
                if 'end_date' not in parameter_config:
                    stock_params.pop('end_date', None)
                
                yield stock_params
    
    def _apply_type_split(self, params_stream: List[Dict[str, Any]]) -> Iterator[Dict[str, Any]]:
        """应用分类分割维度"""
        type_config = self.config['type_split']
        field = type_config.get('field', 'type')
        values = type_config.get('values', [])
        
        if not values:
            yield from params_stream
            return
        
        for params in params_stream:
            for val in values:
                type_params = params.copy()
                type_params[field] = val
                type_params['_type_field'] = field
                type_params['_type_value'] = val
                yield type_params
    
    def _apply_offset(self, params_stream: List[Dict[str, Any]]) -> Iterator[Dict[str, Any]]:
        """应用偏移量维度"""
        offset_config = self.config['offset']
        limit = offset_config.get('limit', 5000)
        
        for params in params_stream:
            params['_offset_pagination'] = {
                'enabled': True,
                'limit': limit,
                'current_offset': 0
            }
            yield params
    
    def _parse_window(self, window_str: str) -> int:
        """解析窗口大小字符串为天数"""
        if not window_str:
            return 365
        window_str = str(window_str).lower().strip()
        if window_str[-1] in self.WINDOW_UNITS:
            return int(window_str[:-1]) * self.WINDOW_UNITS[window_str[-1]]
        return int(window_str)
    
    def _get_trade_days(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """获取交易日列表"""
        if not self.context.trade_calendar:
            return []
        return [
            day for day in self.context.trade_calendar
            if day.get('is_open', 0) == 1 and start_date <= day['cal_date'] <= end_date
        ]
    
    def _stock_data_exists(self, ts_code: str) -> bool:
        """检查股票数据是否已存在"""
        if self.context.coverage_manager:
            return self.context.coverage_manager.check_stock_coverage(
                self.context.interface_name, ts_code
            )
        return False
```

### 3.2 PaginationExecutor（分页执行器）

```python
"""分页执行器 - 执行组合后的分页参数流"""

import logging
from typing import Dict, Any, List, Callable, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

logger = logging.getLogger(__name__)


class PaginationExecutor:
    """分页执行器 - 执行组合后的参数流"""
    
    NON_CONCURRENT_INTERFACES = [
        'fina_audit', 'forecast_vip', 'express_vip', 'disclosure_date'
    ]
    LOW_CONCURRENT_INTERFACES = [
        'top10_holders', 'top10_floatholders', 'pledge_detail', 'dividend'
    ]
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
    
    def execute(
        self,
        interface_config: Dict[str, Any],
        base_params: Dict[str, Any],
        context: PaginationContext,
        make_request: Callable[[Dict[str, Any], Dict[str, Any]], List[Dict[str, Any]]],
        coverage_manager: Optional[Any] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[Dict[str, Any]]:
        """执行分页请求（统一入口）"""
        composer = PaginationComposer(context)
        params_list = list(composer.compose(base_params))
        
        if len(params_list) <= 1:
            return self._execute_single(interface_config, params_list[0], make_request) if params_list else []
        
        if self._should_use_concurrency(interface_config):
            return self._execute_concurrent(
                interface_config, params_list, make_request, coverage_manager, progress_callback
            )
        else:
            return self._execute_sequential(
                interface_config, params_list, make_request, coverage_manager, progress_callback
            )
    
    def _execute_single(self, interface_config, params, make_request):
        """执行单个请求"""
        return self._execute_single_request(interface_config, params, make_request)
    
    def _execute_sequential(self, interface_config, params_list, make_request, coverage_manager, progress_callback):
        """顺序执行"""
        all_data = []
        consecutive_empty = 0
        stop_on_empty = self._get_stop_on_empty_config(interface_config)
        
        for idx, params in enumerate(params_list):
            if progress_callback:
                progress_callback(idx + 1, len(params_list))
            
            if coverage_manager and not params.get('_force_download'):
                if self._should_skip_by_coverage(interface_config, params, coverage_manager):
                    continue
            
            data = self._execute_single_request(interface_config, params, make_request)
            
            if data:
                all_data.extend(data)
                consecutive_empty = 0
            else:
                consecutive_empty += self._estimate_empty_days(params)
                if stop_on_empty > 0 and consecutive_empty >= stop_on_empty:
                    logger.info(f"Stopping after {consecutive_empty} consecutive empty days")
                    break
        
        return all_data
    
    def _execute_concurrent(self, interface_config, params_list, make_request, coverage_manager, progress_callback):
        """并发执行"""
        all_data = []
        max_workers = self._get_max_workers(interface_config)
        
        filtered_params = [
            p for p in params_list
            if not (coverage_manager and not p.get('_force_download') and
                    self._should_skip_by_coverage(interface_config, p, coverage_manager))
        ]
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_params = {
                executor.submit(self._execute_single_request, interface_config, p, make_request): p
                for p in filtered_params
            }
            
            completed = 0
            for future in as_completed(future_to_params):
                completed += 1
                if progress_callback:
                    progress_callback(completed, len(filtered_params))
                try:
                    data = future.result()
                    if data:
                        all_data.extend(data)
                except Exception as e:
                    logger.error(f"Task failed: {e}")
        
        return all_data
    
    def _execute_single_request(self, interface_config, params, make_request):
        """执行单个请求，处理offset分页"""
        offset_config = params.get('_offset_pagination', {})
        
        if not offset_config.get('enabled'):
            clean_params = {k: v for k, v in params.items() if not k.startswith('_')}
            return make_request(interface_config, clean_params)
        
        # 执行offset分页
        all_data = []
        limit = offset_config['limit']
        offset = 0
        base_params = {k: v for k, v in params.items() if not k.startswith('_')}
        
        while True:
            request_params = base_params.copy()
            request_params['limit'] = limit
            request_params['offset'] = offset
            
            data = make_request(interface_config, request_params)
            if not data:
                break
            
            all_data.extend(data)
            if len(data) < limit:
                break
            
            offset += limit
            if offset > limit * 10000:  # 安全限制
                logger.warning(f"Offset pagination exceeded safety limit")
                break
        
        return all_data
    
    def _should_use_concurrency(self, interface_config):
        return interface_config.get('name') not in self.NON_CONCURRENT_INTERFACES
    
    def _get_max_workers(self, interface_config):
        name = interface_config.get('name', '')
        if name in self.NON_CONCURRENT_INTERFACES:
            return 1
        elif name in self.LOW_CONCURRENT_INTERFACES:
            return 2
        return self.max_workers
    
    def _get_stop_on_empty_config(self, interface_config):
        time_range = interface_config.get('pagination', {}).get('time_range', {})
        if time_range.get('reverse', False):
            return time_range.get('stop_on_empty', 0)
        return 0
    
    def _should_skip_by_coverage(self, interface_config, params, coverage_manager):
        api_name = interface_config.get('api_name', '')
        if '_time_window' in params:
            strategy = 'date_range'
        elif '_stock_info' in params:
            strategy = 'stock'
        elif '_type_value' in params:
            strategy = 'type'
        else:
            strategy = 'default'
        
        clean_params = {k: v for k, v in params.items() if not k.startswith('_')}
        try:
            return coverage_manager.should_skip(api_name, clean_params, strategy=strategy)
        except:
            return False
    
    def _estimate_empty_days(self, params):
        if '_time_window' in params:
            try:
                start, end = params['_time_window']
                return (datetime.strptime(end, '%Y%m%d') - datetime.strptime(start, '%Y%m%d')).days + 1
            except:
                pass
        return 1
```

---

## 4. 向后兼容层

### 4.1 配置迁移函数

```python
def migrate_legacy_config(interface_config: Dict[str, Any]) -> Dict[str, Any]:
    """将旧版分页配置迁移为新版配置"""
    old_pagination = interface_config.get('pagination', {})
    
    # 如果已经是新配置格式，直接返回
    if any(key in old_pagination for key in ['time_range', 'stock_loop', 'type_split', 'offset']):
        return old_pagination
    
    mode = old_pagination.get('mode', 'offset')
    new_config = {'enabled': old_pagination.get('enabled', True)}
    window_size_days = old_pagination.get('window_size_days', 365)
    window_str = f"{window_size_days}d"
    
    if mode == 'offset':
        new_config['offset'] = {
            'enabled': True,
            'limit': old_pagination.get('default_limit', 5000)
        }
    elif mode == 'date_range':
        new_config['time_range'] = {
            'enabled': True, 'window': window_str, 'reverse': False
        }
    elif mode == 'reverse_date_range':
        new_config['time_range'] = {
            'enabled': True,
            'window': f"{old_pagination.get('window_size_days', 30)}d",
            'reverse': True,
            'stop_on_empty': old_pagination.get('empty_threshold_days', 90)
        }
    elif mode == 'stock_loop':
        new_config['stock_loop'] = {'enabled': True, 'skip_existing': True}
        new_config['time_range'] = {'enabled': True, 'window': window_str, 'reverse': False}
    elif mode == 'type_split':
        new_config['type_split'] = {
            'enabled': True,
            'field': 'type',
            'values': interface_config.get('type_values', ['HK_SZ', 'SZ_HK', 'HK_SH', 'SH_HK'])
        }
    elif mode == 'period_range':
        new_config['time_range'] = {'enabled': True, 'window': '1q', 'reverse': False}
    elif mode == 'quarterly_range':
        new_config['time_range'] = {'enabled': True, 'window': '1q', 'reverse': False}
    elif mode == 'periodic_range':
        period_type = old_pagination.get('period_type', 'month')
        window_map = {'week': '7d', 'month': '1m', 'quarter': '1q', 'year': '1y'}
        new_config['time_range'] = {
            'enabled': True,
            'window': window_map.get(period_type, '1m'),
            'reverse': False
        }
    elif mode == 'date_range_daily':
        new_config['time_range'] = {'enabled': True, 'window': '1d', 'reverse': False}
    else:
        new_config['offset'] = {'enabled': True, 'limit': 5000}
    
    return new_config


def create_context_with_legacy_support(interface_config: Dict[str, Any], **kwargs) -> PaginationContext:
    """创建分页上下文，自动处理旧版配置"""
    config = interface_config.copy()
    if 'pagination' in config:
        config['pagination'] = migrate_legacy_config(config)
    return PaginationContext(interface_config=config, **kwargs)
```

---

## 5. 使用示例

### 5.1 基础使用

```python
from pagination_composer import PaginationComposer, PaginationContext
from pagination_executor import PaginationExecutor

# 接口配置
interface_config = {
    'name': 'trade_cal',
    'api_name': 'pro.trade_cal',
    'pagination': {
        'enabled': True,
        'time_range': {
            'enabled': True,
            'window': '30d',
            'reverse': False
        }
    }
}

# 创建上下文
context = PaginationContext(
    interface_config=interface_config,
    trade_calendar=trade_calendar
)

# 创建组合器查看生成的参数
composer = PaginationComposer(context)
for params in composer.compose(base_params):
    print(f"start_date={params['start_date']}, end_date={params['end_date']}")

# 使用执行器执行请求
executor = PaginationExecutor()
result = executor.execute(
    interface_config=interface_config,
    base_params=base_params,
    context=context,
    make_request=make_request_callback
)
```

### 5.2 全功能组合（5维度全开）

```python
interface_config = {
    'name': 'complex_data',
    'api_name': 'pro.complex_data',
    'pagination': {
        'time_range': {
            'enabled': True,
            'window': '30d',
            'reverse': True,
            'stop_on_empty': 90
        },
        'stock_loop': {
            'enabled': True,
            'skip_existing': True
        },
        'type_split': {
            'enabled': True,
            'field': 'market_type',
            'values': ['主板', '创业板', '科创板', '北交所']
        },
        'offset': {
            'enabled': True,
            'limit': 1000
        }
    }
}

context = PaginationContext(
    interface_config=interface_config,
    stock_list=stock_list,
    trade_calendar=trade_calendar
)

# 执行
executor = PaginationExecutor()
result = executor.execute(
    interface_config=interface_config,
    base_params={'start_date': '20200101', 'end_date': '20240331'},
    context=context,
    make_request=make_request_callback,
    coverage_manager=coverage_manager
)
```

### 5.3 向后兼容使用

```python
from pagination_composer import create_context_with_legacy_support
from pagination_executor import PaginationExecutor

# 旧配置会自动转换
old_config = {
    'name': 'daily',
    'pagination': {
        'enabled': True,
        'mode': 'reverse_date_range',
        'window_size_days': 30
    }
}

context = create_context_with_legacy_support(
    interface_config=old_config,
    trade_calendar=calendar
)

executor = PaginationExecutor()
result = executor.execute(
    interface_config=old_config,  # 旧配置也能直接使用
    base_params=base_params,
    context=context,
    make_request=make_request_callback
)
```

---

## 6. 配置迁移对照表

| 旧模式 | 旧配置 | 新配置 |
|--------|--------|--------|
| offset | `mode: offset`<br>`default_limit: 5000` | `offset:`<br>&nbsp;&nbsp;`enabled: true`<br>&nbsp;&nbsp;`limit: 5000` |
| date_range | `mode: date_range`<br>`window_size_days: 365` | `time_range:`<br>&nbsp;&nbsp;`enabled: true`<br>&nbsp;&nbsp;`window: 365d` |
| reverse_date_range | `mode: reverse_date_range`<br>`window_size_days: 30`<br>`empty_threshold_days: 90` | `time_range:`<br>&nbsp;&nbsp;`enabled: true`<br>&nbsp;&nbsp;`window: 30d`<br>&nbsp;&nbsp;`reverse: true`<br>&nbsp;&nbsp;`stop_on_empty: 90` |
| stock_loop | `mode: stock_loop`<br>`window_size_days: 3650` | `stock_loop:`<br>&nbsp;&nbsp;`enabled: true`<br>`time_range:`<br>&nbsp;&nbsp;`enabled: true`<br>&nbsp;&nbsp;`window: 3650d` |
| type_split | `mode: type_split`<br>`type_values: [...]` | `type_split:`<br>&nbsp;&nbsp;`enabled: true`<br>&nbsp;&nbsp;`field: type`<br>&nbsp;&nbsp;`values: [...]` |
| period_range | `mode: period_range` | `time_range:`<br>&nbsp;&nbsp;`enabled: true`<br>&nbsp;&nbsp;`window: 1q` |
| quarterly_range | `mode: quarterly_range` | `time_range:`<br>&nbsp;&nbsp;`enabled: true`<br>&nbsp;&nbsp;`window: 1q` |
| periodic_range | `mode: periodic_range`<br>`period_type: month` | `time_range:`<br>&nbsp;&nbsp;`enabled: true`<br>&nbsp;&nbsp;`window: 1m` |
| date_range_daily | `mode: date_range_daily` | `time_range:`<br>&nbsp;&nbsp;`enabled: true`<br>&nbsp;&nbsp;`window: 1d` |

---

## 7. 优势对比

### 7.1 代码量对比

| 模块 | 旧代码 | 新代码 | 减少比例 |
|------|--------|--------|----------|
| pagination.py | ~570行 | ~200行 | 65% |
| pagination_executor.py | ~600行 | ~250行 | 58% |
| **总计** | **~1170行** | **~450行** | **62%** |

### 7.2 功能对比

| 功能 | 旧设计 | 新设计 |
|------|--------|--------|
| 模式数量 | 9种互斥模式 | 4个可组合维度 |
| 组合能力 | ❌ 不支持 | ✅ 任意组合 |
| 扩展性 | 新增模式需改代码 | 配置即可 |
| 维护性 | 重复代码多 | 单一职责 |
| 测试用例 | 9个独立测试 | 4个基础 + 组合测试 |

---

## 8. 窗口大小单位

| 单位 | 含义 | 示例 |
|------|------|------|
| `d` | 天 | `30d` = 30天 |
| `w` | 周 | `1w` = 7天 |
| `m` | 月 | `1m` = 30天 |
| `q` | 季度 | `1q` = 90天 |
| `y` | 年 | `1y` = 365天 |

---

## 9. 实施建议

### 阶段一：核心替换（1-2天）
1. 备份旧文件
2. 复制新模块文件
3. 更新导入语句
4. 验证基础功能

### 阶段二：配置迁移（1天）
1. 编写配置迁移脚本
2. 批量转换接口配置
3. 验证配置正确性

### 阶段三：测试验证（1-2天）
1. 单元测试覆盖所有维度
2. 集成测试验证组合场景
3. 回归测试确保向后兼容

---

**文档版本**: 1.0  
**创建日期**: 2026-02-02
