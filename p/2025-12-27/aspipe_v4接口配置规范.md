# aspipe_v4 接口配置规范文档

## 一、 YAML 配置规范概述

每个接口的 YAML 配置文件必须包含以下 **6 大类核心信息**：

1. **基础元数据 (Metadata)**: 标识接口身份
2. **权限与限制 (Permissions)**: 积分要求与流控
3. **请求配置 (Request)**: 代理路径、HTTP 方法等
4. **输入参数 (Parameters)**: 字段定义与校验
5. **分页策略 (Pagination)**: 定义如何切分任务
6. **输出配置 (Output)**: 主键定义与字段类型清洗

## 二、 完整配置示例

### 2.1 pro_bar.yaml - A股复权行情

```yaml
# 1. 基础元数据
name: pro_bar
api_name: pro_bar
description: "A股复权行情"

# 2. 权限与限制
permissions:
  min_points: 0    # 最低积分要求
  rate_limit: 60   # 每分钟请求限制
  query_limit: 5000 # 单次请求最大返回行数

# 3. 请求配置
request:
  method: POST
  # 关键配置：接口的额外地址（用于代理服务器场景）
  extra_path: "/api/pro_bar" 
  timeout: 60

# 4. 输入参数定义
parameters:
  ts_code:
    type: string
    required: true
    description: "证券代码"
  start_date:
    type: string
    required: false
    description: "开始日期 YYYYMMDD"
  end_date:
    type: string
    required: false
    description: "结束日期 YYYYMMDD"
  adj:
    type: string
    required: false
    default: "qfq"
    options: ["qfq", "hfq", null]
    description: "复权类型"
  freq:
    type: string
    required: false
    default: "D"
    description: "数据频度"
  asset:
    type: string
    required: false
    default: "E"
    description: "资产类别"
  ma:
    type: list
    required: false
    description: "均线"

# 5. 分页与循环策略
pagination:
  enabled: true
  mode: "date_range"
  window_size_days: 3650
  
# 6. 输出与存储配置
output:
  primary_key: 
    - ts_code
    - trade_date
    - adj
    
  sort_by: ["trade_date"]
  
  columns:
    ts_code:
      type: string
      required: true
    trade_date:
      type: date
      format: "%Y%m%d"
      required: true
    open:
      type: float
    close:
      type: float
    high:
      type: float
    low:
      type: float
    vol:
      type: float
    amount:
      type: float
```

### 2.2 stock_basic.yaml - 股票列表

```yaml
name: stock_basic
api_name: stock_basic
description: "股票列表"

permissions:
  min_points: 2000
  rate_limit: 60
  query_limit: 5000

request:
  method: POST
  extra_path: ""
  timeout: 30

parameters:
  exchange:
    type: string
    required: false
    description: "交易所 SSE上交所 SZSE深交所"
  list_status:
    type: string
    required: false
    default: "L"
    options: ["L", "D", "P", "S"]
    description: "上市状态 L上市 D退市 P暂停上市 S终止上市"

pagination:
  enabled: true
  mode: "offset"
  limit_key: "limit"
  offset_key: "offset"
  default_limit: 5000

output:
  primary_key: ["ts_code"]
  columns:
    ts_code: {type: string, required: true}
    symbol: {type: string}
    name: {type: string}
    area: {type: string}
    industry: {type: string}
    fullname: {type: string}
    enname: {type: string}
    market: {type: string}
    exchange: {type: string}
    curr_type: {type: string}
    list_status: {type: string}
    list_date: {type: date, format: "%Y%m%d"}
    delist_date: {type: date, format: "%Y%m%d"}
    is_hs: {type: string}
```

### 2.3 trade_cal.yaml - 交易日历

```yaml
name: trade_cal
api_name: trade_cal
description: "交易日历"

permissions:
  min_points: 0
  rate_limit: 120
  query_limit: 5000

request:
  method: POST
  extra_path: ""
  timeout: 30

parameters:
  exchange:
    type: string
    required: false
    default: "SSE"
    description: "交易所 SSE上交所 SZSE深交所"
  start_date:
    type: string
    required: false
    description: "开始日期 YYYYMMDD"
  end_date:
    type: string
    required: false
    description: "结束日期 YYYYMMDD"

pagination:
  enabled: true
  mode: "date_range"
  window_size_days: 365

output:
  primary_key: ["cal_date", "exchange"]
  sort_by: ["cal_date"]
  columns:
    cal_date: {type: date, format: "%Y%m%d", required: true}
    exchange: {type: string, required: true}
    is_open: {type: int, required: true}
    pretrade_date: {type: date, format: "%Y%m%d"}
```

### 2.4 daily.yaml - 日线行情

```yaml
name: daily
api_name: daily
description: "日线行情"

permissions:
  min_points: 0
  rate_limit: 120
  query_limit: 5000

request:
  method: POST
  extra_path: ""
  timeout: 30

parameters:
  ts_code:
    type: string
    required: false
    description: "证券代码"
  trade_date:
    type: string
    required: false
    description: "交易日期 YYYYMMDD"
  start_date:
    type: string
    required: false
    description: "开始日期 YYYYMMDD"
  end_date:
    type: string
    required: false
    description: "结束日期 YYYYMMDD"

pagination:
  enabled: true
  mode: "date_range"
  window_size_days: 365

output:
  primary_key: ["ts_code", "trade_date"]
  sort_by: ["trade_date"]
  columns:
    ts_code: {type: string, required: true}
    trade_date: {type: date, format: "%Y%m%d", required: true}
    open: {type: float}
    high: {type: float}
    low: {type: float}
    close: {type: float}
    pre_close: {type: float}
    change: {type: float}
    pct_chg: {type: float}
    vol: {type: float}
    amount: {type: float}
```

