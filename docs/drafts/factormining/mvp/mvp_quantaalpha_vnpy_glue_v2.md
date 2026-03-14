# QuantaAlpha + vnpy MVP 集成方案 (修正版)

## 1. 文档目的

本文档是对 `mvp_quantaalpha_vnpy_glue.md` 的修正版本，指出了原文档中存在的问题，并提供正确的实施方案。

**核心目标：** 通过胶水代码串联 QuantaAlpha（LLM因子生成）与 vnpy（回测引擎），验证因子挖掘闭环。

---

## 2. 原方案存在的问题

### 2.1 变量名格式不匹配

| 来源 | 变量格式 | 示例 |
|-----|---------|------|
| **QuantaAlpha** | 带 `$` 前缀 | `$close`, `$volume`, `$vwap` |
| **vnpy** | 无前缀 | `close`, `volume` |
| **原文档错误** | 全大写无前缀 | `CLOSE`, `VOLUME` |

> **TODO:** 查 deepwiki `QuantaAlpha/QuantaAlpha` 确认变量命名规范

### 2.2 算子命名差异

**核心问题：** vnpy 区分时序函数(`ts_*`)和截面函数(`cs_*`)，而 QuantaAlpha 的命名规则不同。

| QuantaAlpha | vnpy | 函数类型 |
|-------------|------|---------|
| `TS_RANK` | `ts_rank` | 时序排名 |
| `DELAY` | `ts_delay` | 时序滞后 |
| `RANK` | `cs_rank` | 截面排名 |
| `ZSCORE` | 需确认 | 截面标准化 |

> **TODO:** 查 deepwiki `vnpy/vnpy` 的 `ts_function` 和 `cs_function` 模块确认完整映射

### 2.3 数据格式要求缺失

vnpy 的 `AlphaDataset` 要求输入 DataFrame 必须包含：
- `datetime` - 时间戳
- `vt_symbol` - 合约标识符
- OHLCV 数据列

原文档未说明这些必需字段。

> **TODO:** 查 deepwiki `vnpy/vnpy` 确认 AlphaDataset 输入格式要求

### 2.4 API 调用流程不完整

原文档伪代码缺少关键步骤：
- 未调用 `prepare_data()` 触发因子计算
- 未说明如何设置标签(label)
- 未说明时间周期划分(`train_period`, `valid_period`, `test_period`)

> **TODO:** 查 deepwiki `vnpy/vnpy` 确认 AlphaDataset 完整使用流程

### 2.5 表达式语法兼容性

QuantaAlpha 支持的表达式语法在 vnpy 中可能不兼容：
- 条件表达式：`(C)?(A):(B)`
- 逻辑运算符：`(C1)&&(C2)`, `(C1)||(C2)`

> **TODO:** 查 deepwiki `vnpy/vnpy` 确认表达式解析器支持的语法

---

## 3. 修正后的实施步骤

### 步骤 1: 环境准备

```bash
pip install vnpy quantaalpha polars
```

> **TODO:** 查 deepwiki `QuantaAlpha/QuantaAlpha` 确认安装方式和依赖

### 步骤 2: 准备测试数据

数据必须包含以下列：
- `datetime` - 时间戳
- `vt_symbol` - 合约标识（格式如 `000001.SZSE`）
- `open`, `high`, `low`, `close`, `volume` 等

```python
# 示例数据结构
# df = pl.DataFrame({
#     "datetime": [...],
#     "vt_symbol": [...],
#     "open": [...],
#     "high": [...],
#     "low": [...],
#     "close": [...],
#     "volume": [...]
# })
```

### 步骤 3: 运行 QuantaAlpha 生成因子

QuantaAlpha 输出格式（JSON）：

```json
{
    "factor_id": "F001",
    "factor_expression": "TS_RANK(TS_DELTA($close, 1), 10)",
    "factor_description": "...",
    "backtest_results": {...}
}
```

> **TODO:** 查 deepwiki `QuantaAlpha/QuantaAlpha` 确认因子输出格式和支持的算子列表

### 步骤 4: 编写胶水代码

核心逻辑：

```python
# 1. 表达式转换
def translate_expression(qalpha_expr: str) -> str:
    # 去除 $ 前缀
    # 映射时序函数 (ts_*)
    # 映射截面函数 (cs_*)
    # 处理条件表达式语法
    pass

# 2. 创建 AlphaDataset
from vnpy.alpha.dataset import AlphaDataset

dataset = AlphaDataset(
    df=pl.read_parquet("test_data.parquet"),
    train_period=("2020-01-01", "2021-01-01"),
    valid_period=("2021-01-01", "2022-01-01"),
    test_period=("2022-01-01", "2023-01-01")
)

# 3. 添加因子
dataset.add_feature("factor_1", expression=translated_expr)

# 4. 设置标签（未来收益）
dataset.set_label("ts_delay(close, -1) / close - 1")

# 5. 触发计算
dataset.prepare_data()

# 6. 计算 IC
# ...
```

> **TODO:** 查 deepwiki `vnpy/vnpy` 确认完整 API 示例

### 步骤 5: 验证闭环

- 成功计算的因子 → 保存到 `success_factors.csv`
- 解析/计算失败的因子 → 记录错误日志

---

## 4. 待确认事项清单

| 序号 | 事项 | 查询来源 |
|-----|------|---------|
| 1 | QuantaAlpha 变量命名规范 | deepwiki `QuantaAlpha/QuantaAlpha` |
| 2 | QuantaAlpha 支持的算子完整列表 | deepwiki `QuantaAlpha/QuantaAlpha` |
| 3 | QuantaAlpha 因子输出 JSON 格式 | deepwiki `QuantaAlpha/QuantaAlpha` |
| 4 | vnpy AlphaDataset 输入格式要求 | deepwiki `vnpy/vnpy` |
| 5 | vnpy ts_function 完整函数列表 | deepwiki `vnpy/vnpy` |
| 6 | vnpy cs_function 完整函数列表 | deepwiki `vnpy/vnpy` |
| 7 | vnpy 表达式解析器支持语法 | deepwiki `vnpy/vnpy` |
| 8 | vnpy AlphaDataset 完整使用示例 | deepwiki `vnpy/vnpy` |

---

## 5. 后续扩展

MVP 验证通过后，可逐步引入完整版设计中的高级功能：
- 质量门控层
- 事件驱动架构
- 并发调度优化

详见 `architecture_design2.md`。
