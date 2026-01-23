# 主键去重统一化实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将系统中的主键去重配置统一到单一来源，使用output.primary_key作为去重和主键验证的唯一配置，移除冗余的dedup配置段。

**Architecture:** 创建独立的去重模块，统一处理所有去重逻辑，通过primary_key配置实现去重和验证的统一，同时提供默认配置确保向后兼容。

**Tech Stack:** Python, Polars, YAML configuration

---

## Task 1: 创建 core/dedup.py 模块

**Files:**
- Create: `app4/core/dedup.py`

**Step 1: Write the new deduplication module code**

```python
"""数据去重模块 - 提供统一的去重逻辑和统计"""
import logging
from typing import List, Tuple, Dict, Any, Optional
import polars as pl
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DedupStats:
    """去重统计信息"""
    total_records: int = 0
    new_records: int = 0
    filtered_duplicates: int = 0
    filtered_null_keys: int = 0

    @property
    def filtered_total(self) -> int:
        """总共过滤的记录数"""
        return self.filtered_duplicates + self.filtered_null_keys


class DataDeduplicator:
    """数据去重器 - 统一处理所有去重逻辑"""

    DEFAULT_CONFIG = {
        'dedup_enabled': True,  # 默认启用去重
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化去重器

        Args:
            config: 去重配置，如果为None则使用默认配置
        """
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}

    def deduplicate_against_existing(
        self,
        df: pl.DataFrame,
        existing_df: pl.DataFrame,
        primary_keys: List[str],
        interface_name: str = ""
    ) -> Tuple[pl.DataFrame, DedupStats]:
        """与现有数据进行去重

        Args:
            df: 新数据DataFrame
            existing_df: 现有数据DataFrame
            primary_keys: 主键字段列表
            interface_name: 接口名称（用于日志）

        Returns:
            Tuple[pl.DataFrame, DedupStats]: (过滤后的数据帧, 去重统计信息)

        Note:
            - 主键包含空值的记录会被丢弃（主键配置错误或数据质量问题）
            - 返回空DataFrame表示没有新记录需要保存
        """
        stats = DedupStats(total_records=len(df))

        # 验证输入
        if df.is_empty():
            logger.info(f"Empty DataFrame provided for deduplication")
            return df, stats

        if existing_df.is_empty() or not primary_keys:
            logger.debug("No existing data or primary keys, skipping deduplication")
            return df, stats

        if not self.config['dedup_enabled']:
            logger.debug("Deduplication disabled by config")
            return df, stats

        # 检查主键字段是否存在（记录警告，但不中断）
        missing_keys = [k for k in primary_keys if k not in df.columns]
        if missing_keys:
            logger.warning(
                f"Primary key fields {missing_keys} not found in data columns {df.columns}. "
                f"Using available keys: {[k for k in primary_keys if k in df.columns]}"
            )

        # 只使用数据中存在的有效主键字段
        available_keys = [k for k in primary_keys if k in df.columns]
        if not available_keys:
            logger.error("No valid primary keys available for deduplication, returning original data")
            return df, stats

        # 构建现有主键集合（跳过包含空值的记录）
        existing_keys = self._build_key_set(existing_df, available_keys)
        logger.info(f"Found {len(existing_keys)} existing key combinations")

        # 过滤新数据
        new_records = []
        for row in df.iter_rows(named=True):
            key_tuple = tuple(row.get(k) for k in available_keys)

            # 检查空值：主键不允许为空，否则丢弃记录
            if any(v is None for v in key_tuple):
                stats.filtered_null_keys += 1
                continue

            # 检查是否已存在
            if key_tuple in existing_keys:
                stats.filtered_duplicates += 1
                continue

            new_records.append(row)

        stats.new_records = len(new_records)

        # 如果没有新记录，返回空DataFrame
        if not new_records:
            logger.info(
                f"All {stats.total_records} records already exist or have null keys"
                f"{f' for {interface_name}' if interface_name else ''}, skipping"
            )
            return pl.DataFrame(), stats

        # 创建新的DataFrame
        new_df = pl.DataFrame(new_records)

        # 记录统计信息
        if stats.filtered_total > 0:
            logger.info(
                f"Deduplication stats{f' for {interface_name}'}: "
                f"{stats.total_records} -> {stats.new_records} "
                f"({stats.filtered_total} filtered: "
                f"{stats.filtered_duplicates} duplicates, "
                f"{stats.filtered_null_keys} null keys)"
            )

        return new_df, stats

    def _build_key_set(self, df: pl.DataFrame, keys: List[str]) -> set:
        """从DataFrame构建主键集合

        Args:
            df: 数据DataFrame
            keys: 主键字段列表

        Returns:
            set: 主键元组的集合（跳过包含空值的记录）
        """
        key_set = set()
        for row in df.iter_rows(named=True):
            key_tuple = tuple(row.get(k) for k in keys)
            # 跳过包含空值的主键记录
            if all(v is not None for v in key_tuple):
                key_set.add(key_tuple)
        return key_set


def deduplicate_against_existing(
    df: pl.DataFrame,
    existing_df: pl.DataFrame,
    primary_keys: List[str],
    interface_name: str = "",
    config: Optional[Dict[str, Any]] = None
) -> Tuple[pl.DataFrame, DedupStats]:
    """便捷的函数接口

    Args:
        df: 新数据DataFrame
        existing_df: 现有数据DataFrame
        primary_keys: 主键字段列表
        interface_name: 接口名称（用于日志）
        config: 去重配置

    Returns:
        Tuple[pl.DataFrame, DedupStats]: (过滤后的数据帧, 去重统计信息)
    """
    deduplicator = DataDeduplicator(config)
    return deduplicator.deduplicate_against_existing(
        df, existing_df, primary_keys, interface_name
    )
```

