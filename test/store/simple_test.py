"""
简单测试修复后的功能
"""
import sys
import os
sys.path.insert(0, '/home/quan/testdata/aspipe_v4/app')

from tushare_api import TuShareDownloader

def test_imports():
    """测试导入是否正常"""
    print("测试导入是否正常...")
    try:
        downloader = TuShareDownloader()
        print("  ✓ TuShareDownloader导入成功")
        return True
    except Exception as e:
        print(f"  ✗ TuShareDownloader导入失败: {e}")
        return False

if __name__ == "__main__":
    print("开始简单验证...")

    if test_imports():
        print("\n✓ 基本导入测试通过！")
    else:
        print("\n✗ 基本导入测试失败！")