# SmartRange 智能增量下载方案

## 1. 方案概述

### 1.1 核心思想

SmartRange 不是简单地判断"是否跳过下载"，而是**智能调整 API 请求的参数范围**，只下载增量数据。

### 1.2 方案对比

| 方案 | 判断逻辑 | API 请求 | 内存占用 | 适用场景 |
|------|---------|---------|---------|---------|
| **CoverageManager（现有）** | 是否跳过？<br>是/否 | 完整范围<br>或跳过 | 低（只读日期列） | 全量更新 |
| **PreDownloadChecker（原方案）** | 过滤已存在记录 | 完整范围<br>然后过滤 | 高（预加载所有主键） | 主键去重 |
| **SmartRange（新方案）** | 调整起始日期 | 增量范围<br>（max_date + 1） | 极低（只读最大值） | 增量更新 |

### 1.3 核心优势

1. **极低的内存占用**：只读取最大日期，内存占用 ~1-10 MB
2. **极快的启动速度**：查询最大值 < 1 秒
3. **智能的 API 节省**：直接调整请求参数，只下载增量数据
4. **适用于所有接口**：支持日期范围、报告期、元数据等接口

---

## 2. 工作流程

### 2.1 场景 1: 首次下载（无历史数据）

```
现有数据: 无
请求参数: start_date=20200101, end_date=20241231

SmartRange 检查:
  - 读取现有数据的最大日期: None
  - 判断: 首次下载，无需调整
  - 返回: start_date=20200101, end_date=20241231

API 请求: 下载 2020-01-01 到 2024-12-31 的全部数据
```

### 2.2 场景 2: 增量更新（有历史数据）

```
现有数据: 2020-01-01 到 2024-06-30
请求参数: start_date=20200101, end_date=20241231

SmartRange 检查:
  - 读取现有数据的最大日期: 20240630
  - 计算增量起始日期: 20240630 + 1 = 20240701
  - 判断: 20240701 <= 20241231，需要下载
  - 返回: start_date=20240701, end_date=20241231

API 请求: 只下载 2024-07-01 到 2024-12-31 的增量数据
节省: 避免下载 2020-01-01 到 2024-06-30 的 4.5 年数据
```

### 2.3 场景 3: 数据已完整（无需下载）

```
现有数据: 2020-01-01 到 2024-12-31
请求参数: start_date=20200101, end_date=20241231

SmartRange 检查:
  - 读取现有数据的最大日期: 20241231
  - 计算增量起始日期: 20241231 + 1 = 20250101
  - 判断: 20250101 > 20241231，无需下载
  - 返回: skip=True

API 请求: 跳过，节省全部请求
```

---

## 3. 技术实现

### 3.1 扩展 CoverageManager

在现有的 `CoverageManager` 基础上，添加 SmartRange 策略：

```python
class CoverageManager:
    """覆盖率管理器 - 实现重复数据检测功能"""

    def get_smart_range_params(self, interface_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取智能调整后的请求参数
        
        Returns:
            {
                'skip': False,  # 是否完全跳过
                'params': {     # 调整后的参数
                    'start_date': '20240701',
                    'end_date': '20241231',
                    # ... 其他参数保持不变
                },
                'reason': 'Incremental update from last date 20240630'
            }
        """
        return self._apply_smart_range(interface_name, params)
    
    def _apply_smart_range(self, interface_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        应用 SmartRange 策略
        
        Args:
            interface_name: 接口名称
            params: 原始请求参数
            
        Returns:
            调整后的结果字典
        """
        # 获取接口配置
        interface_config = self.config_loader.get_interface_config(interface_name)
        detection_config = interface_config.get('duplicate_detection', {})
        
        # 获取日期列名
        date_column = detection_config.get('date_column', 'trade_date')
        
        # 获取请求的日期范围
        start_date = params.get('start_date')
        end_date = params.get('end_date')
        
        if not start_date or not end_date:
            return {
                'skip': False,
                'params': params,
                'reason': 'No date range specified'
            }
        
        try:
            # 读取现有数据的最大日期（只读取一列，极快）
            df = self.storage_manager.read_interface_data(
                interface_name,
                columns=[date_column]
            )
            
            if df.is_empty():
                logger.info(f"No existing data for {interface_name}, downloading full range {start_date}-{end_date}")
                return {
                    'skip': False,
                    'params': params,
                    'reason': 'No existing data'
                }
            
            # 获取最大日期
            max_date = df[date_column].max()
            
            # 计算增量起始日期
            next_date = self._add_days(max_date, 1)
            
            # 判断是否需要下载
            if next_date > end_date:
                logger.info(f"All data up to {end_date} already exists for {interface_name} (max_date: {max_date})")
                return {
                    'skip': True,
                    'params': params,
                    'reason': f'All data up to {end_date} already exists (max_date: {max_date})'
                }
            
            # 调整参数
            adjusted_params = params.copy()
            adjusted_params['start_date'] = next_date
            
            logger.info(f"SmartRange for {interface_name}: {start_date}-{end_date} -> {next_date}-{end_date} (max_date: {max_date})")
            
            return {
                'skip': False,
                'params': adjusted_params,
                'reason': f'Incremental update from max_date {max_date}'
            }
            
        except Exception as e:
            logger.warning(f"SmartRange check failed for {interface_name}: {e}")
            return {
                'skip': False,
                'params': params,
                'reason': f'Check failed: {e}'
            }
    
    def _add_days(self, date_str: str, days: int) -> str:
        """
        给日期字符串增加天数
        
        Args:
            date_str: 日期字符串，格式 YYYYMMDD
            days: 要增加的天数
            
        Returns:
            新的日期字符串
        """
        from datetime import datetime, timedelta
        
        date = datetime.strptime(date_str, '%Y%m%d')
        new_date = date + timedelta(days=days)
        return new_date.strftime('%Y%m%d')
```

