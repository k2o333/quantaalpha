# QuantaAlpha + vnpy MVP 实施与验收文档

## 1. 文档概述

### 1.1 目标
本文档是 QuantaAlpha + vnpy MVP 集成方案的**实施与验收指南**，包含：
- 详细的实施步骤
- 代码实现规范
- 验收测试用例
- 验收通过标准

### 1.2 前置条件
- 已阅读 `mvp_quantaalpha_vnpy_glue_v2.md`（问题分析）
- 已阅读 `mvp_implementation.md`（部署方案）
- 已部署 mining conda 环境
- third_party 目录已包含 vnpy 和 quantaalpha

### 1.3 验收标准概述
| 验收项 | 标准 |
|-------|------|
| 环境部署 | mining 环境可正常运行，依赖完整 |
| 表达式转换 | 支持 80%+ 的 QuantaAlpha 算子转换 |
| 因子计算 | 至少 3 个测试因子成功计算并输出 IC |
| 闭环验证 | 从 QuantaAlpha 输出到 vnpy 计算的完整流程跑通 |

---

## 2. 实施步骤

### 2.1 阶段一：环境验证（第1天）

#### 2.1.1 验证 conda 环境
```bash
# 激活环境
conda activate mining

# 验证 Python 版本
python --version  # 应为 3.12.x

# 验证核心依赖
python -c "import vnpy; import quantaalpha; import polars; print('OK')"
```

**验收检查点：**
- [ ] `conda activate mining` 成功
- [ ] Python 版本为 3.12.x
- [ ] vnpy、quantaalpha、polars 均可导入

#### 2.1.2 验证 vnpy AlphaDataset
```python
# test_vnpy_basic.py
import polars as pl
from vnpy.alpha.dataset import AlphaDataset

# 创建测试数据
df = pl.DataFrame({
    "datetime": ["2023-01-01", "2023-01-02", "2023-01-03"] * 2,
    "vt_symbol": ["000001.SZSE"] * 3 + ["000002.SZSE"] * 3,
    "open": [10.0, 10.5, 11.0, 20.0, 20.5, 21.0],
    "high": [10.5, 11.0, 11.5, 20.5, 21.0, 21.5],
    "low": [9.5, 10.0, 10.5, 19.5, 20.0, 20.5],
    "close": [10.2, 10.8, 11.2, 20.2, 20.8, 21.2],
    "volume": [10000, 12000, 11000, 20000, 22000, 21000],
})
df = df.with_columns(pl.col("datetime").str.to_datetime())

# 创建数据集
dataset = AlphaDataset(
    df=df,
    train_period=("2023-01-01", "2023-01-02"),
    valid_period=("2023-01-02", "2023-01-03"),
    test_period=("2023-01-02", "2023-01-03")
)

# 添加简单因子
dataset.add_feature("close_plus_1", expression="close + 1")
dataset.set_label("ts_delay(close, -1) / close - 1")

# 触发计算
dataset.prepare_data()

print("raw_df columns:", dataset.raw_df.columns)
print("raw_df shape:", dataset.raw_df.shape)
print("Success!")
```

**验收检查点：**
- [ ] 测试脚本运行无错误
- [ ] `raw_df` 包含 `close_plus_1` 列
- [ ] `raw_df` 包含 `label` 列

---

### 2.2 阶段二：表达式转换器实现（第2-3天）

#### 2.2.1 创建转换器模块
创建文件：`/home/quan/testdata/aspipe_v4/third_party/glue/expression_translator.py`

