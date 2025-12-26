#!/usr/bin/env python3
"""
Test 5: pro_bar接口智能缓存提取测试
目的: 验证从全量数据中提取特定股票数据的功能
"""

import sys
import os

# 添加项目路径
sys.path.append('/home/quan/testdata/aspipe_v4')

def test_smart_extraction():
    """测试pro_bar接口智能缓存提取"""
    print("=" * 60)
    print("测试5: pro_bar接口智能缓存提取测试")
    print("=" * 60)
    
    try:
        import pandas as pd
        from app.data_storage import (
            save_interface_data_to_cache,
            load_interface_cached_data
        )
        
        # 创建包含多个股票的全量数据
        full_data = pd.DataFrame({
            'ts_code': ['000001.SZ', '000002.SZ', '600000.SH', '000001.SZ', '000002.SZ', '600000.SH'] * 2,
            'trade_date': ['20230101', '20230101', '20230101', '20230102', '20230102', '20230102'] * 2,
            'close': [10.0, 20.0, 30.0, 10.1, 20.1, 30.1] * 2,
            'open': [9.9, 19.9, 29.9, 10.0, 20.0, 30.0] * 2
        })
        
        print(f"创建全量数据，共{len(full_data)}行")
        print(f"包含的股票代码: {full_data['ts_code'].unique()}")
        print(f"全量数据预览:\n{full_data.head(10)}")
        
        # 保存全量数据（不包含ts_code参数，即保存为通用数据）
        print("\n开始保存全量数据到缓存...")
        
        # 保存全量数据（不指定ts_code）
        save_params = {
            'start_date': '20230101',
            'end_date': '20230110'
        }
        
        save_result = save_interface_data_to_cache(full_data, 'pro_bar', **save_params)
        print(f"全量数据保存结果: {save_result}")
        
        # 尝试提取特定股票数据
        print("\n尝试提取特定股票数据 (000001.SZ)...")
        extract_params = {
            'ts_code': '000001.SZ',
            'start_date': '20230101',
            'end_date': '20230110'
        }
        
        extracted_data = load_interface_cached_data('pro_bar', **extract_params)
        
        if extracted_data is None:
            print("❌ 从缓存提取特定股票数据失败，返回None")
            return False
            
        print(f"提取到的数据条数: {len(extracted_data)}")
        if len(extracted_data) > 0:
            unique_codes = extracted_data['ts_code'].unique()
            print(f"提取到的股票代码: {unique_codes}")
            
            # 验证提取的数据是否只包含指定股票
            correct_stock = all(code == '000001.SZ' for code in unique_codes)
            print(f"提取的数据是否只包含目标股票: {correct_stock}")
            
            print(f"提取数据预览:\n{extracted_data.head()}")
        else:
            print("⚠️  提取到的数据为空")
        
        # 验证提取的数据是否正确
        expected_data = full_data[full_data['ts_code'] == '000001.SZ'].reset_index(drop=True)
        if extracted_data is not None and len(extracted_data) > 0:
            data_matches = expected_data.equals(extracted_data)
            print(f"提取的数据是否与预期一致: {data_matches}")
        
        print("-" * 60)
        if (extracted_data is not None and len(extracted_data) > 0 and 
            all(code == '000001.SZ' for code in extracted_data['ts_code'].unique())):
            print("✅ 测试5通过: 智能缓存提取功能正常")
            return True
        else:
            print("❌ 测试5失败: 智能缓存提取功能存在问题")
            return False
            
    except Exception as e:
        print(f"❌ 测试5执行出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_smart_extraction()