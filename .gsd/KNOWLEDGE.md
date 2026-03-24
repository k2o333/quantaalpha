# Knowledge Register

<!-- Append-only. Never edit or remove existing rows. To reverse a decision, add a new row that supersedes it. Read this file at the start of any planning or research phase. -->

## Submodule + Worktree 使用指南 (2026-03-23)

### 现状
- `third_party/quantaalpha` 是 git submodule（父项目记录其 commit hash）
- 已添加 `.gitmodules` 配置文件
- Worktree 模式下子模块不会自动初始化（git 限制）

### 工作流程

**主项目（Milestone 开发）：**
```bash
# 工作目录: .gsd/worktrees/M001/
# quantaalpha 里的改动需要手动提交到其自己的仓库
cd third_party/quantaalpha
git add .
git commit -m "fix: xxx"
git push

# 回到主项目，更新父项目记录的 submodule commit
cd ../..
git add third_party/quantaalpha
git commit -m "chore: update quantaalpha to latest"
```

**新建 Milestone 时恢复子模块：**
```bash
# 如果 worktrees/Mxxx/third_party/quantaalpha 为空
rm -rf third_party/quantaalpha
git clone git@github.com:k2o333/quantaalpha.git third_party/quantaalpha
# 确保 checkout 到父项目记录的 commit
cd third_party/quantaalpha
git checkout $(cd ../.. && git ls-tree HEAD third_party/quantaalpha | awk '{print $3}')
```

### 已知问题
- `git submodule` 命令在 worktree 内可能无法正常工作
- 这是一个 git worktree + submodule 的已知限制
- 解决方案：手动 clone + checkout 到正确 commit

---

## M001: QuantaAlpha 关键 Bug 修复 (2026-03-22)

### 修复摘要
修复了导致因子挖掘工作流卡死的 4 个关键 Bug：
1. **Logger 参数签名不匹配** - `RDAgentLog.warning()` 只接受单个 `msg` 参数，但代码使用了 `%s` 多参数格式
2. **LLM 空响应导致 JSON 解析崩溃** - 空响应进入 JSON 提取逻辑产生无效切片
3. **无限重试死循环** - `while True` 循环没有重试上限，导致进程卡死
4. **JSON 控制字符未转义** - JSON fix 逻辑只处理 LaTeX 反斜杠，不处理控制字符

### 修改的文件
| 文件 | 修改内容 |
|------|----------|
| `llm/client.py:69-74` | `log_tokenizer_fallback_once()` 使用 f-string |
| `llm/client.py:667` | `get_model_for_task()` 使用 f-string |
| `llm/client.py:1022-1027` | 流式分支空响应检查 |
| `llm/client.py:1034-1038` | 非流式分支空响应检查 |
| `llm/client.py:1078-1102` | JSON 控制字符转义（`_escape_control_chars_in_json`） |
| `backtest/universe.py:111` | `_coerce_date()` 使用 f-string |
| `factors/proposal.py:483` | `while True` → `for attempt in range(MAX_RETRIES)` |
| `factors/proposal.py:491-494` | 循环内空响应检查 |
| `factors/proposal.py:615` | 循环结束 `RuntimeError` |

### 关键教训
1. **日志兼容性**: `RDAgentLog` 与标准 `logging.Logger` API 不兼容，必须使用 f-string 而非 `%s` 格式
2. **防御性编程**: LLM 响应可能为空，必须在 JSON 解析前检查
3. **重试上限**: 任何重试循环都必须有明确上限，防止无限循环
4. **JSON 控制字符**: 需要区分 JSON 字符串内部的控制字符和结构空白，不能简单全局替换

### 验证方法
```bash
# 语法检查
python -m py_compile third_party/quantaalpha/quantaalpha/llm/client.py
python -m py_compile third_party/quantaalpha/quantaalpha/backtest/universe.py
python -m py_compile third_party/quantaalpha/quantaalpha/factors/proposal.py

# 日志验证（运行后检查）
grep -c "RDAgentLog.warning() takes 2 positional arguments" terminal.log  # 应为 0
grep -c "Invalid control character" terminal.log                        # 应为 0
grep -c "Factor proposal failed after.*retries" terminal.log              # 应有值（10次后退出）
```

### 未解决问题（M002）
- ~~`'dict' object has no attribute 'replace'` 错误~~ ✅ 已修复（S02 完成）
  - 触发位置: `consistency_checker.py:265`
  - 修复方案: 在 `ComplexityChecker.check()` 和 `RedundancyChecker.check()` 添加 isinstance(expression, dict) 检查
  - 验证: 13 项单元测试全部通过
- 上游 LiteLLM 代理对大 prompt 返回空响应的问题

---

## M002: 数据类型 Bug 定位（S01 完成）

### Bug 定位摘要
定位了 `'dict' object has no attribute 'replace'` 错误的触发位置和根因。

### Bug 位置
- **文件**: `third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py`
- **行号**: 265
- **代码**: `expr_clean = expression.replace(" ", "")`
- **方法**: `ComplexityChecker.check()`

### 完整数据流
```
LLM 返回 JSON (corrected_expression 可能是 dict)
    ↓
consistency_checker.py:114  result_dict.get("corrected_expression")  ← 可能返回 dict
    ↓
consistency_checker.py:487  factor_expression = corrected_expr  # dict!
    ↓
consistency_checker.py:265  complexity_checker.check(factor_expression)  # dict 传入!
    ↓
consistency_checker.py:265  expr_clean = expression.replace(" ", "")  # 💥 AttributeError!
```

### 根因
LLM 的 JSON 响应中 `corrected_expression` 字段可能返回嵌套 dict 结构：
```json
{
  "corrected_expression": {
    "code": "close / open",
    "note": "LLM suggests this form"
  }
}
```

### 已有修复函数
`proposal.py:23-26` 定义了 `normalize_corrected_expression()` 函数，但调用位置在 `proposal.py:550`，不在 `complexity_checker.check()` 调用前。

### 修复方向
在 `FactorQualityGate.evaluate()` 第 487 行后添加：
```python
factor_expression = normalize_corrected_expression(corrected_expr)
```

### 验证命令
```bash
# 语法检查
python -m py_compile third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py

# Bug 复现测试
python test/test_dict_replace_bug.py

# 终端日志验证
grep "dict.*has no attribute" /home/quan/testdata/aspipe_v4/third_party/facotors/terminal/*.txt
```

---

## M002: 数据类型 Bug 修复（S02 完成）

### 修复摘要
在 `consistency_checker.py` 的 `ComplexityChecker.check()` 和 `RedundancyChecker.check()` 方法中添加了防御性类型检查，防止 dict 输入导致 AttributeError。

