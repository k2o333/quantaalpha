# T01: ProviderPool 核心类实现

**Slice:** S04 — ProviderPool 核心实现 (S2/D016)
**Milestone:** M003

## Description

实现 `quantaalpha/llm/provider_pool.py`，包含：
- `ProviderConfig` 和 `ProviderHealth` dataclass
- `ProviderPool` 类：三种路由策略（single/round_robin/fanout_best）、健康状态机、Token 追踪
- 严格落实 D019 约束：空响应立即切换，网络错误增加 failure_count 进入冷却

## Steps

1. **创建 provider_pool.py 文件结构**
   在 `third_party/quantaalpha/quantaalpha/llm/provider_pool.py` 创建文件，添加必要的 import（dataclass, time, logging, concurrent.futures, openai 例外处理）

2. **实现 ProviderConfig dataclass**
   定义字段：name、role、api_key_env、base_url、model、weight（默认1）、max_rpm（默认60）
   提供 `from_dict(cls, d)` 类方法从字典构造

3. **实现 ProviderHealth dataclass**
   定义字段：name、consecutive_failures（默认0）、last_failure_time（默认0.0）、total_requests（默认0）、total_tokens（默认0）、is_healthy（默认True）、cooldown_until（默认0.0）

4. **实现 ProviderPool.__init__()**
   接收 config dict（来自 experiment.yaml 的 llm.provider_pool 段）
   解析 providers、routing、strategy 配置
   初始化 self.providers: dict[str, ProviderConfig]、self.health: dict[str, ProviderHealth]
   self.role_to_providers: dict[str, list[str]]（task_type → [provider_names]）
   self.strategy: dict[str, str]（task_type → strategy name）
   self._round_robin_index: dict[str, int]（用于 round_robin 轮询）

5. **实现 get_backend(task_type) → APIBackend**
   调用 _get_healthy_candidates(task_type) 获取候选列表
   根据 strategy[task_type] 选择：
   - "fanout_best" → 调用 fanout_best() 返回最优
   - "round_robin" → round_robin() 加权轮询
   - 默认 → single() 返回第一个候选

6. **实现 _get_healthy_candidates(task_type) → list[str]**
   从 role_to_providers 获取该 task_type 的所有 provider names
   过滤条件：is_healthy=True AND (cooldown_until==0 OR cooldown_until < time.time())
   返回过滤后的列表

7. **实现 report_success(provider_name, tokens_used=0)**
   更新 health[provider_name]：consecutive_failures=0, total_requests+=1, total_tokens+=tokens_used
   如果之前是 unhealthy，标记为 healthy

8. **实现 report_failure(provider_name, error_type) — D019 核心约束**
   ```python
   if error_type == "empty_response":
       # M001教训：空响应立即切换，不增加failure_count，不进入冷却
       health[provider_name].total_requests += 1
       logger.warning(f"Provider {provider_name} returned empty, switching immediately")
       return
   # 网络错误
   health[provider_name].consecutive_failures += 1
   health[provider_name].last_failure_time = time.time()
   if health[provider_name].consecutive_failures >= 5:
       health[provider_name].is_healthy = False
       health[provider_name].cooldown_until = time.time() + 300
       logger.warning(f"Provider {provider_name} marked unhealthy, cooldown until {health[provider_name].cooldown_until}")
   elif health[provider_name].consecutive_failures >= 3:
       # degraded但未完全unhealthy
       logger.warning(f"Provider {provider_name} degraded (failures={health[provider_name].consecutive_failures})")
   ```

9. **实现 call_with_fallback(messages, task_type, **kwargs) → str**
   内部调用 get_backend(task_type) 获取 backend
   调用 backend.build_messages_and_create_chat_completion(messages, **kwargs)
   检查返回值：如果为空，调用 report_failure(name, "empty_response") 并抛出 EmptyResponseError 供外层处理
   成功则调用 report_success(name, tokens)
   返回响应字符串

10. **实现 fanout_best(messages, task_type, timeout=60, **kwargs) → str**
    使用 concurrent.futures.ThreadPoolExecutor 并发调用所有健康候选
    任一成功立即返回（first valid response）
    所有失败则抛出 AllProvidersFailedError

11. **实现 get_token_usage_report() → dict**
    返回格式：{"total_tokens": int, "total_requests": int, "providers": {name: {"tokens": int, "requests": int, "is_healthy": bool}}}

12. **实现 get_health_summary() → dict**
    返回格式：{name: {"consecutive_failures": int, "is_healthy": bool, "cooldown_until": float, "last_failure_time": float}}

13. **实现模块级单例 provider_pool**
    ```python
    _provider_pool_instance = None
    def get_provider_pool() -> "ProviderPool | None":
        global _provider_pool_instance
        if _provider_pool_instance is None:
            try:
                from quantaalpha.core.conf import get_settings
                settings = get_settings()
                config = getattr(settings, 'provider_pool_config', None)
                if config and config.get("enabled"):
                    _provider_pool_instance = ProviderPool(config)
            except Exception:
                logger.debug("ProviderPool not configured, using legacy APIBackend")
                return None
        return _provider_pool_instance
    provider_pool = get_provider_pool()
    ```

14. **添加自定义异常类**
    ```python
    class EmptyResponseError(Exception):
        """Raised when a provider returns an empty response (D019: switch immediately)."""
        pass
    class AllProvidersFailedError(Exception):
        """Raised when all providers fail for a given task_type."""
        pass
    ```

## Must-Haves

- [ ] `ProviderPool` 类可从 config dict 初始化，所有字段正确映射
- [ ] `get_backend("hypothesis_generation")` 返回健康 Provider 的 backend
- [ ] `report_failure(name, "empty_response")` 不增加 consecutive_failures、不触发 cooldown
- [ ] `report_failure(name, "network")` 连续 3 次后触发 degraded，5 次后触发 cooldown
- [ ] `get_token_usage_report()` 返回正确的聚合统计
- [ ] 模块可独立导入，无语法错误

## Verification

```bash
python -m py_compile third_party/quantaalpha/quantaalpha/llm/provider_pool.py
```
无输出表示语法正确。

## Observability Impact

- **Signals added/changed**: `logger.warning` 输出在以下场景触发：
  - Provider 返回空响应 → `"Provider X returned empty, switching immediately"`
  - Provider 连续失败 ≥3 → `"Provider X degraded (failures=N)"`
  - Provider 连续失败 ≥5 → `"Provider X marked unhealthy, cooldown until T"`
- **How a future agent inspects this**: 调用 `provider_pool.get_health_summary()` 获取健康状态快照；调用 `provider_pool.get_token_usage_report()` 获取 token 统计
- **Failure state exposed**: 空响应时抛出 `EmptyResponseError`；所有 Provider 失败时抛出 `AllProvidersFailedError`

## Inputs

- `third_party/quantaalpha/quantaalpha/llm/client.py` — 参考 APIBackend 的 build_messages_and_create_chat_completion 签名
- `third_party/quantaalpha/quantaalpha/llm/config.py` — 参考 LLM_SETTINGS 的配置加载模式
- `third_party/quantaalpha/configs/experiment.yaml` — 配置格式参考（将在 T02 中添加）

## Expected Output

- `third_party/quantaalpha/quantaalpha/llm/provider_pool.py` — ProviderPool 核心实现，包含 Provider、ProviderHealth dataclass，ProviderPool 类，所有路由策略，健康状态机，Token 追踪，自定义异常，模块级单例
