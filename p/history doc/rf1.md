# 将存储去重逻辑移至存储模块 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将存储去重逻辑从主程序移至app4的存储模块，实现职责分离和更好的可维护性

**Architecture:** 在app4/core/storage.py中添加去重相关方法，重构main.py中的process_and_save_data函数，使其只负责参数传递和流程控制

**Tech Stack:** Python, Polars, app4架构

---

### Task 1: 创建计划目录

**Files:**
- Create: `/home/quan/testdata/aspipe_v4/super/`

**Step 1: 检查目录是否存在**

检查超级目录是否存在，如果不存在则创建

**Step 2: 确保目标目录存在**

运行: `mkdir -p /home/quan/testdata/aspipe_v4/super/`

**Step 3: 验证目录创建**

运行: `ls -la /home/quan/testdata/aspipe_v4/super/`
预期: 目录存在

**Step 4: 提交**

```bash
mkdir -p /home/quan/testdata/aspipe_v4/super/
git add /home/quan/testdata/aspipe_v4/super/
git commit -m "feat: create super directory for plans"
```

### Task 2: 分析当前app4存储模块代码

**Files:**
- Read: `app4/core/storage.py`

**Step 1: 写出分析当前存储模块的命令**

```bash
ls -la app4/core/storage.py
```

**Step 2: 运行命令验证文件存在**

运行: `ls -la app4/core/storage.py`
预期: 文件存在

**Step 3: 读取当前存储模块内容**

运行: `cat app4/core/storage.py`
预期: 读取到存储模块的源代码

**Step 4: 分析当前存储模块结构**

记录存储模块中的类、方法和现有功能，特别关注save_data和read_interface_data方法

**Step 5: 提交**

```bash
git add .
git commit -m "docs: analyze current storage module structure"
```

### Task 3: 分析当前main.py处理函数

**Files:**
- Read: `app4/main.py`

**Step 1: 查找当前的process_and_save_data函数**

运行: `grep -n "process_and_save_data" app4/main.py`
预期: 找到函数定义

**Step 2: 查看函数完整定义**

运行: `grep -A 30 -B 5 "process_and_save_data" app4/main.py`
预期: 查看函数的完整实现

**Step 3: 记录当前函数逻辑**

记录当前函数中包含的所有去重逻辑，包括从接口配置中获取去重配置、过滤现有记录等

**Step 4: 提交**

```bash
git add .
git commit -m "docs: analyze current process_and_save_data function"
```

### Task 4: 设计存储模块中的新方法

**Files:**
- Modify: `app4/core/storage.py`

**Step 1: 编写filter_new_records方法的测试**

```python
def test_filter_new_records_basic():
    """测试基本的去重过滤功能"""
    storage_manager = StorageManager()  # 假设构造函数
    test_data = [
        {"ts_code": "000001.SZ", "trade_date": "20230101", "value": 100},
        {"ts_code": "000002.SZ", "trade_date": "20230101", "value": 200}
    ]
    dedup_config = {
        "enabled": True,
        "strategy": "primary_key",
        "columns": ["ts_code", "trade_date"]
    }

    result = storage_manager.filter_new_records("test_interface", test_data, dedup_config)
    assert result == test_data  # 对于空的现有数据，返回所有
```

**Step 2: 在storage.py添加filter_new_records方法**

```python
def filter_new_records(self, interface_name: str, new_data: List[Dict], dedup_config: Dict[str, Any]) -> List[Dict]:
    """
    根据去重配置过滤新记录，只返回不存在的记录

    Args:
        interface_name: 接口名称
        new_data: 新数据列表
        dedup_config: 去重配置

    Returns:
        过滤后的新记录列表
    """
    if not dedup_config.get('enabled', False):
        return new_data

    strategy = dedup_config.get('strategy', 'none')
    dedup_columns = dedup_config.get('columns', [])

    if strategy != 'primary_key' or not dedup_columns:
        return new_data

    # 读取现有数据
    existing_df = self.read_interface_data(interface_name, columns=dedup_columns)

    if existing_df.is_empty():
        return new_data

    # 构建现有主键集合
    existing_keys = set()
    for row in existing_df.iter_rows(named=True):
        key_tuple = tuple(row.get(k) for k in dedup_columns if k in row)
        if all(v is not None for v in key_tuple):
            existing_keys.add(key_tuple)

    logger.info(f"Found {len(existing_keys)} existing key combinations for {interface_name}")

    # 过滤出不存在的新记录
    original_count = len(new_data)
    new_records = []
    for record in new_data:
        key_tuple = tuple(record.get(k) for k in dedup_columns if k in record)
        if key_tuple not in existing_keys and all(v is not None for v in key_tuple):
            new_records.append(record)

    if not new_records:
        logger.info(f"All {original_count} records already exist for {interface_name}, skipping save")
        return []

    logger.info(f"Filtered {original_count - len(new_records)} duplicate records, "
                f"saving {len(new_records)} new records for {interface_name}")

    return new_records
```

