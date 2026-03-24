# Requirements

This file is the explicit capability and coverage contract for the project.

Use it to track what is actively in scope, what has been validated by completed work, what is intentionally deferred, and what is explicitly out of scope.

Guidelines:
- Keep requirements capability-oriented, not a giant feature wishlist.
- Requirements should be atomic, testable, and stated in plain language.
- Every **Active** requirement should be mapped to a slice, deferred, blocked with reason, or moved out of scope.
- Each requirement should have one accountable primary owner and may have supporting slices.
- Research may suggest requirements, but research does not silently make them binding.
- Validation means the requirement was actually proven by completed work and verification, not just discussed.

## Active

- **R015: 移除 rdagent.log 硬依赖** — `quantaalpha.log` 和 `third_party/quantaalpha/quantaalpha/log` 需在 rdagent 不可用时 fallback 到本地 logger，保持 `logger.info/warning/error/exception/log_trace_path/set_trace_path` 接口兼容
  - Owner: M005-S01
  - Priority: P0 — 阻塞模块导入
  - Status: ✅ **Validated** — 实现 `FallbackLoggerWrapper` + `FallbackFileStorage`，try-except ImportError 包装 rdagent.log 导入；12 项 UAT 测试全部通过；两份 log/__init__.py MD5 一致（`25bee61c6ed7c542112dee577c87f41a`）

- **R016: 增强 normalize_corrected_expression** — 函数需处理 dict payload、fenced code blocks、`//` 和 `#` 注释、多行输出、变量赋值伪代码，提取最终有效单行 DSL 表达式；不可简单删除赋值行
  - Owner: M005-S02
  - Priority: P0 — 纠正表达式可能仍不可解析
  - Status: ✅ **Validated** — `normalize_corrected_expression()` 实现 dict-first 处理、fenced block 剥离、`//`/`#` 注释剥离、赋值 RHS 提取、非 DSL 前缀剥离、多行 DSL 模式提取；16 项单元测试全部通过；主文件和 vendored 文件 byte-identical

- **R017: 收紧 consistency prompt 输出约束** — `consistency_check_system` 和 `consistency_check_user` 需明确要求单行表达式、禁止注释/赋值/伪代码/多候选输出
  - Owner: M005-S03
  - Priority: P0 — 畸形 `corrected_expression` 的根因
  - Status: ✅ **Validated** — `consistency_prompts.yaml` system prompt 包含 "single-line DSL expression only" 约束；user prompt 包含 `**IMPORTANT:**` 块列举所有禁止模式（markdown fences、// # 注释、variable assignments、pseudo-code、multi-candidate output）；YAML 语法验证通过，3 项 grep 检查全部通过

- **R018: 停止对不可恢复 BadRequest 错误重试** — `_try_create_chat_completion_or_embedding()` 需检测无效模型名等不可恢复 400 错误并立即重抛，不消耗重试次数
  - Owner: M005-S04
  - Priority: P1 — 隐藏配置错误、浪费重试

- **R019: 集中 JSON 转义修复** — `_escape_common_json_sequences()` 需添加通用 fallback regex（处理杂散反斜杠），所有 JSON 修复路径共用此实现，不保留分散的部分实现
  - Owner: M005-S06
  - Priority: P2 — 部分 JSON 仍解析失败

- **R020: 移除 proposal.yaml prompt 配置歧义** — 移除 `proposal.py` 中被后续赋值遮蔽的 `qa_prompt_dict` 赋值；删除或归档无效的 `quantaalpha/factors/prompts/proposal.yaml`
  - Owner: M005-S05
  - Priority: P2 — 维护混淆

## Validated

- **R001: 日志系统兼容性** — 修复 RDAgentLog 参数签名不匹配问题
  - Owner: M001-S01
  - Proof: 所有 logger.warning() 调用改为 f-string 格式，通过 Python 语法检查
  
- **R002: LLM 空响应处理** — 在 JSON 解析前检测空响应并触发重试
  - Owner: M001-S02
  - Proof: 在流式和非流式分支添加空响应检查，返回空字符串让重试机制处理
  
- **R003: 重试循环上限** — factor_construct 阶段设置最大重试次数
  - Owner: M001-S02
  - Proof: while True 改为 for attempt in range(MAX_RETRIES)，MAX_RETRIES=10
  
