# TuShare接口进化方案

## 概述

本文档旨在提供一个完整的TuShare接口进化方案，将现有接口按照积分等级和优化策略进行分类和重构，确保高效、合理的数据下载。

## 接口分类策略

### 第一类：VIP接口（5000积分+，按报告期下载全市场数据）

这些接口应该优先使用VIP版本，避免循环股票代码：

- `income` → `income_vip(period)`
- `balancesheet` → `balancesheet_vip(period)`
- `cashflow` → `cashflow_vip(period)`
- `express` → `express_vip(period)`
- `fina_indicator` → `fina_indicator_vip(period)`
- `fina_mainbz` → `fina_mainbz_vip(period)`

### 第二类：必须循环股票代码接口（无VIP替代或逻辑决定）

这些接口无法使用VIP版本，必须针对个股循环：

- `stk_rewards(ts_code)` - 管理层薪酬和持股
- `top10_holders(ts_code, period)` - 前十大股东
- `top10_floatholders(ts_code, period)` - 前十大流通股东
- `pledge_detail(ts_code)` - 股权质押明细
- `pro_bar(ts_code)` - 复权行情（个股计算）
- `fina_audit(ts_code, period)` - 财务审计意见

### 第三类：按日期下载接口（无需股票代码）

这些接口应该使用日期参数下载全市场数据：

- `daily_basic(trade_date)` - 每日指标
- `daily(trade_date)` - 日线行情
- `moneyflow(trade_date)` - 个股资金流向
- `moneyflow_dc(trade_date)` - 个股资金流向（DC）
- `moneyflow_ths(trade_date)` - 个股资金流向（THS）

## 进化步骤

### 第一步：接口参数标准化

```python
# 定义接口参数策略
INTERFACE_STRATEGIES = {
    # VIP接口
    'income': {
        'strategy': 'vip_period',  # 使用VIP接口按报告期下载
        'params': ['period'],
        'min_points': 2000,
        'vip_points': 5000
    },
    'balancesheet': {
        'strategy': 'vip_period',
        'params': ['period'],
        'min_points': 2000,
        'vip_points': 5000
    },
    'cashflow': {
        'strategy': 'vip_period',
        'params': ['period'],
        'min_points': 2000,
        'vip_points': 5000
    },
    'express': {
        'strategy': 'vip_period',
        'params': ['period'],
        'min_points': 2000,
        'vip_points': 5000
    },
    'fina_indicator': {
        'strategy': 'vip_period',
        'params': ['period'],
        'min_points': 2000,
        'vip_points': 5000
    },
    'fina_mainbz': {
        'strategy': 'vip_period',
        'params': ['period'],
        'min_points': 2000,
        'vip_points': 5000
    },
    
    # 循环股票接口
    'stk_rewards': {
        'strategy': 'stock_loop',  # 循环股票代码
        'params': ['ts_code'],
        'min_points': 2000
    },
    'top10_holders': {
        'strategy': 'stock_loop',
        'params': ['ts_code', 'period'],
        'min_points': 2000
    },
    'top10_floatholders': {
        'strategy': 'stock_loop',
        'params': ['ts_code', 'period'],
        'min_points': 5000
    },
    'pledge_detail': {
        'strategy': 'stock_loop',
        'params': ['ts_code'],
        'min_points': 500
    },
    'fina_audit': {
        'strategy': 'stock_loop',
        'params': ['ts_code', 'period'],
        'min_points': 500
    },
    
    # 日期接口
    'daily_basic': {
        'strategy': 'date_range',  # 按日期范围下载
        'params': ['trade_date'],
        'min_points': 2000
    },
    'daily': {
        'strategy': 'date_range',
        'params': ['trade_date'],
        'min_points': 120
    },
    'moneyflow': {
        'strategy': 'date_range',
        'params': ['trade_date'],
        'min_points': 2000
    }
}
```

### 第二步：实现智能下载调度器

