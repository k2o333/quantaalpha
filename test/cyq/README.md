# Tushare CYQ 数据接口测试

此目录包含用于测试和使用Tushare的CYQ（筹码分布）相关接口的脚本和文档。

## 目录结构

```
test/cyq/
├── README.md                    # 本文档
├── CYQ_INTERFACE_GUIDE.md       # CYQ接口详细使用指南
├── test_cyq_data.py             # 基础测试脚本（使用tushare库）
├── enhanced_test_cyq_data.py    # 增强版测试脚本（含token验证）
├── cyq_usage_example.py         # 使用示例脚本（使用tushare库）
└── http_api_cyq_example.py      # HTTP API使用示例（推荐）
```

## 接口说明

### cyq_chips - 每日筹码分布
- 获取A股每日的筹码分布情况，提供各价位占比
- 数据从2018年开始提供
- 每天18~19点更新

### cyq_perf - 每日筹码及胜率
- 获取A股每日筹码分布及胜率情况
- 数据从2018年开始提供
- 每天18~19点更新

## 使用方法

### 1. 环境准备

确保已安装必要的依赖：

```bash
pip install requests pandas python-dotenv
```

### 2. 配置Token

在 `.env` 文件中设置Tushare token：

```bash
TUSHARE_TOKEN=your_actual_tushare_token_here
PROXY_URL=your_proxy_url_if_needed
```

### 3. 运行测试

推荐使用HTTP API方式（绕过了tushare库的限制）：

```bash
cd /home/quan/testdata/aspipe_v4/test/cyq
python http_api_cyq_example.py
```

## 配置文件使用

脚本会自动从项目配置中读取：

- Token: `/home/quan/testdata/aspipe_v4/.env` 文件中的 `TUSHARE_TOKEN`
- 代理URL: 环境变量 `PROXY_URL` (如果需要)
- 配置文件: `/home/quan/testdata/aspipe_v4/app4/config/settings.yaml`

## HTTP API 方式（推荐）

项目实际使用的是HTTP API调用方式，而不是tushare库。这种方式绕过了tushare库的某些限制，可以直接通过HTTP请求访问API。

### HTTP API 参数结构：
```python
{
    'api_name': 'cyq_chips',  # 或 'cyq_perf'
    'token': 'your_token',
    'params': {
        'ts_code': '000001.SZ',
        'start_date': '20230101',
        'end_date': '20230131'
    },
    'fields': ''  # 空字符串表示返回默认字段
}
```

## 注意事项

1. **Token有效性**: 确保您的Tushare账户token有效且有足够积分
2. **接口权限**: cyq_chips和cyq_perf接口需要至少120积分
3. **数据可用性**: 筹码数据从2018年开始提供
4. **网络连接**: 确保网络连接正常，如使用代理请正确配置
5. **推荐方式**: 使用HTTP API方式而非tushare库，这样可以更好地与项目架构保持一致

## 故障排除

- **Token错误**: 检查token是否正确，账户是否有足够积分
- **网络错误**: 检查网络连接和代理设置
- **数据为空**: 检查日期范围和股票代码是否存在相应数据
- **权限错误**: 检查账户权限是否满足接口要求
- **代理错误**: 确认代理服务器地址和端口是否正确