**Step 2: Save the new module file**

Write the module to `app4/core/dedup.py`

**Step 3: Commit**

```bash
git add app4/core/dedup.py
git commit -m "feat: create core deduplication module with unified logic and detailed stats"
```

---

## Task 2: 修改 daily.yaml 配置文件

**Files:**
- Modify: `app4/config/interfaces/daily.yaml`

**Step 1: Read the current daily.yaml file**

```bash
cat app4/config/interfaces/daily.yaml
```

**Step 2: Update the daily.yaml configuration to remove dedup section and add dedup_enabled**

Remove the dedup configuration section and add dedup_enabled under output section:

```yaml
name: daily
api_name: daily
description: "日线行情"

permissions:
  min_points: 0
  rate_limit: 120
  query_limit: 10000

pagination:
  enabled: true
  mode: "date_range"
  window_size_days: 365

parameters:
  ts_code:
    type: string
    required: false
    description: "证券代码"

output:
  primary_key:
    - ts_code
    - trade_date
  dedup_enabled: true  # 新增
  sort_by:
    - trade_date
  columns:
    ts_code: {type: string, required: true}
    trade_date: {type: date, format: "%Y%m%d", required: true}
    open: {type: float, required: false}
    high: {type: float, required: false}
    low: {type: float, required: false}
    close: {type: float, required: false}
    pre_close: {type: float, required: false}
    change: {type: float, required: false}
    pct_chg: {type: float, required: false}
    vol: {type: float, required: false}
    amount: {type: float, required: false}

duplicate_detection:
  enabled: true
  date_column: "trade_date"
  threshold: 0.95
```

**Step 3: Update the file**

Write the updated configuration to app4/config/interfaces/daily.yaml

**Step 4: Commit**

```bash
git add app4/config/interfaces/daily.yaml
git commit -m "refactor: update daily config to use unified deduplication approach"
```

---

## Task 3: 修改 income_vip.yaml 配置文件

**Files:**
- Modify: `app4/config/interfaces/income_vip.yaml`

**Step 1: Read the current income_vip.yaml file**

```bash
cat app4/config/interfaces/income_vip.yaml
```

**Step 2: Update the income_vip.yaml configuration to remove dedup section and add dedup_enabled**

Remove the dedup configuration section and add dedup_enabled under output section:

