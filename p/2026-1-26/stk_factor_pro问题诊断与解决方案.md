# stk_factor_pro接口问题诊断与解决方案

**文档日期**: 2026-01-27  
**问题接口**: stk_factor_pro  
**影响版本**: aspipe_v4 App4  
**严重级别**: 中（影响数据完整性和性能）

---

## 目录

1. [问题现象](#问题现象)
2. [问题诊断](#问题诊断)
   - 2.1 [类型转换错误](#21-类型转换错误)
   - 2.2 [重复文件保存](#22-重复文件保存)
   - 2.3 [去重功能失效](#23-去重功能失效)
3. [根本原因分析](#根本原因分析)
4. [解决方案](#解决方案)
   - 4.1 [优先级1：修复类型转换错误](#41-优先级1修复类型转换错误)
   - 4.2 [优先级2：消除重复保存](#42-优先级2消除重复保存)
   - 4.3 [优先级3：修复去重逻辑](#43-优先级3修复去重逻辑)
5. [验证方案](#验证方案)
6. [预期效果](#预期效果)

---

## 问题现象

运行 `stk_factor_pro` 接口时出现以下问题：

```bash
python app4/main.py --interface stk_factor_pro --ts_code 000014.SZ
```

### 日志表现

1. **ERROR日志**：多次出现类型转换错误
   ```
   ERROR - 创建DataFrame失败 for stk_factor_pro: could not append value: 1.8783 of type: f64 to the builder
   ERROR - 处理DataFrame时发生错误 for stk_factor_pro: could not append value: 1.8783 of type: f64 to the builder
   ```

2. **重复保存**：同一批数据保存了3个文件
   ```
   INFO - Wrote 8024 records to data/stk_factor_pro/stk_factor_pro_19920602_20260127_1769511511611_8752b584.parquet
   INFO - Wrote 8024 records to data/stk_factor_pro/stk_factor_pro_19920602_20260127_1769511512583_87e2cb01.parquet
   INFO - Wrote 8024 records to data/stk_factor_pro/stk_factor_pro_19920602_20260127_1769511514822_ce449967.parquet
   ```

3. **去重警告**：无法找到现有数据文件
   ```
   WARNING - Deduplication warning for stk_factor_pro: Existing file does not exist: data/stk_factor_pro/stk_factor_pro.parquet
   ```

4. **最终状态**：虽然报错，但最终文件成功保存（共3个文件）

---

## 问题诊断

### 2.1 类型转换错误

**错误信息**：
```
could not append value: 1.8783 of type: f64 to the builder
make sure that all rows have the same schema or consider increasing `infer_schema_length`
```

**发生位置**：`app4/core/storage.py:211`

**错误代码**：
```python
def _write_interface_data(self, interface_name: str, data: List[Dict[str, Any]]):
    # ...
    try:
        df = pl.DataFrame(data)  # ❌ 直接创建，不使用schema
    except Exception as df_error:
        logger.error(f"创建DataFrame失败 for {interface_name}: {str(df_error)}")
        # 尝试使用更大的推断长度
        df = pl.DataFrame(data, infer_schema_length=min(len(data), 100000))
```

**问题分析**：
- 代码直接调用 `pl.DataFrame(data)`，没有使用接口预定义的schema
- Polars自动推断时，前N行可能是整数类型，后续行出现浮点数导致类型冲突
- 尽管配置文件 `config/interfaces/stk_factor_pro.yaml` 中有342个字段的完整定义，但存储层绕过了schema管理
- 错误被捕获后，通过增大`infer_schema_length`回退成功，所以最终数据能保存

### 2.2 重复文件保存

**现象**：同一批数据（8024条记录）被保存了3次，生成3个不同时间戳的文件

**三条保存路径**：

| 时间 | 文件名 | 来源 | 代码位置 |
|------|--------|------|----------|
| 18:58:32 | `...1611_8752b584.parquet` | 处理线程写入 | `storage.py:289` |
| 18:58:33 | `...2583_87e2cb01.parquet` | main函数再次保存 | `main.py:419` |
| 18:58:35 | `...4822_ce449967.parquet` | flush缓存写入 | `storage.py:457` |

**路径1：正常处理流程**
```python
# storage.py:506-573
def _process_worker(self):
    # ...
    df = self.processor.process_data(task['data'], interface_config)  # 处理数据
    # ...
    self.save_data(interface_name, df.to_dicts(), async_write=True)  # 保存数据
    # ↓
    # 触发 _writer_worker → _write_interface_data → 写入文件1
```

**路径2：main函数重复保存**
```python
# main.py:358-425
def process_and_save_data():
    # ...
    df = processor.process_data(data, interface_config)  # 处理数据
    # ...
    storage_manager.save_data(interface_name, df.to_dicts(), async_write=True)  # ❌ 重复保存
    # 导致文件2生成
```

**路径3：flush缓存**
```python
# storage.py:435-465
def flush_remaining_data(self):
    # ...
    self.process_queue.put({...})  # 将剩余数据放入处理队列
    # 程序结束时触发，导致文件3生成
```

### 2.3 去重功能失效

**问题表现**：
```
WARNING - Deduplication warning for stk_factor_pro: Existing file does not exist: data/stk_factor_pro/stk_factor_pro.parquet
```

**问题代码**（`main.py:389`）：
```python
def process_and_save_data():
    # ...
    existing_file_path = os.path.join(data_dir, interface_name, f"{interface_name}.parquet")
    # 期望路径：data/stk_factor_pro/stk_factor_pro.parquet
```

**实际文件名生成**（`storage.py:270`）：
```python
def _write_interface_data(self, interface_name: str, data: List[Dict[str, Any]]):
    # ...
    file_name = f"{interface_name}_{date_range_str}_{current_time}_{unique_id}.parquet"
    # 实际文件名：stk_factor_pro_19920602_20260127_1769511511611_8752b584.parquet
```

**去重逻辑**（`dedup.py:283-287`）：
```python
def deduplicate_against_existing(new_data: pl.DataFrame, existing_data_path: str, ...):
    if not os.path.exists(existing_data_path):
        stats.add_warning(f"Existing file does not exist: {existing_data_path}")
        return new_data, stats  # 跳过去重
```

**结果**：因为固定文件名与实际文件名不匹配，去重逻辑被完全跳过。

---

## 根本原因分析

### 核心架构缺陷

**存储层与Schema管理层解耦不当**，违反了单一职责原则和依赖倒置原则。

**正常架构应该**：
```
Downloader → Processor (使用SchemaManager) → Storage (仅存储)
```

**实际架构**：
```
Downloader → Processor (使用SchemaManager) → Storage (绕过SchemaManager) ❌
                ↓
         Storage再次调用Processor (重复处理) ❌
                ↓
         Storage直接创建DataFrame (无schema) ❌
```

### 具体缺陷点

1. **存储层绕过Schema管理**（`storage.py:211`）
   - `_write_interface_data()` 直接调用 `pl.DataFrame(data)`
   - 没有使用 `SchemaManager.create_dataframe()` 或 `SchemaManager.load_schema()`
   - 导致类型推断失败

2. **多重保存路径**
   - `main.py:419` 显式调用 `save_data()`
   - `storage.py:573` 在 `_process_worker()` 中再次调用
   - `flush_remaining_data()` 触发第三次保存

3. **文件命名策略不一致**
   - 去重逻辑期望固定文件名：`{interface_name}.parquet`
   - 存储层使用时间戳文件名：`{interface}_{date}_{ts}_{uuid}.parquet`
   - 导致去重无法找到现有文件

### 为什么配置文件无效

`config/interfaces/stk_factor_pro.yaml` 确实有342个字段的完整定义，但由于存储层直接创建DataFrame，这些配置完全未被使用。

---

## 解决方案

### 修复原则

1. **存储层不负责数据转换**：存储层只负责存储，不进行DataFrame创建
2. **统一使用SchemaManager**：所有DataFrame创建必须通过SchemaManager
3. **消除重复保存**：数据只需保存一次
4. **文件命名一致性**：去重逻辑与存储逻辑使用相同的文件查找策略

---

### 4.1 优先级1：修复类型转换错误

**修改文件**：`app4/core/storage.py`

**修改内容**：

```python
# 在第10行附近添加导入
from .schema_manager import SchemaManager

# 修改 _write_interface_data 方法（第210-224行）
def _write_interface_data(self, interface_name: str, data: List[Dict[str, Any]]):
    """
    写入接口数据 - Parquet Dataset 模式
    """
    import uuid
    import time

    dir_path = os.path.join(self.storage_dir, interface_name)
    os.makedirs(dir_path, exist_ok=True)

    try:
        if not data:
            return

        # [优化] 增加写入时间戳，用于确定性去重
        current_time = int(time.time() * 1000)
        for item in data:
            item['_update_time'] = current_time

        # ✅ 使用SchemaManager安全创建DataFrame
        try:
            df = SchemaManager.create_dataframe_safe(data, interface_name)
            if df.is_empty():
                logger.error(f"无法为 {interface_name} 创建DataFrame，跳过保存")
                return
            logger.info(f"使用SchemaManager成功创建DataFrame for {interface_name}，记录数: {len(df)}")
        except Exception as df_error:
            logger.error(f"SchemaManager创建DataFrame失败 for {interface_name}: {str(df_error)}")
            return

        # 后续代码保持不变...
        # [优化] 从数据中提取日期范围用于文件名元数据
        # ...
```

**关键点**：
- 使用 `SchemaManager.create_dataframe_safe()` 替代直接创建
- 该方法已内置schema加载、回退机制和类型转换
- 删除原有的错误回退逻辑（因为SchemaManager已处理）

---

### 4.2 优先级2：消除重复保存

**需要修改2个文件**：

#### 修改1：删除 `main.py` 中的重复保存

**修改文件**：`app4/main.py`

**修改内容**（第418-419行）：

```python
def process_and_save_data(data, interface_name, interface_config, processor, storage_manager):
    """处理并保存数据的通用函数"""
    # ... 前面代码不变 ...

    # 保存数据
    # ❌ 删除以下这行（因为processor已通过storage_manager保存）
    # storage_manager.save_data(interface_name, df.to_dicts(), async_write=True)

    logger.info(f"Saved {len(df)} processed records for {interface_name}")
    # ...
```

#### 修改2：优化 `storage.py` 中的flush逻辑

**修改文件**：`app4/core/storage.py`

**修改内容**（第435-465行）：

```python
def flush_remaining_data(self):
    """处理所有缓存中的剩余数据"""
    items_to_flush = []

    with self.buffer_lock:
        for interface_name, buffer in self.interface_buffers.items():
            if buffer['count'] > 0 and buffer['data']:
                items_to_flush.append({
                    'interface_name': interface_name,
                    'data': buffer['data'],
                    'count': buffer['count']
                })
                # 重置缓存
                buffer['data'] = []
                buffer['count'] = 0

    # 处理收集的数据
    for item in items_to_flush:
        # ✅ 直接调用processor处理，而不是放入队列
        try:
            if self.processor:
                interface_config = self._get_interface_config(item['interface_name'])
                df = self.processor.process_data(item['data'], interface_config)
                if not df.is_empty():
                    # 保存数据（不通过队列，直接写入）
                    self._write_interface_data(item['interface_name'], df.to_dicts())
                    logger.info(f"Flushed and saved {len(df)} records for {item['interface_name']}")
        except Exception as e:
            logger.error(f"Failed to flush data for {item['interface_name']}: {str(e)}")
```

**关键点**：
- `main.py` 中删除显式的 `save_data()` 调用
- flush时直接调用 `processor.process_data()` → `_write_interface_data()`，不经过队列
- 避免数据在处理线程和flush时重复保存

---

### 4.3 优先级3：修复去重逻辑

**修改文件**：`app4/main.py`

**修改内容**（第387-389行）：

```python
def process_and_save_data(data, interface_name, interface_config, processor, storage_manager):
    """处理并保存数据的通用函数"""
    # ... 前面代码不变 ...

    # 如果去重功能启用且存在主键定义
    if dedup_config.get('dedup_enabled', True) and primary_keys:
        # ✅ 修改：获取存储目录路径，而不是固定文件路径
        data_dir = storage_manager.storage_dir
        interface_dir = os.path.join(data_dir, interface_name)

        # 读取该接口的所有现有数据文件（支持Parquet Dataset模式）
        if os.path.exists(interface_dir):
            existing_df = storage_manager.read_interface_data(interface_name, columns=primary_keys)

            if not existing_df.is_empty():
                # 使用临时文件进行去重（保持原有逻辑）
                import tempfile
                try:
                    with tempfile.NamedTemporaryFile(suffix='.parquet', delete=False) as tmp_file:
                        existing_df.write_parquet(tmp_file.name)
                        temp_path = tmp_file.name

                    # 使用统一的去重模块
                    df, dedup_stats = deduplicate_against_existing(
                        new_data=df,
                        existing_data_path=temp_path,
                        primary_keys=primary_keys
                    )
                    # ... 后续统计日志不变 ...
                finally:
                    if 'temp_path' in locals() and os.path.exists(temp_path):
                        os.unlink(temp_path)
```

**关键点**：
- 不再查找固定文件名的文件
- 使用 `storage_manager.read_interface_data()` 读取所有现有数据
- 与存储层的Parquet Dataset模式保持一致

---

## 验证方案

### 测试步骤

1. **清理旧数据**
   ```bash
   rm -rf /home/quan/testdata/aspipe_v4/data/stk_factor_pro/*
   ```

2. **运行测试命令**
   ```bash
   python app4/main.py --interface stk_factor_pro --ts_code 000014.SZ
   ```

3. **检查日志输出**
   ```bash
   # 应该只看到1次 "Wrote 8024 records"
   grep "Wrote.*8024" /home/quan/testdata/aspipe_v4/log/app4.log

   # 不应该再有类型转换错误
   grep "创建DataFrame失败" /home/quan/testdata/aspipe_v4/log/app4.log
   ```

4. **验证文件数量**
   ```bash
   ls -la /home/quan/testdata/aspipe_v4/data/stk_factor_pro/
   # 应该只有1个文件
   ```

5. **验证数据完整性**
   ```bash
   python -c "
   import polars as pl
   import glob
   files = glob.glob('/home/quan/testdata/aspipe_v4/data/stk_factor_pro/*.parquet')
   df = pl.read_parquet(files)
   print(f'✓ 记录数: {len(df)}')
   print(f'✓ 字段数: {len(df.columns)}')
   print(f'✓ 文件数: {len(files)} (应该为1)')
   "
   ```

6. **验证去重功能**
   ```bash
   # 再次运行相同命令
   python app4/main.py --interface stk_factor_pro --ts_code 000014.SZ

   # 检查日志 - 应该提示"No new records"或"0 duplicates"
   grep -i "duplicate\|exist" /home/quan/testdata/aspipe_v4/log/app4.log
   ```

### 预期日志

修复后应该看到的日志：
```
INFO - Starting aspipe_v4 App4
INFO - 预热全局缓存...
INFO - 预加载交易日历成功: 8572条记录
INFO - 预加载股票列表成功: 5473只股票
...
INFO - Downloaded 8024 records for 000014.SZ
INFO - Processed and queued 8024 records for stk_factor_pro
INFO - Wrote 8024 records to data/stk_factor_pro/stk_factor_pro_19920602_20260127_xxxx.parquet
INFO - Deduplication completed: input=8024, compared=0, output=8024, removed=0, dedup_rate=0.00%
INFO - Successfully downloaded 8024 total records
...
```

**不应该再出现的日志**：
- ❌ `ERROR - 创建DataFrame失败 for stk_factor_pro`
- ❌ `ERROR - 处理DataFrame时发生错误`
- ❌ 多次 `Wrote 8024 records`
- ❌ `Existing file does not exist`

---

## 预期效果

### 修复后效果

| 指标 | 修复前 | 修复后 | 改善 |
|------|--------|--------|------|
| 错误日志 | 5-6条ERROR | 0条ERROR | ✓ 消除 |
| 生成文件数 | 3个文件 | 1个文件 | ✓ 减少67% |
| 总运行时间 | 79.15秒 | ~75秒 | ✓ 提升5-10% |
| 去重功能 | 失效 | 正常工作 | ✓ 修复 |
| Schema使用 | 绕过配置 | 使用预定义schema | ✓ 正确 |

### 架构改善

1. **职责清晰**：存储层只负责存储，不进行数据转换
2. **配置生效**：接口配置文件中的schema定义被正确使用
3. **性能优化**：减少重复处理和保存，提升10%性能
4. **数据完整性**：使用预定义schema确保数据类型一致性
5. **可维护性**：代码逻辑更清晰，减少重复代码

---

## 附录

### 相关文件路径

```
/home/quan/testdata/aspipe_v4/app4/
├── main.py                          # 重复保存、去重逻辑
├── core/
│   ├── storage.py                   # 类型转换错误核心位置
│   ├── schema_manager.py            # Schema管理器（应该使用）
│   ├── processor.py                 # 数据处理器（已正确使用schema）
│   └── dedup.py                     # 去重模块
└── config/interfaces/
    └── stk_factor_pro.yaml          # 有342个字段的完整配置（未被使用）
```

### 配置文件示例

`config/interfaces/stk_factor_pro.yaml` 已正确定义342个字段：

```yaml
api_name: stk_factor_pro
description: 专业版技术指标因子数据

# 字段定义（342个字段）
fields:
  - name: ts_code
    type: str
    description: 股票代码
  - name: trade_date
    type: str
    description: 交易日期
  - name: open
    type: f64
    description: 开盘价
  # ... 更多字段 ...
  - name: xsii_td4_qfq
    type: f64
    description: 信号II-TD4-前复权

output:
  primary_key: ['ts_code', 'trade_date']  # 主键定义
  
dedup:
  enabled: true
```

### 技术债务记录

本次修复解决了以下技术债务：

1. **架构耦合**：存储层绕过业务层直接处理数据
2. **重复逻辑**：多处调用save_data()导致重复保存
3. **命名不一致**：去重与存储使用不同的文件命名策略
4. **错误处理不当**：依赖运行时回退而非预定义schema

---

**修复预计耗时**: 15-20分钟  
**测试预计耗时**: 10-15分钟  
**风险等级**: 低（修改集中在存储层，不影响核心数据下载逻辑）  
**回滚方案**: 使用git回退到修复前的版本
