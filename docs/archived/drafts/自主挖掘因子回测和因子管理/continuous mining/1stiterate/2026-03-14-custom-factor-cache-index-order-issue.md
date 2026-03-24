# 自定义因子缓存索引顺序问题

Status: draft
Owner: QuantaAlpha team
Created: 2026-03-14
Related-to: /home/quan/testdata/aspipe_v4/docs/drafts/自主挖掘因子回测和因子管理/2026-03-14-quantaalpha-continuous-factor-implementation-checklist.md

---

## 一、问题发现

### 现象

使用以下命令回测自定义因子时，得到异常结果：

```bash
cd /home/quan/testdata/aspipe_v4/third_party/quantaalpha
/root/miniforge3/envs/mining/bin/python -m quantaalpha.backtest.run_backtest \
  -c configs/backtest.yaml \
  --factor-source custom \
  --factor-json data/factorlib/single_factor.json
```

回测结果 JSON 显示：

```json
{
  "IC": 4.12e-17,
  "ICIR": 1.714322401706747,
  "Rank IC": NaN,
  "Rank ICIR": 0.0
}
```

**异常点**：
- IC ≈ 0 (4.12e-17)，几乎完全失去预测能力
- Rank IC = NaN，无法计算
- 1day 的所有组合回测指标都是 null

### 对比历史结果

同一个因子在 `single_factor.json` 中记录的历史回测结果是：

```json
{
  "IC": 0.01320778,
  "Rank IC": 0.0152122,
  "ICIR": 0.20105166,
  "Rank ICIR": 0.22234686
}
```

**差异**：IC 从 0.013 变成 ~0，说明因子数据没有正确加载到回测中。

---

## 二、问题排查

### 1. 确认缓存文件存在

因子 `760e1cbc615bf392` 的缓存文件路径：

```
/home/quan/testdata/aspipe_v4/third_party/data/results/workspace_exp_20260311_201331/aceb072601ae45ef91fa248e61162f35/result.h5
```

文件存在且大小正常（3.2MB）。

### 2. 检查缓存文件内容

```python
import pandas as pd
result = pd.read_hdf('result.h5')
print(f'类型：{type(result)}')           # <class 'pandas.core.series.Series'>
print(f'形状：{result.shape}')           # (285298,)
print(f'索引名称：{result.index.names}')  # ['datetime', 'instrument']
print(f'空值数量：{result.isna().sum()}')  # 200
```

**发现**：缓存文件的索引顺序是 `['datetime', 'instrument']`。

### 3. 确认 Qlib 需要的索引顺序

```python
import qlib
from qlib.data import D

qlib.init(provider_uri='~/.qlib/qlib_data/cn_data', region='cn')
data = D.features(['000001.SZ'], ['$close'], '2022-01-01', '2022-01-31')
print(f'索引名称：{data.index.names}')  # ['instrument', 'datetime']
```

**发现**：Qlib 标准数据格式使用 `['instrument', 'datetime']` 顺序。

### 4. 追踪数据处理流程

#### 4.1 缓存加载入口

`CustomFactorCalculator._load_from_cache_location()` 从 result.h5 读取数据后，调用 `_process_cached_result()` 进行格式标准化。

#### 4.2 `_process_cached_result` 方法逻辑

```python
def _process_cached_result(self, result: Any, source: str) -> Optional[pd.Series]:
    """Normalize cached result format (does not touch self.data_df to avoid lazy load)."""
    try:
        if isinstance(result, pd.DataFrame):
            if len(result.columns) == 1:
                result = result.iloc[:, 0]
            elif 'factor' in result.columns:
                result = result['factor']
            else:
                result = result.iloc[:, 0]

        # Standard order: (datetime, instrument)  ← 问题在这里！
        if isinstance(result.index, pd.MultiIndex):
            cache_idx_names = list(result.index.names)
            expected_order = ['datetime', 'instrument']
            if cache_idx_names != expected_order and set(cache_idx_names) == set(expected_order):
                result = result.swaplevel()
                result = result.sort_index()

        return result
    except Exception as e:
        logger.debug(f"Process cached result failed [{source}]: {e}")
        return None
```

**问题代码**：

```python
# Standard order: (datetime, instrument)  ← 错误的假设
expected_order = ['datetime', 'instrument']
if cache_idx_names != expected_order and set(cache_idx_names) == set(expected_order):
    result = result.swaplevel()
    result = result.sort_index()
```

这段代码认为 `['datetime', 'instrument']` 是"标准顺序"，所以当缓存文件的索引顺序正好是 `['datetime', 'instrument']` 时，**不会进行任何转换**。

#### 4.3 回测数据对齐逻辑

在 `BacktestRunner._create_dataset_with_computed_factors()` 中：

