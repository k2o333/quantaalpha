# 最终方案：基于数据内容的参数反推

## 核心思路

**不记录输入参数，从数据内容反推**

对于 offset 分页，虽然无法直接知道当时使用的 offset 值，但可以通过数据中的关键字段（如 trade_date、ts_code）来推断哪些数据已经下载过。

## 具体实现

### 1. 配置约定

在接口配置中约定用于判断数据唯一性的字段：

```yaml
# 接口配置示例
name: stock_daily
pagination:
  enabled: true
  mode: offset
  offset:
    enabled: true
    limit: 5000

# 新增：用于判断数据是否已下载的字段
dedup_key: ['ts_code', 'trade_date']  # 组合主键
```

### 2. ParamAnalyzer 实现

```python
# app4/core/param_analyzer.py
import polars as pl
import os
from typing import Set, Dict, Any, List, Optional


class ParamAnalyzer:
    """
    参数分析器 - 从已有数据中提取已下载的参数范围
    """

    def __init__(self, storage_dir: str):
        self.storage_dir = storage_dir
        self._cache: Dict[str, Any] = {}

    def _get_interface_dir(self, interface_name: str) -> str:
        """获取接口数据目录"""
        return os.path.join(self.storage_dir, interface_name)

    def _read_data(self, interface_name: str, columns: Optional[List[str]] = None) -> pl.DataFrame:
        """读取接口数据"""
        dir_path = self._get_interface_dir(interface_name)
        if not os.path.exists(dir_path):
            return pl.DataFrame()

        try:
            return pl.read_parquet(dir_path, columns=columns)
        except Exception:
            return pl.DataFrame()

    # ==================== type_split 分页分析 ====================

    def get_downloaded_types(self, interface_name: str, type_field: str = 'type') -> Set[str]:
        """
        获取已下载的 type 值集合

        Args:
            interface_name: 接口名称
            type_field: type 字段名，默认为 'type'

        Returns:
            已下载的 type 值集合
        """
        cache_key = f"{interface_name}_types"
        if cache_key in self._cache:
            return self._cache[cache_key]

        df = self._read_data(interface_name, columns=[type_field])
        if df.is_empty() or type_field not in df.columns:
            return set()

        types = set(df[type_field].to_list())
        self._cache[cache_key] = types
        return types

    # ==================== offset 分页分析 ====================

    def get_downloaded_keys(self, interface_name: str, key_fields: List[str]) -> Set[tuple]:
        """
        获取已下载数据的关键键值集合

        通过数据中的关键字段（如 ts_code + trade_date）来判断哪些数据已存在

        Args:
            interface_name: 接口名称
            key_fields: 关键字段列表，如 ['ts_code', 'trade_date']

        Returns:
            已下载数据的键值元组集合，如 {('000001.SZ', '20240101'), ...}
        """
        cache_key = f"{interface_name}_keys_{'_'.join(key_fields)}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        df = self._read_data(interface_name, columns=key_fields)
        if df.is_empty():
            return set()

        # 检查所有关键字段是否存在
        available_fields = [f for f in key_fields if f in df.columns]
        if not available_fields:
            return set()

        # 提取键值组合
        keys = set()
        for row in df.iter_rows():
            key_tuple = tuple(row[f] for f in available_fields)
            keys.add(key_tuple)

        self._cache[cache_key] = keys
        return keys

    def is_data_downloaded(self, interface_name: str, key_fields: List[str],
                          key_values: Dict[str, Any]) -> bool:
        """
        检查特定数据是否已下载

        Args:
            interface_name: 接口名称
            key_fields: 关键字段列表
            key_values: 要检查的关键字段值，如 {'ts_code': '000001.SZ', 'trade_date': '20240101'}

        Returns:
            是否已下载
        """
        downloaded_keys = self.get_downloaded_keys(interface_name, key_fields)
        if not downloaded_keys:
            return False

        key_tuple = tuple(key_values.get(f) for f in key_fields)
        return key_tuple in downloaded_keys

    def estimate_date_coverage(self, interface_name: str, date_field: str = 'trade_date') -> Dict[str, Any]:
        """
        估计日期覆盖范围

        Args:
            interface_name: 接口名称
            date_field: 日期字段名

        Returns:
            {'min_date': str, 'max_date': str, 'date_count': int, 'dates': Set[str]}
        """
        cache_key = f"{interface_name}_dates"
        if cache_key in self._cache:
            return self._cache[cache_key]

        df = self._read_data(interface_name, columns=[date_field])
        if df.is_empty() or date_field not in df.columns:
            return {'min_date': None, 'max_date': None, 'date_count': 0, 'dates': set()}

        dates = set(df[date_field].to_list())
        result = {
            'min_date': min(dates),
            'max_date': max(dates),
            'date_count': len(dates),
            'dates': dates
        }

        self._cache[cache_key] = result
        return result

    def clear_cache(self, interface_name: str = None):
        """清除缓存"""
        if interface_name:
            keys_to_remove = [k for k in self._cache.keys() if k.startswith(f"{interface_name}_")]
            for k in keys_to_remove:
                del self._cache[k]
        else:
            self._cache.clear()
```

