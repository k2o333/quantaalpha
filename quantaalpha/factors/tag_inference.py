"""
Tag inference for factor expressions.

Provides shared tag inference logic used across:
- FactorLibraryManager.add_factors_from_experiment (library.py)
- ContinuousMutationOperator._normalize_factor_entry (implementations.py)
- FactorTask creation in proposal.py
"""

from __future__ import annotations


# Keywords that indicate financial data dependency
FINANCIAL_KEYWORDS = [
    "roe", "roa", "roic", "gross_margin", "net_margin", "profit_margin",
    "revenue", "income", "ebit", "ebitda", "assets", "liabilities",
    "equity", "debt", "cash_flow", "operating profit", "net profit",
    "eps", "book_value", "financial_ratio",
    "profit", "margin",
]

# Keywords that indicate moneyflow data dependency
MONEYFLOW_KEYWORDS = [
    "moneyflow", "margin", "short", "borrow", "lend",
    "northbound", "southbound", "的主力", "净流入", "融资", "融券",
]

# Keywords that indicate chip/distribution data dependency
CHIP_KEYWORDS = [
    "chip", "float", "holder", "持股", "筹码", "cyq",
    "position", "distribution", "成本", "集中度",
]

# Keywords that indicate price/volume data dependency
PRICE_VOLUME_KEYWORDS = [
    "$close", "$open", "$high", "$low", "$volume", "$amount",
    "close", "open", "high", "low", "volume", "amount",
    "price",
]

# Time-horizon keywords
SHORT_TERM_KEYWORDS = [
    "delay", "ts_", "rolling", "window",
    "1d", "5d", "10d", "20d", "short",
]

LONG_TERM_KEYWORDS = [
    "120d", "240d", "long", "medium",
]


def infer_tags_from_expression(expression: str) -> dict[str, list[str]]:
    """
    Infer all tag dimensions from a factor expression.

    Args:
        expression: Factor expression string (e.g., "$close / ts_mean($volume, 5)")

    Returns:
        Dict with tag categories as keys and lists of inferred tags as values.
        Returns DEFAULT_TAGS-compatible structure.
    """
    if not expression:
        return {
            "category": [],
            "data_dependency": [],
            "market_environment": [],
            "time_horizon": [],
        }

    expr_lower = expression.lower()

    # Infer data_dependency
    data_deps: list[str] = []

    if any(k in expr_lower for k in FINANCIAL_KEYWORDS):
        data_deps.append("financial")
    if any(k in expr_lower for k in MONEYFLOW_KEYWORDS):
        data_deps.append("moneyflow")
    if any(k in expr_lower for k in CHIP_KEYWORDS):
        data_deps.append("chip")
    if any(k in expr_lower for k in PRICE_VOLUME_KEYWORDS):
        data_deps.append("price_volume")

    # Default to price_volume if no specific dependency found
    if not data_deps:
        data_deps.append("price_volume")

    # Infer time_horizon
    time_horizons: list[str] = []

    if any(k in expr_lower for k in SHORT_TERM_KEYWORDS):
        time_horizons.append("short_term")
    if any(k in expr_lower for k in LONG_TERM_KEYWORDS):
        time_horizons.append("medium_term")

    # If expression uses ts_mean/ts_delay with small window, mark as short_term
    import re
    ts_pattern = re.findall(r"ts_(mean|delay|std|corr|skew|kurt)[\^\(]?[\(]?\s*[,(\d]+", expr_lower)
    if ts_pattern:
        time_horizons.append("short_term")

    if not time_horizons:
        time_horizons.append("short_term")  # Default

    # Infer category (simple heuristics)
    categories: list[str] = []

    if any(k in expr_lower for k in ["return", "ret", "yield"]):
        categories.append("momentum")
    if any(k in expr_lower for k in ["rev", "reversal", "inverse"]):
        categories.append("reversal")
    if any(k in expr_lower for k in ["value", "book", "earning", "bv"]):
        categories.append("value")
    if any(k in expr_lower for k in ["quality", "roe", "roa", "margin", "profit"]):
        categories.append("quality")
    if any(k in expr_lower for k in ["vol", "volume", "liquid", "amount"]):
        categories.append("liquidity")

    if not categories:
        categories.append("momentum")  # Default

    return {
        "category": list(set(categories)),
        "data_dependency": list(set(data_deps)),
        "market_environment": [],
        "time_horizon": list(set(time_horizons)),
    }
