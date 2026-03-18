#!/usr/bin/env python3
"""
测试cyq_chips接口使用股票代码返回的数据
"""

import requests
import os
from datetime import datetime, timedelta


def test_cyq_chips_with_stock_code():
    """
    测试cyq_chips接口使用股票代码
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
    
    # 使用平安银行作为示例股票
    ts_code = "000001.SZ"
    # 获取最近的日期
    recent_date = (datetime.now() - timedelta(days=5)).strftime('%Y%m%d')
    
    print(f"\n测试cyq_chips接口使用股票代码: {ts_code}")
    
    try:
        req_params = {
            'api_name': 'cyq_chips',
            'token': token,
            'params': {
                'ts_code': ts_code
            },
            'fields': ''
        }
        
        response = requests.post(api_url, json=req_params, timeout=60)
        response.raise_for_status()
        result = response.json()
        
        if result.get('code') == 0:
            fields = result.get('data', {}).get('fields', [])
            items = result.get('data', {}).get('items', [])
            
            print(f"   ✓ 成功获取 {len(items)} 条筹码分布数据")
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
                
                print(f"   示例数据 (前3条):\n{converted_data[:3]}")
        else:
            print(f"   ✗ 获取筹码分布数据失败: {result.get('msg', 'Unknown error')}")
            
    except Exception as e:
        print(f"   ✗ 获取筹码分布数据失败: {str(e)}")


def test_cyq_chips_with_stock_and_date():
    """
    测试cyq_chips接口使用股票代码和特定日期
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
    
    # 使用平安银行作为示例股票
    ts_code = "000001.SZ"
    # 获取最近的日期
    recent_date = (datetime.now() - timedelta(days=5)).strftime('%Y%m%d')
    
    print(f"\n测试cyq_chips接口使用股票代码和日期: {ts_code}, {recent_date}")
    
    try:
        req_params = {
            'api_name': 'cyq_chips',
            'token': token,
            'params': {
                'ts_code': ts_code,
                'trade_date': recent_date
            },
            'fields': ''
        }
        
        response = requests.post(api_url, json=req_params, timeout=60)
        response.raise_for_status()
        result = response.json()
        
        if result.get('code') == 0:
            fields = result.get('data', {}).get('fields', [])
            items = result.get('data', {}).get('items', [])
            
            print(f"   ✓ 成功获取 {len(items)} 条筹码分布数据")
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
                
                print(f"   示例数据 (前3条):\n{converted_data[:3]}")
        else:
            print(f"   ✗ 获取筹码分布数据失败: {result.get('msg', 'Unknown error')}")
            
    except Exception as e:
        print(f"   ✗ 获取筹码分布数据失败: {str(e)}")


def test_cyq_chips_with_date_only():
    """
    测试cyq_chips接口仅使用日期参数
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
    
    # 获取最近的日期
    recent_date = (datetime.now() - timedelta(days=5)).strftime('%Y%m%d')
    
    print(f"\n测试cyq_chips接口仅使用日期参数: {recent_date}")
    
    try:
        req_params = {
            'api_name': 'cyq_chips',
            'token': token,
            'params': {
                'trade_date': recent_date
            },
            'fields': ''
        }
        
        response = requests.post(api_url, json=req_params, timeout=60)
        response.raise_for_status()
        result = response.json()
        
        if result.get('code') == 0:
            fields = result.get('data', {}).get('fields', [])
            items = result.get('data', {}).get('items', [])
            
            print(f"   ✓ 成功获取 {len(items)} 条筹码分布数据")
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
                
                print(f"   示例数据 (前3条):\n{converted_data[:3]}")
        else:
            print(f"   ✗ 获取筹码分布数据失败: {result.get('msg', 'Unknown error')}")
            
    except Exception as e:
        print(f"   ✗ 获取筹码分布数据失败: {str(e)}")


if __name__ == "__main__":
    print("="*60)
    print("Tushare cyq_chips 接口参数测试")
    print("="*60)
    
    test_cyq_chips_with_stock_code()
    test_cyq_chips_with_stock_and_date()
    test_cyq_chips_with_date_only()
    
    print("\n" + "="*60)
    print("测试完成!")
    print("="*60)