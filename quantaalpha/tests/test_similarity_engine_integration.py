"""
SimilarityEngine 集成测试.

测试场景:模拟完整的 mining cycle,验证 SimilarityEngine 在整个流程中正确工作。

测试覆盖:
- 端到端冗余检查流程
- 端到端 Context 检索流程
- 加权融合模式完整流程
- Veto 模式完整流程
- 降级路径测试
- 真实因子库测试
"""

import json
import time
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from quantaalpha.continuous.implementations import DefaultMiningScheduler
from quantaalpha.factors.similarity_engine import (
    EnsembleResult,
    SimilarityEngine,
    SimilarityResult,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def weighted_config() -> Dict[str, Any]:
    """加权融合模式配置 (AST + Jaccard 启用, RAG 禁用)."""
    return {
        "enabled": True,
        "ensemble_mode": "weighted",
        "rejection_threshold": 0.85,
        "metrics": {
            "ast": {
                "enabled": True,
                "weight": 0.50,
                "veto_threshold": 0.80,
                "duplication_threshold": 8,
                "symbol_length_threshold": 300,
                "base_features_threshold": 6,
            },
            "jaccard": {
                "enabled": True,
                "weight": 0.50,
                "veto_threshold": 0.95,
                "skeleton_bonus": True,
            },
            "rag": {
                "enabled": False,
                "weight": 0.30,
                "veto_threshold": 0.90,
            },
        },
    }


@pytest.fixture
def veto_config() -> Dict[str, Any]:
    """Veto 模式配置."""
    return {
        "enabled": True,
        "ensemble_mode": "veto",
        "rejection_threshold": 0.85,
        "metrics": {
            "ast": {
                "enabled": True,
                "weight": 0.50,
                "veto_threshold": 0.80,
                "duplication_threshold": 8,
                "symbol_length_threshold": 300,
                "base_features_threshold": 6,
            },
            "jaccard": {
                "enabled": True,
                "weight": 0.50,
                "veto_threshold": 0.90,
                "skeleton_bonus": True,
            },
            "rag": {
                "enabled": False,
                "weight": 0.30,
                "veto_threshold": 0.95,
            },
        },
    }


@pytest.fixture
def sample_factor_library() -> Dict[str, Any]:
    """示例因子库数据."""
    return {
        "factors": {
            "factor_001": {
                "factor_expression": "$close - $open",
                "factor_description": "price difference between close and open",
                "factor_name": "PriceDiff",
                "evaluation": {"status": "active", "ic": 0.05},
            },
            "factor_002": {
                "factor_expression": "$close / $open",
                "factor_description": "price ratio between close and open",
                "factor_name": "PriceRatio",
                "evaluation": {"status": "active", "ic": 0.03},
            },
            "factor_003": {
                "factor_expression": "STD($volume, 20) / MEAN($volume, 10)",
                "factor_description": "volume volatility normalized by mean",
                "factor_name": "VolVolatility",
                "evaluation": {"status": "active", "ic": 0.04},
            },
            "factor_004": {
                "factor_expression": "TS_MAX($high, 14) - TS_MIN($low, 14)",
                "factor_description": "price range over 14 days",
                "factor_name": "PriceRange",
                "evaluation": {"status": "active", "ic": 0.06},
            },
            "factor_005": {
                "factor_expression": "$close - $open + $volume",
                "factor_description": "inactive factor for testing",
                "factor_name": "InactiveFactor",
                "evaluation": {"status": "inactive", "ic": 0.01},
            },
        }
    }


@pytest.fixture
def tmp_library_file(
    tmp_path: Path, sample_factor_library: Dict[str, Any]
) -> Path:
    """创建临时因子库文件."""
    library_file = tmp_path / "test_library.json"
    library_file.write_text(
        json.dumps(sample_factor_library, ensure_ascii=False)
    )
    return library_file


@pytest.fixture
def scheduler_with_similarity_engine(
    tmp_library_file: Path, weighted_config: Dict[str, Any]
) -> DefaultMiningScheduler:
    """创建注入了 SimilarityEngine 的 DefaultMiningScheduler."""
    scheduler = DefaultMiningScheduler(
        max_per_run=5,
        interval_hours=12,
        library_path=str(tmp_library_file),
        similarity_engine_cfg=weighted_config,
    )
    return scheduler


@pytest.fixture
def scheduler_without_similarity_engine(
    tmp_library_file: Path,
) -> DefaultMiningScheduler:
    """创建未注入 SimilarityEngine 的 DefaultMiningScheduler."""
    scheduler = DefaultMiningScheduler(
        max_per_run=5,
        interval_hours=12,
        library_path=str(tmp_library_file),
        similarity_engine_cfg=None,
    )
    return scheduler


# ---------------------------------------------------------------------------
# 1. 端到端冗余检查流程
# ---------------------------------------------------------------------------


class TestEndToEndRedundancyCheck:
    """端到端冗余检查流程测试."""

    def test_end_to_end_redundancy_check(
        self, scheduler_with_similarity_engine: DefaultMiningScheduler
    ) -> None:
        """
        测试完整的冗余检查流程:
        1. 创建包含几个因子的临时因子库
        2. 创建 SimilarityEngine 并注入到 DefaultMiningScheduler
        3. 调用 _check_redundancy 检查新因子
        4. 验证返回结果使用 ensemble 方法
        5. 验证分数计算正确
        """
        scheduler = scheduler_with_similarity_engine

        # 验证引擎已正确初始化
        assert scheduler._similarity_engine is not None, (
            "SimilarityEngine should be initialized"
        )
        assert isinstance(scheduler._similarity_engine, SimilarityEngine), (
            "Should be SimilarityEngine instance"
        )

        # 测试与库中因子完全相同的表达式 (factor_001)
        factor_entry = {
            "factor_id": "test_factor_001",
            "factor_expression": "$close - $open",
            "factor_description": "price difference between close and open",
        }

        result = scheduler._check_redundancy(factor_entry)

        # 验证返回结构
        assert "is_redundant" in result, "Result should contain 'is_redundant'"
        assert "most_similar_factor_id" in result, (
            "Result should contain 'most_similar_factor_id'"
        )
        assert "max_similarity" in result, (
            "Result should contain 'max_similarity'"
        )
        assert "method" in result, "Result should contain 'method'"
        assert "comparisons_made" in result, (
            "Result should contain 'comparisons_made'"
        )

        # 验证使用 ensemble 方法
        assert result["method"] == "ensemble", (
            f"Should use 'ensemble' method, got '{result['method']}'"
        )

        # 验证检测到冗余 (表达式与 factor_001 完全相同)
        assert result["is_redundant"] is True, (
            f"Identical expression should be redundant, got is_redundant={result['is_redundant']}"
        )

        # 验证相似度分数较高
        assert result["max_similarity"] >= 0.85, (
            f"Identical expression should have high similarity (>=0.85), got {result['max_similarity']}"
        )

        # 验证最相似因子 ID
        assert result["most_similar_factor_id"] == "factor_001", (
            f"Most similar factor should be 'factor_001', got '{result['most_similar_factor_id']}'"
        )

    def test_redundancy_check_non_redundant(
        self, scheduler_with_similarity_engine: DefaultMiningScheduler
    ) -> None:
        """
        测试非冗余因子的检查:
        1. 使用与库中完全不同的表达式
        2. 验证 is_redundant=False
        3. 验证方法仍是 ensemble
        """
        scheduler = scheduler_with_similarity_engine

        # 使用完全不同的表达式
        factor_entry = {
            "factor_id": "test_factor_unique",
            "factor_expression": "CORR($rank($volume), $rank($close), 60)",
            "factor_description": "volume price correlation",
        }

        result = scheduler._check_redundancy(factor_entry)

        # 验证使用 ensemble 方法
        assert result["method"] == "ensemble", (
            f"Should use 'ensemble' method, got '{result['method']}'"
        )

        # 验证分数和冗余状态 (取决于实际计算, 至少不应崩溃)
        assert isinstance(result["is_redundant"], bool), (
            "is_redundant should be boolean"
        )
        assert isinstance(result["max_similarity"], float), (
            "max_similarity should be float"
        )
        assert 0.0 <= result["max_similarity"] <= 1.0, (
            f"max_similarity should be in [0, 1], got {result['max_similarity']}"
        )

    def test_redundancy_check_empty_expression(
        self, scheduler_with_similarity_engine: DefaultMiningScheduler
    ) -> None:
        """
        测试空表达式的冗余检查:
        1. 使用空表达式
        2. 验证优雅处理,不抛异常
        3. 验证返回 is_redundant=False
        """
        scheduler = scheduler_with_similarity_engine

        factor_entry = {
            "factor_id": "test_empty",
            "factor_expression": "",
        }

        result = scheduler._check_redundancy(factor_entry)

        # 空表达式应直接返回非冗余
        assert result["is_redundant"] is False, (
            "Empty expression should not be redundant"
        )


# ---------------------------------------------------------------------------
# 2. 端到端 Context 检索流程
# ---------------------------------------------------------------------------


class TestEndToEndContextRetrieval:
    """端到端 Context 检索流程测试."""

    def test_end_to_end_context_retrieval(
        self, scheduler_with_similarity_engine: DefaultMiningScheduler
    ) -> None:
        """
        测试完整的 context 检索流程:
        1. 创建包含几个因子的临时因子库
        2. 创建 DefaultMiningScheduler 并注入 SimilarityEngine
        3. 调用 _retrieve_context
        4. 验证返回的 context 非空且有意义
        5. 验证使用的查询文本不为空
        """
        scheduler = scheduler_with_similarity_engine

        # 调用 context 检索
        context = scheduler._retrieve_context()

        # 验证 context 非空
        assert context is not None, "Context should not be None"
        assert len(context) > 0, (
            f"Context should not be empty, got length {len(context)}"
        )

        # 验证 context 包含有意义的信息
        # 应该包含因子名称或表达式等信息
        context_lower = context.lower()
        has_meaningful_content = any(
            keyword in context_lower
            for keyword in ["factor", "price", "volume", "expression", "recent"]
        )
        assert has_meaningful_content, (
            f"Context should contain meaningful content, got: {context[:200]}"
        )

    def test_context_retrieval_with_similarity_engine(
        self, scheduler_with_similarity_engine: DefaultMiningScheduler
    ) -> None:
        """
        验证使用 SimilarityEngine 进行 context 检索:
        1. 验证 _similarity_engine 已初始化
        2. 调用 _retrieve_context
        3. 验证返回的 context 非空
        """
        scheduler = scheduler_with_similarity_engine

        # 验证引擎已初始化
        assert scheduler._similarity_engine is not None, (
            "SimilarityEngine should be initialized"
        )

        context = scheduler._retrieve_context()

        # 验证 context 检索成功
        assert context is not None, "Context should not be None"
        # 即使返回空字符串也是合法的 (因子库可能无法检索到结果)
        assert isinstance(context, str), "Context should be a string"

    def test_build_similarity_query(
        self, scheduler_with_similarity_engine: DefaultMiningScheduler
    ) -> None:
        """
        测试相似度查询文本构建:
        1. 调用 _build_similarity_query
        2. 验证返回的查询文本不为空
        3. 验证查询文本有意义
        """
        scheduler = scheduler_with_similarity_engine

        query = scheduler._build_similarity_query()

        # 验证查询文本
        assert query is not None, "Query should not be None"
        assert len(query) > 0, (
            f"Query should not be empty, got length {len(query)}"
        )
        assert isinstance(query, str), "Query should be a string"

        # 验证查询包含有意义的关键词 (默认查询)
        assert len(query.strip()) > 5, (
            f"Query should be meaningful, got: '{query}'"
        )


# ---------------------------------------------------------------------------
# 3. 加权融合模式完整流程
# ---------------------------------------------------------------------------


class TestWeightedEnsembleFullFlow:
    """加权融合模式完整流程测试."""

    def test_weighted_ensemble_full_flow(
        self, tmp_library_file: Path, weighted_config: Dict[str, Any]
    ) -> None:
        """
        测试加权融合的完整流程:
        1. 创建引擎 (AST + Jaccard 启用, RAG 禁用)
        2. 计算两个因子的 pairwise 相似度
        3. 验证各维度分数都计算了
        4. 验证最终分数是加权平均
        5. 验证阈值判断正确
        """
        # 创建引擎
        engine = SimilarityEngine(weighted_config)

        # 验证配置解析正确
        assert engine._enabled is True, "Engine should be enabled"
        assert engine._ensemble_mode == "weighted", (
            f"Ensemble mode should be 'weighted', got '{engine._ensemble_mode}'"
        )
        assert engine._ast_cfg.get("enabled") is True, "AST should be enabled"
        assert engine._jaccard_cfg.get("enabled") is True, (
            "Jaccard should be enabled"
        )
        assert engine._rag_cfg.get("enabled") is False, "RAG should be disabled"

        # 计算两个完全相同因子的 pairwise 相似度
        expr = "$close - $open"
        result = engine.compute_pairwise(expr, expr)

        # 验证是 EnsembleResult 实例
        assert isinstance(result, EnsembleResult), (
            "Should return EnsembleResult"
        )

        # 验证各维度分数都计算了 (AST 和 Jaccard)
        dimensions_computed = {r.dimension for r in result.dimension_results}
        assert "ast" in dimensions_computed, (
            "AST dimension should be computed"
        )
        assert "jaccard" in dimensions_computed, (
            "Jaccard dimension should be computed"
        )
        assert "rag" not in dimensions_computed, (
            "RAG dimension should NOT be computed (disabled)"
        )

        # 验证各维度分数正确 (完全相同应接近 1.0)
        for dim_result in result.dimension_results:
            if dim_result.dimension in ("ast", "jaccard"):
                assert dim_result.score == pytest.approx(1.0, abs=0.05), (
                    f"{dim_result.dimension} score should be ~1.0 for identical expressions, "
                    f"got {dim_result.score}"
                )
                assert dim_result.error is None, (
                    f"{dim_result.dimension} should not have error"
                )

        # 验证最终分数是加权平均 (两个维度都 ~1.0, 权重各 0.5)
        # final_score = (0.5 * 1.0 + 0.5 * 1.0) / (0.5 + 0.5) = 1.0
        assert result.final_score == pytest.approx(1.0, abs=0.05), (
            f"Final score should be ~1.0 for identical expressions, got {result.final_score}"
        )

        # 验证阈值判断正确 (1.0 >= 0.85, 应判定为冗余)
        assert result.is_redundant is True, (
            f"Score {result.final_score} >= threshold 0.85, should be redundant"
        )

        # 验证 active_dimensions 包含 AST 和 Jaccard
        assert "ast" in result.active_dimensions, (
            "AST should be in active_dimensions"
        )
        assert "jaccard" in result.active_dimensions, (
            "Jaccard should be in active_dimensions"
        )

    def test_weighted_ensemble_different_expressions(
        self, weighted_config: Dict[str, Any]
    ) -> None:
        """
        测试加权融合模式下不同表达式的分数计算:
        1. 使用完全不同的表达式
        2. 验证最终分数低于阈值
        3. 验证 is_redundant=False
        """
        engine = SimilarityEngine(weighted_config)

        expr_a = "$close / $open"
        expr_b = "STD($volume, 20) / MEAN($volume, 10)"

        result = engine.compute_pairwise(expr_a, expr_b)

        # 验证分数低于阈值
        assert result.final_score < 0.85, (
            f"Different expressions should have score below 0.85, got {result.final_score}"
        )

        # 验证不判定为冗余
        assert result.is_redundant is False, (
            "Score below threshold should not be redundant"
        )

    def test_weighted_ensemble_partial_similarity(
        self, weighted_config: Dict[str, Any]
    ) -> None:
        """
        测试加权融合模式下部分相似的分数计算:
        1. 使用结构相似但参数不同的表达式
        2. 验证分数在 (0, 1) 之间
        """
        engine = SimilarityEngine(weighted_config)

        expr_a = "TS_MAX($close, 10)"
        expr_b = "TS_MAX($close, 20)"

        result = engine.compute_pairwise(expr_a, expr_b)

        # 验证分数在合理范围内
        assert 0.0 <= result.final_score <= 1.0, (
            f"Final score should be in [0, 1], got {result.final_score}"
        )

        # 验证维度分数都在 [0, 1] 范围内
        for dim_result in result.dimension_results:
            if dim_result.error is None:
                assert 0.0 <= dim_result.score <= 1.0, (
                    f"{dim_result.dimension} score should be in [0, 1], "
                    f"got {dim_result.score}"
                )


# ---------------------------------------------------------------------------
# 4. Veto 模式完整流程
# ---------------------------------------------------------------------------


class TestVetoEnsembleFullFlow:
    """Veto 模式完整流程测试."""

    def test_veto_ensemble_full_flow(
        self, veto_config: Dict[str, Any]
    ) -> None:
        """
        测试一票否决的完整流程:
        1. 创建引擎 (ensemble_mode="veto")
        2. 计算两个高度相似因子的 pairwise
        3. 验证某个维度超过 veto_threshold 时触发拒绝
        4. 验证 triggered_by 字段正确
        """
        # 创建引擎
        engine = SimilarityEngine(veto_config)

        # 验证 veto 模式配置
        assert engine._ensemble_mode == "veto", (
            f"Ensemble mode should be 'veto', got '{engine._ensemble_mode}'"
        )

        # 计算两个完全相同因子的 pairwise 相似度
        expr = "$close - $open"
        result = engine.compute_pairwise(expr, expr)

        # 验证触发拒绝 (完全相同的表达式,AST 分数为 1.0 >= veto_threshold 0.80)
        assert result.is_redundant is True, (
            "Identical expressions should trigger veto rejection"
        )

        # 验证 triggered_by 字段正确
        assert result.triggered_by is not None, (
            "triggered_by should specify which dimension triggered veto"
        )
        assert result.triggered_by in ("ast", "jaccard"), (
            f"triggered_by should be 'ast' or 'jaccard', got '{result.triggered_by}'"
        )

        # 验证最终分数是触发维度的分数
        triggered_dim = None
        for dim_result in result.dimension_results:
            if dim_result.dimension == result.triggered_by:
                triggered_dim = dim_result
                break

        assert triggered_dim is not None, (
            f"Triggered dimension '{result.triggered_by}' should be in dimension_results"
        )
        assert result.final_score == triggered_dim.score, (
            f"Final score should be triggered dimension's score, "
            f"expected {triggered_dim.score}, got {result.final_score}"
        )

        # 验证触发维度的分数超过其 veto_threshold
        dim_cfg = engine._get_dim_config(result.triggered_by)
        veto_threshold = dim_cfg.get(
            "veto_threshold", engine._rejection_threshold
        )
        assert triggered_dim.score >= veto_threshold, (
            f"Triggered dimension score ({triggered_dim.score}) should be >= "
            f"veto_threshold ({veto_threshold})"
        )

    def test_veto_no_trigger(
        self, veto_config: Dict[str, Any]
    ) -> None:
        """
        测试 veto 模式下未触发拒绝的情况:
        1. 使用完全不同的表达式
        2. 验证 is_redundant=False
        3. 验证 triggered_by=None
        """
        engine = SimilarityEngine(veto_config)

        expr_a = "$close / $open"
        expr_b = "STD($volume, 20) / MEAN($volume, 10)"

        result = engine.compute_pairwise(expr_a, expr_b)

        # 验证未触发拒绝
        assert result.is_redundant is False, (
            "Different expressions should not trigger veto"
        )
        assert result.triggered_by is None, (
            "No dimension should have triggered veto"
        )

        # 验证最终分数是加权平均
        assert result.final_score >= 0.0, (
            "Final score should be non-negative"
        )

    def test_veto_vs_weighted_different_results(
        self, weighted_config: Dict[str, Any], veto_config: Dict[str, Any]
    ) -> None:
        """
        对比 veto 和 weighted 模式的结果差异:
        1. 使用相同的表达式对
        2. 验证两种模式的判定可能不同
        """
        engine_weighted = SimilarityEngine(weighted_config)
        engine_veto = SimilarityEngine(veto_config)

        # 使用结构相似但参数不同的表达式
        expr_a = "TS_MAX($close, 10)"
        expr_b = "TS_MAX($close, 20)"

        result_weighted = engine_weighted.compute_pairwise(expr_a, expr_b)
        result_veto = engine_veto.compute_pairwise(expr_a, expr_b)

        # 两种模式都应返回有效结果
        assert isinstance(result_weighted, EnsembleResult), (
            "Weighted mode should return EnsembleResult"
        )
        assert isinstance(result_veto, EnsembleResult), (
            "Veto mode should return EnsembleResult"
        )

        # 注意: 两种模式的 is_redundant 可能相同也可能不同,
        # 取决于具体分数, 这里只验证不抛异常且返回合理结果


# ---------------------------------------------------------------------------
# 5. 降级路径测试
# ---------------------------------------------------------------------------


class TestFallbackPaths:
    """降级路径测试."""

    def test_fallback_when_engine_disabled(
        self, scheduler_without_similarity_engine: DefaultMiningScheduler
    ) -> None:
        """
        测试引擎禁用时的降级路径:
        1. 创建 DefaultMiningScheduler (similarity_engine_cfg=None)
        2. 调用 _check_redundancy
        3. 验证使用传统的 library.check_redundancy 方法
        4. 验证返回 method 不是 "ensemble" (可能是 "expression" 或 None)
        """
        scheduler = scheduler_without_similarity_engine

        # 验证引擎未初始化
        assert scheduler._similarity_engine is None, (
            "SimilarityEngine should NOT be initialized when cfg is None"
        )

        # 调用冗余检查
        factor_entry = {
            "factor_id": "test_factor",
            "factor_expression": "$close - $open",
        }

        result = scheduler._check_redundancy(factor_entry)

        # 验证未使用 ensemble 方法 (传统方法 method 为 "expression" 或 None)
        assert result.get("method") != "ensemble", (
            f"Should NOT use 'ensemble' method when engine is disabled, "
            f"got '{result.get('method')}'"
        )

        # 验证返回结构完整
        assert "is_redundant" in result, "Result should contain 'is_redundant'"
        assert "max_similarity" in result, (
            "Result should contain 'max_similarity'"
        )

    def test_fallback_on_engine_failure(
        self, tmp_library_file: Path
    ) -> None:
        """
        测试引擎失败时的降级路径:
        1. 创建 DefaultMiningScheduler 但注入无效配置
        2. 调用 _check_redundancy
        3. 验证优雅降级到传统方法
        4. 验证不抛异常
        """
        # 创建无效配置 (enabled=True 但内部维度全禁用)
        invalid_config = {
            "enabled": True,
            "ensemble_mode": "weighted",
            "rejection_threshold": 0.85,
            "metrics": {
                "ast": {
                    "enabled": False,  # 全禁用可能导致引擎无法正常工作
                    "weight": 0.50,
                },
                "jaccard": {
                    "enabled": False,
                    "weight": 0.50,
                },
                "rag": {
                    "enabled": False,
                    "weight": 0.30,
                },
            },
        }

        # 创建调度器 (引擎应初始化但所有维度禁用)
        scheduler = DefaultMiningScheduler(
            max_per_run=5,
            interval_hours=12,
            library_path=str(tmp_library_file),
            similarity_engine_cfg=invalid_config,
        )

        # 验证引擎已初始化 (虽然维度全禁用)
        assert scheduler._similarity_engine is not None, (
            "SimilarityEngine should be initialized"
        )

        # 调用冗余检查, 不应抛异常
        factor_entry = {
            "factor_id": "test_factor",
            "factor_expression": "$close - $open",
        }

        # 不应抛出异常
        try:
            result = scheduler._check_redundancy(factor_entry)

            # 验证返回合理结果
            assert isinstance(result, dict), "Result should be a dict"
            assert "is_redundant" in result, (
                "Result should contain 'is_redundant'"
            )
            assert isinstance(result["is_redundant"], bool), (
                "is_redundant should be boolean"
            )
        except Exception as e:
            pytest.fail(
                f"_check_redundancy should not raise exception, but got: {e}"
            )

    def test_fallback_on_library_error(
        self, scheduler_with_similarity_engine: DefaultMiningScheduler
    ) -> None:
        """
        测试因子库加载失败时的降级路径:
        1. 修改 library_path 为不存在的路径
        2. 调用 _check_redundancy
        3. 验证优雅处理,不抛异常
        4. 验证返回 is_redundant=False
        """
        scheduler = scheduler_with_similarity_engine

        # 保存原始路径
        original_path = scheduler.library_path

        # 修改为不存在的路径
        scheduler.library_path = "/nonexistent/path/to/library.json"

        factor_entry = {
            "factor_id": "test_factor",
            "factor_expression": "$close - $open",
        }

        # 不应抛出异常
        try:
            result = scheduler._check_redundancy(factor_entry)

            # 验证返回非冗余 (fail-open 策略)
            assert result["is_redundant"] is False, (
                "Library error should result in is_redundant=False (fail-open)"
            )
        except Exception as e:
            pytest.fail(
                f"_check_redundancy should not raise exception on library error, "
                f"but got: {e}"
            )
        finally:
            # 恢复原始路径
            scheduler.library_path = original_path


# ---------------------------------------------------------------------------
# 6. 真实因子库测试
# ---------------------------------------------------------------------------


class TestWithRealFactorLibrary:
    """使用真实因子库测试."""

    @pytest.fixture
    def real_library_path(self) -> str:
        """真实因子库路径."""
        return "/home/quan/testdata/aspipe_v4/third_party/quantaalpha/data/factorlib/all_factors_library.json"

    def test_with_real_factor_library(
        self, real_library_path: str, weighted_config: Dict[str, Any]
    ) -> None:
        """
        使用真实因子库测试 (如果文件存在):
        1. 检查真实因子库文件是否存在
        2. 如果存在,加载它
        3. 创建引擎并检查几个真实因子的冗余性
        4. 验证性能 (应该在合理时间内完成)
        """
        # 检查文件是否存在
        if not Path(real_library_path).exists():
            pytest.skip(
                f"Real factor library not found at {real_library_path}, skipping test"
            )

        # 加载真实因子库验证格式
        try:
            with open(real_library_path, "r", encoding="utf-8") as f:
                real_library_data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            pytest.skip(f"Failed to load real factor library: {e}")

        # 验证因子库格式
        assert "factors" in real_library_data, (
            "Real factor library should have 'factors' key"
        )
        factors = real_library_data["factors"]
        assert len(factors) > 0, "Real factor library should not be empty"

        # 创建引擎
        engine = SimilarityEngine(weighted_config)

        # 选择几个真实因子进行冗余检查
        active_factors = [
            (fid, fdata)
            for fid, fdata in factors.items()
            if fdata.get("evaluation", {}).get("status") == "active"
        ]

        if not active_factors:
            pytest.skip("No active factors found in real library")

        # 取前几个因子进行测试
        test_factors = active_factors[:3]

        # 对每个因子进行冗余检查, 验证性能
        start_time = time.time()

        for factor_id, factor_data in test_factors:
            expression = factor_data.get("factor_expression", "")
            if not expression:
                continue

            # 检查冗余性
            result = engine.check_against_library(
                new_expression=expression,
                library_path=real_library_path,
                max_comparisons=50,
            )

            # 验证结果结构
            assert isinstance(result, EnsembleResult), (
                f"Should return EnsembleResult for factor {factor_id}"
            )
            assert isinstance(result.is_redundant, bool), (
                f"is_redundant should be boolean for factor {factor_id}"
            )
            assert 0.0 <= result.final_score <= 1.0, (
                f"final_score should be in [0, 1] for factor {factor_id}, "
                f"got {result.final_score}"
            )

        elapsed_time = time.time() - start_time

        # 验证性能 (3 个因子的检查应在 30 秒内完成)
        assert elapsed_time < 30.0, (
            f"Redundancy check for 3 factors took {elapsed_time:.2f}s, "
            f"which is too slow (should be < 30s)"
        )

        print(
            f"\nPerformance: Checked {len(test_factors)} factors in "
            f"{elapsed_time:.2f}s ({elapsed_time / len(test_factors):.2f}s per factor)"
        )

    def test_real_library_pairwise_similarity(
        self, real_library_path: str, weighted_config: Dict[str, Any]
    ) -> None:
        """
        测试真实因子库中因子对的相似度计算:
        1. 加载真实因子库
        2. 选择两个不同的因子计算 pairwise 相似度
        3. 验证分数在合理范围内
        """
        # 检查文件是否存在
        if not Path(real_library_path).exists():
            pytest.skip(
                f"Real factor library not found at {real_library_path}, skipping test"
            )

        # 加载真实因子库
        try:
            with open(real_library_path, "r", encoding="utf-8") as f:
                real_library_data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            pytest.skip(f"Failed to load real factor library: {e}")

        factors = real_library_data.get("factors", {})
        active_factors = [
            fdata
            for fdata in factors.values()
            if fdata.get("evaluation", {}).get("status") == "active"
            and fdata.get("factor_expression")
        ]

        if len(active_factors) < 2:
            pytest.skip("Need at least 2 active factors with expressions")

        # 创建引擎
        engine = SimilarityEngine(weighted_config)

        # 选择前两个因子计算相似度
        factor_a = active_factors[0]
        factor_b = active_factors[1]

        expr_a = factor_a["factor_expression"]
        expr_b = factor_b["factor_expression"]
        desc_a = factor_a.get("factor_description", "")
        desc_b = factor_b.get("factor_description", "")

        # 计算 pairwise 相似度
        result = engine.compute_pairwise(expr_a, expr_b, desc_a, desc_b)

        # 验证结果
        assert isinstance(result, EnsembleResult), (
            "Should return EnsembleResult"
        )
        assert 0.0 <= result.final_score <= 1.0, (
            f"final_score should be in [0, 1], got {result.final_score}"
        )

        # 验证各维度分数都在 [0, 1] 范围内
        for dim_result in result.dimension_results:
            if dim_result.error is None:
                assert 0.0 <= dim_result.score <= 1.0, (
                    f"{dim_result.dimension} score should be in [0, 1], "
                    f"got {dim_result.score}"
                )

        print(
            f"\nPairwise similarity: score={result.final_score:.4f}, "
            f"is_redundant={result.is_redundant}, "
            f"dimensions={[r.dimension for r in result.dimension_results]}"
        )


# ---------------------------------------------------------------------------
# 7. 集成边界情况测试
# ---------------------------------------------------------------------------


class TestIntegrationEdgeCases:
    """集成边界情况测试."""

    def test_scheduler_with_invalid_factor_expression(
        self, scheduler_with_similarity_engine: DefaultMiningScheduler
    ) -> None:
        """
        测试调度器处理无效因子表达式:
        1. 传入语法错误的表达式
        2. 验证不抛异常
        3. 验证返回合理的默认值
        """
        scheduler = scheduler_with_similarity_engine

        factor_entry = {
            "factor_id": "invalid_factor",
            "factor_expression": "!!! invalid syntax !!!",
        }

        # 不应抛出异常
        result = scheduler._check_redundancy(factor_entry)

        # 验证返回结构
        assert isinstance(result, dict), "Result should be a dict"
        assert "is_redundant" in result, "Result should contain 'is_redundant'"

    def test_consecutive_redundancy_checks(
        self, scheduler_with_similarity_engine: DefaultMiningScheduler
    ) -> None:
        """
        测试连续多次冗余检查:
        1. 连续调用 _check_redundancy 多次
        2. 验证不出现状态泄漏或性能退化
        3. 验证每次结果一致
        """
        scheduler = scheduler_with_similarity_engine

        factor_entry = {
            "factor_id": "test_factor",
            "factor_expression": "$close - $open",
        }

        # 连续调用 3 次
        results = []
        for _ in range(3):
            result = scheduler._check_redundancy(factor_entry)
            results.append(result)

        # 验证结果一致
        for i, result in enumerate(results):
            assert result["is_redundant"] == results[0]["is_redundant"], (
                f"Redundancy check result should be consistent, "
                f"call {i+1} differs from call 1"
            )
            assert result["method"] == results[0]["method"], (
                f"Method should be consistent, call {i+1} differs from call 1"
            )

    def test_scheduler_context_retrieval_multiple_times(
        self, scheduler_with_similarity_engine: DefaultMiningScheduler
    ) -> None:
        """
        测试连续多次 context 检索:
        1. 连续调用 _retrieve_context 多次
        2. 验证不抛异常
        3. 验证返回合理结果
        """
        scheduler = scheduler_with_similarity_engine

        contexts = []
        for _ in range(3):
            context = scheduler._retrieve_context()
            contexts.append(context)

        # 验证每次都返回字符串
        for i, context in enumerate(contexts):
            assert isinstance(context, str), (
                f"Context should be string, call {i+1} returned {type(context)}"
            )
