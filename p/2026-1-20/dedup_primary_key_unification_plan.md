# 去重主键统一方案

## 一、现状分析

### 1.1 当前配置冗余
目前系统中存在两套去重配置：
- `dedup.columns`: 用于与现有数据去重的列
- `output.primary_key`: 输出数据的主键定义

检查发现，三个有 `dedup` 配置的接口中，`dedup.columns` 与 `output.primary_key` 完全一致：

| 接口 | dedup.columns | output.primary_key | 一致性 |
|------|--------------|-------------------|--------|
| daily.yaml | ts_code, trade_date | ts_code, trade_date | ✅ |
| income_vip.yaml | ts_code, ann_date, end_date | ts_code, ann_date, end_date | ✅ |
| pro_bar.yaml | ts_code, trade_date | ts_code, trade_date | ✅ |

### 1.2 当前使用位置
- **main.py (L329-356)**: 读取 `dedup` 配置执行去重
- **core/storage.py (L464-490)**: 存储工作线程中执行去重
- **core/processor.py**: 使用 `primary_key` 进行数据验证

### 1.2 存在的问题
1. **配置冗余**: 两套配置定义相同内容，增加维护成本
2. **逻辑分散**: 去重逻辑依赖 `dedup`，验证逻辑依赖 `primary_key`
3. **容易出错**: 修改时可能忘记同步两处配置
4. **理解成本**: 新人需要理解两套配置的关系

---

## 二、统一方案设计

### 2.1 核心原则
- **单一职责**: `output.primary_key` 既是数据主键，也是去重键
- **向后兼容**: 保留 `dedup` 配置读取逻辑，但优先使用 `primary_key`
- **可选开关**: 通过 `output.dedup_enabled` 控制是否启用去重
- **空值零容忍**: 主键字段不允许为空，空值记录直接丢弃（主键配置错误或数据质量问题）
- **代码复用**: 抽象独立去重模块，避免代码重复

### 2.2 新配置结构
```yaml
output:
  primary_key:
    - ts_code
    - trade_date
  dedup_enabled: true  # 新增：是否启用去重（默认 true）
  sort_by:
    - trade_date
```

### 2.3 默认配置
在代码中提供默认配置，确保即使接口未配置也能正常工作：
```python
DEFAULT_DEDUP_CONFIG = {
    'dedup_enabled': True,  # 默认启用去重
}
```

### 2.3 去重策略
- 默认使用 `output.primary_key` 作为去重列
- 如果 `dedup_enabled=false`，则跳过去重
- 移除独立的 `dedup` 配置段

---

## 三、实施步骤

### 步骤 1: 修改配置文件

#### 1.1 删除 dedup 配置段
修改以下文件，删除 `dedup` 配置：
- `/home/quan/testdata/aspipe_v4/app4/config/interfaces/daily.yaml`
- `/home/quan/testdata/aspipe_v4/app4/config/interfaces/income_vip.yaml`
- `/home/quan/testdata/aspipe_v4/app4/config/interfaces/pro_bar.yaml`

#### 1.2 添加 dedup_enabled 配置
在上述文件的 `output` 段中添加 `dedup_enabled: true`

**示例 (daily.yaml):**
```yaml
api_name: daily
description: 日线行情
name: daily
output:
  primary_key:
  - ts_code
  - trade_date
  dedup_enabled: true  # 新增
  sort_by:
  - trade_date
# ... 其他配置保持不变
```

---

### 步骤 2: 创建 core/dedup.py

**文件**: `/home/quan/testdata/aspipe_v4/app4/core/dedup.py`

**目的**: 抽象统一的去重逻辑，避免代码重复，提供详细的去重统计

**代码内容:**
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

**核心特性:**
- **统一逻辑**: 所有去重操作通过此类处理
- **详细统计**: 提供 DedupStats 记录过滤原因（重复、空值）
- **空值处理**: 主键包含空值的记录直接丢弃
- **配置默认**: 内置默认配置，dedup_enabled 默认为 True
- **日志清晰**: 详细的日志输出，便于调试和监控

---

### 步骤 3: 修改 main.py

**文件**: `/home/quan/testdata/aspipe_v4/app4/main.py`

**位置**: L329-356

