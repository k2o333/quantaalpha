#!/usr/bin/env python3
"""
测试脚本：分析stk_factor_pro API调用的时间间隔模式
"""
import sys
import os
import time
import logging

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.tushare_api import TuShareDownloader

def test_api_call_pattern():
    print("开始测试API调用模式...")
    
    # 创建下载器实例
    downloader = TuShareDownloader()
    
    # 设置日志记录器来捕获详细信息
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)
    
    print(f"API限制: {downloader.api_limits.get('stk_factor_pro', {'calls_per_minute': 30})}")
    print(f"预期间隔: {60.0 / 30} 秒")
    
    # 记录调用时间
    call_times = []
    
    # 连续调用API 10次以观察模式（减少次数以避免超时）
    print("\n开始连续API调用测试...")
    for i in range(5):  # 减少次数避免超时
        start_time = time.time()
        print(f"\n调用 #{i+1} 开始时间: {start_time:.3f}")
        
        try:
            # 记录调用前时间
            call_start = time.perf_counter()
            downloader._advanced_rate_limit('stk_factor_pro')
            rate_limit_time = time.perf_counter() - call_start
            
            print(f"  速率限制耗时: {rate_limit_time:.3f}秒")
            
            # 记录实际的API调用时间
            actual_call_time = time.time()
            call_times.append(actual_call_time)
            
            print(f"  调用 #{i+1} 完成时间: {actual_call_time:.3f}")
            
            # 如果不是最后一次调用，记录到下一次的间隔
            if i < 4:
                print(f"  准备下一次调用...")
                
        except Exception as e:
            print(f"  调用 #{i+1} 失败: {e}")
    
    # 分析时间间隔
    print("\n时间间隔分析:")
    for i in range(1, len(call_times)):
        interval = call_times[i] - call_times[i-1]
        print(f"  间隔 {i} -> {i+1}: {interval:.3f}秒")
    
    print("\n测试完成")


def test_batch_api_calls():
    """
    一次性调用接口30次，然后等反馈，然后再调用30次，再等反馈
    """
    print("测试批量API调用模式...")
    
    downloader = TuShareDownloader()
    
    # 记录时间戳
    timestamps = []
    
    print("\n第一轮：连续调用30次API")
    start_time = time.time()
    
    for i in range(5):  # 先用5次测试，避免超时
        call_time = time.time()
        print(f"  调用 #{i+1} at {call_time - start_time:.3f}s")
        
        try:
            # 使用速率限制
            downloader._advanced_rate_limit('stk_factor_pro')
            
            # 记录调用完成时间
            completion_time = time.time()
            timestamps.append((call_time, completion_time))
            
            print(f"    完成 at {completion_time - start_time:.3f}s, duration: {completion_time - call_time:.3f}s")
            
        except Exception as e:
            print(f"    调用 #{i+1} 失败: {e}")
    
    print("\n第一轮完成，开始分析时间间隔...")
    
    # 分析间隔
    for i in range(1, len(timestamps)):
        prev_completion = timestamps[i-1][1]
        curr_call = timestamps[i][0]
        wait_time = curr_call - prev_completion
        print(f"  调用 {i} -> {i+1}: 等待时间 {wait_time:.3f}s")
    
    print("\n批量调用测试完成")


def test_minimal_rate_limit():
    """
    仅测试速率限制功能，不实际调用API
    """
    print("测试速率限制功能（不实际调用API）...")
    
    downloader = TuShareDownloader()
    
    print("预期API限制:")
    api_config = downloader.api_limits.get('stk_factor_pro', {'calls_per_minute': 30})
    expected_interval = 60.0 / api_config['calls_per_minute']
    print(f"  stk_factor_pro: {api_config['calls_per_minute']} calls/min -> {expected_interval:.3f}s interval")
    
    # 测试速率限制时间
    times = []
    for i in range(5):
        start = time.perf_counter()
        downloader._advanced_rate_limit('stk_factor_pro')
        end = time.perf_counter()
        duration = end - start
        times.append(duration)
        print(f"  调用 {i+1}: 速率限制耗时 {duration:.3f}s")
    
    print(f"\n平均速率限制耗时: {sum(times)/len(times):.3f}s")
    print("速率限制测试完成")


if __name__ == "__main__":
    print("=" * 60)
    print("API调用模式分析测试")
    print("=" * 60)
    
    # 运行不同的测试
    test_minimal_rate_limit()
    print("\n" + "="*60)
    test_api_call_pattern()
    print("\n" + "="*60)
    test_batch_api_calls()
    
    print("\n所有测试完成!")