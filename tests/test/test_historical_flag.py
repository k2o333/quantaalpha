#!/usr/bin/env python3
"""
测试历史下载标记功能
"""
import sys
import os
import json
from datetime import datetime
from pathlib import Path

# 添加项目路径
sys.path.insert(0, '/home/quan/testdata/aspipe_v4')

def test_historical_marker_functions():
    """测试历史下载标记功能"""
    print("测试历史下载标记功能...")

    # 导入必要的函数和模块
    from app.main import get_historical_download_marker_path, mark_interfaces_as_historical_downloaded, get_historical_downloaded_interfaces

    # 测试路径获取
    marker_path = get_historical_download_marker_path()
    print(f"标记文件路径: {marker_path}")

    # 测试标记接口
    test_interfaces = ['stk_rewards', 'top10_holders', 'pro_bar']
    print(f"标记接口: {test_interfaces}")
    mark_interfaces_as_historical_downloaded(test_interfaces)

    # 测试读取已标记的接口
    downloaded_interfaces = get_historical_downloaded_interfaces()
    print(f"已历史下载的接口: {downloaded_interfaces}")

    # 验证接口是否正确记录
    if all(interface in downloaded_interfaces for interface in test_interfaces):
        print("✅ 历史下载标记功能正常工作")
    else:
        print("❌ 历史下载标记功能存在问题")

    # 检查标记文件内容
    if marker_path.exists():
        with open(marker_path, 'r', encoding='utf-8') as f:
            markers = json.load(f)
        print(f"标记文件内容: {markers}")

    # 清理测试标记
    marker_path.unlink(missing_ok=True)
    print(f"已清理测试标记文件: {marker_path}")

def test_config_modification():
    """测试配置修改功能"""
    print("\n测试配置修改功能...")

    # 导入必要的函数和模块
    from app.main import check_and_modify_config_for_date_range_download
    from app.enhanced_download_config import DOWNLOAD_PIPELINE_CONFIG, get_historical_downloaded_interfaces
    from app.main import mark_interfaces_as_historical_downloaded

    # 首先标记一些接口为已历史下载
    test_interfaces = ['stk_rewards', 'top10_holders']
    mark_interfaces_as_historical_downloaded(test_interfaces)
    print(f"已标记接口为历史下载: {test_interfaces}")

    # 记录原始启用状态
    original_states = {}
    for interface in test_interfaces:
        if interface in DOWNLOAD_PIPELINE_CONFIG:
            original_states[interface] = DOWNLOAD_PIPELINE_CONFIG[interface].enabled
            print(f"接口 {interface} 的原始启用状态: {original_states[interface]}")

    # 检查是否可以访问增强配置
    print(f"所有接口配置: {[name for name in DOWNLOAD_PIPELINE_CONFIG.keys() if name in ['stk_rewards', 'top10_holders', 'pro_bar']]}")

    # 恢复原始状态（清理测试影响）
    marker_path = Path('/home/quan/testdata/aspipe_v4/cache/historical_download_marker.json')
    marker_path.unlink(missing_ok=True)
    print("已清理测试标记")

if __name__ == '__main__':
    test_historical_marker_functions()
    test_config_modification()
    print("\n测试完成！")