```python
"""
QuantaAlpha 表达式 → vnpy 表达式转换器
"""

import re
from typing import Dict, List, Tuple


class ExpressionTranslator:
    """
    将 QuantaAlpha 因子表达式转换为 vnpy 兼容表达式
    """
    
    # 时序函数映射: QuantaAlpha -> vnpy
    TS_FUNCTION_MAP = {
        # 基础时序
        "DELTA": "ts_delta",
        "DELAY": "ts_delay",
        "TS_RANK": "ts_rank",
        "TS_MEAN": "ts_mean",
        "TS_SUM": "ts_sum",
        "TS_STD": "ts_std",
        "TS_MIN": "ts_min",
        "TS_MAX": "ts_max",
        "TS_ARGMIN": "ts_argmin",
        "TS_ARGMAX": "ts_argmax",
        "TS_MEDIAN": "ts_quantile",  # 需要特殊处理
        "TS_QUANTILE": "ts_quantile",
        "TS_CORR": "ts_corr",
        "TS_COVARIANCE": "ts_cov",
        "TS_PCTCHANGE": None,  # 需要自定义实现
        "TS_ZSCORE": None,  # 需要自定义实现
        "TS_MAD": None,  # 需要自定义实现
        
        # 移动平均
        "SMA": None,
        "WMA": None,
        "EMA": None,
        "DECAYLINEAR": "ts_decay_linear",
        
        # 其他
        "COUNT": None,
        "SUMIF": None,
        "HIGHDAY": "ts_argmax",  # 语义相近
        "LOWDAY": "ts_argmin",
        "SUMAC": "ts_sum",
        "PROD": "ts_product",
    }
    
    # 截面函数映射
    CS_FUNCTION_MAP = {
        "RANK": "cs_rank",
        "ZSCORE": None,  # 需要自定义实现
        "MEAN": "cs_mean",
        "STD": "cs_std",
        "SKEW": None,
        "KURT": None,
        "MAX": None,
        "MIN": None,
        "MEDIAN": None,
        "CS_SCALE": "cs_scale",
        "CS_SUM": "cs_sum",
    }
    
    # 数学函数映射
    MATH_FUNCTION_MAP = {
        "LOG": "log",
        "SQRT": None,
        "POW": "pow1",
        "SIGN": "sign",
        "EXP": None,
        "ABS": "abs",
        "MAX": "greater",
        "MIN": "less",
        "INV": None,
        "FLOOR": None,
    }
    
    # 技术指标映射
    TA_FUNCTION_MAP = {
        "RSI": "ta_rsi",
        "MACD": None,
        "BB_MIDDLE": None,
        "BB_UPPER": None,
        "BB_LOWER": None,
    }
    
    def __init__(self):
        self.unsupported_functions: List[str] = []
        self.warnings: List[str] = []
    
    def translate(self, qalpha_expr: str) -> Tuple[str, List[str]]:
        """
        转换 QuantaAlpha 表达式为 vnpy 表达式
        
        Args:
            qalpha_expr: QuantaAlpha 表达式，如 "TS_RANK($close, 10)"
            
        Returns:
            (vnpy_expr, warnings): 转换后的表达式和警告列表
        """
        self.unsupported_functions = []
        self.warnings = []
        
        expr = qalpha_expr
        
        # 步骤1: 移除 $ 前缀
        expr = self._remove_dollar_prefix(expr)
        
        # 步骤2: 转换函数名
        expr = self._convert_functions(expr)
        
        # 步骤3: 转换条件表达式 (C)?(A):(B) -> quesval2(C, C, A, B)
        expr = self._convert_conditionals(expr)
        
        # 步骤4: 转换逻辑运算符
        expr = self._convert_logical_operators(expr)
        
        # 步骤5: 处理特殊函数参数
        expr = self._fix_function_arguments(expr)
        
        return expr, self.warnings + [
            f"不支持的功能: {f}" for f in self.unsupported_functions
        ]
    
    def _remove_dollar_prefix(self, expr: str) -> str:
        """移除变量名的 $ 前缀"""
        return re.sub(r'\$(\w+)', r'\1', expr)
    
    def _convert_functions(self, expr: str) -> str:
        """转换函数名"""
        all_maps = {
            **self.TS_FUNCTION_MAP,
            **self.CS_FUNCTION_MAP,
            **self.MATH_FUNCTION_MAP,
            **self.TA_FUNCTION_MAP,
        }
        
        # 按函数名长度降序，避免短名匹配到长名的一部分
        func_names = sorted(all_maps.keys(), key=len, reverse=True)
        
        for qa_name in func_names:
            vnpy_name = all_maps[qa_name]
            if vnpy_name is None:
                # 记录不支持的功能
                pattern = rf'\b{qa_name}\s*\('
                if re.search(pattern, expr):
                    self.unsupported_functions.append(qa_name)
            else:
                # 替换函数名
                pattern = rf'\b{qa_name}\s*\('
                expr = re.sub(pattern, f'{vnpy_name}(', expr)
        
        return expr
    
    def _convert_conditionals(self, expr: str) -> str:
        """
        转换条件表达式:
        (C)?(A):(B) -> quesval2(C, C, A, B)
        """
        # 这是一个简化版本，实际实现需要处理嵌套
        # 使用栈来匹配括号
        result = []
        i = 0
        n = len(expr)
        
        while i < n:
            if expr[i] == '(' and i + 1 < n:
                # 查找条件表达式的模式
                match = self._find_conditional(expr, i)
                if match:
                    cond, true_val, false_val, end_pos = match
                    result.append(f"quesval2({cond}, {cond}, {true_val}, {false_val})")
                    i = end_pos
                    continue
            result.append(expr[i])
            i += 1
        
        return ''.join(result)
    
    def _find_conditional(self, expr: str, start: int) -> Tuple[str, str, str, int]:
        """
        查找条件表达式 (C)?(A):(B)
        返回 (condition, true_value, false_value, end_position)
        """
        # 简化实现：假设格式为 (C)?(A):(B)
        # 实际实现需要更复杂的括号匹配
        try:
            # 从 start 开始，找到完整的条件表达式
            if start >= len(expr) or expr[start] != '(':
                return None
            
            # 找条件部分 C
            cond_start = start + 1
            cond_end = self._find_matching_paren(expr, start)
            if cond_end is None:
                return None
            
            condition = expr[cond_start:cond_end]
            
            # 检查后面是否有 ?(
            pos = cond_end + 1
            if pos + 1 >= len(expr) or expr[pos:pos+2] != '?(':
                return None
            
            # 找真值部分 A
            true_start = pos + 2
            true_end = self._find_matching_paren(expr, true_start - 1)
            if true_end is None:
                return None
            
            true_value = expr[true_start:true_end]
            
            # 检查后面是否有 :(
            pos = true_end + 1
            if pos + 1 >= len(expr) or expr[pos:pos+2] != ':(':
                return None
            
            # 找假值部分 B
            false_start = pos + 2
            false_end = self._find_matching_paren(expr, false_start - 1)
            if false_end is None:
                return None
            
            false_value = expr[false_start:false_end]
            
            return condition, true_value, false_value, false_end + 1
            
        except Exception:
            return None
    
    def _find_matching_paren(self, expr: str, open_pos: int) -> int:
        """找到匹配的右括号位置"""
        if open_pos >= len(expr) or expr[open_pos] != '(':
            return None
        
        count = 1
        i = open_pos + 1
        while i < len(expr) and count > 0:
            if expr[i] == '(':
                count += 1
            elif expr[i] == ')':
                count -= 1
            i += 1
        
        return i - 1 if count == 0 else None
    
    def _convert_logical_operators(self, expr: str) -> str:
        """转换逻辑运算符 && 和 ||"""
        # vnpy 的 eval 可能不支持 && 和 ||，需要转换为 Python 的 and/or
        # 但注意：这会改变语义，因为 Python 的 and/or 是短路求值
        self.warnings.append("逻辑运算符 && 和 || 可能不被支持，需要手动验证")
        return expr
    
    def _fix_function_arguments(self, expr: str) -> str:
        """修复函数参数格式问题"""
        # 例如 TS_MEDIAN 需要转换为 ts_quantile(A, 0.5)
        # 这里可以添加更多特殊处理
        return expr
    
    def get_support_status(self) -> Dict[str, List[str]]:
        """
        获取算子支持状态
        
        Returns:
            {
                "supported": [...],
                "unsupported": [...],
                "partial": [...]
            }
        """
        all_maps = [
            self.TS_FUNCTION_MAP,
            self.CS_FUNCTION_MAP,
            self.MATH_FUNCTION_MAP,
            self.TA_FUNCTION_MAP,
        ]
        
        supported = []
        unsupported = []
        
        for m in all_maps:
            for k, v in m.items():
                if v is not None:
                    supported.append(k)
                else:
                    unsupported.append(k)
        
        return {
            "supported": supported,
            "unsupported": unsupported,
            "partial": ["TS_MEDIAN", "HIGHDAY", "LOWDAY"]  # 需要特殊处理
        }


def translate_expression(qalpha_expr: str) -> Tuple[str, List[str]]:
    """便捷函数"""
    translator = ExpressionTranslator()
    return translator.translate(qalpha_expr)


if __name__ == "__main__":
    # 测试
    test_cases = [
        "$close + 1",
        "TS_RANK($close, 10)",
        "RANK($volume)",
        "ABS($close - $open)",
        "($close > $open)?($close):($open)",
    ]
    
    translator = ExpressionTranslator()
    for expr in test_cases:
        result, warnings = translator.translate(expr)
        print(f"Input:  {expr}")
        print(f"Output: {result}")
        if warnings:
            print(f"Warnings: {warnings}")
        print()
```

