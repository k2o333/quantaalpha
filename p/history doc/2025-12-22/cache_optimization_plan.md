# 缓存优化方案：解决重复下载数据问题

## 问题概述

在当前系统中，重复下载相同数据时没有命中缓存，导致不必要的API调用和资源浪费。主要表现在stk_rewards等接口的下载过程中。

## 问题分析

### 1. 根本原因

1. **缓存键不匹配**
   - 当前下载是按单个股票代码进行的（如`ts_code='000039.SZ'`）
   - 缓存系统期望的路径是：`data/stk_rewards/000039.SZ/all.parquet`
   - 但实际存在的缓存文件是：`data/holders/stk_rewards_full_history.parquet`

2. **下载策略与缓存策略不一致**
   - 系统在下载stk_rewards数据时采用的是逐个股票下载的方式
   - 而现有的缓存是通过批量下载并保存的全量数据

3. **缓存文件命名和组织结构不一致**
   - 缓存系统设计的是一种按参数区分的细粒度缓存
   - 实际实现的是粗粒度的全量数据缓存

## 解决方案

### 方案一：统一缓存策略（推荐）

#### 1. 修改缓存检查逻辑

在`data_storage.py`中修改`is_interface_data_cached`函数：

```python
def is_interface_data_cached(data_type: str, cache_ttl_hours: int = 24, **kwargs) -> bool:
    """
    检查接口数据是否已缓存且未过期
    增加对全量缓存的检查
    """
    # 首先检查标准缓存
    cache_path = get_interface_cache_path(data_type, **kwargs)
    if Path(cache_path).exists():
        file_mtime = Path(cache_path).stat().st_mtime
        cache_age = datetime.now().timestamp() - file_mtime
        if cache_age < (cache_ttl_hours * 3600):
            return True

    # 如果是单个股票的请求，检查是否有全量缓存
    if data_type in ['stk_rewards', 'top10_holders', 'pledge_detail'] and 'ts_code' in kwargs:
        # 检查全量缓存文件
        full_cache_path = DATA_DIR / "holders" / f"{data_type}_full_history.parquet"
        if Path(full_cache_path).exists():
            file_mtime = Path(full_cache_path).stat().st_mtime
            cache_age = datetime.now().timestamp() - file_mtime
            if cache_age < (cache_ttl_hours * 3600):
                return True

    return False
```

#### 2. 修改缓存加载逻辑

在`data_storage.py`中修改`load_interface_cached_data`函数：

```python
def load_interface_cached_data(data_type: str, **kwargs) -> pd.DataFrame:
    """
    加载接口的缓存数据
    增加对全量缓存的支持
    """
    # 首先尝试加载标准缓存
    cache_path = get_interface_cache_path(data_type, **kwargs)
    if Path(cache_path).exists():
        try:
            df = pd.read_parquet(cache_path)
            logger.info(f"从标准缓存加载数据: {data_type}, 路径: {cache_path}")
            return df
        except Exception as e:
            logger.warning(f"加载标准缓存失败: {cache_path}, 错误: {e}")

    # 如果是单个股票的请求，尝试从全量缓存中提取数据
    if data_type in ['stk_rewards', 'top10_holders', 'pledge_detail'] and 'ts_code' in kwargs:
        full_cache_path = DATA_DIR / "holders" / f"{data_type}_full_history.parquet"
        if Path(full_cache_path).exists():
            try:
                df = pd.read_parquet(full_cache_path)
                # 筛选出特定股票的数据
                ts_code = kwargs['ts_code']
                filtered_df = df[df['ts_code'] == ts_code] if 'ts_code' in df.columns else df
                if not filtered_df.empty:
                    logger.info(f"从全量缓存加载数据: {data_type}, 股票代码: {ts_code}")
                    return filtered_df
            except Exception as e:
                logger.warning(f"加载全量缓存失败: {full_cache_path}, 错误: {e}")

    return pd.DataFrame()
```

### 方案二：优化下载策略

#### 1. 修改下载调度器

在`download_scheduler.py`中修改`_should_skip_download_task`函数：

