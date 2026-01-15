# App4 业务逻辑优化方案设计文档

## 1. 核心设计理念

针对现有 SmartRange 逻辑的缺陷，本方案提出 **"覆盖率驱动 (Coverage-Driven)"** 与 **"特征感知 (Feature-Aware)"** 相结合的业务逻辑架构。

*   **覆盖率驱动**: 不再单纯依赖 "Last Update Date"，而是维护一个全局的 `CoverageMap`（数据覆盖图谱），通过对比 `Expected Set`（应有数据集合）与 `Actual Set`（现有数据集合）来精确计算 `Missing Ranges`（缺失区间）。
*   **特征感知**: 针对不同类型的接口（日线行情、财务报表、股东数据），采用不同的完整性校验和更新策略。

## 2. 下载模式设计 (Download Modes)

系统应支持四种原子下载模式，并在配置文件中可针对接口进行指定或切换。

| 模式名称 | 代码标识 | 适用场景 | 逻辑描述 |
| :--- | :--- | :--- | :--- |
| **增量模式** | `incremental` | 日常更新 | 仅下载 `max(local_date)` 之后的数据。包含一个可配置的 `overlap`（回溯窗口）以捕获近期修正。 |
| **补漏模式** | `backfill` | 初始化/修复 | 扫描 `min(start)` 到 `max(end)` 之间的所有空洞（Gaps）并生成下载任务。 |
| **修复模式** | `repair` | 数据修正 | 强制重新下载指定时间段的数据，并执行 `Upsert`（覆盖更新）操作。 |
| **智能模式** | `smart` | 默认推荐 | 结合 `incremental` 和 `backfill`。首先检查头部增量，闲时或周期性检查历史空洞。 |

**配置示例**:
```yaml
interfaces:
  daily:
    download_mode: "smart"
    smart_settings:
      check_gaps_frequency: "weekly" # 每周检查一次历史缺漏
      incremental_overlap: 5         # 每次增量多下载5天以防停牌/修正
```

## 3. 复杂业务场景处理逻辑

### 3.1 数据缺失自动检测与修复 (Gap Detection)

**方案**: 建立 `CoverageManager` 组件。

*   **对于日线类 (Time-Series)**:
    *   依赖 `TradeCalendar` 和 `StockBasic` (上市日期)。
    *   `Expected`: $[ListingDate, Now] \cap TradeDays$
    *   `Actual`: 现有 Parquet 中的日期集合。
    *   `Missing`: $Expected - Actual$。
    *   **优化**: 使用 BitMap 或区间列表 (Interval List) 存储日期，高效运算。

*   **对于报表类 (Reporting)**:
    *   无法预知确切发布日期。
    *   **策略**: 检查 "标准报告期" (3.31, 6.30, 9.30, 12.31) 是否存在。
    *   如果某股票 `20230331` 缺失且 `Now > 20230501` (年报/一季报截止日)，标记为潜在缺失（需考虑退市/延迟披露）。

### 3.2 历史数据修正 (Data Corrections)

财务数据常有 "差错更正" 或 "修正版"。

**方案**:
1.  **基于公告日 (Announce Date) 的版本控制**:
    *   接口主键设为 `[ts_code, end_date, announce_date]`。
    *   同一 `end_date` 可能有多条记录，取 `announce_date` 最大的为最新版。
2.  **回溯更新机制**:
    *   配置 `lookback_window` (如 12个月)。
    *   在执行增量下载时，不仅下载新数据，还请求过去 12 个月的 `Report` 接口，对比本地数据。如果 API 返回了新的 `announce_date` 或数值变更，则更新。

### 3.3 新增历史数据回溯

数据源可能补充上线了 2010 年以前的数据。

**方案**:
*   在 `smart` 模式下，`CoverageManager` 会周期性对比 `StockListingDate`。
*   如果发现 `LocalMinDate > ListingDate`，自动生成 `[ListingDate, LocalMinDate]` 的补漏任务。

### 3.4 多主键与股东数据处理

**多主键去重**:
*   配置文件明确定义 `primary_keys`。
*   存储层（Parquet/Database）在写入时，必须基于 `primary_keys` 进行 Deduplication (保留最新)。
*   **股东数据特例**:
    *   `holders` 接口主键通常是 `[ts_code, end_date, holder_name]`。
    *   **股东改名问题**: 如果 "A公司" 改名为 "B公司"，API 可能作为两条记录返回，或更新历史。
    *   **策略**: 建议引入 ETL 清洗层，维护 `HolderAliasMap`。但在下载层，应严格保持 "原文下载"，即视作不同记录。去重仅针对完全相同的 `[ts_code, end_date, holder_name]`。

