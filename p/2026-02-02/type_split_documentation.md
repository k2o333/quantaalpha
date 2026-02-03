# Stock_HSGT 接口类型分割提取功能完整文档

## 一、项目背景

### 1.1 问题描述
在使用TuShare API的stock_hsgt（沪深港通资金流向）接口时，我们发现了一个限制：该接口单次请求最多只能返回2000条记录。当数据量较大时，会导致数据截断，无法获取完整的数据。

### 1.2 接口特点
stock_hsgt接口有以下几种类型：
- HK_SZ：港股通(深)
- SZ_HK：深股通  
- HK_SH：港股通(沪)
- SH_HK：沪股通

每种类型代表不同的资金流向通道，数据量可能都很大。

### 1.3 需求分析
为了克服2000条记录的限制，我们需要实现一种按类型分割提取数据的机制，即分别对每种类型进行数据提取，避免因总量过大导致的截断问题。

## 二、解决方案设计

### 2.1 设计思路
采用分页模式扩展的方式，在现有的分页框架基础上新增"type_split"模式，专门用于处理此类需要按类型分别提取的接口。

### 2.2 核心组件
1. **参数生成器** - 生成不同类型的请求参数
2. **分页执行器** - 执行按类型分割的分页逻辑
3. **接口配置** - 配置接口支持的类型列表

## 三、技术实现

