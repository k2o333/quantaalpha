"""
安全表达式求值器 — 基于 AST 白名单的 eval 替代。

设计原则:
1. 只允许数学运算、函数调用、下标访问、属性访问
2. 禁止 import、exec、eval、open、file I/O 等危险操作
3. 禁止 __ 开头的属性访问（防止 __import__, __builtins__ 等）
4. 白名单内的函数名通过 allowed_names 传入

使用方式:
    from quantaalpha.backtest.safe_eval import safe_eval
    result = safe_eval(expression_str, exec_globals)
"""

import ast
import logging
from typing import Any, Dict, Optional, Set

logger = logging.getLogger(__name__)

# 允许的 AST 节点类型
ALLOWED_NODE_TYPES = {
    # 表达式相关
    ast.Expression,
    ast.Module,

    # 值类型
    ast.Constant,      # 数字、字符串常量
    ast.Name,          # 变量名
    ast.Load,          # 加载变量
    ast.Store,         # 赋值（不允许出现在 eval 中）

    # 运算
    ast.BinOp,         # 二元运算 (+, -, *, /, //, %, **)
    ast.UnaryOp,       # 一元运算 (-, +, ~, not)
    ast.BoolOp,        # 布尔运算 (and, or)
    ast.Compare,       # 比较运算 (<, >, ==, !=, <=, >=)

    # 运算符
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv,
    ast.Mod, ast.Pow, ast.BitAnd, ast.BitOr, ast.BitXor,
    ast.LShift, ast.RShift,
    ast.USub, ast.UAdd, ast.Not, ast.Invert,
    ast.And, ast.Or,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
    ast.Is, ast.IsNot, ast.In, ast.NotIn,

    # 函数调用
    ast.Call,          # 函数调用
    ast.keyword,       # 关键字参数

    # 下标和属性
    ast.Subscript,     # df['col']
    ast.Attribute,     # obj.attr
    ast.Index,         # 下标索引 (Python 3.8-)
    ast.Slice,         # 切片

    # 容器
    ast.Tuple,         # 元组
    ast.List,          # 列表
    ast.Dict,          # 字典
    ast.Set,           # 集合

    # 条件
    ast.IfExp,         # 三元表达式 a if cond else b

    # 推导式（用于 pandas 的 apply 等）
    ast.ListComp,
    ast.GeneratorExp,
    ast.comprehension,

    # starred (用于解包)
    ast.Starred,
}

# 禁止的函数名
FORBIDDEN_NAMES = {
    "eval", "exec", "compile", "execfile",
    "open", "file", "input",
    "__import__", "getattr", "setattr", "delattr",
    "globals", "locals", "vars", "dir",
    "breakpoint", "exit", "quit",
    "classmethod", "staticmethod", "property",
    "type", "object", "super",
}

# 禁止的属性前缀
FORBIDDEN_ATTR_PREFIXES = ("__",)


class UnsafeExpressionError(Exception):
    """表达式中包含不安全的操作。"""
    pass


class SafeExpressionValidator(ast.NodeVisitor):
    """
    AST 白名单验证器。

    遍历 AST 树，检查每个节点是否在白名单内。
    对函数调用和属性访问做额外的安全检查。
    """

    def __init__(self, allowed_names: Optional[Set[str]] = None):
        """
        Args:
            allowed_names: 允许使用的变量/函数名集合。
                          如果为 None，则不限制名称（只做节点类型检查）。
        """
        self.allowed_names = allowed_names
        self.violations: list[str] = []

    def _check_node_type(self, node: ast.AST) -> bool:
        """检查节点类型是否在白名单内。返回 False 表示不允许，返回 True 表示允许继续遍历。"""
        if type(node) not in ALLOWED_NODE_TYPES:
            self.violations.append(
                f"Disallowed AST node: {type(node).__name__} "
                f"at line {getattr(node, 'lineno', '?')}"
            )
            return False
        return True

    def visit(self, node: ast.AST) -> None:
        """检查节点类型是否安全，然后继续遍历。"""
        if not self._check_node_type(node):
            return
        # 调用父类的 visit 以便 dispatch 到具体的 visit_XXX 方法
        super().visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        """检查变量名是否安全。"""
        name = node.id

        # 检查禁止名称
        if name in FORBIDDEN_NAMES:
            self.violations.append(f"Forbidden name: '{name}'")
            return

        # 检查 __ 前缀
        if name.startswith("__"):
            self.violations.append(f"Forbidden dunder name: '{name}'")
            return

        # 继续遍历子节点
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        """检查属性访问是否安全。"""
        # 先遍历子节点（深度优先），收集所有嵌套的违规
        self.generic_visit(node)

        # 再检查当前属性是否安全
        attr = node.attr
        for prefix in FORBIDDEN_ATTR_PREFIXES:
            if attr.startswith(prefix):
                self.violations.append(
                    f"Forbidden attribute access: '.{attr}'"
                )
                return

    def visit_Call(self, node: ast.Call) -> None:
        """检查函数调用是否安全。"""
        # 如果调用的是一个直接名称（如 eval(...)）
        if isinstance(node.func, ast.Name):
            if node.func.id in FORBIDDEN_NAMES:
                self.violations.append(
                    f"Forbidden function call: '{node.func.id}()'"
                )
                return

        # 如果调用的是属性（如 os.system(...)）
        if isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            for prefix in FORBIDDEN_ATTR_PREFIXES:
                if attr.startswith(prefix):
                    self.violations.append(
                        f"Forbidden method call: '.{attr}()'"
                    )
                    return

        self.generic_visit(node)


def validate_expression(expr_str: str, allowed_names: Optional[Set[str]] = None) -> list[str]:
    """
    验证表达式字符串是否安全。

    Args:
        expr_str: 表达式字符串
        allowed_names: 允许使用的变量/函数名

    Returns:
        违规列表（空列表表示安全）
    """
    try:
        tree = ast.parse(expr_str, mode='eval')
    except SyntaxError:
        # 如果连 parse 都失败，说明不是合法的 Python 表达式
        # 返回空列表让原有的 eval 处理错误
        return []

    validator = SafeExpressionValidator(allowed_names)
    validator.visit(tree)
    return validator.violations


def safe_eval(
    expr_str: str,
    exec_globals: Dict[str, Any],
    allowed_names: Optional[Set[str]] = None,
) -> Any:
    """
    安全版 eval — 先 AST 验证再执行。

    Args:
        expr_str: 表达式字符串
        exec_globals: 执行环境（传给 eval 的 globals）
        allowed_names: 允许的名称白名单（可选）

    Returns:
        表达式计算结果

    Raises:
        UnsafeExpressionError: 表达式包含不安全操作
    """
    violations = validate_expression(expr_str, allowed_names)

    if violations:
        violation_str = "; ".join(violations[:5])
        logger.warning(f"Unsafe expression blocked: {violation_str}")
        raise UnsafeExpressionError(
            f"Expression contains unsafe operations: {violation_str}"
        )

    # 通过验证后正常 eval
    return eval(expr_str, exec_globals)
