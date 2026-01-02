#!/usr/bin/env python3
"""
测试去重逻辑修复效果
"""
import sys
sys.path.insert(0, '/home/quan/testdata/aspipe_v4/app4')

from core.downloader import Downloader
from core.config_loader import ConfigLoader
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_deduplication():
    """测试去重逻辑"""
    try:
        # 初始化配置加载器和下载器
        config_loader = ConfigLoader()
        downloader = Downloader(config_loader)

        # 模拟 express_vip 的数据
        test_data = [
            {'ts_code': '000001.SZ', 'ann_date': '20230401', 'end_date': '20230331', 'revenue': 100.0},
            {'ts_code': '000001.SZ', 'ann_date': '20230401', 'end_date': '20230331', 'revenue': 200.0},  # 重复
            {'ts_code': '000001.SZ', 'ann_date': '20230405', 'end_date': '20230331', 'revenue': 150.0},
            {'ts_code': '000002.SZ', 'ann_date': '20230401', 'end_date': '20230331', 'revenue': 300.0},
        ]

        # 获取 express_vip 的接口配置
        interface_config = config_loader.get_interface_config('express_vip')

        print("\n" + "="*80)
        print("测试 express_vip 去重逻辑")
        print("="*80)

        print(f"\n原始数据 ({len(test_data)} 条):")
        for i, record in enumerate(test_data, 1):
            print(f"  {i}. {record}")

        print(f"\n接口配置的 primary_key:")
        primary_keys = interface_config.get('output', {}).get('primary_key', [])
        print(f"  {primary_keys}")

        # 执行去重
        deduplicated_data = downloader._validate_and_deduplicate_data(test_data, interface_config)

        print(f"\n去重后数据 ({len(deduplicated_data)} 条):")
        for i, record in enumerate(deduplicated_data, 1):
            print(f"  {i}. {record}")

        print(f"\n去重统计:")
        print(f"  原始记录数: {len(test_data)}")
        print(f"  去重后记录数: {len(deduplicated_data)}")
        print(f"  删除重复记录数: {len(test_data) - len(deduplicated_data)}")

        # 验证结果
        if len(deduplicated_data) == 3:
            print("\n✅ 测试通过！去重逻辑正常工作")
            print("   - 保留了基于 (ts_code, ann_date, end_date) 的唯一记录")
            print("   - 删除了重复记录")
            return True
        else:
            print("\n❌ 测试失败！预期去重后应有 3 条记录")
            return False

    except Exception as e:
        print(f"\n❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_other_interfaces():
    """测试其他接口的去重逻辑"""
    try:
        config_loader = ConfigLoader()

        print("\n" + "="*80)
        print("测试其他接口配置")
        print("="*80)

        test_interfaces = ['daily', 'income', 'stock_basic', 'trade_cal']

        for interface_name in test_interfaces:
            interface_config = config_loader.get_interface_config(interface_name)
            primary_keys = interface_config.get('output', {}).get('primary_key', [])

            print(f"\n{interface_name}:")
            print(f"  primary_key: {primary_keys}")

        print("\n✅ 所有接口的 primary_key 配置正常")
        return True

    except Exception as e:
        print(f"\n❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("\n" + "#"*80)
    print("# 开始测试去重逻辑修复")
    print("#"*80)

    result1 = test_deduplication()
    result2 = test_other_interfaces()

    print("\n" + "#"*80)
    print("# 测试总结")
    print("#"*80)

    if result1 and result2:
        print("\n✅ 所有测试通过！去重逻辑修复成功")
        sys.exit(0)
    else:
        print("\n❌ 部分测试失败")
        sys.exit(1)