### 2.5 daily_basic.yaml - 每日指标

```yaml
name: daily_basic
api_name: daily_basic
description: "每日指标"

permissions:
  min_points: 2000
  rate_limit: 120
  query_limit: 5000

request:
  method: POST
  extra_path: ""
  timeout: 30

parameters:
  ts_code:
    type: string
    required: false
    description: "证券代码"
  trade_date:
    type: string
    required: false
    description: "交易日期 YYYYMMDD"
  start_date:
    type: string
    required: false
    description: "开始日期 YYYYMMDD"
  end_date:
    type: string
    required: false
    description: "结束日期 YYYYMMDD"

pagination:
  enabled: true
  mode: "date_range"
  window_size_days: 365

output:
  primary_key: ["ts_code", "trade_date"]
  sort_by: ["trade_date"]
  columns:
    ts_code: {type: string, required: true}
    trade_date: {type: date, format: "%Y%m%d", required: true}
    close: {type: float}
    turnover_rate: {type: float}
    turnover_rate_f: {type: float}
    volume_ratio: {type: float}
    pe: {type: float}
    pe_ttm: {type: float}
    pb: {type: float}
    ps: {type: float}
    ps_ttm: {type: float}
    dv_ratio: {type: float}
    dv_ttm: {type: float}
    total_share: {type: float}
    float_share: {type: float}
    free_share: {type: float}
    total_mv: {type: float}
    circ_mv: {type: float}
```

### 2.6 income.yaml - 利润表

```yaml
name: income
api_name: income
description: "利润表"

permissions:
  min_points: 2000
  rate_limit: 60
  query_limit: 5000

request:
  method: POST
  extra_path: ""
  timeout: 30

parameters:
  ts_code:
    type: string
    required: false
    description: "证券代码"
  ann_date:
    type: string
    required: false
    description: "公告日期 YYYYMMDD"
  f_ann_date:
    type: string
    required: false
    description: "实际公告日期 YYYYMMDD"
  start_date:
    type: string
    required: false
    description: "报告期开始日期 YYYYMMDD"
  end_date:
    type: string
    required: false
    description: "报告期结束日期 YYYYMMDD"
  period:
    type: string
    required: false
    description: "报告期 YYYYMMDD"

pagination:
  enabled: true
  mode: "date_range"
  window_size_days: 365

output:
  primary_key: ["ts_code", "ann_date", "end_date"]
  sort_by: ["ann_date", "end_date"]
  columns:
    ts_code: {type: string, required: true}
    ann_date: {type: date, format: "%Y%m%d"}
    f_ann_date: {type: date, format: "%Y%m%d"}
    end_date: {type: date, format: "%Y%m%d", required: true}
    report_type: {type: string}
    comp_type: {type: string}
    basic_eps: {type: float}
    diluted_eps: {type: float}
    total_revenue: {type: float}
    revenue: {type: float}
    int_income: {type: float}
    prem_earned: {type: float}
    comm_income: {type: float}
    n_comm_income: {type: float}
    n_oth_income: {type: float}
    n_oth_b_income: {type: float}
    total_cogs: {type: float}
    oper_exp: {type: float}
    admin_exp: {type: float}
    fin_exp: {type: float}
    impa_taxes: {type: float}
    disp_ral: {type: float}
    credit_impair: {type: float}
    assets_impair: {type: float}
    invest_income: {type: float}
    ass_invest_income: {type: float}
    oper_profit: {type: float}
    non_oper_income: {type: float}
    non_oper_exp: {type: float}
    nca_disploss: {type: float}
    total_profit: {type: float}
    income_tax: {type: float}
    n_income: {type: float}
    n_income_attr_p: {type: float}
    minority_gain: {type: float}
    oth_compr_income: {type: float}
    t_compr_income: {type: float}
    compr_inc_attr_p: {type: float}
    compr_inc_attr_m_s: {type: float}
```

### 2.7 balancesheet.yaml - 资产负债表

```yaml
name: balancesheet
api_name: balancesheet
description: "资产负债表"

permissions:
  min_points: 2000
  rate_limit: 60
  query_limit: 5000

request:
  method: POST
  extra_path: ""
  timeout: 30

parameters:
  ts_code:
    type: string
    required: false
    description: "证券代码"
  ann_date:
    type: string
    required: false
    description: "公告日期 YYYYMMDD"
  f_ann_date:
    type: string
    required: false
    description: "实际公告日期 YYYYMMDD"
  start_date:
    type: string
    required: false
    description: "报告期开始日期 YYYYMMDD"
  end_date:
    type: string
    required: false
    description: "报告期结束日期 YYYYMMDD"
  period:
    type: string
    required: false
    description: "报告期 YYYYMMDD"

pagination:
  enabled: true
  mode: "date_range"
  window_size_days: 365

output:
  primary_key: ["ts_code", "ann_date", "end_date"]
  sort_by: ["ann_date", "end_date"]
  columns:
    ts_code: {type: string, required: true}
    ann_date: {type: date, format: "%Y%m%d"}
    f_ann_date: {type: date, format: "%Y%m%d"}
    end_date: {type: date, format: "%Y%m%d", required: true}
    report_type: {type: string}
    comp_type: {type: string}
    total_assets: {type: float}
    cur_assets: {type: float}
    non_cur_assets: {type: float}
    total_liab: {type: float}
    cur_liab: {type: float}
    non_cur_liab: {type: float}
    total_hldr_eqy_exc_min_int: {type: float}
    total_hldr_eqy_inc_min_int: {type: float}
    total_equity: {type: float}
    equities_parent_comp: {type: float}
    minority_int: {type: float}
```