```yaml
name: income_vip
api_name: income_vip
description: "利润表(审计报告期VIP)(原income接口升级版)"

permissions:
  min_points: 8000
  rate_limit: 50
  query_limit: 1000

pagination:
  enabled: true
  mode: "date_range"
  window_size_days: 365

parameters:
  ts_code:
    type: string
    required: false
    description: "股票代码"

  period:
    type: string
    required: true
    format: "YYYYMMDD"
    description: "报告期"
    pattern: "^[0-9]{8}$"

output:
  primary_key:
    - ts_code
    - ann_date
    - end_date
  dedup_enabled: true  # 新增
  sort_by:
    - ann_date
  columns:
    ts_code: {type: string, required: true}
    ann_date: {type: string, format: "%Y%m%d", required: true}
    end_date: {type: string, format: "%Y%m%d", required: true}
    # ... 其他列保持不变

duplicate_detection:
  enabled: true
  date_column: "ann_date"
  threshold: 0.95
```

**Step 3: Update the file**

Write the updated configuration to app4/config/interfaces/income_vip.yaml

**Step 4: Commit**

```bash
git add app4/config/interfaces/income_vip.yaml
git commit -m "refactor: update income_vip config to use unified deduplication approach"
```

---

## Task 4: 修改 pro_bar.yaml 配置文件

**Files:**
- Modify: `app4/config/interfaces/pro_bar.yaml`

**Step 1: Read the current pro_bar.yaml file**

```bash
cat app4/config/interfaces/pro_bar.yaml
```

**Step 2: Update the pro_bar.yaml configuration to remove dedup section and add dedup_enabled**

Remove the dedup configuration section and add dedup_enabled under output section:

```yaml
name: pro_bar
api_name: pro_bar
description: "复权因子行情"

permissions:
  min_points: 2000
  rate_limit: 500
  query_limit: 3000

pagination:
  enabled: true
  mode: "date_range"
  window_size_days: 365

parameters:
  ts_code:
    type: string
    required: false
    description: "证券代码"
  asset:
    type: string
    required: false
    description: "资产类型(E:股票 IDX:指数 FT:期货 FD:基金 OPT:期权)"
    default: "E"
  adj:
    type: string
    required: false
    description: "复权类型(前复权: hfq,后复权: qfq,不复权: None)"
    default: "None"

output:
  primary_key:
    - ts_code
    - trade_date
  dedup_enabled: true  # 新增
  sort_by:
    - trade_date
  columns:
    ts_code: {type: string, required: true}
    trade_date: {type: date, format: "%Y%m%d", required: true}
    # ... 其他列保持不变

duplicate_detection:
  enabled: true
  date_column: "trade_date"
  threshold: 0.95
```

**Step 3: Update the file**

Write the updated configuration to app4/config/interfaces/pro_bar.yaml

**Step 4: Commit**

```bash
git add app4/config/interfaces/pro_bar.yaml
git commit -m "refactor: update pro_bar config to use unified deduplication approach"
```

---

## Task 5: 修改 main.py 以使用新的去重模块

**Files:**
- Modify: `app4/main.py`

**Step 1: Read the main.py file to locate the area around L329-356**

Use `awk` or `head`/`tail` to examine the relevant area in main.py

**Step 2: Update the main.py to import and use the new deduplication module**

Replace the old deduplication logic with the new module approach:

```python
# [改进] 使用统一的去重模块
from core.dedup import deduplicate_against_existing

output_config = interface_config.get('output', {})
primary_keys = output_config.get('primary_key', [])
dedup_config = output_config.get('dedup', {'dedup_enabled': True})

# 读取现有数据（只读主键列）
existing_df = storage_manager.read_interface_data(
    interface_name,
    columns=primary_keys
)

if not existing_df.is_empty() and primary_keys:
    # 使用统一去重函数
    df, stats = deduplicate_against_existing(
        df, existing_df, primary_keys, interface_name, dedup_config
    )

    # 如果没有新记录，直接返回
    if stats.new_records == 0:
        return df
```

**Step 3: Apply the changes**

Edit app4/main.py to implement the new logic

**Step 4: Commit**

```bash
git add app4/main.py
git commit -m "feat: update main.py to use unified deduplication module with primary_key"
```

---

## Task 6: 修改 core/storage.py 以使用新的去重模块

**Files:**
- Modify: `app4/core/storage.py`

**Step 1: Read the storage.py file to locate the storage worker deduplication logic**

Find the area around lines 464-490 in core/storage.py

**Step 2: Update the storage.py to import and use the new deduplication module**

Replace the existing deduplication logic with the new module approach:

