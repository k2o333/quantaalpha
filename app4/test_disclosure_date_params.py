#!/usr/bin/env python3
"""
测试 disclosure_date 接口的不同日期参数
"""

import os
import sys
import requests
import json
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 加载环境变量
from dotenv import load_dotenv
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path)

def test_disclosure_date_param(param_name, param_value):
    """
    测试 disclosure_date 接口的特定参数
    
    Args:
        param_name: 参数名称
        param_value: 参数值
    """
    # 获取 Tushare Token
    token = os.getenv('TUSHARE_TOKEN')
    if not token:
        print("错误: 未找到 TUSHARE_TOKEN 环境变量")
        return None
        
    url = "http://api.tushare.pro/api"
    
    params = {
        param_name: param_value
    }
    
    req_params = {
        'api_name': 'disclosure_date',
        'token': token,
        'params': params,
        'fields': ''  # 返回默认字段
    }
    
    print(f"正在测试参数: {param_name} = {param_value}")
    
    try:
        response = requests.post(url, json=req_params, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        
        if result.get('code') != 0:
            print(f"  API 错误: {result.get('msg', 'Unknown error')}")
            return None
            
        data = result.get('data', {})
        items = data.get('items', [])
        fields = data.get('fields', [])
        
        print(f"  返回字段: {fields}")
        print(f"  返回记录数: {len(items)}")
        
        if items:
            print(f"  示例记录: {items[0] if len(items) > 0 else 'N/A'}")
            
        return len(items)
        
    except Exception as e:
        print(f"  请求错误: {str(e)}")
        return None

def main():
    print("开始测试 disclosure_date 接口的日期参数...")
    print("="*60)
    
    # 测试不同的日期参数
    test_cases = [
        ('start_date', '20230101'),  # 测试 start_date
        ('end_date', '20230101'),    # 测试 end_date  
        ('actual_date', '20230101'), # 测试 actual_date
        ('ann_date', '20230101'),    # 测试 ann_date
        ('pre_date', '20230101'),    # 测试 pre_date
    ]
    
    results = {}
    
    for param_name, param_value in test_cases:
        count = test_disclosure_date_param(param_name, param_value)
        results[param_name] = count
        print()
    
    print("="*60)
    print("测试结果汇总:")
    for param, count in results.items():
        status = "有效" if count is not None and count > 0 else "无效"
        print(f"  {param}: {count} 条记录 - {status}")
    
    print("\n建议使用的日期锚点参数:")
    valid_params = [(p, c) for p, c in results.items() if c is not None and c > 0]
    if valid_params:
        # 优先考虑 start_date 和 end_date，因为它们更适合日期范围查询
        preferred_order = ['start_date', 'end_date', 'actual_date', 'ann_date', 'pre_date']
        sorted_valid = sorted(valid_params, key=lambda x: preferred_order.index(x[0]))
        
        for param, count in sorted_valid:
            print(f"  - {param} (返回 {count} 条记录)")
    else:
        print("  没有找到有效的日期锚点参数")

if __name__ == "__main__":
    main()