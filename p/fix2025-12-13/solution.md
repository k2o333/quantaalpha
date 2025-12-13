# 所有API接口调用间隔过长问题解决方案

## 问题描述
根据日志`/home/quan/testdata/aspipe_v4/log/aspipe_v4.log`分析，发现多个API接口（特别是`stk_factor_pro`）两次调用之间存在几分钟的间隔，严重影响数据下载效率。

## 问题分析

### 1. API频率限制
- 不同接口有不同的频率限制，例如：
  - `stk_factor_pro`接口在5000积分时的限制为：**每分钟最多30次调用**
  - `stk_factor`接口在5000积分时的限制为：**每分钟最多100次调用**
  - 其他接口各有不同的限制
- 当前实现没有统一处理这些限制，导致部分接口触发频率限制

### 2. 错误处理导致的延迟
- 当任何API返回频率限制错误时，`ErrorHandler`会额外等待60秒
- 这是导致日志中出现几十秒间隔的主要原因
- 问题不仅限于stk_factor_pro，而是影响所有可能触发频率限制的接口

## 统一解决方案

### 修改tushare_api.py中的_advanced_rate_limit方法

在`/home/quan/testdata/aspipe_v4/app/tushare_api.py`文件中，修改`_advanced_rate_limit`方法，为所有API实现统一的固定间隔控制：

```python
def _advanced_rate_limit(self, api_name: str) -> None:
    """
    统一的速率控制：为所有API实现固定间隔控制
    间隔时间 = 60秒 / 每分钟限制次数
    确保所有API调用都遵循其频率限制，避免触发60秒等待
    """
    # 获取此API的速率限制
    api_config = self.api_limits.get(api_name, {'calls_per_minute': 200})
    calls_per_minute = api_config['calls_per_minute']
    
    # 计算固定间隔时间（秒）
    interval = 60.0 / calls_per_minute
    
    # 检查是否最近调用过此API
    if api_name in self.last_call_times:
        elapsed = time.perf_counter() - self.last_call_times[api_name]
        if elapsed < interval:
            sleep_time = interval - elapsed
            self.logger.debug(f"Rate limiting {api_name}, sleeping for {sleep_time:.2f}s")
            self.interruptible_sleep(sleep_time)
    
    # 记录当前调用时间
    self.last_call_times[api_name] = time.perf_counter()
```

### 实施步骤

1. 备份原始文件：
   ```bash
   cp /home/quan/testdata/aspipe_v4/app/tushare_api.py /home/quan/testdata/aspipe_v4/app/tushare_api.py.backup
   ```

2. 修改`_advanced_rate_limit`方法，替换为上述简化代码

3. 测试修改效果：
   ```bash
   cd /home/quan/testdata/aspipe_v4/app
   python main.py
   ```

## 预期效果

- 所有API接口调用间隔将根据各自的频率限制自动调整：
  - `stk_factor_pro`接口调用间隔将稳定在2秒左右（60秒/30次）
  - `stk_factor`接口调用间隔将稳定在0.6秒左右（60秒/100次）
  - 其他接口调用间隔将根据各自的限制自动计算
- 不再出现任何接口因频率限制导致的分钟级延迟
- 所有接口使用统一的速率控制逻辑，确保一致性
- 避免触发ErrorHandler中的60秒等待机制

## 缺失API调用限制定义

根据`/home/quan/testdata/aspipe_v4/p/tu.md`文档，以下API在项目中使用但未在`score_config.py`中定义调用限制：

