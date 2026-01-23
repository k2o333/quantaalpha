# 接口配置规划文档

**创建日期**: 2026-01-20  
**目标**: 统一接口分组和分页配置管理

---

## 1. 当前接口分组配置现状

### 1.1 settings.yaml中的分组定义

```yaml
groups:
  holders:
    - top10_holders
    - top10_floatholders
    - stk_holdertrade
    - pledge_detail
    - pledge_stat
    - share_float
    - stk_rewards
    - stk_managers
    - stk_surv

  tscode_historical:
    - stk_rewards
    - income_vip
    - balancesheet_vip
    - cashflow_vip
    - forecast_vip
    - express_vip
    - fina_indicator_vip
    - fina_audit
    - fina_mainbz_vip
    - disclosure_date
    - top10_floatholders
    - top10_holders
    - pledge_stat
    - pledge_detail

  daily:
    - daily
    - daily_basic
    - pro_bar
    - trade_cal
    - block_trade
    - bak_daily
    - bak_basic
    - suspend_d
```

### 1.2 问题分析

**问题1**: `dividend`接口未在`tscode_historical`组中
- 导致使用默认日期20230101而非19900101
- 已在README.md中记录，但配置未更新

**问题2**: 分组覆盖不完整
- 55个接口中，只有27个接口被分配到分组
- 28个接口未在任何分组中定义

**未分组的接口列表**:
- bak_basic
- balancesheet
- cashflow
- cyq_chips
- cyq_perf
- disclosure_date (在tscode_historical中但实际分页模式是stock_loop)
- express
- fina_indicator
- fina_mainbz
- forecast
- income
- moneyflow_系列 (8个接口)
- namechange
- new_share
- repurchase
- report_rc
- stk_factor
- stk_factor_pro
- stk_managers
- stk_premarket
- stock_basic
- stock_company
- stock_hsgt
- stock_st
- suspend_d

---

## 2. 分页配置现状

### 2.1 分页模式分布

| 分页模式 | 接口数量 | 说明 |
|---------|---------|------|
| date_range | 33 | 按日期范围分页，使用window_size_days |
| stock_loop | 16 | 按股票循环，每个股票独立请求 |
| offset | 2 | 使用offset/limit分页 |
| 未配置 | 4 | 需要检查是否需要分页 |

### 2.2 window_size_days配置

**默认值来源**:
- 接口YAML配置: `window_size_days: 365` (大多数接口)
- 代码硬编码: `3650`天 (约10年) - downloader.py第305行

**特殊配置**:
- daily: `window_size_days: 1` (按天下载)
- pro_bar: `window_size_days: 5000`

### 2.3 关键问题

**问题**: stock_loop模式的窗口期大小未在YAML中配置

**原因分析**:
```python
# downloader.py 第305行
window_size = pagination_config.get('window_size_days', 3650)  # 默认10年窗口
```

- stock_loop模式也使用date_range的分页逻辑
- 但在stock_loop场景下，这个window_size_days配置在YAML中被**忽略**
- 代码中硬编码的3650覆盖了YAML配置

**对比periodic range**:
```yaml
# 示例：periodic_range配置
pagination:
  enabled: true
  mode: periodic_range
  period_type: quarter  # 支持: day, week, month, quarter, year
```

periodic_range的周期类型在YAML中明确配置，而stock_loop的窗口大小却在代码中硬编码。

---

## 3. 改进方案

### 3.1 方案1: 补充接口分组

**目标**: 将所有接口纳入合理的分组

**新增分组建议**:

```yaml
groups:
  # 现有分组保持不变...

  # 新增: 基础财务数据组
  financial_basic:
    - income
    - balancesheet
    - cashflow
    - fina_indicator
    - fina_mainbz
    - fina_audit

  # 新增: VIP财务数据组（已存在tscode_historical，建议重命名）
  financial_vip:
    - income_vip
    - balancesheet_vip
    - cashflow_vip
    - fina_indicator_vip
    - fina_mainbz_vip
    - express_vip
    - forecast_vip

  # 新增: 市场资金流向组
  moneyflow:
    - moneyflow
    - moneyflow_ths
    - moneyflow_dc
    - moneyflow_ind_ths
    - moneyflow_ind_dc
    - moneyflow_cnt_ths
    - moneyflow_mkt_dc

  # 新增: 特色数据组
  features:
    - cyq_chips
    - cyq_perf
    - stk_factor
    - stk_factor_pro
    - stk_premarket

  # 新增: 公司信息组
  company_info:
    - stock_basic
    - stock_company
    - namechange
    - new_share
    - disclosure_date

  # 新增: 其他数据组
  others:
    - repurchase
    - stock_hsgt
    - stock_st
    - suspend_d
    - bak_basic
    - bak_daily
```

**调整**: 将`dividend`加入`tscode_historical`组

### 3.2 方案2: 统一窗口期配置

**目标**: 所有分页参数都在YAML中配置，移除硬编码

**修改downloader.py**:

