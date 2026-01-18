# 让财务和股东接口支持 --interface 参数的方案

## 问题概述

当前系统虽然支持 `--interface` 参数，但以下接口存在使用问题：

### 受影响的接口列表

1. **stk_rewards** - 管理层薪酬和持股
   - 参数: ts_code（必需）, end_date（报告期）
   - 状态: ✅ 已支持 `--interface stk_rewards`

2. **income** - 利润表
   - 参数: ts_code（可选）, period（报告期）
   - 状态: ⚠️ 已禁用（配置中 `enabled: false`）
   - 说明: 推荐使用 `income_vip`

3. **balancesheet** - 资产负债表
   - 参数: ts_code（可选）, period（报告期）
   - 状态: ⚠️ 已禁用（配置中 `enabled: false`）
   - 说明: 推荐使用 `balancesheet_vip`

4. **cashflow** - 现金流量表
   - 参数: ts_code（可选）, period（报告期）
   - 状态: ⚠️ 已禁用（配置中 `enabled: false`）
   - 说明: 推荐使用 `cashflow_vip`

5. **forecast** - 业绩预告
   - 参数: ts_code（可选）, period（报告期）
   - 状态: ⚠️ 已禁用（配置中 `enabled: false`）
   - 说明: 推荐使用 `forecast_vip`

6. **express** - 业绩快报
   - 参数: ts_code（可选）, period（报告期）
   - 状态: ✅ 已支持 `--interface express`

7. **fina_indicator** - 财务指标数据
   - 参数: ts_code（必需）, period（报告期）
   - 状态: ✅ 已支持 `--interface fina_indicator`

8. **fina_audit** - 财务审计意见
   - 参数: ts_code（必需）, period（报告期）
   - 状态: ✅ 已支持 `--interface fina_audit`

9. **fina_mainbz** - 主营业务构成
   - 参数: ts_code（必需）, period（报告期）
   - 状态: ✅ 已支持 `--interface fina_mainbz`

10. **disclosure_date** - 财报披露计划
    - 参数: ts_code（可选）, end_date（财报周期）
    - 状态: ✅ 已支持 `--interface disclosure_date`

11. **top10_floatholders** - 前十大流通股东
    - 参数: ts_code（必需）, period（报告期）
    - 状态: ✅ 已支持 `--interface top10_floatholders`

12. **top10_holders** - 前十大股东
    - 参数: ts_code（必需）, period（报告期）
    - 状态: ✅ 已支持 `--interface top10_holders`

13. **pledge_detail** - 股权质押明细
    - 参数: ts_code（必需）
    - 状态: ✅ 已支持 `--interface pledge_detail`

14. **pledge_stat** - 股权质押统计
    - 参数: ts_code（可选）, end_date（截止日期）
    - 状态: ✅ 已支持 `--interface pledge_stat`

## 核心问题

### 问题 1: 被禁用的接口无法通过 --interface 调用

`income`, `balancesheet`, `cashflow`, `forecast` 接口在配置文件中被设置为 `enabled: false`，但系统仍然允许通过 `--interface` 参数调用它们，导致下载失败。

### 问题 2: 缺少 period 参数支持

这些财务接口通常需要 `period` 参数（报告期），但当前命令行只支持 `start_date` 和 `end_date`，没有直接支持 `period` 参数。

### 问题 3: ts_code 参数处理不一致

- 有些接口（如 `pledge_detail`）`ts_code` 是必需参数
- 有些接口（如 `forecast`）`ts_code` 是可选参数，不设置可获取全市场数据
- 当前系统对所有使用 `--interface` 的接口都统一添加 `ts_code` 参数（如果通过 `--ts_code` 指定）

## 解决方案

### 方案 1: 启用被禁用的接口并添加警告（推荐）

#### 1.1 修改配置文件

对于被禁用的接口，将 `enabled: false` 改为 `enabled: true`，并添加警告说明：

**income.yaml**
```yaml
name: income
api_name: income
description: "利润表 (单股票模式，建议使用 income_vip 获取全市场数据)"
enabled: true
permissions:
  min_points: 2000
  rate_limit: 60
  query_limit: 10000
  note: "此接口需要指定 ts_code 参数，如需获取全市场数据，请使用 income_vip 接口（需5000积分）"
```

**balancesheet.yaml**
```yaml
name: balancesheet
api_name: balancesheet
description: "资产负债表 (单股票模式，建议使用 balancesheet_vip 获取全市场数据)"
enabled: true
permissions:
  min_points: 2000
  rate_limit: 60
  query_limit: 10000
  note: "此接口需要指定 ts_code 参数，如需获取全市场数据，请使用 balancesheet_vip 接口（需5000积分）"
```

**cashflow.yaml**
```yaml
name: cashflow
api_name: cashflow
description: "现金流量表 (单股票模式，建议使用 cashflow_vip 获取全市场数据)"
enabled: true
permissions:
  min_points: 2000
  rate_limit: 60
  query_limit: 10000
  note: "此接口需要指定 ts_code 参数，如需获取全市场数据，请使用 cashflow_vip 接口（需5000积分）"
```

**forecast.yaml**
```yaml
name: forecast
api_name: forecast
description: "业绩预告 (已禁用，请使用 forecast_vip)"
enabled: true
permissions:
  min_points: 2000
  rate_limit: 60
  query_limit: 10000
  note: "此接口可使用 ts_code 参数获取单只股票数据，不设置 ts_code 可获取全市场数据。如需获取全部股票数据，请使用 forecast_vip 接口（需5000积分）"
```

