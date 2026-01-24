# test_downloader_performance_monitor.py
from app4.core.downloader import GenericDownloader
from app4.core.config_loader import ConfigLoader

def test_downloader_performance_monitor():
    """测试Downloader中的性能监控集成"""
    config_loader = ConfigLoader('app4/config')
    downloader = GenericDownloader(config_loader)

    # 验证性能监控器已初始化
    assert hasattr(downloader, 'performance_monitor')
    assert downloader.performance_monitor is not None