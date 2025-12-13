# stk_factor_pro 接口问题诊断与修复方案

## 问题概述

在分析 `stk_factor_pro` 接口使用过程中发现以下问题：

1. **API函数名无法识别** - 日志中显示为 `unknown_api`
2. **random模块未导入** - 代码中使用但未导入 `random` 模块
3. **速率限制异常** - 存在长时间间隔的API请求（96秒间隔）
4. **与官方限制不匹配** - TuShare官方限制为每分钟30次，但代码中配置为100次

## 问题详细分析

### 1. `unknown_api` 问题

在 `/home/quan/testdata/aspipe_v4/app/tushare_api.py:131`:
```python
api_name = api_func.__name__ if hasattr(api_func, '__name__') else 'unknown_api'
```

此问题导致：
- 无法识别调用的API类型
- 使用默认的速率限制参数（每分钟200次）
- 可能影响API统计和优化

### 2. random模块缺失

在 `/home/quan/testdata/aspipe_v4/app/tushare_api.py:300`:
```python
min_interval = (60.0 / calls_per_minute) * random.uniform(0.8, 1.2)
```

此问题导致：
- 代码执行时会抛出 NameError
- 速率限制功能无法正常工作
- 可能触发异常处理机制导致长时间等待

### 3. 速率限制配置错误

**TuShare官方限制**:
- `stk_factor_pro`: 每分钟最多30次（5000积分用户）

**代码中配置** (`score_config.py:177`):
- `stk_factor_pro`: 每分钟100次

此问题导致：
- 实际请求频率超过TuShare限制
- 触发TuShare服务器的限频机制
- 导致长时间等待或API拒绝服务

### 4. 长时间间隔原因

从日志分析：
```
2025-12-13 14:25:56,641 - 成功调用API
2025-12-13 14:27:22,857 - 成功调用API
```
间隔约96秒，这明显超出正常限频等待时间。

可能原因：
- random模块错误导致异常处理
- TuShare服务器因超频请求而强制延时
- 重试机制中的指数退避

## 修复方案

### 1. 修复模块导入问题

在 `/home/quan/testdata/aspipe_v4/app/tushare_api.py` 文件顶部添加：
```python
import random
```

### 2. 修正API速率限制配置

修改 `/home/quan/testdata/aspipe_v4/app/score_config.py:177`:
```python
# 原配置
'stk_factor_pro': {'calls_per_minute': 100},

# 修正为
'stk_factor_pro': {'calls_per_minute': 30},
```

### 3. 改进API函数名识别

在调用TuShare API前，确保传递正确的函数对象。可以在下载函数中显式指定API名称：

修改 `/home/quan/testdata/aspipe_v4/app/tushare_api.py:131`:
```python
# 原代码
api_name = api_func.__name__ if hasattr(api_func, '__name__') else 'unknown_api'

# 建议改进
if hasattr(api_func, '__name__'):
    api_name = api_func.__name__
else:
    # 为TuShare包装函数提供备用名称映射
    # 比如在调用前传入api_name参数
    api_name = kwargs.pop('api_name', 'unknown_api')
```

或者在调用处指定名称：
```python
def download_stk_factor_pro(self, trade_date: str = '20231201') -> pd.DataFrame:
    try:
        result = self.download_with_retry(
            self.pro.stk_factor_pro,
            api_name='stk_factor_pro',  # 添加此参数
            trade_date=trade_date
        )
```

### 4. 添加更完善的错误处理

修改 `download_with_retry` 函数以处理API函数名缺失的情况：

```python
@retry_on_failure(max_retries=3, delay=1.0, backoff=2.0)
def download_with_retry(self, api_func, *args, max_retries: int = 3, api_name=None, **kwargs):
    """
    Download data with retry mechanism and rate limiting
    """
    if api_name is None:
        api_name = api_func.__name__ if hasattr(api_func, '__name__') else 'unknown_api'
```

## 验证步骤

1. 修改 `tushare_api.py` 添加 `import random`
2. 修改 `score_config.py` 中 `stk_factor_pro` 限制为30次/分钟
3. 验证API函数名能否正确识别
4. 进行小规模测试，观察日志中是否仍有 `unknown_api` 和长时间间隔问题

## 额外建议

### 1. 监控API使用情况
- 添加API调用计数和限频状态监控
- 记录实际调用频率是否符合限制

### 2. 优化批量处理
- 考虑使用日期范围参数而非单日循环调用
- 实现更智能的请求调度

### 3. 错误日志改进
- 添加更详细的错误日志以帮助故障排除
- 记录实际的API响应时间和限频情况

## 结论

通过以上修复，`stk_factor_pro` 接口的长时间间隔问题应该得到解决。关键是确保速率限制与TuShare官方限制一致，并修复代码中的模块导入错误。