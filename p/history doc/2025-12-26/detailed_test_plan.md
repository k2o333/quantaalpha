# TuShare API pro_bar接口重复下载与缓存问题详细测试计划

## 1. 测试环境准备

### 1.1 环境配置
- 确保项目目录结构完整
- 配置有效的TuShare Token（具有pro_bar接口权限）
- 设置合适的积分等级（建议5000+以确保接口可用）
- 准备测试用的股票代码列表

### 1.2 测试目录结构
```bash
# 测试脚本将放置在专门的测试目录中
/home/quan/testdata/aspipe_v4/test/pro_bar_cache_duplicate_test/

# 该目录将包含所有测试脚本文件
```

### 1.3 日志配置
```bash
# 创建日志目录
mkdir -p /home/quan/testdata/aspipe_v4/log
mkdir -p /home/quan/testdata/aspipe_v4/cache
mkdir -p /home/quan/testdata/aspipe_v4/data

# 设置日志级别为DEBUG以便捕获详细信息
export LOG_LEVEL=DEBUG
```

## 2. 测试用例详细说明

### 测试用例1: pro_bar接口缓存键生成一致性测试

#### 2.1 测试目标
验证相同参数在不同时间调用时是否生成相同的缓存键和路径

#### 2.2 测试步骤
1. 导入必要的模块（从项目目录导入）：
   ```python
   import sys
   sys.path.append('/home/quan/testdata/aspipe_v4')
   from app.cache_key_generator import CacheKeyGenerator
   ```

2. 使用相同参数多次调用缓存键生成函数：
   ```python
   params = {
       'interface_name': 'pro_bar',
       'ts_code': '000001.SZ',
       'start_date': '20230101',
       'end_date': '20231231',
       'adj': 'qfq',
       'freq': 'D'
   }

   # 多次生成缓存路径
   paths = []
   for i in range(5):
       path = CacheKeyGenerator.generate_cache_path(**params)
       paths.append(path)
       print(f"第{i+1}次生成路径: {path}")
   ```

3. 验证所有路径是否一致

#### 2.3 预期结果
- 所有5次调用应生成完全相同的缓存路径
- 路径应符合预期格式（如：data/daily/pro_bar/000001.SZ/2023/20230101-20231231.parquet）

#### 2.4 问题定位
如果路径不一致，说明：
- 缓存键生成算法存在问题
- 参数处理过程中引入了随机因素
- 时间戳或其他动态参数被错误地包含在缓存键中

### 测试用例2: pro_bar接口缓存存储与读取测试

#### 2.1 测试目标
验证pro_bar接口数据能否正确存储到缓存并被读取

#### 2.2 测试步骤
1. 导入必要模块（从项目目录导入）：
   ```python
   import sys
   sys.path.append('/home/quan/testdata/aspipe_v4')
   from app.data_storage import (
       save_interface_data_to_cache,
       load_interface_cached_data,
       get_interface_cache_path
   )
   import pandas as pd
   ```

2. 创建测试数据：
   ```python
   test_data = pd.DataFrame({
       'ts_code': ['000001.SZ'] * 5,
       'trade_date': ['20230101', '20230102', '20230103', '20230104', '20230105'],
       'open': [10.0, 10.1, 10.2, 10.3, 10.4],
       'high': [10.5, 10.6, 10.7, 10.8, 10.9],
       'low': [9.9, 10.0, 10.1, 10.2, 10.3],
       'close': [10.4, 10.5, 10.6, 10.7, 10.8],
       'vol': [1000000, 1100000, 1200000, 1300000, 1400000]
   })
   ```

3. 保存数据到缓存：
   ```python
   params = {
       'ts_code': '000001.SZ',
       'start_date': '20230101',
       'end_date': '20231231',
       'adj': 'qfq',
       'freq': 'D'
   }

   save_result = save_interface_data_to_cache(test_data, 'pro_bar', **params)
   print(f"保存结果: {save_result}")
   ```

4. 验证缓存文件存在：
   ```python
   cache_path = get_interface_cache_path('pro_bar', **params)
   print(f"缓存路径: {cache_path}")
   import os
   print(f"文件是否存在: {os.path.exists(cache_path)}")
   ```

