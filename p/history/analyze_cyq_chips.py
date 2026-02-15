import pandas as pd
import pyarrow.parquet as pq

# 文件路径
file_path = '/home/quan/testdata/aspipe_v4/data/cyq_chips/cyq_chips_20230224_20231229_1770705029381_918881cb.parquet'

print(f"分析文件: {file_path}")
print("=" * 60)

# 读取Parquet文件
table = pq.read_table(file_path)
df = table.to_pandas()

print(f"数据行数: {len(df)}")
print(f"数据列数: {len(df.columns)}")
print(f"\n列名:")
for col in df.columns:
    print(f"- {col}")

print(f"\n数据类型:")
print(df.dtypes)

print(f"\n前5行数据:")
print(df.head())

print(f"\n股票代码数量: {df['ts_code'].nunique()}")
print(f"股票代码列表:")
stock_codes = df['ts_code'].unique()
for code in stock_codes[:10]:  # 只显示前10个
    print(f"- {code}")
if len(stock_codes) > 10:
    print(f"... 等{len(stock_codes) - 10}个股票")

print(f"\n时间范围:")
if 'trade_date' in df.columns:
    df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')
    print(f"最早日期: {df['trade_date'].min()}")
    print(f"最晚日期: {df['trade_date'].max()}")
    print(f"日期覆盖天数: {(df['trade_date'].max() - df['trade_date'].min()).days + 1}天")

print(f"\n各列数据统计:")
print(df.describe())

print(f"\n数据完整性检查:")
print(df.isnull().sum())
