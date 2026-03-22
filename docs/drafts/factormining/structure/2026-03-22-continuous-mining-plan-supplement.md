# QuantaAlpha 持续因子挖掘体系：代码级差距验证与补充规划

> **文档性质**: 对 `2026-03-22-quantaalpha-continuous-mining-comprehensive-plan.md` 的代码级深度审查与补充  
> **审查日期**: 2026-03-22  
> **对比基线**: DECISIONS.md (D001-D009) + 全部源码  
> **审查范围**: quantaalpha 完整代码库（llm/, factors/, backtest/, pipeline/, core/, continuous/, configs/）

---

## 1. 原规划准确性验证（逐条代码交叉验证）

下面对原综合规划中引用的每一处代码落点进行实际验证，标注 ✅（准确）、⚠️（部分准确需修正）、❌（有误）。

### 1.1 [P0] 配置解锁即用层

#### 1.1.1 排除北交所 — `universe.py:22`

**验证结果**: ⚠️ 部分准确

原规划建议直接修改 `configs/backtest.yaml` 中的 `exclude_markets: []` → `["bj"]`。

实际代码结构：

```yaml
# configs/backtest.yaml 第43-53行
data:
  stock_filter:
    enabled: false          # ← 注意！这里是 false
    exclude_markets: []     # ← 原规划只关注这里
    exclude_st: false
    min_list_days: 0
```

`filter_by_market()` 函数在 `universe.py:34-38` 确实已实现，逻辑正确。但它只有在 `stock_filter.enabled: true` 时才会被调用路径触达。

**修正后的完整操作**:
```yaml
data:
  stock_filter:
    enabled: true                # 必须同时改为 true
    exclude_markets: ["bj"]      # 排除北交所
    exclude_st: true             # 顺便排除 ST 股票（建议）
    min_list_days: 60            # 上市不满60天也排除（建议）
```

#### 1.1.2 多时间不连续区间回测 — `validation.py:27-62`

**验证结果**: ✅ 准确

`validation.py` 有完整的多周期验证逻辑链：

| 函数 | 行号 | 功能 |
|------|------|------|
| `validate_multi_period_config()` | L16-36 | 校验配置、去重期间名称 |
| `build_period_configs()` | L39-58 | 将基础配置按 periods 展开为多份独立配置 |
| `aggregate_period_metrics()` | L61-83 | 汇聚各期指标、计算稳定性得分 |
| `compute_stability_score()` | L86-116 | 综合 IC/Rank IC/IR 计算 [0,1] 稳定性分数 |

`backtest.yaml` 中已有占位配置:
```yaml
multi_period_validation:
  enabled: false     # 改为 true 即可激活
  fail_fast: true
  periods: []        # 需要填入具体时间段
```

**建议的具体时间段配置**（跨牛熊周期、覆盖不同市场环境）:

```yaml
multi_period_validation:
  enabled: true
  fail_fast: false    # 改为 false，一个周期失败不中止其他周期
  periods:
    - name: "2017_2018_去杠杆"
      train: ["2015-01-01", "2016-12-31"]
      valid: ["2017-01-01", "2017-06-30"]
      test:  ["2017-07-01", "2018-12-31"]

    - name: "2019_2020_结构牛"
      train: ["2017-01-01", "2018-12-31"]
      valid: ["2019-01-01", "2019-06-30"]
      test:  ["2019-07-01", "2020-12-31"]

    - name: "2021_2022_震荡熊"
      train: ["2019-01-01", "2020-12-31"]
      valid: ["2021-01-01", "2021-06-30"]
      test:  ["2021-07-01", "2022-12-31"]

    - name: "2023_2025_复苏"
      train: ["2021-01-01", "2022-12-31"]
      valid: ["2023-01-01", "2023-06-30"]
      test:  ["2023-07-01", "2025-12-26"]
```

这样一个因子必须在去杠杆、结构牛、震荡熊、复苏四个迥异的市场环境中都有效，才能获得高稳定性得分。

---

### 1.2 [P1] 挖掘核心增强层

#### 1.2.1 数据能力感知注入 — `data_capability.py:7-17`

**验证结果**: ⚠️ 部分准确—问题比原规划描述的更严重

原规划说"空有框架，未能送达 LLM 提示词"。实际情况是：

1. `data_capability.py` 有 `render_data_capabilities()` 函数（L64-77），能生成文本摘要
2. 但 **整个 proposal.py 的调用链中从未调用过该函数**
3. `experiment.yaml` 中有 `data_capability_registry.enabled: true`，但**没有任何代码读取此配置**
4. 数据注册仅包含硬编码的 `price_volume` 和 `financial` 两个类别，远不覆盖实际 Parquet 数据

**断裂点精确定位**:

