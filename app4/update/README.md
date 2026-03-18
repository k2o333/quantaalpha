# App4 增量更新模块使用指南

## 快速开始

### 1. 基础用法：更新所有接口
```bash
python app4/main.py --update
```

### 2. 指定特定接口
```bash
python app4/main.py --update --update-interface daily_basic --update-interface moneyflow
```

### 3. 指定接口组
```bash
python app4/main.py --update --update-group daily --update-group financial_vip
```

### 4. 排除特定接口
```bash
python app4/main.py --update --update-exclude stock_basic --update-exclude trade_cal
```

### 5. 强制更新（忽略现有数据）
```bash
python app4/main.py --update --update-force
```

### 6. 预览模式（不实际执行）
```bash
python app4/main.py --update --update-dry-run
```

### 7. 生成JSON报告
```bash
python app4/main.py --update --update-report-format json --update-report-file update_result.json
```

### 8. 组合使用
```bash
python app4/main.py --update \
    --update-group daily \
    --update-exclude daily_basic \
    --update-report-format markdown \
    --update-report-file reports/update_$(date +%Y%m%d).md
```

## 配置说明

### settings.yaml 中的 update 配置

```yaml
update:
  enabled: true

  # 默认更新策略
  default_strategy:
    start_date: "20000101"      # 默认起始日期
    lookback_days: 7            # 回溯天数（处理数据延迟）
    end_date: "today"           # 结束日期

  # 特殊接口配置
  special_interfaces:
    trade_cal:
      start_date: "19900101"
      date_column: "cal_date"
    daily:
      start_date: "20000101"
      date_column: "trade_date"

  # 排除接口（不自动更新）
  excluded_interfaces:
    - stock_basic
    - trade_cal

  # 更新顺序
  update_order:
    - trade_cal
    - stock_basic
    - daily
    - daily_basic
    # ...

  # 报告配置
  reporting:
    enabled: true
    output_format: "markdown"
    save_report: true
    report_dir: "log/update_reports/"

  # 断点续传配置
  checkpoint:
    enabled: true
    file: "data/.update_checkpoint.json"
    interval: 10
    auto_resume: true
```

## 断点续传

增量更新模块支持断点续传功能：

1. **自动恢复**：如果之前的更新中断了，再次运行 `--update` 会自动恢复进度
2. **强制重新开始**：使用 `--update-force` 忽略断点，从头开始
3. **配置控制**：在 `settings.yaml` 中配置 `checkpoint.enabled: false` 可禁用断点续传

## 报告格式

支持三种报告格式：

- **markdown**（默认）：适合人工阅读
- **json**：适合程序处理
- **html**：适合网页展示

## 与旧版参数兼容

`--incremental` 参数仍然可用，但会显示弃用警告：

```bash
python app4/main.py --incremental  # 等同于 --update
```

## 注意事项

1. **首次更新**：如果没有现有数据，会从配置的默认起始日期开始下载
2. **增量更新**：会检测现有数据的最新日期，从该日期开始更新
3. **数据回溯**：默认回溯7天，处理数据延迟问题（可在配置中调整）
4. **容错处理**：单个接口失败不会中断整个更新流程

## 测试

运行测试：

```bash
cd app4
python3 test/test_update_simple.py
```

## 故障排查

### 问题：更新被跳过
- 检查数据是否已经是最新
- 使用 `--update-force` 强制更新
- 检查 `settings.yaml` 中的 `excluded_interfaces` 配置

### 问题：断点续传不工作
- 检查 `data/.update_checkpoint.json` 文件是否存在
- 确认 `checkpoint.enabled` 设置为 `true`
- 使用 `--update-force` 清除断点重新开始

### 问题：接口权限不足
- 检查 `TUSHARE_POINTS` 环境变量
- 查看接口配置中的 `min_points` 要求