```python
class SmartDownloadScheduler:
    def __init__(self, points: int):
        self.points = points
        self.interface_strategies = INTERFACE_STRATEGIES
        
    def get_download_strategy(self, interface_name: str) -> str:
        """根据接口名和用户积分获取下载策略"""
        config = self.interface_strategies.get(interface_name)
        if not config:
            return 'default'
            
        strategy = config['strategy']
        
        # 对于VIP接口，检查用户是否满足VIP条件
        if strategy == 'vip_period' and self.points >= config.get('vip_points', 5000):
            return 'vip_period'
        elif strategy == 'vip_period':
            # 用户积分不够，降级为股票循环
            return 'stock_loop'
        
        return strategy
    
    def schedule_download(self, interface_name: str, **kwargs):
        """根据策略调度下载任务"""
        strategy = self.get_download_strategy(interface_name)
        
        if strategy == 'vip_period':
            return self._download_vip_period(interface_name, **kwargs)
        elif strategy == 'stock_loop':
            return self._download_stock_loop(interface_name, **kwargs)
        elif strategy == 'date_range':
            return self._download_date_range(interface_name, **kwargs)
        else:
            return self._download_default(interface_name, **kwargs)
    
    def _download_vip_period(self, interface_name: str, period: str, **kwargs):
        """使用VIP接口按报告期下载全市场数据"""
        # 使用VIP接口名称
        vip_interface_name = f"{interface_name}_vip"
        return getattr(self.downloader, f"download_{vip_interface_name}")(period=period)
    
    def _download_stock_loop(self, interface_name: str, ts_code: str = None, **kwargs):
        """循环股票代码下载"""
        if ts_code:
            # 单个股票下载
            return getattr(self.downloader, f"download_{interface_name}")(ts_code=ts_code, **kwargs)
        else:
            # 所有股票循环下载
            from stock_list_manager import StockListManager
            stock_manager = StockListManager()
            stock_list = stock_manager.get_stock_basic()
            
            all_data = []
            for _, stock in stock_list.iterrows():
                ts_code = stock['ts_code']
                try:
                    df = getattr(self.downloader, f"download_{interface_name}")(ts_code=ts_code, **kwargs)
                    if not df.empty:
                        all_data.append(df)
                except Exception as e:
                    print(f"下载股票 {ts_code} 失败: {e}")
                    continue
            return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()
    
    def _download_date_range(self, interface_name: str, trade_date: str = None, **kwargs):
        """按日期下载全市场数据"""
        if trade_date:
            return getattr(self.downloader, f"download_{interface_name}")(trade_date=trade_date)
        else:
            # 按日期范围循环下载
            from tushare_api import TuShareDownloader
            downloader = TuShareDownloader()
            trade_cal = downloader.download_trade_cal(start_date=kwargs.get('start_date'), 
                                                    end_date=kwargs.get('end_date'))
            
            all_data = []
            for _, day in trade_cal.iterrows():
                if day['is_open'] == 1:
                    trade_date = day['cal_date']
                    try:
                        df = getattr(self.downloader, f"download_{interface_name}")(trade_date=trade_date)
                        if not df.empty:
                            all_data.append(df)
                    except Exception as e:
                        print(f"下载日期 {trade_date} 失败: {e}")
                        continue
            return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()
```

### 第三步：更新配置文件

```python
# enhanced_download_config.py 更新
from enhanced_download_config import DataTypePriority, DownloadStrategy

ENHANCED_DOWNLOAD_PIPELINE_CONFIG = {
    # VIP接口 - 高优先级
    'income': InterfaceConfig(
        enabled=True,
        priority=DataTypePriority.HIGH,
        strategy=DownloadStrategy.BATCH,
        required_points=5000,  # 需要5000积分使用VIP
        api_params={'use_vip': True}
    ),
    'balancesheet': InterfaceConfig(
        enabled=True,
        priority=DataTypePriority.HIGH,
        strategy=DownloadStrategy.BATCH,
        required_points=5000,
        api_params={'use_vip': True}
    ),
    'cashflow': InterfaceConfig(
        enabled=True,
        priority=DataTypePriority.HIGH,
        strategy=DownloadStrategy.BATCH,
        required_points=5000,
        api_params={'use_vip': True}
    ),
    'express': InterfaceConfig(
        enabled=True,
        priority=DataTypePriority.HIGH,
        strategy=DownloadStrategy.BATCH,
        required_points=5000,
        api_params={'use_vip': True}
    ),
    'fina_indicator': InterfaceConfig(
        enabled=True,
        priority=DataTypePriority.HIGH,
        strategy=DownloadStrategy.BATCH,
        required_points=5000,
        api_params={'use_vip': True}
    ),
    'fina_mainbz': InterfaceConfig(
        enabled=True,
        priority=DataTypePriority.MEDIUM,
        strategy=DownloadStrategy.BATCH,
        required_points=5000,
        api_params={'use_vip': True}
    ),
    
    # 循环股票接口
    'stk_rewards': InterfaceConfig(
        enabled=True,
        priority=DataTypePriority.MEDIUM,
        strategy=DownloadStrategy.SEQUENTIAL,
        required_points=2000,
        api_params={'use_vip': False}
    ),
    'top10_holders': InterfaceConfig(
        enabled=True,
        priority=DataTypePriority.MEDIUM,
        strategy=DownloadStrategy.SEQUENTIAL,
        required_points=2000,
        api_params={'use_vip': False}
    ),
    'top10_floatholders': InterfaceConfig(
        enabled=True,
        priority=DataTypePriority.LOW,
        strategy=DownloadStrategy.SEQUENTIAL,
        required_points=5000,
        api_params={'use_vip': False}
    ),
    'pledge_detail': InterfaceConfig(
        enabled=True,
        priority=DataTypePriority.LOW,
        strategy=DownloadStrategy.SEQUENTIAL,
        required_points=500,
        api_params={'use_vip': False}
    ),
    'fina_audit': InterfaceConfig(
        enabled=True,
        priority=DataTypePriority.LOW,
        strategy=DownloadStrategy.SEQUENTIAL,
        required_points=500,
        api_params={'use_vip': False}
    ),
    
    # 日期接口
    'daily_basic': InterfaceConfig(
        enabled=True,
        priority=DataTypePriority.HIGH,
        strategy=DownloadStrategy.PARALLEL,
        required_points=2000,
        api_params={'use_vip': False, 'by_date': True}
    ),
    'daily': InterfaceConfig(
        enabled=True,
        priority=DataTypePriority.HIGH,
        strategy=DownloadStrategy.PARALLEL,
        required_points=120,
        api_params={'use_vip': False, 'by_date': True}
    ),
    'moneyflow': InterfaceConfig(
        enabled=True,
        priority=DataTypePriority.MEDIUM,
        strategy=DownloadStrategy.PARALLEL,
        required_points=2000,
        api_params={'use_vip': False, 'by_date': True}
    )
}
```

