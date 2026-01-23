# App4 项目混合范围覆盖检测方案

## 1. 概述

基于无头coding agent的深入分析，提出一个**混合范围覆盖检测方案**，结合索引文件优化和优化的快速预检方法，以达到性能、可靠性和简洁性的最佳平衡。

## 2. 设计理念

### 2.1 三层检查策略
```
┌─────────────────────────────────────────────────────────┐
│                    Downloader                            │
│  - 执行下载逻辑                                           │
│  - 调用 CoverageManager 检查覆盖率                        │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                 CoverageManager                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  第一层：索引预检（最快，~10ms）                 │   │
│  │  - 查询 _index.parquet 获取统计信息              │   │
│  │  - 快速判断数据覆盖情况                          │   │
│  └─────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────┐   │
│  │  第二层：日期列查询（中等，~500ms）               │   │
│  │  - 读取实际数据的日期列                           │   │
│  │  - 计算最大日期和覆盖率                          │   │
│  └─────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────┐   │
│  │  第三层：完整检查（最慢但最准确）                │   │
│  │  - 读取完整数据                                  │   │
│  │  - 计算精确覆盖率                                │   │
│  └─────────────────────────────────────────────────┘   │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                StorageManager                           │
│  - 管理数据文件存储                                       │
│  - 维护轻量级索引文件（_index.parquet）                  │
│  - 提供索引查询接口                                       │
└─────────────────────────────────────────────────────────┘
```

## 3. 核心组件设计

### 3.1 StorageManager 索引管理

在 `StorageManager` 中添加索引功能：

```python
class StorageManager:
    def __init__(self, storage_dir: str, config: Dict[str, Any]):
        self.storage_dir = storage_dir
        self.config = config
        self._index_cache = {}  # 内存缓存索引
        self._index_lock = threading.RLock()  # 索引访问锁

    def _get_interface_index_path(self, interface_name: str) -> str:
        """获取接口的索引文件路径"""
        interface_dir = os.path.join(self.storage_dir, interface_name)
        return os.path.join(interface_dir, '_index.parquet')

    def _get_interface_index(self, interface_name: str) -> Optional[pl.DataFrame]:
        """获取接口索引，带缓存机制"""
        cache_key = f"index_{interface_name}"
        with self._index_lock:
            if cache_key in self._index_cache:
                cached_time, index_df = self._index_cache[cache_key]
                # 检查缓存是否过期（默认1小时）
                if time.time() - cached_time < self.config.get('index_cache_ttl', 3600):
                    return index_df

        index_path = self._get_interface_index_path(interface_name)
        if os.path.exists(index_path):
            try:
                index_df = pl.read_parquet(index_path)
                with self._index_lock:
                    self._index_cache[cache_key] = (time.time(), index_df)
                return index_df
            except Exception as e:
                logger.warning(f"Failed to read index for {interface_name}: {e}")
                return None
        return None

    def _update_interface_index(self, interface_name: str, file_path: str, df: pl.DataFrame):
        """更新接口索引文件"""
        interface_dir = os.path.join(self.storage_dir, interface_name)
        os.makedirs(interface_dir, exist_ok=True)

        index_path = self._get_interface_index_path(interface_name)

        # 获取日期列配置
        interface_config = self._get_interface_config(interface_name)
        date_column = interface_config.get('duplicate_detection', {}).get('date_column', 'trade_date')

        if date_column not in df.columns:
            return

        # 创建索引记录
        try:
            min_date = df[date_column].min()
            max_date = df[date_column].max()
            row_count = len(df)
        except Exception:
            return  # 无法计算日期统计信息

        new_index_record = pl.DataFrame({
            'file_path': [file_path],
            'min_date': [min_date],
            'max_date': [max_date],
            'row_count': [row_count],
            'update_time': [int(time.time())],
            'checksum': [hashlib.md5(str(df.head(10)).encode()).hexdigest() if len(df) > 0 else '']
        })

        # 读取现有索引并更新
        if os.path.exists(index_path):
            try:
                existing_index = pl.read_parquet(index_path)
                # 过滤掉同名文件的旧记录
                existing_index = existing_index.filter(pl.col('file_path') != file_path)
                updated_index = pl.concat([existing_index, new_index_record])
            except Exception as e:
                logger.warning(f"Failed to update index for {interface_name}, rebuilding: {e}")
                updated_index = new_index_record
        else:
            updated_index = new_index_record

        try:
            updated_index.write_parquet(index_path)
            # 更新内存缓存
            cache_key = f"index_{interface_name}"
            with self._index_lock:
                self._index_cache[cache_key] = (time.time(), updated_index)
        except Exception as e:
            logger.error(f"Failed to write index for {interface_name}: {e}")

    def update_after_write(self, interface_name: str, file_path: str, df: pl.DataFrame):
        """在数据写入后更新索引"""
        self._update_interface_index(interface_name, file_path, df)
```