```
proposal.py:AlphaAgentHypothesisGen.prepare_context()
  → 构建 context_dict
    → 有: hypothesis_and_feedback, RAG, hypothesis_output_format, hypothesis_specification
    → 缺: data_capabilities  ← 从未注入
  → prompt 模板 prompts.yaml
    → 有: hypothesis_gen.system_prompt, hypothesis_gen.user_prompt
    → 缺: data_capabilities 占位符  ← 从未定义
```

**完整修复路径**（详见第 3.1 节）。

#### 1.2.2 多模型智能路由 — `client.py` 单线条执行

**验证结果**: ✅ 准确

当前 `client.py` 的模型路由机制：

```python
# client.py L661-671
def get_model_for_task(self, task_type=None, tag=None) -> str:
    if task_type:
        model = self.task_model_map.get(task_type)  # 静态映射
        if model:
            return model
        return self.routing_default or self.chat_model_map.get(tag, self.chat_model)
    return self.routing_default or self.chat_model
```

已有的基础:
- `KNOWN_TASK_TYPES` = `{hypothesis_generation, factor_construction, evaluation_screening, feedback_summarization}`
- `task_model_map` 支持按任务类型路由到不同模型
- `chat_model_map` 支持按标签路由

缺失的：
- ❌ 没有多 Provider 实例支持（一个 `APIBackend` 只能用一组 API key/base_url）
- ❌ 没有 round-robin 或 weighted 负载分担
- ❌ 没有 fanout（同一请求发送给多个模型取最优）
- ❌ 没有 Provider 健康状态追踪和自动降级
- ❌ 没有使用 coding 模型修复 JSON 的回路

---

### 1.3 [P2] 知识沉淀强化层

#### 1.3.1 因子库知识流 — `library.py`

**验证结果**: ⚠️ 比原规划描述的稍好一些

原规划说"只能存结果"，实际上 `library.py` 已经具备:

| 已有能力 | 代码位置 |
|----------|----------|
| 因子 CRUD + 原子锁写入 | `upsert_factor()`, `_save()` with `fcntl.flock()` |
| `parent_trajectory_ids` 字段 | `add_factors_from_experiment()` L182 |
| 状态机 (pending→active→degraded→stale→deprecated) | `status_rules.py` 完整实现 |
| 审计追踪 | `_append_audit_entry()` + `get_audit_trail()` |
| 复验候选选择 | `select_revalidation_candidates()` L515-545 |
| 基础字段推断 | `_infer_fields()` + `_infer_dimensions()` |
| 缓存状态检查 | `check_cache_status()` + `warm_cache_from_json()` |
| 多周期验证结果入库 | `apply_validation_result()` L479-513 |
| 摘要统计 | `get_summary()` L633-680 |

**确实缺失的**:
- ❌ 缺少对 Parquet 数据源的**依赖拓扑图谱** — `_infer_dimensions()` 只做关键词匹配，不知道因子实际读了哪个 `.parquet` 文件
- ❌ 缺少因子之间的**相似度/相关性矩阵** — 无法识别因子冗余
- ❌ 缺少 **Few-shot 导出接口** — Active 因子无法被格式化为 LLM prompt 的示例
- ❌ 缺少因子的**版本历史** — 同一 factor_id 被覆写时旧的 backtest_results 丢失

---

### 1.4 [P3] 24H 自治中枢层

#### 1.4.1 持续研究外插模块

**验证结果**: ✅ 准确

- `quantaalpha/continuous/` 目录下**仅有 `__pycache__/`，无任何 Python 源文件**
- 没有 Orchestrator、Trigger、Observability 的任何实现
- `loop.py` 的 `AlphaAgentLoop` 有 `stop_event` 支持，但没有 checkpoint/resume
- 没有定时调度、事件监听、磁盘/API 资源管理

---

## 2. DECISIONS.md 对齐分析

### 2.1 已覆盖的决策

| Decision | 原规划覆盖情况 |
|----------|---------------|
| D004 (ADR-003 外插模块边界) | ✅ P3 Phase 3 明确提及 |
| D005 (ADR-001 持续研究架构) | ✅ Phase 1 明确提及批准 |

### 2.2 未覆盖的决策

| Decision | 遗漏内容 |
|----------|---------|
| D006-D009 (M001 Bug修复) | M001 修复了 4 个高优先级 Bug：JSON 解析死循环、空响应无限重试、dict.replace 调用错误、因子构建阶段错误。`KNOWLEDGE.md` 记录了这些经验教训。**原规划完全未引用这些经验**，特别是 JSON 修复和空响应处理的教训，直接关系到 P1 多模型路由中 coding 模型修复 JSON 的设计 |

---

## 3. 补充规划（原规划未覆盖的 7 个关键项）

### 3.1 【补充 S1】数据能力注入的"最后一公里"完整实现

**问题**: `data_capability.py` → LLM prompt 的调用路径完全断开。

