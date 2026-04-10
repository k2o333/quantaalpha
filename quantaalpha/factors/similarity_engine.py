"""
统一因子相似度引擎 (Similarity Engine).

提供多维度因子相似度计算与融合判定,支持:
- AST 结构相似度 (基于语法树最大公共子树)
- Jaccard 文本相似度 (基于 Token 集合重叠)
- RAG 语义相似度 (基于向量检索)

融合模式:
- **weighted**: 加权平均,与 rejection_threshold 比较
- **veto**: 任一维度超过 veto_threshold 即判定冗余

典型用法:
    >>> engine = SimilarityEngine(config)
    >>> result = engine.compute_pairwise(expr_a, expr_b, desc_a, desc_b)
    >>> print(result.is_redundant, result.final_score)

    >>> result = engine.check_against_library(new_expr, library_path="/path/to/library.json")
    >>> print(result.is_redundant, result.dimension_results)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------


@dataclass
class SimilarityResult:
    """单维度相似度计算结果.

    Attributes:
        dimension: 维度标识, 取值 "rag" | "ast" | "jaccard".
        score: 归一化分数 [0.0, 1.0], 越高表示越相似.
        raw_detail: 原始计算细节 (如 subtree_size, token 数量等).
        error: 错误信息, 成功时为 None.
    """

    dimension: str
    score: float
    raw_detail: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class EnsembleResult:
    """融合判定结果.

    Attributes:
        is_redundant: 是否判定为冗余因子.
        final_score: 融合后的最终分数.
        dimension_results: 各维度的原始计算结果.
        triggered_by: 触发拒绝的维度名称 (仅 veto 模式有效).
        active_dimensions: 实际参与融合的维度列表.
        comparisons_made: 实际比较的因子数量 (用于监控).
    """

    is_redundant: bool
    final_score: float
    dimension_results: List[SimilarityResult] = field(default_factory=list)
    triggered_by: Optional[str] = None
    active_dimensions: List[str] = field(default_factory=list)
    comparisons_made: int = 0


# ---------------------------------------------------------------------------
# SimilarityEngine
# ---------------------------------------------------------------------------


class SimilarityEngine:
    """统一因子相似度引擎.

    从 pipeline.yaml 的 similarity_engine 段读取配置, 支持多维度相似度
    计算与融合判定 (weighted / veto).

    配置示例::

        similarity_engine:
          enabled: true
          ensemble_mode: "weighted"
          rejection_threshold: 0.85
          metrics:
            rag:
              enabled: false
              weight: 0.30
              veto_threshold: 0.90
            ast:
              enabled: true
              weight: 0.50
              veto_threshold: 0.80
              duplication_threshold: 8
              symbol_length_threshold: 300
              base_features_threshold: 6
            jaccard:
              enabled: true
              weight: 0.20
              veto_threshold: 0.95
              skeleton_bonus: true
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """从 pipeline.yaml 的 similarity_engine 段初始化.

        Args:
            config: similarity_engine 配置字典.
        """
        self._config: Dict[str, Any] = config
        self._enabled: bool = config.get("enabled", True)
        self._ensemble_mode: str = config.get("ensemble_mode", "weighted").lower()
        self._rejection_threshold: float = config.get("rejection_threshold", 0.85)

        # 各维度子配置
        self._metrics: Dict[str, Any] = config.get("metrics", {})
        self._ast_cfg: Dict[str, Any] = self._metrics.get("ast", {})
        self._jaccard_cfg: Dict[str, Any] = self._metrics.get("jaccard", {})
        self._rag_cfg: Dict[str, Any] = self._metrics.get("rag", {})

        # 延迟导入: 避免模块级循环依赖
        self._ast_score_module = None
        self._fewshot_module = None
        self._vector_store_module = None

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def compute_pairwise(
        self,
        expr_a: str,
        expr_b: str,
        desc_a: str = "",
        desc_b: str = "",
    ) -> EnsembleResult:
        """计算两个因子之间的融合相似度.

        Args:
            expr_a: 因子 A 的表达式.
            expr_b: 因子 B 的表达式.
            desc_a: 因子 A 的描述 (用于 RAG).
            desc_b: 因子 B 的描述 (用于 RAG).

        Returns:
            EnsembleResult 包含各维度分数和融合结果.
        """
        if not self._enabled:
            logger.debug("SimilarityEngine is disabled, returning no-redundancy result")
            return EnsembleResult(
                is_redundant=False,
                final_score=0.0,
                active_dimensions=[],
            )

        results: List[SimilarityResult] = []

        # --- AST ---
        if self._ast_cfg.get("enabled", False):
            results.append(self._compute_ast_score(expr_a, expr_b))

        # --- Jaccard ---
        if self._jaccard_cfg.get("enabled", False):
            results.append(self._compute_jaccard_score(expr_a, expr_b))

        # --- RAG ---
        if self._rag_cfg.get("enabled", False):
            desc_a_effective = desc_a if desc_a else expr_a
            desc_b_effective = desc_b if desc_b else expr_b
            results.append(self._compute_rag_score(desc_a_effective, desc_b_effective))

        return self._compute_ensemble(results)

    def check_against_library(
        self,
        new_expression: str,
        library_path: str,
        max_comparisons: int = 50,
    ) -> EnsembleResult:
        """检查新因子是否与库中已有因子冗余.

        流程:
        1. 使用 `_find_top_candidates` 快速预筛选 top 候选.
        2. 对每个候选计算三个维度分数.
        3. 返回最高分的 EnsembleResult.

        Args:
            new_expression: 新因子表达式.
            library_path: 因子库 JSON 文件路径.
            max_comparisons: 最大比较次数.

        Returns:
            EnsembleResult 包含与库中最相似因子的对比结果.
        """
        library = self._load_library(library_path)
        if not library:
            logger.warning(f"Failed to load library from {library_path}")
            return EnsembleResult(
                is_redundant=False,
                final_score=0.0,
                active_dimensions=[],
            )

        # 快速预筛选候选因子
        candidates = self._find_top_candidates(
            new_expr=new_expression,
            library=library,
            top_n=max_comparisons,
        )

        if not candidates:
            logger.info("No candidates found in library")
            return EnsembleResult(
                is_redundant=False,
                final_score=0.0,
                active_dimensions=[],
            )

        # 对每个候选计算融合分数
        best_result: Optional[EnsembleResult] = None
        best_score = -1.0

        comparisons_made = 0
        for factor_id, factor_entry in candidates:
            expr_b = factor_entry.get("factor_expression", "")
            desc_b = factor_entry.get("factor_description", "")

            result = self.compute_pairwise(
                expr_a=new_expression,
                expr_b=expr_b,
                desc_b=desc_b,
            )

            comparisons_made += 1

            if result.final_score > best_score:
                best_score = result.final_score
                best_result = result
                # 在 raw_detail 中记录最相似因子 ID
                for dr in best_result.dimension_results:
                    dr.raw_detail["most_similar_factor_id"] = factor_id
                    dr.raw_detail["most_similar_factor_name"] = factor_entry.get(
                        "factor_name", ""
                    )

        if best_result is None:
            return EnsembleResult(
                is_redundant=False,
                final_score=0.0,
                active_dimensions=[],
                comparisons_made=0,
            )

        best_result.comparisons_made = comparisons_made
        logger.info(
            f"check_against_library: {comparisons_made} comparisons, "
            f"best_score={best_score:.4f}, is_redundant={best_result.is_redundant}"
        )
        return best_result

    def query_similar_factors(
        self,
        query: str,
        library_path: str,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """检索语义最相似的因子 (用于 Few-Shot context).

        如果 RAG 已启用则优先使用向量检索, 否则回退到 Jaccard.

        Args:
            query: 查询文本.
            library_path: 因子库路径.
            top_k: 返回数量.

        Returns:
            相似因子列表, 每个包含 score 和因子信息.
        """
        rag_enabled = self._rag_cfg.get("enabled", False)

        if rag_enabled:
            return self._query_similar_factors_rag(query, library_path, top_k)
        else:
            return self._query_similar_factors_jaccard(query, library_path, top_k)

    # -----------------------------------------------------------------------
    # Internal: Per-dimension score computation
    # -----------------------------------------------------------------------

    def _compute_ast_score(self, expr_a: str, expr_b: str) -> SimilarityResult:
        """计算 AST 维度相似度.

        调用 `ast_score.compute_ast_score()` 获取结果.
        """
        mod = self._import_ast_score()
        if mod is None:
            return SimilarityResult(
                dimension="ast",
                score=0.0,
                error="ast_score module not available",
            )

        try:
            result = mod.compute_ast_score(expr_a, expr_b)
            return SimilarityResult(
                dimension="ast",
                score=result.score,
                raw_detail={
                    "subtree_size": result.subtree_size,
                    "nodes_a": result.nodes_a,
                    "nodes_b": result.nodes_b,
                },
                error=result.error,
            )
        except Exception as e:
            logger.warning(f"AST score computation failed: {e}")
            return SimilarityResult(
                dimension="ast",
                score=0.0,
                error=str(e),
            )

    def _compute_jaccard_score(self, expr_a: str, expr_b: str) -> SimilarityResult:
        """计算 Jaccard 维度相似度.

        使用 `fewshot.compute_jaccard_similarity()`.
        """
        mod = self._import_fewshot()
        if mod is None:
            return SimilarityResult(
                dimension="jaccard",
                score=0.0,
                error="fewshot module not available",
            )

        try:
            score = mod.compute_jaccard_similarity(expr_a, expr_b)
            return SimilarityResult(
                dimension="jaccard",
                score=score,
                raw_detail={"method": "jaccard_token_overlap"},
            )
        except Exception as e:
            logger.warning(f"Jaccard score computation failed: {e}")
            return SimilarityResult(
                dimension="jaccard",
                score=0.0,
                error=str(e),
            )

    def _compute_rag_score(self, desc_a: str, desc_b: str) -> SimilarityResult:
        """计算 RAG 维度相似度 (基于描述).

        使用 desc_a 作为 query, 在 desc_b 的上下文中检索, 取最高分
        并做归一化: `min(1.0, max_score * 1.1)`.
        """
        try:
            from quantaalpha.factors.fewshot import query_active_factors_RAG
        except ImportError:
            try:
                from .fewshot import query_active_factors_RAG
            except ImportError:
                return SimilarityResult(
                    dimension="rag",
                    score=0.0,
                    error="fewshot.query_active_factors_RAG not available",
                )

        if not desc_a and not desc_b:
            return SimilarityResult(
                dimension="rag",
                score=0.0,
                error="Both descriptions are empty",
            )

        try:
            # 使用 desc_a 作为 query, 检索活跃因子
            results = query_active_factors_RAG(
                query=desc_a,
                top_k=10,
                min_score=0.0,
                use_vector=True,
                fallback_to_jaccard=True,
            )

            if not results:
                return SimilarityResult(
                    dimension="rag",
                    score=0.0,
                    raw_detail={"query": desc_a[:100], "results_count": 0},
                    error="No RAG results returned",
                )

            # 取最高分并归一化
            max_score = max(r.get("score", 0.0) for r in results)
            normalized_score = min(1.0, max_score * 1.1)

            return SimilarityResult(
                dimension="rag",
                score=normalized_score,
                raw_detail={
                    "raw_max_score": max_score,
                    "normalization_factor": 1.1,
                    "results_count": len(results),
                    "query": desc_a[:100],
                },
            )
        except Exception as e:
            logger.warning(f"RAG score computation failed: {e}")
            return SimilarityResult(
                dimension="rag",
                score=0.0,
                error=str(e),
            )

    # -----------------------------------------------------------------------
    # Internal: Ensemble fusion
    # -----------------------------------------------------------------------

    def _compute_ensemble(self, results: List[SimilarityResult]) -> EnsembleResult:
        """融合各维度分数 (weighted 或 veto 模式).

        自动跳过 error is not None 的维度.
        """
        # 过滤掉有错误的维度
        valid_results = [r for r in results if r.error is None]
        active_dimensions = [r.dimension for r in valid_results]

        if not valid_results:
            logger.warning(
                "All dimensions failed or disabled, returning zero-score ensemble"
            )
            return EnsembleResult(
                is_redundant=False,
                final_score=0.0,
                dimension_results=results,
                active_dimensions=[],
            )

        # --- veto 模式 ---
        if self._ensemble_mode == "veto":
            for r in valid_results:
                dim_cfg = self._get_dim_config(r.dimension)
                veto_threshold = dim_cfg.get("veto_threshold", self._rejection_threshold)
                if r.score >= veto_threshold:
                    logger.info(
                        f"Veto triggered by dimension '{r.dimension}' "
                        f"(score={r.score:.4f} >= threshold={veto_threshold})"
                    )
                    return EnsembleResult(
                        is_redundant=True,
                        final_score=r.score,
                        dimension_results=results,
                        triggered_by=r.dimension,
                        active_dimensions=active_dimensions,
                    )

            # 未触发 veto, 使用加权平均作为最终分数
            final_score = self._weighted_average(valid_results)
            return EnsembleResult(
                is_redundant=False,
                final_score=final_score,
                dimension_results=results,
                active_dimensions=active_dimensions,
            )

        # --- weighted 模式 (默认) ---
        final_score = self._weighted_average(valid_results)
        is_redundant = final_score >= self._rejection_threshold

        if is_redundant:
            logger.info(
                f"Weighted ensemble: final_score={final_score:.4f} >= "
                f"rejection_threshold={self._rejection_threshold}, is_redundant=True"
            )

        return EnsembleResult(
            is_redundant=is_redundant,
            final_score=final_score,
            dimension_results=results,
            active_dimensions=active_dimensions,
        )

    def _weighted_average(self, results: List[SimilarityResult]) -> float:
        """计算加权平均分.

        final_score = sum(w * r.score) / sum(w) for valid results.
        """
        total_weight = 0.0
        weighted_sum = 0.0

        for r in results:
            dim_cfg = self._get_dim_config(r.dimension)
            weight = dim_cfg.get("weight", 1.0)
            weighted_sum += weight * r.score
            total_weight += weight

        if total_weight == 0:
            return 0.0

        return weighted_sum / total_weight

    # -----------------------------------------------------------------------
    # Internal: Library operations
    # -----------------------------------------------------------------------

    def _load_library(self, library_path: str) -> Dict[str, Any]:
        """加载因子库 JSON 文件.

        Returns:
            解析后的 JSON 数据, 失败返回空字典.
        """
        path = Path(library_path)
        if not path.exists():
            logger.error(f"Library file not found: {library_path}")
            return {}

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Failed to load library from {library_path}: {e}")
            return {}

    def _find_top_candidates(
        self,
        new_expr: str,
        library: Dict[str, Any],
        top_n: int,
    ) -> List[Tuple[str, Dict[str, Any]]]:
        """快速预筛选候选因子.

        使用简单 Jaccard 对库中 active 因子排序, 取 top_n 个用于后续详细计算.

        Args:
            new_expr: 新因子表达式.
            library: 因子库 JSON 数据.
            top_n: 返回候选数量.

        Returns:
            [(factor_id, factor_entry), ...] 按 Jaccard 分数降序排列.
        """
        try:
            from quantaalpha.factors.fewshot import compute_jaccard_similarity
        except ImportError:
            try:
                from .fewshot import compute_jaccard_similarity
            except ImportError:
                logger.warning("fewshot module not available, using identity scoring")
                compute_jaccard_similarity = lambda a, b: 1.0  # noqa: E731

        factors = library.get("factors", {})
        scored: List[Tuple[str, Dict[str, Any], float]] = []

        for factor_id, factor_entry in factors.items():
            # 只比较 active 状态的因子
            status = factor_entry.get("evaluation", {}).get("status", "")
            if status != "active":
                continue

            expr_b = factor_entry.get("factor_expression", "")
            if not expr_b:
                continue

            try:
                score = compute_jaccard_similarity(new_expr, expr_b)
            except Exception as e:
                logger.debug(f"Jaccard failed for {factor_id}: {e}")
                score = 0.0

            scored.append((factor_id, factor_entry, score))

        # 按分数降序排列, 取 top_n
        scored.sort(key=lambda x: x[2], reverse=True)
        top_candidates = scored[:top_n]

        logger.debug(
            f"Pre-filtered {len(factors)} factors -> {len(top_candidates)} candidates "
            f"(top Jaccard score: {top_candidates[0][2]:.4f})"
            if top_candidates
            else "Pre-filtered: no candidates found"
        )

        return [(fid, entry) for fid, entry, _score in top_candidates]

    # -----------------------------------------------------------------------
    # Internal: RAG-based query
    # -----------------------------------------------------------------------

    def _query_similar_factors_rag(
        self,
        query: str,
        library_path: str,
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """使用 RAG 向量检索相似因子."""
        try:
            from quantaalpha.factors.fewshot import query_active_factors_RAG
        except ImportError:
            try:
                from .fewshot import query_active_factors_RAG
            except ImportError:
                logger.warning("fewshot module not available for RAG query")
                return []

        try:
            results = query_active_factors_RAG(
                query=query,
                top_k=top_k,
                min_score=0.0,
                library_path=library_path,
                use_vector=True,
                fallback_to_jaccard=True,
            )
            return results
        except Exception as e:
            logger.error(f"RAG query failed: {e}")
            # 回退到 Jaccard
            return self._query_similar_factors_jaccard(query, library_path, top_k)

    def _query_similar_factors_jaccard(
        self,
        query: str,
        library_path: str,
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """使用 AST/Jaccard 回退方法检索相似因子."""
        try:
            from quantaalpha.factors.fewshot import query_active_factors_ast, query_active_factors_jaccard
        except ImportError:
            try:
                from .fewshot import query_active_factors_ast, query_active_factors_jaccard
            except ImportError:
                logger.warning("fewshot module not available for AST/Jaccard query")
                return []

        if self._ast_cfg.get("enabled", False):
            try:
                ast_results = query_active_factors_ast(
                    query=query,
                    top_k=top_k,
                    min_score=0.0,
                    library_path=library_path,
                )
                if ast_results:
                    return ast_results
            except Exception as e:
                logger.error(f"AST query failed: {e}")

        try:
            results = query_active_factors_jaccard(
                query=query,
                top_k=top_k,
                min_score=0.0,
                library_path=library_path,
            )
            return results
        except Exception as e:
            logger.error(f"Jaccard query failed: {e}")
            return []

    # -----------------------------------------------------------------------
    # Internal: Helpers
    # -----------------------------------------------------------------------

    def _get_dim_config(self, dimension: str) -> Dict[str, Any]:
        """获取指定维度的配置."""
        cfg_map = {
            "ast": self._ast_cfg,
            "jaccard": self._jaccard_cfg,
            "rag": self._rag_cfg,
        }
        return cfg_map.get(dimension, {})

    def _import_ast_score(self):
        """懒加载 ast_score 模块."""
        if self._ast_score_module is None:
            try:
                from quantaalpha.factors import ast_score
                self._ast_score_module = ast_score
            except ImportError:
                try:
                    from . import ast_score
                    self._ast_score_module = ast_score
                except ImportError:
                    logger.warning("Failed to import ast_score module")
                    return None
        return self._ast_score_module

    def _import_fewshot(self):
        """懒加载 fewshot 模块."""
        if self._fewshot_module is None:
            try:
                from quantaalpha.factors import fewshot
                self._fewshot_module = fewshot
            except ImportError:
                try:
                    from . import fewshot
                    self._fewshot_module = fewshot
                except ImportError:
                    logger.warning("Failed to import fewshot module")
                    return None
        return self._fewshot_module