**验收检查点：**
- [ ] 转换器模块可导入
- [ ] 测试用例通过：
  - `$close + 1` → `close + 1`
  - `TS_RANK($close, 10)` → `ts_rank(close, 10)`
  - `RANK($volume)` → `cs_rank(volume)`
  - `ABS($close - $open)` → `abs(close - open)`

---

### 2.3 阶段三：数据适配器实现（第3-4天）

#### 2.3.1 创建数据适配器
创建文件：`/home/quan/testdata/aspipe_v4/third_party/glue/data_adapter.py`

```python
"""
数据适配器：准备 vnpy AlphaDataset 所需的输入数据
"""

import polars as pl
from pathlib import Path
from typing import Optional, Tuple
import hashlib


class DataAdapter:
    """
    将原始数据转换为 vnpy AlphaDataset 格式
    """
    
    # vnpy 必需的列
    REQUIRED_COLUMNS = ["datetime", "vt_symbol", "open", "high", "low", "close", "volume"]
    
    # 可选列
    OPTIONAL_COLUMNS = ["vwap", "amount", "turnover", "bid1", "ask1"]
    
    def __init__(self, data_dir: str = "./data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def load_from_csv(
        self, 
        csv_path: str,
        date_col: str = "date",
        symbol_col: str = "symbol",
        **column_mapping
    ) -> pl.DataFrame:
        """
        从 CSV 加载数据并转换为 vnpy 格式
        
        Args:
            csv_path: CSV 文件路径
            date_col: 日期列名
            symbol_col: 股票代码列名
            column_mapping: 列名映射，如 {"open_price": "open"}
        """
        df = pl.read_csv(csv_path)
        
        # 重命名列
        rename_map = {date_col: "datetime", symbol_col: "vt_symbol"}
        rename_map.update(column_mapping)
        
        for old_name, new_name in rename_map.items():
            if old_name in df.columns:
                df = df.rename({old_name: new_name})
        
        # 转换日期格式
        if df["datetime"].dtype == pl.Utf8:
            df = df.with_columns(pl.col("datetime").str.to_datetime())
        
        # 转换 vt_symbol 格式
        df = df.with_columns(
            pl.col("vt_symbol").map_elements(
                self._format_vt_symbol, 
                return_dtype=pl.Utf8
            )
        )
        
        return df
    
    def load_from_parquet(self, parquet_path: str) -> pl.DataFrame:
        """从 Parquet 加载数据"""
        return pl.read_parquet(parquet_path)
    
    def save_to_parquet(self, df: pl.DataFrame, filename: str) -> str:
        """保存为 Parquet 格式"""
        output_path = self.data_dir / filename
        df.write_parquet(output_path)
        return str(output_path)
    
    def validate(self, df: pl.DataFrame) -> Tuple[bool, list]:
        """
        验证数据格式
        
        Returns:
            (is_valid, missing_columns)
        """
        missing = [col for col in self.REQUIRED_COLUMNS if col not in df.columns]
        return len(missing) == 0, missing
    
    def create_sample_data(
        self, 
        start_date: str = "2020-01-01",
        end_date: str = "2023-01-01",
        n_symbols: int = 10,
        output_file: str = "sample_data.parquet"
    ) -> str:
        """
        创建示例数据用于测试
        
        Returns:
            输出文件路径
        """
        import numpy as np
        from datetime import datetime, timedelta
        
        # 生成日期范围
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        dates = []
        current = start
        while current <= end:
            dates.append(current)
            current += timedelta(days=1)
        
        # 生成股票代码
        symbols = [f"{i:06d}.SZSE" if i % 2 == 0 else f"{i:06d}.SSE" 
                   for i in range(1, n_symbols + 1)]
        
        # 生成数据
        rows = []
        np.random.seed(42)
        
        for symbol in symbols:
            base_price = np.random.uniform(10, 100)
            for date in dates:
                # 随机游走生成价格
                change = np.random.normal(0, 0.02)
                close = base_price * (1 + change)
                open_price = close * (1 + np.random.normal(0, 0.005))
                high = max(open_price, close) * (1 + abs(np.random.normal(0, 0.01)))
                low = min(open_price, close) * (1 - abs(np.random.normal(0, 0.01)))
                volume = int(np.random.uniform(100000, 1000000))
                
                rows.append({
                    "datetime": date,
                    "vt_symbol": symbol,
                    "open": round(open_price, 2),
                    "high": round(high, 2),
                    "low": round(low, 2),
                    "close": round(close, 2),
                    "volume": volume,
                })
                
                base_price = close
        
        df = pl.DataFrame(rows)
        df = df.sort(["datetime", "vt_symbol"])
        
        output_path = self.save_to_parquet(df, output_file)
        return output_path
    
    def _format_vt_symbol(self, symbol: str) -> str:
        """
        格式化 vt_symbol
        
        支持的输入格式：
        - 000001.SZ → 000001.SZSE
        - 000001 → 000001.SZSE (默认深交所)
        - 600000.SH → 600000.SSE
        """
        if "." in symbol:
            code, exchange = symbol.split(".")
            exchange_map = {
                "SZ": "SZSE",
                "SH": "SSE",
                "BJ": "BSE",
            }
            return f"{code}.{exchange_map.get(exchange, exchange)}"
        else:
            # 根据代码规则判断交易所
            if symbol.startswith("6"):
                return f"{symbol}.SSE"
            else:
                return f"{symbol}.SZSE"
    
    def get_data_hash(self, df: pl.DataFrame) -> str:
        """计算数据哈希，用于缓存"""
        # 使用数据的形状和前几行计算哈希
        sample = df.head(100).to_numpy().tobytes()
        return hashlib.md5(sample).hexdigest()[:16]


if __name__ == "__main__":
    # 测试
    adapter = DataAdapter()
    
    # 创建示例数据
    print("创建示例数据...")
    data_path = adapter.create_sample_data(
        start_date="2022-01-01",
        end_date="2022-12-31",
        n_symbols=5,
        output_file="test_sample.parquet"
    )
    print(f"数据已保存到: {data_path}")
    
    # 加载并验证
    df = adapter.load_from_parquet(data_path)
    print(f"数据形状: {df.shape}")
    print(f"列: {df.columns}")
    
    is_valid, missing = adapter.validate(df)
    print(f"验证结果: {'通过' if is_valid else '失败'}")
    if missing:
        print(f"缺失列: {missing}")
```

