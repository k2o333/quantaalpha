# type_split 和 offset 分页的已有数据参数过滤方案

## 需求概述

在 `--update` 模式下，根据 `data` 目录中已保存的文件，提取之前下载时使用的输入参数，在当前下载任务中避开这些已下载的参数组合。

## 核心思路

1. **提取历史参数**：从已保存的 parquet 文件中读取之前下载时使用的输入参数
2. **参数去重**：在生成分页参数时，过滤掉已经下载过的参数组合
3. **支持两种分页形态**：`type_split`（分类分割）和 `offset`（偏移量分页）

---

## 一、数据存储分析

### 1.1 当前数据存储格式

数据保存在 `{storage_dir}/{interface_name}/{interface}_{date_start}_{date_end}_{timestamp}_{uuid}.parquet`

```python
# 示例：stock_hsgt 接口的数据文件
# data/stock_hsgt/stock_hsgt_20240101_20240131_1706745600000_a1b2c3d4.parquet
```

### 1.2 需要记录的输入参数

对于 `type_split` 和 `offset` 两种分页形态，需要记录的输入参数：

| 分页形态 | 关键参数 | 示例值 |
|---------|---------|--------|
| type_split | `type` 字段值 | 'HK_SZ', 'SZ_HK', 'HK_SH', 'SH_HK' |
| offset | `offset` + `limit` | offset=0, limit=5000 |

**注意**：offset 分页的实际停止点是动态的（根据返回数据量决定），所以需要记录的是**已经完整下载的 offset 值**。

---

## 二、实现方案

### 2.1 新增组件：ParamHistoryTracker

创建文件：`app4/core/param_history.py`

```python
"""
参数历史记录追踪器
用于记录和查询已下载的参数组合
"""

import os
import json
import logging
from typing import Set, Dict, Any, Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)


class ParamHistoryTracker:
    """
    追踪已下载的参数历史

    为每个接口维护一个参数记录文件：
    {storage_dir}/.param_history/{interface_name}.json

    记录格式：
    {
        "type_split": {"HK_SZ", "SZ_HK", ...},  // type值集合
        "offset": {0, 5000, 10000, ...}          // 已完成的offset值集合
    }
    """

    def __init__(self, storage_dir: str):
        self.storage_dir = storage_dir
        self.history_dir = os.path.join(storage_dir, '.param_history')
        os.makedirs(self.history_dir, exist_ok=True)

        # 内存缓存
        self._cache: Dict[str, Dict[str, Set]] = {}

    def _get_history_file(self, interface_name: str) -> str:
        """获取历史记录文件路径"""
        return os.path.join(self.history_dir, f"{interface_name}.json")

    def _load_history(self, interface_name: str) -> Dict[str, Set]:
        """加载接口的参数历史"""
        if interface_name in self._cache:
            return self._cache[interface_name]

        history_file = self._get_history_file(interface_name)
        history = {"type_split": set(), "offset": set()}

        if os.path.exists(history_file):
            try:
                with open(history_file, 'r') as f:
                    data = json.load(f)
                    history["type_split"] = set(data.get("type_split", []))
                    history["offset"] = set(data.get("offset", []))
            except Exception as e:
                logger.warning(f"加载参数历史失败 {interface_name}: {e}")

        self._cache[interface_name] = history
        return history

    def _save_history(self, interface_name: str, history: Dict[str, Set]):
        """保存接口的参数历史"""
        history_file = self._get_history_file(interface_name)
        try:
            with open(history_file, 'w') as f:
                json.dump({
                    "type_split": list(history["type_split"]),
                    "offset": list(history["offset"])
                }, f, indent=2)
            self._cache[interface_name] = history
        except Exception as e:
            logger.error(f"保存参数历史失败 {interface_name}: {e}")

    def is_type_downloaded(self, interface_name: str, type_value: str) -> bool:
        """检查某个 type 值是否已经下载过"""
        history = self._load_history(interface_name)
        return type_value in history["type_split"]

    def is_offset_downloaded(self, interface_name: str, offset: int) -> bool:
        """检查某个 offset 值是否已经下载过"""
        history = self._load_history(interface_name)
        return offset in history["offset"]

    def record_type(self, interface_name: str, type_value: str):
        """记录已下载的 type 值"""
        history = self._load_history(interface_name)
        history["type_split"].add(type_value)
        self._save_history(interface_name, history)
        logger.debug(f"记录 type 值: {interface_name}.{type_value}")

    def record_offset(self, interface_name: str, offset: int):
        """记录已下载的 offset 值"""
        history = self._load_history(interface_name)
        history["offset"].add(offset)
        self._save_history(interface_name, history)
        logger.debug(f"记录 offset 值: {interface_name}.{offset}")

    def get_downloaded_types(self, interface_name: str) -> Set[str]:
        """获取已下载的所有 type 值"""
        history = self._load_history(interface_name)
        return history["type_split"].copy()

    def get_downloaded_offsets(self, interface_name: str) -> Set[int]:
        """获取已下载的所有 offset 值"""
        history = self._load_history(interface_name)
        return history["offset"].copy()

    def clear_history(self, interface_name: str):
        """清空接口的历史记录"""
        history_file = self._get_history_file(interface_name)
        if os.path.exists(history_file):
            os.remove(history_file)
        if interface_name in self._cache:
            del self._cache[interface_name]
        logger.info(f"清空参数历史: {interface_name}")
```

