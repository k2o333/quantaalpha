# 实施方案：添加缺失接口（简化版）

## 项目目标

1. 将 `/home/quan/testdata/aspipe_v4/p/tudown.md` 中提到但代码中缺失的16个接口添加到系统中
2. 复用现有失败处理机制，保持一致性

## 第一部分：缺失接口添加方案

### 缺失的16个接口清单

#### 基础信息类 (2个)
1. `stock_st` - ST股票列表
2. `bak_basic` - 备用基础数据

#### 资金流向类 (6个)
3. `moneyflow_dc` - 个股资金流向（东财）
4. `moneyflow_ths` - 个股资金流向（同花顺）
5. `moneyflow_ind_dc` - 行业/概念资金流向（东财）
6. `moneyflow_mkt_dc` - 大盘资金流向（东财）
7. `moneyflow_cnt_ths` - 概念板块资金流向（同花顺）
8. `moneyflow_ind_ths` - 行业板块资金流向（同花顺）

#### 股东数据类 (1个)
9. `top10_floatholders` - 前十大流通股东

#### 技术分析与研究类 (7个)
10. `stk_factor` - 股票技术因子
11. `stk_factor_pro` - 股票技术面因子(专业版)
12. `cyq_perf` - 每日筹码及胜率
13. `cyq_chips` - 每日筹码分布
14. `report_rc` - 卖方盈利预测数据
15. `stk_surv` - 机构调研表
16. `broker_recommend` - 券商每月荐股

### 实现步骤

#### 步骤1：在 `tushare_api.py` 中添加接口方法

为每个缺失接口创建对应的下载方法，遵循现有模式。例如：

```python
def download_stock_st(self, trade_date: str = '20231201') -> pd.DataFrame:
    """
    下载ST股票列表
    权限要求：3000积分起
    """
    if TUSHARE_POINTS < 3000:
        self.logger.warning("stock_st requires 3000+ points, skipping download")
        return pd.DataFrame()

    try:
        result = self.download_with_retry(
            self.pro.stock_st,
            trade_date=trade_date
        )
        self.logger.info(f"Successfully downloaded stock_st: {len(result)} records")
        return result
    except Exception as e:
        self.logger.error(f"Failed to download stock_st: {e}")
        ErrorHandler.handle_api_error(e, "download_stock_st")
        raise

def download_bak_basic(self) -> pd.DataFrame:
    """
    下载备用基础数据
    权限要求：5000积分起
    """
    if TUSHARE_POINTS < 5000:
        self.logger.warning("bak_basic requires 5000+ points, skipping download")
        return pd.DataFrame()

    try:
        result = self.download_with_retry(
            self.pro.bak_basic
        )
        self.logger.info(f"Successfully downloaded bak_basic: {len(result)} records")
        return result
    except Exception as e:
        self.logger.error(f"Failed to download bak_basic: {e}")
        ErrorHandler.handle_api_error(e, "download_bak_basic")
        raise
```

#### 步骤2：在 `date_range_downloader.py` 中添加任务调度

在 `_create_download_task_list()` 方法中添加新的任务类型，将这些接口集成到现有的下载流程中：

```python
# 在适当分类中添加新的接口
static_types = ['stock_basic', 'trade_cal', 'new_share', 'stock_company', 'stock_st', 'bak_basic', 'namechange']
# top10_floatholders 可以按其他股东数据分类
other_types = ['stk_rewards', 'stk_managers', 'namechange', 'top10_floatholders', 'broker_recommend']
# 资金流向类接口
fund_types = ['moneyflow', 'moneyflow_dc', 'moneyflow_ths', 'moneyflow_ind_dc', 'moneyflow_mkt_dc', 'moneyflow_cnt_ths', 'moneyflow_ind_ths']
# 技术分析类接口
tech_types = ['stk_factor', 'stk_factor_pro', 'cyq_perf', 'cyq_chips', 'report_rc', 'stk_surv']
```

同时添加对应的下载方法，复用现有的 `_download_daily_type_for_range`、`_download_static_type` 等方法的模式。

#### 步骤3：更新 `score_config.py` 中的权限配置

在 `SCORE_REQUIREMENTS` 字典中添加新接口的权限要求：

```python
SCORE_REQUIREMENTS = {
    ...
    3000: {
        'basic': [
            'stock_st',       # ST股票列表
        ],
        'others': [
            'stock_hsgt',     # 沪深港通股票列表
        ]
    },
    5000: {
        'basic': [
            'bak_basic',      # 备用基础数据
        ],
        'daily': [
            'pro_bar',        # 复权行情
            'bak_daily',      # 备用行情
            'stk_factor',     # 股票技术因子
            'stk_factor_pro', # 股票技术面因子(专业版)
        ],
        'market_structure': [
            'cyq_perf',       # 每日筹码及胜率
            'cyq_chips',      # 每日筹码分布
        ],
        'funds': [
            'moneyflow_dc',   # 个股资金流向(东财)
            'moneyflow_ths',  # 个股资金流向(同花顺)
            'moneyflow_ind_dc', # 行业/概念资金流向（东财）
            'moneyflow_mkt_dc', # 大盘资金流向（东财）
            'moneyflow_cnt_ths', # 概念板块资金流向（同花顺）
            'moneyflow_ind_ths', # 行业板块资金流向（同花顺）
        ],
        'holders': [
            'top10_floatholders', # 前十大流通股东
        ],
        'research': [
            'report_rc',      # 卖方盈利预测数据
            'stk_surv',       # 机构调研表
        ],
    },
    8000: {
        'research': [
            'report_rc',      # 卖方盈利预测数据 (正式权限)
        ]
    },
    2000: {
        'others': [
            'broker_recommend', # 券商每月荐股
        ]
    }
}
```

## 第二部分：失败处理机制

复用现有的失败处理机制，无需额外开发：

1. `@retry_on_failure` 装饰器 - 重试机制
2. 令牌切换机制 - 认证失败时自动切换令牌
3. 错误分类处理 - 不同错误类型的不同处理策略
4. 智能任务队列 - 任务失败后的队列管理

所有新增接口都使用 `download_with_retry` 方法和 `ErrorHandler.handle_api_error` 函数，保持一致性。

## 第三部分：实施步骤

### 步骤1：在 `tushare_api.py` 中添加16个接口方法（1天）
- 按照现有代码模式添加所有缺失接口
- 确保权限检查正确
- 复用现有错误处理机制

### 步骤2：更新 `score_config.py` 权限配置（半天）
- 添加新接口的权限要求
- 按接口类型分类

### 步骤3：更新 `date_range_downloader.py` 任务调度（1天）
- 添加任务到相应分类
- 实现对应的下载方法
- 集成到现有的下载流程中

### 步骤4：测试和验证（半天）
- 单独测试各接口功能
- 整体下载流程测试
- 错误处理机制验证

## 第四部分：预期效果

1. 系统将支持tudown.md中提到的所有接口
2. 保持与现有系统的一致性和兼容性
3. 使用相同的错误处理机制，维护代码统一性