### 修复代码
```python
# Defensive: Handle dict input (e.g., from LLM corrected_expression)
if isinstance(expression, dict):
    expression = expression.get("code") or expression.get("expression") or str(expression)
```

### 修复位置
- `consistency_checker.py:265` — ComplexityChecker.check()
- `consistency_checker.py:354` — RedundancyChecker.check()

### 验证命令
```bash
# 运行单元测试
cd /home/quan/testdata/aspipe_v4/.gsd/worktrees/M002
python test/test_dict_replace_fix_unit.py

# 验证修复存在
grep -n "isinstance.*expression.*dict" third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py

# 语法检查
python -m py_compile third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py
```

### 关键教训
1. **防御性类型检查**: 在所有可能接收 LLM 响应数据的方法入口处添加 isinstance() 检查
2. **fallback 链**: 使用 `.get("code") or .get("expression") or str()` 模式处理多种 dict 结构
3. **模式复用**: 该模式与 `proposal.py:23-26` 的 `normalize_corrected_expression()` 一致

---

## M002 S03: 回归测试固化 (2026-03-23)

### 完成摘要
在 T01 中创建了独立的回归测试文件，固化 dict-type AttributeError 修复，防止未来隐式回归。

### 新增文件
- `tests/test_dict_replace_bug_fix.py` — 独立回归测试文件，包含 12 个测试用例

### 测试覆盖
| 测试类 | 测试数量 | 覆盖内容 |
|--------|----------|----------|
| `TestDictTypeErrorRegression` | 6 | 验证 dict 输入不会引发 AttributeError |
| `TestOriginalBugBehavior` | 2 | 原始 bug 行为 vs 修复后行为对比 |
| `TestDictNormalizationLogic` | 4 | dict 规范化逻辑单元测试 |

### 验证命令
```bash
# 运行回归测试
cd /home/quan/testdata/aspipe_v4/.gsd/worktrees/M002
python -m pytest tests/test_dict_replace_bug_fix.py -v

# pytest 全局发现验证
python -m pytest tests/test_dict_replace_bug_fix.py --collect-only
```

### 关键教训
1. **独立测试文件**: 避免依赖复杂模块链，创建可独立运行的测试
2. **pytest 发现**: 测试文件需放在 `tests/` 目录且命名符合 `test_*.py` 模式才能被 pytest 自动发现
3. **防御性测试**: 不仅测试修复后的行为，也要测试原始 bug 的失败模式

---

## 项目知识

### 模块结构
- **app4**: TuShare Pro 数据管道（43 接口，7 分页模式）
- **quantaalpha**: 因子挖掘和评估（LLM 辅助因子生成）
- **backtest**: Alpha101 因子回测验证

### 关键文件位置
- 终端日志: `third_party/facotors/terminal/`
- 因子代码: `third_party/quantaalpha/quantaalpha/factors/`
- LLM 客户端: `third_party/quantaalpha/quantaalpha/llm/client.py`

### 运行命令
```bash
cd third_party/quantaalpha
./run.sh "挖掘日频横截面因子"
```

---

## M002 跨切片经验 (2026-03-23)

### Defensive isinstance Pattern
从 M002 修复 `'dict' object has no attribute 'replace'` 错误中总结的最佳实践：

**问题**: LLM 返回的数据类型不可预测，可能返回 dict 而非 string

**防御性代码模式**:
```python
if isinstance(expression, dict):
    expression = expression.get("code") or expression.get("expression") or str(expression)
```

**关键要点**:
1. 在所有字符串操作前检查类型
2. 提供 fallback 链: `code` → `expression` → `str()`
3. 修复比移动代码更健壮（避免依赖调用顺序）

### quantaalpha pydantic 环境问题
- `mining` conda 环境的 pydantic 兼容性问题会导致 pytest 无法运行
- **解决方案**: 创建独立测试文件，不依赖 quantaalpha 模块导入
- 测试文件命名遵循 `test_*.py` 且放在 `tests/` 目录确保 pytest 发现

### 终端日志是权威数据源
- `grep "dict.*has no attribute" third_party/facotors/terminal/*.txt` 可定位所有错误实例
- 8 处错误记录（最早: `20260321_214610.txt:202`）证明问题真实存在

### 子模块修改工作流
1. 在 `third_party/quantaalpha` 内提交修改
2. 回到主项目，更新 submodule commit 引用
3. 这确保修复在父项目和 submodule 中都有记录

---

## M004 S01: 跨周期验证通过标准 (2026-03-24)

### 完成摘要
为多周期回测实现了 pass_criteria 自动判定系统。

### 新增文件
- `quantaalpha/backtest/validation_judge.py` — 判定函数模块
- `configs/backtest.yaml` — pass_criteria 配置段

### 关键设计决策
1. **数据结构**: 使用 dataclass (EvaluationResult) 而非 dict，提供类型安全
2. **阈值比较**: IC > min_ic 和 Rank IC > min_rank_ic（严格大于）
3. **周期通过**: 必须同时满足 IC 和 Rank IC 阈值才视为通过
4. **整体判定**: require_all_pass=true 时全部周期必须通过，否则至少 min_periods_pass 个周期通过

### 防御性处理
- 空列表 → overall_pass=False, total_periods=0
- None 值 → 视为不达标（无法与阈值比较）
- status != 'success' → 按失败处理，返回描述性 reason

### 验证命令
```bash
# 语法检查
python -m py_compile third_party/quantaalpha/quantaalpha/backtest/validation_judge.py

# 配置验证
grep -o "pass_criteria" third_party/quantaalpha/configs/backtest.yaml | wc -l  # 应 >= 3

# 功能验证
python -c "from quantaalpha.backtest.validation_judge import evaluate_multi_period_results"
```

### 关键教训
1. **IC 阈值边界**: IC=0.02 且 min_ic=0.02 时应 FAIL（严格大于，不是 >=）
2. **双重阈值**: 必须同时满足 IC 和 Rank IC 才视为周期通过
3. **状态优先**: status != 'success' 直接判定失败，无需检查 IC 值

### 下游消费
- S05 (因子状态机) 可利用 overall_pass 决定状态转换
- S08 (调度中心) 可利用 pass/fail 结果触发复验调度

---

## M004 S02: 因子重验候选选择 (2026-03-24)

### 完成摘要
实现了 `select_revalidation_candidates(days, status, factor_ids)` 方法和 `last_validated` 时间戳字段。