**验收检查点：**
- [ ] 数据适配器可创建示例数据
- [ ] 示例数据包含必需的 7 列
- [ ] 数据验证通过
- [ ] `vt_symbol` 格式正确（如 `000001.SZSE`）

---

### 2.4 阶段四：因子执行器实现（第4-5天）

#### 2.4.1 创建因子执行器
创建文件：`/home/quan/testdata/aspipe_v4/third_party/glue/factor_executor.py`

```python
"""
因子执行器：使用 vnpy 计算因子并评估性能
"""

import polars as pl
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import json

from vnpy.alpha.dataset import AlphaDataset


@dataclass
class FactorResult:
    """因子计算结果"""
    factor_name: str
    original_expression: str
    translated_expression: str
    success: bool
    ic_value: Optional[float] = None
    error_message: Optional[str] = None
    computation_time: Optional[float] = None


class FactorExecutor:
    """
    执行因子计算并收集结果
    """
    
    def __init__(
        self, 
        df: pl.DataFrame,
        train_period: Tuple[str, str],
        valid_period: Tuple[str, str],
        test_period: Tuple[str, str],
        output_dir: str = "./output"
    ):
        self.df = df
        self.train_period = train_period
        self.valid_period = valid_period
        self.test_period = test_period
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.results: List[FactorResult] = []
        self.dataset: Optional[AlphaDataset] = None
    
    def execute_single(
        self, 
        factor_name: str, 
        expression: str,
        label_expr: str = "ts_delay(close, -1) / close - 1"
    ) -> FactorResult:
        """
        执行单个因子计算
        
        Args:
            factor_name: 因子名称
            expression: vnpy 格式的表达式
            label_expr: 标签表达式（未来收益）
            
        Returns:
            FactorResult
        """
        import time
        
        start_time = time.time()
        
        try:
            # 创建数据集
            self.dataset = AlphaDataset(
                df=self.df,
                train_period=self.train_period,
                valid_period=self.valid_period,
                test_period=self.test_period
            )
            
            # 添加因子
            self.dataset.add_feature(factor_name, expression=expression)
            
            # 设置标签
            self.dataset.set_label(label_expr)
            
            # 触发计算
            self.dataset.prepare_data()
            
            # 计算 IC
            ic_value = self._calculate_ic(factor_name)
            
            computation_time = time.time() - start_time
            
            result = FactorResult(
                factor_name=factor_name,
                original_expression=expression,
                translated_expression=expression,
                success=True,
                ic_value=ic_value,
                computation_time=computation_time
            )
            
        except Exception as e:
            computation_time = time.time() - start_time
            result = FactorResult(
                factor_name=factor_name,
                original_expression=expression,
                translated_expression=expression,
                success=False,
                error_message=str(e),
                computation_time=computation_time
            )
        
        self.results.append(result)
        return result
    
    def execute_batch(
        self, 
        factors: List[Dict[str, str]],
        label_expr: str = "ts_delay(close, -1) / close - 1"
    ) -> List[FactorResult]:
        """
        批量执行因子计算
        
        Args:
            factors: 因子列表，每个因子为 {"name": "...", "expression": "..."}
            label_expr: 标签表达式
            
        Returns:
            结果列表
        """
        for factor in factors:
            print(f"计算因子: {factor['name']}")
            result = self.execute_single(
                factor["name"],
                factor["expression"],
                label_expr
            )
            status = "✓" if result.success else "✗"
            print(f"  {status} {result.factor_name}: IC={result.ic_value}")
        
        return self.results
    
    def _calculate_ic(self, factor_name: str) -> Optional[float]:
        """
        计算因子的 Information Coefficient (IC)
        
        IC = corr(factor_value, future_return)
        """
        if self.dataset is None or self.dataset.raw_df is None:
            return None
        
        df = self.dataset.raw_df
        
        # 检查必要的列是否存在
        if factor_name not in df.columns or "label" not in df.columns:
            return None
        
        # 转换为 pandas 计算相关系数
        pdf = df.select([factor_name, "label"]).to_pandas()
        pdf = pdf.dropna()
        
        if len(pdf) < 2:
            return None
        
        ic = pdf[factor_name].corr(pdf["label"])
        return float(ic) if not pd.isna(ic) else None
    
    def save_results(self, filename: str = "factor_results.json"):
        """保存结果到 JSON"""
        output_path = self.output_dir / filename
        
        data = []
        for r in self.results:
            data.append({
                "factor_name": r.factor_name,
                "original_expression": r.original_expression,
                "translated_expression": r.translated_expression,
                "success": r.success,
                "ic_value": r.ic_value,
                "error_message": r.error_message,
                "computation_time": r.computation_time,
            })
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"结果已保存到: {output_path}")
        return str(output_path)
    
    def get_summary(self) -> Dict:
        """获取执行摘要"""
        total = len(self.results)
        success = sum(1 for r in self.results if r.success)
        failed = total - success
        
        ics = [r.ic_value for r in self.results if r.success and r.ic_value is not None]
        avg_ic = sum(ics) / len(ics) if ics else 0
        
        return {
            "total_factors": total,
            "success": success,
            "failed": failed,
            "success_rate": success / total if total > 0 else 0,
            "average_ic": avg_ic,
            "max_ic": max(ics) if ics else None,
            "min_ic": min(ics) if ics else None,
        }


if __name__ == "__main__":
    # 测试
    from data_adapter import DataAdapter
    
    # 创建测试数据
    adapter = DataAdapter()
    data_path = adapter.create_sample_data(
        start_date="2022-01-01",
        end_date="2022-06-30",
        n_symbols=3,
        output_file="executor_test.parquet"
    )
    
    df = adapter.load_from_parquet(data_path)
    
    # 执行因子计算
    executor = FactorExecutor(
        df=df,
        train_period=("2022-01-01", "2022-03-31"),
        valid_period=("2022-04-01", "2022-05-31"),
        test_period=("2022-06-01", "2022-06-30")
    )
    
    # 测试简单因子
    test_factors = [
        {"name": "close_plus_1", "expression": "close + 1"},
        {"name": "ts_rank_close_5", "expression": "ts_rank(close, 5)"},
        {"name": "cs_rank_volume", "expression": "cs_rank(volume)"},
    ]
    
    results = executor.execute_batch(test_factors)
    
    # 打印摘要
    summary = executor.get_summary()
    print("\n执行摘要:")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    
    # 保存结果
    executor.save_results()
```

