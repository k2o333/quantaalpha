# TuShare API pro_bar接口测试执行指南

## 1. 测试环境准备

### 1.1 环境配置
```bash
# 进入项目目录
cd /home/quan/testdata/aspipe_v4

# 确保依赖已安装
pip install -r requirements.txt

# 配置环境变量（确保有有效的TuShare Token）
echo "tushare_token=YOUR_VALID_TOKEN" > .env
echo "tushare_points=5000" >> .env

# 创建必要的目录
mkdir -p log cache data
```

### 1.2 日志配置
```bash
# 设置日志级别为DEBUG
export LOG_LEVEL=DEBUG
```

## 2. 各测试用例执行方法

### 2.1 测试1: 接口配置验证
**文件**: `test_case_1_config_validation.py`

**目的**: 验证pro_bar接口配置是否正确

**执行命令**:
```bash
cd /home/quan/testdata/aspipe_v4
python -c "
import sys
sys.path.append('/home/quan/testdata/aspipe_v4')
from app.enhanced_download_config import DOWNLOAD_PIPELINE_CONFIG
from app.download_scheduler import DownloadScheduler

# 检查接口配置
pro_bar_config = DOWNLOAD_PIPELINE_CONFIG.get('pro_bar')
if pro_bar_config:
    print('pro_bar接口配置:')
    print(f'  requires_tscode: {getattr(pro_bar_config, \"requires_tscode\", False)}')
    print(f'  cache_enabled: {pro_bar_config.cache_enabled}')
    print(f'  cache_ttl_hours: {pro_bar_config.cache_ttl_hours}')
    print(f'  priority: {pro_bar_config.priority}')
    print(f'  strategy: {pro_bar_config.strategy}')
else:
    print('ERROR: pro_bar接口配置未找到')

# 检查调度器识别
scheduler = DownloadScheduler('20230101', '20231231')
is_tscode_interface = scheduler._is_tscode_interface('pro_bar')
print(f'调度器是否识别pro_bar为ts_code接口: {is_tscode_interface}')
```

### 2.2 测试2: 缓存键生成一致性
**文件**: `test_case_2_cache_key_consistency.py`

**目的**: 验证相同参数是否生成相同的缓存键和路径

**执行命令**:
```bash
cd /home/quan/testdata/aspipe_v4
python -c "
import sys
sys.path.append('/home/quan/testdata/aspipe_v4')
from app.cache_key_generator import CacheKeyGenerator

# 测试参数
params = {
    'interface_name': 'pro_bar',
    'ts_code': '000001.SZ',
    'start_date': '20230101',
    'end_date': '20231231',
    'adj': 'qfq',
    'freq': 'D'
}
print('使用参数:', params)

# 多次生成缓存路径
paths = []
cache_keys = []
for i in range(5):
    path = CacheKeyGenerator.generate_cache_path(**params)
    cache_key = CacheKeyGenerator.generate_cache_key(**params)
    paths.append(path)
    cache_keys.append(cache_key)
    print(f'第{i+1}次:')
    print(f'  缓存路径: {path}')
    print(f'  缓存键: {cache_key}')

# 验证一致性
all_paths_same = all(p == paths[0] for p in paths)
all_keys_same = all(k == cache_keys[0] for k in cache_keys)
print(f'所有缓存路径是否相同: {all_paths_same}')
print(f'所有缓存键是否相同: {all_keys_same}')

if not all_paths_same:
    print('ERROR: 缓存路径不一致')
if not all_keys_same:
    print('ERROR: 缓存键不一致')
```

### 2.3 测试3: ts_code参数标准化
**文件**: `test_case_3_tscode_normalization.py`

**目的**: 验证不同格式的ts_code参数是否能正确处理

**执行命令**:
```bash
cd /home/quan/testdata/aspipe_v4
python -c "
import sys
sys.path.append('/home/quan/testdata/aspipe_v4')
from app.cache_key_generator import CacheKeyGenerator
from app.parameter_adapters import ParameterAdapterManager

base_params = {
    'start_date': '20230101',
    'end_date': '20231231',
    'adj': 'qfq',
    'freq': 'D'
}

ts_code_variants = [
    '000001.SZ',  # 标准格式
    '000001.sz',  # 小写后缀
    '000001',     # 无后缀
]

paths = []
adapted_codes = []

adapter = ParameterAdapterManager()

for ts_code in ts_code_variants:
    # 参数适配
    params = {**base_params, 'ts_code': ts_code}
    adapted_params = adapter.adapt_parameters('pro_bar', params)
    adapted_code = adapted_params.get('ts_code', 'UNAVAILABLE')
    adapted_codes.append(adapted_code)

    # 生成缓存路径
    path = CacheKeyGenerator.generate_cache_path('pro_bar', **params)
    paths.append(path)

    print(f'ts_code原始: {ts_code}, 适配后: {adapted_code}, 缓存路径: {path}')

# 验证一致性
all_paths_same = all(p == paths[0] for p in paths)
all_codes_normalized = all(code == '000001.SZ' for code in adapted_codes)
print(f'所有缓存路径是否相同: {all_paths_same}')
print(f'所有适配后ts_code是否相同: {all_codes_normalized}')

if not all_paths_same:
    print('WARNING: 不同ts_code格式生成不同缓存路径')
if not all_codes_normalized:
    print('WARNING: ts_code未正确标准化')
```