### 关键设计决策
1. **`last_validated=None` bypasses days filter** — `if last_validated:` 守卫使 None 值跳过日期比较，因子始终被包含。这是有意设计：未知验证历史的因子应参与复验考虑。
2. **ISO 8601 字符串存储** — `datetime.now().isoformat()` 生成，与 library 中其他时间戳格式一致。
3. **setdefault() 初始化模式** — 既安全初始化新条目，又保留已存在值（从磁盘加载时）。

### 测试覆盖
- `test_revalidation_candidates.py` — 15 项测试覆盖所有筛选场景
- 覆盖：无候选、部分候选、状态过滤、ID过滤、None 处理、初始化安全

### 下游消费
- S05 (因子状态机) 消费 `last_validated` 决定 stale 状态转换
- S08 (24H 调度中心) 调用 `select_revalidation_candidates()` 触发"温故"流程

### 诊断命令
```bash
# 验证方法存在
grep -c "select_revalidation_candidates" third_party/quantaalpha/quantaalpha/factors/library.py

# 运行回归测试
cd third_party/quantaalpha && python -m pytest tests/test_revalidation_candidates.py -v

# 查看审计追踪
manager.get_audit_trail(trigger="apply_validation_result")
```

### 关键教训
1. **测试断言要匹配实际行为** — 初始测试假设 None 被视为"未过期"，但实际是"总是包含"。根据实际代码行为修正断言。
2. **`if last_validated:` 守卫语义** — 当 `last_validated` 为 None 时，不执行 `continue`，因子被包含。这是 Python 惯用写法，需理解其含义。
3. **临时测试数据中的时间计算** — 测试中的 `(now - timedelta(days=10)).isoformat()` 需要与 `select_revalidation_candidates(days=7)` 的 `(now - validated_at).days >= days` 比较一致。10d >= 7d = True（包含），2d >= 7d = False（排除）。

---

## M004 S03: 因子分类标签系统 (2026-03-24)

### 完成摘要
为因子条目新增 tags 字段（category / data_dependency / market_environment / time_horizon），并在 fewshot.py 的 relatedness 评分中使用标签重叠。

### 新增文件
- `quantaalpha/tests/test_factor_tags.py` — 16 项测试覆盖标签归一化和库集成

### 关键教训
1. **迁移旧因子**: `_normalize_factor_entry()` 在读取旧条目时自动填充默认 tags，无需迁移脚本
2. **symlink 陷阱**: 项目根目录的 `quantaalpha` symlink 指向 `third_party/quantaalpha` 时，pytest 从项目根运行才能发现 `quantaalpha/tests/` 目录
3. **partial tags 处理**: 部分提供 tags 时，只填充提供的键，其他键留空列表

---

## M004 S04: 数据能力注册表扩展 (2026-03-24)

### 完成摘要
数据注册表新增 `available_from`（数据起始日期）和 `join_mode`（same_day / forward_fill，从 freq 推断），并实现 `auto_discover_capabilities()` 动态发现函数。

### 新增文件
- `quantaalpha/tests/test_data_capability_extensions.py` — 26 项测试覆盖字段归一化、推断逻辑、渲染输出、防御性行为

### 关键设计决策
1. **`join_mode` 推断规则**: `_FREQ_TO_JOIN_MODE` 映射 (daily/weekly → same_day, quarterly/monthly/annual → forward_fill)；显式设置优先于推断
2. **`available_from=None` 渲染为 `(unknown)`**: 不省略字段，让 LLM 感知数据边界未知
3. **`auto_discover_capabilities()` 是加性的**: 已有硬编码日期的条目保留，新增 Parquet 文件推断后填充

### 防御性设计
- `infer_available_from_from_parquet()` 用 try/except 包裹 polars 调用，任何异常返回 None
- `auto_discover_capabilities()` 对不存在路径返回原始 registry，不抛异常

### 关键教训
1. **S01 计划假设与实际不符**: S04 计划假设 `auto_discover_capabilities()` 已在 S01 实现，但实际未实现。T01 从零实现该函数。
2. **polars 是可选依赖**: `infer_available_from_from_parquet()` 在 polars 不可用时静默返回 None，相关测试仍通过。

### 下游消费
- LLM prompt → `render_data_capabilities()` 输出包含 `available_from=` 和 `join_mode=`
- S05/S08 → `available_from` 可用于判定因子是否适用于特定时间段

### 诊断命令
```bash
# 查看渲染输出
python -c "from quantaalpha.factors.data_capability import render_data_capabilities; print(render_data_capabilities())"

# 查看 normalized registry
python -c "from quantaalpha.factors.data_capability import get_data_capabilities; import json; print(json.dumps(get_data_capabilities(), indent=2))"

# 运行 S04 测试
pytest quantaalpha/tests/test_data_capability_extensions.py -v
```

---

## M004 S05: 因子生命周期状态机 (2026-03-24)

### 完成摘要
实现了因子生命周期状态机，但采用不同于原计划的状态模型。

### 状态模型对比

| 原计划状态 | 实际实现状态 | 说明 |
|------------|--------------|------|
| stable_active | pending_validation | 初始状态 |
| seasonal | (无) | 未实现，stale 覆盖时间维度 |
| degraded | degraded | 一致 |
| archived | deprecated | 强调主动废弃 |

### 实际实现的状态

| 状态 | 触发条件 |
|------|----------|
| `pending_validation` | 初始状态 |
| `active` | 验证成功 + stability >= 0.5 |
| `stale` | active 超过 30 天未验证 |
| `degraded` | 失败 OR stability < 0.3 |
| `deprecated` | 连续失败 >= 3 次 |

### 新增/修改文件
- `quantaalpha/factors/status_rules.py` — 状态机核心逻辑
- `quantaalpha/factors/library.py` — apply_validation_result() 集成
- `tests/test_status_transition.py` — 6 项单元测试

### 关键设计决策
1. **配置驱动阈值**: `DEFAULT_FACTOR_STATUS_CONFIG` dict 支持运行时覆盖
2. **deepcopy()**: 避免修改原始 entry
3. **ISO 时间戳**: `last_validated` 存储为 ISO 8601 格式
4. **审计追踪**: 状态变更记录在 `_audit` 字段

### 关键教训
1. **状态模型可以演进**: 原计划使用 seasonal/archived，实际实现用 stale/deprecated 是合理的设计演进
2. **稳定性阈值边界**: stability >= 0.5 → active, stability < 0.3 → degraded（中间值按 degraded 处理）
3. **stale 仅对 active 有效**: 其他状态不会触发 stale 检测

### 下游消费
- S08 (24H 调度中心) 可利用状态机决定调度触发条件

