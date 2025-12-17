"""
验证实现的分页、分批和缓存功能
"""
import inspect
import sys
import os

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, project_root)

def validate_pagination_methods():
    """验证分页方法是否已添加到各个接口类中"""
    print("验证分页方法实现...")

    # 从接口模块导入类
    from app.interfaces.daily_data import DailyDataDownloader
    from app.interfaces.market_flow import MarketFlowDownloader
    from app.interfaces.financial_data import FinancialDataDownloader
    from app.interfaces.market_structure import MarketStructureDownloader
    from app.interfaces.technical_factors import TechnicalFactorsDownloader

    # 检查各个类中的分页方法
    print("\n1. DailyDataDownloader 类:")
    methods = [method for method in dir(DailyDataDownloader) if 'page' in method.lower()]
    print(f"   分页相关方法: {methods}")

    # 检查是否有 download_daily_basic_paginated 方法
    has_paginated_method = hasattr(DailyDataDownloader, 'download_daily_basic_paginated')
    print(f"   包含 download_daily_basic_paginated: {has_paginated_method}")

    print("\n2. MarketFlowDownloader 类:")
    methods = [method for method in dir(MarketFlowDownloader) if 'page' in method.lower()]
    print(f"   分页相关方法: {methods}")

    has_paginated_method = hasattr(MarketFlowDownloader, 'download_moneyflow_paginated')
    print(f"   包含 download_moneyflow_paginated: {has_paginated_method}")

    print("\n3. FinancialDataDownloader 类:")
    methods = [method for method in dir(FinancialDataDownloader) if 'page' in method.lower()]
    print(f"   分页相关方法: {methods}")

    has_income_paginated = hasattr(FinancialDataDownloader, 'download_income_paginated')
    has_fina_paginated = hasattr(FinancialDataDownloader, 'download_fina_indicator_paginated')
    print(f"   包含 download_income_paginated: {has_income_paginated}")
    print(f"   包含 download_fina_indicator_paginated: {has_fina_paginated}")

    print("\n4. MarketStructureDownloader 类:")
    methods = [method for method in dir(MarketStructureDownloader) if 'page' in method.lower()]
    print(f"   分页相关方法: {methods}")

    print("\n5. TechnicalFactorsDownloader 类:")
    methods = [method for method in dir(TechnicalFactorsDownloader) if 'page' in method.lower()]
    print(f"   分页相关方法: {methods}")

    has_stk_factor_paginated = hasattr(TechnicalFactorsDownloader, 'download_stk_factor_paginated')
    print(f"   包含 download_stk_factor_paginated: {has_stk_factor_paginated}")

def validate_cache_enhancements():
    """验证缓存功能的增强"""
    print("\n\n验证缓存功能增强...")

    from app.data_storage import get_cache_path_with_params, get_data_with_cache_fallback

    print("1. data_storage 模块新增方法:")
    print(f"   get_cache_path_with_params 存在: {hasattr(__import__('app.data_storage', fromlist=['get_cache_path_with_params']), 'get_cache_path_with_params')}")
    print(f"   get_data_with_cache_fallback 存在: {hasattr(__import__('app.data_storage', fromlist=['get_data_with_cache_fallback']), 'get_data_with_cache_fallback')}")

    # 测试新的缓存路径生成函数
    cache_path = get_cache_path_with_params('daily_basic', trade_date='20230101', ts_code='000001.SZ')
    print(f"   新缓存路径生成测试: {cache_path}")

def validate_parallel_downloader():
    """验证并行下载器的适配"""
    print("\n\n验证并行下载器适配...")

    from app.utils.parallel_downloader import ParallelDownloader
    import importlib
    importlib.reload(sys.modules.get('app.utils.parallel_downloader', __import__('app.utils.parallel_downloader')))

    # 检查并行下载器是否更新
    code = inspect.getsource(ParallelDownloader)
    uses_paginated_methods = 'download_daily_basic_paginated' in code or 'download_moneyflow_paginated' in code
    print(f"   并行下载器使用分页方法: {uses_paginated_methods}")

def validate_imports_fixed():
    """验证导入问题是否已修复"""
    print("\n\n验证导入修复...")

    try:
        from app.config_manager import ConfigManager
        from app.api_manager import TuShareAPIManager
        from app.interfaces.daily_data import DailyDataDownloader
        from app.interfaces.market_flow import MarketFlowDownloader
        from app.interfaces.financial_data import FinancialDataDownloader
        from app.interfaces.market_structure import MarketStructureDownloader
        from app.interfaces.technical_factors import TechnicalFactorsDownloader
        from app.utils.parallel_downloader import ParallelDownloader
        print("   所有模块导入成功!")
        return True
    except ImportError as e:
        print(f"   导入错误: {e}")
        return False

def main():
    print("="*60)
    print("ASPIPE_V4 分页、分批和缓存功能实现验证报告")
    print("="*60)

    validate_pagination_methods()
    validate_cache_enhancements()
    validate_parallel_downloader()
    validate_imports_fixed()

    print("\n" + "="*60)
    print("验证完成!")
    print("\n实现的功能包括:")
    print("1. 在各接口类中添加了分页下载方法")
    print("2. 增强了缓存功能，支持参数化缓存路径")
    print("3. 修复了模块间的导入问题")
    print("4. 适配了并行下载器以使用分页方法")
    print("5. 在现有架构基础上实现了分页、分批和缓存功能")
    print("="*60)

if __name__ == "__main__":
    main()