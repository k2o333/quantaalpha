# M005: Mining Pipeline 关键 Bug 修复

**Vision:** 修复 6 个已验证的 Bug，稳定因子挖掘 pipeline：消除硬导入失败、纠正表达式规范化缺陷、强化 LLM prompt 输出约束、优化 API 错误重试策略、集中 JSON 转义修复、消除 prompt 配置歧义。

**Source Document:** `docs/drafts/mining/problems/20260324_bug_fix_plan.md`

**Success Criteria:**
- `from quantaalpha.log import logger` 在不安装 `rdagent` 的环境中成功导入
- consistency correction 返回单行表达式
- corrected expression 通过 `normalize_corrected_expression()` 和 parser 验证
- 无效模型配置首次失败后立即抛出，不消耗重试次数
- 含杂散反斜杠的 JSON 通过统一修复路径解析
- 无运行时代码路径依赖被遮蔽的 `proposal.yaml`

---

## Slices

- [x] **S01: 移除 rdagent.log 硬依赖** `risk:medium` `depends:[]` ✅ 2026-03-24
  > After this: `from quantaalpha.log import logger, LogColors` 在不安装 rdagent 的环境中成功导入；两份 log/__init__.py 行为一致。

- [x] **S02: 强化 normalize_corrected_expression** `risk:medium` `depends:[S01]` ✅ 2026-03-24
  > After this: 函数能正确处理 dict payload、fenced blocks、// 和 # 注释、多行输出、变量赋值伪代码，并提取有效单行 DSL 表达式。

- [x] **S03: 收紧 consistency prompt 输出约束** `risk:low` `depends:[S01]` ✅ 2026-03-24
  > After this: `consistency_check_system` 和 `consistency_check_user` 明确要求单行表达式，禁止注释、赋值、伪代码和多候选输出。

- [ ] **S04: 停止对不可恢复 BadRequest 重试** `risk:low` `depends:[S01]` ✅ 2026-03-24
  > After this: 无效模型名等 400 BadRequest 错误立即重抛，不产生无效重试；配置错误在第一次失败时可见。

- [ ] **S05: 移除 proposal.yaml prompt 配置歧义** `risk:low` `depends:[S01]`
  > After this: `proposal.py` 中无 `qa_prompt_dict` 遮蔽；所有 prompt 查找均指向单一有效配置文件。

- [ ] **S06: 集中 JSON 转义修复** `risk:low` `depends:[S01]`
  > After this: `_escape_common_json_sequences()` 包含通用反斜杠转义 regex，所有 JSON 修复路径共用同一实现。

---

## Boundary Map

### S01 → 所有后续 Slice
Produces:
  `quantaalpha/log/__init__.py` → logger, LogColors (fallback impl)
  `third_party/quantaalpha/quantaalpha/log/__init__.py` → 同上（vendored 副本对齐）

Consumes: nothing (leaf node)

### S02 → S03
Produces:
  `quantaalpha/factors/proposal.py` → normalize_corrected_expression() (hardened)

Consumes from S01:
  logger (for failure logging)

### S03 → (独立)
Produces:
  `quantaalpha/factors/regulator/consistency_prompts.yaml` → consistency_check_system, consistency_check_user (tightened constraints)

Consumes: nothing downstream

### S04 → (独立)
Produces:
  `quantaalpha/llm/client.py` → _try_create_chat_completion_or_embedding() (fast-fail BadRequest)

Consumes: nothing downstream

### S05 → (独立)
Produces:
  `quantaalpha/factors/proposal.py` → 移除 qa_prompt_dict 遮蔽
  `quantaalpha/factors/prompts/proposal.yaml` → 删除或归档

Consumes: nothing downstream

### S06 → (独立)
Produces:
  `quantaalpha/llm/client.py` → _escape_common_json_sequences() (generic fallback + centralized)

Consumes: nothing downstream