5. 从缓存读取数据：
   ```python
   loaded_data = load_interface_cached_data('pro_bar', **params)
   print(f"读取数据条数: {len(loaded_data)}")
   print(f"数据是否一致: {test_data.equals(loaded_data)}")
   ```

#### 2.3 预期结果
- 数据保存成功（返回True）
- 缓存文件正确创建在指定路径
- 读取的数据与原始数据完全一致

#### 2.4 问题定位
如果保存失败或读取数据不一致，说明：
- 缓存存储机制存在问题
- 数据序列化/反序列化过程有错误
- 缓存路径计算不正确

### 测试用例3: pro_bar接口重复请求缓存命中测试

#### 3.1 测试目标
验证重复调用相同参数的pro_bar接口是否会正确使用缓存

#### 3.2 测试步骤
1. 导入必要模块（从项目目录导入）：
   ```python
   import sys
   sys.path.append('/home/quan/testdata/aspipe_v4')
   from app.download_strategies import DailyDataStrategy
   from app.tushare_api import TuShareDownloader
   import time
   ```

2. 创建下载策略实例：
   ```python
   downloader = TuShareDownloader()
   strategy = DailyDataStrategy('pro_bar', downloader)
   ```

3. 第一次调用（应触发实际下载）：
   ```python
   start_time = time.time()
   first_result = strategy.download_with_cache(
       ts_code='000001.SZ',
       start_date='20230101',
       end_date='20230110',
       adj='qfq',
       freq='D'
   )
   first_duration = time.time() - start_time
   print(f"首次调用耗时: {first_duration:.2f}秒")
   print(f"首次调用数据条数: {len(first_result)}")
   ```

4. 立即第二次调用（应使用缓存）：
   ```python
   time.sleep(1)  # 短暂间隔
   start_time = time.time()
   second_result = strategy.download_with_cache(
       ts_code='000001.SZ',
       start_date='20230101',
       end_date='20230110',
       adj='qfq',
       freq='D'
   )
   second_duration = time.time() - start_time
   print(f"第二次调用耗时: {second_duration:.2f}秒")
   print(f"第二次调用数据条数: {len(second_result)}")
   ```

5. 对比结果：
   ```python
   print(f"两次调用数据是否相同: {first_result.equals(second_result)}")
   print(f"第二次是否显著更快: {second_duration < first_duration * 0.5}")
   ```

#### 3.3 预期结果
- 第一次调用耗时较长（实际下载）
- 第二次调用显著更快（使用缓存）
- 两次返回的数据完全相同

#### 3.4 问题定位
如果第二次调用仍然很慢或者数据不一致，说明：
- 缓存命中检查机制失效
- 缓存有效性验证有问题
- 缓存读取过程存在错误

### 测试用例4: pro_bar接口ts_code参数标准化测试

#### 4.1 测试目标
验证不同格式的ts_code参数是否能正确处理并生成相同的缓存键

#### 4.2 测试步骤
1. 导入必要模块（从项目目录导入）：
   ```python
   import sys
   sys.path.append('/home/quan/testdata/aspipe_v4')
   from app.cache_key_generator import CacheKeyGenerator
   from app.parameter_adapters import ParameterAdapterManager
   ```

2. 测试不同格式的ts_code：
   ```python
   base_params = {
       'start_date': '20230101',
       'end_date': '20231231',
       'adj': 'qfq',
       'freq': 'D'
   }

   ts_code_variants = [
       '000001.SZ',  # 标准格式
       '000001.sz',  # 小写后缀
       '000001.Sh',  # 错误大小写
   ]

   cache_paths = []
   for ts_code in ts_code_variants:
       params = {**base_params, 'ts_code': ts_code}
       path = CacheKeyGenerator.generate_cache_path('pro_bar', **params)
       cache_paths.append(path)
       print(f"ts_code '{ts_code}' 生成路径: {path}")
   ```

3. 测试参数适配器：
   ```python
   adapter = ParameterAdapterManager()
   for ts_code in ts_code_variants:
       params = {**base_params, 'ts_code': ts_code}
       adapted_params = adapter.adapt_parameters('pro_bar', params)
       print(f"原始ts_code: {ts_code}, 适配后: {adapted_params.get('ts_code')}")
   ```

#### 4.3 预期结果
- 所有标准格式的ts_code应生成相同的缓存路径
- 参数适配器应将非标准格式转换为标准格式