**修改前:**
```python
# [新增] 基于接口配置的去重
dedup_config = interface_config.get('dedup', {})

if dedup_config.get('enabled', False):
    strategy = dedup_config.get('strategy', 'none')
    dedup_columns = dedup_config.get('columns', [])

    if strategy == 'primary_key' and dedup_columns:
        # 读取现有数据
        existing_df = storage_manager.read_interface_data(
            interface_name,
            columns=dedup_columns
        )
        # ... 后续逻辑
```

**修改后:**
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

**优势:**
- **代码复用**: 调用统一的去重模块，避免重复实现
- **统计详细**: 自动获得详细的去重统计信息
- **日志完整**: 自动记录清晰的日志
- **维护简单**: 去重逻辑集中在一个地方

---

### 步骤 4: 修改 core/storage.py

**文件**: `/home/quan/testdata/aspipe_v4/app4/core/storage.py`

**位置**: L464-490（存储工作线程中的去重逻辑）

**修改前:**
```python
# 基于接口配置与Parquet文件去重
dedup_config = interface_config.get('dedup', {})
if dedup_config.get('enabled', False):
    strategy = dedup_config.get('strategy', 'none')
    dedup_columns = dedup_config.get('columns', [])

    if strategy == 'primary_key' and dedup_columns:
        # 读取现有数据（只读主键列）
        existing_df = self.read_interface_data(
            interface_name,
            columns=dedup_columns
        )
        # ... 后续逻辑
```

**修改后:**
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

**同时修改** L445 行的默认配置：
```python
interface_config = {
    'api_name': interface_name,
    'output': {'primary_key': [], 'dedup': {'dedup_enabled': True}},
}
```

---

### 步骤 5: 添加配置验证（可选）

**文件**: `/home/quan/testdata/aspipe_v4/app4/core/config_loader.py`

**位置**: L173-174

添加主键字段存在性检查（强烈建议）：

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

**说明**: 此步骤确保配置的正确性，提前发现配置错误，避免运行时数据丢失。

---

### 步骤 6: 更新文档

**文件**: `/home/quan/testdata/aspipe_v4/app4/README.md`

**需要更新的内容:**
- 移除 `dedup` 配置说明
- 添加 `output.dedup_enabled` 说明（默认为 true）
- 添加空值处理策略说明
- 更新配置示例
- 添加 core/dedup.py 模块说明

---

## 四、迁移清单

### 4.1 配置文件变更
- [ ] 修改 `app4/config/interfaces/daily.yaml`
- [ ] 修改 `app4/config/interfaces/income_vip.yaml`
- [ ] 修改 `app4/config/interfaces/pro_bar.yaml`

### 4.2 代码文件变更
- [ ] 创建 `app4/core/dedup.py`（新增统一去重模块）
- [ ] 修改 `app4/main.py`（调用去重模块）
- [ ] 修改 `app4/core/storage.py`（调用去重模块）
- [ ] 更新 `app4/core/config_loader.py`（添加配置验证）

### 4.3 测试验证
- [ ] 测试 daily 接口去重功能
- [ ] 测试 income_vip 接口去重功能
- [ ] 测试 pro_bar 接口去重功能
- [ ] 测试 dedup_enabled=false 的情况
- [ ] 测试主键字段缺失的情况
- [ ] 测试主键包含空值的情况
- [ ] 验证去重统计信息是否正确
- [ ] 运行现有测试用例

---

## 五、回滚方案

如果统一后出现问题，可以快速回滚：

### 5.1 恢复配置文件
```bash
cd /home/quan/testdata/aspipe_v4/app4/config/interfaces
git checkout daily.yaml income_vip.yaml pro_bar.yaml
```

### 5.2 恢复代码文件
```bash
cd /home/quan/testdata/aspipe_v4
git checkout app4/main.py app4/core/storage.py
```

### 5.3 验证回滚
```bash
python -m pytest test/ -k "dedup or primary_key"
```

---

## 六、优势总结

### 6.1 配置简化
- **减少冗余**: 删除重复的 `dedup` 配置段
- **统一语义**: 主键即去重键，概念清晰
- **易于理解**: 新人只需理解 `primary_key`
- **默认安全**: dedup_enabled 默认为 true，避免遗漏配置