### 2.8 cashflow.yaml - 现金流量表

```yaml
name: cashflow
api_name: cashflow
description: "现金流量表"

permissions:
  min_points: 2000
  rate_limit: 60
  query_limit: 5000

request:
  method: POST
  extra_path: ""
  timeout: 30

parameters:
  ts_code:
    type: string
    required: false
    description: "证券代码"
  ann_date:
    type: string
    required: false
    description: "公告日期 YYYYMMDD"
  f_ann_date:
    type: string
    required: false
    description: "实际公告日期 YYYYMMDD"
  start_date:
    type: string
    required: false
    description: "报告期开始日期 YYYYMMDD"
  end_date:
    type: string
    required: false
    description: "报告期结束日期 YYYYMMDD"
  period:
    type: string
    required: false
    description: "报告期 YYYYMMDD"

pagination:
  enabled: true
  mode: "date_range"
  window_size_days: 365

output:
  primary_key: ["ts_code", "ann_date", "end_date"]
  sort_by: ["ann_date", "end_date"]
  columns:
    ts_code: {type: string, required: true}
    ann_date: {type: date, format: "%Y%m%d"}
    f_ann_date: {type: date, format: "%Y%m%d"}
    end_date: {type: date, format: "%Y%m%d", required: true}
    report_type: {type: string}
    comp_type: {type: string}
    net_cash_flows_oper_act: {type: float}
    net_cash_flows_inv_act: {type: float}
    net_cash_flows_fin_act: {type: float}
    net_increase_cash_cash_equ: {type: float}
```

### 2.9 fina_indicator.yaml - 财务指标

```yaml
name: fina_indicator
api_name: fina_indicator
description: "财务指标"

permissions:
  min_points: 2000
  rate_limit: 60
  query_limit: 5000

request:
  method: POST
  extra_path: ""
  timeout: 30

parameters:
  ts_code:
    type: string
    required: false
    description: "证券代码"
  ann_date:
    type: string
    required: false
    description: "公告日期 YYYYMMDD"
  start_date:
    type: string
    required: false
    description: "报告期开始日期 YYYYMMDD"
  end_date:
    type: string
    required: false
    description: "报告期结束日期 YYYYMMDD"
  period:
    type: string
    required: false
    description: "报告期 YYYYMMDD"

pagination:
  enabled: true
  mode: "date_range"
  window_size_days: 365

output:
  primary_key: ["ts_code", "ann_date", "end_date"]
  sort_by: ["ann_date", "end_date"]
  columns:
    ts_code: {type: string, required: true}
    ann_date: {type: date, format: "%Y%m%d"}
    end_date: {type: date, format: "%Y%m%d", required: true}
    roe: {type: float}
    roe_waa: {type: float}
    roa: {type: float}
    npta: {type: float}
    roic: {type: float}
    roe_dt: {type: float}
    roa2: {type: float}
    roe_yearly: {type: float}
    roa_yearly: {type: float}
    gross_margin: {type: float}
    cogs_to_sales: {type: float}
    expenses_to_sales: {type: float}
    profit_to_gr: {type: float}
    netprofit_margin: {type: float}
    grossprofit_margin: {type: float}
    cogs_to_gr: {type: float}
    expense_to_gr: {type: float}
    profit_to_op: {type: float}
    netprofit_margin_op: {type: float}
    eb_to_gr: {type: float}
    oe_to_gr: {type: float}
    profit_to_fin: {type: float}
    netprofit_margin_fin: {type: float}
    current_ratio: {type: float}
    quick_ratio: {type: float}
    cash_ratio: {type: float}
    yoy_sales: {type: float}
    yoy_op: {type: float}
    yoy_profit: {type: float}
    yoy_net_profit: {type: float}
```

### 2.10 moneyflow.yaml - 资金流向

```yaml
name: moneyflow
api_name: moneyflow
description: "资金流向"

permissions:
  min_points: 2000
  rate_limit: 60
  query_limit: 5000

request:
  method: POST
  extra_path: ""
  timeout: 30

parameters:
  ts_code:
    type: string
    required: false
    description: "证券代码"
  trade_date:
    type: string
    required: false
    description: "交易日期 YYYYMMDD"
  start_date:
    type: string
    required: false
    description: "开始日期 YYYYMMDD"
  end_date:
    type: string
    required: false
    description: "结束日期 YYYYMMDD"

pagination:
  enabled: true
  mode: "date_range"
  window_size_days: 365

output:
  primary_key: ["ts_code", "trade_date"]
  sort_by: ["trade_date"]
  columns:
    ts_code: {type: string, required: true}
    trade_date: {type: date, format: "%Y%m%d", required: true}
    buy_elg_vol: {type: float}
    sell_elg_vol: {type: float}
    buy_elg_amt: {type: float}
    sell_elg_amt: {type: float}
    buy_lg_vol: {type: float}
    sell_lg_vol: {type: float}
    buy_lg_amt: {type: float}
    sell_lg_amt: {type: float}
    buy_md_vol: {type: float}
    sell_md_vol: {type: float}
    buy_md_amt: {type: float}
    sell_md_amt: {type: float}
    buy_sm_vol: {type: float}
    sell_sm_vol: {type: float}
    buy_sm_amt: {type: float}
    sell_sm_amt: {type: float}
```

