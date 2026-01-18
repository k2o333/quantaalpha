# TuShare API 重复下载与缓存使用问题分析与测试方案

## 问题描述
用户反馈在使用 TuShare API 时发现有重复下载相同股票代码数据，但是没有使用缓存的情况。本方案旨在系统性地测试和分析问题根源。

## 问题分析
根据对代码的分析，可能的原因包括：
1. 缓存键生成和匹配机制问题
2. 缓存TTL设置过短
3. 参数差异导致缓存键不一致
4. 缓存文件损坏或不完整

## 测试方案

### 测试1: 缓存键一致性测试
**目的**: 验证相同参数是否生成相同的缓存键

**步骤**:
1. 选择一个具体的接口（例如 `daily_basic`）和固定参数
2. 多次调用 `CacheKeyGenerator.generate_cache_path` 函数
3. 检查生成的缓存路径是否一致

**代码示例**:
```python
from app.cache_key_generator import CacheKeyGenerator
import hashlib

# 测试参数
interface_name = 'daily_basic'
trade_date = '20231201'

# 多次生成缓存路径
for i in range(5):
    path = CacheKeyGenerator.generate_cache_path(interface_name, trade_date=trade_date)
    print(f"第{i+1}次生成的路径: {path}")

    # 提取参数并验证
    extracted = CacheKeyGenerator.extract_params_from_cache_path(path)
    print(f"提取参数: {extracted}")
```

### 测试2: 缓存存储和读取测试
**目的**: 验证缓存是否正常存储和读取

**步骤**:
1. 手动下载一批数据
2. 检查该数据是否被正确存储到缓存文件
3. 验证后续请求是否能正确从缓存读取

**代码示例**:
```python
import pandas as pd
from pathlib import Path
from app.data_storage import get_interface_cache_path, save_interface_data_to_cache, load_interface_cached_data

interface_name = 'daily'
start_date = '20231201'
end_date = '20231202'

# 1. 创建测试数据
test_data = pd.DataFrame({
    'ts_code': ['000001.SZ', '000002.SZ'],
    'trade_date': ['20231201', '20231201'],
    'open': [10.0, 20.0],
    'close': [10.5, 20.5]
})

# 2. 存储到缓存
save_success = save_interface_data_to_cache(
    test_data,
    interface_name,
    start_date=start_date,
    end_date=end_date
)
print(f"缓存存储结果: {save_success}")

# 3. 检查缓存文件是否存在于指定路径
cache_path = get_interface_cache_path(interface_name, start_date=start_date, end_date=end_date)
print(f"缓存路径: {cache_path}")
print(f"缓存文件是否存在: {Path(cache_path).exists()}")

# 4. 从缓存加载数据
cached_data = load_interface_cached_data(interface_name, start_date=start_date, end_date=end_date)
print(f"从缓存加载的数据条数: {len(cached_data)}")
```

### 测试3: 重复请求缓存命中测试
**目的**: 模拟重复请求场景，验证缓存使用情况

**步骤**:
1. 使用相同的请求参数进行第一次下载
2. 紧接着使用相同的参数进行第二次下载
3. 记录第二次下载是否使用了缓存

**测试代码框架**:
```python
import time
from app.download_strategies import DailyDataStrategy
from app.tushare_api import TuShareDownloader

downloader = TuShareDownloader()
strategy = DailyDataStrategy('daily_basic', downloader)

# 记录日志以监控缓存命中
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

# 第一次请求
start_time = time.time()
result1 = strategy.download_with_cache(trade_date='20231201')
first_duration = time.time() - start_time
print(f"首次下载耗时: {first_duration:.2f}秒")

# 立即第二次请求相同数据
time.sleep(1)  # 短暂间隔
start_time = time.time()
result2 = strategy.download_with_cache(trade_date='20231201')
second_duration = time.time() - start_time
print(f"重复下载耗时: {second_duration:.2f}秒")

# 比较两次结果
print(f"首次结果条数: {len(result1)}")
print(f"重复结果条数: {len(result2)}")
print(f"两次结果是否相同: {result1.equals(result2)}")
print(f"第二次是否更快（可能是缓存）: {second_duration < first_duration * 0.5}")
```

