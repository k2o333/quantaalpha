---
verdict: needs-attention
remediation_round: 0
---

# Milestone Validation: M004

## Success Criteria Checklist

- [x] **跨周期验证具备 pass_criteria 自动判定** — S01 delivered `evaluate_multi_period_results()` in `validation_judge.py` with structured `EvaluationResult` dataclass. UAT: 18/18 checks PASS. Evidence: `backtest.yaml` has `pass_criteria` config (min_ic, min_rank_ic, min_periods_pass), `require_all_pass`.

- [x] **因子库支持 select_revalidation_candidates(days=21)** — S02 delivered `select_revalidation_candidates()` method in `library.py` and `last_validated` timestamp auto-initialization. UAT: 15/15 tests PASS. Evidence: `last_validated` initialized with `datetime.now().isoformat()` on new entries.

- [x] **因子条目具备分类标签** — S03 T01 delivered tags structure in `library.py` with 16 passing tests. T02 (fewshot.py relatedness scoring enhancement) NOT completed. Tags (category/data_dependency/market_environment/time_horizon) exist in library.py. **Partial — see Slice Delivery Audit.**

- [x] **数据能力注册表新增 available_from + join_mode** — S04 delivered both fields plus `auto_discover_capabilities()`. UAT: 26/26 tests PASS. Evidence: `data_capability.py` has 13 occurrences of `available_from`, 9 of `join_mode`.

- [x] **因子完整生命周期状态机含转换规则** — S05 delivered 5-state machine (pending_validation/active/stale/degraded/deprecated). **Deviation from roadmap's seasonal/archived naming — see below.** 6-unit tests PASS. Evidence: `status_rules.py` implements `update_factor_status()` with threshold-driven transitions.

- [x] **RAG 向量检索替代 Jaccard 文本重叠** — S06 delivered `vector_store.py` (ChromaDB-backed `FactorVectorStore`) and `fewshot.py` RAG enhancements. 34 tests documented in UAT. ChromaDB is optional with Jaccard fallback (graceful degradation when unavailable).

- [x] **ProviderPool 新增 Ensemble 聚合层与 least_latency 路由** — S07 delivered `ensemble.py` (4 strategies) and `provider_pool.py` (3 routing strategies). 54 tests PASS. Evidence: `test_ensemble.py` runs successfully.

- [x] **24H 调度中心三合一设计完成** — S08 delivered `MiningOrchestrator`, `scheduler.py` interfaces, `implementations.py` defaults, and `DESIGN.md`. 28 tests documented. Evidence: `continuous/` module with all required components.

## Slice Delivery Audit

| Slice | Claimed | Delivered | Evidence | Status |
|-------|---------|-----------|----------|--------|
| S01 | cross-period pass_criteria | ✅ complete | validation_judge.py + backtest.yaml, 18 UAT checks PASS | pass |
| S02 | revalidation candidates | ✅ complete | select_revalidation_candidates() + last_validated, 15 tests PASS | pass |
| S03 | factor tags + fewshot | ⚠ partial | T01: tags in library.py (16 tests PASS). T02: fewshot.py enhancement NOT done. S03-SUMMARY.md is a placeholder. | **needs-attention** |
| S04 | data capability fields | ✅ complete | available_from + join_mode, 26 tests PASS | pass |
| S05 | factor lifecycle state machine | ✅ complete (deviation) | 5-state machine vs. roadmap's 4-state. pending_validation/active/stale/degraded/deprecated instead of seasonal/archived. 6 tests PASS. | pass (with deviation) |
| S06 | RAG vector retrieval | ✅ complete | vector_store.py + fewshot.py, 34 tests, ChromaDB optional with fallback | pass |
| S07 | Ensemble aggregation layer | ✅ complete | 54 tests PASS. ensemble.py + provider_pool.py | pass |
| S08 | 24H scheduling center | ✅ complete | MiningOrchestrator + scheduler.py + implementations.py + DESIGN.md, 28 tests | pass |