### 2.4 测试4: 缓存存储和读取
**文件**: `test_case_4_cache_storage.py`

**目的**: 验证数据能否正确存储到缓存并被读取

**执行命令**:
```bash
cd /home/quan/testdata/aspipe_v4
python -c "
import sys
import os
import pandas as pd
sys.path.append('/home/quan/testdata/aspipe_v4')
from app.data_storage import (
    save_interface_data_to_cache,
    load_interface_cached_data,
    get_interface_cache_path
)

# 创建测试数据
test_data = pd.DataFrame({
    'ts_code': ['000001.SZ'] * 3,
    'trade_date': ['20230101', '20230102', '20230103'],
    'open': [10.0, 10.1, 10.2],
    'close': [10.5, 10.6, 10.7],
    'vol': [1000000, 1100000, 1200000]
})

params = {
    'ts_code': '000001.SZ',
    'start_date': '20230101',
    'end_date': '20230103',
    'adj': 'qfq'
}

print(f'测试数据条数: {len(test_data)}')

# 保存到缓存
save_result = save_interface_data_to_cache(test_data, 'pro_bar', **params)
print(f'保存结果: {save_result}')

# 检查缓存文件
cache_path = get_interface_cache_path('pro_bar', **params)
print(f'缓存文件路径: {cache_path}')
file_exists = os.path.exists(cache_path)
print(f'缓存文件是否存在: {file_exists}')
if file_exists:
    print(f'缓存文件大小: {os.path.getsize(cache_path)} bytes')

# 从缓存读取
try:
    loaded_data = load_interface_cached_data('pro_bar', **params)
    print(f'读取数据条数: {len(loaded_data)}')
    data_matches = test_data.equals(loaded_data)
    print(f'数据是否一致: {data_matches}')

    if not data_matches:
        print('原始数据:')
        print(test_data)
        print('加载数据:')
        print(loaded_data)

    # 清理测试文件
    os.remove(cache_path)
    print('已清理测试缓存文件')

except Exception as e:
    print(f'读取缓存失败: {e}')

if not save_result:
    print('ERROR: 数据存储失败')
if not file_exists:
    print('ERROR: 缓存文件未创建')
```

### 2.5 测试5: 重复请求缓存命中
**文件**: `test_case_5_duplicate_requests.py`

**目的**: 验证重复请求是否正确使用缓存

**执行命令**:
```bash
cd /home/quan/testdata/aspipe_v4
python -c "
import sys
import time
sys.path.append('/home/quan/testdata/aspipe_v4')
from app.data_storage import (
    is_interface_data_cached,
    load_interface_cached_data
)

params = {
    'ts_code': '000001.SZ',
    'start_date': '20230101',
    'end_date': '20230105',
    'adj': 'qfq'
}

# 首先创建测试数据并缓存
import pandas as pd
test_data = pd.DataFrame({
    'ts_code': ['000001.SZ'] * 5,
    'trade_date': ['20230101', '20230102', '20230103', '20230104', '20230105'],
    'close': [10.0, 10.1, 10.2, 10.3, 10.4]
})

from app.data_storage import save_interface_data_to_cache
save_interface_data_to_cache(test_data, 'pro_bar', **params)

# 检查缓存状态
is_cached = is_interface_data_cached('pro_bar', cache_ttl_hours=24, **params)
print(f'数据是否已缓存: {is_cached}')

if is_cached:
    # 第一次缓存读取
    print('第一次缓存读取...')
    start_time = time.time()
    first_result = load_interface_cached_data('pro_bar', **params)
    first_duration = time.time() - start_time
    print(f'第一次读取耗时: {first_duration:.4f}秒')
    print(f'第一次读取数据条数: {len(first_result)}')

    # 第二次缓存读取
    time.sleep(0.1)
    print('第二次缓存读取...')
    start_time = time.time()
    second_result = load_interface_cached_data('pro_bar', **params)
    second_duration = time.time() - start_time
    print(f'第二次读取耗时: {second_duration:.4f}秒')
    print(f'第二次读取数据条数: {len(second_result)}')

    # 验证一致性
    results_match = first_result.equals(second_result)
    print(f'两次读取结果是否相同: {results_match}')
    print(f'第二次是否更快: {second_duration < first_duration}')

    if not results_match:
        print('ERROR: 两次读取结果不一致')
else:
    print('ERROR: 数据未正确缓存')
```

