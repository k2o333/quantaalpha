#!/bin/bash
# 测试 --update 增量更新模式
# 第一次：下载 20260210-20260212
# 第二次：下载 20260210-20260213（新增 1 天）

set -e

echo "============================================================================"
echo "测试 --update 增量更新模式"
echo "============================================================================"

# 清理现有数据
echo ""
echo "[准备] 清理现有数据..."
rm -rf /home/quan/testdata/aspipe_v4/data/moneyflow_dc

# 第一次下载
echo ""
echo "============================================================================"
echo "[第一次下载] 日期范围：20260210 - 20260212"
echo "============================================================================"
cd /home/quan/testdata/aspipe_v4
python app4/main.py --update --update-interface moneyflow_dc --start_date 20260210 --end_date 20260212 --log-level INFO

echo ""
echo "[统计] 第一次下载结果..."
python -c "
import polars as pl
df = pl.read_parquet('data/moneyflow_dc')
dates = sorted(df['trade_date'].unique().to_list())
print(f'记录数：{len(df)}')
print(f'交易日：{len(dates)} 天 - {dates}')
"

# 记录第一次下载后的文件列表
echo ""
echo "[统计] 数据文件:"
ls -la data/moneyflow_dc/

# 第二次下载（新增 1 天）
echo ""
echo "============================================================================"
echo "[第二次下载] 日期范围：20260210 - 20260213 (新增 1 天)"
echo "============================================================================"
python app4/main.py --update --update-interface moneyflow_dc --start_date 20260210 --end_date 20260213 --log-level INFO

echo ""
echo "[统计] 第二次下载结果..."
python -c "
import polars as pl
df = pl.read_parquet('data/moneyflow_dc')
dates = sorted(df['trade_date'].unique().to_list())
print(f'记录数：{len(df)}')
print(f'交易日：{len(dates)} 天 - {dates}')
"

# 记录第二次下载后的文件列表
echo ""
echo "[统计] 数据文件:"
ls -la data/moneyflow_dc/

echo ""
echo "============================================================================"
echo "测试完成"
echo "============================================================================"