#### 1.2 在 main.py 中添加 period 参数支持

修改命令行参数解析部分，添加 `--period` 参数：

```python
# 新增通用参数
parser.add_argument('--interface', type=str,
                    help='指定接口名称')
parser.add_argument('--group', type=str,
                    help='指定接口组名称')
parser.add_argument('--concurrency', type=int, default=4,
                    help='并发数')
parser.add_argument('--log-level', type=str, default='INFO',
                    help='日志级别')
parser.add_argument('--ts_code', type=str,
                    help='指定股票代码 (如: 000001.SZ)')
parser.add_argument('--period', type=str,
                    help='指定报告期 (YYYYMMDD格式，如: 20231231表示年报)')
```

#### 1.3 修改参数准备逻辑

在准备请求参数时，添加对 `period` 参数的支持：

```python
# 准备请求参数
args.start_date, args.end_date = validate_and_adjust_date(
    args.start_date,
    args.end_date or datetime.now().strftime('%Y%m%d')
)

params = {
    'start_date': args.start_date,
    'end_date': args.end_date
}

# 如果指定了股票代码，添加到参数中
if args.ts_code:
    params['ts_code'] = args.ts_code

# [新增] 如果指定了报告期，添加到参数中
if args.period:
    params['period'] = args.period
    logger.info(f"Using period parameter: {args.period}")

# 对于需要 ts_code 的接口，检查是否已提供
interface_config = config_loader.get_interface_config(interface_name)
if 'ts_code' in interface_config.get('parameters', {}):
    if interface_config.get('parameters', {}).get('ts_code', {}).get('required', False):
        if 'ts_code' not in params:
            logger.error(f"Interface {interface_name} requires ts_code parameter")
            logger.info(f"Please specify --ts_code parameter or use tscode-historical mode")
            continue
```

### 方案 2: 添加接口分组（补充方案）

创建新的接口分组，方便批量下载财务数据：

**settings.yaml 中添加分组**
```yaml
groups:
  financial_statements:
    - income
    - balancesheet
    - cashflow
    - fina_indicator
    - fina_audit
    - fina_mainbz

  performance_forecast:
    - forecast
    - express

  shareholders_data:
    - top10_holders
    - top10_floatholders
    - stk_rewards
    - pledge_detail
    - pledge_stat
```

这样用户可以通过 `--group financial_statements` 批量下载所有财务报表数据。

## 使用示例

### 示例 1: 下载单只股票的财务指标

```bash
python main.py --interface fina_indicator --ts_code 000001.SZ --period 20231231
```

### 示例 2: 下载单只股票的利润表数据

```bash
python main.py --interface income --ts_code 000001.SZ --period 20231231
```

### 示例 3: 下载单只股票的股权质押明细

```bash
python main.py --interface pledge_detail --ts_code 000001.SZ
```

### 示例 4: 批量下载财务报表

```bash
python main.py --group financial_statements --ts_code 000001.SZ --period 20231231
```

### 示例 5: 下载全市场业绩预告（forecast 接口不需要 ts_code）

```bash
python main.py --interface forecast --period 20231231
```

## 验证步骤

### 1. 验证被禁用接口已启用

```bash
python main.py --interface income --ts_code 000001.SZ --period 20231231
```

期望结果：成功下载数据，并在日志中看到关于使用 income_vip 的提示。

### 2. 验证 period 参数支持

```bash
python main.py --interface fina_indicator --ts_code 000001.SZ --period 20231231
```

期望结果：请求参数中包含 `period: 20231231`。

### 3. 验证 ts_code 必需检查

```bash
python main.py --interface stk_rewards --period 20231231
```

期望结果：报错提示 `stk_rewards requires ts_code parameter`。

### 4. 验证接口分组

```bash
python main.py --group shareholders_data --ts_code 000001.SZ
```

期望结果：下载所有股东相关接口的数据。

## 注意事项

1. **积分要求**：确保 tushare 账户积分满足接口要求（查看配置中的 `min_points`）

2. **API 限制**：注意接口的 `query_limit`（单次返回限制），避免一次性请求过多数据

3. **VIP 接口**：对于需要获取全市场数据的场景，推荐使用 VIP 接口（需要5000积分）

4. **数据量**：财务数据通常数据量较大，建议使用 `--start_date` 和 `--end_date` 限定时间范围

5. **并发控制**：下载大量股票数据时，使用 `--concurrency` 参数控制并发数，避免触发 API 限制

## 实施优先级

### 高优先级（立即实施）
- [x] 启用被禁用的财务接口（income, balancesheet, cashflow, forecast）
- [x] 添加 `--period` 参数支持
- [x] 添加 ts_code 必需参数检查

### 中优先级（短期实施）
- [ ] 添加接口分组（financial_statements, performance_forecast, shareholders_data）
- [ ] 在下载失败时提供更友好的错误提示

### 低优先级（长期优化）
- [ ] 添加接口参数验证（检查 period 格式是否正确）
- [ ] 优化批量下载逻辑（按报告期分组）
- [ ] 添加进度显示和统计信息

## 相关文件

- `/home/quan/testdata/aspipe_v4/app4/main.py` - 主程序入口
- `/home/quan/testdata/aspipe_v4/app4/config/interfaces/*.yaml` - 接口配置文件
- `/home/quan/testdata/aspipe_v4/app4/config/settings.yaml` - 全局配置