### 2.11 top10_holders.yaml - 前十大股东

```yaml
name: top10_holders
api_name: top10_holders
description: "前十大股东"

permissions:
  min_points: 2000
  rate_limit: 60
  query_limit: 5000

request:
  method: POST
  extra_path: ""
  timeout: 30

parameters:
  ts_code:
    type: string
    required: false
    description: "证券代码"
  period:
    type: string
    required: false
    default: "20231231"
    description: "报告期 YYYYMMDD"

pagination:
  enabled: false

output:
  primary_key: ["ts_code", "period", "holder_name"]
  columns:
    ts_code: {type: string, required: true}
    ann_date: {type: date, format: "%Y%m%d"}
    end_date: {type: date, format: "%Y%m%d"}
    holder_name: {type: string, required: true}
    holder_amount: {type: float}
    holder_rank: {type: int}
```

### 2.12 top10_floatholders.yaml - 前十大流通股东

```yaml
name: top10_floatholders
api_name: top10_floatholders
description: "前十大流通股东"

permissions:
  min_points: 2000
  rate_limit: 60
  query_limit: 5000

request:
  method: POST
  extra_path: ""
  timeout: 30

parameters:
  ts_code:
    type: string
    required: false
    description: "证券代码"
  period:
    type: string
    required: false
    default: "20231231"
    description: "报告期 YYYYMMDD"

pagination:
  enabled: false

output:
  primary_key: ["ts_code", "period", "holder_name"]
  columns:
    ts_code: {type: string, required: true}
    ann_date: {type: date, format: "%Y%m%d"}
    end_date: {type: date, format: "%Y%m%d"}
    holder_name: {type: string, required: true}
    holder_amount: {type: float}
    holder_rank: {type: int}
```

### 2.13 stk_rewards.yaml - 管理层薪酬与持股

```yaml
name: stk_rewards
api_name: stk_rewards
description: "管理层薪酬与持股"

permissions:
  min_points: 2000
  rate_limit: 60
  query_limit: 5000

request:
  method: POST
  extra_path: ""
  timeout: 30

parameters:
  ts_code:
    type: string
    required: false
    description: "证券代码"
  ann_date:
    type: string
    required: false
    description: "公告日期 YYYYMMDD"

pagination:
  enabled: false

output:
  primary_key: ["ts_code", "name", "ann_date"]
  columns:
    ts_code: {type: string, required: true}
    ann_date: {type: date, format: "%Y%m%d"}
    name: {type: string, required: true}
    title: {type: string}
    gender: {type: string}
    edu: {type: string}
    birth_date: {type: date, format: "%Y%m%d"}
    begin_date: {type: date, format: "%Y%m%d"}
    end_date: {type: date, format: "%Y%m%d"}
    return_share: {type: float}
    return_share_ratio: {type: float}
    reward: {type: float}
    is_indep: {type: string}
```

### 2.14 stk_managers.yaml - 高管持股

```yaml
name: stk_managers
api_name: stk_managers
description: "高管持股"

permissions:
  min_points: 2000
  rate_limit: 60
  query_limit: 5000

request:
  method: POST
  extra_path: ""
  timeout: 30

parameters:
  ts_code:
    type: string
    required: false
    description: "证券代码"
  ann_date:
    type: string
    required: false
    description: "公告日期 YYYYMMDD"

pagination:
  enabled: false

output:
  primary_key: ["ts_code", "name", "ann_date"]
  columns:
    ts_code: {type: string, required: true}
    ann_date: {type: date, format: "%Y%m%d"}
    name: {type: string, required: true}
    gender: {type: string}
    lev: {type: string}
    title: {type: string}
    edu: {type: string}
    birth_date: {type: date, format: "%Y%m%d"}
    begin_date: {type: date, format: "%Y%m%d"}
    end_date: {type: date, format: "%Y%m%d"}
    hold_stock: {type: float}
```

### 2.15 pledge_detail.yaml - 股权质押明细

```yaml
name: pledge_detail
api_name: pledge_detail
description: "股权质押明细"

permissions:
  min_points: 2000
  rate_limit: 60
  query_limit: 5000

request:
  method: POST
  extra_path: ""
  timeout: 30

parameters:
  ts_code:
    type: string
    required: false
    description: "证券代码"
  ann_date:
    type: string
    required: false
    description: "公告日期 YYYYMMDD"

pagination:
  enabled: false

output:
  primary_key: ["ts_code", "ann_date", "pledgor"]
  columns:
    ts_code: {type: string, required: true}
    ann_date: {type: date, format: "%Y%m%d"}
    pledge_id: {type: string}
    pledgor: {type: string, required: true}
    pledgee: {type: string}
    pledge_amount: {type: float}
    pledge_start_date: {type: date, format: "%Y%m%d"}
    pledge_end_date: {type: date, format: "%Y%m%d"}
    pledge_status: {type: string}
```

### 2.16 stk_factor.yaml - 技术因子

