# 性能报告生成开关解决方案

## 问题描述

当前 aspipe_v4 项目中，性能报告的生成是硬编码在代码中的，位于 `app4/main.py` 文件的 `finally` 块中。无论什么情况下，程序结束时都会生成性能报告，没有提供开关来控制这一行为。

在 `/home/quan/testdata/aspipe_v4/app4/main.py` 文件中，有以下代码段：

```python
# 生成性能报告
if 'print_performance_report' in locals():
    print_performance_report()

# 保存性能报告到文件
if 'downloader' in locals() and hasattr(downloader, 'performance_monitor') and downloader.performance_monitor:
    import os
    from datetime import datetime
    # 确保日志目录存在
    log_dir = os.path.dirname(logging_config.get('file', 'log/app4.log'))
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    performance_file = os.path.join(log_dir, f"performance_report_{timestamp}.md")
    downloader.performance_monitor.save_report(performance_file)
    logger.info(f"性能报告已生成: {performance_file}")
```

这段代码会在程序结束时**始终执行**，无论什么情况下都会生成性能报告。

## 解决方案

为了提供更好的灵活性，建议添加一个开关来控制性能报告的生成。结合配置文件和命令行参数，提供最大的灵活性，并解决代码质量和配置层级设计问题：

### 1. 修改配置文件

修改 `/home/quan/testdata/aspipe_v4/app4/config/settings.yaml`，添加独立的 performance 配置块：

```yaml
logging:
  level: "INFO"
  file: "log/app4.log"
  max_size_mb: 100
  backup_count: 5
  verbose_dedup: true  # 启用详细去重日志

# 新增：性能监控和报告配置
performance:
  enabled: true                    # 是否启用性能监控
  auto_generate_report: true       # 程序结束时自动生成报告
  output_format: "markdown"        # 输出格式: markdown, json, html
  output_dir: "log/"               # 报告输出目录
  report_filename_prefix: "performance_report"
```

### 2. 添加命令行参数

在 `main()` 函数的参数解析部分添加：

```python
parser.add_argument('--no-performance-report', action='store_true',
                    help='禁用性能报告生成')
parser.add_argument('--performance-report-dir', type=str,
                    help='指定性能报告输出目录')
```

### 3. 修改性能报告生成逻辑

首先，在 main() 函数开始处初始化性能监控器状态：

```python
def main():
    # ... 现有代码 ...

    # 初始化性能监控器
    performance_config = config_loader.global_config.get('performance', {})
    performance_enabled = performance_config.get('enabled', True)

    # ... 现有代码 ...

    # 在下载器初始化时确保性能监控器被创建
    if performance_enabled:
        downloader = GenericDownloader(
            config_loader=config_loader,
            storage_manager=storage_manager,
            trade_calendar_cache=trade_cal_cache,  # 传递交易日历缓存
            stock_list_cache=stock_list_cache,      # 传递股票列表缓存
            force_download=args.force,              # 传递强制下载标志
            incremental_mode=args.incremental       # 传递增量模式标志
        )
    else:
        # 如果性能监控被禁用，创建不带性能监控的下载器
        downloader = GenericDownloader(
            config_loader=config_loader,
            storage_manager=storage_manager,
            trade_calendar_cache=trade_cal_cache,
            stock_list_cache=stock_list_cache,
            force_download=args.force,
            incremental_mode=args.incremental
        )
        # 显式禁用性能监控
        downloader.performance_monitor = None
```

然后，将 `main.py` 文件末尾的 `finally` 块中的性能报告生成代码替换为：

```python
# 检查命令行参数和配置文件双重控制
perf_report_enabled = (
    performance_config.get('auto_generate_report', True) and
    not args.no_performance_report
)

# 生成性能报告
if perf_report_enabled and performance_enabled:
    print_performance_report()

# 保存性能报告到文件
if (perf_report_enabled and performance_enabled and
    'downloader' in locals() and
    hasattr(downloader, 'performance_monitor') and
    downloader.performance_monitor):

    import os
    from datetime import datetime

    # 使用配置的输出目录，或命令行参数覆盖，或默认目录
    report_dir = getattr(args, 'performance_report_dir', None)
    if not report_dir:
        report_dir = performance_config.get('output_dir', 'log/')

    os.makedirs(report_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    filename_prefix = performance_config.get('report_filename_prefix', 'performance_report')
    output_format = performance_config.get('output_format', 'markdown')

    if output_format == 'json':
        performance_file = os.path.join(report_dir, f"{filename_prefix}_{timestamp}.json")
    else:  # 默认为 markdown
        performance_file = os.path.join(report_dir, f"{filename_prefix}_{timestamp}.md")

    downloader.performance_monitor.save_report(performance_file)
    logger.info(f"性能报告已生成: {performance_file}")
```

### 4. 优化性能监控器类

为了更好地支持配置，可以在 `performance_monitor.py` 中添加对不同输出格式的支持：

