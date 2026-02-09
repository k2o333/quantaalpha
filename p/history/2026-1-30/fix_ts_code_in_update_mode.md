# Update 模式 ts_code 参数修复方案

## 问题描述

在使用 `--update` 模式时，即使用户通过 `--ts_code` 参数指定了单只股票代码，程序仍然会下载所有股票（5479只）的数据，而不是仅下载指定股票的数据。

### 复现命令
```bash
python app4/main.py --update --start_date 20250401 --interface disclosure_date --ts_code 000001.SZ
```

**预期行为**：只下载 `000001.SZ` 这一只股票的数据  
**实际行为**：下载了全部 5479 只股票的数据

## 问题根因分析

### 1. 普通模式（非 --update）的处理逻辑

在普通下载模式下（`main.py:701-725`），`_prepare_stock_list` 函数会检查 `params` 中是否有 `ts_code` 参数，如果有则过滤股票列表：

```python
def _prepare_stock_list(downloader, args, params):
    """统一的股票列表准备方法"""
    # 获取股票列表...
    stock_list = downloader._get_stock_list_from_data_dir()
    
    # 如果参数中指定了股票代码，则只下载该股票
    if 'ts_code' in params:
        target_code = params['ts_code']
        stock_list = [stock for stock in stock_list if stock['ts_code'] == target_code]
        logger.info(f"Filtered to specific stock: {target_code}, {len(stock_list)} stocks remaining")
    
    return stock_list
```

### 2. Update 模式的缺失

在 Update 模式下（`update_manager.py:403-473`），`_execute_download` 方法虽然复用了 `downloader._get_stock_list()` 获取股票列表，但**没有**在获取后根据 `ts_code` 进行过滤：

```python
def _execute_download(self, interface_name, interface_config, date_range, options):
    # ...
    # 检查是否需要股票列表
    if pagination_config.get('stock_loop', {}).get('enabled', False):
        stock_list = self.downloader._get_stock_list()  # 获取所有股票，没有过滤！
    # ...
```

### 3. UpdateOptions 缺少 ts_code 字段

`UpdateOptions` 模型（`update/models.py:46-75`）中没有定义 `ts_code` 字段，导致即使用户传入了 `--ts_code` 参数，也无法传递到更新流程中。

## 修复方案（方案1）

此方案改动最小，只在必要的位置添加过滤逻辑。

### 步骤1：在 UpdateOptions 中添加 ts_code 字段

**文件**：`app4/update/models.py`

在 `UpdateOptions` 类中添加 `ts_code` 字段：

```python
@dataclass
class UpdateOptions:
    """更新选项"""
    # 接口选择
    interfaces: Optional[List[str]] = None
    exclude: List[str] = field(default_factory=list)
    groups: List[str] = field(default_factory=list)

    # 日期范围（强制指定时覆盖智能计算）
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    
    # 股票代码过滤（新增）
    ts_code: Optional[str] = None  # 指定股票代码，只更新该股票

    # 更新模式
    force: bool = False
    dry_run: bool = False
    
    # ... 其他字段保持不变
```

### 步骤2：在 run_update_mode 中传递 ts_code 参数

**文件**：`app4/main.py`

在 `run_update_mode` 函数（约第209-221行）中，创建 `UpdateOptions` 时添加 `ts_code` 参数：

```python
update_options = UpdateOptions(
    interfaces=interfaces_to_update,
    exclude=args.update_exclusions if hasattr(args, 'update_exclusions') else [],
    groups=args.update_groups if hasattr(args, 'update_groups') else [],
    start_date=args.start_date if args.start_date != '20230101' else None,
    end_date=args.end_date,
    ts_code=args.ts_code,  # 新增：传递 ts_code 参数
    force=args.update_force if hasattr(args, 'update_force') else False,
    dry_run=args.update_dry_run if hasattr(args, 'update_dry_run') else False,
    report_format=ReportFormat(args.update_report_format) if hasattr(args, 'update_report_format') else ReportFormat.MARKDOWN,
    report_file=args.update_report_file if hasattr(args, 'update_report_file') else None,
    max_workers=config_loader.global_config.get('concurrency', {}).get('max_workers', 4),
    log_level=args.log_level
)
```

### 步骤3：在 _execute_download 中复用普通模式的参数处理逻辑

**文件**：`app4/update/update_manager.py`

在 `_execute_download` 方法中，需要同时实现：
1. **日期参数智能处理**：根据接口配置决定如何传递日期参数（复用普通模式逻辑）
2. **ts_code 股票过滤**：根据 ts_code 过滤股票列表

修改后的完整代码：

