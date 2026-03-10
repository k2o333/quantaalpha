"""
因子执行器：使用 vnpy 计算因子并评估性能
"""

import polars as pl
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import json
import time


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
        output_dir: str = None
    ):
        self.df = df
        self.train_period = train_period
        self.valid_period = valid_period
        self.test_period = test_period

        # 默认输出目录在 p/factormining/mvp/output
        if output_dir is None:
            project_root = Path(__file__).parent.parent.parent
            output_dir = project_root / "p" / "factormining" / "mvp" / "output"
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.results: List[FactorResult] = []
        self.dataset = None

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
        start_time = time.time()

        try:
            # 延迟导入 vnpy
            from vnpy.alpha.dataset import AlphaDataset

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
            status = "OK" if result.success else "FAIL"
            ic_str = f"IC={result.ic_value:.4f}" if result.ic_value is not None else "IC=N/A"
            print(f"  [{status}] {result.factor_name}: {ic_str}")
            if not result.success:
                print(f"   错误: {result.error_message[:200]}")

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
    import sys
    sys.path.insert(0, str(Path(__file__).parent))

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