**验收检查点：**
- [ ] 执行器可成功计算简单因子（如 `close + 1`）
- [ ] 执行器可计算时序因子（如 `ts_rank(close, 5)`）
- [ ] 执行器可计算截面因子（如 `cs_rank(volume)`）
- [ ] 结果包含 IC 值
- [ ] 结果可保存为 JSON

---

### 2.5 阶段五：集成与闭环验证（第5-6天）

#### 2.5.1 创建集成运行器
创建文件：`/home/quan/testdata/aspipe_v4/third_party/glue/pipeline.py`

```python
"""
MVP 集成流水线：从 QuantaAlpha 到 vnpy 的完整闭环
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

from expression_translator import ExpressionTranslator
from data_adapter import DataAdapter
from factor_executor import FactorExecutor


class MVPPipeline:
    """
    MVP 集成流水线
    
    流程：
    1. 加载 QuantaAlpha 生成的因子
    2. 转换表达式
    3. 准备数据
    4. 执行计算
    5. 输出结果
    """
    
    def __init__(
        self,
        data_path: Optional[str] = None,
        output_dir: str = "./output",
        train_period: tuple = ("2020-01-01", "2021-01-01"),
        valid_period: tuple = ("2021-01-01", "2022-01-01"),
        test_period: tuple = ("2022-01-01", "2023-01-01"),
    ):
        self.translator = ExpressionTranslator()
        self.data_adapter = DataAdapter()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.train_period = train_period
        self.valid_period = valid_period
        self.test_period = test_period
        
        self.data_path = data_path
        self.df = None
        
        self.translated_factors: List[Dict] = []
        self.failed_translations: List[Dict] = []
    
    def prepare_data(self, create_sample: bool = True) -> str:
        """
        准备数据
        
        Args:
            create_sample: 如果没有数据，是否创建示例数据
            
        Returns:
            数据文件路径
        """
        if self.data_path and Path(self.data_path).exists():
            self.df = self.data_adapter.load_from_parquet(self.data_path)
            print(f"已加载数据: {self.data_path}")
        elif create_sample:
            self.data_path = self.data_adapter.create_sample_data(
                start_date=self.train_period[0],
                end_date=self.test_period[1],
                n_symbols=10,
                output_file="mvp_sample_data.parquet"
            )
            self.df = self.data_adapter.load_from_parquet(self.data_path)
            print(f"已创建示例数据: {self.data_path}")
        else:
            raise ValueError("没有可用数据，且 create_sample=False")
        
        # 验证数据
        is_valid, missing = self.data_adapter.validate(self.df)
        if not is_valid:
            raise ValueError(f"数据验证失败，缺失列: {missing}")
        
        return self.data_path
    
    def load_factors_from_quantaalpha(
        self, 
        library_path: str
    ) -> List[Dict]:
        """
        从 QuantaAlpha 因子库加载因子
        
        Args:
            library_path: factor_library.json 路径
            
        Returns:
            因子列表
        """
        with open(library_path, "r", encoding="utf-8") as f:
            library = json.load(f)
        
        factors = []
        for factor_id, factor_info in library.get("factors", {}).items():
            factors.append({
                "id": factor_id,
                "name": factor_info.get("factor_name", factor_id),
                "expression": factor_info.get("factor_expression", ""),
                "description": factor_info.get("factor_description", ""),
            })
        
        return factors
    
    def load_factors_from_json(self, json_path: str) -> List[Dict]:
        """从 JSON 文件加载因子列表"""
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # 支持两种格式
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            # QuantaAlpha 输出格式
            factors = []
            for name, info in data.items():
                factors.append({
                    "name": name,
                    "expression": info.get("expression", ""),
                    "description": info.get("description", ""),
                })
            return factors
        else:
            raise ValueError(f"不支持的 JSON 格式: {type(data)}")
    
    def translate_factors(self, factors: List[Dict]) -> List[Dict]:
        """
        批量转换因子表达式
        
        Args:
            factors: QuantaAlpha 格式的因子列表
            
        Returns:
            转换后的因子列表
        """
        self.translated_factors = []
        self.failed_translations = []
        
        for factor in factors:
            qalpha_expr = factor.get("expression", "")
            if not qalpha_expr:
                self.failed_translations.append({
                    **factor,
                    "error": "Empty expression"
                })
                continue
            
            translated_expr, warnings = self.translator.translate(qalpha_expr)
            
            result = {
                **factor,
                "original_expression": qalpha_expr,
                "translated_expression": translated_expr,
                "translation_warnings": warnings,
            }
            
            # 如果有不支持的功能，标记为失败
            if any("不支持" in w for w in warnings):
                self.failed_translations.append(result)
            else:
                self.translated_factors.append(result)
        
        print(f"表达式转换完成:")
        print(f"  成功: {len(self.translated_factors)}")
        print(f"  失败: {len(self.failed_translations)}")
        
        return self.translated_factors
    
    def execute_factors(self, max_factors: Optional[int] = None) -> List[Dict]:
        """
        执行因子计算
        
        Args:
            max_factors: 最多执行的因子数量（用于测试）
            
        Returns:
            执行结果
        """
        if self.df is None:
            raise ValueError("数据未准备，请先调用 prepare_data()")
        
        factors_to_execute = self.translated_factors[:max_factors] if max_factors else self.translated_factors
        
        if not factors_to_execute:
            print("没有可执行的因子")
            return []
        
        # 准备执行格式
        exec_factors = [
            {"name": f["name"], "expression": f["translated_expression"]}
            for f in factors_to_execute
        ]
        
        # 执行计算
        executor = FactorExecutor(
            df=self.df,
            train_period=self.train_period,
            valid_period=self.valid_period,
            test_period=self.test_period,
            output_dir=self.output_dir
        )
        
        results = executor.execute_batch(exec_factors)
        
        # 合并结果
        for i, factor in enumerate(factors_to_execute):
            if i < len(results):
                factor["execution_result"] = {
                    "success": results[i].success,
                    "ic_value": results[i].ic_value,
                    "error_message": results[i].error_message,
                    "computation_time": results[i].computation_time,
                }
        
        return self.translated_factors
    
    def run(
        self,
        factors_source: str,
        source_type: str = "json",
        max_factors: Optional[int] = None
    ) -> Dict:
        """
        运行完整流水线
        
        Args:
            factors_source: 因子源文件路径
            source_type: "json" 或 "quantaalpha_library"
            max_factors: 最多处理的因子数量
            
        Returns:
            执行摘要
        """
        print("=" * 60)
        print("MVP 集成流水线启动")
        print("=" * 60)
        
        # 步骤1: 准备数据
        print("\n[步骤1] 准备数据...")
        self.prepare_data()
        
        # 步骤2: 加载因子
        print("\n[步骤2] 加载因子...")
        if source_type == "json":
            factors = self.load_factors_from_json(factors_source)
        elif source_type == "quantaalpha_library":
            factors = self.load_factors_from_quantaalpha(factors_source)
        else:
            raise ValueError(f"不支持的 source_type: {source_type}")
        
        print(f"  加载了 {len(factors)} 个因子")
        
        # 步骤3: 转换表达式
        print("\n[步骤3] 转换表达式...")
        self.translate_factors(factors)
        
        # 步骤4: 执行计算
        print("\n[步骤4] 执行因子计算...")
        self.execute_factors(max_factors=max_factors)
        
        # 步骤5: 输出结果
        print("\n[步骤5] 保存结果...")
        self._save_final_results()
        
        # 生成摘要
        summary = self._generate_summary()
        
        print("\n" + "=" * 60)
        print("MVP 集成流水线完成")
        print("=" * 60)
        print(f"摘要:")
        for key, value in summary.items():
            print(f"  {key}: {value}")
        
        return summary
    
    def _save_final_results(self):
        """保存最终结果"""
        # 保存成功的因子
        success_factors = [
            f for f in self.translated_factors
            if f.get("execution_result", {}).get("success", False)
        ]
        
        with open(self.output_dir / "success_factors.json", "w", encoding="utf-8") as f:
            json.dump(success_factors, f, ensure_ascii=False, indent=2)
        
        # 保存失败的因子
        failed_factors = [
            f for f in self.translated_factors
            if not f.get("execution_result", {}).get("success", True)
        ] + self.failed_translations
        
        with open(self.output_dir / "failed_factors.json", "w", encoding="utf-8") as f:
            json.dump(failed_factors, f, ensure_ascii=False, indent=2)
        
        print(f"  成功因子: {len(success_factors)} 个")
        print(f"  失败因子: {len(failed_factors)} 个")
    
    def _generate_summary(self) -> Dict:
        """生成执行摘要"""
        total = len(self.translated_factors) + len(self.failed_translations)
        translated = len(self.translated_factors)
        translation_failed = len(self.failed_translations)
        
        executed = [f for f in self.translated_factors if "execution_result" in f]
        exec_success = sum(1 for f in executed if f["execution_result"]["success"])
        exec_failed = len(executed) - exec_success
        
        ics = [
            f["execution_result"]["ic_value"] 
            for f in executed 
            if f["execution_result"].get("ic_value") is not None
        ]
        
        return {
            "total_factors": total,
            "translation_success": translated,
            "translation_failed": translation_failed,
            "translation_rate": translated / total if total > 0 else 0,
            "execution_success": exec_success,
            "execution_failed": exec_failed,
            "execution_rate": exec_success / len(executed) if executed else 0,
            "average_ic": sum(ics) / len(ics) if ics else None,
            "max_ic": max(ics) if ics else None,
            "min_ic": min(ics) if ics else None,
        }


if __name__ == "__main__":
    # 测试流水线
    
    # 创建测试因子
    test_factors = [
        {
            "name": "Momentum_10D",
            "expression": "TS_RANK($close, 10)",
            "description": "10日收盘价时序排名"
        },
        {
            "name": "Volume_Rank",
            "expression": "RANK($volume)",
            "description": "成交量截面排名"
        },
        {
            "name": "Price_Change",
            "expression": "$close - $open",
            "description": "价格变化"
        },
    ]
    
    # 保存测试因子
    test_file = Path("./test_factors.json")
    with open(test_file, "w", encoding="utf-8") as f:
        json.dump(test_factors, f, ensure_ascii=False, indent=2)
    
    # 运行流水线
    pipeline = MVPPipeline(
        train_period=("2022-01-01", "2022-03-31"),
        valid_period=("2022-04-01", "2022-05-31"),
        test_period=("2022-06-01", "2022-06-30"),
    )
    
    summary = pipeline.run(
        factors_source=str(test_file),
        source_type="json",
        max_factors=None
    )
```