### 2.2 修改 PaginationComposer

文件：`app4/core/pagination.py`

在 `PaginationComposer` 类中注入 `ParamHistoryTracker`，并在参数生成时过滤已下载的参数。

```python
class PaginationComposer:
    """
    分页组合器 - 将多个分页维度组合成一个参数流

    支持的分页维度：
    1. time_range - 时间窗口递归
    2. stock_loop - 股票代码遍历
    3. type_split - 字段分类分割
    4. offset - 记录偏移分页

    执行顺序（从内到外）：time → stock → type → offset
    """

    def __init__(self, config: Dict[str, Any], interface_config: Dict[str, Any],
                 context: 'DownloadContext', param_tracker: Optional['ParamHistoryTracker'] = None):
        """
        Args:
            config: 分页配置
            interface_config: 接口配置
            context: 下载上下文
            param_tracker: 参数历史追踪器（可选，用于--update模式）
        """
        self.config = config
        self.interface_config = interface_config
        self.context = context
        self.param_tracker = param_tracker
        self.interface_name = interface_config.get('name', 'unknown')

    # ... 其他方法保持不变 ...

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
        if self.param_tracker and not self.context.force_download:
            downloaded_types = self.param_tracker.get_downloaded_types(self.interface_name)
            if downloaded_types:
                logger.info(f"[{self.interface_name}] 已下载的 type 值: {downloaded_types}")

        for params in params_stream:
            for val in values:
                # 跳过已下载的 type 值
                if val in downloaded_types:
                    logger.debug(f"[{self.interface_name}] 跳过已下载的 type: {val}")
                    continue

                type_params = params.copy()
                type_params[field] = val
                type_params['_type_field'] = field
                type_params['_type_value'] = val
                yield type_params

    def _apply_offset(self, params_stream: List[Dict[str, Any]]) -> Iterator[Dict[str, Any]]:
        """
        应用偏移量维度，标记需要记录 offset
        """
        offset_config = self.config['offset']
        limit = offset_config.get('limit', 5000)

        for params in params_stream:
            params['_offset_pagination'] = {
                'enabled': True,
                'limit': limit,
                'current_offset': 0,
                '_record_downloaded': self.param_tracker is not None  # 标记需要记录
            }
            yield params
```

### 2.3 修改 PaginationExecutor

文件：`app4/core/pagination_executor.py`

在 offset 分页执行完成后，记录已下载的 offset 值。