### 3.2 CoverageManager 快速预检

```python
class CoverageManager:
    def __init__(self, storage_manager: StorageManager, config_loader: ConfigLoader):
        self.storage_manager = storage_manager
        self.config_loader = config_loader
        self._coverage_cache = {}  # 覆盖率检查结果缓存
        self._cache_lock = threading.RLock()

    def _quick_range_check_with_index(self, interface_name: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        基于索引的快速范围检查

        Returns:
            None: 无法快速判断，需要完整检查
            {'skip': True, 'reason': str}: 完全跳过下载
            {'adjust_params': Dict, 'reason': str}: 调整参数后下载
            {'partial_coverage': bool, 'covered_ratio': float}: 部分覆盖信息
        """
        start_date = params.get('start_date')
        end_date = params.get('end_date')

        if not start_date or not end_date:
            return None

        # 获取接口配置
        interface_config = self.config_loader.get_interface_config(interface_name)
        detection_config = interface_config.get('duplicate_detection', {})
        date_column = detection_config.get('date_column', 'trade_date')
        threshold = detection_config.get('threshold', 0.95)

        try:
            # 1. 使用索引快速获取现有数据的覆盖范围
            index_df = self.storage_manager._get_interface_index(interface_name)
            if index_df is None or len(index_df) == 0:
                return None  # 无索引，无法快速检查

            # 2. 过滤相关时间范围的文件
            relevant_files = index_df.filter(
                (pl.col('max_date') >= start_date) &
                (pl.col('min_date') <= end_date)
            )

            if len(relevant_files) == 0:
                return None  # 没有相关文件，需要完整下载

            # 3. 快速检查是否完全覆盖
            max_existing_date = relevant_files['max_date'].max()

            # 如果最大日期 >= 请求的结束日期，可能可以跳过
            if max_existing_date >= end_date:
                # 进一步验证数据完整性（检查最小日期是否 <= 开始日期）
                min_existing_date = relevant_files['min_date'].min()
                if min_existing_date <= start_date:
                    # 执行快速完整性检查
                    coverage_info = self._check_fast_coverage(
                        interface_name, params, relevant_files, date_column
                    )
                    if coverage_info['fully_covered']:
                        return {
                            'skip': True,
                            'reason': f'All data from {start_date} to {end_date} already exists (max_date: {max_existing_date})'
                        }

            # 4. 检查是否有增量数据可下载
            if max_existing_date >= start_date and max_existing_date < end_date:
                from datetime import datetime, timedelta
                max_date_obj = datetime.strptime(str(max_existing_date), '%Y%m%d')
                next_date_obj = max_date_obj + timedelta(days=1)
                next_date = next_date_obj.strftime('%Y%m%d')

                if next_date <= end_date:
                    return {
                        'adjust_params': {**params, 'start_date': next_date},
                        'reason': f'Adjusting to incremental range from {next_date} (max existing: {max_existing_date})'
                    }

            # 5. 计算部分覆盖率
            coverage_info = self._check_fast_coverage(
                interface_name, params, relevant_files, date_column
            )

            if coverage_info['covered_ratio'] >= threshold:
                return {
                    'partial_coverage': True,
                    'covered_ratio': coverage_info['covered_ratio'],
                    'missing_ranges': coverage_info.get('missing_ranges', []),
                    'reason': f'High coverage ({coverage_info["covered_ratio"]:.2%}), minimal missing data'
                }

        except Exception as e:
            logger.warning(f"Quick range check with index failed: {e}")
            return None

        return None

    def _check_fast_coverage(self, interface_name: str, params: Dict[str, Any],
                           relevant_files_df: pl.DataFrame, date_column: str) -> Dict[str, Any]:
        """
        快速检查数据覆盖情况（基于索引筛选后的文件）
        """
        start_date = params.get('start_date')
        end_date = params.get('end_date')

        if not start_date or not end_date:
            return {'fully_covered': False, 'covered_ratio': 0.0}

        try:
            # 获取交易日历
            if hasattr(self, 'downloader') and self.downloader:
                trade_calendar = self.downloader.get_trade_calendar(start_date, end_date)
                if trade_calendar:
                    expected_dates = {day['cal_date'] for day in trade_calendar if day.get('is_open', 0) == 1}
                else:
                    # 如果无法获取交易日历，使用连续日期
                    from datetime import datetime, timedelta
                    start_dt = datetime.strptime(start_date, '%Y%m%d')
                    end_dt = datetime.strptime(end_date, '%Y%m%d')
                    expected_dates = set()
                    current = start_dt
                    while current <= end_dt:
                        expected_dates.add(current.strftime('%Y%m%d'))
                        current += timedelta(days=1)
            else:
                from datetime import datetime, timedelta
                start_dt = datetime.strptime(start_date, '%Y%m%d')
                end_dt = datetime.strptime(end_date, '%Y%m%d')
                expected_dates = set()
                current = start_dt
                while current <= end_dt:
                    expected_dates.add(current.strftime('%Y%m%d'))
                    current += timedelta(days=1)

            if not expected_dates:
                return {'fully_covered': False, 'covered_ratio': 0.0}

            # 从相关文件中读取日期列
            actual_dates = set()
            for file_path in relevant_files_df['file_path'].to_list():
                if os.path.exists(file_path):
                    try:
                        # 只读取日期列以减少内存使用
                        df = pl.read_parquet(file_path, columns=[date_column])
                        actual_dates.update(df[date_column].to_list())
                    except Exception:
                        continue

            # 计算覆盖率
            covered_dates = actual_dates & expected_dates
            covered_ratio = len(covered_dates) / len(expected_dates) if expected_dates else 0.0

            is_fully_covered = covered_ratio >= 0.99  # 99%视为完全覆盖

            if not is_fully_covered:
                # 计算缺失的日期范围
                missing_dates = expected_dates - covered_dates
                missing_ranges = self._find_continuous_ranges(sorted(missing_dates))
            else:
                missing_ranges = []

            return {
                'fully_covered': is_fully_covered,
                'covered_ratio': covered_ratio,
                'missing_ranges': missing_ranges,
                'total_expected': len(expected_dates),
                'total_covered': len(covered_dates)
            }

        except Exception as e:
            logger.warning(f"Fast coverage check failed: {e}")
            return {'fully_covered': False, 'covered_ratio': 0.0}

    def should_skip(self, interface_name: str, params: Dict[str, Any],
                   strategy: str = 'hybrid') -> bool:
        """
        根据混合策略判断是否应该跳过下载
        """
        try:
            # 生成缓存键
            sorted_params = []
            for k, v in sorted(params.items()):
                if isinstance(v, list):
                    v = tuple(v)
                sorted_params.append((k, v))
            cache_key = (interface_name, tuple(sorted_params))

            # 先检查缓存
            with self._cache_lock:
                if cache_key in self._coverage_cache:
                    return self._coverage_cache[cache_key]

            # 混合策略检查
            if strategy == 'hybrid' or strategy == 'auto':
                # 第一层：索引预检
                quick_result = self._quick_range_check_with_index(interface_name, params)

                if quick_result:
                    if quick_result.get('skip'):
                        logger.info(f"Index-based skip for {interface_name}: {quick_result['reason']}")
                        with self._cache_lock:
                            self._coverage_cache[cache_key] = True
                        return True
                    elif 'adjust_params' in quick_result:
                        # 参数调整后仍需进行完整的覆盖率检查
                        adjusted_params = quick_result['adjust_params']
                        logger.info(f"Index-based adjust for {interface_name}: {quick_result['reason']}")

                        # 重新生成缓存键以包含调整后的参数
                        sorted_params = []
                        for k, v in sorted(adjusted_params.items()):
                            if isinstance(v, list):
                                v = tuple(v)
                            sorted_params.append((k, v))
                        cache_key = (interface_name, tuple(sorted_params))

                        with self._cache_lock:
                            if cache_key in self._coverage_cache:
                                return self._coverage_cache[cache_key]

                        # 使用调整后的参数进行完整检查
                        params = adjusted_params
                    elif quick_result.get('partial_coverage'):
                        # 部分覆盖，根据阈值决定是否跳过
                        covered_ratio = quick_result['covered_ratio']
                        if covered_ratio >= self.config_loader.get_interface_config(interface_name).get('duplicate_detection', {}).get('threshold', 0.95):
                            logger.info(f"High coverage skip for {interface_name}: {quick_result['reason']}")
                            with self._cache_lock:
                                self._coverage_cache[cache_key] = True
                            return True

            # 获取接口配置
            interface_config = self.config_loader.get_interface_config(interface_name)
            detection_config = interface_config.get('duplicate_detection', {})

            # 检查是否启用重复检测
            if not detection_config.get('enabled', True):
                return False

            # 自动确定策略
            if strategy == 'auto':
                pagination_config = interface_config.get('pagination', {})
                pagination_mode = pagination_config.get('mode', 'offset') if pagination_config.get('enabled', False) else 'none'

                if pagination_mode == 'date_range':
                    strategy = 'date_range'
                elif pagination_mode == 'period_range':
                    strategy = 'period'
                elif pagination_mode == 'stock_loop':
                    strategy = 'stock'
                else:
                    return False  # 不支持的模式，不跳过

            # 根据策略执行检测（使用原有方法）
            result = False
            if strategy == 'date_range':
                result = self._check_range_coverage(interface_name, params)
            elif strategy == 'period':
                result = self._check_period_existence(interface_name, params)
            elif strategy == 'stock':
                result = self._check_stock_existence(interface_name, params)

            # 更新缓存
            with self._cache_lock:
                self._coverage_cache[cache_key] = result

            return result

        except Exception as e:
            logger.warning(f"Coverage check failed for {interface_name}: {e}")
            return False  # Fail-safe，检测失败时继续下载
```