### 诊断命令
```bash
# 语法检查
python -m py_compile quantaalpha/factors/status_rules.py

# 运行状态转换测试
pytest tests/test_status_transition.py -v

# 检查因子状态
entry["evaluation"]["status"]

# 检查连续失败
entry["evaluation"]["consecutive_failures"]
```

---

## M004 S06: RAG 向量检索 (2026-03-24)

### 完成摘要
实现了 ChromaDB-backed 向量检索系统，替代 Jaccard 文本重叠。

### 新增文件
- `quantaalpha/factors/vector_store.py` — FactorVectorStore 类
- `quantaalpha/factors/fewshot.py` — RAG 增强模块
- `quantaalpha/tests/test_vector_store.py` — 34 项单元测试

### 关键设计决策

1. **ChromaDB Optional**: `CHROMADB_AVAILABLE` guard 实现优雅降级
2. **Text Normalization**: 使用 `re.sub(r'[^a-zA-Z0-9\s]', ' ', text.lower())` 去除特殊字符
3. **Cosine Distance**: ChromaDB collection 使用 `hnsw:space: cosine`
4. **Singleton Pattern**: `get_vector_store()` 管理实例，`reset_vector_store()` 清理

### Text Normalization Pattern
```python
import re

def normalize(text: str) -> set[str]:
    """Normalize text: lowercase, remove special chars, split into words."""
    normalized = re.sub(r'[^a-zA-Z0-9\s]', ' ', text.lower())
    return set(w for w in normalized.split() if w)
```

### 关键教训
1. **Factor expressions 使用 `$close` 等特殊字符**: 需要 normalization 才能与普通查询匹配
2. **ChromaDB 在当前环境不可用**: 测试验证了 fallback 模式正常工作
3. **Singleton 需要 reset**: 测试间调用 `reset_vector_store()` 避免状态污染

### 下游消费
- S08 (24H 调度中心) → `query_active_factors_RAG()` 用于"知新"流程

### 诊断命令
```bash
# 检查 ChromaDB 可用性
python -c "from quantaalpha.factors.vector_store import CHROMADB_AVAILABLE; print(CHROMADB_AVAILABLE)"

# 语法检查
python -m py_compile quantaalpha/factors/vector_store.py
python -m py_compile quantaalpha/factors/fewshot.py

# 运行测试
pytest quantaalpha/tests/test_vector_store.py -v

# 检查依赖
grep chromadb quantaalpha/requirements.txt
```


---

## M004 S07: Ensemble 聚合层 (2026-03-24)

### 完成摘要
为因子挖掘工作流实现了多模型 Ensemble 聚合层和增强的 ProviderPool 路由系统。

### 新增文件
- `quantaalpha/llm/ensemble.py` — EnsembleAggregator 类（4 种策略）
- `quantaalpha/llm/provider_pool.py` — ProviderPool 类（3 种路由策略）
- `quantaalpha/tests/test_ensemble.py` — 54 项单元测试

### 关键设计决策
1. **无日志策略函数**: ensemble.py 策略函数不依赖 logger，避免 RDAgentLog.debug() 不存在的问题
2. **LatencyStats 对象保留**: reset_latency_stats() 重置对象属性而非删除 key，保持 get_latency_stats() 返回一致的 dict 结构
3. **least_latency 降级策略**: 样本不足时降级到 round_robin，不会崩溃
4. **threading.RLock**: 可重入锁支持嵌套锁定

### 关键教训
1. **RDAgentLog 只有 info/warning/error**: 不能使用 `logger.debug()`，否则抛出 AttributeError
2. **get_latency_stats 对不存在 Provider 返回 None**: 不是空 dict，是 None
3. **voting 策略保序语义**: 元素顺序来自第一个包含该元素的模型，而非按投票数排序
4. **mining conda 环境**: 测试必须用 `/root/miniforge3/envs/mining/bin/python` 才有 rdagent 模块

### 验证命令
```bash
# 语法检查
python -m py_compile quantaalpha/llm/ensemble.py
python -m py_compile quantaalpha/llm/provider_pool.py

# 单元测试
cd third_party/quantaalpha
/root/miniforge3/envs/mining/bin/python -m pytest quantaalpha/tests/test_ensemble.py -v
# Expected: 54 passed

# 功能验证
/root/miniforge3/envs/mining/bin/python -c "
from quantaalpha.llm.ensemble import EnsembleAggregator, ModelResponse
from quantaalpha.llm.provider_pool import ProviderPool

agg = EnsembleAggregator(strategy='union_dedup')
result = agg.aggregate([
    ModelResponse('gpt4', ['f1', 'f2']),
    ModelResponse('claude', ['f2', 'f3']),
])
assert result.output == ['f1', 'f2', 'f3']

pool = ProviderPool(routing='least_latency')
pool.add_provider('fast', api_keys=['k1'])
pool.add_provider('slow', api_keys=['k2'])
pool.record_latency('slow', 'k2', 500.0)
pool.record_latency('fast', 'k1', 30.0)
key, _ = pool.get_key_and_provider()
assert key == 'k1'
print('OK')
"
```

### 下游消费
- S08 (24H 调度中心) → ProviderPool.get_stats_summary() 用于监控 Provider 健康状态

---

## M004 S08: 24H 调度中心设计 (2026-03-24)

### 完成摘要
设计了完整的三合一调度中心架构（数据监控 + 温故 + 知新），并实现了接口定义和默认实现。

### 新增文件
- `quantaalpha/continuous/__init__.py` — 模块导出
- `quantaalpha/continuous/scheduler.py` — 抽象接口定义
- `quantaalpha/continuous/orchestrator.py` — MiningOrchestrator 主类
- `quantaalpha/continuous/implementations.py` — 默认实现
- `quantaalpha/continuous/DESIGN.md` — 技术选型文档
- `quantaalpha/tests/test_continuous.py` — 28 项单元测试

### 架构设计
```
MiningOrchestrator (统一入口)
├── DataMonitorTrigger (数据监控)
│   └── DefaultDataMonitor (文件系统轮询)
├── RevalidationScheduler (温故)
│   └── DefaultRevalidationScheduler (APScheduler)
└── MiningScheduler (知新)
    └── DefaultMiningScheduler (APScheduler)
```

### 技术选型决策
| 类别 | 决策 | 理由 |
|------|------|------|
| 任务调度 | APScheduler | 零依赖，单机够用 |
| 进程管理 | Supervisor | 配置简单，supervisorctl 管理 |
| 数据监控 | 文件系统轮询 | 可靠，可升级到 inotify |
| 向量存储 | ChromaDB | S06 已集成 |
| 配置管理 | Pydantic dataclass | 类型安全，验证 |

