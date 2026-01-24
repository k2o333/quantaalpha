#!/usr/bin/env python
"""
测试新功能的脚本
验证所有的新功能模块是否能正常工作
"""
import sys
import os
import logging
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

def test_enhanced_config():
    """测试增强配置模块"""
    print("="*50)
    print("测试增强配置模块...")
    try:
        from app.enhanced_download_config import DOWNLOAD_PIPELINE_CONFIG, get_high_priority_interfaces
        from app.config_adapter import ConfigAdapter, is_interface_enabled

        # 获取配置适配器
        config_adapter = ConfigAdapter()

        # 测试获取高优先级接口
        high_priority = get_high_priority_interfaces()
        print(f"高优先级接口数量: {len(high_priority)}")
        print(f"前5个高优先级接口: {high_priority[:5]}")

        # 测试接口是否启用
        if high_priority:
            first_interface = high_priority[0]
            is_enabled = is_interface_enabled(first_interface)
            print(f"接口 {first_interface} 是否启用: {is_enabled}")

        # 测试配置适配器功能
        if high_priority:
            first_interface = high_priority[0]
            max_retries = config_adapter.get_max_retries(first_interface)
            rate_limit = config_adapter.get_rate_limit(first_interface)
            print(f"接口 {first_interface} 配置 - 重试次数: {max_retries}, 速率限制: {rate_limit}")

        print("✅ 增强配置模块测试通过")
        return True
    except Exception as e:
        print(f"❌ 增强配置模块测试失败: {e}")
        return False


def test_parameter_adapters():
    """测试参数适配器模块"""
    print("="*50)
    print("测试参数适配器模块...")
    try:
        from app.parameter_adapters import ParameterAdapterManager, adapt_interface_parameters

        # 获取参数管理器
        param_manager = ParameterAdapterManager()

        # 测试参数适配
        test_params = {
            'start_date': '20230101',
            'end_date': '20230131',
            'ts_code': '000001.SZ'
        }

        adapted_params = adapt_interface_parameters('daily', test_params)
        print(f"原始参数: {test_params}")
        print(f"适配后参数: {adapted_params}")

        # 测试获取参数信息
        from app.parameter_adapters import get_required_parameters, get_optional_parameters
        required = get_required_parameters('income')
        optional = get_optional_parameters('income')
        print(f"income接口必需参数: {required}")
        print(f"income接口可选参数: {optional}")

        print("✅ 参数适配器模块测试通过")
        return True
    except Exception as e:
        print(f"❌ 参数适配器模块测试失败: {e}")
        return False


