#!/usr/bin/env python3
"""
分析cyq_chips接口返回数据的时间范围
"""

import requests
import os
from datetime import datetime


def analyze_cyq_chips_date_range():
    """
    分析cyq_chips接口返回数据的时间范围
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
    
    print(f"\n获取股票 {ts_code} 的筹码分布数据时间范围")
    
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
            
            if items and len(items) > 0:
                # 转换数据格式并提取日期
                converted_data = []
                for item in items:
                    row_dict = {}
                    for i, field_name in enumerate(fields):
                        if i < len(item):
                            field_name = str(field_name) if field_name is not None else f"field_{i}"
                            row_dict[field_name] = item[i]
                    converted_data.append(row_dict)
                
                # 提取所有交易日期
                trade_dates = [data['trade_date'] for data in converted_data if 'trade_date' in data]
                
                if trade_dates:
                    # 找到最早的日期和最晚的日期
                    earliest_date = min(trade_dates)
                    latest_date = max(trade_dates)
                    
                    print(f"\n数据时间范围:")
                    print(f"   最早日期: {earliest_date} ({datetime.strptime(earliest_date, '%Y%m%d').strftime('%Y年%m月%d日')})")
                    print(f"   最晚日期: {latest_date} ({datetime.strptime(latest_date, '%Y%m%d').strftime('%Y年%m月%d日')})")
                    
                    # 统计不同日期的数据量
                    from collections import Counter
                    date_counts = Counter(trade_dates)
                    
                    print(f"\n按日期统计:")
                    print(f"   不同交易日总数: {len(date_counts)}")
                    print(f"   平均每个交易日数据条数: {len(items) / len(date_counts):.1f}")
                    
                    # 显示数据最多的几个日期
                    most_common_dates = date_counts.most_common(5)
                    print(f"   数据最多的5个日期:")
                    for date, count in most_common_dates:
                        print(f"     {date} ({datetime.strptime(date, '%Y%m%d').strftime('%m月%d日')}): {count}条")
                        
                    # 显示最早的几个日期
                    sorted_dates = sorted(date_counts.keys())
                    print(f"   最早的5个日期:")
                    for date in sorted_dates[:5]:
                        print(f"     {date} ({datetime.strptime(date, '%Y%m%d').strftime('%m月%d日')}): {date_counts[date]}条")
                        
                    # 显示最晚的几个日期
                    print(f"   最晚的5个日期:")
                    for date in sorted_dates[-5:]:
                        print(f"     {date} ({datetime.strptime(date, '%Y%m%d').strftime('%m月%d日')}): {date_counts[date]}条")
                else:
                    print("   未找到trade_date字段")
            else:
                print("   没有返回数据")
        else:
            print(f"   ✗ 获取筹码分布数据失败: {result.get('msg', 'Unknown error')}")
            
    except Exception as e:
        print(f"   ✗ 获取筹码分布数据失败: {str(e)}")


if __name__ == "__main__":
    print("="*60)
    print("Tushare cyq_chips 数据时间范围分析")
    print("="*60)
    
    analyze_cyq_chips_date_range()
    
    print("\n" + "="*60)
    print("分析完成!")
    print("="*60)