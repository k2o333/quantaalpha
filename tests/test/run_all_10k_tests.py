#!/usr/bin/env python3
"""
综合测试脚本：验证所有修改过的接口都能下载10000+条数据
"""
import sys
import os
import subprocess
import logging
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

def run_test_script(script_name):
    """
    运行单个测试脚本
    """
    print(f"\n{'='*60}")
    print(f"开始运行 {script_name}...")
    print(f"{'='*60}")

    try:
        # 使用指定的conda环境运行测试脚本
        result = subprocess.run([
            '/root/miniforge3/envs/get/bin/python',
            f'test/{script_name}'
        ], cwd='/home/quan/testdata/aspipe_v4', capture_output=True, text=True, timeout=300)

        print(result.stdout)
        if result.stderr:
            print("STDERR输出:")
            print(result.stderr)

        if result.returncode == 0:
            print(f"✅ {script_name} 运行成功")
            return True
        else:
            print(f"❌ {script_name} 运行失败，返回码: {result.returncode}")
            return False

    except subprocess.TimeoutExpired:
        print(f"❌ {script_name} 运行超时")
        return False
    except Exception as e:
        print(f"❌ 运行 {script_name} 时出错: {e}")
        return False

def main():
    """
    主测试函数：运行所有10k+数据下载测试
    """
    print("综合测试：验证所有修改接口的10000+条数据下载能力")
    print(f"测试开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 配置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # 要测试的脚本列表
    test_scripts = [
        'test_forecast_10k_plus.py',
        'test_express_10k_plus.py',
        'test_cyq_chips_10k_plus.py',
        'test_namechange_10k_plus.py'
    ]

    results = {}

    # 依次运行每个测试脚本
    for script in test_scripts:
        results[script] = run_test_script(script)

    # 输出最终结果
    print(f"\n{'='*60}")
    print("📊 综合测试结果汇总:")
    print(f"{'='*60}")

    passed_tests = 0
    total_tests = len(test_scripts)

    for script, success in results.items():
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{script}: {status}")
        if success:
            passed_tests += 1

    print(f"\n总体结果: {passed_tests}/{total_tests} 个测试通过")

    if passed_tests == total_tests:
        print("🎉 所有测试都通过了！所有修改的接口都能下载10000+条数据")
        return True
    else:
        print("⚠️ 部分测试未通过，请检查上述结果")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)