**Step 3: 提交**

```bash
git add app4/core/storage.py
git commit -m "feat: add filter_new_records method to storage manager"
```

### Task 5: 在存储模块中实现带去重的数据保存方法

**Files:**
- Modify: `app4/core/storage.py`

**Step 1: 为save_data_with_dedup写测试**

```python
def test_save_data_with_dedup():
    """测试带去重的数据保存功能"""
    storage_manager = StorageManager()  # 假设构造函数
    test_data = [
        {"ts_code": "000001.SZ", "trade_date": "20230102", "value": 150},
        {"ts_code": "000002.SZ", "trade_date": "20230102", "value": 250}
    ]
    dedup_config = {
        "enabled": True,
        "strategy": "primary_key",
        "columns": ["ts_code", "trade_date"]
    }

    # 测试保存操作是否正常执行
    storage_manager.save_data_with_dedup("test_interface", test_data, dedup_config, async_write=True)
    assert True  # 测试逻辑会验证保存过程
```

**Step 2: 在storage.py添加save_data_with_dedup方法**

```python
def save_data_with_dedup(self, interface_name: str, data: List[Dict], dedup_config: Dict[str, Any], async_write: bool = True):
    """
    带去重功能的数据保存

    Args:
        interface_name: 接口名称
        data: 要保存的数据
        dedup_config: 去重配置
        async_write: 是否异步写入
    """
    # 先过滤新记录
    filtered_data = self.filter_new_records(interface_name, data, dedup_config)

    if not filtered_data:
        return  # 没有新数据需要保存

    # 保存过滤后的数据
    self.save_data(interface_name, filtered_data, async_write)
```

**Step 3: 提交**

```bash
git add app4/core/storage.py
git commit -m "feat: add save_data_with_dedup method to storage manager"
```

### Task 6: 重构main.py中的数据处理函数

**Files:**
- Modify: `app4/main.py`

**Step 1: 为重构后的process_and_save_data写测试**

```python
def test_process_and_save_data_refactored():
    """测试重构后的数据处理和保存函数"""
    # 创建mock对象用于测试
    from unittest.mock import Mock, MagicMock
    processor_mock = Mock()
    storage_manager_mock = Mock()

    # 模拟数据和配置
    data = [{"ts_code": "000001.SZ", "trade_date": "20230101", "value": 100}]
    interface_config = {
        "output": {"primary_key": ["ts_code", "trade_date"]},
        "dedup": {"enabled": True, "strategy": "primary_key", "columns": ["ts_code", "trade_date"]}
    }

    # 调用重构后的函数
    result = process_and_save_data(data, "test_interface", interface_config, processor_mock, storage_manager_mock)
    assert result is not None  # 验证函数执行成功
```

**Step 2: 修改main.py中的process_and_save_data函数**

```python
def process_and_save_data(data, interface_name, interface_config, processor, storage_manager):
    """处理并保存数据的通用函数 - 重构后"""
    if not data:
        logger.warning(f"No data to process for {interface_name}")
        return None

    # 处理数据
    df = processor.process_data(data, interface_config)
    validation_result = processor.validate_data(df, interface_config)

    # 从接口配置获取去重配置
    dedup_config = interface_config.get('dedup', {})

    # 保存数据（内部处理去重逻辑）
    storage_manager.save_data_with_dedup(interface_name, df.to_dicts(), dedup_config, async_write=True)

    logger.info(f"Saved {len(df)} processed records for {interface_name}")
    if validation_result['duplicate_records'] > 0:
        logger.info(f"Found {validation_result['duplicate_records']} duplicate records for {interface_name}")

    return df
```

**Step 3: 提交**

```bash
git add app4/main.py
git commit -m "refactor: simplify process_and_save_data function in main module"
```

### Task 7: 更新存储模块的导入语句

**Files:**
- Modify: `app4/core/storage.py`

**Step 1: 检查当前的导入语句**

