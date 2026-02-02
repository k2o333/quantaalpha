# aspipe_v4 - 配置驱动架构

## 概述

aspipe_v4 是一个现代化的、配置驱动的金融数据管道系统，专为高效下载和处理大量金融数据而设计。

## 新特性：反向日期范围分页模式

在最新版本中，我们引入了 `reverse_date_range` 分页模式，它具有以下优势：

### 特性
1. **从最近日期开始下载**：优先获取最新数据，满足实时性需求
2. **智能窗口管理**：支持可配置的窗口大小（默认30天）
3. **自动终止机制**：当连续N天（默认90天）无数据时自动停止下载
4. **覆盖率检查**：支持跳过已下载的窗口，避免重复下载

### 配置示例

在接口配置文件中启用反向日期范围分页：

```yaml
pagination:
  enabled: true
  mode: reverse_date_range    # 启用反向日期范围模式
  window_size_days: 30        # 每30天一个窗口
  empty_threshold_days: 90    # 连续90天无数据时停止
```

### 使用场景

- **高频数据更新**：优先下载最新数据，快速获得最新市场信息
- **历史数据补全**：从最近日期向前逐步补全历史数据
- **资源优化**：避免从最早日期开始下载大量不需要的数据

## 安装和使用

### 环境要求
- Python 3.8+
- Tushare Pro 账户和API Token

### 配置
1. 复制 `.env.example` 为 `.env`
2. 在 `.env` 中填入您的 Tushare Token

### 运行示例
```bash
# 使用反向日期范围模式下载日线数据
python example_reverse_pagination.py --interface daily --start_date 20230101 --end_date 20231231 --ts_code 000001.SZ
```

## 架构特点

1. **配置驱动**：所有接口行为通过YAML配置文件定义
2. **模块化设计**：分页、下载、存储、处理等功能解耦
3. **智能缓存**：多层缓存机制提升性能
4. **并发处理**：支持多线程下载提高效率
5. **数据去重**：内置重复数据检测和去除功能

## 分页模式

系统支持多种分页模式：
- `offset`：偏移量分页
- `date_range`：日期范围分页
- `stock_loop`：股票循环分页
- `period_range`：报告期范围分页
- `quarterly_range`：季度范围分页
- `periodic_range`：周期性范围分页
- `date_range_daily`：每日范围分页
- `reverse_date_range`：反向日期范围分页（新）

## 贡献

欢迎提交Issue和Pull Request来改进项目。