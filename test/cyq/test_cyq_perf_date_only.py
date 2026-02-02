#!/usr/bin/env python3
"""
测试cyq_perf接口是否可以仅使用日期参数
"""

import requests
import os
from datetime import datetime


def test_cyq_perf_with_date_only():
    """
    测试cyq_perf接口仅使用日期参数
    """
    # 从环境变量获取token和代理
    token = os.getenv('TUSHARE_TOKEN')
    proxy_url = os.getenv('PROXY_URL', '')
    
    if not token:
        print("错误: 未找到TUSHARE_TOKEN环境变量")
        return
    
    # 获取API URL
    api_url = proxy_url if proxy_url else 'http://api.tushare.pro'
    if not api_url.endswith('/api') and not api_url.endswith('/dataapi'):
        if api_url.endswith('/'):
            api_url += 'api'
        else:
            api_url += '/api'
    
    print(f"API URL: {api_url}")
    print(f"Token前缀: {token[:10]}..." if len(token) > 10 else f"Token: {token}")
    
    # 获取今天的日期
    today = datetime.now().strftime('%Y%m%d')
    
    print(f"\n正在测试cyq_perf接口，仅使用日期参数: {today}")
    
    # 测试cyq_perf接口，仅使用日期参数
    try:
        req_params = {
            'api_name': 'cyq_perf',
            'token': token,
            'params': {
                'trade_date': today  # 仅使用日期参数
            },
            'fields': ''
        }
        
        response = requests.post(api_url, json=req_params, timeout=60)
        response.raise_for_status()
        result = response.json()
        
        if result.get('code') == 0:
            fields = result.get('data', {}).get('fields', [])
            items = result.get('data', {}).get('items', [])
            
            print(f"   ✓ 成功获取 {len(items)} 条筹码及胜率数据")
            print(f"   数据列: {fields}")
            
            if items:
                # 转换数据格式
                converted_data = []
                for item in items:
                    row_dict = {}
                    for i, field_name in enumerate(fields):
                        if i < len(item):
                            field_name = str(field_name) if field_name is not None else f"field_{i}"
                            row_dict[field_name] = item[i]
                    converted_data.append(row_dict)
                
                print(f"   示例数据:\n{converted_data[:2]}")
        else:
            print(f"   ✗ 获取筹码及胜率数据失败: {result.get('msg', 'Unknown error')}")
            
    except Exception as e:
        print(f"   ✗ 获取筹码及胜率数据失败: {str(e)}")


def test_cyq_perf_with_date_range():
    """
    测试cyq_perf接口使用日期范围参数
    """
    # 从环境变量获取token和代理
    token = os.getenv('TUSHARE_TOKEN')
    proxy_url = os.getenv('PROXY_URL', '')
    
    if not token:
        print("错误: 未找到TUSHARE_TOKEN环境变量")
        return
    
    # 获取API URL
    api_url = proxy_url if proxy_url else 'http://api.tushare.pro'
    if not api_url.endswith('/api') and not api_url.endswith('/dataapi'):
        if api_url.endswith('/'):
            api_url += 'api'
        else:
            api_url += '/api'
    
    # 获取今天的日期
    today = datetime.now().strftime('%Y%m%d')
    # 一个月前的日期
    from datetime import timedelta
    start_date = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')
    
    print(f"\n正在测试cyq_perf接口，使用日期范围参数: {start_date} 到 {today}")
    
    # 测试cyq_perf接口，使用日期范围参数
    try:
        req_params = {
            'api_name': 'cyq_perf',
            'token': token,
            'params': {
                'start_date': start_date,
                'end_date': today  # 使用日期范围参数
            },
            'fields': ''
        }
        
        response = requests.post(api_url, json=req_params, timeout=60)
        response.raise_for_status()
        result = response.json()
        
        if result.get('code') == 0:
            fields = result.get('data', {}).get('fields', [])
            items = result.get('data', {}).get('items', [])
            
            print(f"   ✓ 成功获取 {len(items)} 条筹码及胜率数据")
            print(f"   数据列: {fields}")
            
            if items:
                # 转换数据格式
                converted_data = []
                for item in items:
                    row_dict = {}
                    for i, field_name in enumerate(fields):
                        if i < len(item):
                            field_name = str(field_name) if field_name is not None else f"field_{i}"
                            row_dict[field_name] = item[i]
                    converted_data.append(row_dict)
                
                print(f"   示例数据:\n{converted_data[:2]}")
        else:
            print(f"   ✗ 获取筹码及胜率数据失败: {result.get('msg', 'Unknown error')}")
            
    except Exception as e:
        print(f"   ✗ 获取筹码及胜率数据失败: {str(e)}")


if __name__ == "__main__":
    print("="*60)
    print("Tushare cyq_perf 接口参数测试")
    print("="*60)
    
    test_cyq_perf_with_date_only()
    test_cyq_perf_with_date_range()
    
    print("\n" + "="*60)
    print("测试完成!")
    print("="*60)