```yaml
name: stk_factor
api_name: stk_factor
description: "技术因子"

permissions:
  min_points: 5000
  rate_limit: 60
  query_limit: 5000

request:
  method: POST
  extra_path: ""
  timeout: 30

parameters:
  ts_code:
    type: string
    required: false
    description: "证券代码"
  trade_date:
    type: string
    required: false
    description: "交易日期 YYYYMMDD"
  start_date:
    type: string
    required: false
    description: "开始日期 YYYYMMDD"
  end_date:
    type: string
    required: false
    description: "结束日期 YYYYMMDD"

pagination:
  enabled: true
  mode: "stock_loop"

output:
  primary_key: ["ts_code", "trade_date"]
  sort_by: ["trade_date"]
  columns:
    ts_code: {type: string, required: true}
    trade_date: {type: date, format: "%Y%m%d", required: true}
    pe: {type: float}
    pe_ttm: {type: float}
    pb: {type: float}
    ps: {type: float}
    ps_ttm: {type: float}
    dv_ratio: {type: float}
    dv_ttm: {type: float}
    total_share: {type: float}
    float_share: {type: float}
    free_share: {type: float}
    total_mv: {type: float}
    circ_mv: {type: float}
```

### 2.17 cyq_perf.yaml - 筹码分布绩效

```yaml
name: cyq_perf
api_name: cyq_perf
description: "筹码分布绩效"

permissions:
  min_points: 5000
  rate_limit: 60
  query_limit: 5000

request:
  method: POST
  extra_path: ""
  timeout: 30

parameters:
  ts_code:
    type: string
    required: false
    description: "证券代码"
  start_date:
    type: string
    required: false
    description: "开始日期 YYYYMMDD"
  end_date:
    type: string
    required: false
    description: "结束日期 YYYYMMDD"

pagination:
  enabled: true
  mode: "stock_loop"

output:
  primary_key: ["ts_code", "trade_date"]
  sort_by: ["trade_date"]
  columns:
    ts_code: {type: string, required: true}
    trade_date: {type: date, format: "%Y%m%d", required: true}
    avg_cost: {type: float}
    profit_ratio: {type: float}
    loss_ratio: {type: float}
```

### 2.18 cyq_chips.yaml - 筹码分布

```yaml
name: cyq_chips
api_name: cyq_chips
description: "筹码分布"

permissions:
  min_points: 5000
  rate_limit: 60
  query_limit: 5000

request:
  method: POST
  extra_path: ""
  timeout: 30

parameters:
  ts_code:
    type: string
    required: false
    description: "证券代码"
  start_date:
    type: string
    required: false
    description: "开始日期 YYYYMMDD"
  end_date:
    type: string
    required: false
    description: "结束日期 YYYYMMDD"

pagination:
  enabled: true
  mode: "stock_loop"

output:
  primary_key: ["ts_code", "trade_date", "pct"]
  sort_by: ["trade_date", "pct"]
  columns:
    ts_code: {type: string, required: true}
    trade_date: {type: date, format: "%Y%m%d", required: true}
    pct: {type: float, required: true}
    amount: {type: float}
    volume: {type: float}
    avg_price: {type: float}
```

### 2.19 suspend_d.yaml - 停牌信息

```yaml
name: suspend_d
api_name: suspend_d
description: "停牌信息"

permissions:
  min_points: 2000
  rate_limit: 60
  query_limit: 5000

request:
  method: POST
  extra_path: ""
  timeout: 30

parameters:
  ts_code:
    type: string
    required: false
    description: "证券代码"
  suspend_date:
    type: string
    required: false
    description: "停牌日期 YYYYMMDD"
  resume_date:
    type: string
    required: false
    description: "复牌日期 YYYYMMDD"

pagination:
  enabled: false

output:
  primary_key: ["ts_code", "suspend_date"]
  columns:
    ts_code: {type: string, required: true}
    suspend_date: {type: date, format: "%Y%m%d", required: true}
    suspend_reason: {type: string}
    resume_date: {type: date, format: "%Y%m%d"}
    suspend_days: {type: int}
```

### 2.20 block_trade.yaml - 大宗交易

```yaml
name: block_trade
api_name: block_trade
description: "大宗交易"

permissions:
  min_points: 2000
  rate_limit: 60
  query_limit: 5000

request:
  method: POST
  extra_path: ""
  timeout: 30

parameters:
  ts_code:
    type: string
    required: false
    description: "证券代码"
  trade_date:
    type: string
    required: false
    description: "交易日期 YYYYMMDD"
  start_date:
    type: string
    required: false
    description: "开始日期 YYYYMMDD"
  end_date:
    type: string
    required: false
    description: "结束日期 YYYYMMDD"

pagination:
  enabled: true
  mode: "date_range"
  window_size_days: 365

output:
  primary_key: ["ts_code", "trade_date", "time"]
  sort_by: ["trade_date", "time"]
  columns:
    ts_code: {type: string, required: true}
    trade_date: {type: date, format: "%Y%m%d", required: true}
    time: {type: string}
    price: {type: float}
    volume: {type: float}
    amount: {type: float}
    buyer_name: {type: string}
    seller_name: {type: string}
```

### 2.21 share_float.yaml - 股东持股变动