### 6.2 代码简化
- **逻辑统一**: 去重和验证都使用 `primary_key`
- **减少分支**: 移除 `strategy` 判断逻辑
- **降低复杂度**: 代码更易维护
- **DRY原则**: 抽象独立模块，消除代码重复

### 6.3 可靠性提升
- **避免不一致**: 单一数据源，不会出现配置不同步
- **减少错误**: 配置项减少，出错概率降低
- **空值安全**: 主键空值记录自动丢弃，保证数据质量
- **易于测试**: 测试用例更简单，边界情况集中处理

### 6.4 可观测性增强
- **详细统计**: 提供分类统计（重复、空值）
- **清晰日志**: 每个去重操作都有明确日志
- **易于调试**: 统计信息帮助快速定位问题

---

## 七、后续优化建议

### 7.1 添加配置迁移工具
创建脚本自动迁移旧配置：
```python
def migrate_dedup_to_primary_key(config_path: str):
    """将旧的 dedup 配置迁移到 primary_key"""
    import yaml
    
    with open(config_path) as f:
        config = yaml.safe_load(f)

    if 'dedup' in config:
        dedup_columns = config['dedup'].get('columns', [])
        primary_key = config.get('output', {}).get('primary_key', [])

        if dedup_columns == primary_key:
            del config['dedup']
            config['output']['dedup_enabled'] = True

            with open(config_path, 'w') as f:
                yaml.dump(config, f, sort_keys=False)
            
            print(f"Migrated {config_path}: removed dedup, added dedup_enabled")
        else:
            print(f"Skipping {config_path}: dedup.columns != primary_key")
```

**使用方式:**
```bash
# 批量迁移所有接口配置
for config in app4/config/interfaces/*.yaml; do
    python migrate_dedup.py "$config"
done
```

### 7.2 添加性能监控
记录去重操作的性能指标：
```python
# 在 dedup.py 中添加
import time

start_time = time.time()
df, stats = deduplicator.deduplicate_against_existing(...)
duration = time.time() - start_time

logger.info(
    f"Dedup performance: {stats.total_records} records "
    f"processed in {duration:.2f}s "
    f"({stats.total_records/duration:.0f} records/s)"
)
```

### 7.3 添加数据质量报告
定期生成数据质量报告，汇总去重统计：
```python
# 在调度器中添加
class DataQualityReporter:
    def __init__(self):
        self.dedup_stats = {}
    
    def record_dedup(self, interface_name: str, stats: DedupStats):
        self.dedup_stats[interface_name] = stats
    
    def generate_report(self):
        """生成数据质量报告"""
        print("=== Data Quality Report ===")
        for interface, stats in self.dedup_stats.items():
            print(f"{interface}: {stats.filtered_total} filtered "
                  f"({stats.filtered_null_keys} null keys)")
```

---

## 八、风险评估

### 8.1 风险点
1. **配置兼容性**: 如果有其他地方依赖 `dedup` 配置，可能需要同步修改
2. **测试覆盖**: 需要确保所有去重场景都被测试覆盖
3. **性能影响**: 需要验证修改后的性能无明显下降

### 8.2 缓解措施
1. **全面搜索**: 搜索所有使用 `dedup` 的代码位置
2. **充分测试**: 运行所有相关测试用例
3. **性能测试**: 对比修改前后的性能指标
4. **逐步发布**: 先在测试环境验证，再发布到生产

---

## 九、实施时间表

| 阶段 | 任务 | 预计工作量 |
|------|------|-----------|
| 准备 | 代码审查、测试准备 | 0.5天 |
| 开发 | 修改配置和代码 | 1天 |
| 测试 | 功能测试、回归测试 | 1天 |
| 验证 | 性能测试、文档更新 | 0.5天 |
| **总计** | | **3天** |

---

## 十、联系方式

如有疑问，请联系：
- 项目负责人: [待补充]
- 技术支持: [待补充]

---

**文档版本**: v2.0
**创建日期**: 2026-01-20
**最后更新**: 2026-01-20

**主要变更 (v2.0):**
- 添加 core/dedup.py 统一去重模块
- 明确空值处理策略（主键空值记录直接丢弃）
- 添加详细的去重统计信息（DedupStats）
- 更新实施步骤，体现代码复用
- 增强配置验证和测试覆盖范围