#!/usr/bin/env python3
"""测试--uno参数功能"""

import sys
import os
import subprocess
import argparse


def test_uno_help():
    """测试--uno参数帮助信息"""
    try:
        result = subprocess.run([sys.executable, '-m', 'app4.main', '--help'],
                              capture_output=True, text=True, timeout=10)
        assert result.returncode == 0
        assert '--uno' in result.stdout
        print("✓ --uno参数帮助信息测试通过")
        return True
    except Exception as e:
        print(f"✗ --uno参数帮助信息测试失败: {e}")
        return False


def test_uno_parsing():
    """测试--uno参数解析"""
    # 使用subprocess直接测试
    try:
        # 测试不带--uno参数
        result = subprocess.run([sys.executable, '-c', '''
import sys
sys.path.insert(0, ".")
from app4.main import _parse_args
import sys
sys.argv = ["", "--start_date", "20240101"]
args = _parse_args()
assert not args.uno
print("No --uno: OK")
        '''], capture_output=True, text=True, timeout=10)

        if "No --uno: OK" in result.stdout:
            print("✓ 不带--uno参数解析测试通过")
        else:
            print(f"✗ 不带--uno参数测试失败: {result.stderr}")
            return False

        # 测试带--uno参数
        result = subprocess.run([sys.executable, '-c', '''
import sys
sys.path.insert(0, ".")
from app4.main import _parse_args
import sys
sys.argv = ["", "--uno"]
args = _parse_args()
assert args.uno
print("With --uno: OK")
        '''], capture_output=True, text=True, timeout=10)

        if "With --uno: OK" in result.stdout:
            print("✓ 带--uno参数解析测试通过")
        else:
            print(f"✗ 带--uno参数测试失败: {result.stderr}")
            return False

        return True
    except Exception as e:
        print(f"✗ --uno参数解析测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("开始测试--uno参数功能...")

    tests = [
        test_uno_help,
        test_uno_parsing
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"✗ 测试 {test.__name__} 失败: {e}")

    print(f"\n测试结果: {passed}/{total} 通过")

    if passed == total:
        print("所有--uno参数功能测试通过!")
        return 0
    else:
        print("部分测试失败!")
        return 1


if __name__ == "__main__":
    exit(main())