```yaml
name: share_float
api_name: share_float
description: "股东持股变动"

permissions:
  min_points: 2000
  rate_limit: 60
  query_limit: 5000

request:
  method: POST
  extra_path: ""
  timeout: 30

parameters:
  ts_code:
    type: string
    required: false
    description: "证券代码"
  ann_date:
    type: string
    required: false
    description: "公告日期 YYYYMMDD"
  start_date:
    type: string
    required: false
    description: "开始日期 YYYYMMDD"
  end_date:
    type: string
    required: false
    description: "结束日期 YYYYMMDD"

pagination:
  enabled: true
  mode: "date_range"
  window_size_days: 365

output:
  primary_key: ["ts_code", "ann_date", "holder_name"]
  sort_by: ["ann_date"]
  columns:
    ts_code: {type: string, required: true}
    ann_date: {type: date, format: "%Y%m%d"}
    end_date: {type: date, format: "%Y%m%d"}
    holder_name: {type: string}
    holder_rank: {type: int}
    holder_amount: {type: float}
    holder_class: {type: string}
```

### 2.22 report_rc.yaml - 卖方盈利预测

```yaml
name: report_rc
api_name: report_rc
description: "卖方盈利预测"

permissions:
  min_points: 5000
  rate_limit: 60
  query_limit: 5000

request:
  method: POST
  extra_path: ""
  timeout: 30

parameters:
  ts_code:
    type: string
    required: false
    description: "证券代码"
  period:
    type: string
    required: false
    description: "报告期 YYYYMMDD"

pagination:
  enabled: false

output:
  primary_key: ["ts_code", "period", "org_name"]
  columns:
    ts_code: {type: string, required: true}
    period: {type: string, required: true}
    org_name: {type: string}
    analyst: {type: string}
    eps: {type: float}
    net_profit: {type: float}
    report_date: {type: date, format: "%Y%m%d"}
```

### 2.23 stk_surv.yaml - 股票调研

```yaml
name: stk_surv
api_name: stk_surv
description: "股票调研"

permissions:
  min_points: 5000
  rate_limit: 60
  query_limit: 5000

request:
  method: POST
  extra_path: ""
  timeout: 30

parameters:
  ts_code:
    type: string
    required: false
    description: "证券代码"
  start_date:
    type: string
    required: false
    description: "开始日期 YYYYMMDD"
  end_date:
    type: string
    required: false
    description: "结束日期 YYYYMMDD"

pagination:
  enabled: true
  mode: "date_range"
  window_size_days: 365

output:
  primary_key: ["ts_code", "surv_date", "org_name"]
  sort_by: ["surv_date"]
  columns:
    ts_code: {type: string, required: true}
    surv_date: {type: date, format: "%Y%m%d", required: true}
    org_name: {type: string}
    surv_type: {type: string}
    surv_way: {type: string}
    surv_obj: {type: string}
    start_date: {type: date, format: "%Y%m%d"}
    end_date: {type: date, format: "%Y%m%d"}
    surv_place: {type: string}
    surv_detail: {type: string}
```

### 2.24 broker_recommend.yaml - 券商评级

```yaml
name: broker_recommend
api_name: broker_recommend
description: "券商评级"

permissions:
  min_points: 5000
  rate_limit: 60
  query_limit: 5000

request:
  method: POST
  extra_path: ""
  timeout: 30

parameters:
  ts_code:
    type: string
    required: false
    description: "证券代码"
  start_date:
    type: string
    required: false
    description: "开始日期 YYYYMMDD"
  end_date:
    type: string
    required: false
    description: "结束日期 YYYYMMDD"

pagination:
  enabled: true
  mode: "date_range"
  window_size_days: 365

output:
  primary_key: ["ts_code", "ann_date", "broker_name"]
  sort_by: ["ann_date"]
  columns:
    ts_code: {type: string, required: true}
    ann_date: {type: date, format: "%Y%m%d", required: true}
    broker_name: {type: string}
    first_rank: {type: string}
    second_rank: {type: string}
    rating: {type: string}
    rating_change: {type: string}
```

### 2.25 news.yaml - 新闻资讯

```yaml
name: news
api_name: news
description: "新闻资讯"

permissions:
  min_points: 5000
  rate_limit: 60
  query_limit: 5000

request:
  method: POST
  extra_path: ""
  timeout: 30

parameters:
  src:
    type: string
    required: false
    description: "来源"
  start_date:
    type: string
    required: false
    description: "开始日期 YYYYMMDD"
  end_date:
    type: string
    required: false
    description: "结束日期 YYYYMMDD"

pagination:
  enabled: true
  mode: "date_range"
  window_size_days: 7

output:
  primary_key: ["datetime", "title"]
  sort_by: ["datetime"]
  columns:
    datetime: {type: string, required: true}
    content: {type: string}
    title: {type: string}
    channels: {type: string}
    score: {type: float}
    src: {type: string}
```

### 2.26 new_share.yaml - 新股发行

```yaml
name: new_share
api_name: new_share
description: "新股发行"

permissions:
  min_points: 2000
  rate_limit: 60
  query_limit: 5000

request:
  method: POST
  extra_path: ""
  timeout: 30

parameters:
  start_date:
    type: string
    required: false
    description: "开始日期 YYYYMMDD"
  end_date:
    type: string
    required: false
    description: "结束日期 YYYYMMDD"

pagination:
  enabled: true
  mode: "date_range"
  window_size_days: 365

output:
  primary_key: ["ts_code", "subs_date"]
  sort_by: ["subs_date"]
  columns:
    ts_code: {type: string, required: true}
    name: {type: string}
    ipo_date: {type: date, format: "%Y%m%d"}
    issue_date: {type: date, format: "%Y%m%d"}
    subs_date: {type: date, format: "%Y%m%d"}
    subs_amount: {type: float}
    issue_price: {type: float}
    issue_amount: {type: float}
    market_amount: {type: float}
```