### 3. 修改 PaginationComposer

```python
# app4/core/pagination.py

class PaginationComposer:
    # ... 原有代码 ...

    def __init__(self, context: PaginationContext, param_analyzer: Optional['ParamAnalyzer'] = None):
        self.context = context
        self.config = context.pagination_config
        self.interface_config = context.interface_config
        self.param_analyzer = param_analyzer  # 新增

    def _apply_type_split(self, params_stream: List[Dict[str, Any]]) -> Iterator[Dict[str, Any]]:
        """
        应用分类分割维度，支持跳过已下载的 type 值
        """
        type_config = self.config['type_split']
        field = type_config.get('field', 'type')
        values = type_config.get('values', [])

        if not values:
            yield from params_stream
            return

        # 获取已下载的 type 值
        downloaded_types = set()
        if not self.context.force_download and self.param_analyzer:
            downloaded_types = self.param_analyzer.get_downloaded_types(
                self.context.interface_name,
                type_field=field
            )
            if downloaded_types:
                logger.info(f"[{self.context.interface_name}] 已下载的 {field} 值: {downloaded_types}")

        for params in params_stream:
            for val in values:
                # 跳过已下载的 type 值
                if val in downloaded_types:
                    logger.debug(f"[{self.context.interface_name}] 跳过已下载的 {field}: {val}")
                    continue

                type_params = params.copy()
                type_params[field] = val
                type_params['_type_field'] = field
                type_params['_type_value'] = val
                yield type_params
```

### 4. 修改 PaginationExecutor

```python
# app4/core/pagination_executor.py

class PaginationExecutor:
    def __init__(self, max_workers: int = 4, param_analyzer: Optional['ParamAnalyzer'] = None):
        self.max_workers = max_workers
        self.param_analyzer = param_analyzer  # 新增

    def _execute_single_request(self, interface_config: Dict[str, Any], params: Dict[str, Any],
                               make_request: Callable) -> List[Dict[str, Any]]:
        """
        执行单个请求，处理 offset 分页
        新增：根据数据内容判断是否跳过已下载的数据
        """
        offset_config = params.get('_offset_pagination', {})

        if not offset_config.get('enabled'):
            clean_params = {k: v for k, v in params.items() if not k.startswith('_')}
            return make_request(interface_config, clean_params)

        # 获取去重键配置
        dedup_key = interface_config.get('dedup_key', [])

        # 获取已下载的数据键值
        downloaded_keys = set()
        if self.param_analyzer and dedup_key:
            downloaded_keys = self.param_analyzer.get_downloaded_keys(
                interface_config.get('name', 'unknown'),
                dedup_key
            )

        all_data = []
        limit = offset_config['limit']
        offset = 0
        base_params = {k: v for k, v in params.items() if not k.startswith('_')}
        interface_name = interface_config.get('name', 'unknown')

        logger.info(f"[{interface_name}] Offset分页开始 - limit={limit}")
        page_num = 0
        consecutive_empty = 0

        while True:
            request_params = base_params.copy()
            request_params['limit'] = limit
            request_params['offset'] = offset

            data = make_request(interface_config, request_params)

            if not data:
                logger.info(f"[{interface_name}] 第{page_num + 1}页无数据，停止")
                break

            # 过滤已下载的数据
            if dedup_key and downloaded_keys:
                new_data = []
                for item in data:
                    key_tuple = tuple(item.get(k) for k in dedup_key)
                    if key_tuple not in downloaded_keys:
                        new_data.append(item)
                    else:
                        logger.debug(f"[{interface_name}] 跳过已存在数据: {key_tuple}")

                if not new_data:
                    # 本页数据全部已存在，继续下一页
                    logger.info(f"[{interface_name}] 第{page_num + 1}页数据全部已存在，继续下一页")
                    offset += limit
                    page_num += 1
                    consecutive_empty += 1
                    if consecutive_empty >= 3:  # 连续3页都是已存在数据，停止
                        logger.info(f"[{interface_name}] 连续{consecutive_empty}页数据已存在，停止")
                        break
                    continue

                data = new_data

            data_count = len(data)
            all_data.extend(data)
            page_num += 1
            consecutive_empty = 0

            logger.info(f"[{interface_name}] 第{page_num}页完成 - offset={offset}, 新数据={data_count}条")

            if data_count < limit:
                logger.info(f"[{interface_name}] 分页完成 - 最后1页返回{data_count}条 < limit={limit}")
                break

            offset += limit
            if offset > limit * 10000:
                logger.warning(f"[{interface_name}] Offset分页超过安全限制")
                break

        logger.info(f"[{interface_name}] Offset分页结束 - 总页数={page_num}, 新数据={len(all_data)}条")
        return all_data
```

