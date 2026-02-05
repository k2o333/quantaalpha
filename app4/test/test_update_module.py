"""
增量更新模块测试
测试 UpdateManager, DateCalculator, InterfaceSelector 等组件
"""
import pytest
import os
import sys
import tempfile
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from update import (
    UpdateManager,
    UpdateOptions,
    DateCalculator,
    InterfaceSelector,
    UpdateReporter,
    CheckpointManager,
    DateRange,
    InterfaceUpdateResult,
    UpdateResult,
    UpdateSummary,
    UpdateStatus,
    ReportFormat,
)


class TestDateRange:
    """测试 DateRange 类"""
    
    def test_date_range_creation(self):
        """测试创建日期范围"""
        dr = DateRange(start_date='20230101', end_date='20231231')
        assert dr.start_date == '20230101'
        assert dr.end_date == '20231231'
    
    def test_is_empty(self):
        """测试空范围检测"""
        # 空范围
        dr = DateRange(start_date='20231231', end_date='20230101')
        assert dr.is_empty() is True
        
        # 非空范围
        dr = DateRange(start_date='20230101', end_date='20231231')
        assert dr.is_empty() is False
    
    def test_days_between(self):
        """测试天数计算"""
        dr = DateRange(start_date='20230101', end_date='20230110')
        assert dr.days_between() == 9


class TestUpdateOptions:
    """测试 UpdateOptions 类"""
    
    def test_default_options(self):
        """测试默认选项"""
        options = UpdateOptions()
        assert options.force is False
        assert options.dry_run is False
        assert options.report_format == ReportFormat.MARKDOWN
        assert options.max_workers == 1
    
    def test_custom_options(self):
        """测试自定义选项"""
        options = UpdateOptions(
            interfaces=['daily', 'daily_basic'],
            force=True,
            dry_run=True,
            report_format=ReportFormat.JSON
        )
        assert options.interfaces == ['daily', 'daily_basic']
        assert options.force is True
        assert options.dry_run is True
        assert options.report_format == ReportFormat.JSON


class TestInterfaceUpdateResult:
    """测试 InterfaceUpdateResult 类"""
    
    def test_result_creation(self):
        """测试结果创建"""
        result = InterfaceUpdateResult(
            interface_name='daily',
            status=UpdateStatus.SUCCESS,
            record_count=1000,
            duration_seconds=5.5
        )
        assert result.interface_name == 'daily'
        assert result.status == UpdateStatus.SUCCESS
        assert result.record_count == 1000
        assert result.duration_seconds == 5.5


class TestCheckpointManager:
    """测试 CheckpointManager 类"""
    
    def test_checkpoint_initialization(self):
        """测试断点管理器初始化"""
        config = {
            'enabled': True,
            'file': 'test_checkpoint.json',
            'interval': 5,
            'auto_resume': True
        }
        manager = CheckpointManager(config)
        assert manager.enabled is True
        assert manager.filepath == 'test_checkpoint.json'
        assert manager.interval == 5
    
    def test_interface_completion_tracking(self):
        """测试接口完成追踪"""
        config = {'enabled': False}
        manager = CheckpointManager(config)
        
        # 记录接口完成
        manager.record_interface_complete('daily', True)
        assert manager.is_interface_completed('daily') is True
        assert manager.is_interface_completed('daily_basic') is False
    
    def test_failed_interface_tracking(self):
        """测试失败接口追踪"""
        config = {'enabled': False}
        manager = CheckpointManager(config)
        
        # 记录接口失败
        manager.record_interface_complete('daily', False, 'Network error')
        assert manager.is_interface_failed('daily') is True
        
        failed = manager.get_failed_interfaces()
        assert 'daily' in failed
        assert failed['daily']['error'] == 'Network error'
    
    def test_get_resume_interfaces(self):
        """测试获取恢复接口列表"""
        config = {'enabled': False}
        manager = CheckpointManager(config)
        
        all_interfaces = ['daily', 'daily_basic', 'moneyflow']
        manager.record_interface_complete('daily', True)
        
        resume_list = manager.get_resume_interfaces(all_interfaces)
        assert 'daily' not in resume_list
        assert 'daily_basic' in resume_list
        assert 'moneyflow' in resume_list


