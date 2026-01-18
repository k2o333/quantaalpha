"""
测试脚本：验证分页、缓存和批量下载功能
"""
import sys
import os
import pandas as pd

# 添加项目路径
project_root = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, project_root)

# 简化导入
try:
    from app.config_manager import ConfigManager
    from app.api_manager import TuShareAPIManager
    from app.data_storage import get_cache_path_with_params, is_data_cached, is_data_fresh, get_data_with_cache_fallback
    from app.interfaces.daily_data import DailyDataDownloader
    from app.interfaces.market_flow import MarketFlowDownloader
    from app.interfaces.financial_data import FinancialDataDownloader
    from app.interfaces.market_structure import MarketStructureDownloader
    from app.interfaces.technical_factors import TechnicalFactorsDownloader
    from app.utils.parallel_downloader import ParallelDownloader
except ImportError as e:
    print(f"Import error: {e}")
    # 尝试另一种导入方式
    sys.path.insert(0, os.path.join(project_root, 'app'))
    from config_manager import ConfigManager
    from api_manager import TuShareAPIManager
    from data_storage import get_cache_path_with_params, is_data_cached, is_data_fresh, get_data_with_cache_fallback
    from interfaces.daily_data import DailyDataDownloader
    from interfaces.market_flow import MarketFlowDownloader
    from interfaces.financial_data import FinancialDataDownloader
    from interfaces.market_structure import MarketStructureDownloader
    from interfaces.technical_factors import TechnicalFactorsDownloader
    from utils.parallel_downloader import ParallelDownloader


def test_cache_functionality():
    """测试缓存功能"""
    print("Testing Cache Functionality...")

    # 测试基础缓存路径生成
    cache_path = get_cache_path_with_params('daily_basic', trade_date='20230101', ts_code='000001.SZ')
    print(f"Cache path for daily_basic with params: {cache_path}")

    # 测试缓存检查
    is_cached = is_data_cached(cache_path)
    print(f"Cache file exists: {is_cached}")

    # 测试新鲜度检查
    if is_cached:
        is_fresh = is_data_fresh(cache_path)
        print(f"Cache is fresh: {is_fresh}")

    # 测试通用缓存获取
    cached_data = get_data_with_cache_fallback('daily_basic', cache_hours=24, trade_date='20230101', ts_code='000001.SZ')
    if cached_data is not None:
        print(f"Retrieved cached data with {len(cached_data)} records")
    else:
        print("No cached data available, need to download from API")
    print()


def test_config_and_api_setup():
    """测试配置和API设置"""
    print("Testing Config and API Setup...")
    try:
        config = ConfigManager()
        print("ConfigManager initialized successfully")

        api_manager = TuShareAPIManager(config)
        print("TuShareAPIManager initialized successfully")
        return api_manager
    except Exception as e:
        print(f"Error with config/api setup: {e}")
        return None


def test_paged_downloaders(api_manager):
    """测试分页下载功能"""
    print("Testing Paged Downloaders...")

    try:
        # 测试日度数据分页下载
        print("Testing daily data page downloaders...")
        daily_downloader = DailyDataDownloader(api_manager.pro, api_manager.config)
        daily_data = daily_downloader.download_daily_basic_paginated(trade_date='20230101')
        print(f"Downloaded daily_basic with pagination: {len(daily_data)} records")

        # 测试资金流分页下载
        print("Testing moneyflow page downloaders...")
        market_flow_downloader = MarketFlowDownloader(api_manager.pro, api_manager.config)
        moneyflow_data = market_flow_downloader.download_moneyflow_paginated(trade_date='20230101')
        print(f"Downloaded moneyflow with pagination: {len(moneyflow_data)} records")

        # 测试财务数据分页下载
        print("Testing financial data page downloaders...")
        financial_downloader = FinancialDataDownloader(api_manager.pro, api_manager.config)
        income_data = financial_downloader.download_income_paginated(period='20221231')
        print(f"Downloaded income with pagination: {len(income_data)} records")

        fina_indicator_data = financial_downloader.download_fina_indicator_paginated(period='20221231')
        print(f"Downloaded fina_indicator with pagination: {len(fina_indicator_data)} records")

        # 测试市场结构分页下载
        print("Testing market structure page downloaders...")
        market_structure_downloader = MarketStructureDownloader(api_manager.pro, api_manager.config)
        cyq_perf_data = market_structure_downloader.download_cyq_perf_paginated(trade_date='20230101')
        print(f"Downloaded cyq_perf with pagination: {len(cyq_perf_data)} records")

        cyq_chips_data = market_structure_downloader.download_cyq_chips_paginated(trade_date='20230101')
        print(f"Downloaded cyq_chips with pagination: {len(cyq_chips_data)} records")

        # 测试技术因子分页下载
        print("Testing technical factors page downloaders...")
        tech_factor_downloader = TechnicalFactorsDownloader(api_manager.pro, api_manager.config)
        stk_factor_data = tech_factor_downloader.download_stk_factor_paginated(trade_date='20230101')
        print(f"Downloaded stk_factor with pagination: {len(stk_factor_data)} records")

    except Exception as e:
        print(f"Error with paged downloaders: {e}")
    print()


def test_parallel_downloader(api_manager):
    """测试并行下载功能"""
    print("Testing Parallel Downloader...")

    try:
        parallel_downloader = ParallelDownloader(api_manager.config)

        # 测试几个交易日的并行下载
        trading_days = ['20230101', '20230102', '20230103']
        results = parallel_downloader.download_daily_type_parallel('daily_basic', trading_days)
        print(f"Parallel download results: {results}")

        # 测试资金流并行下载
        results = parallel_downloader.download_daily_type_parallel('moneyflow', trading_days)
        print(f"Parallel download results for moneyflow: {results}")

    except Exception as e:
        print(f"Error with parallel downloader: {e}")
    print()


def test_api_manager_pagination():
    """测试API管理器的分页功能"""
    print("Testing API Manager Pagination...")

    try:
        config = ConfigManager()
        api_manager = TuShareAPIManager(config)

        # 测试API管理器的分页方法
        daily_basic_data = api_manager.download_daily_basic_paginated(trade_date='20230101')
        print(f"API Manager daily_basic pagination: {len(daily_basic_data)} records")

        stk_factor_data = api_manager.download_stk_factor_paginated(trade_date='20230101')
        print(f"API Manager stk_factor pagination: {len(stk_factor_data)} records")

        cyq_perf_data = api_manager.download_cyq_perf_paginated(trade_date='20230101')
        print(f"API Manager cyq_perf pagination: {len(cyq_perf_data)} records")

        cyq_chips_data = api_manager.download_cyq_chips_paginated(trade_date='20230101')
        print(f"API Manager cyq_chips pagination: {len(cyq_chips_data)} records")

    except Exception as e:
        print(f"Error with API manager pagination: {e}")
    print()


def main():
    """主测试函数"""
    print("Starting pagination, batching and caching tests...\n")

    # 测试缓存功能
    test_cache_functionality()

    # 测试配置和API设置
    api_manager = test_config_and_api_setup()
    if api_manager is None:
        print("Skipping further tests due to API setup failure")
        return

    # 测试API管理器分页功能
    test_api_manager_pagination()

    # 测试分页下载器
    test_paged_downloaders(api_manager)

    # 测试并行下载器
    test_parallel_downloader(api_manager)

    print("All tests completed!")


if __name__ == "__main__":
    main()