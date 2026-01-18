# TuShare接口参数优化下载实现示例

## 1. 交易日历管理器

```python
import pandas as pd
import logging
from datetime import datetime
from typing import List, Optional

class TradingCalendarManager:
    """
    交易日历管理器，用于获取和缓存交易日历
    """
    
    def __init__(self, cache_manager):
        self.cache_manager = cache_manager
        self.logger = logging.getLogger(__name__)
    
    def get_trading_days(self, start_date: str, end_date: str) -> List[str]:
        """
        获取指定日期范围内的交易日
        
        Args:
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)
            
        Returns:
            交易日列表
        """
        # 尝试从缓存获取
        cache_key = f"trading_calendar_{start_date}_{end_date}"
        cached_data = self.cache_manager.get(cache_key)
        
        if cached_data:
            self.logger.info(f"从缓存获取交易日历: {start_date} - {end_date}")
            return [day['cal_date'] for day in cached_data if day.get('is_open') == 1]
        
        # 缓存未命中，从API获取
        self.logger.info(f"从API获取交易日历: {start_date} - {end_date}")
        
        # 这里调用TuShare API获取交易日历
        # pro = ts.pro_api()
        # calendar_data = pro.trade_cal(exchange='', start_date=start_date, end_date=end_date)
        # trading_days = calendar_data[calendar_data['is_open'] == 1]['cal_date'].tolist()
        
        # 模拟数据
        from dateutil.rrule import rrule, DAILY
        from datetime import datetime
        import random
        
        start = datetime.strptime(start_date, '%Y%m%d')
        end = datetime.strptime(end_date, '%Y%m%d')
        
        trading_days = []
        for date in rrule(DAILY, dtstart=start, until=end):
            date_str = date.strftime('%Y%m%d')
            # 模拟交易日（排除周末）
            if date.weekday() < 5:  # 周一到周五
                trading_days.append(date_str)
        
        # 缓存结果
        calendar_records = [{'cal_date': day, 'is_open': 1} for day in trading_days]
        self.cache_manager.set(cache_key, calendar_records)
        
        return trading_days
```

## 2. 参数计算器

```python
from typing import Dict, List, Any

class ParameterCalculator:
    """
    参数计算器，根据接口特点计算最优下载参数
    """
    
    def __init__(self, calendar_manager):
        self.calendar_manager = calendar_manager
    
    def calculate_daily_params(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        计算日线数据的下载参数
        """
        ts_code = params.get('ts_code')
        start_date = params.get('start_date')
        end_date = params.get('end_date')
        
        if not start_date or not end_date:
            # 如果没有指定日期范围，返回原始参数
            return [params]
        
        # 获取交易日历
        trading_days = self.calendar_manager.get_trading_days(start_date, end_date)
        
        if not trading_days:
            return []
        
        # 如果指定了股票代码，按股票下载
        if ts_code:
            # 按交易日分批，避免API限制
            batch_size = 3000  # API限制为6000，预留空间
            params_list = []
            
            for i in range(0, len(trading_days), batch_size):
                batch_days = trading_days[i:i+batch_size]
                batch_params = {
                    'ts_code': ts_code,
                    'start_date': batch_days[0],
                    'end_date': batch_days[-1]
                }
                params_list.append(batch_params)
            
            return params_list
        else:
            # 全市场下载，按日期分批
            params_list = []
            for trade_date in trading_days:
                params_list.append({
                    'trade_date': trade_date
                })
            
            return params_list
    
    def calculate_finance_params(self, interface_name: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        计算财务数据的下载参数
        """
        ts_code = params.get('ts_code')
        start_date = params.get('start_date')
        end_date = params.get('end_date')
        
        if not ts_code:
            # 如果没有指定股票，返回原始参数
            return [params]
        
        # 生成季度报告期
        periods = self._generate_quarter_periods(start_date, end_date)
        
        params_list = []
        for period in periods:
            params_list.append({
                'ts_code': ts_code,
                'period': period
            })
        
        return params_list
    
    def _generate_quarter_periods(self, start_date: str, end_date: str) -> List[str]:
        """
        生成季度报告期列表
        """
        from datetime import datetime
        
        start_year = int(start_date[:4])
        start_month = int(start_date[4:6])
        end_year = int(end_date[:4])
        end_month = int(end_date[4:6])
        
        periods = []
        for year in range(start_year, end_year + 1):
            for quarter in [3, 6, 9, 12]:
                period = f"{year}{quarter:02d}31"
                
                # 检查是否在范围内
                if year == start_year and quarter*100 + 31 < int(start_date[4:]):
                    continue
                if year == end_year and quarter*100 + 31 > int(end_date[4:]):
                    continue
                
                periods.append(period)
        
        return periods
```

