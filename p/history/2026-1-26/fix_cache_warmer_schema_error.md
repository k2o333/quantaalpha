# 修复CacheWarmer Schema错误 - extra column in file outside of expected schema

**日期**: 2026-01-29
**错误**: `extra column in file outside of expected schema: cal_date_dt`
**影响**: 交易日历预加载失败
**优先级**: 🟡 中（非阻塞，有fallback）

---

## 🐛 错误现象

### 错误日志

```
2026-01-29 20:14:11,594 - core.cache_warmer - ERROR - 预加载交易日历失败: extra column in file outside of expected schema: cal_date_dt, hint: specify this column in the schema, or pass extra_columns='ignore' in scan options. File containing extra column: 'data/trade_cal/trade_cal_19901219_20260128_1769614405077_76b9b066.parquet'.
```

### 错误影响

- 交易日历预加载失败，但程序继续运行（有fallback到API）
- 每次启动都会重新从API获取交易日历（增加API调用）
- 不影响数据下载和保存功能

---

## 🔍 根本原因分析

### 1. Schema不匹配

**数据写入方** (processor → storage):
```python
# processor.py → SchemaManager.create_dataframe_safe()
1. 创建DataFrame from data
2. SchemaManager.apply_derived_fields(df, interface_name)  # ✅ 添加cal_date_dt等衍生字段
3. df.with_columns(_update_time)  # ✅ 添加系统字段
4. storage.save_data() → 写入parquet文件  # ✅ 文件包含：原始字段 + 衍生字段 + 系统字段
```

**数据读取方** (cache_warmer):
```python
# cache_warmer.preload_trade_calendar()
1. pl.read_parquet(trade_cal_dir)  # ❌ 读取所有parquet文件
2. df.filter(...).select(['cal_date', 'is_open', 'exchange'])  # ❌ 只选择需要的列
```

**问题**:
- 写入的parquet文件包含：`cal_date`, `is_open`, `exchange`, `cal_date_dt`, `pretrade_date_dt`, `is_open_bool`, `_update_time`
- cache_warmer只选择：`cal_date`, `is_open`, `exchange`
- polars读取多个文件时，如果schema不一致（有的文件有`cal_date_dt`，有的没有），会报错

### 2. 为什么之前没发现？

**时间线分析**:
- **1月19日**: 添加derived_fields支持 → processor开始写入cal_date_dt到parquet
- **1月26日**: 添加CacheWarmer → 开始读取parquet文件
- **初始阶段**: 只有一个parquet文件（1769438716328_a66e8c1a），没有schema不一致问题
- **后续运行**: 生成多个parquet文件（如1769614405077_76b9b066），schema一致，也没问题
- **问题出现**: 某些文件可能schema不一致（可能是程序异常退出导致）

**文件列表分析**:
```bash
# 1月26日: 100K (正常)
trade_cal_19901219_20260126_1769438716328_a66e8c1a.parquet

# 1月27日: 100K (正常)
trade_cal_19901219_20260127_1769501606464_c172a8ad.parquet
...

# 1月28日: 207K (异常！文件大小翻倍)
trade_cal_19901219_20260128_1769614405077_76b9b066.parquet
```

**问题文件特征**:
- 文件大小: 207K (其他文件100K)
- 创建时间: 1月28日 23:33
- 可能原因: 程序异常退出，导致文件损坏或schema异常

### 3. 是文档问题还是代码改坏？

**答案: 代码设计问题，不是用户改坏的**

**证据**:
1. CacheWarmer在1月26日添加时，就有这个问题（没有考虑derived_fields）
2. derived_fields在1月19日添加，早于CacheWarmer
3. 问题根源是CacheWarmer没有处理schema不一致的情况

**用户commit的影响**:
- 用户最近没有修改trade_cal.yaml配置
- 用户最近没有修改CacheWarmer代码
- 用户的dup3分支修改（save twice）不影响derived_fields处理

**结论**: 这个问题从CacheWarmer添加时就存在，不是用户改坏的

---

## ✅ 修复方案

### 方案1: 修改CacheWarmer（推荐，1分钟）

在读取parquet时忽略额外列。

**文件**: `app4/core/cache_warmer.py`

**修改位置**: `preload_trade_calendar()`方法

**修改前**:
```python
try:
    # 读取所有交易日历文件
    df = pl.read_parquet(trade_cal_dir)
    
    # 过滤有效交易日
    df = df.filter(
        (pl.col('is_open') == 1) &
        (pl.col('exchange') == 'SSE')
    ).select(['cal_date', 'is_open', 'exchange'])
    # ...
```

**修改后**:
```python
try:
    # ✅ 修复：读取时忽略额外列，只读取需要的字段
    import polars.selectors as cs
    
    # 读取所有交易日历文件，只选择需要的列
    df = pl.read_parquet(trade_cal_dir, columns=['cal_date', 'is_open', 'exchange', 'pretrade_date'])
    
    # 过滤有效交易日
    df = df.filter(
        (pl.col('is_open') == 1) &
        (pl.col('exchange') == 'SSE')
    ).select(['cal_date', 'is_open', 'exchange'])
    # ...
```

**优点**:
- 只读取需要的列，忽略额外列
- 避免schema不一致问题
- 提高读取性能（减少内存占用）

**缺点**:
- 需要明确指定所有需要的列（包括可能用于后续处理的列）

### 方案2: 使用polars scan（备选）

使用`pl.scan_parquet()` + `collect()`，并设置schema选项。

