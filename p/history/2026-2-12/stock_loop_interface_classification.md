# Stock Loop 接口分类详表

**日期**: 2026-02-12  
**目的**: 根据 Tushare Pro 接口特性和配置文件，对所有 stock_loop 模式的接口进行分类

---

## 一、类型 A：交易日历接口（按交易日存储）

这些接口按实际交易日存储数据，支持 `start_date` 和 `end_date` 参数进行范围查询。

| 接口 | 查询参数 | 数据日期字段 | 特点 | 配置文件 |
|------|---------|-------------|------|----------|
| `cyq_chips` | `start_date`, `end_date` | `trade_date` | 每日筹码分布数据 | cyq_chips.yaml |
| `moneyflow_dc` | `start_date`, `end_date` | `trade_date` | 个股资金流向（东财） | moneyflow_dc.yaml |
| `stk_factor_pro` | `start_date`, `end_date` | `trade_date` | 股票因子数据 | stk_factor_pro.yaml |

**缺口检测方式**: 使用交易日历，检测缺失的交易日

---

## 二、类型 B：报告期接口（财报类，支持范围查询）

这些接口按财务报告期存储数据（通常是季度末），支持 `start_date` 和 `end_date` 参数进行范围查询。

| 接口 | 查询参数 | 数据日期字段 | 特点 | 配置文件 |
|------|---------|-------------|------|----------|
| `income_vip` | `start_date`, `end_date` | `end_date` | 利润表(VIP)，按报告期存储 | income_vip.yaml |
| `balancesheet_vip` | `start_date`, `end_date` | `end_date` | 资产负债表(VIP)，按报告期存储 | balancesheet_vip.yaml |
| `cashflow_vip` | `start_date`, `end_date` | `end_date` | 现金流量表(VIP)，按报告期存储 | cashflow_vip.yaml |
| `fina_indicator_vip` | `start_date`, `end_date` | `end_date` | 财务指标数据(VIP)，按报告期存储 | fina_indicator_vip.yaml |
| `fina_audit` | `start_date`, `end_date` | `end_date` | 财务审计信息，按报告期存储 | fina_audit.yaml |
| `fina_mainbz_vip` | `start_date`, `end_date` | `end_date` | 主营业务构成(VIP)，按报告期存储 | fina_mainbz_vip.yaml |
| `forecast_vip` | `start_date`, `end_date` | `end_date` | 业绩预告(VIP)，按报告期存储 | forecast_vip.yaml |

**缺口检测方式**: 使用报告期列表（0331、0630、0930、1231），检测缺失的报告期

---

## 三、类型 C：日期锚定接口（不支持范围查询，需逐个查询）

这些接口不支持 `start_date`/`end_date` 范围查询，而是通过特定的日期锚定参数进行单次查询。

| 接口 | 查询参数 | 数据日期字段 | 锚定参数 | 特点 | 配置文件 |
|------|---------|-------------|----------|------|----------|
| `disclosure_date` | `end_date` (单个) | `end_date` | `end_date` | 财报披露计划，只能按单个报告期查询 | disclosure_date.yaml |
| `top10_holders` | `period` (单个) | `end_date` | `period` | 前十大股东，只能按单个报告期查询 | top10_holders.yaml |
| `top10_floatholders` | `period` (单个) | `end_date` | `period` | 前十大流通股东，只能按单个报告期查询 | top10_floatholders.yaml |
| `dividend` | `ann_date` (单个) | `ann_date` | `ann_date` | 分红送股，只能按单个公告日期查询 | dividend.yaml |
| `pledge_detail` | `ann_date` (单个) | `ann_date` | `ann_date` | 股权质押明细，只能按单个公告日期查询 | pledge_detail.yaml |
| `pledge_stat` | `end_date` (单个) | `end_date` | `end_date` | 股权质押统计，只能按单个报告期查询 | pledge_stat.yaml |
| `stk_rewards` | `end_date` (单个) | `end_date` | `end_date` | 股票奖励，只能按单个报告期查询 | stk_rewards.yaml |

**缺口检测方式**: 遍历所有可能的锚点值，逐个查询缺失的

---

## 四、接口参数特征分析

### 4.1 交易日历接口参数特征
- 包含 `trade_date`, `start_date`, `end_date` 参数
- 数据日期字段通常为 `trade_date`
- 支持日期范围查询

### 4.2 报告期接口参数特征
- 包含 `start_date`, `end_date`, `period`, `ann_date` 参数
- 数据日期字段通常为 `end_date` 或 `ann_date`
- 支持日期范围查询
- `is_date_anchor` 标记为 `false`

### 4.3 日期锚定接口参数特征
- 包含特定锚定参数如 `end_date`, `period`, `ann_date`
- 数据日期字段与锚定参数相关
- 不支持 `start_date`/`end_date` 范围查询
- `is_date_anchor` 标记为 `true`

---

## 五、缺口检测策略建议

### 5.1 类型 A 接口（交易日历）
- 使用交易日历检测缺失的交易日
- 合并连续的日期缺口为范围参数

### 5.2 类型 B 接口（报告期）
- 生成标准报告期列表（Q1:0331, Q2:0630, Q3:0930, Q4:1231）
- 检测缺失的报告期
- 由于支持范围查询，可返回整个范围

### 5.3 类型 C 接口（日期锚定）
- 生成锚定参数的所有可能值
- 逐一检测每个锚定值是否存在
- 为每个缺失的锚定值生成单独的查询任务

---

## 六、总结

本分类基于以下因素：
1. 接口参数配置（特别是 `is_date_anchor` 标记）
2. 数据日期字段类型（`trade_date` vs `end_date` vs `ann_date`）
3. 是否支持范围查询（`start_date`/`end_date`）
4. 业务数据特性（交易日数据 vs 报告期数据 vs 公告数据）

此分类有助于实现精确的增量下载策略，针对不同类型的接口采用最适合的缺口检测方法。