**改造分两步**:

#### 步骤 A: 动态注册表替代硬编码

当前 `DATA_CAPABILITIES` 是硬编码字典，需要改为**自动扫描 Parquet 目录**动态生成:

```python
# factors/data_capability.py — 新增 auto_discover_capabilities()

import polars as pl
from pathlib import Path

def auto_discover_capabilities(
    data_dir: str = "/home/quan/testdata/aspipe_v4/data",
    output_path: str | None = None,
) -> dict[str, dict]:
    """扫描 Parquet 目录，自动生成数据能力注册表"""
    registry = {}
    data_root = Path(data_dir)
    
    for parquet_dir in sorted(data_root.iterdir()):
        if not parquet_dir.is_dir():
            continue
        parquet_files = list(parquet_dir.glob("*.parquet"))
        if not parquet_files:
            continue
        
        # 读取第一个文件的 schema
        sample = parquet_files[0]
        schema = pl.scan_parquet(sample).schema
        fields = [f"${col}" for col in schema.keys() 
                  if col not in ("date", "datetime", "symbol", "code", "ts_code", "ann_date")]
        
        # 推断频率和时滞
        freq = "quarterly" if "ann_date" in schema else "daily"
        lag_days = 45 if freq == "quarterly" else 0
        join_mode = "forward_fill" if freq == "quarterly" else "same_day"
        
        # 推断因子提示
        name = parquet_dir.name
        hints = _infer_factor_hints(name, fields)
        
        registry[name] = {
            "fields": fields,
            "freq": freq,
            "lag_days": lag_days,
            "join_mode": join_mode,
            "factor_hints": hints,
            "source_path": str(parquet_dir),
            "file_count": len(parquet_files),
            "pit_field": "ann_date" if "ann_date" in schema else None,
        }
    
    if output_path:
        import json
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(registry, f, indent=2, ensure_ascii=False)
    
    return registry


def _infer_factor_hints(name: str, fields: list[str]) -> list[str]:
    """根据目录名和字段推断因子研究方向"""
    hints = []
    name_lower = name.lower()
    if any(k in name_lower for k in ("income", "balance", "cashflow", "financial")):
        hints.extend(["fundamental", "quality", "value"])
    if any(k in name_lower for k in ("money", "flow")):
        hints.extend(["flow", "sentiment", "institutional"])
    if any(k in name_lower for k in ("daily", "price", "kline")):
        hints.extend(["momentum", "reversal", "volatility", "liquidity"])
    if any(k in name_lower for k in ("margin", "pledge", "holder")):
        hints.extend(["leverage", "ownership", "event"])
    return hints or ["general"]
```

#### 步骤 B: 在 proposal prompt 中注入数据能力

```python
# factors/proposal.py — AlphaAgentHypothesisGen.prepare_context() 修改

from quantaalpha.factors.data_capability import render_data_capabilities, get_data_capabilities

def prepare_context(self, trace, history_limit=DEFAULT_HISTORY_LIMIT):
    # ... 现有代码 ...
    
    # 新增: 注入数据能力声明
    data_capabilities_text = render_data_capabilities()
    
    context_dict = {
        "hypothesis_and_feedback": hypothesis_and_feedback,
        "data_capabilities": data_capabilities_text,    # ← 新增
        "RAG": None,
        "hypothesis_output_format": qa_prompt_dict["hypothesis_output_format"],
        "hypothesis_specification": qa_prompt_dict["hypothesis_specification"],
    }
    return context_dict, True
```

同时在 `prompts/prompts.yaml` 的 `hypothesis_gen.system_prompt` 模板中增加:

```yaml
hypothesis_gen:
  system_prompt: |
    ...existing prompt...
    
    {% if data_capabilities %}
    ## Available Data Dimensions
    The following data sources are available for factor construction. 
    You MUST only use fields from these sources.
    For quarterly financial data, respect the lag_days constraint to avoid look-ahead bias.
    
    {{ data_capabilities }}
    {% endif %}
```

**估算工作量**: 1-2 天。代码量小，但 prompt 调优需要迭代测试。

---

### 3.2 【补充 S2】ProviderPool 多模型管理架构

**问题**: 当前 `APIBackend` 依赖全局 `LLM_SETTINGS` 单例配置，无法支持多 Provider 并存。

**设计原则**: 不修改 `APIBackend` 内部逻辑，在其上层封装 `ProviderPool`。

#### 配置格式

