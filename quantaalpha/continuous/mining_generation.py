from __future__ import annotations

from .implementation_shared import *
from .implementation_shared import _translate_factor_expression


class MiningGenerationMixin:
    """Responsibility slice for DefaultMiningScheduler."""

    def _retrieve_context(self) -> str:
        """
        Retrieve context via RAG or fallback to library-based context.

        修复:
        1. 不再使用空字符串 query="",而是使用方向规划器的输出或默认查询
        2. 如果 SimilarityEngine 已初始化,优先使用其 query_similar_factors 方法
        3. 配置驱动 RAG 启停

        Returns:
            Context string for factor generation.
        """
        try:
            from quantaalpha.factors.fewshot import (
                query_active_factors_RAG,
                query_active_factors_jaccard,
                build_fewshot_context,
            )

            # 构建查询文本 - 不再使用空字符串
            query = self._build_similarity_query()

            # 优先使用 SimilarityEngine (如果已初始化)
            if self._similarity_engine is not None:
                try:
                    if getattr(self, "library_backend", "json") == "parquet":
                        from quantaalpha.factors.factor_store_facade import FactorStoreFacade

                        facade = FactorStoreFacade(store_path=self.parquet_library_dir)
                        results = self._similarity_engine.query_similar_factors_data(
                            query=query,
                            library=facade.as_legacy_library(),
                            top_k=10,
                        )
                    else:
                        results = self._similarity_engine.query_similar_factors(
                            query=query,
                            library_path=self.library_path,
                            top_k=10,
                        )
                    if results:
                        context = build_fewshot_context(
                            factors=results,
                            include_expression=True,
                            include_tags=True,
                            include_ic=True,
                        )
                        logger.info(f"Retrieved context via SimilarityEngine from {len(results)} factors")
                        return context
                except Exception as e:
                    logger.warning(f"SimilarityEngine query failed: {e}, falling back to legacy")

            if getattr(self, "library_backend", "json") == "parquet":
                from quantaalpha.factors.factor_store_facade import FactorStoreFacade
                from quantaalpha.factors.fewshot import compute_jaccard_similarity

                facade = FactorStoreFacade(store_path=self.parquet_library_dir)
                library_data = facade.as_legacy_library()
                results = []
                for factor_id, factor_entry in library_data.get("factors", {}).items():
                    if factor_entry.get("evaluation", {}).get("status") != "active":
                        continue
                    expression = factor_entry.get("factor_expression", "")
                    description = factor_entry.get("factor_description", "")
                    score = max(
                        compute_jaccard_similarity(query, expression) if expression else 0.0,
                        compute_jaccard_similarity(query, description) if description else 0.0,
                    )
                    results.append(
                        {
                            "factor_id": factor_id,
                            "score": round(score, 4),
                            "factor_expression": expression,
                            "factor_description": description,
                            "factor_name": factor_entry.get("factor_name", ""),
                            "tags": factor_entry.get("tags", {}),
                            "metadata": {
                                "status": factor_entry.get("evaluation", {}).get("status", ""),
                                "ic": factor_entry.get("backtest_results", {}).get("IC"),
                                "rank_ic": factor_entry.get("backtest_results", {}).get("Rank IC"),
                            },
                        }
                    )
                results.sort(key=lambda item: item["score"], reverse=True)
                results = results[:10]
            else:
                # 回退到传统方法: RAG -> Jaccard
                try:
                    results = query_active_factors_RAG(
                        query=query,
                        top_k=10,
                        library_path=self.library_path,
                    )
                except Exception:
                    # Fallback to Jaccard similarity
                    results = query_active_factors_jaccard(
                        query=query,
                        top_k=10,
                        library_path=self.library_path,
                    )

            if results and len(results) > 0:
                context = build_fewshot_context(
                    factors=results,
                    include_expression=True,
                    include_tags=True,
                    include_ic=True,
                )
                logger.info(f"Retrieved context from {len(results)} active factors via legacy path")
                return context

            return ""
        except Exception as e:
            logger.warning(f"Context retrieval failed: {e}")
            return ""

    def _build_similarity_query(self) -> str:
        """
        构建用于相似度检索的查询文本。

        优先级:
        1. 方向规划器的输出 (如果配置)
        2. 默认的高质量因子查询文本

        Returns:
            查询字符串
        """
        # 尝试从方向规划器获取查询
        if self._direction_planner is not None:
            try:
                direction = self._direction_planner.get_current_direction()
                if direction:
                    logger.info(f"Using direction planner query: {direction}")
                    return direction
            except Exception as e:
                logger.info(f"Direction planner query failed: {e}")

        # 默认查询 - 描述需要高质量因子的意图
        default_query = "high IC factor with volume and momentum signals"
        logger.info(f"Using default similarity query: {default_query}")
        return default_query

    def _build_fallback_context(self) -> str:
        """
        Build context from recent active factors in the library without RAG.

        Returns:
            Context string from recent active factors.
        """
        try:
            if getattr(self, "library_backend", "json") == "parquet":
                # Parquet backend: use FactorStoreFacade
                from quantaalpha.factors.factor_store_facade import FactorStoreFacade

                facade = FactorStoreFacade(store_path=self.parquet_library_dir)
                records = facade.read_effective_factor_records()
                candidates = [
                    {
                        "factor_id": r.get("factor_id", ""),
                        "factor_name": r.get("factor_name", ""),
                        "factor_expression": r.get("factor_expression", ""),
                        "evaluation_status": r.get("evaluation_status", ""),
                        "updated_at": r.get("updated_at", ""),
                    }
                    for r in records
                ]
            else:
                from quantaalpha.factors.library import FactorLibraryManager

                library = FactorLibraryManager(self.library_path)

                # Get active factors sorted by last_validated
                candidates = library.select_revalidation_candidates(
                    status="active",
                )

                if not candidates:
                    # Fall back to any non-failed factors
                    candidates = library.select_revalidation_candidates()

            if not candidates:
                return ""

            # Build simple context string
            lines = ["Recent active factors from the library:\n"]

            for i, factor in enumerate(candidates[:10], 1):
                lines.append(f"--- Factor {i} ---")
                lines.append(f"Name: {factor.get('factor_name', 'Unknown')}")
                expr = factor.get("factor_expression", "")
                if expr:
                    lines.append(f"Expression: {expr}")
                tags = factor.get("tags", {})
                if tags:
                    lines.append(f"Tags: {tags}")
                lines.append("")

            return "\n".join(lines)

        except Exception as e:
            logger.warning(f"Error building fallback context: {e}")
            return ""

    def _generate_factors(self, context: str) -> list[dict]:
        """
        Generate new factors via bounded mutation or template-based approach.

        MVP strategy:
        1. If LLM client is available and configured, use it for generation
        2. Otherwise, use bounded mutation over recent active factors
           - Take active factor expressions as templates
           - Apply simple transformations (parameter variation, combination)
           - Normalize to library-compatible shape

        Args:
            context: RAG context from existing factors.

        Returns:
            List of generated factor entry dicts with keys:
            - factor_id: unique identifier
            - factor_name: human-readable name
            - factor_expression: the factor expression
            - tags: factor tags including data_dependency
            - evaluation: initial evaluation dict with status
        """
        logger.info("Generating new factors")

        generated_factors = []

        # Try LLM-based generation first
        llm_candidates = self._generate_via_llm(context)
        if llm_candidates:
            generated_factors.extend(llm_candidates)
            logger.info(f"Generated {len(llm_candidates)} factors via LLM")

        # Fallback to bounded mutation if no LLM candidates
        if not generated_factors:
            mutation_candidates = self._generate_via_mutation()
            generated_factors.extend(mutation_candidates)
            logger.info(f"Generated {len(mutation_candidates)} factors via mutation")

        # Deduplicate by expression
        seen_expressions = set()
        unique_factors = []
        for factor in generated_factors:
            expr = factor.get("factor_expression", "")
            if expr and expr not in seen_expressions:
                seen_expressions.add(expr)
                unique_factors.append(factor)

        return unique_factors[: self.max_per_run]

    def _generate_via_llm(self, context: str) -> list[dict]:
        """
        Generate factors via LLM client if available.

        Returns:
            List of generated factor dicts, or empty list if LLM unavailable.
        """
        try:
            from quantaalpha.llm.client import APIBackend

            client = APIBackend()

            prompt = self._build_generation_prompt(context)
            retry_feedback = ""

            for attempt in range(1, 4):
                user_prompt = prompt
                if retry_feedback:
                    user_prompt = f"{prompt}\n\n{retry_feedback}"

                response = client.build_messages_and_create_chat_completion(
                    user_prompt=user_prompt,
                    system_prompt="You are a quantitative factor researcher. Generate novel alpha factors.",
                    stream=False,
                    llm_call_site="continuous.mining_generation.generate_via_llm",
                )

                if response:
                    factors = self._parse_llm_response(response)
                    if factors:
                        return factors
                    logger.info(f"LLM generation attempt {attempt}/3 produced no valid factors")
                    retry_feedback = self._build_generation_retry_feedback(response, attempt)
            return []

        except ImportError:
            logger.info("LLM client not available")
            return []
        except Exception as e:
            logger.warning(f"LLM generation failed: {e}")
            return []

    def _build_generation_prompt(self, context: str) -> str:
        """Build prompt for factor generation."""
        prompt_parts = [
            "You are a quantitative factor researcher.",
            "",
            "Generate new factors that are different from existing ones.",
            "",
            "Existing similar factors:\n" + (context or "No existing factors available."),
            "",
            "Generate 3-5 new factors following these rules:",
            "1. Use $field syntax for data fields (e.g., $close, $volume, $open)",
            "2. Use operators only with these signatures:",
            "   - ts_mean(A, N), ts_std(A, N), ts_var(A, N), ts_sum(A, N), ts_delta(A, N), ts_delay(A, N)",
            "   - ts_corr(A, B, N), ts_cov(A, B, N), ts_regresi(A, B, N), ts_regbeta(A, B, N), ts_slope(A, B, N)",
            "   - ts_resi(A, N), cs_mean(A), cs_std(A), cs_rank(A), cs_skew(A), cs_kurt(A), cs_median(A), cs_sum(A), cs_scale(A)",
            "   - rank(A), delta(A, N), log(A)",
            "3. Do not call cs_mean(A, B, C) or any cs_ operator with more than one argument",
            "4. Factors should be novel, not direct copies",
            "5. Return as JSON array of objects with keys: factor_name, factor_expression, tags",
            "",
            'Example: {"factor_name": "volume_strength", "factor_expression": "$volume/ts_mean($volume,20)", "tags": {"data_dependency": ["price_volume"]}}',
        ]
        return "\n".join(prompt_parts)

    def _build_generation_retry_feedback(self, response: str, attempt: int) -> str:
        """Build bounded feedback for a failed continuous LLM generation attempt."""
        excerpt = str(response or "").replace("\n", " ")[:500]
        return (
            f"Previous LLM response produced no valid factors on attempt {attempt}/3. "
            "Return only a JSON array with valid factor_expression values. "
            "Check operator argument counts exactly; cs_ operators take one argument. "
            f"Previous response excerpt: {excerpt}"
        )

    def _parse_llm_response(self, response: str) -> list[dict]:
        """Parse LLM response into factor dicts."""
        import json
        import re

        factors = []

        try:
            # Try direct JSON parsing
            # Find JSON array in response
            json_match = re.search(r"\[.*\]", response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and "factor_expression" in item:
                            factor = self._normalize_factor_entry(item)
                            # Syntax validation — match mutation path behavior
                            expr = factor.get("factor_expression", "")
                            if expr and not self._is_parsable(expr):
                                logger.info(f"Skipping unparsable LLM factor: {expr[:80]}")
                                continue
                            factors.append(factor)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")

        return factors

    def _generate_via_mutation(self) -> list[dict]:
        """
        Generate factors via bounded mutation over recent active factors.

        Mutations applied:
        - Parameter variation: change time windows (5, 10, 20, 60)
        - Operator substitution: ts_mean <-> ts_sum, ts_std <-> ts_var, rank <-> ZSCORE

        Returns:
            List of mutated factor dicts.
        """
        try:
            if getattr(self, "library_backend", "json") == "parquet":
                from quantaalpha.factors.factor_store_facade import FactorStoreFacade

                facade = FactorStoreFacade(store_path=self.parquet_library_dir)
                records = facade.read_effective_factor_records()
                candidates = [
                    {
                        "factor_id": r.get("factor_id", ""),
                        "factor_name": r.get("factor_name", ""),
                        "factor_expression": r.get("factor_expression", ""),
                        "evaluation_status": r.get("evaluation_status", ""),
                    }
                    for r in records
                ]
            else:
                from quantaalpha.factors.library import FactorLibraryManager

                library = FactorLibraryManager(self.library_path)

                # Get recent active factors as templates
                candidates = library.select_revalidation_candidates(
                    status="active",
                )

            if not candidates:
                return []

            # Take up to 5 templates
            templates = candidates[:5]

            mutated = []
            import hashlib
            import time

            for template in templates:
                template_expr = template.get("factor_expression", "")
                if not template_expr:
                    continue

                # Generate mutations (simple variation removed - it produced trivial mutations)
                mutations = [
                    self._mutate_time_windows(template_expr),
                    self._mutate_operators(template_expr),
                ]

                for mutated_expr in mutations:
                    if mutated_expr and mutated_expr != template_expr:
                        # Filter through is_parsable to ensure syntactic validity
                        if not self._is_parsable(mutated_expr):
                            logger.info(f"Mutation unparsable, skipping: {mutated_expr[:80]}")
                            continue
                        # Create factor entry
                        factor_id = self._generate_mutated_factor_id(template.get("factor_id", "unknown"), mutated_expr)

                        mutated.append(
                            {
                                "factor_id": factor_id,
                                "factor_name": f"Mutated_{template.get('factor_name', 'Factor')}",
                                "factor_expression": mutated_expr,
                                "tags": template.get("tags", {}).copy(),
                                "evaluation": {
                                    "status": "pending_validation",
                                    "last_validated": None,
                                    "stability_score": None,
                                },
                                "metadata": {
                                    "source": "mutation",
                                    "template_factor_id": template.get("factor_id"),
                                },
                            }
                        )

            logger.info(f"Mutation stats: {len(templates)} templates → {len(mutated)} valid mutants (rejected {len(templates) * 2 - len(mutated)} unparsable/identical)")
            return mutated

        except ImportError:
            logger.warning("Factor library not available for mutation")
            return []
        except Exception as e:
            logger.error(f"Error in mutation generation: {e}")
            return []

    def _mutate_time_windows(self, expression: str) -> str:
        """Replace a window-parameter argument without touching other numeric constants."""
        import re

        replacement_map = {
            "5": "10",
            "10": "20",
            "20": "60",
            "60": "5",
        }

        def replace_match(match):
            window = match.group(1)
            suffix = match.group(2)
            return f", {replacement_map.get(window, window)}{suffix}"

        return re.sub(r",\s*(5|10|20|60)(\s*\))", replace_match, expression, count=1)

    def _mutate_operators(self, expression: str) -> str:
        """Substitute one operator to create a variant expression.

        Strategy: 尝试多种替换，返回第一个与原始不同的结果。
        只替换第一次出现（count=1），避免全局替换导致语义破坏。
        """
        # 替换候选列表: (source, target)
        substitutions = [
            ("ts_mean(", "ts_sum("),
            ("ts_sum(", "ts_mean("),
            ("ts_std(", "ts_var("),
            ("ts_var(", "ts_std("),
            ("rank(", "ZSCORE("),
            ("ZSCORE(", "rank("),
        ]

        for source, target in substitutions:
            if source in expression:
                return expression.replace(source, target, 1)  # count=1

        return expression

    def _is_parsable(self, expression: str) -> bool:
        """Check if expression can be parsed successfully."""
        try:
            from quantaalpha.factors.regulator.factor_regulator import FactorRegulator

            regulator = FactorRegulator()
            return regulator.is_parsable(expression)
        except Exception:
            # If regulator is not available, assume it's parsable
            return True

    def _generate_mutated_factor_id(self, template_id: str, expression: str) -> str:
        """Generate unique factor ID for mutated factor."""
        import hashlib

        content = f"{template_id}:{expression}"
        hash_val = hashlib.md5(content.encode(), usedforsecurity=False).hexdigest()[:8]
        return f"mut_{template_id}_{hash_val}"

    def _normalize_factor_entry(self, raw_entry: dict) -> dict:
        """
        Normalize a raw factor entry to library-compatible shape.

        Args:
            raw_entry: Raw factor dict potentially from LLM or mutation

        Returns:
            Normalized factor dict with required keys.
        """
        # Ensure required keys exist
        normalized = {
            "factor_id": raw_entry.get("factor_id", ""),
            "factor_name": raw_entry.get("factor_name", "Generated Factor"),
            "factor_expression": raw_entry.get("factor_expression", ""),
            "tags": raw_entry.get("tags", {}),
            "evaluation": raw_entry.get(
                "evaluation",
                {
                    "status": "pending_validation",
                    "last_validated": None,
                    "stability_score": None,
                },
            ),
            "metadata": raw_entry.get("metadata", {}),
        }

        # Ensure factor_id is set
        if not normalized["factor_id"]:
            import uuid

            normalized["factor_id"] = f"gen_{uuid.uuid4().hex[:12]}"

        # Infer tags from expression using shared inference engine
        # This is the "three-point convergence" for tag inference safety net
        from quantaalpha.factors.tag_inference import infer_tags_from_expression

        expr = normalized["factor_expression"]
        if expr:
            inferred = infer_tags_from_expression(expr)
            # Merge: only fill in empty slots, don't override existing tags
            for tag_key, tag_values in inferred.items():
                existing = normalized["tags"].get(tag_key, [])
                if not existing:
                    normalized["tags"][tag_key] = tag_values
                elif isinstance(existing, list) and not existing:
                    normalized["tags"][tag_key] = tag_values

        return normalized
