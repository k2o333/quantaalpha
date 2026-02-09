# --update 参数实现方案

## 需求概述

在 `app4/main.py` 中添加 `--update` 命令行参数，实现智能增量更新功能：

1. **全接口更新**：所有数据接口都按照各自的配置形态进行下载
2. **智能日期范围**：不输入日期参数时，从股票上市日到今天
3. **增量下载**：只下载未下载过的数据，避免重复下载
4. **容错处理**：支持各种分页模式和参数配置

## 核心设计思路

### 1. 参数设计
```bash
python app4/main.py --update
```

- 启用增量更新模式
- 自动计算日期范围（从最早数据到今天）
- 启用智能去重和覆盖检测

### 2. 实现逻辑

#### 2.1 日期范围智能计算
```python
def _calculate_update_date_range(interface_name: str, interface_config: Dict[str, Any]) -> tuple:
    """
    智能计算更新日期范围
    
    Returns:
        tuple: (start_date, end_date)
    """
    # 1. 检查现有数据的最晚日期
    # 2. 如果无数据，从股票最早上市日期开始
    # 3. 结束日期为今天
    # 4. 特殊接口特殊处理（如trade_cal从1990年开始）
```

#### 2.2 增量检测机制
```python
def _check_existing_coverage(interface_name: str, start_date: str, end_date: str) -> Dict[str, Any]:
    """
    检查现有数据覆盖情况
    
    Returns:
        Dict: {
            'has_data': bool,
            'latest_date': str,
            'missing_ranges': List[tuple],
            'should_download': bool
        }
    """
```

### 3. 代码修改点

#### 3.1 命令行参数添加
在 `main.py` 的 `parse_arguments()` 函数中添加：

```python
parser.add_argument('--update', action='store_true',
                   help='增量更新模式：自动下载所有接口的缺失数据')
```

#### 3.2 主流程修改
在 `main()` 函数中添加 `--update` 处理逻辑：

```python
def main():
    # ... 现有代码 ...
    
    if args.update:
        logger.info("=== 启动增量更新模式 ===")
        return run_update_mode(args, config_loader, downloader, scheduler, 
                             storage_manager, processor, global_rate_limiter)
    
    # ... 现有代码 ...
```

#### 3.3 核心更新函数
```python
def run_update_mode(args, config_loader, downloader, scheduler, 
                   storage_manager, processor, global_rate_limiter):
    """
    执行增量更新模式
    
    核心逻辑：
    1. 获取所有可用接口列表
    2. 对每个接口执行智能更新
    3. 处理不同分页模式的接口
    4. 记录更新结果和统计
    """
    
    # 获取所有接口配置
    all_interfaces = config_loader.get_all_interface_configs()
    
    update_stats = {
        'total_interfaces': len(all_interfaces),
        'processed': 0,
        'updated': 0,
        'skipped': 0,
        'failed': 0,
        'total_records': 0
    }
    
    for interface_name, interface_config in all_interfaces.items():
        try:
            # 智能计算日期范围
            start_date, end_date = _calculate_update_date_range(interface_name, interface_config)
            
            # 检查是否需要更新
            coverage_info = _check_existing_coverage(interface_name, start_date, end_date)
            
            if not coverage_info['should_download']:
                logger.info(f"✅ {interface_name}: 数据已是最新，跳过更新")
                update_stats['skipped'] += 1
                continue
            
            logger.info(f"🔄 {interface_name}: 开始更新 {start_date} 到 {end_date}")
            
            # 执行下载（复用现有逻辑）
            success = _download_interface_data(
                downloader, scheduler, interface_name, interface_config,
                start_date, end_date, storage_manager, processor,
                global_rate_limiter, args
            )
            
            if success:
                update_stats['updated'] += 1
                logger.info(f"✅ {interface_name}: 更新完成")
            else:
                update_stats['failed'] += 1
                logger.error(f"❌ {interface_name}: 更新失败")
                
        except Exception as e:
            update_stats['failed'] += 1
            logger.error(f"❌ {interface_name}: 更新异常 - {e}")
        
        finally:
            update_stats['processed'] += 1
    
    # 输出更新报告
    _print_update_report(update_stats)
```