```python
# [改进] 使用统一的去重模块
from core.dedup import deduplicate_against_existing

output_config = interface_config.get('output', {})
primary_keys = output_config.get('primary_key', [])
dedup_config = output_config.get('dedup', {'dedup_enabled': True})

# 读取现有数据（只读主键列）
existing_df = self.read_interface_data(
    interface_name,
    columns=primary_keys
)

if not existing_df.is_empty() and primary_keys:
    # 使用统一去重函数
    original_count = len(df)
    df, stats = deduplicate_against_existing(
        df, existing_df, primary_keys, interface_name, dedup_config
    )

    # 累加统计信息
    total_filtered += stats.filtered_total

    # 如果没有新记录，跳过保存
    if stats.new_records == 0:
        logger.info(f"No new records to save for {interface_name}, skipping")
        continue
```

**Step 3: Also update the default config at line around 445**

```python
interface_config = {
    'api_name': interface_name,
    'output': {'primary_key': [], 'dedup': {'dedup_enabled': True}},
}
```

**Step 4: Apply the changes**

Edit core/storage.py to implement the new logic

**Step 5: Commit**

```bash
git add app4/core/storage.py
git commit -m "feat: update storage.py to use unified deduplication module with primary_key"
```

---

## Task 7: 更新 config_loader.py 以验证新的配置格式

**Files:**
- Modify: `app4/core/config_loader.py`

**Step 1: Read the config_loader.py to locate where validation occurs**

Find the area around lines 173-174 in core/config_loader.py

**Step 2: Update config_loader.py to add validation for primary key fields**

```python
# 验证主键字段存在且不为空
output_config = config.get('output', {})
primary_key = output_config.get('primary_key', [])

if not primary_key:
    logger.error(f"Interface '{interface_name}' must have non-empty primary_key")
    return False

# 验证 dedup_enabled 为布尔值（如果存在）
if 'dedup_enabled' in output_config and not isinstance(output_config['dedup_enabled'], bool):
    logger.error(f"Interface '{interface_name}' dedup_enabled must be boolean")
    return False
```

**Step 3: Apply the changes**

Edit core/config_loader.py to implement the new validation

**Step 4: Commit**

```bash
git add app4/core/config_loader.py
git commit -m "feat: add primary key validation in config loader to ensure config correctness"
```

---

## Task 8: 运行测试确保功能正常工作

**Files:**
- Test: All modified files and new module

**Step 1: Check if the system can still load configurations correctly**

```bash
python -c "from app4.core.config_loader import load_interface_config; print(load_interface_config('daily'))"
```

**Step 2: Test the new dedup module with sample data**

```python
# Create a simple test script to validate deduplication functionality
python -c "
import polars as pl
from app4.core.dedup import DataDeduplicator

# Create test data
df = pl.DataFrame({
    'ts_code': ['000001', '000002', '000001'],
    'trade_date': ['20230101', '20230101', '20230101'],
    'close': [10.0, 11.0, 10.1]
})

existing_df = pl.DataFrame({
    'ts_code': ['000001', '000003'],
    'trade_date': ['20230101', '20230101'],
})

dedup = DataDeduplicator()
result_df, stats = dedup.deduplicate_against_existing(df, existing_df, ['ts_code', 'trade_date'], 'test')
print('Original:', len(df), 'Final:', len(result_df), 'Stats:', stats)
"
```

**Step 3: Run existing tests to make sure nothing is broken**

```bash
python -m pytest test/ -k "dedup" -v
```

**Step 4: Commit if all tests pass**

```bash
git add .
git commit -m "test: verify deduplication functionality works correctly with new module"
```

---

## Task 9: 创建测试用例验证主键去重统一化

**Files:**
- Create: `test/test_dedup_unification.py`

**Step 1: Create comprehensive test cases for the new deduplication module**

