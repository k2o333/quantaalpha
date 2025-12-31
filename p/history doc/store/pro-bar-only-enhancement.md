# Pro Bar Only 参数增强方案

## 目标
实现 `--pro-bar-only` 参数功能增强，使其能够遍历所有股票代码，为每个股票从2005年开始下载完整的复权行情数据。

## 当前问题
目前 `--pro-bar-only` 参数只下载最新6000条数据，没有充分利用TuShare API的分页功能来获取完整的股票历史数据。

## 解决方案

### 1. 主程序逻辑修改 (app4/main.py)

在 `main()` 函数中增强参数逻辑处理：

```python
# 在参数处理部分增强pro_bar_only逻辑
if args.pro_bar_only:
    interfaces_to_run = ['pro_bar']

    # 为pro_bar特别处理，获取完整的股票列表和日期范围
    if interface_name == 'pro_bar':
        # 自动设置日期范围从2005年至今
        params['start_date'] = '20050101'
        params['end_date'] = args.end_date or datetime.now().strftime('%Y%m%d')

        # 标记为股票循环模式
        params['download_mode'] = 'stock_loop'
```

### 2. 股票列表和交易日历获取函数

创建新的辅助函数来获取股票列表和交易日历：

```python
def get_stock_list(cache_manager):
    """获取所有A股股票列表，优先从缓存读取"""
    cache_key = "stock_basic_all"
    stock_list = cache_manager.get(cache_key)

    if stock_list is None:
        # 调用stock_basic接口获取股票列表
        # 这里需要创建一个临时下载器来获取股票列表
        stock_downloader = GenericDownloader(config_loader, cache_manager)
        params = {'list_status': 'L'}  # 只获取上市股票
        stock_list = stock_downloader.download('stock_basic', params)

        # 缓存股票列表，有效期24小时
        cache_manager.set(cache_key, stock_list, ttl=86400)

    return stock_list

def get_trade_calendar(cache_manager, start_date, end_date):
    """获取指定日期范围内的交易日历，优先从缓存读取"""
    cache_key = f"trade_cal_{start_date}_{end_date}"
    calendar = cache_manager.get(cache_key)

    if calendar is None:
        # 调用trade_cal接口获取交易日历
        calendar_downloader = GenericDownloader(config_loader, cache_manager)
        params = {
            'start_date': start_date,
            'end_date': end_date,
            'exchange': 'SSE'
        }
        calendar = calendar_downloader.download('trade_cal', params)

        # 缓存交易日历，有效期24小时
        cache_manager.set(cache_key, calendar, ttl=86400)

    return calendar
```

### 3. 分页逻辑增强 (app4/core/downloader.py)

增强 `_execute_pagination` 方法以支持股票循环分页：

```python
def _execute_stock_loop_pagination(self, interface_config: Dict[str, Any], params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """执行股票循环分页"""
    all_data = []

    # 如果参数中包含ts_code，则直接调用API
    if 'ts_code' in params:
        return self._make_request(interface_config, params)

    # 获取股票列表
    from .utils import get_stock_list  # 假设上面的函数放在utils模块中
    stock_list = get_stock_list(self.cache_manager)

    # 为每个股票下载数据
    for stock in stock_list:
        stock_params = params.copy()
        stock_params['ts_code'] = stock['ts_code']

        # 为每个股票下载数据
        stock_data = self._make_request(interface_config, stock_params)
        if stock_data:
            all_data.extend(stock_data)

    return all_data

def _execute_date_range_pagination(self, interface_config: Dict[str, Any], params: Dict[str, Any],
                                  pagination_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """执行日期范围分页"""
    all_data = []

    # 获取日期范围
    start_date = params.get('start_date', '20050101')
    end_date = params.get('end_date', datetime.now().strftime('%Y%m%d'))

    # 获取交易日历
    from .utils import get_trade_calendar
    trade_calendar = get_trade_calendar(self.cache_manager, start_date, end_date)
    trade_days = [day for day in trade_calendar if day.get('is_open', 0) == 1]

    # 按窗口分割日期范围
    window_size = pagination_config.get('window_size_days', 3650)  # 默认10年窗口

    for i in range(0, len(trade_days), window_size):
        window_trade_days = trade_days[i:i+window_size]
        window_start = window_trade_days[0]['cal_date']
        window_end = window_trade_days[-1]['cal_date']

        window_params = params.copy()
        window_params['start_date'] = window_start
        window_params['end_date'] = window_end

        # 下载该窗口的数据
        window_data = self._make_request(interface_config, window_params)
        if window_data:
            all_data.extend(window_data)

    return all_data
```

### 4. 缓存管理器增强 (app4/core/cache_manager.py)

增强缓存管理器以支持更复杂的数据缓存：

```python
class CacheManager:
    def get_stock_list(self):
        """获取股票列表缓存"""
        return self.get("stock_list")

    def set_stock_list(self, stock_list):
        """设置股票列表缓存"""
        self.set("stock_list", stock_list, ttl=86400)  # 24小时缓存

    def get_trade_calendar(self, start_date, end_date):
        """获取交易日历缓存"""
        cache_key = f"calendar_{start_date}_{end_date}"
        return self.get(cache_key)

    def set_trade_calendar(self, start_date, end_date, calendar):
        """设置交易日历缓存"""
        cache_key = f"calendar_{start_date}_{end_date}"
        self.set(cache_key, calendar, ttl=86400)  # 24小时缓存
```

### 5. 配置文件更新 (app4/config/interfaces/pro_bar.yaml)

更新pro_bar接口配置以支持股票循环分页：

```yaml
# 5. 分页与循环策略
pagination:
  enabled: true
  mode: "stock_loop"  # 改为股票循环模式
  date_pagination: true  # 同时启用日期分页
  window_size_days: 3650

# 增强参数配置
parameters:
  ts_code:
    type: string
    required: false  # 改为非必需，由系统自动填充
    description: "证券代码"
  start_date:
    type: string
    required: false
    default: "20050101"  # 默认从2005年开始
    description: "开始日期 YYYYMMDD"
  end_date:
    type: string
    required: false
    description: "结束日期 YYYYMMDD"

output:
  primary_key:
    - ts_code
    - trade_date
  cache:
    enabled: true
    ttl: 86400  # 24小时缓存
```

## 实施步骤

1. 修改主程序逻辑，增强`--pro-bar-only`参数处理
2. 实现股票列表获取和缓存函数
3. 实现交易日历获取和缓存函数
4. 增强下载器的分页逻辑
5. 更新配置文件
6. 测试功能并优化性能

## 预期效果

1. 使用`--pro-bar-only`参数时，系统自动下载所有A股股票的历史数据
2. 数据时间范围从2005年至今
3. 利用缓存机制减少API调用次数
4. 支持断点续传，提高下载稳定性
5. 数据按股票代码分别存储，便于后续处理

## 注意事项

1. 需要考虑API调用频率限制，适当添加延迟
2. 大量数据下载可能需要较长时间，需提供进度显示
3. 考虑磁盘空间需求，完整历史数据可能占用较大空间
4. 实现错误处理机制，确保单个股票下载失败不影响整体流程