```yaml
# configs/experiment.yaml — 在 llm 段下新增

llm:
  providers:
    - name: "deepseek-r1"
      role: "hypothesis"          # 用于假说生成
      api_key_env: "DEEPSEEK_API_KEY"
      base_url: "https://api.deepseek.com/v1"
      model: "deepseek-reasoner"
      weight: 3                   # 轮询权重
      max_rpm: 10                 # 每分钟最大请求数
      
    - name: "gpt4o"
      role: "hypothesis"          # 也用于假说生成（fanout 场景）
      api_key_env: "OPENAI_API_KEY"
      base_url: "https://api.openai.com/v1"
      model: "gpt-4o"
      weight: 2
      max_rpm: 30

    - name: "qwen-coder"
      role: "json_repair"         # 专门修复 JSON
      api_key_env: "QWEN_API_KEY"
      base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
      model: "qwen-coder-plus"
      weight: 1
      max_rpm: 60

    - name: "glm4-flash"
      role: "screening"           # 初筛和打分
      api_key_env: "GLM_API_KEY"
      base_url: "https://open.bigmodel.cn/api/paas/v4"
      model: "glm-4-flash"
      weight: 5
      max_rpm: 100

  routing:
    hypothesis_generation: ["deepseek-r1", "gpt4o"]     # fanout: 同时发两家取较优
    factor_construction: ["deepseek-r1"]                  # 单一: 构因子用推理模型
    json_repair: ["qwen-coder"]                           # 单一: JSON 修复用代码模型
    evaluation_screening: ["glm4-flash"]                  # 单一: 初筛用便宜模型
    feedback_summarization: ["gpt4o", "deepseek-r1"]      # 轮询: 分担调用压力
    
  strategy:
    hypothesis_generation: "fanout_best"    # 多路并发取最优
    factor_construction: "single"           # 单一 provider
    json_repair: "single"
    evaluation_screening: "single"
    feedback_summarization: "round_robin"   # 轮询分担压力
```

#### 核心类设计

```python
# llm/provider_pool.py — 新增

import os
import time
import threading
from dataclasses import dataclass, field
from typing import Literal
from quantaalpha.llm.client import APIBackend

@dataclass
class ProviderConfig:
    name: str
    role: str
    api_key_env: str
    base_url: str
    model: str
    weight: int = 1
    max_rpm: int = 60

@dataclass
class ProviderHealth:
    name: str
    consecutive_failures: int = 0
    last_failure_time: float = 0
    total_requests: int = 0
    total_tokens: int = 0
    is_healthy: bool = True
    cooldown_until: float = 0    # 失败后冷却到何时

class ProviderPool:
    def __init__(self, config: dict):
        self.providers: dict[str, ProviderConfig] = {}
        self.backends: dict[str, APIBackend] = {}
        self.health: dict[str, ProviderHealth] = {}
        self.routing: dict[str, list[str]] = config.get("routing", {})
        self.strategy: dict[str, str] = config.get("strategy", {})
        self._rr_counters: dict[str, int] = {}  # round-robin 计数器
        self._lock = threading.Lock()
        
        for p in config.get("providers", []):
            pc = ProviderConfig(**p)
            self.providers[pc.name] = pc
            self.health[pc.name] = ProviderHealth(name=pc.name)
            # 每个 provider 独立初始化 APIBackend
            api_key = os.environ.get(pc.api_key_env, "")
            self.backends[pc.name] = APIBackend(
                chat_api_key=api_key,
                chat_model=pc.model,
            )
    
    def get_backend(self, task_type: str) -> APIBackend:
        """按任务类型路由到一个 provider"""
        strategy = self.strategy.get(task_type, "single")
        candidates = self._get_healthy_candidates(task_type)
        
        if not candidates:
            raise RuntimeError(f"No healthy provider for task_type={task_type}")
        
        if strategy == "round_robin":
            return self._round_robin(task_type, candidates)
        else:
            return self.backends[candidates[0]]
    
    def fanout(self, task_type: str) -> list[APIBackend]:
        """返回所有该任务类型的 backends，用于并行调用"""
        candidates = self._get_healthy_candidates(task_type)
        return [self.backends[c] for c in candidates]
    
    def report_success(self, provider_name: str, tokens_used: int = 0):
        h = self.health[provider_name]
        h.consecutive_failures = 0
        h.total_requests += 1
        h.total_tokens += tokens_used
        h.is_healthy = True
    
    def report_failure(self, provider_name: str):
        h = self.health[provider_name]
        h.consecutive_failures += 1
        h.last_failure_time = time.time()
        h.total_requests += 1
        if h.consecutive_failures >= 3:
            h.is_healthy = False
            h.cooldown_until = time.time() + 300  # 冷却 5 分钟
    
    def _get_healthy_candidates(self, task_type: str) -> list[str]:
        names = self.routing.get(task_type, [])
        now = time.time()
        healthy = []
        for n in names:
            h = self.health.get(n)
            if h and (h.is_healthy or now > h.cooldown_until):
                if not h.is_healthy and now > h.cooldown_until:
                    h.is_healthy = True  # 冷却结束，重新尝试
                healthy.append(n)
        return healthy
    
    def _round_robin(self, task_type: str, candidates: list[str]) -> APIBackend:
        with self._lock:
            idx = self._rr_counters.get(task_type, 0)
            provider_name = candidates[idx % len(candidates)]
            self._rr_counters[task_type] = idx + 1
        return self.backends[provider_name]
    
    def get_token_usage_report(self) -> dict:
        """返回各 provider 的 token 使用情况"""
        return {
            name: {
                "total_requests": h.total_requests,
                "total_tokens": h.total_tokens,
                "is_healthy": h.is_healthy,
                "consecutive_failures": h.consecutive_failures,
            }
            for name, h in self.health.items()
        }
```