```python
# 修改前 (第305行)
window_size = pagination_config.get('window_size_days', 3650)

# 修改后
window_size = pagination_config.get('window_size_days', 365)  # 改为默认365天
```

**为stock_loop接口添加window_size_days配置**:

```yaml
# 示例：income_vip.yaml
pagination:
  enabled: true
  mode: stock_loop
  window_size_days: 3650  # 明确配置10年窗口
```

**配置建议**:
- stock_loop接口: `window_size_days: 3650` (10年，平衡数据量和请求次数)
- daily类接口: `window_size_days: 1` (按天)
- 普通接口: `window_size_days: 365` (1年)

### 3.3 方案3: 增强配置验证

**目标**: 确保配置的一致性和完整性

**新增验证脚本**:

```python
# validate_interface_config.py
"""
验证接口配置:
1. 检查所有接口都有明确的分页配置
2. 检查stock_loop和date_range接口都有window_size_days
3. 检查所有接口都属于至少一个分组
4. 检查重复定义的接口
"""
```

### 3.4 方案4: 文档更新

**更新README.md**:

```markdown
## 接口分组配置

### 分组说明
- **tscode_historical**: 需要股票代码循环的接口（默认起始日期19900101）
- **holders**: 股东相关数据
- **financial_vip**: VIP财务数据（季度数据）
- **financial_basic**: 基础财务数据
- **daily**: 日线市场数据
- **moneyflow**: 资金流向数据
- **features**: 特色指标数据
- **company_info**: 公司基本信息
- **others**: 其他数据

### 分页配置

#### date_range模式
适用于按时间序列的数据，使用window_size_days控制单次请求的时间范围。

```yaml
pagination:
  enabled: true
  mode: date_range
  window_size_days: 365  # 每次请求1年的数据
```

#### stock_loop模式
适用于需要按股票代码循环的数据，每个股票独立请求。

```yaml
pagination:
  enabled: true
  mode: stock_loop
  window_size_days: 3650  # 每个股票单次请求10年的数据
```

#### periodic_range模式
适用于按固定周期（日、周、月、季、年）的数据。

```yaml
pagination:
  enabled: true
  mode: periodic_range
  period_type: quarter  # 支持: day, week, month, quarter, year
```

#### offset模式
适用于使用offset/limit分页的数据。

```yaml
pagination:
  enabled: true
  mode: offset
  default_limit: 5000    # 默认每页数量
  limit_key: limit       # API的limit参数名
  offset_key: offset     # API的offset参数名
```

#### 禁用分页
对于不需要分页的接口，显式禁用分页配置。

```yaml
pagination:
  enabled: false
```

**注意**: 当前配置中，`broker_recommend`和`namechange`接口已正确设置`pagination.enabled: false`。

---

## 4. 实施计划

### 阶段1: 配置补全 (优先级: 高)

**任务**:
1. 将`dividend`添加到`tscode_historical`组
2. 为所有stock_loop接口添加`window_size_days: 3650`配置
3. 为所有date_range接口确认`window_size_days`配置

**影响**: 修复默认日期问题，统一窗口期配置

**预计工作量**: 2小时

### 阶段2: 分组完善 (优先级: 中)

**任务**:
1. 按照方案1补充新的分组
2. 更新settings.yaml
3. 测试分组功能

**影响**: 提高接口管理的清晰度

**预计工作量**: 4小时

### 阶段3: 代码优化 (优先级: 高)

**任务**:
1. 修改downloader.py，移除硬编码3650
2. 添加配置缺失的警告日志
3. 测试所有stock_loop接口

**影响**: 实现真正的配置驱动

**预计工作量**: 3小时

### 阶段4: 验证机制 (优先级: 低)

**任务**:
1. 编写配置验证脚本
2. 添加到CI/CD流程
3. 文档更新

**影响**: 提高配置质量

**预计工作量**: 4小时

---

## 5. 配置示例

### 5.1 完整的接口配置示例

```yaml
# app4/config/interfaces/income_vip.yaml
api_name: income_vip
description: 利润表(VIP) - 按季度获取全部上市公司数据

name: income_vip

pagination:
  enabled: true
  mode: stock_loop  # 股票循环模式
  window_size_days: 3650  # 每个股票请求10年数据

permissions:
  min_points: 5000
  query_limit: 8800
  rate_limit: 60

parameters:
  ts_code:
    description: 股票代码(可选，不填则获取全部股票)
    required: false
    type: string
  start_date:
    description: 报告期开始日期 YYYYMMDD
    required: false
    type: string
  end_date:
    description: 报告期结束日期 YYYYMMDD
    required: false
    type: string
  # ... 其他参数

output:
  primary_key:
    - ts_code
    - ann_date
    - end_date
  sort_by:
    - ann_date
    - end_date
  dedup_enabled: true

derived_fields:
  ann_date_dt:
    description: 日期类型的ann_date
    format: '%Y%m%d'
    source: ann_date
    type: date
  # ... 其他衍生字段
