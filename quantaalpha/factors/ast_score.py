"""
AST 相似度归一化评分模块。

提供基于抽象语法树 (AST) 的代码相似度计算功能,
通过寻找两棵 AST 之间的最大公共子树来评估表达式的结构相似性。

归一化公式:
    score = min(1.0, max_common_subtree_size / max(nodes_a, nodes_b))

该分数范围在 [0.0, 1.0] 之间,1.0 表示完全相同,0.0 表示完全不相同。
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ASTSimilarityResult:
    """AST 相似度计算结果"""

    score: float  # 归一化分数 [0.0, 1.0]
    subtree_size: int  # 最大公共子树节点数
    nodes_a: int  # 表达式 A 的节点数
    nodes_b: int  # 表达式 B 的节点数
    error: Optional[str] = None  # 错误信息,成功为 None


def compute_ast_score(expr_a: str, expr_b: str) -> ASTSimilarityResult:
    """
    计算两个因子表达式的 AST 相似度归一化分数。

    通过解析两个表达式为 AST,然后寻找它们之间的最大公共子树,
    最后使用归一化公式计算相似度分数。

    转换公式:
        score = min(1.0, max_common_subtree_size / max(nodes_a, nodes_b))

    Args:
        expr_a: 表达式 A (字符串形式)
        expr_b: 表达式 B (字符串形式)

    Returns:
        ASTSimilarityResult: 包含归一化分数和详细信息的对象
            - score: 归一化分数,范围 [0.0, 1.0]
            - subtree_size: 最大公共子树的节点数
            - nodes_a: 表达式 A 的 AST 节点总数
            - nodes_b: 表达式 B 的 AST 节点总数
            - error: 错误信息,成功时为 None

    Examples:
        >>> result = compute_ast_score("a + b", "a + b")
        >>> result.score
        1.0

        >>> result = compute_ast_score("a + b", "x * y")
        >>> result.score
        0.0

        >>> result = compute_ast_score("TS_MAX($close, 10)", "TS_MAX($close, 20)")
        >>> 0.0 < result.score < 1.0
        True
    """
    try:
        # 支持两种导入方式:
        # 1. 相对导入 (当作为包内模块使用时)
        # 2. 绝对导入 (当作为独立脚本运行时)
        try:
            from .coder.factor_ast import (
                count_nodes,
                find_largest_common_subtree,
                parse_expression,
            )
        except ImportError:
            from quantaalpha.factors.coder.factor_ast import (
                count_nodes,
                find_largest_common_subtree,
                parse_expression,
            )

        # 解析表达式为 AST
        tree_a = parse_expression(expr_a)
        tree_b = parse_expression(expr_b)

        # 寻找最大公共子树
        match = find_largest_common_subtree(tree_a, tree_b)

        # 计算节点数
        nodes_a = count_nodes(tree_a)
        nodes_b = count_nodes(tree_b)

        # 如果没有公共子树,返回 0 分
        if match is None:
            return ASTSimilarityResult(
                score=0.0,
                subtree_size=0,
                nodes_a=nodes_a,
                nodes_b=nodes_b,
                error=None,
            )

        # 归一化: 公共子树节点数 / 较大树的节点数
        max_nodes = max(nodes_a, nodes_b)
        score = min(1.0, match.size / max_nodes) if max_nodes > 0 else 0.0

        return ASTSimilarityResult(
            score=score,
            subtree_size=match.size,
            nodes_a=nodes_a,
            nodes_b=nodes_b,
            error=None,
        )

    except Exception as e:
        return ASTSimilarityResult(
            score=0.0,
            subtree_size=0,
            nodes_a=0,
            nodes_b=0,
            error=str(e),
        )


if __name__ == "__main__":
    # 示例用法

    print("=" * 60)
    print("AST 相似度归一化评分示例")
    print("=" * 60)

    # 示例 1: 完全相同的表达式
    expr1_a = "($close - TS_MIN($low, 14)) / (TS_MAX($high, 14) - TS_MIN($low, 14) + 1e-8)"
    expr1_b = "($close - TS_MIN($low, 14)) / (TS_MAX($high, 14) - TS_MIN($low, 14) + 1e-8)"
    result1 = compute_ast_score(expr1_a, expr1_b)
    print(f"\n【示例 1】完全相同的表达式")
    print(f"  表达式 A: {expr1_a}")
    print(f"  表达式 B: {expr1_b}")
    print(f"  相似度分数: {result1.score:.4f}")
    print(f"  公共子树大小: {result1.subtree_size}")
    print(f"  节点数 A: {result1.nodes_a}, B: {result1.nodes_b}")
    print(f"  错误信息: {result1.error}")

    # 示例 2: 部分相似的表达式
    expr2_a = "($close - TS_MIN($low, 14)) / (TS_MAX($high, 14) - TS_MIN($low, 14) + 1e-8)"
    expr2_b = "($close - TS_MIN($low, 20)) / (TS_MAX($high, 20) - TS_MIN($low, 20) + 1e-8)"
    result2 = compute_ast_score(expr2_a, expr2_b)
    print(f"\n【示例 2】部分相似的表达式 (参数不同)")
    print(f"  表达式 A: {expr2_a}")
    print(f"  表达式 B: {expr2_b}")
    print(f"  相似度分数: {result2.score:.4f}")
    print(f"  公共子树大小: {result2.subtree_size}")
    print(f"  节点数 A: {result2.nodes_a}, B: {result2.nodes_b}")
    print(f"  错误信息: {result2.error}")

    # 示例 3: 完全不同的表达式
    expr3_a = "$close / $open"
    expr3_b = "STD($volume, 20) / MEAN($volume, 10)"
    result3 = compute_ast_score(expr3_a, expr3_b)
    print(f"\n【示例 3】完全不同的表达式")
    print(f"  表达式 A: {expr3_a}")
    print(f"  表达式 B: {expr3_b}")
    print(f"  相似度分数: {result3.score:.4f}")
    print(f"  公共子树大小: {result3.subtree_size}")
    print(f"  节点数 A: {result3.nodes_a}, B: {result3.nodes_b}")
    print(f"  错误信息: {result3.error}")

    # 示例 4: 包含错误的表达式
    expr4_a = "invalid expression !!!"
    expr4_b = "$close + $open"
    result4 = compute_ast_score(expr4_a, expr4_b)
    print(f"\n【示例 4】包含解析错误的表达式")
    print(f"  表达式 A: {expr4_a}")
    print(f"  表达式 B: {expr4_b}")
    print(f"  相似度分数: {result4.score:.4f}")
    print(f"  公共子树大小: {result4.subtree_size}")
    print(f"  节点数 A: {result4.nodes_a}, B: {result4.nodes_b}")
    print(f"  错误信息: {result4.error}")

    # 示例 5: 实际因子对比
    expr5_a = "($close - TS_MIN($low, 14)) / (TS_MAX($high, 14) - TS_MIN($low, 14) + 1e-8)"
    expr5_b = "TS_MAX($high, 14) - TS_MIN($low, 14)"
    result5 = compute_ast_score(expr5_a, expr5_b)
    print(f"\n【示例 5】实际因子对比 (复杂 vs 简单)")
    print(f"  表达式 A: {expr5_a}")
    print(f"  表达式 B: {expr5_b}")
    print(f"  相似度分数: {result5.score:.4f}")
    print(f"  公共子树大小: {result5.subtree_size}")
    print(f"  节点数 A: {result5.nodes_a}, B: {result5.nodes_b}")
    print(f"  错误信息: {result5.error}")

    print("\n" + "=" * 60)