```python
class PaginationExecutor:
    """分页执行器"""

    def __init__(self, config_loader: Any, storage_manager: Any,
                 param_tracker: Optional['ParamHistoryTracker'] = None):
        """
        Args:
            config_loader: 配置加载器
            storage_manager: 存储管理器
            param_tracker: 参数历史追踪器（可选）
        """
        self.config_loader = config_loader
        self.storage_manager = storage_manager
        self.param_tracker = param_tracker

    # ... 其他方法 ...

    def _execute_single_request(self, interface_config: Dict[str, Any], params: Dict[str, Any],
                               make_request: Callable) -> List[Dict[str, Any]]:
        """
        执行单个请求，处理offset分页，并记录已下载的offset值
        """
        offset_config = params.get('_offset_pagination', {})

        if not offset_config.get('enabled'):
            clean_params = {k: v for k, v in params.items() if not k.startswith('_')}
            return make_request(interface_config, clean_params)

        all_data = []
        limit = offset_config['limit']
        offset = 0
        base_params = {k: v for k, v in params.items() if not k.startswith('_')}
        interface_name = interface_config.get('name', 'unknown')

        # 获取已下载的 offset 值
        downloaded_offsets = set()
        should_record = offset_config.get('_record_downloaded', False)
        if should_record and self.param_tracker:
            downloaded_offsets = self.param_tracker.get_downloaded_offsets(interface_name)

        logger.info(f"[{interface_name}] Offset分页开始 - limit={limit}, 已下载offset: {downloaded_offsets}")
        page_num = 0

        while True:
            # 跳过已下载的 offset
            if offset in downloaded_offsets:
                logger.debug(f"[{interface_name}] 跳过已下载的 offset: {offset}")
                offset += limit
                continue

            request_params = base_params.copy()
            request_params['limit'] = limit
            request_params['offset'] = offset

            data = make_request(interface_config, request_params)
            if not data:
                break

            data_count = len(data)
            all_data.extend(data)
            page_num += 1

            # 记录已下载的 offset
            if should_record and self.param_tracker:
                self.param_tracker.record_offset(interface_name, offset)

            if data_count < limit:
                break

            offset += limit

            # 安全限制
            if offset > limit * 10000:
                logger.warning(f"[{interface_name}] Offset分页超过安全限制")
                break

        logger.info(f"[{interface_name}] Offset分页结束 - 总页数={page_num}, 总记录数={len(all_data)}")
        return all_data
```

### 2.4 修改下载流程

文件：`app4/core/downloader.py` 或 `app4/main.py`

在创建 `PaginationComposer` 和 `PaginationExecutor` 时传入 `ParamHistoryTracker`。

```python
from app4.core.param_history import ParamHistoryTracker

class Downloader:
    def __init__(self, ...):
        # ... 其他初始化 ...

        # 初始化参数历史追踪器
        self.param_tracker = ParamHistoryTracker(self.storage_dir)

    def download_interface(self, interface_config: Dict[str, Any], ...):
        """下载接口数据"""

        # 创建分页组合器，传入 param_tracker
        composer = PaginationComposer(
            config=pagination_config,
            interface_config=interface_config,
            context=context,
            param_tracker=self.param_tracker if not context.force_download else None
        )

        # 创建分页执行器，传入 param_tracker
        executor = PaginationExecutor(
            config_loader=self.config_loader,
            storage_manager=self.storage_manager,
            param_tracker=self.param_tracker if not context.force_download else None
        )

        # ... 执行下载 ...

        # 对于 type_split 分页，在成功下载后记录 type 值
        if self._is_type_split_mode(pagination_config):
            type_value = params.get('_type_value')
            if type_value:
                self.param_tracker.record_type(interface_name, type_value)
```

---

## 三、使用方式

### 3.1 正常下载模式

```bash
python -m app4.main --interface stock_hsgt
```

- 不启用参数历史追踪
- 下载所有参数组合

### 3.2 增量更新模式（--update）

```bash
python -m app4.main --update --interface stock_hsgt
```

- 启用参数历史追踪
- 自动跳过已下载的 type 值或 offset 值
- 参数历史保存在 `data/.param_history/stock_hsgt.json`

### 3.3 强制重新下载

```bash
python -m app4.main --update --update-force --interface stock_hsgt
```

- 即使启用 `--update`，也忽略参数历史，重新下载所有数据
- 同时清空该接口的参数历史记录

---

## 四、参数历史文件格式

### 4.1 示例：stock_hsgt 接口

文件路径：`data/.param_history/stock_hsgt.json`

```json
{
  "type_split": ["HK_SZ", "SZ_HK"],
  "offset": []
}
```

表示：
- `HK_SZ` 和 `SZ_HK` 两个 type 值已经下载过
- 没有 offset 分页的记录

### 4.2 示例：带 offset 的接口

```json
{
  "type_split": [],
  "offset": [0, 5000, 10000, 15000]
}
```