class TestUpdateReporter:
    """测试 UpdateReporter 类"""
    
    def test_reporter_initialization(self):
        """测试报告器初始化"""
        reporter = UpdateReporter()
        assert reporter.start_time is None
        assert reporter.end_time is None
        assert len(reporter.interface_results) == 0
    
    def test_record_interface_result(self):
        """测试记录接口结果"""
        reporter = UpdateReporter()
        
        result = InterfaceUpdateResult(
            interface_name='daily',
            status=UpdateStatus.SUCCESS,
            record_count=1000
        )
        
        reporter.record_interface_result(result)
        assert len(reporter.interface_results) == 1
        assert reporter.interface_results[0].interface_name == 'daily'
    
    def test_get_summary(self):
        """测试获取摘要"""
        reporter = UpdateReporter()
        reporter.record_update_start()
        
        # 添加一些结果
        reporter.record_interface_result(
            InterfaceUpdateResult('daily', UpdateStatus.SUCCESS, record_count=100)
        )
        reporter.record_interface_result(
            InterfaceUpdateResult('daily_basic', UpdateStatus.SUCCESS, record_count=200)
        )
        reporter.record_interface_result(
            InterfaceUpdateResult('moneyflow', UpdateStatus.FAILED, error_message='Error')
        )
        
        reporter.record_update_end()
        
        summary = reporter.get_summary()
        assert summary.total == 3
        assert summary.success == 2
        assert summary.failed == 1
        assert summary.total_records == 300


class TestInterfaceSelector:
    """测试 InterfaceSelector 类"""
    
    @pytest.fixture
    def mock_config_loader(self):
        """创建模拟配置加载器"""
        config_loader = Mock()
        config_loader.global_config = {
            'groups': {
                'daily': ['daily', 'daily_basic', 'moneyflow'],
                'financial': ['income', 'balancesheet']
            },
            'update': {
                'excluded_interfaces': ['trade_cal'],
                'update_order': ['daily', 'daily_basic', 'moneyflow']
            }
        }
        config_loader.get_available_interfaces.return_value = [
            'daily', 'daily_basic', 'moneyflow', 'income', 'balancesheet', 'trade_cal'
        ]
        return config_loader
    
    def test_select_all_interfaces(self, mock_config_loader):
        """测试选择所有接口"""
        selector = InterfaceSelector(mock_config_loader)
        options = UpdateOptions()
        
        interfaces = selector.select_interfaces(options)
        # 应该排除 trade_cal
        assert 'trade_cal' not in interfaces
        assert 'daily' in interfaces
        assert 'income' in interfaces
    
    def test_select_by_interface(self, mock_config_loader):
        """测试按接口选择"""
        selector = InterfaceSelector(mock_config_loader)
        options = UpdateOptions(interfaces=['daily', 'income'])
        
        interfaces = selector.select_interfaces(options)
        assert interfaces == ['daily', 'income']
    
    def test_select_by_group(self, mock_config_loader):
        """测试按组选择"""
        selector = InterfaceSelector(mock_config_loader)
        options = UpdateOptions(groups=['daily'])
        
        interfaces = selector.select_interfaces(options)
        assert set(interfaces) == {'daily', 'daily_basic', 'moneyflow'}
    
    def test_apply_exclusions(self, mock_config_loader):
        """测试排除规则"""
        selector = InterfaceSelector(mock_config_loader)
        options = UpdateOptions(exclude=['moneyflow'])
        
        interfaces = selector.select_interfaces(options)
        assert 'moneyflow' not in interfaces
        assert 'daily' in interfaces
    
    def test_sort_by_update_order(self, mock_config_loader):
        """测试按更新顺序排序"""
        selector = InterfaceSelector(mock_config_loader)
        options = UpdateOptions(groups=['daily'])
        
        interfaces = selector.select_interfaces(options)
        # 检查是否按配置顺序排序
        assert interfaces.index('daily') < interfaces.index('daily_basic')


