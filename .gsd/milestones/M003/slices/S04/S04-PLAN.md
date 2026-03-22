# S04: ProviderPool 多模型管理架构

**触发决策**: D016、D019 (M001 教训转化为设计约束)

**问题**: 当前 `client.py` 单线条执行，没有多 Provider 实例支持、负载分担、健康状态追踪和自动降级。M001 Bug 2（空响应无限重试）暴露了单 Provider 模式的脆弱性。

**参考文档**:
- `docs/drafts/factormining/structure/2026-03-22-continuous-mining-plan-supplement.md` 第 3.2 节
- `quantaalpha/llm/client.py`
- DECISIONS.md D016, D019

---

## 目标

实现 ProviderPool 封装层，支持：
1. 多 Provider 并存（不同模型/厂商）
2. 按任务类型路由（hypothesis/coding/screening）
3. Fanout 并发取最优
4. 健康状态监控与自动降级
5. Token 使用追踪

---

## 成功标准

- [ ] ProviderPool 类实现完整 API
- [ ] 支持 round_robin、single、fanout_best 三种路由策略
- [ ] Provider 健康状态追踪（连续失败、冷却期）
- [ ] 空响应立即切换 Provider（M001 教训 D019）
- [ ] JSON 修复任务路由到 coding 模型
- [ ] experiment.yaml 支持 providers/routing 配置
- [ ] 兼容现有 APIBackend 调用模式

---

## 设计约束（来自 D019）

**必须遵守的 M001 教训**：

1. **重试必须有上限**: ProviderPool 内部重试次数 ≤ 3 次
2. **空响应立即切换**: 空响应不进入冷却期，立即路由到下一个 Provider
3. **冷却期机制**: 连续 3 次失败后进入 5 分钟冷却
4. **Token 追踪**: 每次调用记录 token 使用量
5. **类型安全检查**: 处理 schema 字段时验证数据类型

---

## 任务拆分

### T01: 实现 ProviderPool 核心类
**文件**: `quantaalpha/llm/provider_pool.py` (新建)
**估算**: 6h

类结构：
```python
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
    cooldown_until: float = 0

class ProviderPool:
    def __init__(self, config: dict):
        # 初始化 providers、backends、health 状态

    def get_backend(self, task_type: str) -> APIBackend:
        # 按策略返回单个 backend

    def fanout(self, task_type: str) -> list[APIBackend]:
        # 返回所有符合条件的 backends

    def report_success(self, provider_name: str, tokens_used: int = 0):
        # 更新健康状态

    def report_failure(self, provider_name: str, error_type: str = "network"):
        # 更新健康状态，区分空响应和网络错误

    def _get_healthy_candidates(self, task_type: str) -> list[str]:
        # 根据冷却期和空响应规则筛选候选

    def _round_robin(self, task_type: str, candidates: list[str]) -> APIBackend:
        # 加权轮询实现

    def get_token_usage_report(self) -> dict:
        # 返回 token 使用情况
```

**验收**:
- [ ] ProviderPool 初始化成功
- [ ] get_backend 按 task_type 路由正确
- [ ] fanout 返回多个 backends
- [ ] report_success/report_failure 更新健康状态
- [ ] 连续失败进入冷却期
- [ ] 空响应不进入冷却期，立即切换

### T02: 设计 experiment.yaml 配置格式
**文件**: `configs/experiment.yaml` (新增 llm.providers 段)
**估算**: 2h

配置结构：
```yaml
llm:
  providers:
    - name: "deepseek-r1"
      role: "hypothesis"
      api_key_env: "DEEPSEEK_API_KEY"
      base_url: "https://api.deepseek.com/v1"
      model: "deepseek-reasoner"
      weight: 3
      max_rpm: 10
    - name: "gpt4o"
      role: "hypothesis"
      api_key_env: "OPENAI_API_KEY"
      base_url: "https://api.openai.com/v1"
      model: "gpt-4o"
      weight: 2
    - name: "qwen-coder"
      role: "json_repair"
      api_key_env: "QWEN_API_KEY"
      model: "qwen-coder-plus"
    - name: "glm4-flash"
      role: "screening"
      api_key_env: "GLM_API_KEY"
      model: "glm-4-flash"
      weight: 5

  routing:
    hypothesis_generation: ["deepseek-r1", "gpt4o"]
    factor_construction: ["deepseek-r1"]
    json_repair: ["qwen-coder"]
    evaluation_screening: ["glm4-flash"]
    feedback_summarization: ["gpt4o", "deepseek-r1"]

  strategy:
    hypothesis_generation: "fanout_best"  # 多路并发取最优
    factor_construction: "single"
    json_repair: "single"
    evaluation_screening: "single"
    feedback_summarization: "round_robin"  # 轮询分担压力
```