### 2.27 stock_company.yaml - 上市公司信息

```yaml
name: stock_company
api_name: stock_company
description: "上市公司信息"

permissions:
  min_points: 2000
  rate_limit: 60
  query_limit: 5000

request:
  method: POST
  extra_path: ""
  timeout: 30

parameters:
  ts_code:
    type: string
    required: false
    description: "证券代码"
  exchange:
    type: string
    required: false
    description: "交易所"

pagination:
  enabled: false

output:
  primary_key: ["ts_code"]
  columns:
    ts_code: {type: string, required: true}
    exchange: {type: string}
    chairman: {type: string}
    manager: {type: string}
    secretary: {type: string}
    reg_capital: {type: float}
    setup_date: {type: date, format: "%Y%m%d"}
    province: {type: string}
    city: {type: string}
    introduction: {type: string}
    website: {type: string}
    email: {type: string}
    office_address: {type: string}
```

### 2.28 namechange.yaml - 股票更名

```yaml
name: namechange
api_name: namechange
description: "股票更名"

permissions:
  min_points: 2000
  rate_limit: 60
  query_limit: 5000

request:
  method: POST
  extra_path: ""
  timeout: 30

parameters:
  ts_code:
    type: string
    required: false
    description: "证券代码"

pagination:
  enabled: false

output:
  primary_key: ["ts_code", "start_date"]
  sort_by: ["start_date"]
  columns:
    ts_code: {type: string, required: true}
    name: {type: string}
    start_date: {type: date, format: "%Y%m%d", required: true}
    end_date: {type: date, format: "%Y%m%d"}
    reason: {type: string}
```

### 2.29 dividend.yaml - 分红送股

```yaml
name: dividend
api_name: dividend
description: "分红送股"

permissions:
  min_points: 2000
  rate_limit: 60
  query_limit: 5000

request:
  method: POST
  extra_path: ""
  timeout: 30

parameters:
  ts_code:
    type: string
    required: false
    description: "证券代码"
  ann_date:
    type: string
    required: false
    description: "公告日期 YYYYMMDD"
  record_date:
    type: string
    required: false
    description: "股权登记日 YYYYMMDD"

pagination:
  enabled: false

output:
  primary_key: ["ts_code", "end_date"]
  sort_by: ["end_date"]
  columns:
    ts_code: {type: string, required: true}
    end_date: {type: date, format: "%Y%m%d", required: true}
    ann_date: {type: date, format: "%Y%m%d"}
    div_proc: {type: string}
    stk_div: {type: float}
    stk_bo_rate: {type: float}
    stk_co_rate: {type: float}
    cash_div: {type: float}
    cash_div_tax: {type: float}
    record_date: {type: date, format: "%Y%m%d"}
    ex_date: {type: date, format: "%Y%m%d"}
    pay_date: {type: date, format: "%Y%m%d"}
```

## 三、 配置字段详细说明

### 3.1 基础元数据 (Metadata)

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | 是 | 接口唯一标识符 |
| `api_name` | string | 是 | TuShare API 实际接口名称 |
| `description` | string | 是 | 接口功能描述 |

### 3.2 权限与限制 (Permissions)

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `min_points` | int | 是 | 最低积分要求，0 表示无限制 |
| `rate_limit` | int | 是 | 每分钟请求次数限制 |
| `query_limit` | int | 否 | 单次请求最大返回行数 |

### 3.3 请求配置 (Request)

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `method` | string | 是 | HTTP 方法 (GET/POST) |
| `extra_path` | string | 否 | 接口额外路径（代理服务器场景） |
| `timeout` | int | 否 | 请求超时时间（秒） |

### 3.4 输入参数 (Parameters)

每个参数支持以下配置项：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | string | 是 | 参数类型 (string/int/float/list/date) |
| `required` | bool | 否 | 是否必填，默认 false |
| `default` | any | 否 | 默认值 |
| `options` | list | 否 | 可选值列表 |
| `description` | string | 否 | 参数说明 |

### 3.5 分页策略 (Pagination)

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `enabled` | bool | 是 | 是否启用分页 |
| `mode` | string | 是 | 分页模式 (offset/date_range/stock_loop) |
| `limit_key` | string | 否 | limit 参数名称 |
| `offset_key` | string | 否 | offset 参数名称 |
| `default_limit` | int | 否 | 默认每页大小 |
| `window_size_days` | int | 否 | 日期范围模式下的窗口大小（天） |

**分页模式说明**：
- `offset`: 使用 offset/limit 分页
- `date_range`: 按日期范围分批下载
- `stock_loop`: 按股票代码循环下载

### 3.6 输出配置 (Output)

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `primary_key` | list | 是 | 主键字段列表 |
| `sort_by` | list | 否 | 排序字段列表 |
| `columns` | object | 是 | 字段定义 |

**字段定义 (columns)**:
每个字段支持以下配置：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | string | 是 | 字段类型 (string/int/float/date) |
| `required` | bool | 否 | 是否必填 |
| `format` | string | 否 | 日期格式（如 "%Y%m%d"） |

## 四、 全局配置示例

### 4.1 settings.yaml - 全局配置

