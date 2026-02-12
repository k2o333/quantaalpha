"""
更新管理器
协调整个增量更新流程
"""
import logging
import time
import os
from datetime import datetime
from typing import Optional, Dict, Any, List

from .models import (
    UpdateStatus,
    DateRange,
    UpdateOptions,
    InterfaceUpdateResult,
    UpdateResult
)
from .date_calculator import DateCalculator
from .interface_selector import InterfaceSelector
from .update_reporter import UpdateReporter
from .checkpoint_manager import CheckpointManager
from core.pagination import PaginationContext, create_context_with_legacy_support, migrate_legacy_config

logger = logging.getLogger(__name__)


class UpdateManager:
    """更新管理器 - 协调整个增量更新流程"""
    
    def __init__(
        self,
        config_loader,
        storage_manager,
        downloader,
        scheduler,
        processor
    ):
        """
        初始化更新管理器
        
        Args:
            config_loader: 配置加载器
            storage_manager: 存储管理器
            downloader: 通用下载器
            scheduler: 任务调度器
            processor: 数据处理器
        """
        self.config_loader = config_loader
        self.storage_manager = storage_manager
        self.downloader = downloader
        self.scheduler = scheduler
        self.processor = processor
        
        # 子组件
        self.date_calculator = DateCalculator(config_loader, storage_manager)
        self.interface_selector = InterfaceSelector(config_loader)
        self.reporter = UpdateReporter()
        
        # 复用现有的 CoverageManager（通过 downloader 获取）
        self.coverage_manager = downloader.coverage_manager if downloader else None
        
        # 复用现有的 PaginationExecutor（通过 downloader 获取）
        self.pagination_executor = downloader.pagination_executor if downloader else None
        
        # 断点续传管理器
        update_config = config_loader.global_config.get('update', {})
        self.checkpoint_manager = CheckpointManager(
            update_config.get('checkpoint', {})
        )
        
        # 容错配置
        self.fault_tolerance = update_config.get('fault_tolerance', {})
        self.skip_on_error = self.fault_tolerance.get('skip_on_error', True)
        self.stop_on_storage_error = self.fault_tolerance.get('stop_on_storage_error', True)
        self.max_consecutive_errors = self.fault_tolerance.get('max_consecutive_errors', 5)
    
    def run_update(self, options: UpdateOptions) -> UpdateResult:
        """
        执行增量更新
        
        流程：
        1. 初始化环境
        2. 加载断点（如有）
        3. 选择需要更新的接口
        4. 逐个接口执行更新
        5. 保存断点
        6. 生成更新报告
        
        Args:
            options: 更新选项
            
        Returns:
            UpdateResult: 更新结果
        """
        # 记录更新开始
        self.reporter.record_update_start()
        
        try:
            # 初始化环境
            logger.info("=" * 60)
            logger.info("开始增量更新")
            logger.info("=" * 60)
            
            # 检查断点续传
            if self.checkpoint_manager.should_resume() and not options.force:
                checkpoint = self.checkpoint_manager.load_checkpoint()
                if checkpoint:
                    summary = self.checkpoint_manager.get_checkpoint_summary()
                    logger.info(f"检测到未完成的更新，已恢复进度。已完成: {summary['total_completed']} 个接口")
            
            # 初始化新的断点
            if not options.force:
                self.checkpoint_manager.initialize_checkpoint({
                    'interfaces': options.interfaces,
                    'groups': options.groups,
                    'start_date': options.start_date,
                    'end_date': options.end_date,
                    'force': options.force
                })
            
            # 选择需要更新的接口
            interfaces = self.interface_selector.select_interfaces(options)
            
            if not interfaces:
                logger.warning("没有选择任何接口进行更新")
                self.reporter.record_update_end()
                return self._create_result()
            
            # 如果是恢复模式，过滤已完成的接口
            if self.checkpoint_manager.should_resume() and not options.force:
                interfaces = self.checkpoint_manager.get_resume_interfaces(interfaces)
                logger.info(f"恢复模式：剩余 {len(interfaces)} 个接口需要更新")
            
            # 逐个接口执行更新
            consecutive_errors = 0
            for idx, interface_name in enumerate(interfaces, 1):
                logger.info(f"\n[{idx}/{len(interfaces)}] 处理接口: {interface_name}")
                
                # 检查是否超过最大连续错误数
                if consecutive_errors >= self.max_consecutive_errors:
                    logger.error(f"连续错误次数超过 {self.max_consecutive_errors}，停止更新")
                    break
                
                # 记录接口开始
                self.checkpoint_manager.record_interface_start(interface_name)
                self.reporter.record_interface_start(interface_name)
                
                # 执行接口更新
                try:
                    result = self.update_interface(interface_name, options)
                    self.reporter.record_interface_result(result)
                    
                    # 更新连续错误计数
                    if result.status == UpdateStatus.FAILED:
                        consecutive_errors += 1
                    else:
                        consecutive_errors = 0
                    
                    # 记录接口完成
                    self.checkpoint_manager.record_interface_complete(
                        interface_name,
                        result.status in [UpdateStatus.SUCCESS, UpdateStatus.SKIPPED],
                        result.error_message
                    )
                    
                except Exception as e:
                    logger.error(f"更新接口 {interface_name} 时发生异常: {e}")
                    consecutive_errors += 1
                    
                    # 创建失败结果
                    result = InterfaceUpdateResult(
                        interface_name=interface_name,
                        status=UpdateStatus.FAILED,
                        error_message=str(e)
                    )
                    self.reporter.record_interface_result(result)
                    
                    # 记录接口失败
                    self.checkpoint_manager.record_interface_complete(
                        interface_name,
                        False,
                        str(e)
                    )
                    
                    # 如果不跳过错误，则终止
                    if not self.skip_on_error:
                        logger.error("设置为出错时不跳过，终止更新")
                        break
            
            # 更新完成
            self.reporter.record_update_end()
            
            # 清除断点（如果全部成功）
            result = self._create_result()
            if result.failed_count == 0:
                self.checkpoint_manager.clear_checkpoint()
                logger.info("所有接口更新成功，清除断点记录")
            else:
                # 保存最终断点
                self.checkpoint_manager.save_checkpoint()
            
            # 生成报告
            self._generate_and_save_report(options)
            
            return result
            
        except Exception as e:
            logger.error(f"更新过程中发生异常: {e}")
            self.reporter.record_update_end()
            self.checkpoint_manager.save_checkpoint()
            raise
    
    def update_interface(
        self,
        interface_name: str,
        options: UpdateOptions
    ) -> InterfaceUpdateResult:
        """
        更新单个接口

        Args:
            interface_name: 接口名称
            options: 更新选项

        Returns:
            InterfaceUpdateResult: 接口更新结果
        """
        start_time = time.time()

        try:
            # 获取接口配置
            interface_config = self.config_loader.get_interface_config(interface_name)

            # 计算日期范围
            date_range = self.date_calculator.calculate_update_range(
                interface_name,
                forced_start=options.start_date,
                forced_end=options.end_date
            )

            logger.info(f"开始更新 {interface_name}: {date_range}")

            # 预览模式
            if options.dry_run:
                logger.info(f"[预览模式] 接口 {interface_name} 需要更新: {date_range}")
                return InterfaceUpdateResult(
                    interface_name=interface_name,
                    status=UpdateStatus.SUCCESS,
                    date_range=date_range,
                    skip_reason="预览模式",
                    duration_seconds=time.time() - start_time
                )

            # 【新增】缺口检测：检查是否支持并启用
            if (options.gap_detection_enabled and
                self.coverage_manager and
                self.coverage_manager.is_time_range_mode(interface_name)):

                # 获取交易日历
                trade_calendar = self.downloader.get_trade_calendar(
                    date_range.start_date,
                    date_range.end_date
                )

                if trade_calendar:
                    # 检测缺口
                    from core.coverage_manager import DateRange as GapDateRange
                    gaps = self.coverage_manager.detect_gaps(
                        interface_name=interface_name,
                        target_range=GapDateRange(date_range.start_date, date_range.end_date),
                        trade_calendar=trade_calendar,
                        min_gap_days=options.min_gap_days,
                        max_gaps=options.max_gaps
                    )

                    if not gaps:
                        logger.info(f"接口 {interface_name} 数据已完整，跳过")
                        return InterfaceUpdateResult(
                            interface_name=interface_name,
                            status=UpdateStatus.SKIPPED,
                            date_range=date_range,
                            skip_reason="数据已完整覆盖",
                            duration_seconds=time.time() - start_time
                        )

                    # 逐个下载缺口
                    total_records = 0
                    for i, gap in enumerate(gaps):
                        logger.info(f"下载缺口 [{i+1}/{len(gaps)}]: {gap}")
                        gap_date_range = DateRange(gap.start_date, gap.end_date)
                        records = self._execute_download(
                            interface_name, interface_config, gap_date_range, options
                        )
                        total_records += records

                    duration = time.time() - start_time
                    logger.info(f"接口 {interface_name} 更新完成，共 {total_records} 条记录，耗时 {duration:.2f}秒")

                    return InterfaceUpdateResult(
                        interface_name=interface_name,
                        status=UpdateStatus.SUCCESS,
                        date_range=date_range,
                        record_count=total_records,
                        duration_seconds=duration
                    )
                else:
                    logger.warning(f"无法获取交易日历，回退到原有逻辑")

            # 原有逻辑（缺口检测关闭或不支持时）
            should_update, skip_reason = self.should_update_interface(
                interface_name,
                date_range,
                options
            )

            if not should_update:
                logger.info(f"接口 {interface_name} 已是最新，跳过")
                return InterfaceUpdateResult(
                    interface_name=interface_name,
                    status=UpdateStatus.SKIPPED,
                    date_range=date_range,
                    skip_reason=skip_reason,
                    duration_seconds=time.time() - start_time
                )

            # 执行实际下载
            logger.info(f"开始下载 {interface_name}: {date_range}")
            record_count = self._execute_download(interface_name, interface_config, date_range, options)

            duration = time.time() - start_time
            logger.info(f"接口 {interface_name} 更新完成，共 {record_count} 条记录，耗时 {duration:.2f}秒")

            return InterfaceUpdateResult(
                interface_name=interface_name,
                status=UpdateStatus.SUCCESS,
                date_range=date_range,
                record_count=record_count,
                duration_seconds=duration
            )

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"接口 {interface_name} 更新失败: {e}")
            return InterfaceUpdateResult(
                interface_name=interface_name,
                status=UpdateStatus.FAILED,
                error_message=str(e),
                duration_seconds=duration
            )
    
    def should_update_interface(
        self, 
        interface_name: str, 
        date_range: DateRange,
        options: UpdateOptions
    ):
        """
        判断接口是否需要更新
        
        Args:
            interface_name: 接口名称
            date_range: 日期范围
            options: 更新选项
            
        Returns:
            Tuple[bool, Optional[str]]: (是否需要更新, 跳过原因)
        """
        # 如果强制更新，直接返回需要更新
        if options.force:
            return True, None
        
        # 如果 CoverageManager 不可用，默认需要更新
        if not self.coverage_manager:
            logger.warning(f"CoverageManager 不可用，默认需要更新 {interface_name}")
            return True, None
        
        # 复用 CoverageManager.should_skip() 方法
        params = {
            'start_date': date_range.start_date,
            'end_date': date_range.end_date
        }
        
        try:
            should_skip = self.coverage_manager.should_skip(
                interface_name, 
                params, 
                strategy='auto'
            )
            
            if should_skip:
                return False, "数据已完全覆盖"
            
            return True, None
            
        except Exception as e:
            logger.warning(f"检查接口 {interface_name} 覆盖状态时出错: {e}")
            # 检测失败时，默认继续下载
            return True, None
    
    def _execute_download(
        self,
        interface_name: str,
        interface_config: Dict[str, Any],
        date_range: DateRange,
        options: UpdateOptions
    ) -> int:
        """
        执行下载

        Args:
            interface_name: 接口名称
            interface_config: 接口配置
            date_range: 日期范围
            options: 更新选项

        Returns:
            int: 下载的记录数
        """
        # 构建参数
        params = {
            'start_date': date_range.start_date,
            'end_date': date_range.end_date
        }

        # 先转换旧版分页配置为新版格式
        pagination_config = migrate_legacy_config(interface_config)

        # 获取交易日历和股票列表（如果需要）
        trade_calendar = None
        stock_list = None

        if pagination_config.get('enabled', False):
            # 检查是否需要交易日历
            if pagination_config.get('time_range', {}).get('enabled', False):
                trade_calendar = self.downloader.get_trade_calendar(
                    date_range.start_date,
                    date_range.end_date
                )

            # 检查是否需要股票列表
            if pagination_config.get('stock_loop', {}).get('enabled', False):
                stock_list = self.downloader._get_stock_list()

        # 构建上下文 - 使用 create_context_with_legacy_support 以支持旧版配置格式
        context = create_context_with_legacy_support(
            interface_config=interface_config,
            trade_calendar=trade_calendar,
            stock_list=stock_list,
            coverage_manager=self.coverage_manager,
            force_download=options.force
        )

        # 使用统一的分页执行入口
        result_data = self.pagination_executor.execute(
            interface_config=interface_config,
            base_params=params,
            context=context,
            make_request=self.downloader._make_request,
            coverage_manager=self.coverage_manager
        )

        # 处理和保存数据
        if result_data and len(result_data) > 0:
            # 直接传入原始数据，让 _process_worker 统一处理（包括去重）
            # 避免重复处理：不在此处调用 processor，由 storage 的处理线程完成
            self.storage_manager.save_data(interface_name, result_data, async_write=True)

            return len(result_data)

        return 0
    
    def _create_result(self) -> UpdateResult:
        """创建更新结果对象"""
        return UpdateResult(
            start_time=self.reporter.start_time or datetime.now(),
            end_time=self.reporter.end_time or datetime.now(),
            interface_results=self.reporter.interface_results
        )
    
    def _generate_and_save_report(self, options: UpdateOptions):
        """生成并保存报告"""
        try:
            # 获取报告配置
            update_config = self.config_loader.global_config.get('update', {})
            reporting_config = update_config.get('reporting', {})
            
            if not reporting_config.get('enabled', True):
                return
            
            # 生成报告
            report_content = self.reporter.generate_report(options.report_format)
            
            # 输出到控制台
            if reporting_config.get('console_output', True):
                print("\n" + "=" * 60)
                print(report_content)
                print("=" * 60)
            
            # 保存到文件
            if reporting_config.get('save_report', True) or options.report_file:
                if options.report_file:
                    report_file = options.report_file
                else:
                    # 生成默认文件名
                    report_dir = reporting_config.get('report_dir', 'log/update_reports/')
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"update_report_{timestamp}.{options.report_format.value}"
                    report_file = os.path.join(report_dir, filename)
                
                self.reporter.save_report(report_file, options.report_format)
                
        except Exception as e:
            logger.warning(f"生成报告时出错: {e}")