### 4. 关键技术实现

#### 4.1 现有数据检测
```python
def _get_existing_data_range(interface_name: str, storage_dir: str) -> tuple:
    """
    获取现有数据的日期范围
    
    Returns:
        tuple: (earliest_date, latest_date) 或 (None, None) 如果无数据
    """
    import polars as pl
    
    try:
        # 读取现有parquet文件
        data_path = f"{storage_dir}/{interface_name}"
        if not os.path.exists(data_path):
            return None, None
            
        # 使用Polars读取数据集
        df = pl.read_parquet(data_path)
        
        # 根据接口类型确定日期列
        date_columns = _get_interface_date_columns(interface_name)
        
        if df.is_empty() or not date_columns:
            return None, None
            
        # 获取日期范围
        latest_date = df.select(pl.max(date_columns[0])).item()
        earliest_date = df.select(pl.min(date_columns[0])).item()
        
        return earliest_date, latest_date
        
    except Exception as e:
        logger.warning(f"无法获取 {interface_name} 的现有数据范围: {e}")
        return None, None
```

#### 4.2 接口日期列映射
```python
def _get_interface_date_columns(interface_name: str) -> List[str]:
    """
    获取接口的主要日期列，用于日期范围检测
    """
    date_column_mapping = {
        # 交易相关
        'daily': ['trade_date'],
        'daily_basic': ['trade_date'],
        'adj_factor': ['trade_date'],
        'moneyflow': ['trade_date'],
        
        # 财务相关
        'income': ['end_date'],
        'balancesheet': ['end_date'],
        'cashflow': ['end_date'],
        'fina_indicator': ['end_date'],
        
        # 股东相关
        'top10_holders': ['end_date'],
        'top10_floatholders': ['end_date'],
        'pledge_detail': ['end_date'],
        'stk_rewards': ['end_date'],
        
        # 基础数据
        'trade_cal': ['cal_date'],
        'stock_basic': ['list_date'],  # 特殊处理
        'stock_company': ['setup_date'],  # 特殊处理
        
        # VIP接口
        'income_vip': ['end_date'],
        'balancesheet_vip': ['end_date'],
        'cashflow_vip': ['end_date'],
        'fina_indicator_vip': ['end_date'],
    }
    
    return date_column_mapping.get(interface_name, ['trade_date'])
```

#### 4.3 智能开始日期计算
```python
def _calculate_smart_start_date(interface_name: str) -> str:
    """
    智能计算开始日期
    """
    # 特殊接口的最早日期
    special_dates = {
        'trade_cal': '19900101',  # 交易日历从1990年开始
        'stock_basic': '19900101',  # 股票基础信息
        'stock_company': '19900101',  # 公司基础信息
        'daily': '20000101',  # 日线数据从2000年开始
    }
    
    if interface_name in special_dates:
        return special_dates[interface_name]
    
    # 获取股票最早上市日期
    try:
        df = pl.read_parquet('data/stock_basic')
        if not df.is_empty():
            earliest_list_date = df.select(pl.min('list_date')).item()
            return earliest_list_date.replace('-', '')  # 确保格式为YYYYMMDD
    except:
        pass
    
    # 默认从2000年开始
    return '20000101'
```

### 5. 分页模式处理

#### 5.1 stock_loop 模式
```python
def _handle_stock_loop_update(interface_name: str, interface_config: Dict[str, Any], 
                            start_date: str, end_date: str, args):
    """
    处理stock_loop模式的更新
    """
    # 检查接口是否支持日期参数
    parameter_config = interface_config.get('parameters', {})
    has_start_end = 'start_date' in parameter_config and 'end_date' in parameter_config
    
    if has_start_end:
        # 场景1：直接传递日期参数
        params = {
            'start_date': start_date,
            'end_date': end_date
        }
    else:
        # 场景2：尝试使用日期锚定或全历史更新
        date_anchor_param = None
        for param_name, param_def in parameter_config.items():
            if param_def.get('is_date_anchor', False):
                date_anchor_param = param_name
                break
        
        if date_anchor_param:
            params = {
                'start_date': start_date,
                'end_date': end_date,
                '_date_anchor_param': date_anchor_param
            }
        else:
            # 场景3：全历史更新（依赖覆盖管理去重）
            params = {
                'start_date': start_date,
                'end_date': end_date  # 仍然传递，让系统处理
            }
    
    return params
```

