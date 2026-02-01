#!/usr/bin/env python3
"""
测试 disclosure_date 接口只传 ts_code 参数是否能获取单个股票的历史数据
"""
import os
import sys
import json

# 添加项目路径
sys.path.insert(0, '/home/quan/testdata/aspipe_v4')

from app4.core.config_loader import ConfigLoader
from app4.core.downloader import GenericDownloader

# 加载配置
config_loader = ConfigLoader('/home/quan/testdata/aspipe_v4/app4/config')
interface_config = config_loader.get_interface_config('disclosure_date')

print("=" * 60)
print("测试 disclosure_date 接口")
print("=" * 60)
print(f"\n接口配置:")
print(f"  - api_name: {interface_config['api_name']}")
print(f"  - pagination mode: {interface_config.get('pagination', {}).get('mode', 'N/A')}")
print(f"  - query_limit: {interface_config.get('permissions', {}).get('query_limit', 'N/A')}")

# 创建下载器
downloader = GenericDownloader(config_loader)

# 测试1: 只传 ts_code
print("\n" + "=" * 60)
print("测试1: 只传入 ts_code='000001.SZ'")
print("=" * 60)

params1 = {'ts_code': '000001.SZ'}
print(f"请求参数: {params1}")

try:
    result1 = downloader._make_request(interface_config, params1)
    print(f"返回记录数: {len(result1)}")
    if result1:
        print(f"\n前3条记录:")
        for i, record in enumerate(result1[:3]):
            print(f"  {i+1}. {record}")
    else:
        print("没有返回数据")
except Exception as e:
    print(f"错误: {e}")

# 测试2: 传 ts_code + start_date + end_date
print("\n" + "=" * 60)
print("测试2: 传入 ts_code='000001.SZ' + start_date='20180101' + end_date='20241231'")
print("=" * 60)

params2 = {
    'ts_code': '000001.SZ',
    'start_date': '20180101',
    'end_date': '20241231'
}
print(f"请求参数: {params2}")

try:
    result2 = downloader._make_request(interface_config, params2)
    print(f"返回记录数: {len(result2)}")
    if result2:
        print(f"\n前3条记录:")
        for i, record in enumerate(result2[:3]):
            print(f"  {i+1}. {record}")
    else:
        print("没有返回数据")
except Exception as e:
    print(f"错误: {e}")

# 测试3: 只传 end_date（按季度查询）
print("\n" + "=" * 60)
print("测试3: 只传入 end_date='20241231' (不按股票查询)")
print("=" * 60)

params3 = {'end_date': '20241231'}
print(f"请求参数: {params3}")

try:
    result3 = downloader._make_request(interface_config, params3)
    print(f"返回记录数: {len(result3)}")
    if result3:
        print(f"\n前3条记录:")
        for i, record in enumerate(result3[:3]):
            print(f"  {i+1}. {record}")
        if len(result3) >= 3000:
            print(f"\n⚠️ 警告: 返回数据量达到上限 {len(result3)} 条，可能数据不完整！")
    else:
        print("没有返回数据")
except Exception as e:
    print(f"错误: {e}")

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
