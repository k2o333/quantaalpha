#!/usr/bin/env python3
"""
内存调试版本的 main.py

在 main.py 基础上增加了内存监控功能，用于验证回调机制是否正确释放内存。

前提条件：
  需要先完成 memory_release_solution.md 中的代码修改，确保：
  - pagination_executor.py 支持 on_data_ready 回调
  - downloader.py 支持 on_data_ready 回调
  - main.py 使用回调方式调用下载

使用方法:
    # 复制到 app4 目录
    cp memory_debug_main.py app4/
    cp memory_inspector.py app4/

    # 运行调试
    python memory_debug_main.py --interface cyq_chips --memory-debug
    
    # 启用详细追踪
    python memory_debug_main.py --interface cyq_chips --memory-debug --memory-trace
"""

import sys
import os
import gc
import argparse
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable
import logging

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 先导入 main.py 的所有内容
from main import *

# 导入内存监控工具
from memory_inspector import MemoryInspector, quick_inspect


# 全局内存检查器（用于回调中访问）
_global_inspector: Optional[MemoryInspector] = None


def create_memory_aware_callback(
    storage_manager,
    processor,
    interface_name: str,
    inspector: MemoryInspector
) -> Callable[[str, List[Dict[str, Any]]], None]:
    """
    创建带内存跟踪的数据回调
    
    这是关键：每个请求单元完成后，立即保存数据并释放内存
    """
    def on_data_ready(iface_name: str, data: List[Dict[str, Any]]):
        if not data:
            return
        
        data_id = id(data)
        data_len = len(data)
        
        logger.info(f"[MemoryCallback] 接收到数据: interface={iface_name}, id={data_id}, len={data_len}")
        
        # 跟踪这个数据对象
        inspector.track_data(data, label=f"{iface_name}_data_{data_id}")
        
        # 保存前检查
        inspector.inspect(label=f"{iface_name}_before_save", check_leaks=False)
        
        # 获取接口配置
        try:
            interface_config = storage_manager.config_loader.get_interface_config(iface_name)
        except:
            interface_config = {'api_name': iface_name}
        
        # 处理并保存数据
        try:
            df = processor.process_data(data, interface_config)
            if not df.is_empty():
                storage_manager.save_data(iface_name, df.to_dicts(), async_write=True)
                logger.info(f"[MemoryCallback] 已保存 {len(df)} 条记录")
        except Exception as e:
            logger.error(f"[MemoryCallback] 保存失败: {e}")
        
        # 保存后检查
        inspector.inspect(label=f"{iface_name}_after_save", check_leaks=True)
        
        # 【关键】显式删除引用
        logger.info(f"[MemoryCallback] 显式删除数据引用: id={data_id}")
        del data
        del df if 'df' in dir() else None
        
        # 强制垃圾回收
        gc.collect()
        
        # GC 后检查
        inspector.inspect(label=f"{iface_name}_after_gc", check_leaks=True)
    
    return on_data_ready