### 测试4: 参数标准化测试
**目的**: 检查不同形式的相同参数是否能生成相同的缓存键

**步骤**:
1. 使用不同顺序的参数字典
2. 使用不同格式但等价的值（如字符串和整数）
3. 验证这些参数是否生成相同缓存键

**代码示例**:
```python
from app.cache_key_generator import CacheKeyGenerator

# 测试相同参数不同顺序
path1 = CacheKeyGenerator.generate_cache_path('daily', start_date='20230101', end_date='20230102')
path2 = CacheKeyGenerator.generate_cache_path('daily', end_date='20230102', start_date='20230101')
print(f"不同顺序参数生成的路径是否相同: {path1 == path2}")

# 测试参数键值是否标准化
path3 = CacheKeyGenerator.generate_cache_path('daily', start_date='20230101', ts_code='000001.SZ')
path4 = CacheKeyGenerator.generate_cache_path('daily', ts_code='000001.SZ', start_date='20230101')
print(f"不同顺序的复杂参数生成的路径是否相同: {path3 == path4}")
```

### 测试5: 多进程/多线程并发缓存测试
**目的**: 验证并发访问是否影响缓存行为

**代码示例**:
```python
import threading
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from app.download_strategies import DailyDataStrategy
from app.tushare_api import TuShareDownloader

def test_concurrent_download(params):
    """并发测试函数"""
    downloader = TuShareDownloader()
    strategy = DailyDataStrategy('daily_basic', downloader)
    return strategy.download_with_cache(trade_date=params['trade_date'])

# 同时发起多个相同请求
test_params = [{'trade_date': '20231201'} for _ in range(5)]

start_time = time.time()
with ThreadPoolExecutor(max_workers=5) as executor:
    results = list(executor.map(test_concurrent_download, test_params))

total_time = time.time() - start_time
print(f"并发下载{len(test_params)}次耗时: {total_time:.2f}秒")

# 检查是否有重复下载
actual_downloads = sum(1 for df in results if len(df) > 0)
print(f"实际下载次数: {actual_downloads}")
```

### 测试6: 股票列表管理器的缓存测试
**目的**: 验证股票列表的缓存是否正常工作

**代码示例**:
```python
from app.stock_list_manager import StockListManager, init_stock_manager
from app.tushare_api import TuShareDownloader

# 初始化管理器
downloader = TuShareDownloader()
manager = init_stock_manager(downloader)

# 第一次获取股票列表
print("第一次获取股票列表...")
df1 = manager.get_stock_basic()
print(f"第一次获取股票数量: {len(df1)}")

# 第二次获取股票列表（应该使用缓存）
print("第二次获取股票列表...")
df2 = manager.get_stock_basic()
print(f"第二次获取股票数量: {len(df2)}")

# 检查是否使用了缓存
print(f"两次结果是否相同: {df1.equals(df2)}")

# 检查缓存状态
status = manager.get_cache_status()
print(f"缓存状态: {status}")
```

## 执行顺序和指标
1. **先执行缓存键一致性测试**：验证缓存系统的基础功能
2. **再执行缓存存储和读取测试**：验证缓存的读写功能
3. **执行重复请求缓存命中测试**：验证核心问题
4. **执行参数标准化测试**：验证参数处理
5. **执行并发测试**：验证在多线程环境下的行为
6. **执行股票列表管理器测试**：验证特定组件

## 预期结果
- 如果是缓存键问题：相同参数生成不同路径
- 如果是缓存读写问题：存储后无法正确读取
- 如果是参数标准化问题：不同顺序参数生成不同缓存键
- 如果是并发问题：多个线程同时下载相同数据

## 问题定位
根据测试结果，我们可以定位问题属于以下哪一类：
1. **缓存机制故障** - 缓存键生成或读写有问题
2. **参数处理问题** - 相同逻辑但参数不一致
3. **并发控制问题** - 多线程环境下的竞态条件
4. **配置问题** - 缓存TTL设置不合理

## 附加测试
- 测试不同接口类型的缓存行为差异
- 检查日志中关于缓存命中/未命中的记录
- 验证缓存文件的完整性和内容