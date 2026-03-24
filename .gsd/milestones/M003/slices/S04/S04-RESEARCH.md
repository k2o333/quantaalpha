# S04: ProviderPool 核心实现 (S2/D016) — Research

**Milestone:** M003 | **Slice:** S04 | **Status:** Research
**Risk:** High | **Depends:** S01 (complete)

---

## 1. What This Slice Delivers

Implements a `ProviderPool` abstraction layer that wraps the existing `APIBackend` class to enable:

1. **Multi-provider coexistence** — multiple provider instances with different models/vendors
2. **Role-based routing** — task-to-provider assignment (hypothesis_generation/coding/evaluation_screening)
3. **Fanout concurrency** — parallel requests to multiple providers for critical tasks, select first valid response
4. **Health monitoring** — track provider availability, failure rates, latency
5. **Automatic fallback** — degraded provider automatically bypassed; round-robin or priority selection
6. **Token usage tracking** — per-provider and aggregate token consumption

D019 constraint: **empty response ≠ network error** — must immediately switch provider on empty response (per M001 Bug 2 lesson).

---

## 2. Current State Analysis

### 2.1 Existing APIBackend Architecture

**Location:** `quantaalpha/llm/client.py` (1178 lines)

```
APIBackend
├── __init__: handles Llama2/GCR/Azure/OpenAI backend selection
├── get_model_for_task: single-model routing via task_model_map
├── build_messages_and_create_chat_completion: primary entry point
├── _try_create_chat_completion_or_embedding: retry loop (max_retry=10)
└── _create_chat_completion_inner_function: actual API call
```

**Critical Problem:** Creates a **new `APIBackend()` instance per call** in `proposal.py`:

```python
# proposal.py:363
api = APIBackend() if attempt == 0 else APIBackend(use_chat_cache=False)

# proposal.py:407
resp = APIBackend().build_messages_and_create_chat_completion(...)

# proposal.py:552
resp = APIBackend().build_messages_and_create_chat_completion(...)
```

**No health tracking, no provider state, no cross-request awareness.**

### 2.2 Retry Logic (client.py:781-813)

```python
for i in range(max_retry):
    try:
        return self._create_chat_completion_auto_continue(...)
    except openai.BadRequestError as e:
        # handles JSON mode error, context length
        time.sleep(self.retry_wait_seconds)
    except Exception as e:
        # catches ALL exceptions, including empty response
        time.sleep(self.retry_wait_seconds)
```

**Problem:** Does NOT distinguish empty response from network error. Retries same provider.

### 2.3 Task Routing (client.py:661-669)

```python
def get_model_for_task(self, task_type=None, tag=None) -> str:
    if task_type:
        if task_type not in KNOWN_TASK_TYPES:
            logger.warning(f"Unknown task_type={task_type}")
        model = self.task_model_map.get(task_type)
        if model:
            return model
        return self.routing_default or self.chat_model_map.get(tag or "", self.chat_model)
```

**Problem:** Static routing only — no provider-level abstraction.

### 2.4 Configuration (llm/config.py)

```python
class LLMSettings(ExtendedBaseSettings):
    chat_model_map: str = "{}"  # JSON: tag → model
    routing_default: str = ""
    routing_tasks: str = "{}"   # JSON: task_type → model
```

**Problem:** No provider-level config (base_url, api_key, health_threshold).

---

## 3. ProviderPool Design

### 3.1 Provider Class

```python
class Provider:
    """Represents a single provider instance with health state."""
    name: str
    backend: APIBackend  # wrapped instance
    base_url: str
    api_key: str
    model: str
    health_state: HealthState  # healthy/degraded/unhealthy
    failure_count: int
    success_count: int
    total_tokens: int
    last_error: str | None
    last_success: datetime | None
```

**Health State Transitions:**
- `healthy`: failure_count == 0, or failure_count < 3 and success_rate > 0.8
- `degraded`: 3 <= failure_count < 5
- `unhealthy`: failure_count >= 5, or consecutive timeouts >= 3

### 3.2 ProviderPool Class

```python
class ProviderPool:
    """
    Manages multiple providers with health-aware routing.
    
    Key behaviors:
    - get_provider(task_type): select provider based on role mapping
    - call_with_fallback(messages, task_type): retry with provider switch on failure
    - fanout_call(messages, task_type, n=2): concurrent calls, return first valid
    - track_usage(provider_name, tokens): update token budget
    """
    
    providers: dict[str, Provider]
    role_mapping: dict[str, list[str]]  # task_type → [provider_names]
    default_provider: str
    
    def __init__(self, config: ProviderPoolConfig):
        # Initialize from experiment.yaml providers section
```

### 3.3 Fanout Mode

For critical tasks (hypothesis_generation), send to N providers concurrently:

```python
async def fanout_call(self, messages, task_type, n=2, timeout=30):
    """Send to N providers, return first valid response."""
    providers = self.get_providers_for_task(task_type)[:n]
    tasks = [self._call_provider(p, messages, timeout) for p in providers]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for result in results:
        if isinstance(result, str) and result.strip():
            return result  # first valid response
    raise AllProvidersFailedError([str(r) for r in results])
```

