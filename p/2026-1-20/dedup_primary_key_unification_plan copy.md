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

### 步骤 2: 修改 main.py

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
# [改进] 基于 primary_key 的去重
output_config = interface_config.get('output', {})
primary_keys = output_config.get('primary_key', [])
dedup_enabled = output_config.get('dedup_enabled', True)

if dedup_enabled and primary_keys:
    # 读取现有数据（只读主键列）
    existing_df = storage_manager.read_interface_data(
        interface_name,
        columns=primary_keys
    )

    if not existing_df.is_empty():
        # 构建现有主键集合
        existing_keys = set()
        for row in existing_df.iter_rows(named=True):
            key_tuple = tuple(row.get(k) for k in primary_keys if k in row)
            if all(v is not None for v in key_tuple):
                existing_keys.add(key_tuple)

        logger.info(f"Found {len(existing_keys)} existing key combinations for {interface_name}")

        # 过滤出不存在的新记录
        original_count = len(df)
        new_records = []
        for row in df.iter_rows(named=True):
            key_tuple = tuple(row.get(k) for k in primary_keys)
            if key_tuple not in existing_keys:
                new_records.append(row)

        if not new_records:
            logger.info(f"All {original_count} records already exist for {interface_name}, skipping save")
            return df

        # 重新创建 DataFrame
        df = pl.DataFrame(new_records)
        logger.info(f"Filtered {original_count - len(df)} duplicate records, saving {len(df)} new records for {interface_name}")
```

---

### 步骤 3: 修改 core/storage.py

**文件**: `/home/quan/testdata/aspipe_v4/app4/core/storage.py`

**位置**: L464-490

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
# 基于 primary_key 与现有数据去重
output_config = interface_config.get('output', {})
primary_keys = output_config.get('primary_key', [])
dedup_enabled = output_config.get('dedup_enabled', True)

if dedup_enabled and primary_keys:
    # 读取现有数据（只读主键列）
    existing_df = self.read_interface_data(
        interface_name,
        columns=primary_keys
    )

    if not existing_df.is_empty():
        # 构建现有主键集合
        existing_keys = set()
        for row in existing_df.iter_rows(named=True):
            key_tuple = tuple(row.get(k) for k in primary_keys if k in row)
            if all(v is not None for v in key_tuple):
                existing_keys.add(key_tuple)

        logger.info(f"Found {len(existing_keys)} existing keys for {interface_name}")

        # 过滤新数据
        original_count = len(df)
        new_records = []
        for row in df.iter_rows(named=True):
            key_tuple = tuple(row.get(k) for k in primary_keys)
            if key_tuple not in existing_keys:
                new_records.append(row)

        if not new_records:
            logger.info(f"All {original_count} records already exist, skipping")
            continue

        # 重新创建 DataFrame
        df = pl.DataFrame(new_records)
        logger.info(f"Filtered {original_count - len(df)} duplicates, saving {len(df)} new records")
```

**同时修改** L445 行的默认配置：
```python
interface_config = {
    'api_name': interface_name,
    'output': {'primary_key': [], 'dedup_enabled': True},  # 添加 dedup_enabled
}
```

---

### 步骤 4: 更新 core/config_loader.py

**文件**: `/home/quan/testdata/aspipe_v4/app4/core/config_loader.py`

**位置**: L173-174

**检查逻辑不变**，但可以添加 `dedup_enabled` 的默认值设置：

```python
# 确保输出配置完整
if 'dedup_enabled' not in output_config:
    output_config['dedup_enabled'] = True
```

---

### 步骤 5: 更新文档

**文件**: `/home/quan/testdata/aspipe_v4/app4/README.md`

**需要更新的内容:**
- 移除 `dedup` 配置说明
- 添加 `output.dedup_enabled` 说明
- 更新配置示例

---

## 四、迁移清单

### 4.1 配置文件变更
- [ ] 修改 `app4/config/interfaces/daily.yaml`
- [ ] 修改 `app4/config/interfaces/income_vip.yaml`
- [ ] 修改 `app4/config/interfaces/pro_bar.yaml`

### 4.2 代码文件变更
- [ ] 修改 `app4/main.py`
- [ ] 修改 `app4/core/storage.py`
- [ ] 检查 `app4/core/config_loader.py`

### 4.3 测试验证
- [ ] 测试 daily 接口去重功能
- [ ] 测试 income_vip 接口去重功能
- [ ] 测试 pro_bar 接口去重功能
- [ ] 测试 dedup_enabled=false 的情况
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

### 6.2 代码简化
- **逻辑统一**: 去重和验证都使用 `primary_key`
- **减少分支**: 移除 `strategy` 判断逻辑
- **降低复杂度**: 代码更易维护

### 6.3 可靠性提升
- **避免不一致**: 单一数据源，不会出现配置不同步
- **减少错误**: 配置项减少，出错概率降低
- **易于测试**: 测试用例更简单

---

## 七、后续优化建议

### 7.1 添加配置验证
在 `config_loader.py` 中添加验证逻辑：
```python
def validate_interface_config(config: dict) -> bool:
    """验证接口配置的完整性"""
    output = config.get('output', {})
    primary_key = output.get('primary_key', [])

    if not primary_key:
        logger.error(f"Interface {config.get('name')} must have primary_key")
        return False

    return True
```

### 7.2 添加配置迁移工具
创建脚本自动迁移旧配置：
```python
def migrate_dedup_to_primary_key(config_path: str):
    """将旧的 dedup 配置迁移到 primary_key"""
    with open(config_path) as f:
        config = yaml.safe_load(f)

    if 'dedup' in config:
        dedup_columns = config['dedup'].get('columns', [])
        primary_key = config.get('output', {}).get('primary_key', [])

        if dedup_columns == primary_key:
            del config['dedup']
            config['output']['dedup_enabled'] = True

            with open(config_path, 'w') as f:
                yaml.dump(config, f)
```

### 7.3 添加去重统计
在日志中记录去重统计信息：
```python
logger.info(f"Deduplication stats: {original_count} -> {len(df)} ({original_count - len(df)} filtered)")
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

**文档版本**: v1.0
**创建日期**: 2026-01-20
**最后更新**: 2026-01-20