**验收检查点：**
- [ ] 流水线可完整运行
- [ ] 成功因子保存到 `success_factors.json`
- [ ] 失败因子保存到 `failed_factors.json`
- [ ] 摘要报告包含转换率和执行成功率

---

## 3. 验收测试

### 3.1 测试用例

创建文件：`/home/quan/testdata/aspipe_v4/third_party/glue/test_acceptance.py`

```python
"""
MVP 验收测试
"""

import json
import sys
from pathlib import Path

# 添加 glue 目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from expression_translator import ExpressionTranslator
from data_adapter import DataAdapter
from factor_executor import FactorExecutor
from pipeline import MVPPipeline


def test_expression_translator():
    """测试表达式转换器"""
    print("\n" + "=" * 60)
    print("测试: 表达式转换器")
    print("=" * 60)
    
    translator = ExpressionTranslator()
    
    test_cases = [
        ("$close + 1", "close + 1"),
        ("TS_RANK($close, 10)", "ts_rank(close, 10)"),
        ("RANK($volume)", "cs_rank(volume)"),
        ("ABS($close - $open)", "abs(close - open)"),
        ("TS_MEAN($close, 20)", "ts_mean(close, 20)"),
    ]
    
    passed = 0
    failed = 0
    
    for input_expr, expected in test_cases:
        result, warnings = translator.translate(input_expr)
        success = result == expected
        
        status = "✓" if success else "✗"
        print(f"{status} {input_expr}")
        print(f"   → {result}")
        if not success:
            print(f"   期望: {expected}")
            failed += 1
        else:
            passed += 1
    
    print(f"\n结果: {passed} 通过, {failed} 失败")
    return failed == 0


def test_data_adapter():
    """测试数据适配器"""
    print("\n" + "=" * 60)
    print("测试: 数据适配器")
    print("=" * 60)
    
    adapter = DataAdapter()
    
    # 创建示例数据
    data_path = adapter.create_sample_data(
        start_date="2022-01-01",
        end_date="2022-03-31",
        n_symbols=5,
        output_file="acceptance_test.parquet"
    )
    print(f"✓ 创建示例数据: {data_path}")
    
    # 加载数据
    df = adapter.load_from_parquet(data_path)
    print(f"✓ 加载数据: {df.shape}")
    
    # 验证数据
    is_valid, missing = adapter.validate(df)
    if is_valid:
        print(f"✓ 数据验证通过")
    else:
        print(f"✗ 数据验证失败: {missing}")
        return False
    
    # 检查必需列
    required = ["datetime", "vt_symbol", "open", "high", "low", "close", "volume"]
    for col in required:
        if col in df.columns:
            print(f"✓ 列存在: {col}")
        else:
            print(f"✗ 列缺失: {col}")
            return False
    
    return True


def test_factor_executor():
    """测试因子执行器"""
    print("\n" + "=" * 60)
    print("测试: 因子执行器")
    print("=" * 60)
    
    # 准备数据
    adapter = DataAdapter()
    data_path = adapter.create_sample_data(
        start_date="2022-01-01",
        end_date="2022-06-30",
        n_symbols=3,
        output_file="executor_acceptance.parquet"
    )
    df = adapter.load_from_parquet(data_path)
    
    # 创建执行器
    executor = FactorExecutor(
        df=df,
        train_period=("2022-01-01", "2022-03-31"),
        valid_period=("2022-04-01", "2022-05-31"),
        test_period=("2022-06-01", "2022-06-30")
    )
    
    # 测试因子
    test_factors = [
        {"name": "test_simple", "expression": "close + 1"},
        {"name": "test_ts_rank", "expression": "ts_rank(close, 5)"},
        {"name": "test_cs_rank", "expression": "cs_rank(volume)"},
    ]
    
    results = executor.execute_batch(test_factors)
    
    # 验证结果
    success_count = sum(1 for r in results if r.success)
    print(f"\n执行结果: {success_count}/{len(results)} 成功")
    
    for r in results:
        status = "✓" if r.success else "✗"
        ic_str = f"IC={r.ic_value:.4f}" if r.ic_value else "IC=N/A"
        print(f"{status} {r.factor_name}: {ic_str}")
        if not r.success:
            print(f"   错误: {r.error_message}")
    
    # 至少2个成功才算通过
    return success_count >= 2


def test_full_pipeline():
    """测试完整流水线"""
    print("\n" + "=" * 60)
    print("测试: 完整流水线")
    print("=" * 60)
    
    # 创建测试因子
    test_factors = [
        {
            "name": "Momentum_10D",
            "expression": "TS_RANK($close, 10)",
            "description": "10日收盘价时序排名"
        },
        {
            "name": "Volume_Rank",
            "expression": "RANK($volume)",
            "description": "成交量截面排名"
        },
        {
            "name": "Price_Change",
            "expression": "$close - $open",
            "description": "价格变化"
        },
        {
            "name": "Unsupported_Factor",
            "expression": "ZSCORE($close)",  # 可能不支持
            "description": "测试不支持的因子"
        },
    ]
    
    test_file = Path("./test_acceptance_factors.json")
    with open(test_file, "w", encoding="utf-8") as f:
        json.dump(test_factors, f, ensure_ascii=False, indent=2)
    
    # 运行流水线
    pipeline = MVPPipeline(
        train_period=("2022-01-01", "2022-03-31"),
        valid_period=("2022-04-01", "2022-05-31"),
        test_period=("2022-06-01", "2022-06-30"),
    )
    
    summary = pipeline.run(
        factors_source=str(test_file),
        source_type="json"
    )
    
    # 验证结果
    print("\n验收标准检查:")
    
    checks = [
        ("至少3个因子", summary.get("total_factors", 0) >= 3),
        ("转换率 > 50%", summary.get("translation_rate", 0) > 0.5),
        ("执行率 > 50%", summary.get("execution_rate", 0) > 0.5),
        ("至少1个IC值", summary.get("average_ic") is not None),
    ]
    
    all_passed = True
    for name, passed in checks:
        status = "✓" if passed else "✗"
        print(f"{status} {name}")
        if not passed:
            all_passed = False
    
    return all_passed


def main():
    """运行所有验收测试"""
    print("\n" + "=" * 60)
    print("MVP 验收测试套件")
    print("=" * 60)
    
    results = []
    
    # 运行测试
    results.append(("表达式转换器", test_expression_translator()))
    results.append(("数据适配器", test_data_adapter()))
    results.append(("因子执行器", test_factor_executor()))
    results.append(("完整流水线", test_full_pipeline()))
    
    # 汇总
    print("\n" + "=" * 60)
    print("验收测试汇总")
    print("=" * 60)
    
    for name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"{status}: {name}")
    
    all_passed = all(r[1] for r in results)
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 所有验收测试通过！MVP 可进入下一阶段。")
    else:
        print("⚠️ 部分测试失败，请修复后重新运行。")
    print("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
```