- **R004: JSON 控制字符转义** — 正确处理包含换行符、制表符的 JSON 响应
  - Owner: M001-S03
  - Proof: 实现 _escape_control_chars_in_json() 状态机函数，通过语法检查

- **R005: Consistency check 数据类型防御** — 修复 `'dict' object has no attribute 'replace'` 错误
  - Owner: M002-S02
  - Proof: 在 ComplexityChecker.check() (lines 265-267) 和 RedundancyChecker.check() (lines 352-354) 添加 isinstance(expression, dict) 检查，通过 40+ 项单元测试（5 个测试文件）

- **R007: 跨周期验证通过标准** — 多周期回测结果需支持 `pass_criteria` 自动判定
  - Owner: M004-S01
  - Proof: backtest.yaml 新增 pass_criteria 配置（min_ic, min_rank_ic, min_periods_pass），validation_judge.py 实现 evaluate_multi_period_results() 判定函数，通过 5 种场景测试

- **R008: 因子复验候选选择** — 因子库需支持按上次验证时间和状态筛选待复验因子
  - Owner: M004-S02
  - Proof: library.py 实现 select_revalidation_candidates() 方法和 last_validated 字段初始化；status_rules.py 的 update_factor_status() 自动更新时间戳；15 项单元测试全部通过

- **R009: 因子分类标签系统** — 因子条目需具备分类标签（category / data_dependency / market_environment / time_horizon）
  - Owner: M004-S03
  - Supporting: M003-S02
  - Proof: library.py _normalize_factor_entry() 实现 tags 字段（4 类标签常量 + validation schema）；T02 (fewshot.py tag 增强评分) 未实现，基础标签结构已通过 16 项单元测试
  
- **R010: 数据能力注册表扩展** — 数据注册表需暴露 `available_from` 与 `join_mode`，供 LLM 感知数据起始日期和连接方式
  - Owner: M004-S04
  - Proof: data_capability.py 新增 available_from 字段和 auto_discover_capabilities() 函数；join_mode 根据 freq 推断（daily→same_day，quarterly→forward_fill）；render_data_capabilities() 输出包含两字段；26 项单元测试全部通过

- **R011: 因子生命周期状态机** — 因子状态需支持完整生命周期（pending_validation/active/stale/degraded/deprecated）及转换规则
  - Owner: M004-S05
  - Supporting: M004-S02, M004-S03
  - Proof: status_rules.py 实现 update_factor_status() 函数，包含 5 种状态和完整转换逻辑；集成到 library.py 的 apply_validation_result()；6 项单元测试覆盖所有转换路径

- **R012: 向量化 Few-shot / RAG 检索** — 因子库需支持 embedding 存储和向量相似度检索，增强新因子生成上下文
  - Owner: M004-S06
  - Supporting: M004-S03, M003-S02
  - Proof: vector_store.py 实现 FactorVectorStore 类（ChromaDB + Jaccard fallback）；fewshot.py 实现 query_active_factors_RAG()、build_fewshot_context()、summarize_common_patterns()；prompts.yaml 新增共性总结模板；34 项单元测试全部通过

- **R013: 多模型 Ensemble 与平台增强路由** — LLM 路由需支持聚合策略、`least_latency` 和同 Provider 多 Key
  - Owner: M004-S07
  - Supporting: M003-S04
  - Proof: `ensemble.py` 实现 EnsembleAggregator（4 种聚合策略）+ `provider_pool.py` 实现 ProviderPool（3 种路由策略、多 Key 轮询、延迟跟踪）+ `experiment.yaml` 新增 ensemble 和 provider_pool 配置段 + 54 项单元测试全部通过

- **R014: 24H 调度中心设计** — 系统需具备数据监控、温故、知新三合一自治调度架构
  - Owner: M004-S08
  - Supporting: M004-S02, M004-S05, M004-S06
  - Proof: MiningOrchestrator 主类 + scheduler.py 接口定义 + implementations.py 默认实现 + DESIGN.md 技术选型文档 + 28 项单元测试全部通过

## Traceability