### 第四步：参数验证器增强

```python
class EnhancedParameterValidator:
    def __init__(self):
        self.validation_rules = {
            'income': {
                'vip_required_params': ['period'],
                'vip_forbidden_params': ['ts_code'],  # VIP模式下不应有ts_code
                'min_points': 5000
            },
            'balancesheet': {
                'vip_required_params': ['period'],
                'vip_forbidden_params': ['ts_code'],
                'min_points': 5000
            },
            'cashflow': {
                'vip_required_params': ['period'],
                'vip_forbidden_params': ['ts_code'],
                'min_points': 5000
            },
            'daily_basic': {
                'date_required_params': ['trade_date'],
                'min_points': 2000
            }
        }
    
    def validate_for_strategy(self, interface_name: str, strategy: str, params: dict, user_points: int) -> dict:
        """根据下载策略验证参数"""
        rules = self.validation_rules.get(interface_name, {})
        
        if strategy == 'vip_period':
            # 验证VIP参数
            if user_points < rules.get('min_points', 5000):
                raise ValueError(f"积分不足，需要{rules.get('min_points', 5000)}积分使用VIP接口")
            
            required = rules.get('vip_required_params', [])
            forbidden = rules.get('vip_forbidden_params', [])
            
            for param in required:
                if param not in params:
                    raise ValueError(f"VIP模式下必须提供参数: {param}")
            
            for param in forbidden:
                if param in params and params[param]:
                    print(f"警告: VIP模式下不应提供{param}参数，将被忽略")
                    del params[param]
        
        elif strategy == 'date_range':
            # 验证日期参数
            if 'trade_date' not in params and not ('start_date' in params and 'end_date' in params):
                raise ValueError("日期模式下必须提供trade_date或start_date+end_date参数")
        
        return params
```

### 第五步：实现接口适配器

```python
class InterfaceAdapter:
    def __init__(self, points: int):
        self.points = points
        self.scheduler = SmartDownloadScheduler(points)
        self.validator = EnhancedParameterValidator()
    
    def download(self, interface_name: str, **kwargs):
        """智能下载接口"""
        # 获取下载策略
        strategy = self.scheduler.get_download_strategy(interface_name)
        
        # 验证参数
        validated_kwargs = self.validator.validate_for_strategy(
            interface_name, strategy, kwargs, self.points
        )
        
        # 执行下载
        return self.scheduler.schedule_download(interface_name, **validated_kwargs)
```

## 实施建议

### 1. 优先级排序
- 首先实现VIP接口的优化（影响最大）
- 然后优化日期范围下载接口
- 最后处理循环股票接口的效率优化

### 2. 渐进式迁移
- 保持向后兼容
- 逐步替换旧的下载逻辑
- 添加详细的日志记录以便监控效果

### 3. 性能监控
- 记录每种策略的下载效率
- 监控API调用次数和成功率
- 定期评估积分使用情况

### 4. 错误处理
- 为VIP接口添加降级机制
- 当VIP接口失败时自动切换到普通接口
- 提供详细的错误日志便于调试

## 预期效果

通过以上进化方案，预期可以实现：

1. **效率提升**：VIP接口可将某些财务数据下载时间从数小时缩短到几分钟
2. **API调用优化**：减少不必要的API调用，更好地利用积分
3. **代码维护性**：统一的接口策略使代码更易维护和扩展
4. **用户积分节约**：更高效的下载策略可节约用户积分消耗