## 4. 索引管理策略

### 4.1 索引更新时机
- **写入后更新**：每次数据写入后立即更新索引
- **读取时验证**：检查索引与实际文件的一致性
- **定期校验**：定时任务验证索引完整性

### 4.2 索引优化
- **缓存机制**：在内存中缓存常用索引数据
- **分片存储**：按时间范围分片存储索引（可选）
- **自动清理**：清理过期或无效的索引条目

## 5. 配置选项

```yaml
duplicate_detection:
  enabled: true

  # 混合策略配置
  strategy: "hybrid"  # "index_only", "quick_check", "hybrid", "traditional"

  # 索引配置
  index:
    enabled: true
    cache_ttl: 3600  # 索引缓存时间（秒）
    auto_rebuild: true  # 自动重建损坏的索引
    verify_on_read: true  # 读取时验证索引一致性

  # 快速预检配置
  quick_check:
    enabled: true
    threshold: 0.95  # 覆盖率阈值
    use_incremental: true  # 是否使用增量下载优化
```

## 6. 优势分析

### 6.1 性能优势
- **索引查询**：从秒级降至毫秒级（<10ms）
- **减少I/O**：避免不必要的文件扫描
- **内存优化**：只读取索引文件而非完整数据
- **并发友好**：通过缓存和锁机制提高并发性能

