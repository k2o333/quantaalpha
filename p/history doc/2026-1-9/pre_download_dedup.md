# 下载前主键去重方案

## 背景与问题

当前的去重实现在**保存阶段**进行，存在以下问题：

1. **浪费 API 配额**：每次运行都会下载完整的 API 数据，即使数据已存在
2. **网络资源浪费**：重复请求相同的数据
3. **效率低下**：下载 124 条记录，然后发现有 109 条已存在

**示例**：
```
第一次运行：
- API 下载：124 条记录
- 去重后保存：108 条新记录
- 耗时：~4 秒

第二次运行：
- API 下载：124 条记录（重复下载）
- 去重发现：109 条全部已存在，跳过保存
- 耗时：~3 秒（浪费）
```

## 解决方案设计

### 核心思路
在**下载前**检查现有数据的主键，对于已存在的记录跳过 API 请求。

### 实现层次

#### 方案 A：全局预加载（推荐）
在开始下载前，一次性加载所有接口的主键数据到内存，下载时进行快速过滤。

**优点**：
- 性能最优，只读一次磁盘
- 支持所有接口类型
- 实现相对简单

**缺点**：
- 内存占用较高（对于大量历史数据）

#### 方案 B：按需加载
在每次下载前加载特定接口的主键数据。

**优点**：
- 内存占用低
- 灵活性高

**缺点**：
- 多次磁盘读取
- 实现复杂度高

### 推荐实现：方案 A

## 实现方案

### 1. 在接口配置中添加 `pre_download_check` 配置

```yaml
# 示例：income_vip.yaml
dedup:
  enabled: true
  strategy: "primary_key"
  columns: ["ts_code", "ann_date", "end_date"]

# 新增：下载前检查配置
pre_download_check:
  enabled: true
  strategy: "primary_key"  # 支持: "primary_key", "date_range", "none"
  check_columns: ["ts_code", "ann_date", "end_date"]  # 用于检查的列
```

### 2. 创建 PreDownloadChecker 类

**文件位置**: `app4/core/pre_download_checker.py`

```python
import polars as pl
from typing import Set, Tuple, List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class PreDownloadChecker:
    """下载前主键检查器 - 避免 API 重复请求"""

    def __init__(self, storage_manager):
        self.storage_manager = storage_manager
        # 缓存接口的主键数据：{interface_name: set_of_keys}
        self._key_cache: Dict[str, Set[Tuple[Any, ...]]] = {}

    def preload_interface_keys(self, interface_name: str, interface_config: Dict[str, Any]):
        """预加载接口的主键数据到内存

        Args:
            interface_name: 接口名称
            interface_config: 接口配置
        """
        # 检查配置
        check_config = interface_config.get('pre_download_check', {})
        if not check_config.get('enabled', False):
            logger.debug(f"Pre-download check disabled for {interface_name}")
            return

        # 获取检查列
        check_columns = check_config.get('check_columns', [])
        if not check_columns:
            logger.warning(f"No check_columns configured for {interface_name}")
            return

        logger.info(f"Preloading existing keys for {interface_name}...")

        # 读取现有数据的主键列
        existing_df = self.storage_manager.read_interface_data(
            interface_name,
            columns=check_columns
        )

        if existing_df.is_empty():
            logger.info(f"No existing data for {interface_name}")
            self._key_cache[interface_name] = set()
            return

        # 构建主键集合
        key_set = set()
        for row in existing_df.iter_rows(named=True):
            key_tuple = tuple(row.get(k) for k in check_columns if k in row)
            # 只添加非空的键
            if all(v is not None for v in key_tuple):
                key_set.add(key_tuple)

        self._key_cache[interface_name] = key_set
        logger.info(f"Loaded {len(key_set)} existing key combinations for {interface_name}")

    def filter_existing_records(
        self,
        interface_name: str,
        records: List[Dict[str, Any]],
        check_columns: List[str]
    ) -> Tuple[List[Dict[str, Any]], int]:
        """过滤已存在的记录

        Args:
            interface_name: 接口名称
            records: 待检查的记录列表
            check_columns: 用于检查的列

        Returns:
            (过滤后的记录列表, 过滤掉的数量)
        """
        if interface_name not in self._key_cache:
            logger.warning(f"No cached keys for {interface_name}, skipping filter")
            return records, 0

        existing_keys = self._key_cache[interface_name]
        new_records = []
        filtered_count = 0

        for record in records:
            key_tuple = tuple(record.get(k) for k in check_columns)
            if key_tuple not in existing_keys:
                new_records.append(record)
            else:
                filtered_count += 1

        if filtered_count > 0:
            logger.info(f"Filtered {filtered_count} existing records for {interface_name}")

        return new_records, filtered_count

    def add_keys_to_cache(
        self,
        interface_name: str,
        records: List[Dict[str, Any]],
        check_columns: List[str]
    ):
        """将新记录的键添加到缓存

        Args:
            interface_name: 接口名称
            records: 新记录列表
            check_columns: 检查列
        """
        if interface_name not in self._key_cache:
            self._key_cache[interface_name] = set()

        key_set = self._key_cache[interface_name]

        for record in records:
            key_tuple = tuple(record.get(k) for k in check_columns)
            if all(v is not None for v in key_tuple):
                key_set.add(key_tuple)
```

### 3. 修改 GenericDownloader 的 `_execute_date_range_pagination` 方法

**文件位置**: `app4/core/downloader.py`

在方法开始处添加检查逻辑：