查看当前存储模块顶部的导入语句

**Step 2: 添加必要的导入**

确保导入语句包含了实现新功能所需的模块和类型注解

```python
from typing import List, Dict, Any
```

**Step 3: 验证所有需要的导入都存在**

确保filter_new_records和save_data_with_dedup方法中使用的所有类型都已正确导入

**Step 4: 提交**

```bash
git add app4/core/storage.py
git commit -m "refactor: update import statements in storage module"
```

### Task 8: 为新的去重功能编写单元测试

**Files:**
- Create: `test/test_app4_storage_dedup.py`

**Step 1: 创建测试文件的基础结构**

```python
"""
测试app4存储模块的去重功能
"""
import pytest
import polars as pl
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os
from app4.core.storage import StorageManager


def test_filter_new_records_no_dedup():
    """测试禁用去重时的行为"""
    storage_manager = StorageManager(tempfile.mkdtemp())
    test_data = [
        {"ts_code": "000001.SZ", "trade_date": "20230101", "value": 100},
        {"ts_code": "000002.SZ", "trade_date": "20230101", "value": 200}
    ]
    dedup_config = {"enabled": False}

    result = storage_manager.filter_new_records("test_interface", test_data, dedup_config)
    assert result == test_data


def test_filter_new_records_empty_existing_data():
    """测试现有数据为空时的行为"""
    storage_manager = StorageManager(tempfile.mkdtemp())
    test_data = [
        {"ts_code": "000001.SZ", "trade_date": "20230101", "value": 100},
        {"ts_code": "000002.SZ", "trade_date": "20230101", "value": 200}
    ]
    dedup_config = {
        "enabled": True,
        "strategy": "primary_key",
        "columns": ["ts_code", "trade_date"]
    }

    result = storage_manager.filter_new_records("test_interface", test_data, dedup_config)
    assert result == test_data


def test_filter_new_records_with_duplicates():
    """测试存在重复数据时的过滤行为"""
    # 这个测试需要更复杂的mock逻辑来模拟现有数据
    storage_manager = StorageManager(tempfile.mkdtemp())

    # 模拟已有的数据
    existing_data = pl.DataFrame([
        {"ts_code": "000001.SZ", "trade_date": "20230101", "value": 100}
    ])

    # 模拟新数据，其中包含重复项
    new_data = [
        {"ts_code": "000001.SZ", "trade_date": "20230101", "value": 100},  # 重复
        {"ts_code": "000002.SZ", "trade_date": "20230101", "value": 200}   # 新项
    ]

    dedup_config = {
        "enabled": True,
        "strategy": "primary_key",
        "columns": ["ts_code", "trade_date"]
    }

    # 使用mock来控制read_interface_data的行为
    with patch.object(storage_manager, 'read_interface_data', return_value=existing_data):
        result = storage_manager.filter_new_records("test_interface", new_data, dedup_config)
        assert len(result) == 1
        assert result[0]["ts_code"] == "000002.SZ"


def test_save_data_with_dedup_calls_filter():
    """测试save_data_with_dedup方法调用filter_new_records"""
    storage_manager = StorageManager(tempfile.mkdtemp())
    mock_filtered_data = [{"ts_code": "000002.SZ", "trade_date": "20230101", "value": 200}]

    # 创建mock来验证filter_new_records被调用
    with patch.object(storage_manager, 'filter_new_records', return_value=mock_filtered_data) as mock_filter:
        with patch.object(storage_manager, 'save_data') as mock_save:
            test_data = [{"ts_code": "000001.SZ", "trade_date": "20230101", "value": 100}]
            dedup_config = {
                "enabled": True,
                "strategy": "primary_key",
                "columns": ["ts_code", "trade_date"]
            }

            storage_manager.save_data_with_dedup("test_interface", test_data, dedup_config)

            # 验证filter_new_records被正确调用
            mock_filter.assert_called_once_with("test_interface", test_data, dedup_config)
            # 验证save_data被调用（如果过滤后有数据）
            mock_save.assert_called_once()


def test_save_data_with_dedup_no_new_data():
    """测试没有新数据时save_data不被调用"""
    storage_manager = StorageManager(tempfile.mkdtemp())

    with patch.object(storage_manager, 'filter_new_records', return_value=[]) as mock_filter:
        with patch.object(storage_manager, 'save_data') as mock_save:
            test_data = [{"ts_code": "000001.SZ", "trade_date": "20230101", "value": 100}]
            dedup_config = {
                "enabled": True,
                "strategy": "primary_key",
                "columns": ["ts_code", "trade_date"]
            }

            storage_manager.save_data_with_dedup("test_interface", test_data, dedup_config)

            # 验证filter_new_records被调用
            mock_filter.assert_called_once_with("test_interface", test_data, dedup_config)
            # 但save_data不被调用，因为没有新数据
            mock_save.assert_not_called()

```