#### 在 pipeline 中集成

```python
# pipeline/loop.py — AlphaAgentLoop.__init__() 中

# 替代原来的 APIBackend() 单例调用
from quantaalpha.llm.provider_pool import ProviderPool

pool_config = experiment_config.get("llm", {})
if pool_config.get("providers"):
    self.provider_pool = ProviderPool(pool_config)
else:
    self.provider_pool = None  # 降级到单一 APIBackend
```

**估算工作量**: 3-5 天。`ProviderPool` 本身 1-2 天，集成到 proposal/feedback/coder 各调用点 2-3 天。

---

### 3.3 【补充 S3】Coding 模型修复 JSON 的闭环流程

**问题**: 原规划提到用 coding 模型做 JSON 修复，但没有定义完整流程。

当前 `client.py` 的 `robust_json_parse()` 有 4 层纯规则修复策略。新增的 coding 模型修复应作为**第 5 层**,在规则修复全部失败后触发：

```
策略 1: 直接 json.loads()
  ↓ 失败
策略 2: 提取 ```json ``` code block
  ↓ 失败
策略 3: balanced brace 提取 + LaTeX escape + 尾逗号修复
  ↓ 失败
策略 4: 宽松正则提取
  ↓ 失败
**策略 5 [新增]: coding 模型修复**
  ↓ 失败
抛出 JSONDecodeError
```

```python
# llm/client.py — robust_json_parse() 末尾新增

def robust_json_parse(text: str, max_retries: int = 3, 
                      provider_pool=None) -> dict:
    # ... 现有策略 1-4 ...
    
    # 策略 5: coding 模型修复
    if provider_pool:
        try:
            repair_backend = provider_pool.get_backend("json_repair")
            repair_prompt = (
                "Fix the following broken JSON and return ONLY the valid JSON object. "
                "Do not add any explanation.\n\n"
                f"```\n{text[:4000]}\n```"  # 截断防止 token 超限
            )
            repaired = repair_backend.build_messages_and_create_chat_completion(
                repair_prompt,
                system_prompt="You are a JSON repair specialist. Return only valid JSON.",
            )
            return json.loads(repaired.strip())
        except Exception:
            pass
    
    raise json.JSONDecodeError(...)
```

---

### 3.4 【补充 S4】因子库 Few-shot 导出与智能采样

**问题**: 原规划提到让 Active 因子作为 Few-shot，但缺少选择策略。

```python
# factors/library.py — FactorLibraryManager 新增方法

def export_few_shot_examples(
    self,
    direction: str | None = None,
    max_examples: int = 3,
    min_stability: float = 0.5,
    max_token_budget: int = 2000,
    exclude_factor_ids: set[str] | None = None,
) -> str:
    """导出 Active 因子作为 LLM 的 few-shot 示例"""
    candidates = []
    for fid, entry in self.data.get("factors", {}).items():
        if exclude_factor_ids and fid in exclude_factor_ids:
            continue
        eval_data = entry.get("evaluation", {})
        if eval_data.get("status") != "active":
            continue
        stability = eval_data.get("stability_score")
        if stability is None or stability < min_stability:
            continue
        
        # 按方向相关度排序（如果提供了 direction）
        relevance = 0.0
        if direction:
            hypothesis = entry.get("metadata", {}).get("hypothesis", "")
            desc = entry.get("factor_description", "")
            # 简单关键词重叠度
            dir_tokens = set(direction.lower().split())
            hyp_tokens = set(hypothesis.lower().split()) | set(desc.lower().split())
            overlap = len(dir_tokens & hyp_tokens)
            relevance = overlap / max(len(dir_tokens), 1)
        
        candidates.append({
            "factor_id": fid,
            "relevance": relevance,
            "stability": stability,
            "entry": entry,
        })
    
    # 按 (相关度, 稳定性) 降序排序
    candidates.sort(key=lambda x: (x["relevance"], x["stability"]), reverse=True)
    
    # 选取 top-N 并控制 token 预算
    examples = []
    total_chars = 0
    for c in candidates[:max_examples * 2]:  # 多选一些备选
        text = _format_factor_example(c["entry"])
        if total_chars + len(text) > max_token_budget * 3:  # 粗略 1 token ≈ 3 chars
            break
        examples.append(text)
        total_chars += len(text)
        if len(examples) >= max_examples:
            break
    
    if not examples:
        return ""
    
    header = "## Reference: Active High-Quality Factors\n"
    header += "These factors have proven stable across multiple market periods.\n\n"
    return header + "\n---\n".join(examples)


def _format_factor_example(entry: dict) -> str:
    """格式化单个因子为 few-shot 示例"""
    name = entry.get("factor_name", "")
    expr = entry.get("factor_expression", "")
    desc = entry.get("factor_description", "")
    stability = entry.get("evaluation", {}).get("stability_score", "N/A")
    
    # 从 backtest_results 提取关键指标
    bt = entry.get("backtest_results", {})
    ic = bt.get("IC", "N/A")
    rank_ic = bt.get("Rank IC", "N/A")
    
    return (
        f"**{name}**\n"
        f"- Expression: `{expr}`\n"
        f"- Description: {desc}\n"
        f"- Metrics: IC={ic}, Rank IC={rank_ic}, Stability={stability}\n"
    )
```

