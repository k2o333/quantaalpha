#!/usr/bin/env python3
"""
Tushare CYQ 接口使用示例
展示如何使用cyq_chips和cyq_perf接口
使用项目中的配置方式
"""

import requests
import os
import json
from datetime import datetime, timedelta


def get_cyq_data_example():
    """
    使用示例：获取筹码分布和筹码胜率数据
    使用项目中的配置方式
    """
    # 从环境变量获取token和代理
    token = os.getenv('TUSHARE_TOKEN')
    proxy_url = os.getenv('PROXY_URL', '')
    
    if not token:
        print("错误: 未找到TUSHARE_TOKEN环境变量")
        print("请确保已设置环境变量或检查配置文件")
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
    
    # 定义股票代码和日期范围
    ts_code = "000001.SZ"  # 平安银行
    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')
    
    print(f"\n正在获取 {ts_code} 从 {start_date} 到 {end_date} 的数据...")
    
    # 获取筹码分布数据 (cyq_chips)
    print("\n1. 获取筹码分布数据 (cyq_chips)...")
    try:
        req_params = {
            'api_name': 'cyq_chips',
            'token': token,
            'params': {
                'ts_code': ts_code,
                'start_date': start_date,
                'end_date': end_date
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
                
                print(f"   示例数据:\n{converted_data[:2]}")
        else:
            print(f"   ✗ 获取筹码分布数据失败: {result.get('msg', 'Unknown error')}")
    except Exception as e:
        print(f"   ✗ 获取筹码分布数据失败: {str(e)}")
    
    # 获取筹码及胜率数据 (cyq_perf)
    print("\n2. 获取筹码及胜率数据 (cyq_perf)...")
    try:
        req_params = {
            'api_name': 'cyq_perf',
            'token': token,
            'params': {
                'ts_code': ts_code,
                'start_date': start_date,
                'end_date': end_date
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
    print("Tushare CYQ 接口使用示例")
    print("使用项目中的配置方式（HTTP API调用）")
    print("="*60)
    
    get_cyq_data_example()
    
    print("\n" + "="*60)
    print("示例完成!")
    print("="*60)
    print("\n注意: 要成功运行此示例，您需要:")
    print("1. 有效的Tushare token")
    print("2. 足够的积分权限访问cyq_chips和cyq_perf接口")
    print("3. 网络连接正常")
    print("4. 如果使用代理，确保PROXY_URL设置正确")