```python
def _execute_date_range_pagination(self, interface_config, params):
    """执行日期范围分页下载（带下载前检查）"""

    # ... 原有的参数处理逻辑 ...

    # [新增] 下载前检查
    check_config = interface_config.get('pre_download_check', {})
    if check_config.get('enabled', False):
        check_columns = check_config.get('check_columns', [])
        if check_columns:
            # 检查是否有 PreDownloadChecker 实例
            if hasattr(self, 'pre_download_checker'):
                # 预加载主键（如果还没有加载）
                if interface_name not in self.pre_download_checker._key_cache:
                    self.pre_download_checker.preload_interface_keys(interface_name, interface_config)

                # 检查所有请求的键是否都存在
                # 注意：这里需要根据不同的接口类型（ts_code, date_range等）进行不同的检查逻辑
                # 对于 stock_loop 模式，检查指定 ts_code 的所有日期是否已存在
                pass  # 具体实现需要根据接口类型调整

    # ... 原有的下载逻辑 ...
```

### 4. 在 main.py 中初始化 PreDownloadChecker

```python
# 在 main() 函数中初始化
from core.pre_download_checker import PreDownloadChecker

# 初始化组件
pre_download_checker = PreDownloadChecker(storage_manager)
downloader.pre_download_checker = pre_download_checker  # 将检查器传递给 downloader

# 对于需要下载前检查的接口，预加载主键
for interface_name in interfaces_to_run:
    interface_config = config_loader.get_interface_config(interface_name)
    check_config = interface_config.get('pre_download_check', {})
    if check_config.get('enabled', False):
        pre_download_checker.preload_interface_keys(interface_name, interface_config)
```

### 5. 针对 stock_loop 模式的特殊处理

对于 `income_vip` 这类使用 `stock_loop` 模式的接口，需要在下载特定股票前检查：

```python
# 在 downloader.download_single_stock 方法中
def download_single_stock(self, interface_config, stock, params):
    """下载单只股票的数据（带下载前检查）"""

    interface_name = interface_config['name']
    check_config = interface_config.get('pre_download_check', {})

    if check_config.get('enabled', False) and hasattr(self, 'pre_download_checker'):
        check_columns = check_config.get('check_columns', [])

        # 生成该股票可能的日期范围
        # 注意：这里需要根据接口的实际参数逻辑生成可能的键组合
        # 对于 income_vip，键是 (ts_code, ann_date, end_date)
        # 我们可以检查该 ts_code 的所有现有记录

        existing_keys = self.pre_download_checker._key_cache.get(interface_name, set())
        stock_existing_keys = {
            key for key in existing_keys
            if key[0] == stock.get('ts_code')  # 假设第一列是 ts_code
        }

        # 如果该股票已有足够的数据，可以跳过或优化
        # 这里需要一个启发式的判断逻辑
        # 例如：如果请求的日期范围内，90% 以上的记录已存在，则跳过

        logger.info(f"Stock {stock.get('ts_code')} has {len(stock_existing_keys)} existing records")

    # ... 原有的下载逻辑 ...
```

## 配置示例

### 1. income_vip.yaml
```yaml
dedup:
  enabled: true
  strategy: "primary_key"
  columns: ["ts_code", "ann_date", "end_date"]

pre_download_check:
  enabled: true
  strategy: "primary_key"
  check_columns: ["ts_code", "ann_date", "end_date"]
```

### 2. pro_bar.yaml
```yaml
dedup:
  enabled: true
  strategy: "primary_key"
  columns: ["ts_code", "trade_date"]

pre_download_check:
  enabled: true
  strategy: "primary_key"
  check_columns: ["ts_code", "trade_date"]
```

### 3. daily.yaml（不去重）
```yaml
# 不配置 pre_download_check，默认不启用
# 或者明确禁用
pre_download_check:
  enabled: false
```

## 预期效果

### 优化前（当前）
```
第二次运行 income_vip --ts_code 000002.SZ：
- API 请求：3 个窗口
- 下载数据：124 条记录
- 去重检查：109 条已存在，跳过保存
- 耗时：~3 秒
- API 配额消耗：3 次请求（浪费）
```

### 优化后
```
第二次运行 income_vip --ts_code 000002.SZ：
- 检查主键：发现 109 条已存在
- 跳过 API 请求：0 次请求
- 下载数据：0 条记录
- 耗时：~0.5 秒（仅加载缓存）
- API 配额消耗：0 次请求
```

## 实施步骤

1. **创建 PreDownloadChecker 类**（`app4/core/pre_download_checker.py`）
2. **在接口配置中添加 `pre_download_check` 配置**
3. **修改 main.py**，初始化 PreDownloadChecker 并传递给 downloader
4. **修改 downloader**，集成下载前检查逻辑
5. **测试验证**，确认：
   - 第一次运行正常下载并保存
   - 第二次运行跳过 API 请求
   - 新增数据能正常下载

## 注意事项

1. **数据一致性**：确保 `dedup` 和 `pre_download_check` 使用相同的检查列
2. **缓存更新**：当数据写入后，需要更新缓存中的键（可选）
3. **内存管理**：对于大规模数据，考虑使用数据库或索引文件代替内存缓存
4. **接口兼容**：不是所有接口都适合下载前检查（如实时数据接口）
5. **回退机制**：检查失败时自动回退到下载模式

## 优缺点分析

### 优点
- ✅ 节省 API 配额（避免重复请求）
- ✅ 提升性能（减少网络请求）
- ✅ 降低服务器负载
- ✅ 支持增量更新（只下载新增数据）

### 缺点
- ❌ 增加内存占用（需要缓存主键）
- ❌ 实现复杂度增加
- ❌ 需要维护两套去重逻辑（下载前、下载后）
- ❌ 对于实时数据接口不适用

## 总结

本方案通过在下载前检查现有数据的主键，避免重复的 API 请求，大幅提升系统效率。推荐优先在历史数据接口（如 income_vip、pro_bar）上实施，对于实时数据接口保持原有的保存前去重机制。