**在 prompt 中使用**:

```python
# factors/proposal.py — prepare_context() 中

few_shot_text = ""
try:
    from quantaalpha.factors.library import FactorLibraryManager
    manager = FactorLibraryManager(str(library_path))
    few_shot_text = manager.export_few_shot_examples(
        direction=self.potential_direction,
        max_examples=3,
        min_stability=0.5,
    )
except Exception:
    pass

context_dict["few_shot_examples"] = few_shot_text
```

---

### 3.5 【补充 S5】异常恢复、幂等性和 Checkpoint 机制

**问题**: 24 小时运行中，进程崩溃会丢失整轮进度。

#### 3.5.1 Checkpoint 机制

```python
# pipeline/checkpoint.py — 新增

import json
import pickle
from pathlib import Path
from datetime import datetime

class LoopCheckpoint:
    """为 AlphaAgentLoop 提供中断恢复能力"""
    
    def __init__(self, checkpoint_dir: str):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
    
    def save(self, loop_state: dict, step_name: str):
        """在每个 pipeline 步骤完成后保存检查点"""
        ckpt = {
            "step_name": step_name,          # 最后完成的步骤
            "timestamp": datetime.now().isoformat(),
            "round_idx": loop_state.get("round_idx", 0),
            "direction_id": loop_state.get("direction_id", 0),
            "trace_len": loop_state.get("trace_len", 0),
        }
        # 文本元数据
        meta_path = self.checkpoint_dir / "checkpoint_meta.json"
        with open(meta_path, "w") as f:
            json.dump(ckpt, f, indent=2)
        
        # 序列化完整状态
        state_path = self.checkpoint_dir / "checkpoint_state.pkl"
        with open(state_path, "wb") as f:
            pickle.dump(loop_state, f)
    
    def load(self) -> dict | None:
        """尝试加载最近的检查点"""
        state_path = self.checkpoint_dir / "checkpoint_state.pkl"
        if not state_path.exists():
            return None
        with open(state_path, "rb") as f:
            return pickle.load(f)
    
    def clear(self):
        """清除检查点（正常完成时调用）"""
        for f in self.checkpoint_dir.glob("checkpoint_*"):
            f.unlink(missing_ok=True)
```

#### 3.5.2 因子版本化

```python
# factors/library.py — _normalize_factor_entry() 中增加 versions 字段

def _normalize_factor_entry(self, factor_entry):
    entry = dict(factor_entry or {})
    # ...现有字段...
    entry.setdefault("versions", [])  # ← 新增: 历史 backtest 版本
    return entry

def add_factors_from_experiment(self, ...):
    # ...现有逻辑...
    
    # 如果因子已存在，保留历史版本
    existing = self.data["factors"].get(factor_id)
    if existing and existing.get("backtest_results"):
        versions = existing.get("versions", [])
        versions.append({
            "backtest_results": existing["backtest_results"],
            "timestamp": existing.get("metadata", {}).get("created_at"),
            "experiment_id": existing.get("metadata", {}).get("experiment_id"),
        })
        # 只保留最近 10 个版本
        factor_entry["versions"] = versions[-10:]
    
    self.data["factors"][factor_id] = factor_entry
```

#### 3.5.3 锁超时

```python
# factors/library.py — _acquire_lock() 改为带超时

import time

def _acquire_lock(self, timeout: int = 30):
    self._ensure_lock_dir()
    lock_file = self._lock_dir / f"{self.library_path.name}.lock"
    lock_fd = open(lock_file, "w")
    start = time.time()
    while True:
        try:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return lock_fd
        except BlockingIOError:
            if time.time() - start > timeout:
                lock_fd.close()
                # 强制清理 stale lock
                logger.warning(f"Lock timeout after {timeout}s, forcing lock acquisition")
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
                return lock_fd
            time.sleep(0.5)
```

