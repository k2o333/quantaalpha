#!/usr/bin/env python3
"""
测试修复后的TuShare API调用
"""

import sys
import os
import logging

# 添加项目路径
sys.path.insert(0, '/home/quan/testdata/aspipe_v4/app')

from tushare_api import TuShareDownloader

def setup_logging():
    """设置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def test_cyq_chips():
    """测试cyq_chips接口修复"""
    print("测试cyq_chips接口...")
    downloader = TuShareDownloader()

    try:
        # 测试使用ts_code参数
        result = downloader.download_cyq_chips(ts_code='000001.SZ', trade_date='20231101')
        print(f"cyq_chips下载结果: {len(result) if result is not None else 0} 条记录")
        return True
    except Exception as e:
        print(f"cyq_chips测试失败: {e}")
        return False

def test_broker_recommend():
    """测试broker_recommend接口修复"""
    print("测试broker_recommend接口...")
    downloader = TuShareDownloader()

    try:
        # 测试使用month参数
        result = downloader.download_broker_recommend(month='202311')
        print(f"broker_recommend下载结果: {len(result) if result is not None else 0} 条记录")
        return True
    except Exception as e:
        print(f"broker_recommend测试失败: {e}")
        return False

def test_paginated_downloads():
    """测试分页下载功能"""
    print("测试分页下载功能...")
    downloader = TuShareDownloader()

    try:
        # 测试cyq_chips分页下载
        result = downloader.download_cyq_chips_paginated(
            ts_code='000001.SZ',
            start_date='20231101',
            end_date='20231130'
        )
        print(f"cyq_chips分页下载结果: {len(result) if result is not None else 0} 条记录")
        return True
    except Exception as e:
        print(f"分页下载测试失败: {e}")
        return False

def main():
    """主测试函数"""
    setup_logging()

    print("开始测试修复后的TuShare API调用...")

    tests = [
        test_cyq_chips,
        test_broker_recommend,
        test_paginated_downloads
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"测试 {test.__name__} 发生异常: {e}")

    print(f"\n测试完成: {passed}/{total} 个测试通过")

    if passed == total:
        print("所有测试通过！修复成功。")
        return 0
    else:
        print("部分测试失败，请检查代码。")
        return 1

if __name__ == "__main__":
    sys.exit(main())