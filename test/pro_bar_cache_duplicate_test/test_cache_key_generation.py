#!/usr/bin/env python3
"""
测试pro_bar接口缓存键生成一致性
"""
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from app.cache_key_generator import CacheKeyGenerator


def test_cache_key_generation():
    """测试缓存键生成一致性"""
    print("开始测试pro_bar接口缓存键生成...")

    params = {
        'interface_name': 'pro_bar',
        'ts_code': '000001.SZ',
        'start_date': '20230101',
        'end_date': '20231231',
        'adj': 'qfq',
        'freq': 'D'
    }

    print(f"使用参数: {params}")

    # 多次生成缓存路径
    paths = []
    cache_keys = []
    for i in range(5):
        path = CacheKeyGenerator.generate_cache_path(**params)
        cache_key = CacheKeyGenerator.generate_cache_key(**params)
        paths.append(path)
        cache_keys.append(cache_key)
        print(f"第{i+1}次生成路径: {path}")
        print(f"第{i+1}次生成缓存键: {cache_key}")

    # 验证一致性
    all_paths_same = all(p == paths[0] for p in paths)
    all_keys_same = all(k == cache_keys[0] for k in cache_keys)

    print(f"所有缓存路径是否相同: {all_paths_same}")
    print(f"所有缓存键是否相同: {all_keys_same}")

    if not all_paths_same:
        print("ERROR: 缓存路径不一致!")
        return False
    if not all_keys_same:
        print("ERROR: 缓存键不一致!")
        return False

    print("缓存键生成测试通过!")
    return True


if __name__ == "__main__":
    test_cache_key_generation()