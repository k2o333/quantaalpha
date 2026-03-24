# S04: ProviderPool 核心实现 (S2/D016) — Slice Summary

**Milestone:** M003 | **Status:** ✅ Complete | **Completed:** 2026-03-23

## What This Slice Delivered

S04 implements the **ProviderPool** — a multi-provider LLM routing layer with health monitoring and automatic fallback. This is the core infrastructure for the 24H autonomous factor mining pipeline (M003 Goal).

### Deliverables

| Deliverable | File | Status |
|---|---|---|
| ProviderPool core class | `quantaalpha/llm/provider_pool.py` | ✅ |
| 26-unit test suite | `tests/test_provider_pool.py` | ✅ (26/26 pass) |
| provider_pool config | `configs/experiment.yaml` | ✅ |
| Module singleton export | `provider_pool.py` | ✅ |

### Key Features Implemented

1. **Three Routing Strategies:**
   - `single` — Return first healthy provider (default)
   - `round_robin` — Cycle through providers (weighted by `weight` field)
   - `fanout_best` — Call all providers concurrently, return first valid response

2. **Health State Machine:**
   - ≥3 consecutive failures → degraded (logged warning)
   - ≥5 consecutive failures → unhealthy, 300s cooldown
   - Success → reset failures, recover if cooldown expired

3. **D019 Design Constraint (critical):**
   - Empty response (`response.strip() == ""`) → immediate switch
   - Does NOT increment `consecutive_failures`
   - Does NOT trigger cooldown
   - Does increment `total_requests` (for tracking)
   - Logs: `Provider X returned empty, switching immediately`

4. **Observability Surfaces:**
   - `get_token_usage_report()` — per-provider token/request stats
   - `get_health_summary()` — health state snapshot
   - WARNING-level logs for state transitions

### Configuration

```yaml
llm.provider_pool:
  enabled: true
  providers:
    - name: "deepseek-r1"; role: "hypothesis"; weight: 3
    - name: "gpt4o"; role: "hypothesis"; weight: 2
    - name: "qwen-coder"; role: "json_repair"; weight: 1
    - name: "glm4-flash"; role: "screening"; weight: 5
  routing:
    hypothesis_generation: ["deepseek-r1", "gpt4o"]
    factor_construction: ["deepseek-r1"]
    json_repair: ["qwen-coder"]
  strategy:
    hypothesis_generation: "fanout_best"
    factor_construction: "single"
    feedback_summarization: "round_robin"
  health:
    failure_threshold: 5
    degradation_threshold: 3
    cooldown_seconds: 300
```

**Backward Compatibility:** When `llm.provider_pool.enabled` is not `true`, `provider_pool` singleton returns `None`, allowing callers to fall back to direct `APIBackend()` usage.

## Verification Results

| Check | Command | Result |
|---|---|---|
| Syntax | `python -m py_compile provider_pool.py` | ✅ pass |
| Unit tests | `python -m pytest tests/test_provider_pool.py -v` | ✅ 26/26 pass |
| Import | `from quantaalpha.llm.provider_pool import ProviderPool, provider_pool` | ✅ pass |
| YAML config | `yaml.safe_load()` on experiment.yaml | ✅ pass |

## Key Decisions

| Decision | Rationale |
|---|---|
| D019: empty_response ignores failure_count | Ensures immediate switch to downstream provider; avoids 300s cooldown on transient upstream empty response |
| Mock `_build_backend` in unit tests | Avoids rdagent import chain; keeps tests fast and environment-independent |
| Lazy logger initialization | Prevents circular import between `provider_pool.py` and `quantaalpha.log` |
| Singleton returns `None` when not configured | Backward-compatible fallback without requiring config changes in legacy code |

## Patterns Established

1. **D019 test pattern:** Verify `failure_count` unchanged after `empty_response` call
2. **Lazy import guard:** `try: import X; except: import logging.getLogger()` pattern avoids circular deps
3. **Mock isolation in routing tests:** `_build_backend` mocked to test routing logic without rdagent
4. **Weighted round-robin cursor per task_type:** Ensures task types don't interfere with each other's round-robin state

## What Downstream Slices Need to Know

### Integration Points

- **S05** will wire `proposal.py`'s `APIBackend()` calls to `provider_pool.call_with_fallback()`
- **S08** will integrate `get_token_usage_report()` into ResourceManager
- The `provider_pool` singleton is already exported at module level

### Preconditions for S05 Integration

- `experiment.yaml` must have `llm.provider_pool.enabled: true`
- At least one provider must have `role` matching `task_type` in routing config
- When `provider_pool` is `None` (not configured), S05 must fall back to direct `APIBackend()`

### Observability How-To

```python
# Runtime inspection
from quantaalpha.llm.provider_pool import provider_pool
health = provider_pool.get_health_summary()
tokens = provider_pool.get_token_usage_report()
```

### Gotcha: Fanout Does Not Auto-Switch on Empty

`fanout_best()` internally calls `_report_empty()` which logs the event, but callers should be aware that empty responses in fanout mode try the next provider immediately (no cooldown). This is correct D019 behavior.

## Dependencies Consumed

- **S01:** Data capability registry (used for config validation in experiment.yaml)
- **D016:** Architecture decision for multi-provider routing
- **D019:** Design constraint for empty response handling

## Known Limitations

- `provider_pool` singleton requires `quantaalpha.core.conf.get_settings()` — will return `None` if that fails
- Token estimation uses `backend.encoder.encode()` — returns 0 if encoder unavailable
- `fanout_best` does not have per-provider timeout; uses a single `timeout` parameter

## Reusable Test Patterns

```python
# Test D019 constraint
pool.report_failure("provider", "network")
pool.report_failure("provider", "network")
assert pool.health["provider"].consecutive_failures == 2
pool.report_failure("provider", "empty_response")
assert pool.health["provider"].consecutive_failures == 2  # Unchanged per D019
assert pool.health["provider"].cooldown_until == 0.0       # No cooldown per D019

# Test health state machine
for _ in range(5):
    pool.report_failure("provider", "network")
assert pool.health["provider"].is_healthy is False
assert pool.health["provider"].cooldown_until > time.time()

# Test recovery after cooldown
pool.health["provider"].cooldown_until = time.time() - 1
pool.report_success("provider")
assert pool.health["provider"].is_healthy is True
```