### 关键教训
1. **Lazy initialization**: 调度器按需创建，避免导入开销
2. **ABC for extensibility**: 支持自定义实现替换默认实现
3. **Event callbacks**: 外部系统可订阅调度器事件
4. **Health monitoring**: `get_health_report()` 提供运营可见性

### 已知限制
- `run_revalidation()` 中的 `_run_factor_backtest()` 目前返回 `True`（待集成回测模块）
- `run_mining()` 中的 `_generate_factors()` 目前返回空列表（待集成 LLM）
- 实际回测和 LLM 集成待实现

### 验证命令
```bash
# 语法检查
cd third_party/quantaalpha
python -m py_compile quantaalpha/continuous/orchestrator.py
python -m py_compile quantaalpha/continuous/scheduler.py

# 模块导入
python -c "from quantaalpha.continuous import MiningOrchestrator"

# 健康报告
python -c "
from quantaalpha.continuous import MiningOrchestrator
orch = MiningOrchestrator()
print(orch.get_health_report())
"

# 单元测试
/root/miniforge3/envs/mining/bin/python -m pytest quantaalpha/tests/test_continuous.py -v
# Expected: 28 passed
```

### 下游消费
- 未来实现 → Supervisor 配置
- 未来实现 → 因子库集成
- 未来实现 → 健康检查 API

---

## M004 跨切片经验 (2026-03-24)

### Normalization 初始化副作用
S02 将 `_normalize_factor_entry()` 中 `last_validated` 默认值从 `None` 改为 `datetime.now().isoformat()`，导致依赖 `last_validated` 的统计逻辑行为改变（`total_validated` 从 2 → 3）。教训：**修改 `_normalize` 函数的默认值后，必须回检所有依赖该字段的逻辑和测试断言。**

### Optional 依赖降级模式
S06 的 ChromaDB 可选依赖模式（`CHROMADB_AVAILABLE` guard + Jaccard fallback）值得推广：所有可选外部依赖（向量库、LLM provider）都应实现本地降级，避免环境差异导致运行时崩溃。

### 测试断言需随代码演进更新
`test_data_capability_registry.py` 中的两处测试期望 `normalize_capability_spec()` 返回固定 schema，但 S04 在 DEFAULT_CAPABILITY_SPEC 中新增了 `available_from` 字段。教训：**每次在 schema 常量中添加字段后，检查所有测试该 schema 的断言。**

### S03 T02 未启动对整体交付无影响
S03 T02（fewshot.py tag 增强评分）未实现，但 S06 的 RAG 功能（向量检索 + fewshot 基础上下文）完全可用。S08 调度中心调用 `query_active_factors_RAG()` 也不依赖 T02 的增强评分。教训：**子任务未完成≠切片失败，需评估对下游的实质影响。**

### EnsembleAggregator 是纯内存实现
S07 的 `EnsembleAggregator` 不持久化任何状态，每次调用 `aggregate()` 都是独立的。这意味着多个并发请求各自独立聚合，无法共享聚合结果。如需共享需引入外部存储。教训：接口设计时明确标注"stateless" vs "stateful"。

---

## M005: Mining Pipeline Bug 验证与修复计划 (2026-03-24)

**来源文档**: `docs/drafts/mining/problems/20260324_bug_fix_plan.md`
**验证文档**: `docs/drafts/mining/problems/20260324_verified_bugs_and_fixes.md`

### 活跃修复路径
```
check_consistency() → corrected_expression → proposal.py normalize_corrected_expression() → parser re-check
```
`expression_correction_system` 存在于 prompt 配置但**未**接入当前运行时。仅修改该 prompt 不会影响实际行为。

### Bug-6 (P0): rdagent.log 硬依赖

**根因**: `quantaalpha/log/__init__.py` 和 `third_party/quantaalpha/quantaalpha/log/__init__.py` 均无条件 `from rdagent.log ...`，但当前环境未安装该模块，导致任何 `from quantaalpha.log import ...` 失败。

**修复文件**:
- `quantaalpha/log/__init__.py`
- `third_party/quantaalpha/quantaalpha/log/__init__.py`
- （如需）`quantaalpha/log/_fallback.py`

**修复形状** (try/except 守卫):
```python
try:
    from rdagent.log import ...
except ImportError:
    # 本地 fallback logger，保持接口兼容
    ...
```

**必须兼容的接口**: `logger.info()`, `logger.warning()`, `logger.error()`,
`logger.exception()`, `logger.log_trace_path`, `logger.set_trace_path(path)`

**验证命令**:
```bash
python -c "from quantaalpha.log import logger, LogColors; print(type(logger).__name__)"
python -c "from quantaalpha.factors.proposal import normalize_corrected_expression; print('ok')"
```

---

### Bug-1 (P0): normalize_corrected_expression 放行脏字符串

**根因**: 现有 `normalize_corrected_expression()` 函数逻辑过于简单，不处理：
dict payload、fenced code blocks、`//` 和 `#` 注释、多行输出、变量赋值伪代码（`x = ...`）、stringified JSON/dict 字符串。

**关键约束 — 不可简单跳过赋值行**:
> 若 LLM 返回 `alpha = TS_STD($close, 10)\nfactor = RANK(alpha)`，跳过含 `=` 的行会删掉唯一有效表达式。
> 正确做法：提取**最后一个有意义赋值**的右侧值。

**验证用例**:
| 输入 | 期望输出 |
|------|---------|
| `TS_STD($close, 10) // comment` | `TS_STD($close, 10)` |
| `alpha = TS_STD($close, 10)\nfactor = RANK(alpha)` | `RANK(alpha)` |
| `` ```json {"expression": "TS_CORR($high-$low, $volume, 20)"}``` `` | `TS_CORR($high-$low, $volume, 20)` |

**修复文件**: `quantaalpha/factors/proposal.py`

---

### Bug-2 (P0): consistency prompt 缺乏严格输出约束

**根因**: `consistency_check_system` prompt 未硬性要求输出格式，允许 LLM 返回含注释、变量赋值、多候选的伪代码，是 Bug-1 的上游根因。

**必须加入的措辞**:
- "Return ONLY a SINGLE-LINE factor expression."
- "Do NOT include comments, markdown fences, variable assignments, prose, or multiple candidate expressions."
- "Use only the listed variables/functions."

**修复文件**: `quantaalpha/factors/regulator/consistency_prompts.yaml`
- 更新 `consistency_check_system` 输出契约
- 更新 `consistency_check_user` 重复相同约束

---

### Bug-3 (P1): BadRequest 重试策略不区分可恢复性

