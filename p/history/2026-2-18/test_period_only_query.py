#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 Type B 接口是否可以只通过 period 参数获取所有股票数据
"""

import sys
import os
import requests
import json
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
    
    print(f"\n{'='*60}")
    print(f"API: {api_name}")
    print(f"Params: {params}")
    print(f"URL: {api_url}")
    
    try:
        response = requests.post(api_url, json=req_params, timeout=60)
        response.raise_for_status()
        result = response.json()
        
        if result.get('code') != 0:
            print(f"❌ API Error: {result.get('msg', 'Unknown error')}")
            return None
        
        data = result.get('data', {})
        fields = data.get('fields', [])
        items = data.get('items', [])
        
        print(f"✅ Success!")
        print(f"   Fields count: {len(fields)}")
        print(f"   Records count: {len(items)}")
        
        if items:
            print(f"   Fields: {fields[:10]}{'...' if len(fields) > 10 else ''}")
            print(f"   First 3 records:")
            for i, item in enumerate(items[:3]):
                print(f"      {item[:5]}{'...' if len(item) > 5 else ''}")
            
            if 'end_type' in fields:
                end_type_idx = fields.index('end_type')
                end_types = set()
                for item in items:
                    if len(item) > end_type_idx:
                        end_types.add(item[end_type_idx])
                print(f"   end_type values: {end_types}")
        
        return {
            'fields': fields,
            'items': items,
            'count': len(items)
        }
        
    except Exception as e:
        print(f"❌ Exception: {e}")
        return None


def main():
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
    config_path = os.path.join(project_root, 'app4/config')
    loader = ConfigLoader(config_path)
    config = loader.global_config
    
    type_b_interfaces = [
        ('income_vip', '利润表'),
        ('balancesheet_vip', '资产负债表'),
        ('cashflow_vip', '现金流量表'),
        ('fina_indicator_vip', '财务指标'),
        ('fina_audit', '财务审计'),
        ('fina_mainbz_vip', '主营业务'),
        ('forecast_vip', '业绩预告'),
        ('top10_floatholders', '十大流通股东'),
    ]
    
    test_period = '20240930'
    
    print("="*70)
    print(f"测试 Type B 接口 - 仅使用 period 参数获取所有股票数据")
    print(f"测试报告期: {test_period}")
    print("="*70)
    
    results = []
    
    for api_name, desc in type_b_interfaces:
        print(f"\n>>> 测试 {api_name} ({desc})")
        
        result = direct_api_call(api_name, {'period': test_period}, config)
        
        results.append({
            'api_name': api_name,
            'desc': desc,
            'success': result is not None,
            'count': result['count'] if result else 0
        })
        
        time.sleep(0.5)
    
    print("\n" + "="*70)
    print("测试结果汇总")
    print("="*70)
    print(f"{'接口名':<25} {'描述':<15} {'状态':<8} {'记录数':<10}")
    print("-"*70)
    
    for r in results:
        status = "✅ 成功" if r['success'] else "❌ 失败"
        print(f"{r['api_name']:<25} {r['desc']:<15} {status:<8} {r['count']:<10}")
    
    success_count = sum(1 for r in results if r['success'])
    print("-"*70)
    print(f"总计: {success_count}/{len(results)} 个接口成功")


if __name__ == '__main__':
    main()
