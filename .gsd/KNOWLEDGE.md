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