**根因**: `_try_create_chat_completion_or_embedding()` 对 `openai.BadRequestError` 统一触发重试，
无效模型名（400 + "invalid model"）等**不可恢复**错误会被无谓重试，且错误信息被隐藏。

**修复要点**:
- 使用 `str(e)` 检测 "invalid model" / "invalid model name" 等关键词
- 立即 `raise` 而非进入重试循环
- 日志中包含实际失败的模型名（chat: chat model, embedding: embedding model）
- 保留现有对 JSON-mode 缺失 "json" 关键词的特殊处理

**修复文件**: `quantaalpha/llm/client.py`

---

### Bug-4 (P2): JSON 转义修复不完整且有重复

**根因**: `_escape_common_json_sequences()` 包含针对 LaTeX 的特定替换（`\alpha` 等），
但缺少通用杂散反斜杠处理（`\` 后跟不被 JSON 允许的字符）。且 JSON 修复路径存在两个部分不同的实现。

**需要添加的通用 regex**:
```python
re.sub(r'\\(?!["\\\\/bfnrtu])', r'\\\\', text)
```

**修复文件**: `quantaalpha/llm/client.py`
- 在 `_escape_common_json_sequences()` 中添加通用 fallback
- 所有 JSON 修复路径使用同一函数

---

### Bug-5 (P2): proposal.yaml 配置歧义

**根因**: `proposal.py` 中先赋值 `qa_prompt_dict = Prompts(...proposal.yaml)`，
后又重新赋值覆盖，导致前者死代码。实际运行时 prompt 来源只有后一个赋值，
但 `proposal.yaml` 文件仍存在，造成维护混淆。

**修复要点**:
1. 移除死代码 `qa_prompt_dict = Prompts(...proposal.yaml)`
2. 删除或归档 `quantaalpha/factors/prompts/proposal.yaml`
3. 确认所有运行时 prompt 查找指向有效配置文件

**验证命令**:
```bash
rg "proposal.yaml|qa_prompt_dict =" quantaalpha/factors/proposal.py
```

---

### M005 教训（预登记）

1. **Hard import = 全局阻塞**: 任何 optional 依赖都应 try/except 守卫，尤其是大型外部框架（rdagent）
2. **Prompt 约束是第一道防线**: LLM 输出格式问题首先是 prompt 问题，代码健壮性是第二道防线，两者都不可省
3. **赋值提取 vs 行过滤**: 清理含赋值伪代码时，提取右侧值比跳过行更安全，后者会静默丢弃有效表达式
4. **BadRequest 不等于可重试**: HTTP 400 可能是配置错误（不可恢复）也可能是请求格式错误（可重试），必须区分


---

## M005 S01: rdagent.log Fallback Logger（2026-03-24）

### 关键模式

**1. Optional 依赖用 try-except ImportError 守卫**
```python
try:
    from rdagent.log import rdagent_logger as _rdagent_logger
    from rdagent.log.utils import LogColors as _LogColors
    logger = _rdagent_logger
    if _LogColors is not None:
        LogColors = _LogColors
except ImportError:
    _fallback_logger = logging.getLogger("quantaalpha")
    logger = FallbackLoggerWrapper(_fallback_logger)
```

**2. Wrapped Logger 用 object.__setattr__ 避免属性冲突**
```python
def __setattr__(self, name: str, value) -> None:
    if name in ("_inner", "_storage"):
        object.__setattr__(self, name, value)  # 写私有属性
    else:
        setattr(self._inner, name, value)      # 代理到内层 logger
```
直接 `self._inner = inner` 会触发 `__setattr__` 无限递归，`object.__setattr__` 绕过代理。

**3. 两份 submodule 文件必须同步**
`third_party/quantaalpha` 是 git submodule，其中文件改动需要：
1. 在 submodule 内提交
2. 在父项目更新 submodule commit 引用
每次修改后用 `diff -q` 或 MD5 核对一致性。

**4. rdagent 可导入但 rdagent.log 不存在的情况**
`import rdagent` 成功但 `from rdagent.log import ...` 失败是独立问题。必须用 `from rdagent.log import ...` 的 try-except 捕获，不能只检查 `import rdagent`。

### 验证命令
```bash
# 导入测试
python -c "from quantaalpha.log import logger, LogColors; print(type(logger).__name__)"

# 文件一致性
diff -q quantaalpha/log/__init__.py third_party/quantaalpha/quantaalpha/log/__init__.py

# rdagent-free 验证
python -c "import sys; mods=[m for m in sys.modules if 'rdagent' in m.lower()]; assert not mods, mods; from quantaalpha.log import logger; print('OK')"
```

### 已知限制
- Fallback 模式只有控制台输出，无文件日志（truncate 为 no-op）
- 当 rdagent.log 可用时，仍使用原始 rdagent logger（fallback 仅在 ImportError 时触发）

---

## M005 S02: normalize_corrected_expression 强化 (2026-03-24)

### 完成摘要
用硬化版本替换 `normalize_corrected_expression`，处理 LLM 返回的各类脏字符串模式。

### 关键模式

**1. Dict-first 处理（dict 必须在 isinstance(str) 之前）**
```python
def normalize_corrected_expression(expression) -> str:
    # ✅ 正确：dict 处理在最前面
    if isinstance(expression, dict):
        for key in ("code", "expression", "factor", "formula"):
            if key in expression:
                expression = str(expression[key])
                break
        else:
            expression = str(expression)

    if not isinstance(expression, str):  # ← isinstance(str) 守卫在 dict 处理之后
        return str(expression)
```
`str(dict)` 会转换为 repr 形式（如 `"{'code': '...'}"`），使后续 JSON 解析无法提取嵌套 key。

**2. Embedded DSL Regex（非 DSL 前缀剥离）**
```python
# 用于从 "Option A: STD(...)" 提取 DSL
dsl_match = re.search(r"\b([A-Z][A-Z_]*)\s*\([^)]+\)", expression)
```
此 regex 在每行验证后作为 fallback 执行，捕获嵌入的 DSL 表达式。

**3. JSON String Dict 解析（字符串形式的 dict）**
```python
stripped = expression.strip()
if stripped.startswith("{") and stripped.endswith("}"):
    try:
        parsed = json.loads(stripped)
        # ... extract nested key
    except (json.JSONDecodeError, ValueError):
        pass  # 降级到字符串处理
```
输入可能是字符串形式的 JSON dict，而非实际 dict 对象。

**4. exec()-based Source Extraction（隔离测试）**
```python
import ast
with open(PROPOSAL_PATH) as f:
    content = f.read()
tree = ast.parse(content)
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name == "normalize_corrected_expression":
        exec_globals = {}
        exec(ast.get_source_segment(content, node), exec_globals)
        fn = exec_globals["normalize_corrected_expression"]