---

### 3.6 【补充 S6】Point-in-Time (PIT) 对齐执行层

**问题**: 仅靠 prompt 约束无法阻止 LLM 生成使用未来数据的因子表达式。

#### 核心约束

对于财务数据（如 `balancesheet_vip`, `income_vip`），最关键的约束是:

> **因子在 T 日的值，只能使用 T 日之前已经公告（`ann_date <= T`）的财报数据**

如果 LLM 生成了 `$roe` 这样的表达式，系统在回测时必须自动对齐到最近一个 `ann_date <= trade_date` 的值，而不是直接取最新值。

#### 实现方案

```python
# factors/pit_alignment.py — 新增

import polars as pl
from pathlib import Path
from quantaalpha.factors.data_capability import get_data_capabilities

def apply_pit_alignment(
    factor_df: pl.LazyFrame,    # 包含 date, symbol, factor_val 的因子数据
    data_source: str,           # 数据源名称（如 "income_vip"）
    pit_field: str = "ann_date",
    trade_date_field: str = "date",
) -> pl.LazyFrame:
    """
    对财务数据应用 Point-in-Time 对齐。
    确保 T 日只能看到 ann_date <= T 的数据。
    """
    capabilities = get_data_capabilities()
    source_spec = capabilities.get(data_source, {})
    
    if source_spec.get("freq") != "quarterly":
        return factor_df  # 日频数据不需要 PIT 对齐
    
    lag_days = source_spec.get("lag_days", 0)
    
    # 核心逻辑: 对于每个 (symbol, date)，只取 ann_date <= date - lag_days 的最新记录
    return (
        factor_df
        .filter(pl.col(pit_field) <= pl.col(trade_date_field) - pl.duration(days=lag_days))
        .sort([pl.col("symbol"), pl.col(pit_field)])
        .group_by(["symbol", trade_date_field])
        .last()  # 取每组最后一条 = 最新公告的数据
    )
```

在 `custom_factor_calculator.py` 中集成:

```python
# backtest/custom_factor_calculator.py — calculate_factor() 中

# 在计算因子值之后、返回结果之前
pit_field = data_spec.get("pit_field")
if pit_field:
    result = apply_pit_alignment(result, data_source_name, pit_field=pit_field)
```

---

### 3.7 【补充 S7】24 小时运行资源管理

**问题**: 持续运行会导致磁盘、内存、API 成本不可控。

#### 3.7.1 资源管理模块

```python
# continuous/resource_manager.py — 新增

import os
import shutil
from pathlib import Path
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class ResourceManager:
    """24 小时运行的资源管理"""
    
    def __init__(self, config: dict):
        self.max_disk_gb = config.get("max_disk_gb", 50)
        self.daily_token_budget = config.get("daily_token_budget", 5_000_000)
        self.max_trace_history = config.get("max_trace_history", 50)
        self.max_library_factors = config.get("max_library_factors", 10000)
        self.h5_retention_days = config.get("h5_retention_days", 30)
        
        self._daily_tokens_used = 0
        self._daily_reset_date = datetime.now().date()
    
    def check_disk_space(self, data_dir: str) -> bool:
        """检查磁盘空间是否充足"""
        total, used, free = shutil.disk_usage(data_dir)
        free_gb = free / (1024**3)
        if free_gb < 5:  # 少于 5GB 告警
            logger.warning(f"Low disk space: {free_gb:.1f} GB free")
            return False
        return True
    
    def cleanup_old_h5_files(self, workspace_root: str):
        """清理过期的 result.h5 文件"""
        cutoff = datetime.now() - timedelta(days=self.h5_retention_days)
        cleaned = 0
        for h5 in Path(workspace_root).rglob("result.h5"):
            mtime = datetime.fromtimestamp(h5.stat().st_mtime)
            if mtime < cutoff:
                h5.unlink()
                cleaned += 1
        if cleaned > 0:
            logger.info(f"Cleaned {cleaned} expired result.h5 files")
    
    def check_token_budget(self, tokens_to_use: int) -> bool:
        """检查日 token 预算"""
        today = datetime.now().date()
        if today != self._daily_reset_date:
            self._daily_tokens_used = 0
            self._daily_reset_date = today
        
        if self._daily_tokens_used + tokens_to_use > self.daily_token_budget:
            logger.warning(
                f"Daily token budget exceeded: "
                f"{self._daily_tokens_used}/{self.daily_token_budget}"
            )
            return False
        return True
    
    def record_tokens(self, tokens_used: int):
        self._daily_tokens_used += tokens_used
    
    def should_archive_trace(self, trace_len: int) -> bool:
        """trace 历史超过阈值时建议归档"""
        return trace_len > self.max_trace_history
```

