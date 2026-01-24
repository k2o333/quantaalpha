#!/usr/bin/env python3
"""
pro_bar接口缓存重复问题综合测试
按照推荐顺序执行所有测试用例
"""

import sys
import subprocess
import os

# 测试脚本列表（按推荐顺序）
test_scripts = [
    "test_interface_config.py",      # 测试7: 配置验证
    "test_cache_key_generation.py",  # 测试1 & 4: 缓存键生成和ts_code标准化
    "test_cache_storage_read.py",    # 测试2: 缓存存储与读取
    "test_cache_hit.py",             # 测试3: 缓存命中
    "test_smart_extraction.py",      # 测试5: 智能提取
    "test_historical_mode.py"        # 测试6: 历史模式
]

def run_tests():
    """运行所有测试"""
    print("=" * 80)
    print("开始执行pro_bar接口缓存重复问题综合测试")
    print("=" * 80)
    
    results = {}
    
    for i, script in enumerate(test_scripts, 1):
        script_path = f"/home/quan/testdata/aspipe_v4/test/pro_bar_cache_duplicate_test/{script}"
        print(f"\n[{i}/{len(test_scripts)}] 执行测试: {script}")
        print("-" * 60)
        
        try:
            # 执行测试脚本
            result = subprocess.run([sys.executable, script_path], 
                                  capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                # 检查输出中是否包含测试通过的信息
                if "通过" in result.stdout:
                    results[script] = True
                    print(f"✅ {script} 执行成功")
                else:
                    results[script] = False
                    print(f"❌ {script} 执行完成但未通过")
                    print(result.stdout)
            else:
                results[script] = False
                print(f"❌ {script} 执行失败")
                print("错误输出:", result.stderr)
                
        except subprocess.TimeoutExpired:
            results[script] = False
            print(f"❌ {script} 执行超时")
        except Exception as e:
            results[script] = False
            print(f"❌ {script} 执行出错: {str(e)}")
    
    # 输出测试结果汇总
    print("\n" + "=" * 80)
    print("测试结果汇总:")
    print("=" * 80)
    
    passed_count = sum(1 for result in results.values() if result)
    total_count = len(results)
    
    for script, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status}: {script}")
    
    print(f"\n总体结果: {passed_count}/{total_count} 个测试通过")
    
    if passed_count == total_count:
        print("\n🎉 所有测试通过！pro_bar接口缓存机制正常工作。")
    else:
        print(f"\n⚠️  {total_count - passed_count} 个测试失败，需要进一步调查问题。")
        
        # 根据失败的测试提供问题诊断
        failed_tests = [script for script, result in results.items() if not result]
        print("\n问题诊断建议:")
        for failed_test in failed_tests:
            if "test_interface_config" in failed_test:
                print("- 配置问题: 检查pro_bar接口的配置是否正确，特别是requires_tscode设置")
            elif "test_cache_key_generation" in failed_test:
                print("- 缓存键生成问题: 检查cache_key_generator.py中的键生成逻辑")
            elif "test_cache_storage_read" in failed_test:
                print("- 缓存存储/读取问题: 检查data_storage.py中的缓存读写功能")
            elif "test_cache_hit" in failed_test:
                print("- 缓存命中问题: 检查缓存有效性验证和命中逻辑")
            elif "test_smart_extraction" in failed_test:
                print("- 智能提取问题: 检查从全量数据中提取特定股票数据的功能")
            elif "test_historical_mode" in failed_test:
                print("- 历史模式问题: 检查下载调度器对pro_bar接口的处理")
    
    print("\n" + "=" * 80)
    return results

if __name__ == "__main__":
    run_tests()