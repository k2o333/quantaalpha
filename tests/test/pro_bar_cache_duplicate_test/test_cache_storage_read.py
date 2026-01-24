#!/usr/bin/env python3
"""
Test 2: pro_bar接口缓存存储与读取测试
目的: 验证pro_bar接口数据是否能正确存储到缓存并被读取
"""

import sys
import os

# 添加项目路径
sys.path.append('/home/quan/testdata/aspipe_v4')

def test_cache_storage_read():
    """测试pro_bar接口缓存存储与读取"""
    print("=" * 60)
    print("测试2: pro_bar接口缓存存储与读取测试")
    print("=" * 60)
    
    try:
        import pandas as pd
        from app.data_storage import (
            save_interface_data_to_cache,
            load_interface_cached_data,
            get_interface_cache_path
        )
        
        # 创建测试数据
        test_data = pd.DataFrame({
            'ts_code': ['000001.SZ'] * 5,
            'trade_date': ['20230101', '20230102', '20230103', '20230104', '20230105'],
            'open': [10.0, 10.1, 10.2, 10.3, 10.4],
            'high': [10.5, 10.6, 10.7, 10.8, 10.9],
            'low': [9.9, 10.0, 10.1, 10.2, 10.3],
            'close': [10.4, 10.5, 10.6, 10.7, 10.8],
            'vol': [1000000, 1100000, 1200000, 1300000, 1400000]
        })
        
        print(f"创建测试数据，共{len(test_data)}行")
        print(f"测试数据预览:\n{test_data.head()}")
        
        # 测试参数
        params = {
            'ts_code': '000001.SZ',
            'start_date': '20230101',
            'end_date': '20231231',
            'adj': 'qfq',
            'freq': 'D'
        }

        # 保存数据到缓存
        print("\n开始保存数据到缓存...")
        save_result = save_interface_data_to_cache(test_data, 'pro_bar', **params)
        print(f"保存结果: {save_result}")
        
        # 获取缓存路径
        cache_path = get_interface_cache_path('pro_bar', **params)
        print(f"缓存路径: {cache_path}")
        
        # 验证缓存文件存在
        file_exists = os.path.exists(cache_path)
        print(f"文件是否存在: {file_exists}")
        
        if not file_exists:
            print("❌ 缓存文件未创建")
            return False
        
        # 获取文件大小
        file_size = os.path.getsize(cache_path) if file_exists else 0
        print(f"文件大小: {file_size} 字节")
        
        if file_size == 0:
            print("❌ 缓存文件为空")
            return False

        # 从缓存读取数据
        print("\n开始从缓存读取数据...")
        loaded_data = load_interface_cached_data('pro_bar', **params)
        
        if loaded_data is None:
            print("❌ 从缓存读取数据失败，返回None")
            return False
            
        print(f"读取数据条数: {len(loaded_data)}")
        
        # 验证数据一致性
        data_consistent = test_data.equals(loaded_data)
        print(f"数据是否一致: {data_consistent}")
        
        if not data_consistent:
            print("原始数据预览:")
            print(test_data)
            print("加载数据预览:")
            print(loaded_data)
        
        print("-" * 60)
        if save_result and file_exists and file_size > 0 and loaded_data is not None and data_consistent:
            print("✅ 测试2通过: pro_bar接口缓存存储与读取功能正常")
            return True
        else:
            print("❌ 测试2失败: pro_bar接口缓存存储与读取存在问题")
            return False
            
    except Exception as e:
        print(f"❌ 测试2执行出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_cache_storage_read()