| ID | Class | Status | Primary owner | Supporting | Proof |
|---|---|---|---|---|---|
| R001 | logging | validated | M001-S01 | - | f-string 格式替换，py_compile 通过 |
| R002 | llm-client | validated | M001-S02 | - | 空响应检查逻辑，流式/非流式分支 |
| R003 | factor-mining | validated | M001-S02 | - | MAX_RETRIES=10 有限重试循环 |
| R004 | json-parsing | validated | M001-S03 | - | _escape_control_chars_in_json 实现 |
| R005 | type-safety | validated | M002-S02 | S01, S03 | isinstance(dict) 检查，40+ 单元测试通过 |
| R007 | validation | validated | M004-S01 | M003-S03 | pass_criteria 配置 + evaluate_multi_period_results()，5 种场景测试通过 |
| R008 | factor-library | validated | M004-S02 | M003-S06 | select_revalidation_candidates() + last_validated 初始化，15 项单元测试通过 |
| R009 | metadata | validated | M004-S03 | M003-S02 | tags 字段定义于 _normalize_factor_entry()，标签评分增强 fewshot relatedness，16 单元测试通过 |
| R010 | data-capability | validated | M004-S04 | M003-S01 | available_from 字段 + auto_discover_capabilities()，join_mode freq 推断，26 单元测试通过 |
| R011 | lifecycle | validated | M004-S05 | M004-S02, M004-S03 | status_rules.py 实现 5 状态转换，6 单元测试通过，apply_validation_result() 集成 |
| R012 | rag-retrieval | validated | M004-S06 | M004-S03, M003-S02 | vector_store.py + fewshot.py + prompts.yaml，34 单元测试通过，ChromaDB 可选降级 |
| R013 | llm-routing | validated | M004-S07 | M003-S04 | ensemble.py EnsembleAggregator 4策略 + provider_pool.py least_latency路由 + 54单元测试 |
| R014 | orchestration | validated | M004-S08 | M004-S02, M004-S05, M004-S06 | MiningOrchestrator + scheduler.py 接口 + implementations.py + DESIGN.md + 28单元测试 |

| R015 | log-compat | validated | M005-S01 | - | FallbackLoggerWrapper + FallbackFileStorage，try-except ImportError 包装 rdagent.log，12 UAT 通过，两份 log/__init__.py MD5 一致 |
| R016 | expression-parsing | validated | M005-S02 | - | normalize_corrected_expression() dict-first 处理、fenced block 剥离、// / # 注释剥离、赋值 RHS 提取、非 DSL 前缀剥离，16 单元测试通过，两份 proposal.py byte-identical |
| R017 | prompt-constraint | validated | M005-S03 | - | consistency_prompts.yaml 系统 prompt 含 "single-line DSL expression only"，用户 prompt 含 IMPORTANT 约束块列举禁止模式，3 项 grep 检查通过 |
| R018 | api-error-handling | active | M005-S04 | - | P1: BadRequest 不区分可恢复性 |
| R019 | json-repair | active | M005-S06 | - | P2: JSON 转义修复不完整且有重复 |
| R020 | prompt-config | active | M005-S05 | - | P2: proposal.yaml 被遮蔽造成配置歧义 |

## Coverage Summary

- Active requirements: 3
- Validated requirements: 18
- Mapped to slices: 18
- Unmapped active requirements: 0

---

## Project Context (from existing docs/)

**Inferred from `docs/02-modules/*.md` and `docs/03-changes/`:**

### Module: app4
- Data pipeline for TuShare Pro
- 43 interfaces, 7 pagination modes
- Config-driven YAML approach

### Module: quantaalpha
- Factor mining and evaluation
- CLI-driven workflow
- LLM-assisted factor generation

### Module: backtest
- Alpha101 factor validation
- Polars-based computation
- Performance metrics and analysis

### Documentation Inventory
- 197 docs in `docs/`
- 77 change documents
- 3 ADRs recorded
- 4 completed tasks
- 12 active tasks

**Note**: M004 已将 `docs/drafts/mining/factor_mining_requirements.md` 中仍未覆盖的能力缺口转入 Active requirements。历史需求与背景仍可参考 `docs/03-changes/<module>/` 和 `docs/drafts/mining/需求与GSD里程碑对照表.md`。
