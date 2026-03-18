# Tushare CYQ 接口使用指南

## 说明

本项目包含用于测试Tushare的cyq_chips（每日筹码分布）和cyq_perf（每日筹码及胜率）接口的脚本。

## 文件结构

- `test_cyq_data.py`: 基础测试脚本
- `enhanced_test_cyq_data.py`: 增强版测试脚本，包含token验证
- `README.md`: 使用说明文档

## 接口详情

### cyq_chips - 每日筹码分布
- **功能**: 获取A股每日的筹码分布情况，提供各价位占比
- **数据起始**: 2018年开始
- **更新时间**: 每天18~19点之间更新当日数据
- **积分要求**: 120积分
- **单次最大**: 2000条

### cyq_perf - 每日筹码及胜率
- **功能**: 获取A股每日筹码分布及胜率情况
- **数据起始**: 2018年开始
- **更新时间**: 每天18~19点之间更新当日数据
- **积分要求**: 120积分
- **单次最大**: 5000条

## 使用方法

### 1. HTTP API 方式（推荐）

项目实际使用的是HTTP API调用方式，而不是tushare库。这种方式与项目架构保持一致。

```python
import requests
import os
import json

# 从环境变量获取token和代理
token = os.getenv('TUSHARE_TOKEN')
proxy_url = os.getenv('PROXY_URL', '')

# 获取API URL
api_url = proxy_url if proxy_url else 'http://api.tushare.pro'
if not api_url.endswith('/api') and not api_url.endswith('/dataapi'):
    if api_url.endswith('/'):
        api_url += 'api'
    else:
        api_url += '/api'

# 获取筹码分布数据
req_params = {
    'api_name': 'cyq_chips',
    'token': token,
    'params': {
        'ts_code': '000001.SZ',
        'start_date': '20230101',
        'end_date': '20230131'
    },
    'fields': ''
}

response = requests.post(api_url, json=req_params)
result = response.json()

# 获取筹码及胜率数据
req_params['api_name'] = 'cyq_perf'
response = requests.post(api_url, json=req_params)
result = response.json()
```

### 2. 使用项目配置

```python
from app4.core.config_loader import ConfigLoader

# 加载项目配置
config_loader = ConfigLoader("/home/quan/testdata/aspipe_v4/app4/config")
config = config_loader.get_global_config()

# 获取token
token = config['tushare']['token']

# 使用HTTP API方式
import requests
api_url = os.getenv('PROXY_URL', 'http://api.tushare.pro/api')
# ... 继续使用上面的HTTP API代码
```

## 参数说明

### 共同参数
- `ts_code`: 股票代码 (可选)
- `trade_date`: 交易日期 (可选，YYYYMMDD)
- `start_date`: 开始日期 (可选，YYYYMMDD)
- `end_date`: 结束日期 (可选，YYYYMMDD)

## 配置信息

- **Token位置**: `/home/quan/testdata/aspipe_v4/.env` 文件中的 `TUSHARE_TOKEN`
- **代理URL**: 环境变量 `PROXY_URL` (如果需要)
- **配置文件**: `/home/quan/testdata/aspipe_v4/app4/config/settings.yaml`

## 注意事项

1. **Token有效性**: 确保Tushare账户的token有效且有足够积分
2. **数据权限**: 部分数据可能需要特定权限才能访问
3. **网络连接**: 确保网络连接正常
4. **代理设置**: 如需使用代理，确保代理服务器正常工作
5. **数据限制**: 单次请求有数量限制，大量数据需要分批获取

## 测试脚本运行

```bash
cd /home/quan/testdata/aspipe_v4/test/cyq
python enhanced_test_cyq_data.py
```

## 错误排查

- **Token错误**: 检查token是否正确，账户是否有足够积分
- **网络错误**: 检查网络连接，代理设置是否正确
- **数据为空**: 检查日期范围和股票代码是否存在相应数据
- **权限错误**: 检查账户权限是否满足接口要求