| API名称 | 所需积分 | 建议调用限制(次/分钟) | 高积分用户限制(次/分钟) | 说明 |
|---------|---------|---------------------|---------------------|------|
| trade_cal | 2000 | 200 | 500 | 交易日历数据 |
| stock_st | 3000 | 200 | 500 | ST股票列表 |
| suspend_d | 未明确 | 200 | 500 | 每日停复牌信息 |
| block_trade | 300 | 200 | 500 | 大宗交易 |
| share_float | 120 | 200 | 500 | 限售股解禁 |
| top10_holders | 2000 | 200 | 500 | 前十大股东数据 |
| stk_rewards | 2000 | 200 | 500 | 管理层薪酬和持股 |
| stk_managers | 2000 | 200 | 500 | 上市公司管理层 |
| stk_holdertrade | 未明确 | 200 | 500 | 股东增减持数据 |
| forecast | 2000 | 200 | 500 | 业绩预告数据 |
| forecast_vip | 5000 | 200 | 500 | 业绩预告数据(VIP) |
| express | 2000 | 200 | 500 | 业绩快报 |
| express_vip | 5000 | 200 | 500 | 业绩快报(VIP) |
| fina_audit | 500 | 200 | 500 | 财务审计意见 |
| fina_mainbz | 2000 | 200 | 500 | 主营业务构成 |
| fina_mainbz_vip | 5000 | 200 | 500 | 主营业务构成(VIP) |
| disclosure_date | 未明确 | 200 | 500 | 财报披露计划 |
| new_share | 120 | 200 | 500 | IPO新股列表 |
| stock_company | 120 | 200 | 500 | 上市公司基本信息 |
| namechange | 未明确 | 200 | 500 | 股票曾用名 |
| dividend | 2000 | 200 | 500 | 分红送股数据 |
| stock_hsgt | 3000 | 200 | 500 | 沪深港通股票列表 |
| pledge_stat | 未明确 | 200 | 500 | 股票质押统计 |
| pledge_detail | 未明确 | 200 | 500 | 股票质押明细 |
| repurchase | 600 | 200 | 500 | 上市公司回购股票 |
| bak_basic | 5000 | 200 | 500 | 备用基础数据 |

### 已知API频次信息（来自tu.md）

| API名称 | 5000积分限制 | 8000积分限制 | 说明 |
|---------|-------------|-------------|------|
| daily | 500 | 500 | 基础积分每分钟500次 |
| stk_factor | 100 | 500 | 技术面因子数据 |
| stk_factor_pro | 30 | 500 | 技术面因子数据(专业版) |
| report_rc | - | 500 | 8000积分正式权限，每天100000次 |

### 完善score_config.py建议

根据分析，现有的score_config.py已经对部分API进行了积分分层限制，但不够全面。**强烈建议统一使用5000积分的限制，完全移除积分判断逻辑**，这样可以：

1. 最大化5000积分用户的下载效率
2. 简化代码结构，减少维护成本
3. 避免因积分判断逻辑错误导致的限制问题

#### 实施方案一：完全移除积分判断（推荐）