```yaml
# 全局配置
app:
  name: "aspipe_v4"
  version: "4.0.0"

# TuShare API 配置
tushare:
  token: "${TUSHARE_TOKEN}"  # 从环境变量读取
  api_url: "http://api.tushare.pro"
  points_threshold: 2000

# 并发配置
concurrency:
  max_workers: 8
  max_queue_size: 1000

# 缓存配置
cache:
  enabled: true
  base_dir: "./cache"
  default_ttl: 86400  # 24小时（秒）
  max_size_gb: 10
  cleanup_interval: 3600  # 清理间隔（秒）

# 存储配置
storage:
  base_dir: "./data"
  format: "parquet"
  batch_size: 100
  async_write: true

# 日志配置
logging:
  level: "INFO"
  file: "./logs/aspipe_v4.log"
  max_size_mb: 100
  backup_count: 5

# 接口组定义
groups:
  holders:
    - top10_holders
    - top10_floatholders
    - stk_rewards
    - stk_managers
    - pledge_detail
  
  daily:
    - daily
    - daily_basic
    - pro_bar
  
  financial:
    - income
    - balancesheet
    - cashflow
    - fina_indicator
```

## 五、 接口配置模板

### 5.1 日期范围分页模板

```yaml
name: daily
api_name: daily
description: "日线行情"

permissions:
  min_points: 0
  rate_limit: 120
  query_limit: 5000

request:
  method: POST
  extra_path: ""
  timeout: 30

parameters:
  ts_code:
    type: string
    required: false
  trade_date:
    type: string
    required: false
  start_date:
    type: string
    required: false
  end_date:
    type: string
    required: false

pagination:
  enabled: true
  mode: "date_range"
  window_size_days: 365

output:
  primary_key: ["ts_code", "trade_date"]
  sort_by: ["trade_date"]
  columns:
    ts_code: {type: string}
    trade_date: {type: date, format: "%Y%m%d"}
    open: {type: float}
    high: {type: float}
    low: {type: float}
    close: {type: float}
    pre_close: {type: float}
    change: {type: float}
    pct_chg: {type: float}
    vol: {type: float}
    amount: {type: float}
```

### 5.2 Offset 分页模板

```yaml
name: top10_holders
api_name: top10_holders
description: "前十大股东"

permissions:
  min_points: 2000
  rate_limit: 60

request:
  method: POST
  extra_path: ""
  timeout: 30

parameters:
  ts_code:
    type: string
    required: false
  period:
    type: string
    required: false
    default: "20231231"

pagination:
  enabled: false

output:
  primary_key: ["ts_code", "period", "holder_name"]
  columns:
    ts_code: {type: string}
    ann_date: {type: date, format: "%Y%m%d"}
    end_date: {type: date, format: "%Y%m%d"}
    holder_name: {type: string}
    holder_amount: {type: float}
    holder_rank: {type: int}
```

### 5.3 股票循环模板

```yaml
name: stk_factor
api_name: stk_factor
description: "技术因子"

permissions:
  min_points: 5000
  rate_limit: 60

request:
  method: POST
  extra_path: ""
  timeout: 30

parameters:
  ts_code:
    type: string
    required: false
  trade_date:
    type: string
    required: false
  start_date:
    type: string
    required: false
  end_date:
    type: string
    required: false

pagination:
  enabled: true
  mode: "stock_loop"

output:
  primary_key: ["ts_code", "trade_date"]
  sort_by: ["trade_date"]
  columns:
    ts_code: {type: string}
    trade_date: {type: date, format: "%Y%m%d"}
    pe: {type: float}
    pe_ttm: {type: float}
    pb: {type: float}
    ps: {type: float}
    ps_ttm: {type: float}
    dv_ratio: {type: float}
    dv_ttm: {type: float}
    total_share: {type: float}
    float_share: {type: float}
    free_share: {type: float}
    total_mv: {type: float}
    circ_mv: {type: float}
```

## 六、 配置验证规则

### 6.1 必填字段检查

- 所有接口配置必须包含 6 大类核心信息
- `name`, `api_name`, `description` 为必填
- `primary_key` 至少包含一个字段

### 6.2 类型检查

- `type` 必须为有效类型：string, int, float, list, date
- `mode` 必须为有效分页模式：offset, date_range, stock_loop
- `method` 必须为：GET 或 POST

### 6.3 数值范围检查

- `min_points` 必须 >= 0
- `rate_limit` 必须 > 0
- `query_limit` 必须 > 0
- `timeout` 必须 > 0

### 6.4 依赖关系检查

- 当 `pagination.enabled = true` 时，必须指定 `mode`
- 当 `mode = "offset"` 时，必须指定 `limit_key` 和 `offset_key`
- 当 `mode = "date_range"` 时，建议指定 `window_size_days`

## 七、 最佳实践

### 7.1 命名规范

- 接口名称使用小写字母和下划线：`pro_bar`, `stock_basic`
- 参数名称与 TuShare API 保持一致
- 描述使用中文，简洁明了

### 7.2 性能优化

- 合理设置 `rate_limit` 避免触发 API 限制
- 大数据量接口使用分页策略
- 合理设置 `window_size_days` 平衡请求次数和单次数据量

### 7.3 缓存策略

- 静态数据（如股票列表）设置较长的 TTL
- 实时数据（如行情）设置较短的 TTL
- 在接口配置中可以覆盖全局缓存设置

### 7.4 错误处理

- 在 `description` 中说明接口的特殊要求
- 对于有积分要求的接口，明确标注 `min_points`
- 对于有限制的接口，说明 `rate_limit` 和 `query_limit`