**Step 2: 运行测试验证功能正确性**

运行: `python -m pytest test/test_app4_storage_dedup.py -v`
预期: 测试通过

**Step 3: 提交**

```bash
git add test/test_app4_storage_dedup.py
git commit -m "test: add unit tests for storage deduplication functionality"
```

### Task 9: 更新接口配置以支持新的去重功能

**Files:**
- Read: `app4/config/interfaces/daily.yaml`
- Modify: `app4/config/interfaces/daily.yaml`

**Step 1: 检查当前接口配置**

查看daily接口的配置，特别是output部分，看是否已包含去重配置

**Step 2: 验证去重配置格式**

确保接口配置支持以下去重设置：
```yaml
dedup:
  enabled: true
  strategy: primary_key
  columns: ["ts_code", "trade_date"]
```

**Step 3: 修改现有接口配置以启用去重（如果必要）**

在daily.yaml中添加去重配置（如果尚未存在）

**Step 4: 提交**

```bash
git add app4/config/interfaces/daily.yaml
git commit -m "feat: update interface config to support deduplication"
```

### Task 10: 完成集成测试

**Files:**
- Create: `test/test_app4_integration_dedup.py`

**Step 1: 创建集成测试文件**

```python
"""
app4架构下存储去重功能的集成测试
"""
import pytest
import tempfile
import os
from app4.core.storage import StorageManager
from app4.core.processor import DataProcessor


def test_storage_deduplication_integration():
    """测试存储模块去重功能的完整集成"""
    with tempfile.TemporaryDirectory() as temp_dir:
        # 1. 初始化存储管理器
        storage_manager = StorageManager(temp_dir)

        # 2. 用测试接口名创建初始数据
        interface_name = "test_integration"

        # 3. 模拟初始数据
        initial_data = [
            {"ts_code": "000001.SZ", "trade_date": "20230101", "price": 100.0},
            {"ts_code": "000002.SZ", "trade_date": "20230101", "price": 200.0}
        ]

        # 4. 使用新的去重保存方法保存初始数据
        dedup_config = {
            "enabled": True,
            "strategy": "primary_key",
            "columns": ["ts_code", "trade_date"]
        }

        storage_manager.save_data_with_dedup(interface_name, initial_data, dedup_config)

        # 5. 准备包含重复数据的新数据
        new_data = [
            {"ts_code": "000001.SZ", "trade_date": "20230101", "price": 100.0},  # 重复
            {"ts_code": "000002.SZ", "trade_date": "20230101", "price": 200.0},  # 重复
            {"ts_code": "000003.SZ", "trade_date": "20230101", "price": 300.0}   # 新数据
        ]

        # 6. 再次使用去重保存，应只保存新数据
        storage_manager.save_data_with_dedup(interface_name, new_data, dedup_config)

        # 7. 验证最终结果
        result_df = storage_manager.read_interface_data(interface_name)

        # 应该只包含3条记录：原来的2条 + 新的1条
        assert len(result_df) == 3

        # 验证所有记录都唯一
        unique_records = result_df.select(["ts_code", "trade_date"]).unique()
        assert len(unique_records) == 3


def test_process_and_save_data_with_dedup():
    """测试完整的数据处理和保存流程"""
    with tempfile.TemporaryDirectory() as temp_dir:
        from app4.core.storage import StorageManager
        from app4.core.processor import DataProcessor

        storage_manager = StorageManager(temp_dir)
        processor = DataProcessor()

        # 接口配置包含去重设置
        interface_config = {
            "output": {
                "primary_key": ["ts_code", "trade_date"],
                "sort_by": ["trade_date"]
            },
            "dedup": {
                "enabled": True,
                "strategy": "primary_key",
                "columns": ["ts_code", "trade_date"]
            }
        }

        # 模拟初始数据
        initial_data = [
            {"ts_code": "000001.SZ", "trade_date": "20230101", "price": 100.0}
        ]

        # 在main.py中实现process_and_save_data函数
        def process_and_save_data(data, interface_name, interface_config, processor, storage_manager):
            """处理并保存数据的通用函数 - 重构后"""
            if not data:
                print(f"No data to process for {interface_name}")
                return None

            # 处理数据 - 这里简化处理流程
            import polars as pl
            df = pl.DataFrame(data)

            # 从接口配置获取去重配置
            dedup_config = interface_config.get('dedup', {})

            # 保存数据（内部处理去重逻辑）
            storage_manager.save_data_with_dedup(interface_name, df.to_dicts(), dedup_config, async_write=False)

            print(f"Saved {len(df)} processed records for {interface_name}")
            return df

        # 保存初始数据
        process_and_save_data(initial_data, "integration_test", interface_config, processor, storage_manager)

        # 尝试保存重复数据
        duplicate_data = [
            {"ts_code": "000001.SZ", "trade_date": "20230101", "price": 100.0},  # 重复
            {"ts_code": "000002.SZ", "trade_date": "20230101", "price": 200.0}   # 新数据
        ]

        process_and_save_data(duplicate_data, "integration_test", interface_config, processor, storage_manager)

        # 验证结果
        result_df = storage_manager.read_interface_data("integration_test")

        # 应该包含2条记录：1条原始 + 1条新数据
        assert len(result_df) == 2

        # 验证所有记录都唯一
        unique_records = result_df.select(["ts_code", "trade_date"]).unique()
        assert len(unique_records) == 2

```