### 3.4 Empty Response Handling (D019)

```python
def _call_provider(self, provider, messages, **kwargs):
    response = provider.backend.build_messages_and_create_chat_completion(...)
    
    # D019 constraint: empty response → immediate provider switch
    if not response or not response.strip():
        provider.health_state = HealthState.unhealthy
        provider.failure_count += 1
        raise EmptyResponseError(f"Provider {provider.name} returned empty")
    
    # Network error → try again with same provider (degraded)
    except (ConnectionError, TimeoutError) as e:
        provider.failure_count += 1
        provider.last_error = str(e)
        raise
```

**Distinction:** Empty response = provider bug (switch immediately). Network error = transient (may retry same provider up to max_retries).

---

## 4. Integration Points

### 4.1 proposal.py Changes

**Before (current):**
```python
api = APIBackend() if attempt == 0 else APIBackend(use_chat_cache=False)
resp = api.build_messages_and_create_chat_completion(...)
```

**After (with ProviderPool):**
```python
# Module-level singleton
try:
    from quantaalpha.llm.provider_pool import provider_pool
except ImportError:
    provider_pool = None

# In gen() method
if provider_pool:
    resp = provider_pool.call_with_fallback(messages, task_type="hypothesis_generation")
else:
    api = APIBackend()
    resp = api.build_messages_and_create_chat_completion(...)
```

**Pattern:** Graceful degradation — if `provider_pool` import fails or not configured, fall back to existing `APIBackend()`.

### 4.2 experiment.yaml Configuration

```yaml
provider_pool:
  enabled: true
  
  # Provider definitions
  providers:
    - name: "primary-gpt4"
      base_url: "https://api.openai.com/v1"
      api_key_env: "OPENAI_API_KEY"
      model: "gpt-4-turbo"
      priority: 1
      
    - name: "backup-claude"
      base_url: "https://api.anthropic.com"
      api_key_env: "ANTHROPIC_API_KEY"
      model: "claude-3-sonnet"
      priority: 2
      
    - name: "coding-qwen"
      base_url: "http://localhost:8000"
      model: "qwen-coder"
      priority: 1

  # Role-based routing
  routing:
    hypothesis_generation: ["primary-gpt4", "backup-claude"]
    factor_construction: ["primary-gpt4"]
    evaluation_screening: ["primary-gpt4", "backup-claude"]
    coding: ["coding-qwen"]

  # Fanout config
  fanout:
    enabled: true
    hypothesis_generation: 2  # call 2 providers, return first valid
    timeout: 30  # seconds per provider

  # Health config
  health:
    failure_threshold: 5  # mark unhealthy after 5 failures
    degradation_threshold: 3  # mark degraded after 3 failures
    recovery_attempts: 2  # try unhealthy provider after 2 successes elsewhere
```

### 4.3 backward Compatibility

**Critical constraint:** existing code must continue to work.

```python
# In provider_pool.py
_provider_pool_instance = None

def get_provider_pool() -> ProviderPool | None:
    """Returns singleton if configured, None otherwise."""
    global _provider_pool_instance
    if _provider_pool_instance is None:
        try:
            config = load_provider_pool_config()
            if config and config.get("enabled"):
                _provider_pool_instance = ProviderPool(config)
        except Exception:
            logger.warning("ProviderPool initialization failed, using legacy APIBackend")
            return None
    return _provider_pool_instance

# Export the singleton for import
provider_pool = get_provider_pool()
```

---

## 5. File Structure

| File | Change | Purpose |
|------|--------|---------|
| `llm/provider_pool.py` | **NEW** | ProviderPool class, Provider class, health state machine |
| `llm/client.py` | MODIFY | Minor: expose token tracking methods |
| `llm/config.py` | MODIFY | Add `ProviderPoolSettings` |
| `factors/proposal.py` | MODIFY | Replace `APIBackend()` calls with `provider_pool.call_*()` |
| `configs/experiment.yaml` | MODIFY | Add `provider_pool` section |
| `tests/test_provider_pool.py` | **NEW** | Unit tests for ProviderPool |

---

## 6. Verification Criteria

1. **py_compile** passes for all modified files
2. **Multi-provider routing**: task type correctly selects configured provider
3. **Health state**: provider marked unhealthy after 5 failures
4. **Empty response**: immediately switches provider (D019)
5. **Fanout**: returns first valid from concurrent calls
6. **Token tracking**: aggregate counts match actual usage
7. **Backward compat**: existing `APIBackend()` calls work without config

---

## 7. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Breaking existing `APIBackend()` calls | Graceful fallback to legacy mode |
| Concurrent provider failures | Circuit breaker pattern with timeout |
| Config migration complexity | Keep `routing_tasks` as legacy fallback |
| Worktree import paths | Use `quantaalpha.llm.provider_pool` import pattern |

---

## 8. Downstream Dependencies

- **S05 (Coding JSON fix)**: Uses ProviderPool for retry-with-provider-switch on JSON parse failure
- **S08 (ResourceManager)**: ProviderPool provides token usage API to ResourceManager
