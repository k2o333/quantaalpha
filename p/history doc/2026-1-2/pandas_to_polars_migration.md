# 将 pandas 替换为 polars 的分析与实施方案

## 项目概述

项目路径：`/home/quan/testdata/aspipe_v4/app4`

该项目目前同时使用 pandas 和 polars，但核心数据处理逻辑主要依赖 pandas。代码中已经存在从 pandas 到 polars 的转换逻辑，表明开发者已有意迁移到 polars。

## 当前 pandas 使用情况分析

### 1. core/processor.py
- **导入**: `import pandas as pd`
- **创建 DataFrame**: `pd.DataFrame(data)`
- **类型转换**: 
  - `pd.to_datetime(df[column_name], format=date_format, errors='coerce')`
  - `pd.to_numeric(df[column_name], errors='coerce').astype('Int64')`
  - `pd.to_numeric(df[column_name], errors='coerce')`
- **数据操作**:
  - `df.drop_duplicates(subset=existing_keys, keep='last')`
  - `df.sort_values(by=existing_sort_fields)`
  - `df.fillna(value=np.nan)`
  - `df.dropna(how='all')`
  - `df.dropna(axis=1, how='all')`
  - `df.duplicated(subset=existing_keys, keep=False)`

### 2. core/cache_manager.py
- **导入**: `import pandas as pd`
- **类型检查**: `isinstance(data, pd.DataFrame)`
- **转换**: `pl.from_pandas(data)` 将 pandas DataFrame 转换为 polars

### 3. main.py
- **导入**: `import pandas as pd` (仅在 broker_recommend 接口处理中使用)
- **日期范围生成**: `pd.date_range(params['start_date'], params['end_date'], freq='M')`

### 4. core/storage.py
- **导入**: `import pandas as pd` (但实际代码中并未使用)

## polars 替换方案

### 1. core/processor.py 修改方案

#### 创建 DataFrame
```python
# 原代码
df = pd.DataFrame(data)

# 替换为
df = pl.DataFrame(data)
```

#### 类型转换
```python
# 原代码
df[column_name] = pd.to_datetime(df[column_name], format=date_format, errors='coerce')

# 替换为
df = df.with_columns([
    pl.col(column_name).str.strptime(pl.Date, date_format, strict=False).alias(column_name)
])
```

```python
# 原代码
df[column_name] = pd.to_numeric(df[column_name], errors='coerce').astype('Int64')

# 替换为
df = df.with_columns([
    pl.col(column_name).cast(pl.Int64, strict=False).alias(column_name)
])
```

```python
# 原代码
df[column_name] = pd.to_numeric(df[column_name], errors='coerce')

# 替换为
df = df.with_columns([
    pl.col(column_name).cast(pl.Float64, strict=False).alias(column_name)
])
```

#### 数据操作
```python
# 原代码
df = df.drop_duplicates(subset=existing_keys, keep='last')

# 替换为
df = df.unique(subset=existing_keys, keep='last')
```

```python
# 原代码
df = df.sort_values(by=existing_sort_fields)

# 替换为
df = df.sort(by=existing_sort_fields)
```

```python
# 原代码
df = df.fillna(value=np.nan)

# 替换为
df = df.fill_null(np.nan)
```

```python
# 原代码
df = df.dropna(how='all')

# 替换为
df = df.filter(~pl.fold(acc=True, function=lambda acc, s: acc & s.is_null(), exprs=pl.all()))
```

```python
# 原代码
df = df.dropna(axis=1, how='all')

# 替换为
df = df[[col for col in df.columns if not df[col].null_count() == len(df)]]
```

```python
# 原代码
duplicates = df.duplicated(subset=existing_keys, keep=False)

# 替换为
duplicates = df.with_columns(
    pl.int_range(0, pl.len()).alias('__index')
).group_by(existing_keys).agg(
    pl.col('__index').list()
).filter(
    pl.col('__index').list.lengths() > 1
).explode('__index').select(
    pl.col('__index')
)
```

### 2. core/cache_manager.py 修改方案

```python
# 移除 pandas 导入
# import pandas as pd

# 修改类型检查
elif isinstance(data, pl.DataFrame):
    # 如果已经是Polars DataFrame
    data.write_parquet(temp_path)
```

### 3. main.py 修改方案

```python
# 原代码
months = pd.date_range(
    params['start_date'],
    params['end_date'],
    freq='M'
).strftime('%Y%m').tolist()

# 替换为
import datetime
from dateutil.relativedelta import relativedelta

start = datetime.datetime.strptime(params['start_date'][:6] + '01', '%Y%m%d')
end = datetime.datetime.strptime(params['end_date'][:6] + '01', '%Y%m%d')
months = []
current = start
while current <= end:
    months.append(current.strftime('%Y%m'))
    current += relativedelta(months=1)
```

## 修改步骤

### 第一步：修改 core/processor.py
1. 替换所有 pandas DataFrame 操作为 polars 对应操作
2. 更新函数签名中的类型注解
3. 测试数据处理功能

### 第二步：修改 core/cache_manager.py
1. 移除 pandas 导入
2. 更新类型检查逻辑
3. 确保缓存功能正常

### 第三步：修改 main.py
1. 替换 pd.date_range 的使用
2. 移除不必要的 pandas 导入

### 第四步：更新 requirements.txt
1. 移除 pandas 依赖（如果不再需要）
2. 确保 polars 版本满足需求

## 预期收益

1. **性能提升**: Polars 基于 Apache Arrow，具有更好的内存效率和处理速度
2. **并行处理**: Polars 天然支持并行操作
3. **内存效率**: 更少的内存占用
4. **现代化 API**: 更直观的链式操作

## 风险与注意事项

1. **API 差异**: 需要仔细处理 pandas 和 polars 之间的 API 差异
2. **数据类型**: 注意数据类型转换的差异
3. **测试验证**: 需要充分测试确保数据处理逻辑的正确性
4. **学习曲线**: 团队需要熟悉 polars 的 API

## 结论

项目中已经存在从 pandas 到 polars 的转换逻辑，说明开发者已有意迁移到 polars。完全替换为 polars 是可行的，并且会带来显著的性能和内存效率提升。建议按上述步骤逐步实施迁移。