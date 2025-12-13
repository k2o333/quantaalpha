#!/usr/bin/env python3
"""
详细分析API调用和错误处理的测试脚本
"""
import sys
import os
import time
import logging

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.tushare_api import TuShareDownloader
from app.error_handler import ErrorHandler

def test_with_mock_api_call():
    """
    模拟API调用以测试错误处理
    """
    print("测试API调用和错误处理...")
    
    downloader = TuShareDownloader()
    
    # 测试正常速率限制
    print("\n1. 测试正常速率限制:")
    for i in range(3):
        start_time = time.time()
        print(f"  调用 {i+1} 开始 at {start_time:.2f}")
        downloader._advanced_rate_limit('stk_factor_pro')
        end_time = time.time()
        print(f"  调用 {i+1} 结束 at {end_time:.2f}, duration: {end_time-start_time:.3f}s")
    
    # 测试错误处理
    print("\n2. 测试错误处理机制:")
    
    # 测试频率限制错误
    print("  测试频率限制错误处理...")
    try:
        ErrorHandler.handle_api_error(Exception("freq limit exceeded"), "test context")
    except Exception:
        print("  频率限制错误处理完成 (已等待)")
    
    # 测试其他错误
    print("  测试其他类型错误...")
    try:
        ErrorHandler.handle_api_error(Exception("timeout error"), "test context")
    except Exception:
        print("  超时错误处理完成")
    
    print("\n错误处理测试完成")


def test_api_limits_and_timing():
    """
    详细测试API限制和计时
    """
    print("详细测试API限制和计时...")
    
    downloader = TuShareDownloader()
    
    # 获取API配置
    api_config = downloader.api_limits.get('stk_factor_pro', {'calls_per_minute': 30})
    expected_interval = 60.0 / api_config['calls_per_minute']
    print(f"  stk_factor_pro 限制: {api_config['calls_per_minute']} calls/min")
    print(f"  期望间隔: {expected_interval:.3f}s")
    
    # 测试多次调用并记录详细时间
    print("\n  详细时间记录:")
    calls = []
    
    for i in range(5):
        real_time_start = time.time()
        perf_time_start = time.perf_counter()
        
        # 调用速率限制
        downloader._advanced_rate_limit('stk_factor_pro')
        
        perf_time_end = time.perf_counter()
        real_time_end = time.time()
        
        total_real_time = real_time_end - real_time_start
        actual_wait_time = perf_time_end - perf_time_start
        
        calls.append({
            'real_time': real_time_end,
            'total_real_time': total_real_time,
            'actual_wait_time': actual_wait_time
        })
        
        print(f"    调用 {i+1}: 等待 {actual_wait_time:.3f}s, 总时间 {total_real_time:.3f}s")
    
    # 计算真实间隔
    print(f"\n  真实调用间隔:")
    for i in range(1, len(calls)):
        interval = calls[i]['real_time'] - calls[i-1]['real_time']
        print(f"    调用 {i} -> {i+1}: {interval:.3f}s")
    
    print("\n详细计时测试完成")


def simulate_download_process():
    """
    模拟实际下载过程，看看完整的流程
    """
    print("模拟实际下载流程...")
    
    downloader = TuShareDownloader()
    
    print("\n模拟下载流程 (不实际调用API，只测试流程):")
    
    # 模拟下载调用流程
    for i in range(3):
        print(f"\n下载任务 {i+1}:")
        
        # 1. 准备参数
        print(f"  1. 准备参数...")
        
        # 2. 速率限制检查
        rate_start = time.time()
        downloader._advanced_rate_limit('stk_factor_pro')
        rate_end = time.time()
        print(f"  2. 速率限制完成 ({rate_end - rate_start:.3f}s)")
        
        # 3. 模拟API调用时间（这部分可能变化很大）
        api_start = time.time()
        # 模拟API响应时间
        print(f"  3. 模拟API调用...")
        time.sleep(0.1)  # 模拟实际API响应时间
        api_end = time.time()
        print(f"  4. API调用完成 ({api_end - api_start:.3f}s)")
        
        # 5. 数据处理
        print(f"  5. 数据处理...")
        time.sleep(0.01)  # 模拟数据处理时间
        print(f"  6. 任务 {i+1} 完成")
    
    print("\n下载流程模拟完成")


def analyze_time_gaps():
    """
    分析时间间隔的具体原因
    """
    print("分析时间间隔原因...")
    
    downloader = TuShareDownloader()
    
    print("\n当前API限制配置:")
    important_apis = ['stk_factor_pro', 'stk_factor', 'daily']
    for api in important_apis:
        config = downloader.api_limits.get(api, {'calls_per_minute': 200})
        interval = 60.0 / config['calls_per_minute']
        print(f"  {api}: {config['calls_per_minute']} calls/min -> {interval:.3f}s")
    
    print("\n速率限制机制分析:")
    print("  - 我们的速率限制是固定的，确保每x秒调用一次")
    print("  - 但如果API服务器返回频率限制错误，ErrorHandler会等待60秒")
    print("  - 可能原因：")
    print("    1. 服务器端有更复杂的频率限制算法")
    print("    2. 在高并发或多令牌环境中，服务器可能检测到更高的总频率")
    print("    3. 网络延迟导致请求到达时间与预期不一致") 
    print("    4. 服务器可能根据IP、令牌或其他因素进行综合评估")
    
    print("\n解决方案建议:")
    print("  - 已将ErrorHandler的频率限制等待时间从60秒减少到5秒")
    print("  - 确保速率限制计算准确")
    print("  - 可能需要在实际API调用之间增加额外缓冲时间")


if __name__ == "__main__":
    print("=" * 70)
    print("详细API调用和错误处理分析测试")
    print("=" * 70)
    
    # 运行各种测试
    test_api_limits_and_timing()
    print("\n" + "="*70)
    test_with_mock_api_call()
    print("\n" + "="*70)
    simulate_download_process()
    print("\n" + "="*70)
    analyze_time_gaps()
    
    print("\n所有分析测试完成!")
    print("\n注意：日志中出现长时间间隔(30+秒)可能是由以下原因造成的:")
    print("1. 服务器端的复杂频率限制算法")
    print("2. 网络延迟导致的请求时间偏差") 
    print("3. 服务器基于IP/令牌等的综合频率评估")
    print("4. 罕见情况下的网络超时或重试")