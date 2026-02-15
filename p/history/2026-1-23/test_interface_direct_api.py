#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试接口是否可以通过只传递股票代码参数来一次性返回历史所有该股票记录
此版本绕过分页逻辑，直接调用API
"""

import sys
import os
import requests
import json
import random
import time
from datetime import datetime
from typing import Dict, Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app4'))

from app4.core.config_loader import ConfigLoader


def direct_api_call(interface_config: Dict, params: Dict, global_config: Dict):
    """
    直接调用API，绕过分页逻辑
    """
    # 读取重试配置
    req_config = global_config.get('request', {})
    
    # 获取 API URL，优先使用代理 URL
    import os
    proxy_url = os.getenv('PROXY_URL', '')
    tushare_config = global_config.get('tushare', {})
    if proxy_url:
        api_url = proxy_url
    else:
        api_url = tushare_config.get('api_url', 'http://api.tushare.pro/api')

    # 在没有指定额外路径的情况下，使用 /api 作为默认路径
    request_config = interface_config.get('request', {})
    extra_path = request_config.get('extra_path', '')
    if extra_path:
        api_url += extra_path
    elif not api_url.endswith('/api') and not api_url.endswith('/dataapi'):
        if api_url.endswith('/'):
            api_url += 'api'
        else:
            api_url += '/api'

    # 添加 token
    token_placeholder = tushare_config.get('token', '')
    if '${TUSHARE_TOKEN}' in token_placeholder:
        token = os.getenv('TUSHARE_TOKEN', '')
    else:
        token = token_placeholder

    # 获取接口配置中的 fields
    config_fields = interface_config.get('fields', [])

    if config_fields:
        # 如果配置了 fields，传递所有配置的字段
        req_params = {
            'api_name': interface_config['api_name'],
            'token': token,
            'params': params,
            'fields': ','.join(config_fields)
        }
    else:
        # 如果没有配置 fields，返回默认字段
        req_params = {
            'api_name': interface_config['api_name'],
            'token': token,
            'params': params,
            'fields': ''  # 空字符串，返回默认字段
        }

    # 随机延迟，错开多个线程的请求时刻
    time.sleep(random.uniform(
        req_config.get('jitter_min', 0.1),
        req_config.get('jitter_max', 0.5)
    ))

    method = request_config.get('method', 'POST')
    timeout_val = request_config.get('timeout', 60)
    timeout = (10, timeout_val)

    print(f"Making {method} request to {api_url}")
    print(f"Request params: {params}")

    try:
        if method.upper() == 'POST':
            response = requests.post(api_url, json=req_params, timeout=timeout)
        else:
            response = requests.get(api_url, json=req_params, timeout=timeout)

        response.raise_for_status()
        result = response.json()

        # 检查 API 返回是否成功
        if result.get('code') != 0:
            msg = result.get('msg', '')
            print(f"API error: {msg}")
            return None

        # 数据转换逻辑
        fields = result.get('data', {}).get('fields', [])
        items = result.get('data', {}).get('items', [])

        print(f"API returned {len(fields)} fields")
        print(f"API returned {len(items)} items")
        if len(fields) < 50:  # 如果字段少，全部显示
            print(f"Returned fields: {fields}")
        else:
            print(f"First 10 fields: {fields[:10]}")
            print(f"Last 10 fields: {fields[-10:]}")

        converted_data = []
        for item in items:
            row_dict = {}
            for i, field_name in enumerate(fields):
                if i < len(item):
                    field_name = str(field_name) if field_name is not None else f"field_{i}"
                    row_dict[field_name] = item[i]
            converted_data.append(row_dict)

        return converted_data

    except (requests.RequestException, json.JSONDecodeError) as e:
        print(f"Request error: {str(e)}")
        return None
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return None


def test_interface_with_stock_code_only(interface_name: str, ts_code: str = "000001.SZ"):
    """
    测试接口是否可以通过只传递股票代码参数来一次性返回历史所有该股票记录
    
    Args:
        interface_name: 接口名称
        ts_code: 股票代码，默认为平安银行
    """
    print(f"\n{'='*60}")
    print(f"Testing interface: {interface_name}")
    print(f"Stock code: {ts_code}")
    
    try:
        # 初始化配置加载器
        config_loader = ConfigLoader("./app4/config")
        
        # 获取接口配置
        interface_config = config_loader.get_interface_config(interface_name)
        print(f"Interface config loaded successfully")
        
        # 获取全局配置
        global_config = config_loader.get_global_config()
        
        # 根据接口配置确定是否需要额外的日期参数
        parameter_config = interface_config.get('parameters', {})
        
        # 构建请求参数 - 只包含股票代码
        params = {
            'ts_code': ts_code
        }
        
        # 检查接口是否需要日期锚定参数
        date_anchor_param = None
        for param_name, param_def in parameter_config.items():
            if param_def.get('is_date_anchor', False):
                date_anchor_param = param_name
                break
        
        # 如果接口有日期锚定参数，我们可能需要提供一个宽泛的时间范围
        if date_anchor_param:
            print(f"Interface has date anchor parameter: {date_anchor_param}")
            # 对于日期锚定参数，我们可以尝试不设置它，或者设置一个很宽泛的范围
            # 有些接口可能只需要股票代码就能返回所有历史数据
            print(f"Date anchor parameter '{date_anchor_param}' detected, but we'll try with just stock code")
        else:
            print("No date anchor parameter detected")
        
        print(f"Making direct API call with params: {params}")
        
        # 直接调用API
        result = direct_api_call(interface_config, params, global_config)
        
        if result is not None:
            print(f"✓ Request successful")
            print(f"  Records returned: {len(result)}")
            
            if result:
                print(f"  Sample record keys: {list(result[0].keys())}")
                
                # 检查是否包含预期的日期字段
                date_field_mapping = {
                    'disclosure_date': 'end_date',
                    'top10_holders': 'end_date',  # period is the query param, but end_date is in data
                    'dividend': 'ann_date',
                    'pledge_stat': 'end_date',
                    'stk_rewards': 'end_date'
                }
                
                expected_date_field = date_field_mapping.get(interface_name)
                if expected_date_field and expected_date_field in result[0]:
                    print(f"  Date field '{expected_date_field}' present: {result[0][expected_date_field]}")
                    
                    # 检查是否有历史数据（最早的日期）
                    if len(result) > 1:
                        dates = [record.get(expected_date_field) for record in result if record.get(expected_date_field)]
                        if dates:
                            earliest_date = min(dates)
                            latest_date = max(dates)
                            print(f"  Date range: {earliest_date} to {latest_date}")
                
                # 检查是否包含股票代码
                if 'ts_code' in result[0]:
                    print(f"  Stock code field present: {result[0]['ts_code']}")
                    
            # 总结：接口是否可以通过只传递股票代码参数来一次性返回历史所有该股票记录
            if len(result) > 0:
                print(f"  CONCLUSION: ✓ Interface CAN return historical data with only stock code")
            else:
                print(f"  CONCLUSION: ✗ Interface returned no data with only stock code")
        else:
            print(f"✗ Request failed - returned None")
            print(f"  CONCLUSION: ✗ Interface CANNOT return historical data with only stock code")
            
    except Exception as e:
        print(f"✗ Error occurred: {str(e)}")
        import traceback
        traceback.print_exc()
        print(f"  CONCLUSION: ✗ Interface CANNOT return historical data with only stock code")


def main():
    """主函数 - 测试所有指定的接口"""
    print("Testing interfaces with stock code only parameter")
    print("This script tests if the following interfaces can return all historical records for a stock with only the stock code parameter:")
    print("- disclosure_date")
    print("- top10_holders") 
    print("- dividend")
    print("- pledge_stat")
    print("- stk_rewards")
    
    # 测试的接口列表
    interfaces_to_test = [
        'disclosure_date',
        'top10_holders',
        'dividend', 
        'pledge_stat',
        'stk_rewards'
    ]
    
    # 使用一个示例股票代码进行测试
    sample_stock_code = "000001.SZ"  # 平安银行
    
    for interface in interfaces_to_test:
        test_interface_with_stock_code_only(interface, sample_stock_code)

    print("\n" + "="*60)
    print("SUMMARY:")
    print("Based on the test results, we can determine if each interface supports retrieving")
    print("all historical records for a stock with only the stock code parameter.")


if __name__ == "__main__":
    main()