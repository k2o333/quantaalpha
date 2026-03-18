#!/usr/bin/env python
"""用于调试混合类型处理函数"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, '/home/quan/testdata/aspipe_v4')

from app4.core.schema_manager import SchemaManager

# 创建包含混合类型的数据
data = {
    'ts_code': ['000001.SZ', '000002.SZ', '000003.SZ'],
    'trade_date': ['20230101', '20230102', '20230103'],
    'close': ['10.5', '11.2', 12.8],  # 混合字符串和数值
    'volume': [1000000, '2000000', 1500000],  # 混合数值和字符串
    'name': ['平安银行', '万科A', '国农科技']
}

# 将字典转换为列表格式
list_data = []
for i in range(len(data['ts_code'])):
    row = {key: data[key][i] for key in data.keys()}
    list_data.append(row)

print("原始数据:")
for i, row in enumerate(list_data):
    print(f"  Row {i}: {row}")

# 测试_process_mixed_types方法
processed_data = SchemaManager._process_mixed_types(list_data)
print("\n处理后的数据:")
for i, row in enumerate(processed_data):
    print(f"  Row {i}: {row}")

# 测试创建DataFrame
try:
    schema_manager = SchemaManager()
    df = schema_manager.create_dataframe_safe(processed_data, 'daily')
    print(f"\nDataFrame创建成功，形状: {df.shape}")
    print("DataFrame列类型:")
    for col in df.columns:
        print(f"  {col}: {df[col].dtype}")
    print("\nDataFrame内容:")
    print(df)
except Exception as e:
    print(f"创建DataFrame失败: {e}")
    import traceback
    traceback.print_exc()