**修改前**:
```python
df = pl.read_parquet(trade_cal_dir)
```

**修改后**:
```python
# ✅ 修复：使用scan_parquet并忽略额外列
df = pl.scan_parquet(trade_cal_dir, low_memory=True).select(
    ['cal_date', 'is_open', 'exchange']
).collect()
```

**优点**:
- scan_parquet对大数据集更友好
- 可以延迟选择列

**缺点**:
- 如果schema严重不一致，可能仍然报错

### 方案3: 清理异常文件（临时方案）

删除schema异常的文件，让程序重新生成。

```bash
# 备份异常文件
mkdir -p /tmp/trade_cal_backup
cp data/trade_cal/trade_cal_19901219_20260128_1769614405077_76b9b066.parquet /tmp/trade_cal_backup/

# 删除异常文件
rm data/trade_cal/trade_cal_19901219_20260128_1769614405077_76b9b066.parquet

# 重新运行程序，会自动重新下载并生成正确的文件
python app4/main.py --interface trade_cal --start_date 19900101 --end_date 20260129
```

**优点**:
- 快速解决问题
- 不需要修改代码

**缺点**:
- 治标不治本，问题可能再次出现
- 需要手动干预

### 推荐：使用方案1

---

## 🧪 验证修复

### 验证步骤

1. **应用修复**: 修改cache_warmer.py
```python
# 添加columns参数
df = pl.read_parquet(trade_cal_dir, columns=['cal_date', 'is_open', 'exchange', 'pretrade_date'])
```

2. **重新运行**:
```bash
python app4/main.py --interface stk_factor_pro --ts_code 000014.SZ
```

3. **预期输出**:
```
# 修复前:
2026-01-29 20:14:11,594 - core.cache_warmer - ERROR - 预加载交易日历失败: extra column in file outside of expected schema: cal_date_dt

# 修复后:
2026-01-29 20:14:11,594 - core.cache_warmer - INFO - 预加载交易日历成功: 8574条记录
```

4. **验证数据正确性**:
```bash
# 检查是否正确加载了交易日历
ls -lh data/trade_cal/*.parquet
# 应该有文件存在，且文件大小正常
```

### 验证标准

✅ **修复成功**:
- 没有`extra column in file outside of expected schema`错误
- 显示`预加载交易日历成功: X条记录`
- 程序正常运行，数据正确下载和保存

❌ **修复失败**:
- 仍然出现schema错误
- 交易日历预加载失败

---

## 📚 相关文档更新

### 更新cache_warmer文档

在CacheWarmer类文档中添加说明：

```python
class CacheWarmer:
    """
    缓存预热器 - 预加载常用数据到内存
    
    注意事项:
    - 读取parquet文件时，只读取必要的列，忽略衍生字段
    - 如果parquet文件schema不一致，使用columns参数指定需要的列
    - 预加载失败时，会自动从API获取（fallback机制）
    """
```

### 更新架构文档

在架构文档中添加：

```markdown
### Schema兼容性

**问题**: processor写入的parquet包含derived_fields，cache_warmer读取时可能schema不一致

**解决方案**: cache_warmer读取时明确指定columns参数，只读取需要的列

**代码示例**:
```python
# 写入时（包含derived_fields）
df = SchemaManager.apply_derived_fields(df, interface_name)  # 添加cal_date_dt等
storage.save_data(df)  # 写入parquet（包含derived_fields）

# 读取时（只读取需要的列）
df = pl.read_parquet(dir_path, columns=['cal_date', 'is_open', 'exchange'])  # 忽略derived_fields
```
```

---

## 💡 根本原因总结

### 问题根源

1. **设计不一致**: processor写入完整schema（原始+衍生），cache_warmer期望简洁schema（只原始）
2. **异常处理不足**: 没有考虑parquet文件可能损坏或schema不一致的情况
3. **测试覆盖不足**: 没有测试过多个parquet文件schema不一致的场景

### 责任归属

- **不是用户改坏的**: 用户最近没有修改相关代码
- **是代码设计问题**: CacheWarmer在1月26日添加时就有这个问题
- **是隐藏Bug**: 在特定条件下才会触发（schema不一致的文件）

### 经验教训

1. **读写一致性**: 写入方和读取方应该协商好schema
2. **异常处理**: 读取数据时应该处理schema不一致的情况
3. **测试覆盖**: 需要测试边界情况，如文件损坏、schema不一致等
4. **版本兼容**: 考虑代码升级时的数据兼容性

---

## 📋 后续行动

### 立即行动

1. **修复CacheWarmer**: 应用方案1，添加columns参数
2. **验证修复**: 重新运行，确认错误消失
3. **清理异常文件**: 删除schema异常的文件（可选）

### 短期行动

1. **更新文档**: 添加schema兼容性说明
2. **添加测试**: 测试多个parquet文件schema不一致的场景
3. **添加监控**: 监控parquet文件的schema一致性

### 长期行动

1. **Schema版本管理**: 为parquet文件添加schema版本号
2. **数据迁移工具**: 提供工具将旧schema文件转换为新schema
3. **写入时过滤**: 考虑在写入时只保留必要字段（不包括derived_fields）

---

**文档版本**: 1.0
**创建日期**: 2026-01-29
**作者**: iFlow CLI
**适用场景**: CacheWarmer预加载失败，报错extra column in file outside of expected schema
**关联文档**: buffer_mechanism_analysis_and_solution.md, fix_validate_data_bug.md