class TestDateCalculator:
    """测试 DateCalculator 类"""
    
    @pytest.fixture
    def mock_config_loader(self):
        """创建模拟配置加载器"""
        config_loader = Mock()
        config_loader.global_config = {
            'update': {
                'default_strategy': {
                    'start_date': '20000101',
                    'lookback_days': 7
                },
                'special_interfaces': {
                    'trade_cal': {
                        'start_date': '19900101',
                        'date_column': 'cal_date'
                    }
                }
            }
        }
        return config_loader
    
    @pytest.fixture
    def mock_storage_manager(self):
        """创建模拟存储管理器"""
        storage = Mock()
        return storage
    
    def test_calculate_update_range_with_forced_dates(self, mock_config_loader, mock_storage_manager):
        """测试强制日期范围"""
        calculator = DateCalculator(mock_config_loader, mock_storage_manager)
        
        date_range = calculator.calculate_update_range(
            'daily',
            forced_start='20230101',
            forced_end='20231231'
        )
        
        assert date_range.start_date == '20230101'
        assert date_range.end_date == '20231231'
    
    def test_get_interface_date_column(self, mock_config_loader, mock_storage_manager):
        """测试获取接口日期列"""
        calculator = DateCalculator(mock_config_loader, mock_storage_manager)
        
        # 交易日历
        assert calculator._get_interface_date_column('trade_cal') == 'cal_date'
        
        # 财务数据
        assert calculator._get_interface_date_column('income_vip') == 'end_date'
        
        # 默认
        assert calculator._get_interface_date_column('daily') == 'trade_date'
    
    def test_get_default_start_date(self, mock_config_loader, mock_storage_manager):
        """测试获取默认起始日期"""
        calculator = DateCalculator(mock_config_loader, mock_storage_manager)
        
        # 特殊接口
        assert calculator._get_default_start_date('trade_cal') == '19900101'
        
        # 一般接口
        assert calculator._get_default_start_date('daily') == '20000101'


class TestUpdateManager:
    """测试 UpdateManager 类"""
    
    @pytest.fixture
    def mock_components(self):
        """创建模拟组件"""
        config_loader = Mock()
        config_loader.global_config = {
            'update': {
                'checkpoint': {'enabled': False},
                'fault_tolerance': {
                    'skip_on_error': True,
                    'max_consecutive_errors': 5
                }
            }
        }
        
        storage_manager = Mock()
        downloader = Mock()
        downloader.coverage_manager = Mock()
        downloader.pagination_executor = Mock()
        
        scheduler = Mock()
        processor = Mock()
        rate_limiter = Mock()
        
        return {
            'config_loader': config_loader,
            'storage_manager': storage_manager,
            'downloader': downloader,
            'scheduler': scheduler,
            'processor': processor,
            'rate_limiter': rate_limiter
        }
    
    def test_should_update_interface_force_mode(self, mock_components):
        """测试强制更新模式"""
        manager = UpdateManager(**mock_components)
        options = UpdateOptions(force=True)
        date_range = DateRange('20230101', '20231231')
        
        should_update, reason = manager.should_update_interface('daily', date_range, options)
        assert should_update is True
        assert reason is None
    
    def test_create_result(self, mock_components):
        """测试创建结果对象"""
        manager = UpdateManager(**mock_components)
        
        # 添加一些模拟结果
        manager.reporter.interface_results = [
            InterfaceUpdateResult('daily', UpdateStatus.SUCCESS, record_count=100),
            InterfaceUpdateResult('daily_basic', UpdateStatus.FAILED, error_message='Error')
        ]
        manager.reporter.start_time = datetime.now()
        manager.reporter.end_time = datetime.now()
        
        result = manager._create_result()
        
        assert result.total_interfaces == 2
        assert result.success_count == 1
        assert result.failed_count == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
