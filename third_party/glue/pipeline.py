"""
MVP 集成流水线：整合表达式转换、数据准备、因子计算
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import time

# 添加 glue 目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from expression_translator import ExpressionTranslator
from data_adapter import DataAdapter
from factor_executor import FactorExecutor


class MVPPipeline:
    """
    MVP 集成流水线

    整合以下步骤：
    1. 数据准备
    2. 因子加载和转换
    3. 因子执行
    4. 结果汇总
    """

    def __init__(
        self,
        train_period: Tuple[str, str] = ("2022-01-01", "2022-03-31"),
        valid_period: Tuple[str, str] = ("2022-04-01", "2022-05-31"),
        test_period: Tuple[str, str] = ("2022-06-01", "2022-06-30"),
        data_dir: Optional[str] = None,
        output_dir: Optional[str] = None
    ):
        self.train_period = train_period
        self.valid_period = valid_period
        self.test_period = test_period

        # 初始化组件
        self.translator = ExpressionTranslator()
        self.adapter = DataAdapter(data_dir=data_dir)

        # 设置输出目录
        if output_dir is None:
            project_root = Path(__file__).parent.parent.parent
            output_dir = project_root / "p" / "factormining" / "mvp" / "output"
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 状态
        self.df = None
        self.translated_factors: List[Dict] = []
        self.failed_translations: List[Dict] = []
        self.executor: Optional[FactorExecutor] = None

    def prepare_data(
        self,
        data_source: Optional[str] = None,
        n_symbols: int = 10,
        start_date: str = "2022-01-01",
        end_date: str = "2022-06-30"
    ) -> "MVPPipeline":
        """
        准备数据

        Args:
            data_source: 数据源路径（CSV 或 Parquet），如果为 None 则创建示例数据
            n_symbols: 创建示例数据时的股票数量
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            self，支持链式调用
        """
        print("[Pipeline] 准备数据...")

        if data_source is None:
            # 创建示例数据
            data_path = self.adapter.create_sample_data(
                start_date=start_date,
                end_date=end_date,
                n_symbols=n_symbols,
                output_file="pipeline_sample_data.parquet"
            )
            print(f"  创建示例数据: {data_path}")
            self.df = self.adapter.load_from_parquet(data_path)
        elif data_source.endswith('.csv'):
            self.df = self.adapter.load_from_csv(data_source)
        elif data_source.endswith('.parquet'):
            self.df = self.adapter.load_from_parquet(data_source)
        else:
            raise ValueError(f"不支持的数据格式: {data_source}")

        # 验证数据
        is_valid, missing = self.adapter.validate(self.df)
        if not is_valid:
            raise ValueError(f"数据验证失败，缺失列: {missing}")

        print(f"  数据形状: {self.df.shape}")
        print(f"  列: {self.df.columns}")
        print(f"  股票数量: {self.df['vt_symbol'].n_unique()}")
        print(f"  日期范围: {self.df['datetime'].min()} ~ {self.df['datetime'].max()}")

        return self

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
                if isinstance(info, dict):
                    factors.append({
                        "name": name,
                        "expression": info.get("expression", info.get("factor_expression", "")),
                        "description": info.get("description", info.get("factor_description", "")),
                    })
                else:
                    # 简单格式: {"factor_name": "expression"}
                    factors.append({
                        "name": name,
                        "expression": info,
                        "description": "",
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
        print(f"[Pipeline] 转换 {len(factors)} 个因子表达式...")

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
            print("[Pipeline] 没有可执行的因子")
            return []

        print(f"[Pipeline] 执行 {len(factors_to_execute)} 个因子计算...")

        # 准备执行格式
        exec_factors = [
            {"name": f["name"], "expression": f["translated_expression"]}
            for f in factors_to_execute
        ]

        # 执行计算
        self.executor = FactorExecutor(
            df=self.df,
            train_period=self.train_period,
            valid_period=self.valid_period,
            test_period=self.test_period,
            output_dir=self.output_dir
        )

        results = self.executor.execute_batch(exec_factors)

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
        max_factors: Optional[int] = None,
        data_source: Optional[str] = None,
        n_symbols: int = 10
    ) -> Dict:
        """
        运行完整流水线

        Args:
            factors_source: 因子源文件路径
            source_type: "json" 或 "quantaalpha_library"
            max_factors: 最多处理的因子数量
            data_source: 数据源路径，None 则创建示例数据
            n_symbols: 创建示例数据时的股票数量

        Returns:
            执行摘要
        """
        print("=" * 60)
        print("MVP 集成流水线启动")
        print("=" * 60)

        start_time = time.time()

        # 步骤1: 准备数据
        print("\n[步骤1] 准备数据...")
        self.prepare_data(data_source=data_source, n_symbols=n_symbols)

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
        summary["total_time"] = time.time() - start_time

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

        success_path = self.output_dir / "success_factors.json"
        with open(success_path, "w", encoding="utf-8") as f:
            json.dump(success_factors, f, ensure_ascii=False, indent=2)

        # 保存失败的因子
        failed_factors = [
            f for f in self.translated_factors
            if not f.get("execution_result", {}).get("success", True)
        ] + self.failed_translations

        failed_path = self.output_dir / "failed_factors.json"
        with open(failed_path, "w", encoding="utf-8") as f:
            json.dump(failed_factors, f, ensure_ascii=False, indent=2)

        print(f"  成功因子: {len(success_factors)} 个 -> {success_path}")
        print(f"  失败因子: {len(failed_factors)} 个 -> {failed_path}")

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
        {
            "name": "Price_Mean_20",
            "expression": "TS_MEAN($close, 20)",
            "description": "20日均价"
        },
        {
            "name": "ZScore_Close",
            "expression": "ZSCORE($close)",
            "description": "收盘价ZScore"
        },
    ]

    # 保存测试因子
    test_file = Path(__file__).parent / "test_factors.json"
    with open(test_file, "w", encoding="utf-8") as f:
        json.dump(test_factors, f, ensure_ascii=False, indent=2)

    print(f"测试因子已保存到: {test_file}")

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

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)