### 5. 修改 Downloader

```python
# app4/core/downloader.py

from .param_analyzer import ParamAnalyzer

class GenericDownloader:
    def __init__(self, config_loader: ConfigLoader, storage_manager=None, ...):
        # ... 原有代码 ...

        # 新增：参数分析器
        if storage_manager:
            self.param_analyzer = ParamAnalyzer(storage_manager.storage_dir)
        else:
            self.param_analyzer = None

    def _execute_pagination(self, interface_config: Dict[str, Any], params: Dict[str, Any]) -> List[Dict[str, Any]]:
        # ... 原有代码 ...

        # 创建分页组合器，传入 param_analyzer
        pagination_context = create_context_with_legacy_support(...)
        composer = PaginationComposer(pagination_context, param_analyzer=self.param_analyzer)

        # 创建分页执行器，传入 param_analyzer
        executor = PaginationExecutor(param_analyzer=self.param_analyzer)

        # ... 原有代码 ...
```

## 使用示例

### type_split 分页接口配置

```yaml
# stock_hsgt.yaml
name: stock_hsgt
api_name: hsgt_top10
pagination:
  enabled: true
  mode: type_split
  type_split:
    enabled: true
    field: market_type
    values: ['HK_SZ', 'SZ_HK', 'HK_SH', 'SH_HK']
```

### offset 分页接口配置

```yaml
# stock_daily.yaml
name: stock_daily
api_name: daily
pagination:
  enabled: true
  mode: offset
  offset:
    enabled: true
    limit: 5000

# 关键：指定用于判断数据是否已下载的字段
dedup_key: ['ts_code', 'trade_date']
```

## 工作流程

### type_split 分页

```
1. 启动下载 --update 模式
2. ParamAnalyzer 读取已有数据的 type 列
3. PaginationComposer 过滤掉已存在的 type 值
4. 只下载未下载过的 type 值对应的数据
```

### offset 分页

```
1. 启动下载 --update 模式
2. ParamAnalyzer 读取已有数据的 dedup_key 字段
3. PaginationExecutor 逐页请求数据
4. 每页数据与已下载的键值对比，过滤已存在的数据
5. 如果连续多页都是已存在数据，提前停止
```

## 优势

1. **无需额外存储**：不创建单独的参数历史文件
2. **数据驱动**：直接从数据内容反推，准确可靠
3. **配置简单**：只需在接口配置中指定 `dedup_key`
4. **自动适应**：数据变化时自动适应，无需维护
5. **支持断点续传**：offset 分页可以从断点继续

## 实施步骤

1. 创建 `app4/core/param_analyzer.py`（30 分钟）
2. 修改 `PaginationComposer` 支持 type_split 过滤（20 分钟）
3. 修改 `PaginationExecutor` 支持 offset 数据过滤（30 分钟）
4. 修改 `GenericDownloader` 集成 ParamAnalyzer（10 分钟）
5. 为 offset 分页接口添加 `dedup_key` 配置（10 分钟）
6. 测试验证（30 分钟）

总计约 2.5 小时完成。