```python
def _should_skip_download_task(self, interface_name: str, **task_kwargs) -> tuple[bool, pd.DataFrame]:
    """
    检查是否应该跳过下载任务（因为已有有效缓存）
    增加对全量缓存的检查
    """
    # 获取缓存设置
    from config_adapter import get_interface_cache_settings
    cache_settings = get_interface_cache_settings(interface_name)

    if not cache_settings['enabled']:
        return False, pd.DataFrame()

    # 提取缓存检查需要的参数
    cache_kwargs = {}
    for key in ['ts_code', 'trade_date', 'start_date', 'end_date', 'period']:
        if key in task_kwargs:
            cache_kwargs[key] = task_kwargs[key]

    # 检查标准缓存
    if is_interface_data_cached(
        interface_name,
        cache_ttl_hours=cache_settings['ttl_hours'],
        **cache_kwargs
    ):
        # 缓存存在，加载数据
        cached_data = load_interface_cached_data(interface_name, **cache_kwargs)
        if not cached_data.empty:
            self.logger.info(f"使用标准缓存数据: {interface_name}")
            return True, cached_data

    # 对于特定接口，检查全量缓存
    if interface_name in ['stk_rewards', 'top10_holders', 'pledge_detail'] and 'ts_code' in cache_kwargs:
        # 构造全量缓存检查参数
        full_cache_kwargs = {k: v for k, v in cache_kwargs.items() if k != 'ts_code'}
        if is_interface_data_cached(
            interface_name,
            cache_ttl_hours=cache_settings['ttl_hours'],
            **full_cache_kwargs
        ):
            # 从全量缓存中提取数据
            full_data = load_interface_cached_data(interface_name, **full_cache_kwargs)
            if not full_data.empty:
                ts_code = cache_kwargs['ts_code']
                filtered_data = full_data[full_data['ts_code'] == ts_code] if 'ts_code' in full_data.columns else full_data
                if not filtered_data.empty:
                    self.logger.info(f"使用全量缓存数据: {interface_name}, 股票代码: {ts_code}")
                    return True, filtered_data

    return False, pd.DataFrame()
```

### 方案三：增强缓存保存机制

#### 1. 修改缓存保存逻辑

在`data_storage.py`中修改`save_interface_data_to_cache`函数：

```python
def save_interface_data_to_cache(df: pd.DataFrame, data_type: str, **kwargs) -> bool:
    """
    保存接口数据到缓存
    同时更新全量缓存
    """
    if df is None or df.empty:
        return False

    try:
        # 保存标准缓存
        cache_path = get_interface_cache_path(data_type, **kwargs)
        df.to_parquet(cache_path, index=False)
        logger.info(f"数据已保存到标准缓存: {data_type}, 路径: {cache_path}")

        # 对于特定接口，同时更新全量缓存
        if data_type in ['stk_rewards', 'top10_holders', 'pledge_detail']:
            full_cache_path = DATA_DIR / "holders" / f"{data_type}_full_history.parquet"

            # 如果全量缓存存在，合并数据；否则直接保存
            if Path(full_cache_path).exists():
                try:
                    existing_df = pd.read_parquet(full_cache_path)
                    # 合并数据，去重
                    combined_df = pd.concat([existing_df, df], ignore_index=True)
                    # 根据业务逻辑去重（例如基于ts_code和公告日期等）
                    if 'ts_code' in combined_df.columns and 'ann_date' in combined_df.columns:
                        combined_df = combined_df.drop_duplicates(subset=['ts_code', 'ann_date'], keep='last')
                    elif 'ts_code' in combined_df.columns:
                        combined_df = combined_df.drop_duplicates(subset=['ts_code'], keep='last')

                    combined_df.to_parquet(full_cache_path, index=False)
                    logger.info(f"全量缓存已更新: {data_type}")
                except Exception as e:
                    logger.warning(f"更新全量缓存失败: {full_cache_path}, 错误: {e}")
            else:
                df.to_parquet(full_cache_path, index=False)
                logger.info(f"全量缓存已创建: {data_type}")

        return True
    except Exception as e:
        logger.error(f"保存缓存失败: {e}")
        return False
```

## 实施步骤

### 第一步：备份现有文件
```bash
cp /home/quan/testdata/aspipe_v4/app/data_storage.py /home/quan/testdata/aspipe_v4/app/data_storage.py.backup
cp /home/quan/testdata/aspipe_v4/app/download_scheduler.py /home/quan/testdata/aspipe_v4/app/download_scheduler.py.backup
```

### 第二步：修改data_storage.py
1. 修改`is_interface_data_cached`函数
2. 修改`load_interface_cached_data`函数
3. 修改`save_interface_data_to_cache`函数

### 第三步：修改download_scheduler.py
1. 修改`_should_skip_download_task`函数

### 第四步：测试验证
1. 运行测试下载，验证缓存命中情况
2. 检查日志输出，确认"使用缓存数据"的消息出现
3. 验证数据完整性

## 预期效果

1. **减少重复下载**：通过充分利用已有的全量缓存，避免重复下载相同数据
2. **提高效率**：减少API调用次数，提高整体下载效率
3. **节省资源**：减少网络流量和系统资源消耗
4. **改善用户体验**：缩短下载时间，提供更好的反馈信息

## 风险评估

### 低风险
- 缓存逻辑变更不会影响核心下载功能
- 增加了容错机制，即使缓存加载失败也会继续下载

### 注意事项
- 需要确保全量缓存文件的数据结构与单个股票数据一致
- 需要定期清理过期缓存文件
- 需要在多线程环境下确保缓存文件访问的安全性

## 后续优化建议

1. **智能缓存清理**：实现LRU缓存淘汰策略
2. **缓存压缩**：对大型缓存文件进行压缩存储
3. **分布式缓存**：支持Redis等分布式缓存系统
4. **缓存预热**：在系统启动时预加载常用缓存