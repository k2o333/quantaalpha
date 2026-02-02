#!/usr/bin/env python3
"""
测试cyq_perf接口在最近10个交易日是否有数据
"""

import requests
import os
from datetime import datetime, timedelta


def get_recent_trade_dates(num_days=10):
    """
    获取最近的交易日列表
    """
    # 为了测试，我们使用最近的日期，实际应用中应查询交易日历
    trade_dates = []
    current_date = datetime.now()
    
    # 循环查找最近的交易日
    while len(trade_dates) < num_days:
        date_str = current_date.strftime('%Y%m%d')
        # 简单模拟，实际应查询交易日历
        # 这里我们只是获取最近的日期，包括周末
        trade_dates.append(date_str)
        current_date -= timedelta(days=1)
    
    return trade_dates


def test_cyq_perf_for_dates():
    """
    测试cyq_perf接口在最近10个交易日是否有数据
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
    
    # 获取最近10个交易日
    trade_dates = get_recent_trade_dates(10)
    
    print(f"\n正在测试最近10个交易日的cyq_perf数据: {trade_dates}")
    
    success_count = 0
    for trade_date in trade_dates:
        print(f"\n测试日期: {trade_date}")
        
        try:
            req_params = {
                'api_name': 'cyq_perf',
                'token': token,
                'params': {
                    'trade_date': trade_date  # 仅使用日期参数
                },
                'fields': ''
            }
            
            response = requests.post(api_url, json=req_params, timeout=60)
            response.raise_for_status()
            result = response.json()
            
            if result.get('code') == 0:
                fields = result.get('data', {}).get('fields', [])
                items = result.get('data', {}).get('items', [])
                
                if len(items) > 0:
                    print(f"   ✓ 成功获取 {len(items)} 条筹码及胜率数据")
                    success_count += 1
                    # 显示第一条数据的股票代码
                    if items and len(fields) > 0:
                        first_item = items[0]
                        # 找到ts_code字段的索引
                        ts_code_idx = -1
                        for i, field in enumerate(fields):
                            if field == 'ts_code':
                                ts_code_idx = i
                                break
                        if ts_code_idx != -1 and ts_code_idx < len(first_item):
                            print(f"     第一条数据股票代码: {first_item[ts_code_idx]}")
                else:
                    print(f"   - 无数据")
            else:
                print(f"   ✗ 获取数据失败: {result.get('msg', 'Unknown error')}")
                
        except Exception as e:
            print(f"   ✗ 获取数据失败: {str(e)}")
    
    print(f"\n总共 {len(trade_dates)} 个交易日中，有 {success_count} 个交易日有数据")


def test_with_sample_stock():
    """
    测试cyq_perf接口使用特定股票代码和日期
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
    
    print(f"\n测试使用股票代码和日期参数: {ts_code}, {recent_date}")
    
    try:
        req_params = {
            'api_name': 'cyq_perf',
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
    print("Tushare cyq_perf 接口日期测试")
    print("="*60)
    
    test_cyq_perf_for_dates()
    test_with_sample_stock()
    
    print("\n" + "="*60)
    print("测试完成!")
    print("="*60)