### 3.2 在 Downloader 中集成

修改 `downloader.py` 中的分页方法，使用 SmartRange：

```python
class GenericDownloader:
    """通用下载器 - 原子化的执行引擎"""

    def _execute_date_range_pagination(self, interface_config: Dict[str, Any], params: Dict[str, Any],
                                      pagination_config: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """执行日期范围分页 - 支持 SmartRange"""
        
        # [新增] 应用 SmartRange 策略
        if self.coverage_manager:
            smart_range_result = self.coverage_manager.get_smart_range_params(
                interface_config['api_name'],
                params
            )
            
            if smart_range_result.get('skip'):
                logger.info(f"Skipping {interface_config['api_name']} - {smart_range_result.get('reason')}")
                return []
            
            # 使用调整后的参数
            params = smart_range_result['params']
            logger.info(f"Using SmartRange: {smart_range_result.get('reason')}")
        
        # [原有] 检查覆盖率，如果已覆盖则跳过
        if self.coverage_manager:
            should_skip = self.coverage_manager.should_skip(
                interface_config['api_name'],
                params,
                strategy='date_range'
            )
            if should_skip:
                logger.info(f"Skipping window {window_start} - {window_end} for {interface_config['api_name']} (already covered)")
                continue
        
        # ... 原有的下载逻辑 ...
```

### 3.3 配置文件支持

在接口配置中添加 SmartRange 选项：

```yaml
# daily.yaml
name: daily
api_name: daily
description: "日线行情"

pagination:
  enabled: true
  mode: "date_range"
  window_size_days: 365

# 重复数据检测配置
duplicate_detection:
  enabled: true
  mode: "smart_range"  # 使用 SmartRange 策略
  date_column: "trade_date"
  threshold: 0.95
  smart_range:
    enabled: true
    min_interval_days: 7  # 至少间隔 7 天才使用 SmartRange

output:
  primary_key: ["ts_code", "trade_date"]
  sort_by: ["trade_date"]
```

---

## 4. 性能对比

### 4.1 场景：下载 daily 接口，时间范围 2020-01-01 到 2024-12-31

| 方案 | 内存占用 | 启动时间 | API 请求次数 | 下载的数据量 |
|------|---------|---------|-------------|-------------|
| **无优化** | 0 MB | 0 秒 | 1,200 次 | 24,000,000 条 |
| **CoverageManager（现有）** | ~10 MB | ~1 秒 | 1,200 次 | 24,000,000 条 |
| **PreDownloadChecker（全局预加载）** | 2.4 GB | ~60 秒 | 1,200 次 | 24,000,000 条 |
| **SmartRange（增量更新）** | ~1 MB | < 1 秒 | 200 次 | 4,000,000 条 |

**说明**：
- 假设已有数据到 2024-06-30
- SmartRange 只下载 2024-07-01 到 2024-12-31 的增量数据
- 节省了 83% 的 API 请求和 83% 的数据下载量

### 4.2 内存占用对比

```python
# SmartRange 只需要读取最大日期
df = storage_manager.read_interface_data(
    interface_name,
    columns=['trade_date']  # 只读取一列
)

# 内存占用: ~1-10 MB（取决于接口）
# 对比 PreDownloadChecker: ~2.4 GB
```

### 4.3 启动速度对比

```python
# SmartRange 只需要查询最大值
max_date = df['trade_date'].max()

# 查询时间: < 1 秒
# 对比 PreDownloadChecker: ~60 秒（需要读取全部数据）
```

---

## 5. 注意事项

### 5.1 数据完整性

SmartRange 假设数据是按时间顺序写入的，如果数据有缺失或乱序，可能会有问题：

```python
# 场景：数据有缺失
现有数据: 2020-01-01, 2020-01-03, 2020-01-05（缺失 2020-01-02, 2020-01-04）
最大日期: 2020-01-05
SmartRange: 从 2020-01-06 开始下载
问题: 缺失的 2020-01-02, 2020-01-04 不会被重新下载

# 解决方案：
# 1. 定期全量更新（如每周一次）
# 2. 结合 CoverageManager 的覆盖率检查
# 3. 在配置中设置最小间隔（如至少 7 天才使用 SmartRange）
```