```python
"""测试主键去重统一化功能的测试用例"""
import pytest
import polars as pl
from app4.core.dedup import DataDeduplicator, DedupStats


def test_basic_deduplication_functionality():
    """测试基本去重功能"""
    df = pl.DataFrame({
        'ts_code': ['000001', '000002', '000001'],  # 重复的ts_code+trade_date
        'trade_date': ['20230101', '20230101', '20230101'],
        'close': [10.0, 11.0, 10.1]  # 不同的价格但相同日期，应只保留第一个
    })

    existing_df = pl.DataFrame({
        'ts_code': ['000001'],
        'trade_date': ['20230101'],
    })

    dedup = DataDeduplicator()
    result_df, stats = dedup.deduplicate_against_existing(
        df, existing_df, ['ts_code', 'trade_date'], 'daily'
    )

    # 应该过滤掉2条记录（1个重复，1个已存在）
    assert len(result_df) == 1  # 只剩000002的数据
    assert stats.filtered_duplicates == 1  # 1个重复
    assert stats.filtered_total == 2  # 1个重复 + 1个已存在 = 2个被过滤


def test_null_key_handling():
    """测试空主键值处理"""
    df = pl.DataFrame({
        'ts_code': ['000001', None, '000002'],
        'trade_date': ['20230101', '20230101', None],  # 一个有值一个为空
        'close': [10.0, 11.0, 12.0]
    })

    existing_df = pl.DataFrame()

    dedup = DataDeduplicator()
    result_df, stats = dedup.deduplicate_against_existing(
        df, existing_df, ['ts_code', 'trade_date'], 'daily'
    )

    # 应该丢弃主键中包含空值的记录
    assert len(result_df) == 1  # 只有000001, 20230101这一个有效记录
    assert stats.filtered_null_keys == 2  # 2个主键包含空值被丢弃
    assert result_df['ts_code'][0] == '000001'
    assert result_df['trade_date'][0] == '20230101'


def test_disabled_deduplication():
    """测试禁用去重功能"""
    df = pl.DataFrame({
        'ts_code': ['000001', '000001'],
        'trade_date': ['20230101', '20230101'],
        'close': [10.0, 10.1]
    })

    existing_df = pl.DataFrame({
        'ts_code': ['000001'],
        'trade_date': ['20230101'],
    })

    dedup = DataDeduplicator(config={'dedup_enabled': False})
    result_df, stats = dedup.deduplicate_against_existing(
        df, existing_df, ['ts_code', 'trade_date'], 'daily'
    )

    # 禁用去重时，应该返回所有数据
    assert len(result_df) == 2
    assert stats.total_records == 2


def test_empty_data_conditions():
    """测试空数据情况"""
    df = pl.DataFrame(schema={'ts_code': pl.Utf8, 'trade_date': pl.Utf8, 'close': pl.Float64})
    existing_df = pl.DataFrame({
        'ts_code': ['000001'],
        'trade_date': ['20230101'],
    })

    dedup = DataDeduplicator()
    result_df, stats = dedup.deduplicate_against_existing(
        df, existing_df, ['ts_code', 'trade_date'], 'daily'
    )

    # 空输入应该返回空结果
    assert result_df.is_empty()


def test_no_primary_keys():
    """测试无主键配置情况"""
    df = pl.DataFrame({
        'ts_code': ['000001', '000002'],
        'trade_date': ['20230101', '20230101'],
        'close': [10.0, 11.0]
    })

    existing_df = pl.DataFrame({
        'ts_code': ['000003'],
        'trade_date': ['20230101'],
    })

    dedup = DataDeduplicator()
    result_df, stats = dedup.deduplicate_against_existing(
        df, existing_df, [], 'daily'  # 空主键列表
    )

    # 无主键时，应该返回所有数据
    assert len(result_df) == 2


def test_missing_primary_key_fields():
    """测试主键字段缺失"""
    df = pl.DataFrame({
        'ts_code': ['000001', '000002'],
        'close': [10.0, 11.0]
    })  # 缺少trade_date字段

    existing_df = pl.DataFrame({
        'ts_code': ['000003'],
        'trade_date': ['20230101'],
    })

    dedup = DataDeduplicator()
    result_df, stats = dedup.deduplicate_against_existing(
        df, existing_df, ['ts_code', 'trade_date'], 'daily'
    )

    # 应只使用存在的字段进行去重
    assert len(result_df) == 2  # 使用ts_code进行去重，但因为没有重复所以返回2条
```


**Step 2: Save the test file**

Write the test to test/test_dedup_unification.py

**Step 3: Run the new tests**

```bash
python -m pytest test/test_dedup_unification.py -v
```

**Step 4: Commit the test**

