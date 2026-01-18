#!/usr/bin/env python
"""
测试 adj_factor 功能的简单脚本
"""
import sys
import os

# 将项目根目录添加到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

def test_imports():
    """测试相关模块是否能正确导入"""
    print("测试模块导入...")

    try:
        from app.interfaces.technical_factors import TechnicalFactorsDownloader
        print("✅ TechnicalFactorsDownloader 导入成功")
    except ImportError as e:
        print(f"❌ TechnicalFactorsDownloader 导入失败: {e}")
        return False

    try:
        from app.tushare_api import TuShareDownloader
        print("✅ TuShareDownloader 导入成功")
    except ImportError as e:
        print(f"❌ TuShareDownloader 导入失败: {e}")
        return False

    try:
        from app.download_strategies import DailyDataStrategy
        print("✅ DailyDataStrategy 导入成功")
    except ImportError as e:
        print(f"❌ DailyDataStrategy 导入失败: {e}")
        return False

    try:
        from app.download_scheduler import create_adj_factor_download_task
        print("✅ create_adj_factor_download_task 导入成功")
    except ImportError as e:
        print(f"❌ create_adj_factor_download_task 导入失败: {e}")
        return False

    return True

def test_methods_exist():
    """测试新增的方法是否存在"""
    print("\n测试新增方法是否存在...")

    try:
        from app.interfaces.technical_factors import TechnicalFactorsDownloader
        methods = [method for method in dir(TechnicalFactorsDownloader) if 'adj_factor' in method.lower()]
        print(f"✅ 找到包含 'adj_factor' 的方法: {methods}")

        expected_methods = [
            'download_adj_factor_all',
            'download_adj_factor_range',
            'download_all_stocks_adj_factor',
            'download_adj_factor_with_cache'
        ]

        missing_methods = []
        for method in expected_methods:
            if hasattr(TechnicalFactorsDownloader, method):
                print(f"✅ {method} 方法存在")
            else:
                print(f"❌ {method} 方法不存在")
                missing_methods.append(method)

        if missing_methods:
            print(f"❌ 缺少方法: {missing_methods}")
            return False
        else:
            print("✅ 所有预期方法都存在")
            return True

    except Exception as e:
        print(f"❌ 测试方法时出错: {e}")
        return False

def test_strategy_methods():
    """测试策略类中的方法"""
    print("\n测试策略类方法...")

    try:
        from app.download_strategies import DailyDataStrategy
        if hasattr(DailyDataStrategy, 'create_adj_factor_download_task'):
            print("✅ DailyDataStrategy.create_adj_factor_download_task 方法存在")
            return True
        else:
            print("❌ DailyDataStrategy.create_adj_factor_download_task 方法不存在")
            return False
    except Exception as e:
        print(f"❌ 测试策略类方法时出错: {e}")
        return False

def test_main_integration():
    """测试 main.py 中的参数集成"""
    print("\n测试 main.py 集成...")

    try:
        # 读取 main.py 检查是否包含 adj_factor_hfq 相关代码
        main_file = os.path.join(os.path.dirname(__file__), 'app', 'main.py')
        with open(main_file, 'r', encoding='utf-8') as f:
            content = f.read()

        if 'adj_factor_hfq' in content and 'download_all_stocks_adj_factor' in content:
            print("✅ main.py 中包含 adj_factor_hfq 相关代码")
            return True
        else:
            print("❌ main.py 中未找到 adj_factor_hfq 相关代码")
            return False
    except Exception as e:
        print(f"❌ 测试 main.py 集成时出错: {e}")
        return False

def run_tests():
    """运行所有测试"""
    print("="*50)
    print("开始测试 adj_factor 功能...")
    print("="*50)

    tests = [
        test_imports,
        test_methods_exist,
        test_strategy_methods,
        test_main_integration
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ 测试 {test.__name__} 出现异常: {e}")
            results.append(False)

    print("\n" + "="*50)
    print("测试总结:")
    print(f"总测试数: {len(results)}")
    print(f"通过: {sum(results)}")
    print(f"失败: {len(results) - sum(results)}")

    if all(results):
        print("✅ 所有测试通过！adj_factor 功能已成功集成")
    else:
        print("❌ 部分测试失败，请检查实现")

    print("="*50)
    return all(results)

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)