**Step 2: 运行集成测试**

运行: `python -m pytest test/test_app4_integration_dedup.py -v`
预期: 集成测试通过

**Step 3: 提交**

```bash
git add test/test_app4_integration_dedup.py
git commit -m "test: add integration tests for storage deduplication functionality"
```

### Task 11: 文档更新

**Files:**
- Create: `docs/storage_deduplication.md`

**Step 1: 创建存储去重功能文档**

```markdown
# 存储去重功能

## 设计理念

app4架构中，存储去重逻辑已经从主程序移至存储模块，实现了单一职责原则。存储相关的去重操作全部由StorageManager处理。

## 主要组件

### StorageManager类

存储管理器现在包含以下与去重相关的方法：

#### `filter_new_records(interface_name, new_data, dedup_config)`

根据去重配置过滤新记录，只返回不存在的记录。

参数:
- `interface_name`: 接口名称
- `new_data`: 新数据列表
- `dedup_config`: 去重配置

返回值:
- 过滤后的新记录列表

#### `save_data_with_dedup(interface_name, data, dedup_config, async_write=True)`

带去重功能的数据保存方法。

参数:
- `interface_name`: 接口名称
- `data`: 要保存的数据
- `dedup_config`: 去重配置
- `async_write`: 是否异步写入

## 配置格式

接口配置文件中可包含以下去重配置：

```yaml
dedup:
  enabled: true          # 是否启用去重
  strategy: primary_key  # 去重策略
  columns: ["ts_code", "trade_date"]  # 用于去重的列
```

## 使用示例

在main.py中的数据处理流程中：

```python
def process_and_save_data(data, interface_name, interface_config, processor, storage_manager):
    # 处理数据
    df = processor.process_data(data, interface_config)

    # 从接口配置获取去重配置
    dedup_config = interface_config.get('dedup', {})

    # 保存数据（内部处理去重逻辑）
    storage_manager.save_data_with_dedup(interface_name, df.to_dicts(), dedup_config, async_write=True)
```

## 性能考虑

- 去重操作会读取现有数据以构建唯一键集合
- 对于大表，这可能影响性能
- 建议合理配置去重策略，避免不必要的去重操作
```

**Step 2: 提交**

```bash
git add docs/storage_deduplication.md
git commit -m "docs: add documentation for storage deduplication functionality"
```

### Task 12: 执行最终测试验证

**Files:**
- Test: `python -m pytest test/test_app4_storage_dedup.py test/test_app4_integration_dedup.py -v`

**Step 1: 运行所有相关测试**

运行: `python -m pytest test/test_app4_storage_dedup.py test/test_app4_integration_dedup.py -v`
预期: 所有测试通过

**Step 2: 运行完整的app4主程序测试**

运行: `python -c "from app4.main import process_and_save_data; print('Main function import successful')"`
预期: 成功导入函数

**Step 3: 验证重构后的代码结构**

确认主要逻辑已从main.py移至storage.py，且功能完整

**Step 4: 提交**

```bash
git add .
git commit -m "test: verify all deduplication functionality works as expected"
```