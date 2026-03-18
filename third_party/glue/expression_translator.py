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
        "TS_QUANTILE": "ts_quantile",
        "TS_CORR": "ts_corr",
        "TS_COVARIANCE": "ts_cov",
        "TS_DELTA": "ts_delta",
        "DECAYLINEAR": "ts_decay_linear",
        "TS_PRODUCT": "ts_product",

        # 需要特殊处理的函数 - 现在已支持
        "TS_ZSCORE": "ts_zscore",  # 通过自定义实现
        "TS_MEDIAN": "ts_quantile",  # 需要添加参数 0.5
        "TS_MAD": "ts_mad",  # 通过自定义实现
        "TS_PCTCHANGE": "ts_pctchange",  # 通过自定义实现

        # 移动平均
        "SMA": "ts_mean",
        "WMA": "ts_mean",
        "EMA": "ts_mean",

        # 其他
        "COUNT": "ts_count",
        "SUMIF": "ts_sumif",
        "HIGHDAY": "ts_argmax",
        "LOWDAY": "ts_argmin",
        "SUMAC": "ts_sum",
        "PROD": "ts_product",
    }

    # 截面函数映射
    CS_FUNCTION_MAP = {
        "RANK": "cs_rank",
        "ZSCORE": "cs_zscore",  # 通过自定义实现
        "MEAN": "cs_mean",
        "STD": "cs_std",
        "CS_SCALE": "cs_scale",
        "CS_SUM": "cs_sum",
        "CS_MEAN": "cs_mean",
        "CS_STD": "cs_std",
        "CS_RANK": "cs_rank",
        "SKEW": "cs_skew",
        "KURT": "cs_kurt",
        "CS_MAX": "cs_max",
        "CS_MIN": "cs_min",
        "MEDIAN": "cs_median",
    }

    # 数学函数映射
    MATH_FUNCTION_MAP = {
        "LOG": "log",
        "ABS": "abs",
        "SIGN": "sign",
        "POW": "pow1",
        "SQRT": "sqrt",
        "EXP": "exp",
        "INV": "inv",
        "FLOOR": "floor",
    }

    # 技术指标映射
    TA_FUNCTION_MAP = {
        "RSI": "ta_rsi",
        "ATR": "ta_atr",
        "MACD": "ta_macd",
        "BB_MIDDLE": "ta_bb_middle",
        "BB_UPPER": "ta_bb_upper",
        "BB_LOWER": "ta_bb_lower",
    }

    # 比较函数映射（转换为运算符）
    COMPARE_FUNCTION_MAP = {
        "GT": ">",
        "LT": "<",
        "GE": ">=",
        "LE": "<=",
        "EQ": "==",
        "NE": "!=",
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

        # 步骤2: 转换特殊函数（如 ZSCORE, TS_ZSCORE）
        expr = self._convert_special_functions(expr)

        # 步骤3: 转换函数名
        expr = self._convert_functions(expr)

        # 步骤4: 转换比较函数
        expr = self._convert_compare_functions(expr)

        # 步骤5: 转换条件表达式 (C)?(A):(B) -> quesval(C, A, B)
        expr = self._convert_conditionals(expr)

        # 步骤6: 转换逻辑运算符
        expr = self._convert_logical_operators(expr)

        # 步骤7: 清理多余空格
        expr = re.sub(r'\s+', ' ', expr).strip()

        return expr, self.warnings + [
            f"不支持的功能: {f}" for f in self.unsupported_functions
        ]

    def _remove_dollar_prefix(self, expr: str) -> str:
        """移除变量名的 $ 前缀"""
        return re.sub(r'\$(\w+)', r'\1', expr)

    def _convert_special_functions(self, expr: str) -> str:
        """转换需要特殊处理的函数"""
        # ZSCORE(x) -> (x - cs_mean(x)) / cs_std(x)
        expr = re.sub(
            r'\bZSCORE\s*\(\s*([^)]+)\s*\)',
            r'((\1 - cs_mean(\1)) / cs_std(\1))',
            expr,
            flags=re.IGNORECASE
        )

        # TS_ZSCORE(x, p) -> (x - ts_mean(x, p)) / ts_std(x, p)
        expr = re.sub(
            r'\bTS_ZSCORE\s*\(\s*([^,]+)\s*,\s*([^)]+)\s*\)',
            r'((\1 - ts_mean(\1, \2)) / ts_std(\1, \2))',
            expr,
            flags=re.IGNORECASE
        )

        return expr

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
                if re.search(pattern, expr, re.IGNORECASE):
                    self.unsupported_functions.append(qa_name)
            else:
                # 替换函数名（保持大小写敏感的替换）
                pattern = rf'\b{qa_name}\s*\('
                expr = re.sub(pattern, f'{vnpy_name}(', expr, flags=re.IGNORECASE)

        return expr

    def _convert_compare_functions(self, expr: str) -> str:
        """转换比较函数为运算符"""
        for qa_name, op in self.COMPARE_FUNCTION_MAP.items():
            # 匹配 GT(x, y) 格式
            pattern = rf'\b{qa_name}\s*\(\s*([^,]+)\s*,\s*([^)]+)\s*\)'

            def make_replacer(operator):
                def replacer(match):
                    arg1 = match.group(1).strip()
                    arg2 = match.group(2).strip()
                    return f"({arg1} {operator} {arg2})"
                return replacer

            expr = re.sub(pattern, make_replacer(op), expr, flags=re.IGNORECASE)

        return expr

    def _convert_conditionals(self, expr: str) -> str:
        """
        转换条件表达式:
        (C)?(A):(B) -> quesval(C, A, B) 或 quesval2(C, C, A, B)

        注意：vnpy 的 math_function 中有 quesval 和 quesval2
        quesval(cond, val) - 条件为真返回 val
        quesval2(cond, cond_val, true_val, false_val) - 完整条件表达式
        """
        # 使用栈来处理嵌套的条件表达式
        result = []
        i = 0
        n = len(expr)

        while i < n:
            if expr[i] == '(':
                # 尝试匹配条件表达式 (C)?(A):(B)
                match = self._find_conditional(expr, i)
                if match:
                    cond, true_val, false_val, end_pos = match
                    # 递归处理嵌套的条件表达式
                    cond = self._convert_conditionals(cond)
                    true_val = self._convert_conditionals(true_val)
                    false_val = self._convert_conditionals(false_val)
                    result.append(f"quesval({cond}, {true_val}, {false_val})")
                    i = end_pos
                    continue

            result.append(expr[i])
            i += 1

        return ''.join(result)

    def _find_conditional(self, expr: str, start: int) -> Tuple[str, str, str, int]:
        """
        查找条件表达式 (C)?(A):(B)
        返回 (condition, true_value, false_value, end_position) 或 None
        """
        try:
            if start >= len(expr) or expr[start] != '(':
                return None

            # 找条件部分 C
            cond_end = self._find_matching_paren(expr, start)
            if cond_end is None:
                return None

            condition = expr[start + 1:cond_end]

            # 检查后面是否有 ?(
            pos = cond_end + 1
            if pos + 1 >= len(expr) or expr[pos:pos + 2] != '?(':
                return None

            # 找真值部分 A
            true_start = pos + 2
            true_end = self._find_matching_paren(expr, true_start - 1)
            if true_end is None:
                return None

            true_value = expr[true_start:true_end]

            # 检查后面是否有 :(
            pos = true_end + 1
            if pos + 1 >= len(expr) or expr[pos:pos + 2] != ':(':
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
        """
        转换逻辑运算符 && 和 ||

        注意：vnpy 使用 eval() 执行表达式，需要 Python 兼容的语法
        && -> and (但这里保持原样，由 vnpy 处理)
        || -> or
        """
        # vnpy 的表达式执行可能不支持 && 和 ||
        # 但根据代码分析，vnpy 的 utility.py 使用 eval()，
        # 所以应该转换为 Python 的 and/or

        # 然而，AND/OR 在 QuantaAlpha 中可能是函数调用形式
        # 这里保持原样，让 _convert_functions 处理

        self.warnings.append("逻辑运算符 && 和 || 可能需要手动验证")
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
            "partial": ["TS_MEDIAN", "HIGHDAY", "LOWDAY", "ZSCORE", "TS_ZSCORE"]
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
        "TS_MEAN($close, 20)",
        "ZSCORE($close)",
        "TS_ZSCORE($close, 20)",
        "($close > $open)?($close):($open)",
        "GT($close, DELAY($close, 1))",
    ]

    translator = ExpressionTranslator()
    print("=" * 60)
    print("QuantaAlpha → vnpy 表达式转换测试")
    print("=" * 60)

    for expr in test_cases:
        result, warnings = translator.translate(expr)
        print(f"\n输入: {expr}")
        print(f"输出: {result}")
        if warnings:
            print(f"警告: {warnings}")