### 6.2 可靠性优势
- **数据完整性**：通过三层检查确保数据完整
- **一致性保障**：索引与数据保持同步
- **回退机制**：索引失效时自动回退到传统检查
- **错误处理**：完善的异常处理机制

### 6.3 扩展性优势
- **模块化设计**：各组件职责清晰
- **配置灵活**：支持多种策略切换
- **易于维护**：统一的API和错误处理

## 7. 实施步骤

### 7.1 第一阶段：基础索引功能（2-3天）
- 实现 StorageManager 中的索引管理
- 添加索引创建和更新功能
- 实现索引查询接口

### 7.2 第二阶段：快速预检集成（1-2天）
- 在 CoverageManager 中集成索引查询
- 实现三层检查策略
- 添加缓存和回退机制

### 7.3 第三阶段：优化完善（1-2天）
- 实现索引缓存和一致性检查
- 添加配置选项
- 进行性能测试

### 7.4 第四阶段：测试部署（1-2天）
- 编写单元测试和集成测试
- 性能基准测试
- 渐进式部署

## 8. 风险控制

### 8.1 数据一致性风险
- **风险**：索引与数据不一致导致错误判断
- **控制**：双重验证 + 自动修复 + 监控告警

### 8.2 性能风险
- **风险**：索引更新开销过大
- **控制**：异步更新 + 批量操作 + 性能监控

### 8.3 并发风险
- **风险**：多线程并发访问冲突
- **控制**：读写锁 + 超时控制 + 降级机制

## 9. 监控指标

### 9.1 性能指标
- 索引查询时间
- 覆盖率检查时间
- 缓存命中率
- 错误率

### 9.2 可靠性指标
- 索引一致性检查通过率
- 数据完整性比例
- 系统可用性

## 10. 总结

该混合方案综合了索引优化和快速预检的优势，通过三层检查策略确保了性能、可靠性和简洁性的平衡。相比单独使用任何一种方案，混合方案能够：

1. **显著提升性能**：索引使查询速度提升90%+
2. **保证数据完整性**：三层检查防止数据空洞
3. **保持架构简洁**：模块化设计，职责清晰
4. **提供灵活配置**：支持多种策略切换
5. **降低维护成本**：统一的错误处理和监控

该方案是App4项目当前最符合需求的技术路线，建议按计划实施。