---

## 4. 验收标准

### 4.1 必过标准（P0）

| 验收项 | 标准 | 验证方式 |
|-------|------|---------|
| 环境部署 | mining 环境可正常运行 | `conda activate mining && python -c "import vnpy; import quantaalpha"` |
| 表达式转换 | 基础算子转换正确 | 运行 `test_expression_translator()` |
| 数据准备 | 可创建并验证示例数据 | 运行 `test_data_adapter()` |
| 因子计算 | 至少1个因子成功计算 | 运行 `test_factor_executor()` |

### 4.2 核心标准（P1）

| 验收项 | 标准 | 验证方式 |
|-------|------|---------|
| 表达式转换覆盖率 | 支持 80%+ 常用算子 | 检查 `TS_FUNCTION_MAP` 和 `CS_FUNCTION_MAP` |
| 因子执行成功率 | 转换后的因子 70%+ 可执行 | 运行 `test_full_pipeline()` |
| IC 计算 | 成功计算的因子可输出 IC | 检查结果中的 `ic_value` |
| 闭环完整性 | 从 JSON 输入到结果输出的完整流程 | 运行 `test_full_pipeline()` |

### 4.3 优化标准（P2）

| 验收项 | 标准 | 验证方式 |
|-------|------|---------|
| 条件表达式 | 支持 `(C)?(A):(B)` 语法 | 添加测试用例 |
| 逻辑运算符 | 支持 `&&` 和 `\|\|` | 添加测试用例 |
| 性能 | 单个因子计算 < 10秒 | 检查 `computation_time` |
| 文档 | 所有模块有 docstring | 代码审查 |