### 2.6 测试6: 智能缓存提取
**文件**: `test_case_6_smart_extraction.py`

**目的**: 验证从全量数据中提取特定股票数据的功能

**执行命令**:
```bash
cd /home/quan/testdata/aspipe_v4
python -c "
import sys
import os
import pandas as pd
sys.path.append('/home/quan/testdata/aspipe_v4')
from app.data_storage import (
    save_interface_data_to_cache,
    load_interface_cached_data,
    get_interface_cache_path
)

# 创建包含多个股票的全量数据
full_data = pd.DataFrame({
    'ts_code': ['000001.SZ', '000002.SZ', '600000.SH', '000001.SZ', '000002.SZ'],
    'trade_date': ['20230101', '20230101', '20230101', '20230102', '20230102'],
    'close': [10.0, 20.0, 30.0, 10.1, 20.1]
})

# 保存为全量数据（不含ts_code参数）
save_interface_data_to_cache(full_data, 'pro_bar', start_date='20230101', end_date='20230102')

# 尝试提取特定股票数据
print('尝试提取特定股票数据...')
specific_data = load_interface_cached_data(
    'pro_bar',
    ts_code='000001.SZ',
    start_date='20230101',
    end_date='20230102'
)

print(f'提取到的数据条数: {len(specific_data)}')
print(f'提取到的股票代码: {specific_data[\"ts_code\"].unique() if len(specific_data) > 0 else \"无\"}')
print('提取到的数据:')
if len(specific_data) > 0:
    print(specific_data[['ts_code', 'trade_date', 'close']])

    # 验证是否只包含指定股票
    only_target_stock = all(code == '000001.SZ' for code in specific_data['ts_code'])
    print(f'是否只包含目标股票: {only_target_stock}')

    if not only_target_stock:
        print('ERROR: 提取的数据包含非目标股票')
else:
    print('WARNING: 未提取到数据')

# 清理测试文件
try:
    # 清理全量数据缓存
    full_cache_path = get_interface_cache_path('pro_bar', start_date='20230101', end_date='20230102')
    if os.path.exists(full_cache_path):
        os.remove(full_cache_path)
        print('已清理全量数据缓存')

    # 清理特定股票缓存
    specific_cache_path = get_interface_cache_path('pro_bar', ts_code='000001.SZ', start_date='20230101', end_date='20230102')
    if os.path.exists(specific_cache_path):
        os.remove(specific_cache_path)
        print('已清理特定股票缓存')

except Exception as e:
    print(f'清理缓存文件失败: {e}')
```

## 3. 测试执行顺序建议

1. **首先执行测试1** (配置验证) - 确保基础配置正确
2. **然后执行测试2和3** (缓存键生成和参数标准化) - 验证基础功能
3. **接着执行测试4** (缓存存储和读取) - 验证核心缓存机制
4. **再执行测试5** (重复请求) - 验证实际使用场景
5. **最后执行测试6** (智能提取) - 验证高级功能

## 4. 问题诊断指南

### 4.1 如果测试1失败
- 检查`app/enhanced_download_config.py`中pro_bar接口配置
- 确认requires_tscode设置为True
- 验证缓存相关配置正确

### 4.2 如果测试2或3失败
- 检查`app/cache_key_generator.py`中的缓存键生成逻辑
- 验证参数处理和标准化过程
- 确认相同参数生成相同键值

### 4.3 如果测试4失败
- 检查`app/data_storage.py`中的缓存读写函数
- 验证文件路径生成和数据序列化过程
- 确认缓存文件正确创建和读取

### 4.4 如果测试5失败
- 检查缓存命中检测逻辑
- 验证缓存有效性判断
- 确认重复请求确实使用缓存

### 4.5 如果测试6失败
- 检查智能缓存提取逻辑
- 验证全量数据和特定数据的匹配机制
- 确认数据筛选条件正确

## 5. 日志监控要点

执行测试时，注意观察以下日志信息：
- "使用缓存数据" - 表示缓存命中
- "数据已保存到缓存" - 表示缓存存储成功
- "从全量缓存提取数据" - 表示智能提取生效
- 缓存路径信息 - 确认缓存位置正确
- 参数适配日志 - 确认参数处理正确

通过按此指南逐步执行测试，应该能够准确定位pro_bar接口重复下载但未使用缓存的具体原因。