#### 3.7.2 资源管理配置

```yaml
# configs/experiment.yaml — 新增 resource_management 段

resource_management:
  max_disk_gb: 50
  daily_token_budget: 5000000      # 每日 token 预算
  max_trace_history: 50            # trace.hist 最大长度
  max_library_factors: 10000       # 因子库最大条目
  h5_retention_days: 30            # result.h5 保留天数
  cleanup_interval_hours: 6        # 清理间隔
  
  # 因子库膨胀后迁移到 SQLite
  sqlite_migration_threshold: 5000  # 超过此数量触发迁移
```

---

## 4. 完整优先级排序（含补充项）

按实施紧迫度和依赖关系重新排序：

| 优先级 | 编号 | 内容 | 估算工作量 | 依赖项 |
|--------|------|------|-----------|--------|
| **P0** | 原 P0.1 | 排除北交所（含 `stock_filter.enabled`） | 0.5 天 | 无 |
| **P0** | 原 P0.2 | 多时间区间回测配置 | 0.5 天 | 无 |
| **P0.5** | S1 | 数据能力注入最后一公里 | 1-2 天 | 无 |
| **P1** | S4 | 因子库 Few-shot 导出 | 2 天 | 无 |
| **P1** | S2 | ProviderPool 最小实现（round-robin + fallback） | 3-5 天 | 无 |
| **P1** | S3 | Coding 模型 JSON 修复闭环 | 1 天 | S2 |
| **P1** | 原 P1.2 | 多模型 Fanout（在 S2 基础上扩展） | 2 天 | S2 |
| **P2** | S6 | PIT 对齐执行层 | 3 天 | S1 |
| **P2** | 原 P2.1 | 因子依赖拓扑 + 族谱增强 | 3 天 | S1 |
| **P2** | S5 | Checkpoint + 因子版本化 + 锁超时 | 2 天 | 无 |
| **P3** | S7 | 资源管理模块 | 2 天 | 无 |
| **P3** | 原 P3.1 | Orchestrator + Trigger + Observability | 5-7 天 | S2, S5, S7 |

---

## 5. 修订后的实施路线图

### ⚡ Phase 1: 防御与觉察（本周）

```
Day 1:
  [P0] backtest.yaml: exclude_markets + stock_filter.enabled
  [P0] backtest.yaml: 填入 4 个跨周期 multi_period_validation periods
  [P0.5] data_capability.py: 实现 auto_discover_capabilities()

Day 2-3:
  [P0.5] proposal.py: prepare_context() 注入 data_capabilities
  [P0.5] prompts.yaml: 增加 data_capabilities 占位符
  [P1] library.py: 实现 export_few_shot_examples()
  [P1] proposal.py: 注入 few_shot_examples
```

### 🚀 Phase 2: 分层计算与多模型（次周）

```
Day 4-6:
  [P1] llm/provider_pool.py: ProviderPool 核心实现
  [P1] experiment.yaml: providers + routing 配置
  [P1] client.py: robust_json_parse() 增加 coding 模型修复层
  [P1] pipeline 各调用点: 从 APIBackend() → ProviderPool.get_backend()

Day 7-9:
  [P2] factors/pit_alignment.py: PIT 对齐实现
  [P2] custom_factor_calculator.py: 集成 PIT 对齐
  [P2] library.py: 增加 versions 字段 + 因子依赖推断增强
  [P2] pipeline/checkpoint.py: Checkpoint 机制
  [P2] library.py: 锁超时改造
```

### 🔄 Phase 3: 无人值守（第三周起）

```
Day 10-12:
  [P3] continuous/resource_manager.py: 资源管理
  [P3] continuous/orchestrator.py: 调度核心
  [P3] continuous/trigger.py: 数据更新事件监听

Day 13-15:
  [P3] continuous/revalidation.py: 定期复验循环
  [P3] continuous/observability.py: 监控告警
  [P3] 集成测试: 72 小时无人值守跑批验证
```

---

## 6. 与 M001 修复经验的交叉参考

根据 DECISIONS.md D006-D009 和 KNOWLEDGE.md 中 M001 的修复经验:

| M001 教训 | 对本规划的影响 |
|----------|---------------|
| Bug 1: JSON 解析死循环 | S3 的 coding 模型修复必须设置**超时和重试上限**，防止新引入的修复层再次死循环 |
| Bug 2: 空响应无限重试 | S2 的 ProviderPool 需要在 `report_failure()` 中**区分空响应和网络错误**，空响应应立即切换 Provider 而非等待冷却 |
| Bug 4: `dict.replace` 调用错误 | S1 的 `auto_discover_capabilities()` 处理 schema 字段名时需注意类型安全 |
| S03 验证: grep 多行匹配问题 | S5 的 Checkpoint 机制序列化时需注意**含换行符的字段**的 pickle 兼容性 |