---

## 5. 实施时间表

| 阶段 | 任务 | 预计时间 | 依赖 |
|-----|------|---------|------|
| 1 | 环境验证 | 0.5天 | 无 |
| 2 | 表达式转换器 | 1.5天 | 阶段1 |
| 3 | 数据适配器 | 1天 | 阶段1 |
| 4 | 因子执行器 | 1.5天 | 阶段2,3 |
| 5 | 集成流水线 | 1.5天 | 阶段4 |
| 6 | 验收测试 | 0.5天 | 阶段5 |
| - | **总计** | **6.5天** | - |

---

## 6. 风险与应对

| 风险 | 影响 | 应对措施 |
|-----|------|---------|
| vnpy 不支持某些算子 | 高 | 记录不支持的算子，提供替代方案 |
| 表达式解析复杂 | 中 | 分阶段实现，先支持简单表达式 |
| 数据格式不匹配 | 中 | 增加数据适配器的转换逻辑 |
| 性能问题 | 低 | 使用并行计算，优化关键路径 |

---

## 7. 附录

### 7.1 目录结构

```
third_party/
├── quantaalpha/                       # QuantaAlpha 源码
├── vnpy/                              # vnpy 源码
├── setup_env.sh                       # 环境初始化脚本
└── glue/                              # 胶水代码（本MVP实现）
    ├── __init__.py
    ├── expression_translator.py       # 表达式转换器
    ├── data_adapter.py                # 数据适配器
    ├── factor_executor.py             # 因子执行器
    ├── pipeline.py                    # 集成流水线
    └── test_acceptance.py             # 验收测试

p/factormining/mvp/
├── mvp_implementation.md              # 部署方案
├── mvp_quantaalpha_vnpy_glue_v2.md    # 问题分析
├── mvp_implementation_and_acceptance.md  # 本文档
├── data/                              # 数据目录
│   └── sample_data.parquet
└── output/                            # 输出目录
    ├── success_factors.json
    └── failed_factors.json
```

### 7.2 常用命令

```bash
# 激活环境
conda activate mining

# 运行验收测试
cd /home/quan/testdata/aspipe_v4/third_party/glue
python test_acceptance.py

# 运行流水线
cd /home/quan/testdata/aspipe_v4/third_party/glue
python pipeline.py
```

### 7.3 参考文档

- [vnpy AlphaDataset 文档](https://github.com/vnpy/vnpy)
- [QuantaAlpha 文档](https://github.com/quantaalpha/quantaalpha)
- `mvp_quantaalpha_vnpy_glue_v2.md` - 问题分析
- `mvp_implementation.md` - 部署方案
