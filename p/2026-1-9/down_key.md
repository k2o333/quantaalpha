## 实现基于接口配置主键的记录级别重复检测

### 需求分析
当前系统的重复检测机制主要基于范围（日期范围、报告期、股票代码），而不是记录级别的主键。用户希望系统能够在下载时，根据已有数据的主键决定是否跳过每一条记录，实现更精确的重复数据检测。

### 现有系统支持
1. **接口配置已定义primary_key**：每个接口的yaml文件中已配置`output.primary_key`（如`pro_bar`接口的`ts_code`和`trade_date`）
2. **StorageManager已支持基于主键操作**：`read_interface_data`方法已实现基于主键的去重
3. **CoverageManager已实现范围级别检测**：现有机制可扩展支持主键级别检测

### 实现方案

#### 核心设计原则
**完全基于接口yaml配置的primary_key**：系统会自动读取每个接口yaml文件中定义的`output.primary_key`，作为该接口的主键，用于记录级别的重复检测。

#### 1. 扩展`CoverageManager`，添加主键级别的重复检测

##### 1.1 实现`_check_primary_key_existence`方法
- **读取接口配置主键**：从接口yaml的`output.primary_key`获取主键定义
- **批量读取已有主键**：使用`StorageManager.read_interface_data`只读取主键列，减少IO开销
- **高效检测**：将已有主键转换为集合，实现O(1)时间复杂度的存在性检查

##### 1.2 扩展`should_skip`方法
- 添加`primary_key`策略支持
- 根据接口配置自动选择合适的检测策略

#### 2. 优化数据下载与处理流程

##### 2.1 在`download_single_stock`方法中添加主键过滤
- **下载前检测**：获取已有数据的主键集合
- **下载后过滤**：对下载的数据，过滤掉已存在主键的记录
- **只保留新记录**：确保只有新数据被保存

##### 2.2 实现步骤

1. **修改`CoverageManager`类**
   - 添加`_check_primary_key_existence`方法，支持按接口配置的primary_key检查记录是否存在
   - 扩展`should_skip`方法，添加`primary_key`策略支持
   - 实现主键集合的缓存机制，提高检测性能

2. **优化`GenericDownloader.download_single_stock`方法**
   - 在下载数据后，检查每条记录的主键是否已存在
   - 过滤掉已存在的记录，只保留新记录
   - 利用接口配置的primary_key进行检测

3. **配置支持**
   - 系统会自动读取每个接口yaml中的`output.primary_key`配置
   - 支持多主键（如`ts_code`和`trade_date`组合）
   - 对于没有配置primary_key的接口，默认使用范围检测策略

#### 3. 关键技术实现

##### 3.1 主键读取优化
```python
# 只读取接口配置的primary_key列
df = self.storage_manager.read_interface_data(
    interface_name,
    start_date=start_date,
    end_date=end_date,
    columns=primary_keys  # 从接口yaml读取的primary_key配置
)
```

##### 3.2 高效主键检测
```python
# 将已有主键转换为集合，实现O(1)检测
existing_primary_keys = set(
    tuple(row[pk] for pk in primary_keys) 
    for row in df.to_dicts()
)

# 过滤新数据，只保留不存在的记录
new_records = [
    record for record in downloaded_data 
    if tuple(record[pk] for pk in primary_keys) not in existing_primary_keys
]
```

##### 3.3 缓存机制
- 为每个接口和时间范围创建主键集合缓存
- 实现缓存的自动更新和失效机制
- 支持多线程安全访问

### 预期效果

1. **精确检测**：系统会根据每个接口yaml配置的primary_key，精确检测每条记录是否已存在
2. **自动适配**：不同接口可以有不同的primary_key配置，系统自动适配
3. **高效处理**：采用集合检测和缓存机制，确保检测性能
4. **减少开销**：只下载新记录，避免重复API调用和存储开销
5. **配置灵活**：支持多主键配置，适应不同接口的需求

### 文件修改清单

1. **`/home/quan/testdata/aspipe_v4/app4/core/coverage_manager.py`**
   - 扩展覆盖率管理器，添加基于接口配置主键的记录检测
   - 实现`_check_primary_key_existence`方法
   - 扩展`should_skip`方法，添加`primary_key`策略

2. **`/home/quan/testdata/aspipe_v4/app4/core/downloader.py`**
   - 优化`download_single_stock`方法，添加基于主键的记录过滤
   - 实现主键集合的缓存机制

3. **接口配置文件**（如`pro_bar.yaml`等）
   - 确保每个接口都正确配置了`output.primary_key`
   - 支持多主键配置

### 实现风险评估与缓解

1. **性能影响**：大量数据的主键检测可能影响性能
   - 缓解方案：只读取主键列，使用集合检测，添加缓存机制

2. **内存消耗**：存储大量主键可能导致内存占用过高
   - 缓解方案：采用分批处理，实现缓存自动过期机制

3. **并发安全**：多线程环境下可能出现检测不准确
   - 缓解方案：使用线程安全的缓存，实现原子检测操作

### 测试计划

1. **单元测试**：测试`_check_primary_key_existence`方法，验证不同接口配置下的检测准确性
2. **集成测试**：测试完整下载流程，验证基于主键的过滤效果
3. **性能测试**：测试不同数据量下的检测性能
4. **并发测试**：测试多线程环境下的检测准确性

通过以上实现，系统将能够根据每个接口yaml文件配置的primary_key，在下载时精确检测每条记录是否已存在，只下载新记录，提高数据处理效率和准确性。