def run_download_with_memory_tracking(
    downloader,
    scheduler,
    interface_name: str,
    interface_config: Dict[str, Any],
    params: Dict[str, Any],
    storage_manager,
    processor,
    logger,
    inspector: MemoryInspector
) -> int:
    """
    使用回调机制下载，并跟踪内存
    """
    global _global_inspector
    _global_inspector = inspector
    
    logger.info(f"[MemoryDebug] 开始下载接口: {interface_name}")
    inspector.inspect(label=f"{interface_name}_start")
    
    # 创建带内存跟踪的回调
    callback = create_memory_aware_callback(
        storage_manager, processor, interface_name, inspector
    )
    
    # 检查 downloader 是否支持 on_data_ready 回调
    import inspect
    sig = inspect.signature(downloader.download)
    if 'on_data_ready' in sig.parameters:
        # 【关键】使用回调方式下载
        logger.info(f"[MemoryDebug] 使用回调模式下载（推荐）")
        data = downloader.download(
            interface_name,
            params,
            on_data_ready=callback
        )
        # data 应该为空（数据通过回调保存）
        if data:
            logger.warning(f"[MemoryDebug] 返回了 {len(data)} 条数据，回调可能未生效")
    else:
        # 旧模式：无回调（需要修改代码）
        logger.warning(f"[MemoryDebug] downloader 不支持 on_data_ready 回调")
        logger.warning(f"[MemoryDebug] 请先完成 memory_release_solution.md 中的代码修改！")
        logger.warning(f"[MemoryDebug] 回退到传统模式（内存不会被释放）")
        
        data = downloader.download(interface_name, params)
        if data:
            inspector.track_data(data, label=f"{interface_name}_legacy_data")
            process_and_save_data(
                data, interface_name, interface_config,
                processor, storage_manager, logger
            )
            inspector.inspect(label=f"{interface_name}_after_save_legacy")
            del data
            gc.collect()
            inspector.inspect(label=f"{interface_name}_after_gc_legacy")
    
    # 最终检查
    inspector.inspect(label=f"{interface_name}_complete", check_leaks=True)
    
    return 0


def run_stock_loop_with_memory_tracking(
    downloader,
    scheduler,
    interface_name: str,
    interface_config: Dict[str, Any],
    params_list: List[Dict[str, Any]],
    stock_list: List[Dict[str, Any]],
    storage_manager,
    processor,
    logger,
    context,
    inspector: MemoryInspector
) -> int:
    """
    stock_loop 模式的内存跟踪下载
    """
    global _global_inspector
    _global_inspector = inspector
    
    logger.info(f"[MemoryDebug] stock_loop 模式: {interface_name}, {len(params_list)} 只股票")
    inspector.inspect(label=f"{interface_name}_start")
    
    # 检查 download_single_stock 是否支持回调
    import inspect
    
    # 创建回调
    callback = create_memory_aware_callback(
        storage_manager, processor, interface_name, inspector
    )
    
    total_records = 0
    batch_size = 50  # 每50只股票检查一次内存
    
    for idx, params in enumerate(params_list):
        ts_code = params.get('ts_code', f'unknown_{idx}')
        
        # 下载单只股票
        try:
            # 检查是否支持回调
            sig = inspect.signature(downloader.download_single_stock)
            if 'on_data_ready' in sig.parameters:
                data = downloader.download_single_stock(
                    interface_config, 
                    {'ts_code': ts_code}, 
                    params,
                    context=context,
                    on_data_ready=callback
                )
            else:
                data = downloader.download_single_stock(
                    interface_config,
                    {'ts_code': ts_code},
                    params,
                    context=context
                )
                if data:
                    inspector.track_data(data, label=f"{interface_name}_{ts_code}")
                    process_and_save_data(
                        data, interface_name, interface_config,
                        processor, storage_manager, logger
                    )
                    del data
                    gc.collect()
            
            if data:
                total_records += len(data)
                
        except Exception as e:
            logger.error(f"[MemoryDebug] 下载 {ts_code} 失败: {e}")
        
        # 定期检查内存
        if (idx + 1) % batch_size == 0:
            inspector.inspect(label=f"{interface_name}_batch_{(idx+1)//batch_size}", check_leaks=True)
            logger.info(f"[MemoryDebug] 已处理 {idx + 1}/{len(params_list)} 只股票, 累计记录: {total_records}")
    
    # 最终检查
    inspector.inspect(label=f"{interface_name}_complete", check_leaks=True)
    
    return total_records