### 5.2 实时数据接口

对于实时数据接口（如 minute、tick），SmartRange 可能不适用：

```python
# 场景：分钟级数据
现有数据: 2024-01-13 14:00:00
最大日期: 2024-01-13 14:00:00
SmartRange: 从 2024-01-13 14:01:00 开始下载
问题: 如果数据延迟，可能错过最新的数据

# 解决方案：
# 1. 对实时接口禁用 SmartRange
# 2. 设置缓冲时间（如从 10 分钟前开始）
```

### 5.3 多主键接口

对于多主键接口（如 income_vip），SmartRange 需要特殊处理：

```python
# income_vip 的主键: ["ts_code", "ann_date", "end_date"]
# SmartRange 只能基于一个日期列

# 解决方案：
# 1. 使用 ann_date 作为日期列
# 2. 或者使用 end_date 作为日期列
# 3. 在配置中明确指定
```

---

## 6. 配置示例

### 6.1 完全启用 SmartRange

```yaml
# daily.yaml
duplicate_detection:
  enabled: true
  mode: "smart_range"  # 使用 SmartRange
  date_column: "trade_date"
  smart_range:
    enabled: true
    min_interval_days: 7  # 至少间隔 7 天才使用 SmartRange
```

### 6.2 混合模式（SmartRange + CoverageManager）

```yaml
# daily.yaml
duplicate_detection:
  enabled: true
  mode: "hybrid"  # 混合模式
  date_column: "trade_date"
  smart_range:
    enabled: true
    min_interval_days: 7
  coverage:
    enabled: true
    threshold: 0.95
```

### 6.3 禁用 SmartRange（使用现有 CoverageManager）

```yaml
# daily.yaml
duplicate_detection:
  enabled: true
  mode: "range"  # 使用现有的范围检查
  date_column: "trade_date"
  threshold: 0.95
```

---

## 7. 实施步骤

### 7.1 第一阶段：扩展 CoverageManager

- 添加 `_apply_smart_range` 方法
- 添加 `get_smart_range_params` 方法
- 添加 `_add_days` 辅助方法

### 7.2 第二阶段：集成到 Downloader

- 修改 `_execute_date_range_pagination` 方法
- 修改 `_execute_period_range_pagination` 方法
- 添加 SmartRange 日志

### 7.3 第三阶段：配置支持

- 在接口配置中添加 `smart_range` 选项
- 更新配置加载器
- 添加配置验证

### 7.4 第四阶段：测试

- 在测试环境验证
- 对比 API 请求次数
- 监控内存占用

### 7.5 第五阶段：灰度发布

- 先在非关键接口上启用
- 逐步推广到所有接口
- 准备回滚方案

---

## 8. 适用场景

### 8.1 推荐使用 SmartRange 的接口

- **日线数据**: daily, pro_bar
- **周线数据**: weekly
- **月线数据**: monthly
- **财务数据**: income, balance_sheet, cashflow
- **报告期数据**: income_vip, balance_sheet_vip, cashflow_vip

### 8.2 不推荐使用 SmartRange 的接口

- **分钟级数据**: minute, stk_mins
- **实时数据**: tick, realtime
- **元数据**: stock_basic, trade_cal（这些接口数据量小，不需要优化）

### 8.3 需要特殊处理的接口

- **复权数据**: adj_factor（需要考虑复权因子变化）
- **停牌数据**: suspend（需要考虑停牌状态变化）
- **分红数据**: div_oper（需要考虑分红除权）

---

## 9. 与现有方案的对比

### 9.1 与 CoverageManager 的关系

- **CoverageManager**: 判断是否跳过下载
- **SmartRange**: 调整下载参数范围
- **互补关系**: 可以同时使用，先调整范围，再判断是否跳过

### 9.2 与 PreDownloadChecker 的关系

- **PreDownloadChecker**: 预加载所有主键，过滤已存在记录
- **SmartRange**: 只读取最大日期，调整请求范围
- **替代关系**: SmartRange 是 PreDownloadChecker 的轻量级替代方案

### 9.3 方案选择建议

| 场景 | 推荐方案 | 原因 |
|------|---------|------|
| 首次全量下载 | 无优化 | 无历史数据，无需优化 |
| 日常增量更新 | SmartRange | 只下载增量数据，节省 API |
| 定期全量更新 | CoverageManager | 确保数据完整性 |
| 主键去重 | PreDownloadChecker | 精确去重，避免重复 |

---

## 10. 总结

SmartRange 方案通过智能调整 API 请求参数范围，实现增量数据下载，具有以下优势：

1. **极低的内存占用**：只读取最大日期，内存占用 ~1-10 MB
2. **极快的启动速度**：查询最大值 < 1 秒
3. **智能的 API 节省**：直接调整请求参数，只下载增量数据
4. **适用于所有接口**：支持日期范围、报告期、元数据等接口

SmartRange 是 PreDownloadChecker 的轻量级替代方案，适用于日常增量更新场景，可以显著降低 API 请求次数和数据下载量。