```bash
git add test/test_dedup_unification.py
git commit -m "test: add comprehensive tests for deduplication unification functionality"
```

---

## Task 10: 创建迁移脚本用于自动化配置更新

**Files:**
- Create: `scripts/migrate_dedup_config.py`

**Step 1: Write configuration migration script**

```python
"""
配置迁移脚本：自动将旧的 dedup 配置迁移到新的 primary_key 格式
"""

import yaml
import os
import glob

def migrate_dedup_to_primary_key(config_path: str):
    """将旧的 dedup 配置迁移到 primary_key 格式"""
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    if 'dedup' not in config:
        return  # 没有旧配置需要处理

    # 获取 dedup 和 primary_key 配置
    dedup_config = config.get('dedup', {})
    dedup_columns = dedup_config.get('columns', [])
    current_primary_keys = config.get('output', {}).get('primary_key', [])

    if dedup_columns == current_primary_keys and len(dedup_columns) > 0:
        # 两套配置一致，可以迁移到新的格式
        print(f"Migrating {config_path}: removing dedup, adding dedup_enabled")

        # 删除旧的 dedup 配置
        del config['dedup']

        # 确保 output 段存在
        if 'output' not in config:
            config['output'] = {}

        # 添加新的 dedup_enabled 配置
        config['output']['dedup_enabled'] = True

        # 保存更新后配置
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, sort_keys=False, default_flow_style=False, allow_unicode=True)

        print(f"✓ Migrated {config_path}")
    else:
        print(f"⚠ Skipping {config_path}: dedup.columns != primary_key or no primary_key defined")


def batch_migrate():
    """批量迁移所有接口配置文件"""
    interfaces_dir = "app4/config/interfaces/"
    yaml_files = glob.glob(os.path.join(interfaces_dir, "*.yaml"))

    print(f"Found {len(yaml_files)} interface configuration files")

    for yaml_file in yaml_files:
        migrate_dedup_to_primary_key(yaml_file)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--batch":
        print("Starting batch migration...")
        batch_migrate()
    elif len(sys.argv) > 1:
        migrate_dedup_to_primary_key(sys.argv[1])
    else:
        print("Usage: python migrate_dedup_config.py <config_file> | --batch")
        print("Use --batch to migrate all interface configs in app4/config/interfaces/")
```

**Step 2: Save the migration script**

Write script to scripts/migrate_dedup_config.py

**Step 3: Run a dry run of the migration script**

```bash
mkdir -p scripts
python scripts/migrate_dedup_config.py --batch
```

**Step 4: Commit the migration script**

```bash
git add scripts/migrate_dedup_config.py
git commit -m "chore: add dedup configuration migration script"
```

---

## Task 11: 更新 App4 README.md 文件

**Files:**
- Modify: `app4/README.md`

**Step 1: Read the current README.md**

```bash
cat app4/README.md
```

**Step 2: Update the README to document the new configuration format**

Add information about the new unified primary_key + dedup_enabled approach:

```markdown
## 配置说明

### 主键与去重 (Primary Key & Deduplication)
在新版本中，我们将主键定义和去重配置统一到单一位置：

```yaml
output:
  primary_key:          # 输出数据的主键，也用作去重列
    - ts_code
    - trade_date
  dedup_enabled: true   # 是否启用去重 (默认为 true)
  sort_by:
    - trade_date
```

- `primary_key`: 定义数据的主键字段，同时用于去重检查
- `dedup_enabled`: 控制是否启用去重逻辑 (默认为 true)
- 旧的 `dedup` 配置段已被废弃，请使用新格式

### 配置字段

- `name`: 系统中接口的内部名称
- `api_name`: 调用TuShare API的具体接口名
- `output.primary_key`: 输出数据的主键，同时用于去重检查
- `output.dedup_enabled`: 是否启用去重 (默认为 true)
- `permissions`: API权限配置，根据TuShare积分要求设置
- `pagination`: 分页策略配置
- `parameters`: API参数验证规则
- `output.columns`: 定义输出数据的列和类型
```

**Step 3: Apply the changes to README**

Edit app4/README.md to include the updated documentation

**Step 4: Commit the README update**

```bash
git add app4/README.md
git commit -m "docs: update documentation to reflect unified deduplication configuration"
```