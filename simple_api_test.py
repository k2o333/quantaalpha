#!/usr/bin/env python3
"""
简单API测试 - 查看TuShare API返回的原始数据格式
"""
import os
import sys

# 加载环境变量
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# 获取token
token = os.environ.get('TUSHARE_TOKEN')
if not token:
    print("错误: 未找到TUSHARE_TOKEN环境变量")
    sys.exit(1)

print("正在测试TuShare API...")

try:
    import tushare as ts
    pro = ts.pro_api(token)
    
    # 调用daily接口获取一天的数据
    print("\n=== 调用 daily 接口 ===")
    df = pro.daily(trade_date='20240101', limit=10)
    print(f"返回数据形状: {df.shape}")
    print("数据类型:")
    for col in df.columns:
        print(f"  {col}: {df[col].dtype}")
    print("\n前3行数据:")
    print(df.head(3))
    
    # 查看具体的数据类型
    print("\n=== 详细数据类型检查 ===")
    for i, (idx, row) in enumerate(df.head(3).iterrows()):
        print(f"\n第{i}行数据:")
        for col in df.columns:
            value = row[col]
            print(f"  {col}: {value} (type: {type(value).__name__})")
        if i >= 2:
            break
    
except ImportError:
    print("错误: 未安装tushare包")
except Exception as e:
    print(f"API调用失败: {e}")
