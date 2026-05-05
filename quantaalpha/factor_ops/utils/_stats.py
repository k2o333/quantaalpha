"""基础统计函数。"""

from __future__ import annotations

import math
from collections.abc import Iterable


def is_finite(value: object) -> bool:
    """判断值是否为有限数字。"""
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def mean(values: Iterable[float]) -> float:
    """计算均值。"""
    items = [float(value) for value in values if is_finite(value)]
    if not items:
        return math.nan
    return sum(items) / len(items)


def sample_std(values: Iterable[float]) -> float:
    """计算样本标准差。"""
    items = [float(value) for value in values if is_finite(value)]
    if len(items) < 2:
        return math.nan
    avg = mean(items)
    variance = sum((value - avg) ** 2 for value in items) / (len(items) - 1)
    return math.sqrt(variance)


def population_std(values: Iterable[float]) -> float:
    """计算总体标准差。"""
    items = [float(value) for value in values if is_finite(value)]
    if not items:
        return math.nan
    avg = mean(items)
    variance = sum((value - avg) ** 2 for value in items) / len(items)
    return math.sqrt(variance)


def ranks(values: list[float]) -> list[float]:
    """计算平均秩，忽略 NaN 后保留原位置。"""
    ranked: list[float] = [math.nan] * len(values)
    finite_items = [(idx, float(value)) for idx, value in enumerate(values) if is_finite(value)]
    finite_items.sort(key=lambda item: item[1])

    pos = 0
    while pos < len(finite_items):
        end = pos + 1
        while end < len(finite_items) and finite_items[end][1] == finite_items[pos][1]:
            end += 1
        avg_rank = (pos + 1 + end) / 2
        for idx, _ in finite_items[pos:end]:
            ranked[idx] = avg_rank
        pos = end

    return ranked


def pearson_corr(left: list[float], right: list[float]) -> float:
    """计算 Pearson 相关系数。"""
    pairs = [
        (float(lhs), float(rhs))
        for lhs, rhs in zip(left, right, strict=False)
        if is_finite(lhs) and is_finite(rhs)
    ]
    if len(pairs) < 2:
        return math.nan

    left_values = [pair[0] for pair in pairs]
    right_values = [pair[1] for pair in pairs]
    left_mean = mean(left_values)
    right_mean = mean(right_values)
    left_den = math.sqrt(sum((value - left_mean) ** 2 for value in left_values))
    right_den = math.sqrt(sum((value - right_mean) ** 2 for value in right_values))
    if left_den == 0 or right_den == 0:
        return math.nan
    numerator = sum((lhs - left_mean) * (rhs - right_mean) for lhs, rhs in pairs)
    return numerator / (left_den * right_den)


def spearman_corr(left: list[float], right: list[float]) -> float:
    """计算 Spearman 秩相关系数。"""
    pairs = [
        (float(lhs), float(rhs))
        for lhs, rhs in zip(left, right, strict=False)
        if is_finite(lhs) and is_finite(rhs)
    ]
    if len(pairs) < 2:
        return math.nan
    return pearson_corr(ranks([pair[0] for pair in pairs]), ranks([pair[1] for pair in pairs]))


def linear_slope(values: list[float]) -> float:
    """计算序列对时间索引的一元线性回归斜率。"""
    y_values = [float(value) for value in values if is_finite(value)]
    if len(y_values) < 2:
        return math.nan
    x_values = list(range(len(y_values)))
    x_mean = mean(x_values)
    y_mean = mean(y_values)
    denominator = sum((x_value - x_mean) ** 2 for x_value in x_values)
    if denominator == 0:
        return math.nan
    numerator = sum((x_value - x_mean) * (y_value - y_mean) for x_value, y_value in zip(x_values, y_values))
    return numerator / denominator