```python
def save_report(self, filepath: str):
    """保存详细报告"""
    summary = self.get_summary()

    # 根据文件扩展名确定输出格式
    if filepath.endswith('.json'):
        self._save_json_report(filepath, summary)
    else:  # 默认为 markdown
        self._save_markdown_report(filepath, summary)

def _save_markdown_report(self, filepath: str, summary: Dict[str, Any]):
    """保存 Markdown 格式的报告"""
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("# 性能监控报告\n\n")
        f.write(f"生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"总运行时间: {time.time() - self.start_time:.2f}秒\n")
        f.write(f"总请求数: {len(self.metrics)}\n\n")

        for interface, stats in summary.items():
            f.write(f"## 接口: {interface}\n")
            f.write(f"- 请求次数: {stats['total_requests']}\n")
            f.write(f"- 总记录数: {stats['total_records']}\n")
            f.write(f"- 总耗时: {stats['total_time']:.2f}秒\n")
            f.write(f"- 成功率: {stats['success_rate']:.1f}%\n")
            f.write(f"- 平均请求时间: {stats['avg_duration']:.2f}秒\n")
            f.write(f"- P50/P90/P99: {stats['p50_duration']:.2f}/{stats['p90_duration']:.2f}/{stats['p99_duration']:.2f}秒\n")
            f.write(f"- 平均记录数: {stats['avg_records']:.0f}条\n\n")

    logger.info(f"性能报告已保存: {filepath}")

def _save_json_report(self, filepath: str, summary: Dict[str, Any]):
    """保存 JSON 格式的报告"""
    import json

    report_data = {
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'total_runtime_seconds': time.time() - self.start_time,
        'total_requests': len(self.metrics),
        'summary': summary,
        'raw_metrics': [
            {
                'interface': metric.interface,
                'duration': metric.duration,
                'record_count': metric.record_count,
                'retry_count': metric.retry_count,
                'window_start': metric.window_start,
                'window_end': metric.window_end,
                'timestamp': metric.timestamp
            } for metric in self.metrics
        ]
    }

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)

    logger.info(f"JSON性能报告已保存: {filepath}")
```

## 使用说明

### 通过配置文件控制

编辑 `settings.yaml` 文件，设置：

```yaml
performance:
  enabled: false                   # 完全禁用性能监控
  # 或者只禁用自动生成报告
  auto_generate_report: false      # 禁用程序结束时自动生成报告
  output_format: "markdown"        # 输出格式: markdown, json
  output_dir: "log/"               # 报告输出目录
  report_filename_prefix: "performance_report"
```

### 通过命令行参数控制

运行程序时添加参数：

```bash
# 禁用性能报告
python app4/main.py --no-performance-report

# 指定报告输出目录
python app4/main.py --performance-report-dir ./custom_reports

# 或者与其他参数一起使用
python app4/main.py --interface daily --no-performance-report --performance-report-dir ./daily_reports
```

### 双重控制逻辑

当同时设置了配置文件和命令行参数时，命令行参数优先级更高：

- `performance.auto_generate_report: true` + `--no-performance-report` = 不生成报告
- `performance.auto_generate_report: false` + （无命令行参数） = 不生成报告
- `performance.auto_generate_report: true` + （无命令行参数） = 生成报告
- 命令行参数 `--performance-report-dir` 会覆盖配置文件中的 `output_dir` 设置

## 实施步骤

1. **修改配置文件**：
   在 `settings.yaml` 中添加 `performance` 配置块

2. **修改 main.py 文件**：
   - 在参数解析部分添加 `--no-performance-report` 和 `--performance-report-dir` 参数
   - 更新性能监控器初始化逻辑
   - 更新性能报告生成逻辑，加入配置检查

3. **优化 performance_monitor.py 文件**：
   - 添加对不同输出格式的支持（JSON、Markdown）

4. **测试**：
   - 设置 `performance.auto_generate_report: false`，确认不生成报告
   - 使用 `--no-performance-report` 参数，确认不生成报告
   - 正常运行，确认仍能生成报告
   - 测试不同输出格式和目录设置

## 优势

1. **解决代码质量问题**：消除使用 `locals()` 检查变量的做法，改用明确的配置和状态变量
2. **改进配置层级设计**：将性能相关配置独立到专门的 `performance` 块中
3. **灵活性**：用户可以根据需要开启或关闭性能报告生成
4. **扩展性**：支持多种输出格式和自定义输出目录
5. **兼容性**：默认值保持原有行为，确保向后兼容
6. **双重控制**：同时支持配置文件和命令行参数控制
7. **易用性**：不需要修改代码即可控制功能

## 注意事项

1. 确保默认值保持原有行为，以保持向后兼容性
2. 测试各种组合场景，确保逻辑正确
3. 文档化新添加的配置项和命令行参数
4. 更新性能监控器类以支持多种输出格式