```python
def _normalize_multiindex(df, df_name):
    """Ensure MultiIndex has standard (datetime, instrument) level names."""
    # ... 代码省略 ...
    
    actual_names = list(df.index.names)
    if len(actual_names) == 2 and actual_names == ['instrument', 'datetime']:
        df = df.swaplevel()      # 把 ['instrument', 'datetime'] 转成 ['datetime', 'instrument']
        df = df.sort_index()
        logger.debug(f"  {df_name} index swapped to (datetime, instrument)")

    return df
```

**发现**：这个函数会把 `['instrument', 'datetime']` 顺序的数据交换成 `['datetime', 'instrument']`。

### 5. 数据流总结

```
缓存文件 (result.h5)
  ↓ 索引顺序：['datetime', 'instrument']
  ↓
_process_cached_result()
  ↓ 认为 ['datetime', 'instrument'] 是"标准顺序"，不做转换
  ↓ 输出：['datetime', 'instrument']
  ↓
_normalize_multiindex()
  ↓ 期望输入是 ['instrument', 'datetime']，但实际收到 ['datetime', 'instrument']
  ↓ 条件判断不满足，不做转换
  ↓ 输出：['datetime', 'instrument']（错误顺序）
  ↓
Qlib 回测
  ↓ 期望 ['instrument', 'datetime']，但实际收到 ['datetime', 'instrument']
  ↓ 数据无法正确对齐
  ↓ IC ≈ 0
```

---

## 三、根本原因

**核心问题**：`_process_cached_result()` 方法中对"标准顺序"的定义错误。

```python
# 错误代码
expected_order = ['datetime', 'instrument']  # ❌ 这不是 Qlib 的标准顺序
```

**正确顺序**：Qlib 的标准数据格式使用 `['instrument', 'datetime']` 作为 MultiIndex 的顺序。

### 为什么之前能工作？

查看因子库 JSON 中记录的历史回测结果，IC = 0.013 是有效的。这说明在某个时间点之前，系统是正常工作的。

可能的原因：
1. 之前的缓存文件索引顺序是 `['instrument', 'datetime']`
2. 或者之前的数据处理逻辑与现在不同
3. 或者因子是在不同版本的代码下计算的

### 因子计算时的索引顺序

查看因子计算代码（`factor.py`）：

```python
def calculate_factor(expr: str, name: str):
    df = pd.read_hdf('./daily_pv.h5', key='data')
    # ... 解析表达式 ...
    df[name] = eval(expr)
    result = df[name].astype(np.float64)
    result.to_hdf('result.h5', key='data')
```

`daily_pv.h5` 的索引顺序决定了输出 `result.h5` 的索引顺序。如果原始数据使用 `['datetime', 'instrument']` 顺序，那么计算结果也会保持这个顺序。

---

## 四、解决方案

### 方案 1：修复 `_process_cached_result()` 方法

将"标准顺序"从 `['datetime', 'instrument']` 改为 `['instrument', 'datetime']`：

```python
def _process_cached_result(self, result: Any, source: str) -> Optional[pd.Series]:
    """Normalize cached result format (does not touch self.data_df to avoid lazy load)."""
    try:
        if isinstance(result, pd.DataFrame):
            if len(result.columns) == 1:
                result = result.iloc[:, 0]
            elif 'factor' in result.columns:
                result = result['factor']
            else:
                result = result.iloc[:, 0]

        # Standard order for Qlib: (instrument, datetime)
        if isinstance(result.index, pd.MultiIndex):
            cache_idx_names = list(result.index.names)
            expected_order = ['instrument', 'datetime']  # ✅ 修正为 Qlib 标准顺序
            if cache_idx_names != expected_order and set(cache_idx_names) == set(expected_order):
                result = result.swaplevel()
                result = result.sort_index()

        return result
    except Exception as e:
        logger.debug(f"Process cached result failed [{source}]: {e}")
        return None
```

### 方案 2：同时修复因子计算输出格式

修改因子计算代码，确保输出的 `result.h5` 使用 `['instrument', 'datetime']` 顺序：

```python
def calculate_factor(expr: str, name: str):
    df = pd.read_hdf('./daily_pv.h5', key='data')
    # ... 解析表达式 ...
    df[name] = eval(expr)
    result = df[name].astype(np.float64)
    
    # 确保索引顺序是 ['instrument', 'datetime']
    if isinstance(result.index, pd.MultiIndex):
        if result.index.names == ['datetime', 'instrument']:
            result = result.swaplevel()
            result = result.sort_index()
    
    result.to_hdf('result.h5', key='data')
```

### 推荐方案

**同时实施方案 1 和方案 2**：
- 方案 1 确保现有缓存文件能被正确加载
- 方案 2 确保新生成的缓存文件格式正确

---

## 五、验证方法

### 1. 单元测试

