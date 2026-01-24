# test_smart_pagination.py
from app4.core.downloader import GenericDownloader
from app4.core.config_loader import ConfigLoader

def test_smart_pagination_strategy():
    """测试智能分页策略"""
    config_loader = ConfigLoader('app4/config')
    downloader = GenericDownloader(config_loader)

    # 测试不同类型接口的窗口大小
    small_interfaces = ['fina_audit', 'forecast_vip']
    medium_interfaces = ['top10_holders', 'top10_floatholders', 'pledge_detail', 'dividend']
    financial_interfaces = ['balancesheet_vip', 'income_vip', 'cashflow_vip']

    for interface in small_interfaces:
        window_size = downloader._get_window_size_for_interface(interface)
        assert window_size >= 3650  # 小数据量接口使用大窗口

    for interface in medium_interfaces:
        window_size = downloader._get_window_size_for_interface(interface)
        assert 1000 <= window_size <= 2000  # 中等数据量接口使用中等窗口

    for interface in financial_interfaces:
        window_size = downloader._get_window_size_for_interface(interface)
        assert window_size >= 10000  # 财务数据接口使用大窗口