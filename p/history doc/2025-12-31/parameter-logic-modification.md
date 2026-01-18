# aspipe_v4 参数逻辑修改方案

## 修改背景

当前代码中，`--tscode-historical` 和 `--pro_bar_only` 等参数是互斥的（使用 if-elif 链），无法组合使用。同时，`--tscode-historical` 单独使用时会下载所有接口，而不是只下载需要 ts_code 的4个接口。

## 修改目标

1. 支持参数组合使用（如 `--tscode-historical --pro_bar_only`）
2. `--tscode-historical` 单独使用时，只下载那4个需要 ts_code 的接口
3. 默认行为（不加任何参数）时，排除那4个接口以及 pro_bar

## 修改位置

**文件**：`/home/quan/testdata/aspipe_v4/app4/main.py`  
**行数**：约 332-353 行

## 修改前代码

```python
# 确定要执行的接口
interfaces_to_run = []

# 参数映射逻辑
if args.pro_bar_only:
    interfaces_to_run = ['pro_bar']
elif args.holders_data:
    holders_group = config_loader.global_config.get('groups', {}).get('holders', [])
    interfaces_to_run = holders_group
elif args.interface:
    interfaces_to_run = [args.interface]
elif args.group:
    groups = config_loader.global_config.get('groups', {})
    if args.group in groups:
        interfaces_to_run = groups[args.group]
    else:
        logger.error(f"Group '{args.group}' not found")
        return 1
else:
    # 默认运行所有可用接口（可根据积分限制过滤）
    available_interfaces = config_loader.get_available_interfaces()
    # 过滤掉ts_code依赖的接口，如果是日期范围下载模式
    if not args.tscode_historical:
        interfaces_to_run = [iface for iface in available_interfaces if iface not in ['stk_rewards', 'top10_holders', 'pledge_detail', 'fina_audit']]
    else:
        interfaces_to_run = available_interfaces

logger.info(f"Interfaces to run: {interfaces_to_run}")
```

## 修改后代码

```python
# 确定要执行的接口
interfaces_to_run = []

# 参数映射逻辑（改为累加模式）
if args.tscode_historical:
    # tscode-historical 模式：只下载那4个需要 ts_code 的接口
    interfaces_to_run.extend(['stk_rewards', 'top10_holders', 'pledge_detail', 'fina_audit'])

if args.pro_bar_only:
    # pro_bar_only 模式：添加 pro_bar 接口
    interfaces_to_run.append('pro_bar')

if args.holders_data:
    # holders_data 模式：添加 holders 组
    holders_group = config_loader.global_config.get('groups', {}).get('holders', [])
    interfaces_to_run.extend(holders_group)

if args.interface:
    # 指定接口
    interfaces_to_run.append(args.interface)

if args.group:
    # 指定组
    groups = config_loader.global_config.get('groups', {})
    if args.group in groups:
        interfaces_to_run.extend(groups[args.group])
    else:
        logger.error(f"Group '{args.group}' not found")
        return 1

# 如果没有指定任何参数，使用默认行为
if not interfaces_to_run:
    # 默认运行所有可用接口（可根据积分限制过滤）
    available_interfaces = config_loader.get_available_interfaces()
    # 过滤掉ts_code依赖的接口和pro_bar
    interfaces_to_run = [iface for iface in available_interfaces if iface not in ['stk_rewards', 'top10_holders', 'pledge_detail', 'fina_audit', 'pro_bar']]

logger.info(f"Interfaces to run: {interfaces_to_run}")
```

## 改动说明

### 主要改动

1. **从互斥模式改为累加模式**：将 `if-elif` 链改为独立的 `if` 语句，支持参数组合使用
2. **新增 `--tscode-historical` 的独立处理**：不再依赖 else 分支，而是直接指定要下载的接口
3. **默认行为过滤列表增加 `pro_bar`**：在默认下载时排除 `pro_bar` 接口

### 具体变化

| 改动点 | 修改前 | 修改后 |
|--------|--------|--------|
| 参数判断方式 | if-elif 互斥 | if 独立累加 |
| `--tscode-historical` 单独使用 | 下载所有接口 | 只下载4个接口 |
| `--tscode-historical --pro_bar_only` | 只下载 pro_bar（忽略 tscode-historical） | 下载4个接口 + pro_bar |
| 默认行为（无参数） | 排除4个接口 | 排除4个接口 + pro_bar |

## 参数组合效果表

| 命令 | 下载的接口 |
|------|-----------|
| `python main.py` | 所有接口，**排除** stk_rewards, top10_holders, pledge_detail, fina_audit, **pro_bar** |
| `--tscode-historical` | 只下载 stk_rewards, top10_holders, pledge_detail, fina_audit |
| `--pro_bar_only` | 只下载 pro_bar |
| `--tscode-historical --pro_bar_only` | 下载 stk_rewards, top10_holders, pledge_detail, fina_audit, **pro_bar** |
| `--holders-data` | 下载 holders 组的所有接口 |
| `--tscode-historical --holders-data` | 下载 stk_rewards, top10_holders, pledge_detail, fina_audit + holders 组 |
| `--interface daily` | 只下载 daily 接口 |
| `--group daily` | 下载 daily 组的所有接口 |

## 需要排除的接口列表

在默认下载模式下，以下接口会被排除：

1. **stk_rewards** - 股票回报（需要 ts_code）
2. **top10_holders** - 前十大股东（需要 ts_code）
3. **pledge_detail** - 质押明细（需要 ts_code）
4. **fina_audit** - 财务审计（需要 ts_code）
5. **pro_bar** - 专业行情（数据量大，单独下载）

## 实施步骤

1. 打开 `/home/quan/testdata/aspipe_v4/app4/main.py`
2. 找到约 332-353 行的参数判断逻辑
3. 将 `if-elif` 链替换为独立的 `if` 语句
4. 在默认行为的过滤列表中添加 `'pro_bar'`
5. 保存文件
6. 测试各种参数组合

## 测试建议

```bash
# 测试默认行为（应该排除5个接口）
python main.py --start_date 20250101 --end_date 20250101

# 测试 tscode-historical 单独使用（应该只下载4个接口）
python main.py --tscode-historical

# 测试 pro_bar_only 单独使用（应该只下载 pro_bar）
python main.py --pro_bar_only

# 测试参数组合（应该下载4个接口 + pro_bar）
python main.py --tscode-historical --pro_bar_only
```
