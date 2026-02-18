#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试不同报告期的 end_type 值
"""

import sys
import os
import requests
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))

from app4.core.config_loader import ConfigLoader


def direct_api_call(api_name: str, params: dict, config: dict):
    tushare_config = config.get('tushare', {})
    proxy_url = os.getenv('PROXY_URL', '')
    api_url = proxy_url if proxy_url else tushare_config.get('api_url', 'http://api.tushare.pro/api')
    
    if not api_url.endswith('/api'):
        api_url = api_url.rstrip('/') + '/api'
    
    token_placeholder = tushare_config.get('token', '')
    if '${TUSHARE_TOKEN}' in token_placeholder:
        token = os.getenv('TUSHARE_TOKEN', '')
    else:
        token = token_placeholder
    
    req_params = {
        'api_name': api_name,
        'token': token,
        'params': params,
        'fields': ''
    }
    
    try:
        response = requests.post(api_url, json=req_params, timeout=60)
        response.raise_for_status()
        result = response.json()
        
        if result.get('code') != 0:
            return None
        
        data = result.get('data', {})
        fields = data.get('fields', [])
        items = data.get('items', [])
        
        return {
            'fields': fields,
            'items': items,
            'count': len(items)
        }
        
    except Exception as e:
        return None


def main():
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
    config_path = os.path.join(project_root, 'app4/config')
    loader = ConfigLoader(config_path)
    config = loader.global_config
    
    test_periods = [
        ('20241231', '年报'),
        ('20240930', '三季报'),
        ('20240630', '半年报'),
        ('20240331', '一季报'),
    ]
    
    api_name = 'income_vip'
    
    print("="*70)
    print(f"测试不同报告期的 end_type 值 (接口: {api_name})")
    print("="*70)
    
    for period, period_desc in test_periods:
        result = direct_api_call(api_name, {'period': period}, config)
        
        if result and result['items']:
            fields = result['fields']
            items = result['items']
            
            if 'end_type' in fields:
                end_type_idx = fields.index('end_type')
                end_types = set()
                for item in items:
                    if len(item) > end_type_idx and item[end_type_idx] is not None:
                        end_types.add(item[end_type_idx])
                
                print(f"\n报告期: {period} ({period_desc})")
                print(f"   记录数: {result['count']}")
                print(f"   end_type 值: {end_types}")
            else:
                print(f"\n报告期: {period} ({period_desc})")
                print(f"   记录数: {result['count']}")
                print(f"   无 end_type 字段")
        else:
            print(f"\n报告期: {period} ({period_desc}) - 查询失败或无数据")
        
        time.sleep(0.3)
    
    print("\n" + "="*70)
    print("end_type 值含义推测:")
    print("  1 = 一季报")
    print("  2 = 半年报/中报")
    print("  3 = 三季报")
    print("  4 = 年报")
    print("="*70)


if __name__ == '__main__':
    main()