```

### 5.2 更新后的settings.yaml

```yaml
# 接口组定义
groups:
  # 需要股票循环的接口组（默认起始日期19900101）
  tscode_historical:
    - stk_rewards
    - income_vip
    - balancesheet_vip
    - cashflow_vip
    - forecast_vip
    - express_vip
    - fina_indicator_vip
    - fina_audit
    - fina_mainbz_vip
    - disclosure_date
    - top10_floatholders
    - top10_holders
    - pledge_stat
    - pledge_detail
    - dividend  # 新增
    - stk_factor
    - stk_factor_pro

  # 股东数据组
  holders:
    - top10_holders
    - top10_floatholders
    - stk_holdertrade
    - pledge_detail
    - pledge_stat
    - share_float
    - stk_rewards
    - stk_managers
    - stk_surv

  # VIP财务数据组
  financial_vip:
    - income_vip
    - balancesheet_vip
    - cashflow_vip
    - fina_indicator_vip
    - fina_mainbz_vip
    - express_vip
    - forecast_vip

  # 基础财务数据组
  financial_basic:
    - income
    - balancesheet
    - cashflow
    - fina_indicator
    - fina_mainbz
    - fina_audit

  # 日线市场数据组
  daily:
    - daily
    - daily_basic
    - pro_bar
    - trade_cal
    - block_trade
    - bak_daily
    - bak_basic
    - suspend_d

  # 资金流向数据组
  moneyflow:
    - moneyflow
    - moneyflow_ths
    - moneyflow_dc
    - moneyflow_ind_ths
    - moneyflow_ind_dc
    - moneyflow_cnt_ths
    - moneyflow_mkt_dc

  # 特色指标数据组
  features:
    - cyq_chips
    - cyq_perf
    - stk_factor
    - stk_factor_pro
    - stk_premarket

  # 公司信息数据组
  company_info:
    - stock_basic
    - stock_company
    - namechange
    - new_share
    - disclosure_date

  # 其他数据组
  others:
    - repurchase
    - stock_hsgt
    - stock_st
    - suspend_d
    - bak_basic
    - bak_daily
    - report_rc  # 卖方盈利预测数据
    - broker_recommend
    - dividend
```

---

## 6. 风险评估

### 6.1 低风险改动
- 添加接口到分组: 不影响现有功能
- 更新README文档: 无功能影响

### 6.2 中风险改动
- 修改downloader.py默认值: 可能影响未配置window_size_days的接口
- 为接口添加window_size_days: 需要测试验证

**缓解措施**:
- 先在小范围接口测试
- 添加配置验证警告
- 保持向后兼容

### 6.3 高风险改动
- 批量修改所有接口配置: 可能引入配置错误

**缓解措施**:
- 分阶段实施
- 完整测试覆盖
- 配置备份

---

## 7. 测试计划

### 7.1 单元测试

```python
# test_interface_config.py

def test_window_size_days_config():
    """测试所有date_range和stock_loop接口都有window_size_days配置"""
    pass

def test_group_membership():
    """测试所有接口都属于至少一个分组"""
    pass

def test_tscode_historical_default_date():
    """测试tscode_historical组接口使用19900101作为默认起始日期"""
    pass
```

### 7.2 集成测试

**测试用例**:
1. 下载dividend接口，验证起始日期为19900101
2. 下载income_vip接口，验证使用3650天窗口
3. 下载daily接口，验证使用1天窗口
4. 批量下载tscode_historical组，验证所有接口行为一致

---

## 8. 后续优化建议

### 8.1 配置继承机制

```yaml
# 基础配置模板
base_pagination: &base_pagination
  enabled: true
  window_size_days: 365

# 接口配置中使用继承
pagination:
  << : *base_pagination
  mode: date_range
```

### 8.2 动态窗口调整

```python
# 根据API返回的数据量动态调整窗口大小
if avg_records < 1000:
    window_size *= 2  # 数据量小，增大窗口
elif avg_records > 5000:
    window_size //= 2  # 数据量大，减小窗口
```

### 8.3 配置文件拆分

```
config/
├── interfaces/           # 接口配置
├── groups/              # 分组配置
│   ├── tscode_historical.yaml
│   ├── holders.yaml
│   └── ...
└── settings.yaml        # 全局配置
```

---

## 9. 结论

通过本次规划，将解决以下问题:
1. ✅ dividend接口默认日期问题
2. ✅ 接口分组覆盖不完整问题
3. ✅ stock_loop窗口期硬编码问题
4. ✅ 配置管理的统一性和可维护性

**下一步行动**:
- [ ] 阶段1: 修复dividend和window_size_days配置
- [ ] 阶段2: 完善接口分组
- [ ] 阶段3: 优化downloader.py代码
- [ ] 阶段4: 添加配置验证机制
- [ ] 更新相关文档

---

**文档版本**: v1.0  
**创建人**: CodeBuddy  
**创建日期**: 2026-01-20