#### 4.4 问题定位
如果不同格式生成不同路径，说明：
- ts_code标准化处理不完善
- 参数适配器未正确处理ts_code格式
- 缓存键生成未考虑参数标准化

### 测试用例5: pro_bar接口智能缓存提取测试

#### 5.1 测试目标
验证从包含多个股票的全量数据中提取特定股票数据的功能

#### 5.2 测试步骤
1. 创建包含多个股票的全量数据（从项目目录导入）：
   ```python
   import sys
   sys.path.append('/home/quan/testdata/aspipe_v4')
   import pandas as pd
   from app.data_storage import save_interface_data_to_cache

   # 创建全量数据（不包含ts_code参数）
   full_data = pd.DataFrame({
       'ts_code': ['000001.SZ', '000002.SZ', '600000.SH'] * 3,
       'trade_date': ['20230101', '20230101', '20230101'] * 3,
       'close': [10.0, 20.0, 30.0] * 3
   })

   # 保存为全量数据（不含ts_code）
   save_interface_data_to_cache(full_data, 'pro_bar', start_date='20230101', end_date='20231231')
   ```

2. 尝试提取特定股票数据：
   ```python
   from app.data_storage import load_interface_cached_data

   # 尝试加载特定股票数据
   specific_data = load_interface_cached_data(
       'pro_bar',
       ts_code='000001.SZ',
       start_date='20230101',
       end_date='20231231'
   )

   print(f"提取到的数据条数: {len(specific_data)}")
   if len(specific_data) > 0:
       print(f"提取到的股票代码: {specific_data['ts_code'].unique()}")
   ```

#### 5.3 预期结果
- 能够从全量数据中正确提取特定股票的数据
- 提取的数据只包含指定股票的信息

#### 5.4 问题定位
如果无法提取或提取错误，说明：
- 智能缓存提取逻辑有缺陷
- 全量数据和特定数据的缓存键匹配机制不正确

### 测试用例6: pro_bar接口在tscode_historical模式下的行为测试

#### 6.1 测试目标
验证在全历史下载模式下pro_bar接口的缓存和下载行为

#### 6.2 测试步骤
1. 检查接口配置（从项目目录导入）：
   ```python
   import sys
   sys.path.append('/home/quan/testdata/aspipe_v4')
   from app.enhanced_download_config import DOWNLOAD_PIPELINE_CONFIG

   pro_bar_config = DOWNLOAD_PIPELINE_CONFIG.get('pro_bar')
   print(f"pro_bar接口配置:")
   print(f"  requires_tscode: {getattr(pro_bar_config, 'requires_tscode', False)}")
   print(f"  cache_enabled: {getattr(pro_bar_config, 'cache_enabled', True)}")
   print(f"  cache_ttl_hours: {getattr(pro_bar_config, 'cache_ttl_hours', 24)}")
   ```

2. 模拟tscode_historical模式调用：
   ```python
   from app.download_scheduler import DownloadScheduler

   scheduler = DownloadScheduler('20230101', '20231231')
   # 检查是否正确识别pro_bar为需要ts_code的接口
   is_tscode_interface = scheduler._is_tscode_interface('pro_bar')
   print(f"pro_bar是否为ts_code接口: {is_tscode_interface}")
   ```

#### 6.3 预期结果
- pro_bar接口应正确标记为requires_tscode=True
- 在tscode_historical模式下应正确调度

#### 6.4 问题定位
如果配置不正确，说明：
- 接口配置文件设置错误
- 配置适配器未能正确读取配置

## 3. 测试执行指南

### 3.1 执行顺序建议
1. 先执行测试用例6（配置验证）
2. 再执行测试用例1和4（缓存键生成）
3. 然后执行测试用例2（缓存读写）
4. 接着执行测试用例3（重复请求）
5. 最后执行测试用例5（智能提取）

### 3.2 观察要点
- 查看日志输出中的缓存相关信息
- 监控网络请求次数（避免真实API调用过多）
- 检查缓存文件的创建和更新时间
- 验证数据一致性

### 3.3 故障排查
如果发现问题，应：
1. 检查相关模块的日志输出
2. 验证涉及的配置文件
3. 检查缓存目录中的文件状态
4. 分析具体失败的测试用例

## 4. 测试结果分析与结论

