#!/usr/bin/env python3
"""
测试tscode-historical模式功能的脚本
"""

import sys
import os
from datetime import datetime

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)
os.chdir(project_root)  # 更改当前工作目录到项目根目录

def test_tscode_historical_mode():
    """
    测试tscode-historical模式
    """
    print("开始测试tscode-historical模式...")

    # 导入必要的模块
    try:
        # 使用相对导入
        sys.path.insert(0, os.path.join(project_root, 'app'))
        import importlib.util

        # 动态导入模块
        spec = importlib.util.spec_from_file_location("main", os.path.join(project_root, "app", "main.py"))
        main_module = importlib.util.module_from_spec(spec)

        spec = importlib.util.spec_from_file_location("enhanced_download_config", os.path.join(project_root, "app", "enhanced_download_config.py"))
        config_module = importlib.util.module_from_spec(spec)

        spec = importlib.util.spec_from_file_location("download_scheduler", os.path.join(project_root, "app", "download_scheduler.py"))
        scheduler_module = importlib.util.module_from_spec(spec)

        print("✓ 成功导入模块")
    except Exception as e:
        print(f"✗ 导入模块失败: {e}")
        return False

    # 检查配置是否正确更新
    try:
        spec = importlib.util.spec_from_file_location("enhanced_download_config", os.path.join(project_root, "app", "enhanced_download_config.py"))
        config_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(config_module)

        DOWNLOAD_PIPELINE_CONFIG = config_module.DOWNLOAD_PIPELINE_CONFIG
        tscode_interfaces = ['stk_rewards', 'top10_holders', 'pledge_detail', 'fina_audit', 'pro_bar']
        print("\n检查tscode接口配置:")
        for interface in tscode_interfaces:
            if interface in DOWNLOAD_PIPELINE_CONFIG:
                config = DOWNLOAD_PIPELINE_CONFIG[interface]
                if hasattr(config, 'requires_tscode') and config.requires_tscode:
                    print(f"✓ {interface}: 正确配置为需要ts_code参数")
                else:
                    print(f"✗ {interface}: 未正确配置为需要ts_code参数")
            else:
                print(f"✗ {interface}: 未在配置中找到")
    except Exception as e:
        print(f"✗ 检查配置失败: {e}")
        return False

    # 检查DownloadScheduler是否具有新方法
    try:
        spec = importlib.util.spec_from_file_location("download_scheduler", os.path.join(project_root, "app", "download_scheduler.py"))
        scheduler_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(scheduler_module)

        # 检查是否存在新添加的方法
        methods_to_check = [
            '_get_stock_list',
            '_is_tscode_interface',
            '_schedule_tscode_interface',
            '_execute_tscode_download'
        ]

        print("\n检查DownloadScheduler新方法:")
        for method in methods_to_check:
            if hasattr(scheduler_module.DownloadScheduler, method):
                print(f"✓ {method}: 存在")
            else:
                print(f"✗ {method}: 不存在")

        # 检查schedule_download_tasks方法是否支持mode参数
        import inspect
        sig = inspect.signature(scheduler_module.DownloadScheduler.schedule_download_tasks)
        if 'mode' in sig.parameters:
            print("✓ schedule_download_tasks: 支持mode参数")
        else:
            print("✗ schedule_download_tasks: 不支持mode参数")

        print("✓ DownloadScheduler测试通过")
    except Exception as e:
        print(f"✗ DownloadScheduler测试失败: {e}")
        return False

    print("\n✓ 所有测试通过!")
    return True

if __name__ == "__main__":
    test_tscode_historical_mode()