表示：
- offset 值为 0, 5000, 10000, 15000 的分页已经下载过

---

## 五、注意事项

### 5.1 数据一致性

- 参数历史记录与实际的 parquet 文件是**松耦合**的
- 如果手动删除了 parquet 文件，需要同时删除对应的参数历史记录
- 可以使用 `--update-force` 强制重新下载并清空历史

### 5.2 offset 分页的特殊处理

- offset 分页是动态的，需要根据实际返回数据量决定是否继续
- 只记录**已经成功返回数据**的 offset 值
- 如果某次下载中断，下次会从断点继续

### 5.3 组合分页

如果接口同时使用了 `type_split` 和 `offset`（例如先按 type 分割，再对每个 type 做 offset 分页）：

```yaml
pagination:
  enabled: true
  mode: type_split
  type_split:
    enabled: true
    field: type
    values: ['A', 'B', 'C']
  offset:
    enabled: true
    limit: 5000
```

- 先检查 type 值是否已下载，如果已下载则跳过整个 type
- 对于未下载的 type，再检查具体的 offset 值

---

## 六、文件修改清单

| 文件 | 操作 | 说明 |
|-----|-----|-----|
| `app4/core/param_history.py` | 新增 | 参数历史追踪器 |
| `app4/core/pagination.py` | 修改 | 在 `_apply_type_split` 和 `_apply_offset` 中添加过滤逻辑 |
| `app4/core/pagination_executor.py` | 修改 | 在 `_execute_single_request` 中添加记录逻辑 |
| `app4/core/downloader.py` | 修改 | 初始化 `ParamHistoryTracker` 并传递给分页组件 |

---

## 七、测试验证

### 7.1 测试场景 1：type_split 分页

```python
# 配置
interface_config = {
    'name': 'test_interface',
    'pagination': {
        'enabled': True,
        'mode': 'type_split',
        'type_split': {
            'enabled': True,
            'field': 'type',
            'values': ['A', 'B', 'C']
        }
    }
}

# 第一次下载：下载 A, B, C
# 参数历史：{"type_split": ["A", "B", "C"]}

# 第二次下载（--update）：跳过所有，无新下载
# 参数历史保持不变
```

### 7.2 测试场景 2：offset 分页

```python
# 配置
interface_config = {
    'name': 'test_interface',
    'pagination': {
        'enabled': True,
        'mode': 'offset',
        'offset': {
            'enabled': True,
            'limit': 100
        }
    }
}

# 假设数据有 250 条
# 第一次下载：offset=0 (100条), offset=100 (100条), offset=200 (50条)
# 参数历史：{"offset": [0, 100, 200]}

# 第二次下载（--update）：跳过所有，无新下载
```

---

## 八、扩展建议

### 8.1 支持更多分页维度

可以扩展 `ParamHistoryTracker` 支持其他分页维度：

```python
# 例如：stock_loop 维度
def is_stock_downloaded(self, interface_name: str, ts_code: str) -> bool:
    history = self._load_history(interface_name)
    return ts_code in history.get("stocks", set())

def record_stock(self, interface_name: str, ts_code: str):
    history = self._load_history(interface_name)
    if "stocks" not in history:
        history["stocks"] = set()
    history["stocks"].add(ts_code)
    self._save_history(interface_name, history)
```

### 8.2 参数历史压缩

对于 offset 值很多的情况，可以存储为范围而不是单个值：

```json
{
  "offset_ranges": [[0, 50000], [100000, 150000]]
}
```

表示 offset 0-50000 和 100000-150000 已经下载过。

### 8.3 与 CoverageManager 集成

可以将 `ParamHistoryTracker` 与现有的 `CoverageManager` 结合：

```python
class CoverageManager:
    def __init__(self, ..., param_tracker: Optional[ParamHistoryTracker] = None):
        self.param_tracker = param_tracker

    def should_skip(self, interface_name: str, params: Dict[str, Any], ...) -> bool:
        # 先检查参数历史
        if self.param_tracker:
            if '_type_value' in params:
                if self.param_tracker.is_type_downloaded(interface_name, params['_type_value']):
                    return True
            if '_offset' in params:
                if self.param_tracker.is_offset_downloaded(interface_name, params['_offset']):
                    return True

        # 再执行原有的覆盖率检查
        ...
```