## 4. 交易日历优化 (Calendar Awareness)

利用交易日历减少无效请求。

*   **非交易日过滤**: 下载器生成任务前，先查 `TradeCalendar`。如果请求区间 `[D1, D2]` 内无交易日（如春节长假），直接跳过 API 请求。
*   **停牌处理**:
    *   如果某股票在某交易日无数据，需区分是 "缺失" 还是 "停牌"。
    *   建议维护一份 `SuspendTable` (停牌表)。
    *   `Missing = Expected - Actual - Suspensions`。只有真正的 Missing 才触发下载。

## 5. 配置文件结构设计 (Config Schema)

建议采用分层配置，支持全局默认与接口覆盖。

```yaml
global:
  storage:
    format: "parquet"
    compression: "zstd"
  concurrency:
    max_workers: 4

interfaces:
  # === 日线行情 (标准时间序列) ===
  daily:
    api_name: "daily"
    type: "time_series"
    primary_keys: ["ts_code", "trade_date"]
    
    pagination:
      mode: "date_range"
      window_size_days: 3650
    
    completeness:
      rule: "calendar_match" # 必须匹配交易日历
      calendar_type: "SSE"   # 上交所日历
    
    download:
      mode: "smart"
      incremental_overlap: 5 # 增量时多抓5天
  
  # === 财务指标 (存在修正) ===
  fina_indicator:
    api_name: "fina_indicator"
    type: "report"
    primary_keys: ["ts_code", "end_date", "announce_date"] # 包含公告日
    
    pagination:
      mode: "period_range" # 按报告期轮询
    
    completeness:
      rule: "quarterly_check" # 检查每个季度末
    
    download:
      mode: "incremental"
      correction_lookback: "1y" # 每次检查过去1年的财报是否有更新

  # === 股东人数 (多主键) ===
  stk_holdernumber:
    api_name: "stk_holdernumber"
    type: "event"
    primary_keys: ["ts_code", "end_date"]
    
    download:
      mode: "smart"
```

## 6. 伪代码逻辑 (Pseudo-code)

### 智能调度器逻辑

```python
class SmartScheduler:
    def plan_tasks(self, interface_conf):
        # 1. 获取元数据
        listing_dates = get_stock_listing_dates()
        trade_cal = get_trade_calendar()
        local_coverage = coverage_manager.get_coverage(interface_conf.name)
        
        tasks = []
        
        # 2. 遍历所有股票/对象
        for stock in listing_dates:
            expected_ranges = calculate_expected(stock, trade_cal)
            actual_ranges = local_coverage.get(stock.code)
            
            # 3. 计算差异 (Set Difference)
            missing_intervals = expected_ranges - actual_ranges
            
            # 4. 根据模式生成任务
            if interface_conf.mode == 'incremental':
                # 只取 Now 附近的缺失
                tasks.extend(filter_recent(missing_intervals))
                # 添加重叠窗口以检测修正
                tasks.append(create_overlap_task(stock, overlap_days=5))
                
            elif interface_conf.mode == 'backfill':
                # 所有历史缺失都生成任务
                tasks.extend(missing_intervals)
                
            elif interface_conf.mode == 'smart':
                # 优先生成最近的缺失任务 (High Priority)
                recent = filter_recent(missing_intervals)
                priority_queue.push(recent, priority=HIGH)
                
                # 闲时生成历史缺失任务 (Low Priority)
                historical = filter_historical(missing_intervals)
                priority_queue.push(historical, priority=LOW)
                
        return tasks
```

## 7. 数据完整性与质量报告

*   **质量埋点**: 在写入 Parquet 前，统计 `null` 值率、`0` 值率。
*   **完整性报告**: 每次运行后，生成 `Data Quality Report`。
    *   Coverage: 98.5% (Missing 1500 records)
    *   Freshness: Last update 2 hours ago
    *   Anomalies: 5 stocks have huge price jumps (>20%) - *Optional warning*

## 8. 总结

本方案通过引入 `CoverageManager` 和区分 `DownloadMode`，解决了原方案 "无法感知缺失" 和 "无法处理修正" 的核心痛点。通过配置化的策略（如 `correction_lookback` 和 `incremental_overlap`），在性能和数据准确性之间取得了平衡。