```python
def test_cache_index_order():
    """测试缓存加载后的索引顺序是否正确。"""
    import pandas as pd
    from quantaalpha.backtest.custom_factor_calculator import CustomFactorCalculator
    
    # 创建测试数据（模拟缓存文件，索引顺序为 ['datetime', 'instrument']）
    dates = pd.date_range('2022-01-01', periods=10)
    instruments = ['000001.SZ', '000002.SZ', '000003.SZ']
    index = pd.MultiIndex.from_product([dates, instruments], names=['datetime', 'instrument'])
    data = pd.Series(np.random.randn(len(index)), index=index)
    
    # 保存到临时文件
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.h5', delete=False) as f:
        data.to_hdf(f.name, key='data')
        cache_path = f.name
    
    try:
        # 加载并处理
        calc = CustomFactorCalculator()
        cache_location = {'result_h5_path': cache_path}
        result = calc._load_from_cache_location(cache_location)
        
        # 验证索引顺序
        assert result.index.names == ['instrument', 'datetime'], \
            f"Expected ['instrument', 'datetime'], got {result.index.names}"
        
    finally:
        import os
        os.unlink(cache_path)
```

### 2. 集成测试

```bash
# 修复后重新运行回测
cd /home/quan/testdata/aspipe_v4/third_party/quantaalpha
/root/miniforge3/envs/mining/bin/python -m quantaalpha.backtest.run_backtest \
  -c configs/backtest.yaml \
  --factor-source custom \
  --factor-json data/factorlib/single_factor.json

# 验证结果
# 预期：IC ≈ 0.013（与历史记录一致）
```

### 3. 手工验证

```python
import pandas as pd

# 读取缓存
result = pd.read_hdf('result.h5')
print(f'原始索引顺序：{result.index.names}')

# 模拟修复后的处理
if result.index.names == ['datetime', 'instrument']:
    result = result.swaplevel()
    result = result.sort_index()

print(f'处理后索引顺序：{result.index.names}')
# 预期输出：['instrument', 'datetime']
```

---

## 六、影响范围

### 受影响的模块

1. `quantaalpha/backtest/custom_factor_calculator.py`
   - `_process_cached_result()` 方法
   - `_load_from_cache_location()` 方法（间接影响）

2. `quantaalpha/backtest/runner.py`
   - `_normalize_multiindex()` 方法（可能需要调整注释）

### 受影响的场景

1. **使用缓存的自定义因子回测**：所有从 `result.h5` 加载的因子都会受影响
2. **因子库复验**：使用 `revalidate` 命令时，如果因子有缓存路径，会受影响
3. **演化流程**：evolution 阶段加载历史因子结果时，会受影响

### 不受影响的场景

1. **Qlib 官方因子**：alpha158/alpha360 等官方因子使用 QlibDataLoader，不经过此逻辑
2. **实时计算的自定义因子**：不使用缓存、直接从表达式计算的因子不受影响

---

## 七、经验教训

### 1. 索引顺序规范

**问题**：代码中对"标准顺序"的定义不一致。

- `_process_cached_result()` 认为 `['datetime', 'instrument']` 是标准
- `_normalize_multiindex()` 会把 `['instrument', 'datetime']` 转成 `['datetime', 'instrument']`
- Qlib 实际使用 `['instrument', 'datetime']`

**改进**：
- 在项目中明确定义索引顺序规范
- 在关键函数中添加文档说明期望的输入/输出格式
- 考虑添加索引顺序验证的单元测试

### 2. 缓存格式兼容性

**问题**：缓存文件的格式依赖于计算时的数据顺序，没有显式标准化。

**改进**：
- 在保存缓存时显式转换索引顺序
- 在缓存元数据中记录索引顺序信息
- 考虑使用更稳定的缓存格式（如包含 schema 版本）

### 3. 测试覆盖

**问题**：这个明显的索引顺序问题没有在测试中被发现。

**改进**：
- 添加缓存加载的集成测试
- 测试数据对齐逻辑的边界情况
- 在回测结果验证中添加 IC 合理性检查（如 IC 不应接近 0）

---

## 八、待办事项

- [ ] 修复 `_process_cached_result()` 中的索引顺序定义
- [ ] 修复因子计算输出，确保保存时使用正确顺序
- [ ] 添加索引顺序单元测试
- [ ] 添加缓存加载集成测试
- [ ] 更新相关文档，明确索引顺序规范
- [ ] 检查其他可能存在类似问题的模块

---

## 九、参考

- Qlib 数据格式文档：https://qlib.readthedocs.io/en/latest/component/data.html
- Pandas MultiIndex 文档：https://pandas.pydata.org/docs/user_guide/advanced.html
- 相关代码文件：
  - `quantaalpha/backtest/custom_factor_calculator.py`
  - `quantaalpha/backtest/runner.py`
  - `quantaalpha/backtest/factor_loader.py`