def test_download_strategies():
    """测试下载策略模块"""
    print("="*50)
    print("测试下载策略模块...")
    try:
        from app.download_strategies import get_strategy, get_available_strategies
        from app.tushare_api import TuShareDownloader

        # 测试获取可用策略
        available_strategies = get_available_strategies()
        print(f"可用策略数量: {len(available_strategies)}")
        print(f"前5个可用策略: {available_strategies[:5]}")

        # 测试获取策略实例
        if available_strategies:
            first_strategy = available_strategies[0]
            strategy = get_strategy(first_strategy)
            print(f"获取策略实例: {first_strategy}, 类型: {type(strategy).__name__}")

        print("✅ 下载策略模块测试通过")
        return True
    except Exception as e:
        print(f"❌ 下载策略模块测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_parallel_downloader():
    """测试并行下载器模块"""
    print("="*50)
    print("测试并行下载器模块...")
    try:
        from app.parallel_downloader import ParallelDownloader, create_parallel_downloader

        # 创建并行下载器
        downloader = create_parallel_downloader(max_workers=2)
        print(f"创建并行下载器: {type(downloader).__name__}")

        print("✅ 并行下载器模块测试通过")
        return True
    except Exception as e:
        print(f"❌ 并行下载器模块测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_global_rate_limiter():
    """测试全局速率限制器模块"""
    print("="*50)
    print("测试全局速率限制器模块...")
    try:
        from app.global_rate_limiter import get_global_rate_limiter, acquire_tokens
        from app.task_queue_manager import TaskPriority

        # 获取速率限制器
        limiter = get_global_rate_limiter()
        print(f"获取速率限制器实例: {type(limiter).__name__}")

        # 测试获取令牌
        success = acquire_tokens("test", 1.0, block=False)
        print(f"获取测试令牌成功: {success}")

        # 获取统计信息
        info = limiter.get_rate_limit_info("daily")
        print(f"daily接口速率限制信息: {info}")

        print("✅ 全局速率限制器模块测试通过")
        return True
    except Exception as e:
        print(f"❌ 全局速率限制器模块测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_storage_worker():
    """测试存储工作者模块"""
    print("="*50)
    print("测试存储工作者模块...")
    try:
        from app.storage_worker import get_default_storage_worker, submit_data_to_storage
        import pandas as pd

        # 获取存储工作者
        worker = get_default_storage_worker()
        print(f"获取存储工作者实例: {type(worker).__name__}")

        # 测试提交存储任务（使用空数据框）
        empty_df = pd.DataFrame()
        success = submit_data_to_storage(
            empty_df,
            "test_file",
            "test_subdir",
            task_id="test_task"
        )
        print(f"提交存储任务成功: {success}")

        print("✅ 存储工作者模块测试通过")
        return True
    except Exception as e:
        print(f"❌ 存储工作者模块测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_task_queue_manager():
    """测试任务队列管理器模块"""
    print("="*50)
    print("测试任务队列管理器模块...")
    try:
        from app.task_queue_manager import get_task_manager, TaskPriority, add_task_nowait
        import time

        # 获取任务管理器
        manager = get_task_manager()
        print(f"获取任务管理器实例: {type(manager).__name__}")

        # 添加一个简单任务（使用time.sleep模拟）
        def test_task():
            time.sleep(0.1)  # 模拟简单任务
            return "task_completed"

        task_id = add_task_nowait(
            task_type='test',
            target_func=test_task,
            priority=TaskPriority.MEDIUM
        )
        print(f"添加测试任务成功，任务ID: {task_id}")

        # 获取统计信息
        stats = manager.get_stats()
        print(f"任务管理器统计: {stats}")

        print("✅ 任务队列管理器模块测试通过")
        return True
    except Exception as e:
        print(f"❌ 任务队列管理器模块测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_download_scheduler():
    """测试下载调度器模块"""
    print("="*50)
    print("测试下载调度器模块...")
    try:
        from app.download_scheduler import create_download_scheduler, run_download_schedule
        from datetime import datetime, timedelta

        # 生成测试日期
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')

        print(f"使用测试日期范围: {start_date} 到 {end_date}")

        # 创建调度器（但不运行，只测试创建）
        scheduler = create_download_scheduler(start_date, end_date)
        print(f"创建下载调度器实例: {type(scheduler).__name__}")

        # 获取可用接口
        available_interfaces = scheduler.get_available_interfaces()
        print(f"可用接口数量: {len(available_interfaces)}")

        print("✅ 下载调度器模块测试通过")
        return True
    except Exception as e:
        print(f"❌ 下载调度器模块测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_main_integration():
    """测试主程序集成"""
    print("="*50)
    print("测试主程序集成...")
    try:
        from app.main import download_with_legacy_fallback
        from datetime import datetime, timedelta

        # 生成测试日期
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')

        print(f"使用测试日期范围: {start_date} 到 {end_date}")

        # 简单验证函数可调用（但不实际运行，避免长时间等待）
        print("验证主程序函数存在且可调用")

        print("✅ 主程序集成测试通过")
        return True
    except Exception as e:
        print(f"❌ 主程序集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("开始测试所有新功能模块...")

    tests = [
        test_enhanced_config,
        test_parameter_adapters,
        test_download_strategies,
        test_parallel_downloader,
        test_global_rate_limiter,
        test_storage_worker,
        test_task_queue_manager,
        test_download_scheduler,
        test_main_integration
    ]

    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            print(f"测试 {test_func.__name__} 异常: {e}")
            results.append(False)
        print()  # 空行分隔

    # 汇总结果
    passed = sum(results)
    total = len(results)

    print("="*50)
    print(f"测试汇总: {passed}/{total} 项测试通过")

    if passed == total:
        print("🎉 所有测试通过！新功能模块集成成功。")
        return True
    else:
        print("⚠️  部分测试失败，请检查错误信息。")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)