```python
def get_api_limits_for_score(user_points):
    """
    Get appropriate API limits based on user's score
    完全移除积分判断，统一使用5000积分的限制
    """
    # 统一使用5000积分的限制，不再根据user_points进行判断
    limits = {
        'daily': {'calls_per_minute': 500},
        'stock_basic': {'calls_per_minute': 500},
        'daily_basic': {'calls_per_minute': 500},
        'income': {'calls_per_minute': 500},
        'balancesheet': {'calls_per_minute': 500},
        'cashflow': {'calls_per_minute': 500},
        'fina_indicator': {'calls_per_minute': 500},
        
        # VIP接口
        'income_vip': {'calls_per_minute': 500},
        'balancesheet_vip': {'calls_per_minute': 500},
        'cashflow_vip': {'calls_per_minute': 500},
        'fina_indicator_vip': {'calls_per_minute': 500},
        'fina_mainbz_vip': {'calls_per_minute': 500},
        
        # 技术面因子（保持特殊限制）
        'stk_factor': {'calls_per_minute': 100},
        'stk_factor_pro': {'calls_per_minute': 30},
        
        # 市场结构
        'cyq_perf': {'calls_per_minute': 500},  # 注意：实际是每天20000次限制，不是每分钟限制
        'cyq_chips': {'calls_per_minute': 500},  # 注意：实际是每天20000次限制，不是每分钟限制
        
        # 资金流向
        'moneyflow_dc': {'calls_per_minute': 500},
        'moneyflow_ths': {'calls_per_minute': 500},
        'moneyflow_ind_dc': {'calls_per_minute': 500},
        'moneyflow_mkt_dc': {'calls_per_minute': 500},
        'moneyflow_cnt_ths': {'calls_per_minute': 500},
        'moneyflow_ind_ths': {'calls_per_minute': 500},
        'moneyflow': {'calls_per_minute': 500},
        
        # 股东数据
        'top10_holders': {'calls_per_minute': 500},
        'top10_floatholders': {'calls_per_minute': 500},
        'stk_rewards': {'calls_per_minute': 500},
        'stk_managers': {'calls_per_minute': 500},
        'stk_holdertrade': {'calls_per_minute': 500},
        
        # 研究数据
        'report_rc': {'calls_per_minute': 500},  # 注意：实际是8000积分每天100000次限制，不是每分钟限制
        'stk_surv': {'calls_per_minute': 500},
        'broker_recommend': {'calls_per_minute': 500},
        
        # 基础数据
        'trade_cal': {'calls_per_minute': 500},
        'stock_st': {'calls_per_minute': 500},
        'suspend_d': {'calls_per_minute': 500},
        'block_trade': {'calls_per_minute': 500},
        'share_float': {'calls_per_minute': 500},
        'new_share': {'calls_per_minute': 500},
        'stock_company': {'calls_per_minute': 500},
        'namechange': {'calls_per_minute': 500},
        'dividend': {'calls_per_minute': 500},
        'stock_hsgt': {'calls_per_minute': 500},
        'pledge_stat': {'calls_per_minute': 500},
        'pledge_detail': {'calls_per_minute': 500},
        'repurchase': {'calls_per_minute': 500},
        'bak_basic': {'calls_per_minute': 500},
        
        # 财务数据
        'forecast': {'calls_per_minute': 500},
        'forecast_vip': {'calls_per_minute': 500},
        'express': {'calls_per_minute': 500},
        'express_vip': {'calls_per_minute': 500},
        'fina_audit': {'calls_per_minute': 500},
        'fina_mainbz': {'calls_per_minute': 500},
        'disclosure_date': {'calls_per_minute': 500},
    }
    
    return limits
```

#### 实施步骤

1. 备份原始文件：
   ```bash
   cp /home/quan/testdata/aspipe_v4/app/score_config.py /home/quan/testdata/aspipe_v4/app/score_config.py.backup
   ```

2. 替换`get_api_limits_for_score`函数为上述代码，完全移除积分判断逻辑

3. 测试修改效果：
   ```bash
   cd /home/quan/testdata/aspipe_v4/app
   python main.py
   ```

#### 优化说明

1. **完全移除积分判断**：不再根据user_points进行任何判断，统一使用最高限制

2. **最大化下载效率**：所有API（除stk_factor_pro和stk_factor外）统一使用500次/分钟的限制

3. **保留特殊限制**：
   - `stk_factor_pro`：保持30次/分钟（2秒间隔）
   - `stk_factor`：保持100次/分钟（0.6秒间隔）

4. **简化代码结构**：移除所有if/else判断，使代码更简洁、更易维护

5. **避免潜在问题**：消除因积分判断逻辑可能导致的限制错误

6. **特别说明**：根据tu.md文档，以下API实际是每日总次数限制而非每分钟限制：
   - `cyq_perf`和`cyq_chips`：5000积分每天20000次（非每分钟限制）
   - `report_rc`：8000积分每天100000次（非每分钟限制）
   
   为了简化实现，这些接口仍设置为500次/分钟，但在实际使用中不太可能触发每日总次数限制。

**注意**：此方案假设用户拥有5000或以上积分。如果用户积分低于5000，可能需要调整方案或添加积分验证逻辑。

## 验证方法

1. 监控日志中所有API调用的时间间隔，确认它们符合各自的频率限制
2. 确认不再出现任何接口因频率限制导致的60秒等待
3. 验证数据下载完整性，确保所有接口都能正常工作
4. 特别关注stk_factor_pro（2秒间隔）和stk_factor（0.6秒间隔）的调用频率