**验收**:
- [ ] YAML 语法正确
- [ ] 包含必需字段：name, role, api_key_env, base_url, model
- [ ] routing 映射已知 task_type
- [ ] strategy 支持 single/round_robin/fanout_best

### T03: 集成到 pipeline/loop.py
**文件**: `quantaalpha/pipeline/loop.py`
**估算**: 3h

修改 `AlphaAgentLoop.__init__()`:
```python
from quantaalpha.llm.provider_pool import ProviderPool

pool_config = experiment_config.get("llm", {})
if pool_config.get("providers"):
    self.provider_pool = ProviderPool(pool_config)
else:
    self.provider_pool = None  # 降级到单一 APIBackend
```

**验收**:
- [ ] 有 providers 配置时启用 ProviderPool
- [ ] 无 providers 配置时降级到 APIBackend
- [ ] 现有代码不破坏

### T04: 实现 fanout_best 策略
**文件**: `quantaalpha/llm/provider_pool.py`
**估算**: 4h

```python
def fanout_best(
    self,
    task_type: str,
    prompt: str,
    system_prompt: str = None,
    timeout: int = 60,
) -> dict:
    """并发调用多个 Provider，返回最优结果"""
    import concurrent.futures

    backends = self.fanout(task_type)
    results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(backends)) as executor:
        futures = {
            executor.submit(
                self._call_with_timeout,
                backend,
                prompt,
                system_prompt,
                timeout,
            ): name
            for name, backend in backends.items()
        }

        for future in concurrent.futures.as_completed(futures):
            name = futures[future]
            try:
                result = future.result()
                results.append((name, result, self._score_result(result)))
                self.report_success(name, result.get("tokens", 0))
            except Exception:
                self.report_failure(name, error_type="network")

    if not results:
        raise RuntimeError(f"All providers failed for task_type={task_type}")

    best = max(results, key=lambda x: x[2])
    return best[1]
```

**验收**:
- [ ] 并发调用多个 Provider
- [ ] 任一成功即返回最优结果
- [ ] 所有失败才抛出异常

### T05: 添加单元测试
**文件**: `tests/llm/test_provider_pool.py` (新建)
**估算**: 3h

测试用例：
1. ProviderPool 初始化
2. get_backend 路由正确
3. round_robin 轮询均衡
4. 健康状态冷却机制
5. 空响应立即切换（D019 约束）
6. 连续失败进入冷却
7. Token 追踪正确

**验收**:
- [ ] 所有测试用例通过
- [ ] 包含 D019 约束验证

### T06: 手动验证 ProviderPool
**估算**: 3h

验证：
1. ProviderPool 正确加载两个 Provider
2. 第一个 Provider 返回空响应时立即切换到第二个
3. 第二个 Provider 连续失败 3 次后进入冷却
4. Token 追踪正确

**验收**:
- [ ] 空响应切换日志可见
- [ ] 冷却期触发日志可见
- [ ] 正常运行后可从第一个 Provider 恢复

---

## 关键实现细节

### 空响应 vs 网络错误的区分
```python
def report_failure(self, provider_name: str, error_type: str = "network"):
    h = self.health[provider_name]

    if error_type == "empty_response":
        # M001 教训：空响应立即切换，不进入冷却
        h.total_requests += 1
        return  # 不增加 consecutive_failures

    h.consecutive_failures += 1
    if h.consecutive_failures >= 3:
        h.is_healthy = False
        h.cooldown_until = time.time() + 300  # 冷却 5 分钟
```

---

## 依赖关系

**输入**:
- S01 数据能力注册表（用于配置验证）
- experiment.yaml 配置格式

**输出到 S05**:
- ProviderPool 实例
- get_backend("json_repair") 路由能力