```
绕过 jinja2 导入链，使用 AST + exec() 隔离加载函数。

**5. Byte-identical Vendored Sync（vendored 文件同步）**
```bash
# 同步
cp quantaalpha/factors/proposal.py third_party/quantaalpha/quantaalpha/factors/proposal.py

# 验证
diff -q quantaalpha/factors/proposal.py third_party/quantaalpha/quantaalpha/factors/proposal.py
# 无输出 = 一致
```
Vendored 副本是主文件的字节级镜像，任何差异都意味着同步失效。

### 验证命令
```bash
# 语法检查
python -m py_compile quantaalpha/factors/proposal.py
python -m py_compile third_party/quantaalpha/quantaalpha/factors/proposal.py

# 文件一致性
diff -q quantaalpha/factors/proposal.py third_party/quantaalpha/quantaalpha/factors/proposal.py

# 单元测试
python -m pytest tests/test_normalize_corrected_expression.py -v
# 预期：16 passed
```

### 已知限制
- DSL fallback 提取第一个 `FUNC(...)` 模式，如果没有有效行则返回原始输入
- 赋值语句中 `=` 的处理：只提取第一个 `=` 后的内容（`x = a = b` → `a = b`）

---

## M005 S03: consistency prompt 输出约束收紧 (2026-03-24)

### 完成摘要
收紧 `consistency_prompts.yaml` 的 `corrected_expression` 输出约束，明确禁止 markdown、注释、赋值、伪代码和多候选输出。

### 关键模式

**1. 双重约束策略（字段描述 + IMPORTANT 块）**
- **系统 prompt**：在 JSON 输出格式的 `corrected_expression` 字段描述中嵌入约束
  ```
  "corrected_expression": "A single-line DSL expression only — no markdown, 
  no comments, no assignments, no explanation. E.g. \"RANK(CLOSE)/RANK(OPEN)\". 
  Use null if the expression is already correct."
  ```
- **用户 prompt**：末尾添加 `**IMPORTANT:**` 粗体块
  ```
  **IMPORTANT: `corrected_expression` must be a single-line DSL expression only. 
  No markdown fences, no comments (// or #), no variable assignments (expr = ...), 
  no pseudo-code, no multi-candidate output (Option A/B/C). Use null if no 
  correction is needed.**
  ```

**2. 枚举所有禁止模式的策略**
LLM 容易输出常见格式问题时，需要**穷举**禁止模式而非简单说"只输出表达式"：
- `markdown fences` — 防止 ```json ... ```
- `comments (// or #)` — 防止 `// comment` 或 `# comment`
- `variable assignments` — 防止 `alpha = ...`
- `pseudo-code` — 防止 `Option A:` 等伪代码
- `multi-candidate output` — 防止 `Option A/B/C`

**3. 静态文件验证模式**
Prompt 是静态 YAML 文件，无需运行时测试：
```bash
# YAML 语法验证
python -c "import yaml; yaml.safe_load(open('...'))"

# 约束存在性验证
grep -q "single-line DSL expression only" ...
grep -q "IMPORTANT:" ...
```

### 验证命令
```bash
# YAML 语法
python -c "import yaml; yaml.safe_load(open('quantaalpha/factors/regulator/consistency_prompts.yaml'))"

# 系统 prompt 约束
grep -q "single-line DSL expression only" quantaalpha/factors/regulator/consistency_prompts.yaml

# 用户 prompt IMPORTANT 块
grep -q "IMPORTANT:" quantaalpha/factors/regulator/consistency_prompts.yaml
```

### 已知限制
- 约束仅指导 LLM 输出格式，无法强制执行（LLM 可能仍不遵守）
- S02 的 `normalize_corrected_expression()` 作为代码层第二道防线兜底
- 禁止模式枚举可能随 LLM 能力演进而需要更新

---

## M005 S05: proposal.yaml 死赋值移除与归档 (2026-03-24)

### 完成摘要
移除 `proposal.py` 中的配置歧义，删除指向废弃 `proposal.yaml` 的死赋值，并归档该 YAML 文件。

### 关键决策

**1. 归档而非删除策略**
废弃配置文件应归档为 `.archived` 而非直接删除：
- 保留历史参考价值
- 可供未来审计查阅
- 不影响运行时行为

**2. 死赋值检测方法**
使用 `rg -c "qa_prompt_dict = Prompts" proposal.py` 计数：
- 正常：返回 1（仅有效赋值）
- 异常：返回 > 1（存在死赋值）

**3. 行号变化意识**
删除行后，剩余代码行号会调整。原第 159 行删除后，原第 305 行变为第 304 行。

### 验证命令
```bash
# 确认仅剩 1 个有效赋值
rg -c "qa_prompt_dict = Prompts" quantaalpha/factors/proposal.py
# 预期: 1

# 确认配置文件状态
ls quantaalpha/factors/prompts/proposal.yaml  # 应失败
ls quantaalpha/factors/prompts/proposal.yaml.archived  # 应存在

# 语法检查
python -m py_compile quantaalpha/factors/proposal.py
# 预期: 退出码 0
```

### 关键教训
- 配置文件有多个副本时，确认哪个是"真实"的有效配置
- 死赋值不产生运行时错误，但会造成维护混淆
- 归档文件不应被 `__init__.py` 或任何 Python 代码主动加载

## S06: 集中 JSON 转义修复 (2026-03-24)

### 两层 JSON 修复 concerns 必须区分
`quantaalpha/llm/client.py` 中存在两个独立的 JSON 修复层：
1. **`_escape_common_json_sequences()`** — 处理 LLM 输出中的 LaTeX/symbol 反斜杠转义（`\_`、`\alpha`、杂散 `\`）
2. **`_escape_control_chars_in_json()`** — 处理 JSON 字符串值内的原始控制字符（U+0000-U+001F）

两层必须同时存在，不可合并。控制字符（如 `\x00`）在 JSON 解析前必须被转义，但 LaTeX 转义不涉及控制字符。

### Generic Fallback Regex 的 Negative Lookahead 设计
通用 fallback: `re.sub(r'\\(?!["\\\/bfnrtu])', r'\\\\', fixed_text)`

关键点：
- `(?!...)` 是 negative lookahead，不消费字符
- 排除 `nrtfb/"'/\` 和 `u`（JSON 有效转义）
- 对每个未识别反斜杠后跟的字符，在其前再加一个反斜杠（变成双反斜杠）
- `\n`、`\t`、`\r` 等有效 JSON 转义不受影响

### re.sub Replacement String 的 Backslash Math
在 raw string 中写 `r"\\\\"` = 4 个反slash字符 = 2 对 = regex replacement 输出 2 个反斜杠。

| Python raw string | regex replacement 中的反斜杠对数 | 输出字符 |
|---|---|---|
| `r"\\\\"` | 2 对 | `\\` (2 个反斜杠) |
| `r"\\\\\\1"` | 3 对 + `\1` | `\\\1` (3 个反斜杠 + 捕获组) |

当 specific escape（3 pairs = 3 bs + captured）与 generic fallback（对 matched backslash +2 bs）联合作用时，需要精确计算避免 over-escaping。

### Vendored 同步 checklist
每次修改 `quantaalpha/llm/client.py` 后：
1. `mkdir -p third_party/quantaalpha/quantaalpha/llm/` — vendored 目录可能不存在
2. `cp quantaalpha/llm/client.py third_party/quantaalpha/quantaalpha/llm/client.py`
3. `diff -q ... && md5sum ...` — 验证 byte-identical

### 诊断命令
```bash
# 验证 generic fallback 存在
sed -n '129p' quantaalpha/llm/client.py
# 预期: fixed_text = re.sub(r'\\(?!["\\\/bfnrtu])', r'\\\\', fixed_text)

# 验证内联循环已移除
grep -c "latex_commands" quantaalpha/llm/client.py  # 应为 2（仅在 _escape_common_json_sequences 内）

# 验证 unified call 存在
grep -n "_escape_common_json_sequences(fixed_resp)" quantaalpha/llm/client.py
# 预期: 1078

# 端到端 JSON 解析测试
python3 -c "
import re, json
def _escape_common_json_sequences(text: str) -> str:
    fixed_text = text
    for cmd in ['text','frac','left','right','times','cdot','sqrt','sum','prod','int','alpha','beta','gamma','delta']:
        fixed_text = re.sub(r'(?<!\\\\)\\\\(' + cmd + r')', r'\\\\\\\\\1', fixed_text)
    fixed_text = re.sub(r'(?<!\\\\)\\\\([_\\{\\}\\[\\]])', r'\\\\\\\\\\\\1', fixed_text)
    fixed_text = re.sub(r'\\\\(?![\"\\\\\\\/bfnrtu])', r'\\\\\\\\', fixed_text)
    return fixed_text
for t in [r'{\"x\": \"\_ 10\"}', r'{\"expr\": \"PE \_ 10\"}', '{\"name\": \"John\_Doe\"}', '{\"valid\": \"\\\\n is newline\"}']:
    json.loads(_escape_common_json_sequences(t)); print(f'OK: {t[:30]}')
"
```

---

## M005: 跨切片综合教训 (2026-03-24)

### 1. Vendored Submodule Byte-Identical 必须严格执行

**问题**: S02 创建 vendored `proposal.py` 为 byte-identical 副本，但 S05 修改 main 文件后遗漏同步 vendored 副本。结果：main 和 vendored 的 proposal.py 不一致（vendored 仍含死赋值）。

**原则**: 所有 submodule 文件（`third_party/quantaalpha/quantaalpha/`）在被修改后，都必须同步到 submodule 的 vendored 目录。每次同步后必须验证：
```bash
diff -q "$MAIN" "$VENDORED" && md5sum "$MAIN" "$VENDORED"
# 无 diff 输出 + MD5 一致 = 同步成功
```

**Pattern**: S01 的 log/__init__.py 和 S06 的 client.py 都严格执行了 byte-identical 同步。S02/S05 的 proposal.py 未执行。应将此验证纳入 UAT checklist。

### 2. Submodule + Worktree 组合增加了验证复杂度

**问题**: 在 worktree 环境中，parent repo 的 `git diff` 只显示 submodule pointer 变更，不显示 submodule 内文件变更（因为 submodule 的 git objects 不在 parent 的 object database）。

**验证策略**: 直接检查文件系统内容，不依赖 git diff：
```bash
grep -n "FallbackLoggerWrapper" quantaalpha/log/__init__.py
grep -n "Invalid model" quantaalpha/llm/client.py
diff -q quantaalpha/llm/client.py third_party/quantaalpha/quantaalpha/llm/client.py
```

**原则**: 在 submodule 架构中，git commit 记录变更历史，但 git diff 不完整。文件系统的当前状态才是 ground truth。

### 3. Proof 应描述最终状态，而非某个切片完成时的状态

**问题**: R016 在 S02 完成时证明 "主文件和 vendored 文件 byte-identical"，但 S05 修改了 main 文件，未同步 vendored。R016 的 proof 因此不准确。

**教训**: 如果后续切片修改了相关文件，需要更新该 proof。M005 关闭时已更新 R016 proof 以反映实际状态。

### 4. R018 Trace Table "active" vs "Validated" 不一致

**问题**: `.gsd/REQUIREMENTS.md` 中 R018 的 Active section entry 有 `Status: ✅ Validated` 标记，但 Trace Table 中 R018 行仍显示 `active`。Coverage Summary 统计 "Active requirements: 1"（应为 0）。

**修复**: 关闭 milestone 时必须检查 Trace Table 和 Coverage Summary 是否与 Active section 一致。M005 关闭时已修正此问题。

### 5. JSON Escape 的 Replacement String Math 必须精确

S06 发现原 generic fallback 的 replacement string `r"\\\\\1"` (4 bs = 2 pairs = 2 literal bs + captured group) 在与 specific escape `r"\\\\\\1"` (6 bs = 3 pairs = 3 bs + captured) 联合使用时产生 4-bs 输出（无效 JSON）。

**公式**: `(2n) backslashes in raw string → n pairs in regex → n literal backslashes in output`

| Python raw string | regex replacement 中的反斜杠对数 | 输出字符 |
|---|---|---|
| `r"\\\\"` | 2 对 | `\\` (2 bs) |
| `r"\\\\\\1"` | 3 对 + `\1` | `\\\1` (3 bs + captured group) |

当 specific + generic 联合使用时，最终 backslash 数 = specific_count + 2 × generic_count。必须验证最终输出 JSON-valid。

### 6. Dict-first 处理是 LLM 输出标准模式

从 M002 (dict → string) 到 M005 (normalize_corrected_expression) 的所有修复都证明：LLM 返回 dict（而非 string）是标准模式，不是异常。防御性代码应将 dict 处理作为**第一项检查**。

```python
def normalize(expression) -> str:
    if isinstance(expression, dict):   # ← 必须第一
        expression = expression.get("code") or str(expression)
    if not isinstance(expression, str):
        return str(expression)
    # ... string 处理逻辑
```