### 3.1 参数生成器增强
在 [core/pagination.py](file:///home/quan/testdata/aspipe_v4/app4/core/pagination.py) 文件中添加新的参数生成方法：

```python
def generate_type_split_params(
    self,
    base_params: Dict[str, Any]
) -> Iterator[Tuple[Dict[str, Any], str]]:
    """
    生成按类型分割的分页参数（适用于stock_hsgt等接口）

    Args:
        base_params: 基础参数

    Yields:
        (类型参数, type_value) 元组
    """
    # 获取接口配置中的类型值
    type_values = self.context.interface_config.get('type_values', ['HK_SZ', 'SZ_HK', 'HK_SH', 'SH_HK'])
    logger.info(f"Generating type split parameters for types: {type_values}")

    for type_val in type_values:
        type_params = base_params.copy()
        # 添加或替换type参数
        type_params['type'] = type_val

        yield type_params, type_val
```

### 3.2 分页执行器增强
在 [core/pagination_executor.py](file:///home/quan/testdata/aspipe_v4/app4/core/pagination_executor.py) 文件中添加新的分页执行方法：

```python
def execute_type_split_pagination(
    self,
    interface_config: Dict[str, Any],
    params: Dict[str, Any],
    context: PaginationContext,
    make_request_callback: Callable
) -> List[Dict[str, Any]]:
    """
    执行按类型分割的分页模式（适用于stock_hsgt等接口）
    
    特性：
    1. 按接口支持的不同类型分别请求
    2. 适用于有type参数且单次请求有2000条记录限制的接口
    3. 避免因数据量超限导致的截断问题
    
    Args:
        interface_config: 接口配置
        params: 请求参数
        context: 分页上下文
        make_request_callback: 请求回调函数

    Returns:
        合并后的数据列表
    """
    import logging
    logger = logging.getLogger(__name__)

    interface_name = interface_config['name']
    logger.info(f"Starting type split pagination for {interface_name}")

    # 获取接口配置中定义的类型选项
    type_values = interface_config.get('type_values', ['HK_SZ', 'SZ_HK', 'HK_SH', 'SH_HK'])  # 默认为stock_hsgt的类型
    logger.info(f"Type values to iterate: {type_values}")

    all_data = []
    successful_requests = 0

    for type_val in type_values:
        logger.info(f"Processing type: {type_val}")

        # 创建带有特定type值的参数
        type_params = params.copy()
        type_params['type'] = type_val

        # 从参数配置中移除type，因为它现在是固定的
        if 'type' in interface_config.get('parameters', {}) and interface_config['parameters']['type'].get('required', False):
            type_params['type'] = type_val

        # 发起请求
        logger.info(f"Making request for {interface_name} with type={type_val}")
        type_data = make_request_callback(interface_config, type_params)

        if type_data:
            all_data.extend(type_data)
            successful_requests += 1
            logger.info(f"Got {len(type_data)} records for type {type_val}")
        else:
            logger.info(f"No data for type {type_val}")

    logger.info(f"Type split pagination completed. Total records: {len(all_data)}, Successful requests: {successful_requests}")
    return all_data
```

### 3.3 分发逻辑更新
在PaginationExecutor的分发方法中添加新的分发逻辑：

```python
elif mode == 'type_split':
    # 新增：按类型分割分页（适用于stock_hsgt等接口）
    return self.pagination_executor.execute_type_split_pagination(
        interface_config, params, context, self._make_request
    )
```

### 3.4 接口配置更新
修改 [config/interfaces/stock_hsgt.yaml](file:///home/quan/testdata/aspipe_v4/app4/config/interfaces/stock_hsgt.yaml) 文件：

```yaml
api_name: stock_hsgt
derived_fields:
  trade_date_dt:
    description: 日期类型的trade_date
    format: '%Y%m%d'
    source: trade_date
    type: date
description: 沪深港通股票列表
name: stock_hsgt
output:
  primary_key:
  - ts_code
  - trade_date
  - type
  sort_by:
  - trade_date
  - ts_code
pagination:
  enabled: true
  mode: type_split  # 使用新的分页模式
type_values: ['HK_SZ', 'SZ_HK', 'HK_SH', 'SH_HK']  # 定义可用的类型值
parameters:
  end_date:
    description: 结束时间
    required: false
    type: string
  start_date:
    description: 开始时间
    required: false
    type: string
  trade_date:
    description: 交易日期（格式：YYYYMMDD）
    required: false
    type: string
  ts_code:
    description: 股票代码
    required: false
    type: string
  type:
    description: 类型（HK_SZ深股通, SZ_HK港股通(深), HK_SH沪股通, SH_HK港股通(沪)）
    required: true
    type: string
permissions:
  min_points: 3000
  query_limit: 2000
  rate_limit: 120
request:
  extra_path: ''
  method: POST
  timeout: 30
```

## 四、实现步骤

### 4.1 第一步：修改参数生成模块
在 [core/pagination.py](file:///home/quan/testdata/aspipe_v4/app4/core/pagination.py) 文件中添加类型分割参数生成方法。

### 4.2 第二步：修改分页执行模块
在 [core/pagination_executor.py](file:///home/quan/testdata/aspipe_v4/app4/core/pagination_executor.py) 文件中添加类型分割分页执行方法和分发逻辑。

### 4.3 第三步：更新接口配置
修改 [config/interfaces/stock_hsgt.yaml](file:///home/quan/testdata/aspipe_v4/app4/config/interfaces/stock_hsgt.yaml) 配置文件，设置分页模式为type_split。

### 4.4 第四步：测试验证
运行测试程序，验证类型分割分页功能是否正常工作。

## 五、功能特点

### 5.1 优势
- 解决了单次请求2000条记录的限制问题
- 保持了原有的接口调用方式不变
- 可扩展到其他需要按类型分割的接口
- 提供了清晰的日志记录

### 5.2 性能考虑
- 按类型分割可能会增加API调用次数
- 需要合理设置请求频率，避免超出API限制
- 建议在非高峰时段执行大批量数据提取

## 六、维护和扩展

### 6.1 日常维护
- 监控API调用频率，确保不超过限制
- 检查数据完整性，确保所有类型的数据都被正确提取
- 定期审查日志，查找潜在问题

### 6.2 扩展应用
此类型分割分页模式不仅适用于stock_hsgt接口，还可以扩展到其他具有相似特性的接口：
- 具有类型参数的接口
- 单次请求有记录数限制的接口
- 需要按不同维度分别提取数据的接口

### 6.3 故障排除
常见问题及解决方法：
1. 数据缺失：检查type_values配置是否正确
2. API限制：调整请求频率或添加延迟
3. 性能问题：优化参数配置或添加缓存机制

## 七、总结

通过实现类型分割分页功能，我们成功解决了stock_hsgt接口因单次请求限制导致的数据截断问题。该方案不仅解决了当前问题，还为类似需求提供了可复用的解决方案，提高了系统的灵活性和扩展性。