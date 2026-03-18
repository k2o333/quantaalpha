"""
MVP 验收测试套件
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
        ("DELTA($close, 1)", "ts_delta(close, 1)"),
        ("TS_SUM($volume, 5)", "ts_sum(volume, 5)"),
        ("LOG($close)", "log(close)"),
        ("SIGN($close - $open)", "sign(close - open)"),
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


def test_advanced_expression_translator():
    """测试高级表达式转换功能"""
    print("\n" + "=" * 60)
    print("测试: 高级表达式转换")
    print("=" * 60)

    translator = ExpressionTranslator()

    # 测试 ZSCORE 转换
    test_cases = [
        ("ZSCORE($close)", "((close - cs_mean(close)) / cs_std(close))"),
        ("TS_ZSCORE($close, 20)", "((close - ts_mean(close, 20)) / ts_std(close, 20))"),
        ("GT($close, $open)", "(close > open)"),
        ("LT($close, $open)", "(close < open)"),
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

    # 检查 vt_symbol 格式
    sample_symbols = df["vt_symbol"].unique().to_list()[:3]
    for symbol in sample_symbols:
        if ".SZSE" in symbol or ".SSE" in symbol:
            print(f"✓ vt_symbol 格式正确: {symbol}")
        else:
            print(f"✗ vt_symbol 格式错误: {symbol}")
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
        {"name": "test_ts_mean", "expression": "ts_mean(close, 10)"},
    ]

    results = executor.execute_batch(test_factors)

    # 验证结果
    success_count = sum(1 for r in results if r.success)
    print(f"\n执行结果: {success_count}/{len(results)} 成功")

    for r in results:
        status = "✓" if r.success else "✗"
        ic_str = f"IC={r.ic_value:.4f}" if r.ic_value is not None else "IC=N/A"
        print(f"{status} {r.factor_name}: {ic_str}")
        if not r.success:
            print(f"   错误: {r.error_message}")

    # 至少2个成功才算通过
    return success_count >= 2


def test_pipeline():
    """测试集成流水线"""
    print("\n" + "=" * 60)
    print("测试: 集成流水线")
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
            "name": "Price_Mean_20",
            "expression": "TS_MEAN($close, 20)",
            "description": "20日均价"
        },
    ]

    test_file = Path(__file__).parent / "test_acceptance_factors.json"
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
        n_symbols=5
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


def test_output_files():
    """测试输出文件生成"""
    print("\n" + "=" * 60)
    print("测试: 输出文件")
    print("=" * 60)

    output_dir = Path(__file__).parent.parent.parent / "p" / "factormining" / "mvp" / "output"

    success_file = output_dir / "success_factors.json"
    failed_file = output_dir / "failed_factors.json"

    checks = []

    if success_file.exists():
        with open(success_file, "r", encoding="utf-8") as f:
            success_data = json.load(f)
        checks.append(("success_factors.json 存在", True))
        checks.append((f"成功因子数量: {len(success_data)}", len(success_data) >= 0))
    else:
        checks.append(("success_factors.json 存在", False))

    if failed_file.exists():
        with open(failed_file, "r", encoding="utf-8") as f:
            failed_data = json.load(f)
        checks.append(("failed_factors.json 存在", True))
        checks.append((f"失败因子数量: {len(failed_data)}", len(failed_data) >= 0))
    else:
        checks.append(("failed_factors.json 存在", False))

    all_passed = True
    for name, passed in checks:
        status = "✓" if passed else "✗"
        print(f"{status} {name}")
        if not passed:
            all_passed = False

    return all_passed


def test_operator_coverage():
    """测试算子覆盖率"""
    print("\n" + "=" * 60)
    print("测试: 算子覆盖率")
    print("=" * 60)

    translator = ExpressionTranslator()
    status = translator.get_support_status()

    supported = len(status["supported"])
    unsupported = len(status["unsupported"])
    total = supported + unsupported

    coverage = supported / total if total > 0 else 0

    print(f"支持的算子: {supported}")
    print(f"不支持的算子: {unsupported}")
    print(f"覆盖率: {coverage:.1%}")

    print(f"\n支持的算子列表:")
    for op in sorted(status["supported"]):
        print(f"  - {op}")

    print(f"\n不支持的算子列表:")
    for op in sorted(status["unsupported"]):
        print(f"  - {op}")

    # 覆盖率目标: 80%
    target_coverage = 0.8
    passed = coverage >= target_coverage

    status_str = "✓" if passed else "✗"
    print(f"\n{status_str} 覆盖率目标 ({target_coverage:.0%}): {coverage:.1%}")

    return passed


def main():
    """运行所有验收测试"""
    print("\n" + "=" * 60)
    print("MVP 验收测试套件")
    print("=" * 60)

    results = []

    # 运行测试
    results.append(("基础表达式转换", test_expression_translator()))
    results.append(("高级表达式转换", test_advanced_expression_translator()))
    results.append(("数据适配器", test_data_adapter()))
    results.append(("因子执行器", test_factor_executor()))
    results.append(("集成流水线", test_pipeline()))
    results.append(("输出文件生成", test_output_files()))
    results.append(("算子覆盖率", test_operator_coverage()))

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
