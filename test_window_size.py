#!/usr/bin/env python3
"""
测试 stock_hsgt 接口的 window_size_days 功能
"""

import sys
import os
sys.path.insert(0, './app4')

from app4.core.pagination_executor import PaginationExecutor
from app4.core.pagination import PaginationContext
import yaml
from typing import Dict, Any, List, Optional, Callable

def mock_make_request(interface_config: Dict[str, Any], params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """模拟请求函数"""
    print(f"  Mock request called with params: {params}")
    
    # 模拟返回一些数据
    type_val = params.get('type', 'UNKNOWN')
    start_date = params.get('start_date', 'N/A')
    end_date = params.get('end_date', 'N/A')
    
    # 模拟返回一些数据记录
    mock_data = [
        {
            'ts_code': '000001.SZ',
            'trade_date': start_date,
            'type': type_val,
            'vol': 1000000,
            'amount': 20000000
        }
    ] if start_date != 'N/A' else []
    
    return mock_data

def mock_get_trade_calendar(start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """模拟获取交易日历"""
    print(f"  Mock getting trade calendar for {start_date} to {end_date}")
    
    # 模拟返回一些交易日
    from datetime import datetime, timedelta
    
    start = datetime.strptime(start_date, '%Y%m%d')
    end = datetime.strptime(end_date, '%Y%m%d')
    
    trade_days = []
    current = start
    day_count = 0
    
    while current <= end and day_count < 10:  # 限制返回10天以简化测试
        trade_day = {
            'cal_date': current.strftime('%Y%m%d'),
            'is_open': 1  # 表示是交易日
        }
        trade_days.append(trade_day)
        current += timedelta(days=1)
        day_count += 1
        
    return trade_days

def test_type_split_pagination():
    """测试 type_split 分页功能"""
    print("Testing type_split pagination with window_size_days...")
    
    # 加载配置
    with open('./app4/config/interfaces/stock_hsgt.yaml', 'r', encoding='utf-8') as f:
        interface_config = yaml.safe_load(f)
    
    print(f"Interface config loaded: {interface_config['name']}")
    print(f"Pagination config: {interface_config.get('pagination')}")
    
    # 创建分页上下文
    context = PaginationContext(interface_config=interface_config, force_download=False)
    
    # 创建分页执行器
    executor = PaginationExecutor()
    
    # 测试参数
    params = {
        'start_date': '20230101',
        'end_date': '20230110'
    }
    
    print(f"Test params: {params}")
    
    # 执行分页
    result = executor.execute_type_split_pagination(
        interface_config=interface_config,
        params=params,
        context=context,
        make_request_callback=mock_make_request,
        get_trade_calendar_callback=mock_get_trade_calendar
    )
    
    print(f"Result: Got {len(result)} records total")
    print("Test completed successfully!")
    
    return result

if __name__ == "__main__":
    test_type_split_pagination()