def main_with_memory_debug():
    """带内存调试的主函数"""
    
    # 创建参数解析器，继承 main.py 的所有参数
    parser = argparse.ArgumentParser(description="aspipe_v4 内存调试版本")
    
    # 添加 main.py 的所有参数
    parser.add_argument('--start_date', type=str, default=DEFAULT_START_DATE)
    parser.add_argument('--end_date', type=str, default=None)
    parser.add_argument('--holders-data', action='store_true')
    parser.add_argument('--pro-bar-only', action='store_true')
    parser.add_argument('--tscode-historical', action='store_true')
    parser.add_argument('--interface', type=str, nargs='+')
    parser.add_argument('--group', type=str)
    parser.add_argument('--concurrency', type=int, default=4)
    parser.add_argument('--log-level', type=str, default='INFO')
    parser.add_argument('--ts_code', type=str)
    parser.add_argument('--update', action='store_true')
    parser.add_argument('--update-interface', type=str, action='append', dest='update_interfaces')
    parser.add_argument('--update-group', type=str, action='append', dest='update_groups')
    parser.add_argument('--update-force', action='store_true', dest='update_force')
    
    # 内存调试专用参数
    parser.add_argument('--memory-debug', action='store_true',
                        help='启用内存调试模式')
    parser.add_argument('--memory-trace', action='store_true',
                        help='启用 tracemalloc 详细追踪')
    parser.add_argument('--memory-interval', type=float, default=5.0,
                        help='内存检查间隔（秒）')
    
    args = parser.parse_args()
    
    if not args.memory_debug:
        # 非调试模式，调用原始 main
        return main()
    
    # 内存调试模式
    print("="*60)
    print("  内存调试模式已启用")
    print("  验证回调机制是否正确释放内存")
    print("="*60)
    
    # 初始化内存检查器
    inspector = MemoryInspector(enable_tracemalloc=args.memory_trace)
    
    # 初始检查
    inspector.inspect(label="program_start")
    
    # 设置日志
    user_provided_start_date = '--start_date' in sys.argv
    user_provided_end_date = '--end_date' in sys.argv
    user_provided_dates = user_provided_start_date or user_provided_end_date
    setattr(args, 'user_provided_dates', user_provided_dates)
    
    # 初始化配置
    config_dir_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
    config_loader = ConfigLoader(config_dir=config_dir_path)
    
    if not config_loader.validate_config():
        print("Configuration validation failed")
        return 1
    
    logging_config = config_loader.global_config.get('logging', {})
    if args.log_level:
        logging_config['level'] = args.log_level
    setup_logging(logging_config)
    
    logger = logging.getLogger(__name__)
    logger.info("Starting aspipe_v4 with MEMORY DEBUG MODE")
    
    # 创建组件
    components = create_app_components(config_loader, args)
    
    # 检查点
    inspector.inspect(label="components_initialized")
    
    # 启动组件
    components.scheduler.start()
    components.storage_manager.start_writer()
    
    inspector.inspect(label="components_started")
    
    try:
        # 确定要执行的接口
        interfaces_to_run = []
        
        if args.tscode_historical:
            tscode_historical_group = config_loader.global_config.get('groups', {}).get('tscode_historical', [])
            interfaces_to_run.extend(tscode_historical_group)
        
        if args.pro_bar_only:
            interfaces_to_run.append('pro_bar')
        
        if args.holders_data:
            holders_group = config_loader.global_config.get('groups', {}).get('holders', [])
            interfaces_to_run.extend(holders_group)
        
        if args.interface:
            interfaces_to_run.extend(args.interface)
        
        if args.group:
            groups = config_loader.global_config.get('groups', {})
            if args.group in groups:
                interfaces_to_run.extend(groups[args.group])
        
        if not interfaces_to_run:
            available_interfaces = config_loader.get_available_interfaces()
            tscode_historical_group = config_loader.global_config.get('groups', {}).get('tscode_historical', [])
            interfaces_to_run = [iface for iface in available_interfaces if iface not in tscode_historical_group and iface != 'pro_bar']
        
        logger.info(f"[MemoryDebug] 要运行的接口: {interfaces_to_run}")
        
        # 预加载交易日历
        preload_global_trade_calendar(components.downloader, components.storage_manager, logger)
        inspector.inspect(label="after_preload")
        
        # 执行下载任务
        for interface_name in interfaces_to_run:
            try:
                logger.info(f"\n{'='*60}")
                logger.info(f"[MemoryDebug] 开始处理接口: {interface_name}")
                logger.info(f"{'='*60}")
                
                interface_config = config_loader.get_interface_config(interface_name)
                
                # 检查积分
                min_points = interface_config.get('permissions', {}).get('min_points', 0)
                actual_points = int(os.getenv('TUSHARE_POINTS', '120'))
                if min_points > actual_points:
                    logger.warning(f"积分不足: {interface_name} (需要 {min_points}, 有 {actual_points})")
                    continue
                
                # 检查接口类型
                tscode_historical_group = config_loader.global_config.get('groups', {}).get('tscode_historical', [])
                is_tscode_historical = interface_name in tscode_historical_group
                
                # 准备日期
                loop_start_date = args.start_date
                loop_end_date = args.end_date
                
                if is_tscode_historical and not user_provided_dates and interface_name != 'disclosure_date':
                    if loop_start_date == DEFAULT_START_DATE and loop_end_date is None:
                        loop_start_date = HISTORICAL_START_DATE
                        loop_end_date = datetime.now().strftime('%Y%m%d')
                
                loop_start_date, loop_end_date = validate_and_adjust_date(loop_start_date, loop_end_date)
                
                # 构建参数
                builder = ParamsBuilder(interface_config)
                result = builder.build(args, date_range={
                    'start_date': loop_start_date,
                    'end_date': loop_end_date
                })
                
                inspector.inspect(label=f"{interface_name}_params_built")
                
                # 根据类型执行下载
                if result.requires_stock_loop:
                    # 股票循环模式
                    stock_list = _prepare_stock_list(
                        components.downloader, args, result.params, 
                        components.storage_manager, logger
                    )
                    
                    if stock_list is None:
                        logger.warning(f"无法获取股票列表: {interface_name}")
                        continue
                    
                    inspector.inspect(label=f"{interface_name}_stock_list_ready")
                    
                    params_list, context = builder.build_params_list(result, stock_list)
                    
                    # 使用带内存监控的下载函数
                    downloaded_count = run_stock_loop_with_memory_tracking(
                        components.downloader, components.scheduler, 
                        interface_name, interface_config, params_list, 
                        stock_list, components.storage_manager, 
                        components.processor, logger, context, inspector
                    )
                    
                    logger.info(f"[MemoryDebug] {interface_name} 下载完成: {downloaded_count} 条记录")
                    
                else:
                    # 普通下载模式
                    run_download_with_memory_tracking(
                        components.downloader, components.scheduler,
                        interface_name, interface_config, result.params,
                        components.storage_manager, components.processor,
                        logger, inspector
                    )
                
                # 接口完成后检查
                inspector.inspect(label=f"{interface_name}_interface_complete")
                
            except Exception as e:
                logger.exception(f"[MemoryDebug] 处理接口 {interface_name} 时出错: {e}")
                inspector.inspect(label=f"{interface_name}_error")
        
        # 所有接口完成
        inspector.inspect(label="all_interfaces_complete")
        
    except KeyboardInterrupt:
        logger.warning("\n用户手动中断")
        inspector.inspect(label="interrupted")
    except Exception as e:
        logger.exception(f"发生错误: {e}")
        inspector.inspect(label="error")
    finally:
        # 清理
        logger.info("正在清理...")
        components.scheduler.stop()
        components.storage_manager.stop_writer()
        
        inspector.inspect(label="cleanup_complete")
        
        # 最终报告
        final_report = inspector.get_memory_report()
        logger.info("\n" + "="*60)
        logger.info("  最终内存报告")
        logger.info("="*60)
        logger.info(final_report)
        
        # 保存最终报告
        final_report_file = f"log/memory_final_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        os.makedirs(os.path.dirname(final_report_file), exist_ok=True)
        with open(final_report_file, 'w') as f:
            f.write(final_report)
        logger.info(f"[MemoryDebug] 最终报告已保存: {final_report_file}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main_with_memory_debug())