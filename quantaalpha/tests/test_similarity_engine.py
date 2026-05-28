"""
SimilarityEngine 单元测试.

测试覆盖:
- AST 维度相似度计算
- Jaccard 维度相似度计算
- RAG 维度相似度计算
- 融合逻辑 (weighted / veto 模式)
- check_against_library 功能
- query_similar_factors 功能
- 配置相关测试
"""

import json
import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest

from quantaalpha.factors.similarity_engine import (
    EnsembleResult,
    SimilarityEngine,
    SimilarityResult,
    compute_expression_similarity,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def minimal_config() -> Dict[str, Any]:
    """最简配置: 仅启用 AST 和 Jaccard."""
    return {
        "enabled": True,
        "ensemble_mode": "weighted",
        "rejection_threshold": 0.85,
        "metrics": {
            "ast": {
                "enabled": True,
                "weight": 0.50,
                "veto_threshold": 0.80,
            },
            "jaccard": {
                "enabled": True,
                "weight": 0.50,
                "veto_threshold": 0.95,
            },
            "rag": {
                "enabled": False,
                "weight": 0.30,
                "veto_threshold": 0.90,
            },
        },
    }


@pytest.fixture
def all_enabled_config() -> Dict[str, Any]:
    """所有维度均启用的配置."""
    return {
        "enabled": True,
        "ensemble_mode": "weighted",
        "rejection_threshold": 0.85,
        "metrics": {
            "ast": {
                "enabled": True,
                "weight": 0.40,
                "veto_threshold": 0.80,
            },
            "jaccard": {
                "enabled": True,
                "weight": 0.30,
                "veto_threshold": 0.95,
            },
            "rag": {
                "enabled": True,
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
            },
            "jaccard": {
                "enabled": True,
                "weight": 0.50,
                "veto_threshold": 0.90,
            },
            "rag": {
                "enabled": False,
                "weight": 0.30,
                "veto_threshold": 0.95,
            },
        },
    }


@pytest.fixture
def all_disabled_config() -> Dict[str, Any]:
    """所有维度禁用的配置."""
    return {
        "enabled": True,
        "ensemble_mode": "weighted",
        "rejection_threshold": 0.85,
        "metrics": {
            "ast": {
                "enabled": False,
                "weight": 0.50,
                "veto_threshold": 0.80,
            },
            "jaccard": {
                "enabled": False,
                "weight": 0.50,
                "veto_threshold": 0.95,
            },
            "rag": {
                "enabled": False,
                "weight": 0.30,
                "veto_threshold": 0.90,
            },
        },
    }


@pytest.fixture
def engine(minimal_config: Dict[str, Any]) -> SimilarityEngine:
    """使用最简配置创建引擎实例."""
    return SimilarityEngine(minimal_config)


@pytest.fixture
def engine_all_enabled(all_enabled_config: Dict[str, Any]) -> SimilarityEngine:
    """使用全启用配置创建引擎实例."""
    return SimilarityEngine(all_enabled_config)


@pytest.fixture
def engine_veto(veto_config: Dict[str, Any]) -> SimilarityEngine:
    """使用 veto 配置创建引擎实例."""
    return SimilarityEngine(veto_config)


@pytest.fixture
def engine_all_disabled(all_disabled_config: Dict[str, Any]) -> SimilarityEngine:
    """使用全禁用配置创建引擎实例."""
    return SimilarityEngine(all_disabled_config)


@pytest.fixture
def sample_library_data() -> Dict[str, Any]:
    """示例因子库数据."""
    return {
        "factors": {
            "factor_001": {
                "factor_expression": "$close - $open",
                "factor_description": "price difference factor",
                "factor_name": "PriceDiff",
                "evaluation": {"status": "active"},
            },
            "factor_002": {
                "factor_expression": "$close / $open",
                "factor_description": "price ratio factor",
                "factor_name": "PriceRatio",
                "evaluation": {"status": "active"},
            },
            "factor_003": {
                "factor_expression": "STD($volume, 20) / MEAN($volume, 10)",
                "factor_description": "volume volatility factor",
                "factor_name": "VolVolatility",
                "evaluation": {"status": "active"},
            },
            "factor_004": {
                "factor_expression": "TS_MAX($high, 14) - TS_MIN($low, 14)",
                "factor_description": "price range factor",
                "factor_name": "PriceRange",
                "evaluation": {"status": "active"},
            },
            "factor_005": {
                "factor_expression": "$close - $open",
                "factor_description": "inactive factor",
                "factor_name": "InactiveFactor",
                "evaluation": {"status": "inactive"},
            },
        }
    }


@pytest.fixture
def tmp_library_file(
    tmp_path: Path, sample_library_data: Dict[str, Any]
) -> Path:
    """创建临时因子库文件."""
    library_file = tmp_path / "test_library.json"
    library_file.write_text(json.dumps(sample_library_data, ensure_ascii=False))
    return library_file


# ---------------------------------------------------------------------------
# 1. AST 维度测试
# ---------------------------------------------------------------------------


class TestASTDimension:
    """AST 维度相似度测试."""


def test_shared_expression_similarity_applies_single_skeleton_bonus() -> None:
    score, detail = compute_expression_similarity("TS_MEAN($close, 10)", "TS_MEAN($close, 20)")

    assert score >= 0.90
    assert detail["skeleton_match"] is True


def test_similarity_engine_jaccard_reports_skeleton_detail() -> None:
    engine = SimilarityEngine(
        {
            "enabled": True,
            "ensemble_mode": "weighted",
            "rejection_threshold": 0.85,
            "metrics": {
                "jaccard": {
                    "enabled": True,
                    "weight": 1.0,
                    "skeleton_bonus": True,
                    "skeleton_floor": 0.90,
                }
            },
        }
    )

    result = engine.compute_pairwise("TS_MEAN($close, 10)", "TS_MEAN($close, 20)")

    assert result.final_score >= 0.90
    assert result.dimension_results[0].raw_detail["skeleton_match"] is True

    def test_ast_identical_expressions(self, engine: SimilarityEngine) -> None:
        """完全相同的表达式, AST 分数应接近 1.0."""
        expr = "$close - $open"
        result = engine._compute_ast_score(expr, expr)

        assert result.dimension == "ast", "Dimension should be 'ast'"
        assert result.score == pytest.approx(1.0, abs=1e-6), (
            f"Identical expressions should have score 1.0, got {result.score}"
        )
        assert result.error is None, "No error expected for valid expressions"
        assert result.raw_detail["subtree_size"] > 0, (
            "Subtree size should be positive for identical expressions"
        )

    def test_ast_different_expressions(self, engine: SimilarityEngine) -> None:
        """完全不同的表达式, AST 分数应接近 0.0."""
        expr_a = "$close / $open"
        expr_b = "STD($volume, 20) / MEAN($volume, 10)"
        result = engine._compute_ast_score(expr_a, expr_b)

        assert result.dimension == "ast", "Dimension should be 'ast'"
        assert result.score == pytest.approx(0.0, abs=0.05), (
            f"Completely different expressions should have score near 0.0, got {result.score}"
        )
        assert result.error is None, "No error expected for valid expressions"

    def test_ast_similar_parameters(self, engine: SimilarityEngine) -> None:
        """结构相同但参数不同的表达式, AST 分数应在 (0, 1) 之间."""
        expr_a = "TS_MAX($close, 10)"
        expr_b = "TS_MAX($close, 20)"
        result = engine._compute_ast_score(expr_a, expr_b)

        assert result.dimension == "ast", "Dimension should be 'ast'"
        assert 0.0 < result.score < 1.0, (
            f"Similar structure with different params should have 0 < score < 1, got {result.score}"
        )
        assert result.error is None, "No error expected for valid expressions"
        # 结构相似, subtree_size 应该大于 0
        assert result.raw_detail["subtree_size"] > 0, (
            "Should have common subtree for similar expressions"
        )

    def test_ast_error_handling(self, engine: SimilarityEngine) -> None:
        """无效表达式应返回 error 而不是抛异常."""
        invalid_expr = "!!! invalid expression !!!"
        valid_expr = "$close + $open"

        # 不应抛出异常
        result = engine._compute_ast_score(invalid_expr, valid_expr)

        assert result.dimension == "ast", "Dimension should be 'ast'"
        # AST 解析失败时 error 不为 None
        assert result.error is not None, (
            "Invalid expression should have error message"
        )
        assert result.score == 0.0, (
            "Failed AST computation should return score 0.0"
        )


# ---------------------------------------------------------------------------
# 2. Jaccard 维度测试
# ---------------------------------------------------------------------------


class TestJaccardDimension:
    """Jaccard 维度相似度测试."""

    def test_jaccard_identical(self, engine: SimilarityEngine) -> None:
        """完全相同文本, Jaccard 分数应为 1.0."""
        text = "$close - $open"
        result = engine._compute_jaccard_score(text, text)

        assert result.dimension == "jaccard", "Dimension should be 'jaccard'"
        assert result.score == pytest.approx(1.0, abs=1e-6), (
            f"Identical text should have score 1.0, got {result.score}"
        )
        assert result.error is None, "No error expected"

    def test_jaccard_completely_different(self, engine: SimilarityEngine) -> None:
        """完全不同文本, Jaccard 分数应为 0.0."""
        text_a = "alpha beta gamma"
        text_b = "xyz uvw qrs"
        result = engine._compute_jaccard_score(text_a, text_b)

        assert result.dimension == "jaccard", "Dimension should be 'jaccard'"
        assert result.score == pytest.approx(0.0, abs=1e-6), (
            f"Completely different text should have score 0.0, got {result.score}"
        )

    def test_jaccard_partial_match(self, engine: SimilarityEngine) -> None:
        """部分匹配的情况, Jaccard 分数应在 (0, 1) 之间."""
        text_a = "$close $open $high $low"
        text_b = "$close $open $volume"
        result = engine._compute_jaccard_score(text_a, text_b)

        assert result.dimension == "jaccard", "Dimension should be 'jaccard'"
        assert 0.0 < result.score < 1.0, (
            f"Partial match should have 0 < score < 1, got {result.score}"
        )
        # close 和 open 是共同词, 所以 intersection=2, union=5, score=0.4
        assert result.score == pytest.approx(0.4, abs=0.01), (
            f"Expected Jaccard score ~0.4, got {result.score}"
        )


# ---------------------------------------------------------------------------
# 3. RAG 维度测试
# ---------------------------------------------------------------------------


class TestRAGDimension:
    """RAG 维度相似度测试."""

    def test_rag_disabled(self, minimal_config: Dict[str, Any]) -> None:
        """RAG 禁用时, compute_pairwise 结果中不应包含 RAG 维度."""
        config = minimal_config.copy()
        config["metrics"]["rag"]["enabled"] = False
        engine = SimilarityEngine(config)

        result = engine.compute_pairwise(
            expr_a="$close - $open",
            expr_b="$close - $open",
            desc_a="price diff",
            desc_b="price diff",
        )

        # 检查 dimension_results 中没有 rag 维度
        rag_results = [
            r for r in result.dimension_results if r.dimension == "rag"
        ]
        assert len(rag_results) == 0, (
            "RAG dimension should not be present when disabled"
        )

    def test_rag_error_handling(self, engine_all_enabled: SimilarityEngine) -> None:
        """RAG 失败时不应抛异常, 应优雅降级."""
        # RAG 需要向量检索服务, 在没有服务的情况下可能会失败
        # 但引擎不应抛出未捕获异常
        try:
            result = engine_all_enabled._compute_rag_score(
                "price difference", "price difference"
            )
            # 如果成功, 分数应 >= 0
            assert result.score >= 0.0, "Score should be non-negative"
            assert result.dimension == "rag", "Dimension should be 'rag'"
        except Exception as e:
            pytest.fail(f"RAG computation should not raise exception, but got: {e}")


# ---------------------------------------------------------------------------
# 4. 融合逻辑测试
# ---------------------------------------------------------------------------


class TestWeightedEnsemble:
    """Weighted 模式融合逻辑测试."""

    def test_weighted_ensemble(self, engine: SimilarityEngine) -> None:
        """加权平均计算正确."""
        # 使用两个完全相同的表达式, AST 和 Jaccard 都应接近 1.0
        expr = "$close - $open"
        result = engine.compute_pairwise(expr, expr)

        assert result.final_score == pytest.approx(1.0, abs=0.05), (
            f"Identical expressions should have final_score ~1.0, got {result.final_score}"
        )
        assert result.is_redundant is True, (
            f"Score {result.final_score} >= threshold 0.85, should be redundant"
        )

    def test_weighted_with_failed_dimension(
        self, engine: SimilarityEngine
    ) -> None:
        """一个维度失败时动态调整权重."""
        # 一个有效表达式和一个无效表达式
        expr_a = "$close - $open"
        expr_b = "!!! invalid !!!"
        result = engine.compute_pairwise(expr_a, expr_b)

        # 不应抛出异常
        assert isinstance(result, EnsembleResult), (
            "Should return EnsembleResult even with failed dimension"
        )
        # 检查有效维度参与了计算
        valid_dims = [
            r for r in result.dimension_results if r.error is None
        ]
        assert len(valid_dims) >= 1, (
            "At least one dimension should be valid"
        )

    def test_weighted_below_threshold(self, engine: SimilarityEngine) -> None:
        """分数低于阈值, is_redundant=False."""
        # 完全不同的表达式, 分数应远低于 0.85
        expr_a = "$close / $open"
        expr_b = "STD($volume, 20) / MEAN($volume, 10)"
        result = engine.compute_pairwise(expr_a, expr_b)

        assert result.final_score < 0.85, (
            f"Different expressions should have score below 0.85, got {result.final_score}"
        )
        assert result.is_redundant is False, (
            "Score below threshold should not be redundant"
        )

    def test_weighted_above_threshold(self, engine: SimilarityEngine) -> None:
        """分数高于阈值, is_redundant=True."""
        # 完全相同的表达式
        expr = "$close - $open"
        result = engine.compute_pairwise(expr, expr)

        assert result.final_score >= 0.85, (
            f"Identical expressions should have score >= 0.85, got {result.final_score}"
        )
        assert result.is_redundant is True, (
            "Score above threshold should be redundant"
        )


class TestVetoEnsemble:
    """Veto 模式融合逻辑测试."""

    def test_veto_no_trigger(self, engine_veto: SimilarityEngine) -> None:
        """所有维度低于 veto_threshold, is_redundant=False."""
        # 不同的表达式, 各维度分数应较低
        expr_a = "$close / $open"
        expr_b = "STD($volume, 20) / MEAN($volume, 10)"
        result = engine_veto.compute_pairwise(expr_a, expr_b)

        assert result.is_redundant is False, (
            "Different expressions should not trigger veto"
        )
        assert result.triggered_by is None, (
            "No dimension should have triggered veto"
        )

    def test_veto_single_trigger(self, engine_veto: SimilarityEngine) -> None:
        """一个维度超过 veto_threshold, is_redundant=True, triggered_by 正确."""
        # 完全相同的表达式, AST 分数为 1.0 >= veto_threshold 0.80
        expr = "$close - $open"
        result = engine_veto.compute_pairwise(expr, expr)

        assert result.is_redundant is True, (
            "Identical expressions should trigger veto"
        )
        assert result.triggered_by is not None, (
            "triggered_by should specify which dimension triggered veto"
        )
        assert result.triggered_by in ("ast", "jaccard"), (
            f"triggered_by should be 'ast' or 'jaccard', got '{result.triggered_by}'"
        )

    @pytest.mark.parametrize(
        "expr_a,expr_b,expect_redundant,description",
        [
            (
                "$close - $open",
                "$close - $open",
                True,
                "identical expressions trigger veto",
            ),
            (
                "$close / $open",
                "STD($volume, 20)",
                False,
                "different expressions no trigger",
            ),
            (
                "TS_MAX($close, 10)",
                "TS_MAX($close, 20)",
                True,
                "same skeleton parameter variants trigger veto",
            ),
        ],
    )
    def test_veto_parametrized(
        self,
        engine_veto: SimilarityEngine,
        expr_a: str,
        expr_b: str,
        expect_redundant: bool,
        description: str,
    ) -> None:
        """参数化测试 veto 模式的不同输入."""
        result = engine_veto.compute_pairwise(expr_a, expr_b)

        assert result.is_redundant == expect_redundant, (
            f"{description}: expected is_redundant={expect_redundant}, got {result.is_redundant}"
        )


# ---------------------------------------------------------------------------
# 5. check_against_library 测试
# ---------------------------------------------------------------------------


class TestCheckAgainstLibrary:
    """check_against_library 功能测试."""

    def test_check_with_empty_library(
        self, engine: SimilarityEngine, tmp_path: Path
    ) -> None:
        """空库应返回 is_redundant=False."""
        empty_lib_file = tmp_path / "empty_library.json"
        empty_lib_file.write_text(json.dumps({"factors": {}}))

        result = engine.check_against_library(
            new_expression="$close - $open",
            library_path=str(empty_lib_file),
        )

        assert result.is_redundant is False, (
            "Empty library should return is_redundant=False"
        )
        assert result.final_score == 0.0, (
            "Empty library should have final_score 0.0"
        )

    def test_check_with_similar_factor(
        self, engine: SimilarityEngine, tmp_library_file: Path
    ) -> None:
        """库中有相似因子时应检测冗余."""
        # 表达式与 factor_001 完全相同
        result = engine.check_against_library(
            new_expression="$close - $open",
            library_path=str(tmp_library_file),
        )

        assert result.is_redundant is True, (
            f"Expression identical to library factor should be redundant, got score={result.final_score}"
        )
        assert result.final_score >= 0.85, (
            f"Identical expression should have high score, got {result.final_score}"
        )

    def test_respects_max_comparisons(
        self, engine: SimilarityEngine, tmp_library_file: Path
    ) -> None:
        """比较次数不超过 max_comparisons."""
        # 创建一个较大的因子库
        large_lib = {"factors": {}}
        for i in range(100):
            large_lib["factors"][f"factor_{i:03d}"] = {
                "factor_expression": f"$close - $open + {i}",
                "factor_description": f"factor {i}",
                "factor_name": f"Factor{i}",
                "evaluation": {"status": "active"},
            }

        large_lib_file = tmp_library_file.parent / "large_library.json"
        large_lib_file.write_text(json.dumps(large_lib, ensure_ascii=False))

        max_comparisons = 10
        result = engine.check_against_library(
            new_expression="$close - $open",
            library_path=str(large_lib_file),
            max_comparisons=max_comparisons,
        )

        # 验证结果返回, 无法直接获取比较次数, 但至少不应报错
        assert isinstance(result, EnsembleResult), (
            "Should return EnsembleResult"
        )


# ---------------------------------------------------------------------------
# 6. query_similar_factors 测试
# ---------------------------------------------------------------------------


class TestQuerySimilarFactors:
    """query_similar_factors 功能测试."""

    def test_query_returns_top_k(
        self, engine: SimilarityEngine, tmp_library_file: Path
    ) -> None:
        """返回数量正确."""
        top_k = 3
        results = engine.query_similar_factors(
            query="price difference close open",
            library_path=str(tmp_library_file),
            top_k=top_k,
        )

        assert isinstance(results, list), "Should return a list"
        assert len(results) <= top_k, (
            f"Should return at most {top_k} results, got {len(results)}"
        )

    def test_query_with_no_results(
        self, engine: SimilarityEngine, tmp_path: Path
    ) -> None:
        """无匹配时返回空列表."""
        empty_lib_file = tmp_path / "empty_query_lib.json"
        empty_lib_file.write_text(json.dumps({"factors": {}}))

        results = engine.query_similar_factors(
            query="some unique query xyz",
            library_path=str(empty_lib_file),
            top_k=5,
        )

        assert isinstance(results, list), "Should return a list even with no results"
        assert len(results) == 0, (
            f"Empty library should return empty list, got {len(results)} results"
        )

    def test_query_scores_sorted_descending(
        self, engine: SimilarityEngine, tmp_library_file: Path
    ) -> None:
        """分数按降序排列."""
        results = engine.query_similar_factors(
            query="price close open",
            library_path=str(tmp_library_file),
            top_k=10,
        )

        if len(results) >= 2:
            scores = [r.get("score", 0.0) for r in results]
            for i in range(len(scores) - 1):
                assert scores[i] >= scores[i + 1], (
                    f"Scores should be sorted in descending order, "
                    f"but found {scores[i]} < {scores[i + 1]} at index {i}"
                )


# ---------------------------------------------------------------------------
# 7. 配置测试
# ---------------------------------------------------------------------------


class TestConfiguration:
    """配置相关测试."""

    def test_config_all_enabled(
        self, engine_all_enabled: SimilarityEngine
    ) -> None:
        """所有维度启用时初始化正确."""
        assert engine_all_enabled._enabled is True, "Engine should be enabled"
        assert engine_all_enabled._ensemble_mode == "weighted", (
            "Ensemble mode should be 'weighted'"
        )
        assert engine_all_enabled._ast_cfg.get("enabled") is True, (
            "AST should be enabled"
        )
        assert engine_all_enabled._jaccard_cfg.get("enabled") is True, (
            "Jaccard should be enabled"
        )
        assert engine_all_enabled._rag_cfg.get("enabled") is True, (
            "RAG should be enabled"
        )

    def test_config_all_disabled(
        self, engine_all_disabled: SimilarityEngine
    ) -> None:
        """所有维度禁用时引擎仍工作 (final_score=0)."""
        result = engine_all_disabled.compute_pairwise(
            expr_a="$close - $open",
            expr_b="$close - $open",
        )

        assert result.is_redundant is False, (
            "All dimensions disabled should not be redundant"
        )
        assert result.final_score == 0.0, (
            f"All dimensions disabled should have final_score 0.0, got {result.final_score}"
        )
        assert len(result.active_dimensions) == 0, (
            "No active dimensions expected"
        )

    def test_config_veto_mode(self, veto_config: Dict[str, Any]) -> None:
        """Veto 模式配置正确解析."""
        engine = SimilarityEngine(veto_config)

        assert engine._ensemble_mode == "veto", (
            f"Ensemble mode should be 'veto', got '{engine._ensemble_mode}'"
        )
        # 检查 veto_threshold 在各维度配置中
        assert "veto_threshold" in engine._ast_cfg, (
            "AST config should have veto_threshold"
        )
        assert "veto_threshold" in engine._jaccard_cfg, (
            "Jaccard config should have veto_threshold"
        )


# ---------------------------------------------------------------------------
# Additional edge case tests
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """边界情况测试."""

    def test_engine_disabled(self, minimal_config: Dict[str, Any]) -> None:
        """引擎整体禁用时, 返回无冗余结果."""
        config = minimal_config.copy()
        config["enabled"] = False
        engine = SimilarityEngine(config)

        result = engine.compute_pairwise(
            expr_a="$close - $open",
            expr_b="$close - $open",
        )

        assert result.is_redundant is False, (
            "Disabled engine should always return is_redundant=False"
        )
        assert result.final_score == 0.0, (
            "Disabled engine should return final_score 0.0"
        )

    def test_empty_expressions(self, engine: SimilarityEngine) -> None:
        """空表达式不应导致崩溃."""
        result = engine.compute_pairwise("", "")

        assert isinstance(result, EnsembleResult), (
            "Should return EnsembleResult for empty expressions"
        )

    def test_library_file_not_found(self, engine: SimilarityEngine) -> None:
        """库文件不存在时, 不应抛异常."""
        result = engine.check_against_library(
            new_expression="$close - $open",
            library_path="/nonexistent/path/to/library.json",
        )

        assert result.is_redundant is False, (
            "Missing library file should return is_redundant=False"
        )
        assert result.final_score == 0.0, (
            "Missing library file should return final_score 0.0"
        )

    def test_library_invalid_json(self, engine: SimilarityEngine, tmp_path: Path) -> None:
        """库文件 JSON 格式无效时, 不应抛异常."""
        bad_lib_file = tmp_path / "bad_library.json"
        bad_lib_file.write_text("this is not valid json {{{")

        result = engine.check_against_library(
            new_expression="$close - $open",
            library_path=str(bad_lib_file),
        )

        assert result.is_redundant is False, (
            "Invalid JSON library should return is_redundant=False"
        )

    @pytest.mark.parametrize(
        "expr_a,expr_b",
        [
            ("$close", "$close"),
            ("$close - $open", "$close - $open"),
            ("TS_MAX($close, 10)", "TS_MAX($close, 10)"),
            ("a + b * c", "a + b * c"),
        ],
    )
    def test_identical_expressions_various(
        self, engine: SimilarityEngine, expr_a: str, expr_b: str
    ) -> None:
        """参数化测试各种完全相同的表达式."""
        result = engine.compute_pairwise(expr_a, expr_b)

        assert result.final_score >= 0.85, (
            f"Identical expressions '{expr_a}' should have high score, got {result.final_score}"
        )
        assert result.is_redundant is True, (
            f"Identical expressions '{expr_a}' should be redundant"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