#### 5.2 date_range 模式
```python
def _handle_date_range_update(interface_config: Dict[str, Any], 
                           start_date: str, end_date: str):
    """
    处理date_range模式的更新
    """
    params = {
        'start_date': start_date,
        'end_date': end_date
    }
    
    # 处理窗口大小，避免单次请求过大
    pagination_config = interface_config.get('pagination', {})
    window_size = pagination_config.get('window_size_days', 365)
    
    # 如果日期范围过大，进行分批处理
    if _days_between(start_date, end_date) > window_size * 2:
        return _batch_date_ranges(start_date, end_date, window_size)
    
    return params
```

### 6. 覆盖管理集成

利用现有的 `CoverageManager` 进行智能去重：

```python
def _integrate_coverage_check(interface_name: str, start_date: str, end_date: str, 
                            coverage_manager: CoverageManager) -> tuple:
    """
    集成覆盖管理检查
    
    Returns:
        tuple: (should_download, adjusted_start_date)
    """
    if not coverage_manager:
        return True, start_date
    
    # 检查现有覆盖
    coverage_info = coverage_manager.check_coverage(
        interface_name, start_date, end_date
    )
    
    if coverage_info['fully_covered']:
        return False, None  # 无需下载
    
    # 调整开始日期到缺失数据的起点
    if coverage_info['missing_ranges']:
        first_missing = coverage_info['missing_ranges'][0]
        return True, first_missing[0]
    
    return True, start_date
```

### 7. 报告生成

```python
def _print_update_report(stats: Dict[str, Any]):
    """
    打印更新报告
    """
    logger.info("\n" + "="*60)
    logger.info("📊 增量更新完成报告")
    logger.info("="*60)
    logger.info(f"总接口数量: {stats['total_interfaces']}")
    logger.info(f"已处理: {stats['processed']}")
    logger.info(f"成功更新: {stats['updated']}")
    logger.info(f"跳过(已是最新): {stats['skipped']}")
    logger.info(f"更新失败: {stats['failed']}")
    logger.info(f"总记录数: {stats['total_records']}")
    
    if stats['failed'] > 0:
        logger.warning(f"⚠️  有 {stats['failed']} 个接口更新失败，请检查日志")
    else:
        logger.info("🎉 所有接口更新成功！")
    
    logger.info("="*60)
```

### 8. 使用示例

```bash
# 基础增量更新
python app4/main.py --update

# 增量更新 + 指定股票
python app4/main.py --update --ts_code 000001.SZ

# 增量更新 + 调试模式
python app4/main.py --update --log-level DEBUG

# 增量更新 + 自定义并发
python app4/main.py --update --concurrency 8
```

### 9. 兼容性考虑

1. **与现有参数兼容**：`--update` 可以与 `--ts_code`、`--concurrency` 等参数组合使用
2. **与现有逻辑不冲突**：当使用 `--update` 时，忽略 `--start_date` 和 `--end_date` 参数
3. **错误处理**：如果某个接口更新失败，继续处理其他接口
4. **性能优化**：利用现有的缓存和并发机制

### 10. 实现优先级

1. **高优先级**：核心更新逻辑和日期范围计算
2. **中优先级**：现有数据检测和覆盖管理集成
3. **低优先级**：详细报告和统计功能

---

## 总结

`--update` 参数的实现充分利用了App4现有的架构优势：

- **配置驱动**：根据接口配置自动选择合适的下载策略
- **智能去重**：集成现有的CoverageManager避免重复下载
- **高性能**：利用现有的并发和缓存机制
- **容错性强**：处理各种接口类型和异常情况
- **用户友好**：提供清晰的进度反馈和更新报告

这个实现方案让用户只需一个简单的 `--update` 参数就能实现全系统的智能增量更新。