### 4.1 测试结果判定标准
每个测试用例的成功标准如下：

#### 测试用例1 - 缓存键生成一致性
- **通过**: 5次调用生成完全相同的缓存路径
- **失败**: 任意两次调用生成不同路径

#### 测试用例2 - 缓存存储与读取
- **通过**:
  - 数据保存返回True
  - 缓存文件存在且大小>0
  - 读取数据与原始数据完全一致
- **失败**: 任一条件不满足

#### 测试用例3 - 重复请求缓存命中
- **通过**:
  - 第二次调用耗时明显小于第一次（至少快50%）
  - 两次返回数据完全相同
- **失败**: 任一条件不满足

#### 测试用例4 - ts_code参数标准化
- **通过**: 不同格式的ts_code生成相同缓存路径
- **失败**: 不同格式生成不同路径

#### 测试用例5 - 智能缓存提取
- **通过**:
  - 能从全量数据中提取特定股票数据
  - 提取的数据只包含指定股票
  - 提取数据条数>0
- **失败**: 任一条件不满足

#### 测试用例6 - tscode_historical模式行为
- **通过**:
  - pro_bar接口配置requires_tscode=True
  - 调度器正确识别为ts_code接口
- **失败**: 任一条件不满足

### 4.2 测试结果综合分析

#### 全部通过
如果所有测试用例都通过，说明：
- 缓存系统基本功能正常
- 需要进一步检查实际使用场景中的问题
- 可能是并发访问或特殊情况下的问题

#### 部分失败的分析结论

##### 如果测试用例1和4失败
表明存在**缓存键生成问题**：
- 参数标准化处理不一致
- 缓存键生成算法有问题
- 需要修复`cache_key_generator.py`中的逻辑

##### 如果测试用例2失败
表明存在**缓存存储/读取问题**：
- 数据序列化/反序列化出错
- 缓存文件路径计算错误
- 文件权限或磁盘空间问题
- 需要检查`data_storage.py`中的实现

##### 如果测试用例3失败但测试用例2通过
表明存在**缓存命中检查问题**：
- 缓存有效性判断逻辑有误
- 缓存TTL设置过短
- 缓存命中检测机制失效
- 需要检查缓存有效性验证逻辑

##### 如果测试用例5失败
表明存在**智能缓存提取问题**：
- 全量数据与特定数据路径匹配失败
- 数据筛选逻辑有误
- 需要修复智能提取功能

##### 如果测试用例6失败
表明存在**接口配置问题**：
- pro_bar接口配置不正确
- requires_tscode设置错误
- 需要检查`enhanced_download_config.py`配置

### 4.3 问题定位优先级

1. **最高优先级**: 测试用例6（配置验证）- 影响所有其他功能
2. **高优先级**: 测试用例1和4（缓存键生成和参数标准化）- 核心功能问题
3. **中优先级**: 测试用例2和3（缓存读写和命中）- 功能实现问题
4. **低优先级**: 测试用例5（智能提取）- 高级功能问题

### 4.4 建议的修复措施

根据测试结果采取相应措施：

#### 缓存键生成问题
- 统一参数处理和标准化逻辑
- 确保相同参数始终生成相同键值
- 移除缓存键生成中的随机因素

#### 缓存存储/读取问题
- 检查数据序列化过程
- 验证缓存路径计算逻辑
- 确保文件读写权限正确

#### 缓存命中问题
- 调整缓存TTL设置
- 优化缓存有效性判断逻辑
- 改进缓存命中检测机制

#### 智能提取问题
- 修复全量数据与特定数据匹配逻辑
- 完善数据筛选条件
- 优化提取算法性能

## 5. 预期问题解决方案

### 5.1 缓存键不一致
- 修改`cache_key_generator.py`中的键生成逻辑
- 确保参数排序和标准化处理一致

### 5.2 参数处理问题
- 完善`parameter_adapters.py`中的ts_code标准化
- 统一参数处理流程

### 5.3 缓存命中失败
- 检查`data_storage.py`中的缓存有效性验证
- 优化缓存命中检查逻辑

### 5.4 智能提取失效
- 修复`data_storage.py`中的全量数据提取逻辑
- 确保数据筛选条件正确

通过执行以上测试计划，应该能够准确定位pro_bar接口重复下载但未使用缓存的具体原因。