```python
def _execute_download(
    self,
    interface_name: str,
    interface_config: Dict[str, Any],
    date_range: DateRange,
    options: UpdateOptions
) -> int:
    """
    执行下载
    """
    # ========== 1. 智能日期参数处理（复用普通模式逻辑）==========
    parameter_config = interface_config.get('parameters', {})
    has_start_end = 'start_date' in parameter_config and 'end_date' in parameter_config
    
    # 检查是否有日期锚定参数
    date_anchor_param = None
    for param_name, param_def in parameter_config.items():
        if param_def.get('is_date_anchor', False):
            date_anchor_param = param_name
            break
    
    # 根据接口支持的参数类型构建参数
    if has_start_end:
        # 场景1：接口支持 start_date/end_date
        params = {
            'start_date': date_range.start_date,
            'end_date': date_range.end_date
        }
        logger.info(f"Using start_date/end_date for {interface_name}: {date_range.start_date} - {date_range.end_date}")
    elif date_anchor_param:
        # 场景2：接口使用日期锚定参数
        params = {
            'start_date': date_range.start_date,
            'end_date': date_range.end_date,
            '_date_anchor_param': date_anchor_param  # 内部标记，用于分页执行器
        }
        logger.info(f"Using date anchor parameter '{date_anchor_param}' for {interface_name}: {date_range.start_date} - {date_range.end_date}")
    else:
        # 场景3：接口不支持日期参数
        params = {}
        logger.info(f"No date parameters for {interface_name}, fetching full history")
    
    # 如果指定了 ts_code，添加到参数中
    if options.ts_code:
        params['ts_code'] = options.ts_code
    
    # 先转换旧版分页配置为新版格式
    pagination_config = migrate_legacy_config(interface_config)
    
    # ========== 2. 获取并过滤股票列表 ==========
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
            
            # 新增：如果指定了 ts_code，过滤股票列表
            if options.ts_code:
                original_count = len(stock_list)
                stock_list = [s for s in stock_list if s.get('ts_code') == options.ts_code]
                logger.info(f"根据 ts_code={options.ts_code} 过滤股票列表: {original_count} -> {len(stock_list)} 只")
    
    # 构建上下文
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
        self.storage_manager.save_data(interface_name, result_data, async_write=True)
        return len(result_data)
    
    return 0
```

## 修改文件清单

| 文件路径 | 修改类型 | 说明 |
|---------|---------|------|
| `app4/update/models.py` | 新增字段 | 在 `UpdateOptions` 中添加 `ts_code` 字段 |
| `app4/main.py` | 新增参数 | 在 `run_update_mode` 中传递 `ts_code` 给 `UpdateOptions` |
| `app4/update/update_manager.py` | 重构逻辑 | 1. 复用普通模式的日期参数处理逻辑<br>2. 根据 `ts_code` 过滤股票列表 |

## 验证方法

修复后，运行以下命令验证：

```bash
python app4/main.py --update --start_date 20250401 --interface disclosure_date --ts_code 000001.SZ
```

**预期输出**：
```
根据 ts_code=000001.SZ 过滤股票列表: 5479 -> 1 只
```

## 注意事项

1. **向后兼容**：`ts_code` 字段为可选参数，不指定时行为与之前一致（下载所有股票）
2. **日志记录**：添加了过滤前后的股票数量日志，便于排查问题
3. **与其他功能的兼容性**：此修复不影响其他功能（如缺口检测、断点续传等）
4. **日期参数处理一致性**：Update 模式现在与普通模式使用相同的日期参数处理逻辑，确保接口配置被正确解析

## 技术说明

### 为什么要复用普通模式的日期参数处理？

普通模式（`main.py:813-870`）的日期参数处理更加精细：

1. **检查接口参数配置**：读取 `interface_config['parameters']` 确定接口支持的参数
2. **区分三种场景**：
   - 支持 `start_date`/`end_date`：直接传递
   - 使用日期锚定参数（如 `ann_date`）：传递 `_date_anchor_param` 标记
   - 不支持日期参数：不传递日期范围

Update 模式原来直接传递 `start_date`/`end_date`，对于 `disclosure_date` 这类使用日期锚定参数的接口会导致 API 返回空结果。

### 修改后的参数传递流程

```
用户命令行参数
    ↓
main.py: run_update_mode()
    ↓ 创建 UpdateOptions（包含 ts_code, start_date, end_date）
update_manager.py: run_update()
    ↓ 计算日期范围
update_manager.py: update_interface()
    ↓ 根据接口配置智能处理参数
update_manager.py: _execute_download()
    ↓ 构建 params（支持三种场景）
    ↓ 过滤 stock_list（如果指定了 ts_code）
pagination_executor.execute()
```
