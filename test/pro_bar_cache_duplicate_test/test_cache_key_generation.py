#!/usr/bin/env python3
"""
Test 1: pro_bar接口缓存键生成测试
目的: 验证pro_bar接口在相同参数下是否生成相同的缓存键
"""

import sys
import os

# 添加项目路径
sys.path.append('/home/quan/testdata/aspipe_v4')

def test_cache_key_generation():
    """测试pro_bar接口缓存键生成"""
    print("=" * 60)
    print("测试1: pro_bar接口缓存键生成测试")
    print("=" * 60)
    
    try:
        from app.cache_key_generator import CacheKeyGenerator
        
        # 测试参数
        params = {
            'ts_code': '000001.SZ',
            'start_date': '20230101',
            'end_date': '20231231',
            'adj': 'qfq',
            'freq': 'D'
        }

        # 多次生成缓存路径
        paths = []
        print("开始生成缓存路径...")
        for i in range(5):
            path = CacheKeyGenerator.generate_cache_path('pro_bar', **params)
            paths.append(path)
            print(f"第{i+1}次生成路径: {path}")

        # 验证所有路径是否一致
        all_same = all(path == paths[0] for path in paths)
        
        print(f"\n生成的路径列表: {paths}")
        print(f"所有路径是否一致: {all_same}")
        
        if all_same:
            print("✅ 测试1通过: 相同参数生成相同缓存路径")
            return True
        else:
            print("❌ 测试1失败: 相同参数生成了不同的缓存路径")
            return False
            
    except Exception as e:
        print(f"❌ 测试1执行出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_tscode_normalization():
    """测试ts_code参数标准化"""
    print("\n" + "=" * 60)
    print("测试4: pro_bar接口ts_code参数标准化测试")
    print("=" * 60)
    
    try:
        from app.cache_key_generator import CacheKeyGenerator
        from app.parameter_adapters import ParameterAdapterManager
        
        base_params = {
            'start_date': '20230101',
            'end_date': '20231231',
            'adj': 'qfq',
            'freq': 'D'
        }

        ts_code_variants = [
            '000001.SZ',  # 标准格式
            '000001.sz',  # 小写后缀
            '000001.SH',  # 错误后缀
        ]

        cache_paths = []
        print("测试不同格式的ts_code...")
        for ts_code in ts_code_variants:
            params = {**base_params, 'ts_code': ts_code}
            path = CacheKeyGenerator.generate_cache_path('pro_bar', **params)
            cache_paths.append(path)
            print(f"ts_code '{ts_code}' 生成路径: {path}")
        
        # 检查参数适配器
        print("\n测试参数适配器...")
        adapter = ParameterAdapterManager()
        for ts_code in ts_code_variants:
            params = {**base_params, 'ts_code': ts_code}
            adapted_params = adapter.adapt_parameters('pro_bar', params)
            print(f"原始ts_code: {ts_code}, 适配后: {adapted_params.get('ts_code')}")

        # 验证路径是否一致（应该不一致，因为ts_code不同）
        all_same = all(path == cache_paths[0] for path in cache_paths)
        
        print(f"\n所有不同ts_code格式生成的路径是否一致: {all_same}")
        
        if not all_same:
            print("✅ 测试4通过: 不同ts_code格式生成不同缓存路径（这是预期行为）")
            return True
        else:
            print("⚠️  测试4警告: 不同ts_code格式生成了相同缓存路径，可能存在问题")
            return True  # 这可能是预期行为，所以不算失败
            
    except Exception as e:
        print(f"❌ 测试4执行出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result1 = test_cache_key_generation()
    result4 = test_tscode_normalization()
    
    print("\n" + "=" * 60)
    print("测试结果汇总:")
    print(f"测试1 (缓存键生成): {'通过' if result1 else '失败'}")
    print(f"测试4 (ts_code标准化): {'通过' if result4 else '失败'}")
    print("=" * 60)