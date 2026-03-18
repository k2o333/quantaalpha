# Primary Key 有效性验证测试

本目录包含用于测试16个接口 primary key 完整性的脚本和数据。

## 测试目标

验证以下16个接口的YAML配置中，`primary_key` 是否能唯一标识记录：

```
balancesheet_vip, cashflow_vip, disclosure_date, dividend, express_vip,
fina_audit, fina_indicator_vip, fina_mainbz_vip, forecast_vip, income_vip,
pledge_detail, pledge_stat, stk_factor_pro, stk_rewards, top10_floatholders, top10_holders
```

## 核心测试原理

```
下载数据 → 按primary key分组 → 检查组内非主键字段是否一致
```

**判定标准**：
- 如果重复组内所有非主键字段完全相同 → 正常重复，可安全去重
- 如果重复组内存在任何非主键字段不同 → **问题！** primary key 定义不完整

## 目录结构

```
test/prim/
├── README.md                 # 本文件
├── run_test.sh              # 一键运行脚本（下载+测试）
├── download_data.py         # 数据下载脚本
├── test_primary_key.py      # Primary key 测试脚本
├── data/                    # 下载的数据资产（parquet文件）
└── reports/                 # 测试报告
```

## 使用方法

### 1. 一键运行（推荐）

```bash
# 一键运行（下载+测试，默认只测试 000002.SZ 的数据）
cd /home/quan/testdata/aspipe_v4/test/prim
./run_test.sh
```

### 2. 只下载数据

```bash
./run_test.sh --no-test
```

### 3. 只运行测试（数据已下载）

```bash
./run_test.sh --no-download
```

### 4. 测试单个接口

```bash
# 下载并测试单个接口
./run_test.sh --interface balancesheet_vip

# 指定股票代码
./run_test.sh --interface balancesheet_vip --ts_code 000001.SZ
```

### 5. 使用Python脚本直接运行

```bash
# 下载所有接口数据
cd /home/quan/testdata/aspipe_v4
python test/prim/download_data.py

# 下载单个接口
python test/prim/download_data.py --interface balancesheet_vip

# 运行测试
python test/prim/test_primary_key.py

# 测试单个接口
python test/prim/test_primary_key.py --interface balancesheet_vip
```

## 数据获取策略

脚本复用项目原有代码（[`app4/core/downloader.py`](../../app4/core/downloader.py) 和 [`app4/core/config_loader.py`](../../app4/core/config_loader.py)）：

| 接口模式 | 获取策略 |
|---------|---------|
| stock_loop | 只下载 000002.SZ 一只股票的全部历史数据 |
| date_range | 最近365天数据 |
| offset | 前10000条数据 |

## 测试报告

测试完成后，报告将生成在 `reports/` 目录：

- `primary_key_test_report_YYYYMMDD_HHMMSS.json` - 详细JSON报告
- `primary_key_test_report_YYYYMMDD_HHMMSS.md` - Markdown摘要报告

报告包含：
1. 汇总统计（通过/失败/错误）
2. 失败接口的详细问题分析
3. 问题样本（primary key值、冲突字段、不同值）
4. 修复建议（需要添加到primary_key的字段）

## 配置文件

测试脚本读取接口配置：
- 配置文件位置: [`app4/config/interfaces/*.yaml`](../../app4/config/interfaces/)
- 每个配置文件的 `output.primary_key` 字段定义了主键

## 注意事项

1. 数据下载需要有效的 `TUSHARE_TOKEN` 环境变量
2. 下载过程可能耗时较长（特别是stock_loop模式的接口）
3. 如果某接口无数据，可能是该股票没有相关数据，尝试更换 `--ts_code`
4. 测试结果是基于下载的数据样本，建议用不同股票代码多次测试验证

## 修复建议示例

如果测试发现 `balancesheet_vip` 接口在 `ts_code`, `ann_date`, `end_date` 相同的情况下，`update_flag` 和 `report_type` 有不同值，则建议在配置中添加这些字段：

```yaml
output:
  primary_key:
    - ts_code
    - ann_date
    - end_date
    - update_flag
    - report_type
```