## Cross-Slice Integration

**S06 depends on S03 tags** — S06's `FactorVectorStore` embeds tags in vector metadata and `query_active_factors_RAG()` uses tag information. With S03 T02 incomplete, the tag-enhanced fewshot relatedness scoring is not available, but the base RAG functionality (vector storage, retrieval, Jaccard fallback) works without it.

**S08 depends on S06** — S08's "知新" (new knowledge) flow calls `query_active_factors_RAG()`. Works with base RAG; enhanced scoring from S03 T02 would improve quality but is not required for the design to be validated.

**S05 depends on S02 and S03** — S05 consumes `last_validated` (S02) and `tags` (S03). S05 summary notes tags are "not directly consumed" — status machine uses validation results and timestamps, not tag labels. This is acceptable; the dependency was for potential future use.

**Boundary map vs. actual:** S05-PLAN notes "Consumes: S03's `tags.market_environment`" but S05-SUMMARY admits "tags (not directly consumed)". The integration point was speculative and not actually wired. No breakage since tags exist (S03 T01 done) but the cross-slice contract was overstated.

## Requirement Coverage

- **§A.3.2, §A.3.4, §B.3.1** (Ensemble/ProviderPool): Covered by S07 ✅
- **§C.3.1, §C.3.2** (Factor library tags): Covered by S03 T01 ✅, T02 incomplete ⚠
- **§D.3.1, §D.3.2, §D.3.4** (Data capability registry): Covered by S04 ✅
- **§E.3.1** (Lifecycle state machine): Covered by S05 ✅ (with state name deviation)
- **§F.2, §F.3.1** (RAG retrieval): Covered by S06 ✅
- **§G.3.1, §H.3.1** (Revalidation scheduling): Covered by S02 + S08 ✅
- **§I.3.1** (Cross-period validation): Covered by S01 ✅

All requirements are addressed by at least one slice. No unaddressed requirements.

## Verdict Rationale

**`needs-attention`** — The milestone delivers all 8 success criteria functionally, but three issues warrant attention before the milestone is sealed:

1. **S03 T02 incomplete** — The fewshot.py relatedness scoring enhancement (标签信息进入 few-shot 评分公式) was not implemented. The S03-SUMMARY.md is a placeholder. The tags structure (T01) is correctly delivered, but the planned integration into fewshot scoring is missing. This is not a blocker since S06/S08 don't require the enhanced scoring to function, but it is a gap between the plan and delivery.

2. **S05 state model deviation** — Roadmap specifies `active / seasonal / degraded / archived`. S05 implements `pending_validation / active / stale / degraded / deprecated`. The 5-state model is functionally richer (adds `pending_validation` and `stale` states), but the naming diverges from roadmap language. This is documented in the S05 summary but the roadmap checkbox was marked `[x]` without a deviation note. Functional and tested, but the roadmap needs a correction.

3. **S03-SUMMARY.md is a placeholder** — The slice summary file has not been updated with actual delivery content. It reads "尚未开始实现" despite T01 being completed. This makes it look like S03 was never started, which is misleading.

These are **attention-level issues** — none of them block the milestone's core functionality. All 8 success criteria are functionally satisfied. The milestone can be completed with these issues documented.

## Attention Items (Non-Blocking)

- [ ] **Update S03-SUMMARY.md** — Replace placeholder with actual T01 delivery summary. T01 was completed; only T02 is pending.
- [ ] **Update roadmap state model** — Change roadmap language from "active / seasonal / degraded / archived" to "pending_validation / active / stale / degraded / deprecated" to match S05's implementation.
- [ ] **Consider S03 T02** — The fewshot.py relatedness scoring enhancement is not required for M004 success criteria, but would improve RAG quality in S06/S08. Low priority given optional nature of the enhancement.

## Remediation Plan

No remediation slices required. The attention items above are documentation fixes and optional enhancements — the milestone deliverables are functionally complete.