## 3. 增量下载器

```python
import hashlib
from typing import Dict, Any, List

class IncrementalDownloader:
    """
    增量下载器，基于主键检查避免重复下载
    """
    
    def __init__(self, api_client, storage_manager, cache_manager):
        self.api_client = api_client
        self.storage_manager = storage_manager
        self.cache_manager = cache_manager
        self.primary_key_mapping = {
            'daily': ['ts_code', 'trade_date'],
            'daily_basic': ['ts_code', 'trade_date'],
            'income': ['ts_code', 'ann_date', 'end_date'],
            'balancesheet': ['ts_code', 'ann_date', 'end_date'],
            'stock_basic': ['ts_code'],
            'trade_cal': ['cal_date', 'exchange']
        }
    
    def get_primary_key(self, interface_name: str, record: Dict[str, Any]) -> str:
        """
        生成记录的主键
        """
        if interface_name not in self.primary_key_mapping:
            # 默认使用所有字段生成哈希
            return hashlib.md5(str(sorted(record.items())).encode()).hexdigest()
        
        primary_keys = self.primary_key_mapping[interface_name]
        key_parts = []
        
        for key in primary_keys:
            if key in record and record[key] is not None:
                key_parts.append(str(record[key]))
        
        return "|".join(key_parts)
    
    def record_exists(self, interface_name: str, primary_key: str) -> bool:
        """
        检查记录是否已存在
        """
        # 这里可以查询本地存储或缓存来检查记录是否存在
        # 实现方式取决于具体的存储方案
        cache_key = f"exists_{interface_name}_{primary_key}"
        exists = self.cache_manager.get(cache_key)
        return exists is not None
    
    def mark_record_exists(self, interface_name: str, primary_key: str):
        """
        标记记录已存在
        """
        cache_key = f"exists_{interface_name}_{primary_key}"
        self.cache_manager.set(cache_key, True)
    
    def download_incremental(self, interface_name: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        增量下载数据
        """
        # 从API获取数据
        raw_data = self.api_client.call(interface_name, params)
        
        if not raw_data:
            return []
        
        # 过滤已存在的记录
        new_data = []
        for record in raw_data:
            primary_key = self.get_primary_key(interface_name, record)
            
            if not self.record_exists(interface_name, primary_key):
                new_data.append(record)
                # 标记记录已存在
                self.mark_record_exists(interface_name, primary_key)
            else:
                self.logger.info(f"跳过已存在记录: {interface_name} - {primary_key}")
        
        return new_data
```

## 4. 综合下载器

```python
class OptimizedDownloader:
    """
    优化的下载器，结合参数计算和增量下载
    """
    
    def __init__(self, api_client, storage_manager, cache_manager):
        self.api_client = api_client
        self.storage_manager = storage_manager
        self.cache_manager = cache_manager
        self.calendar_manager = TradingCalendarManager(cache_manager)
        self.param_calculator = ParameterCalculator(self.calendar_manager)
        self.incremental_downloader = IncrementalDownloader(
            api_client, storage_manager, cache_manager
        )
    
    def download_optimized(self, interface_name: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        优化下载流程
        """
        # 1. 计算最优参数
        if interface_name == 'daily':
            param_list = self.param_calculator.calculate_daily_params(params)
        elif interface_name in ['income', 'balancesheet']:
            param_list = self.param_calculator.calculate_finance_params(interface_name, params)
        else:
            # 其他接口使用原始参数
            param_list = [params]
        
        # 2. 批量下载
        all_new_data = []
        for param in param_list:
            new_data = self.incremental_downloader.download_incremental(interface_name, param)
            all_new_data.extend(new_data)
        
        return all_new_data
```

## 5. 使用示例

```python
# 使用示例
def example_usage():
    # 初始化组件
    # cache_manager = CacheManager()
    # storage_manager = StorageManager()
    # api_client = TuShareClient()
    
    # downloader = OptimizedDownloader(api_client, storage_manager, cache_manager)
    
    # 下载平安银行2023年日线数据
    params = {
        'ts_code': '000001.SZ',
        'start_date': '20230101',
        'end_date': '20231231'
    }
    
    # 优化下载
    data = downloader.download_optimized('daily', params)
    
    print(f"下载了 {len(data)} 条新记录")
```