# S05: Coding 模型 JSON 修复闭环 — Slice Summary

**Milestone:** M003 | **Status:** ✅ Complete | **Completed:** 2026-03-23

## What This Slice Delivered

S05 implements Strategy 5 in `robust_json_parse()`: when all four rule-based repair strategies fail, a dedicated coding model (via ProviderPool `json_repair` routing) repairs the malformed JSON with bounded retries and timeout. This closes the D019 feedback loop — JSON parsing failures no longer silently drop but trigger a recoverable repair path.

## Deliverables

| Deliverable | File | Status |
|---|---|---|
| Strategy 5 implementation | `quantaalpha/llm/client.py` | ✅ |
| Unit test suite | `tests/test_json_repair.py` | ✅ (17/17 pass) |
| conftest.py rdagent mock | `tests/conftest.py` | ✅ (supports both test suites) |
| T01/T02 task summaries | `.gsd/milestones/M003/slices/S05/tasks/` | ✅ |

## What Was Changed

### `client.py` — Strategy 5 (113 lines added)

**Constants (D019 constraints):**
- `MAX_JSON_REPAIR_ATTEMPTS = 3` — max retries
- `JSON_REPAIR_TIMEOUT_SECONDS = 30.0` — per-attempt timeout
- `JSON_REPAIR_SYSTEM_PROMPT` — instructs coding model to return only JSON

**ProviderPool import guard:**
- `_provider_pool_available` flag — set at import time
- Lazy import of `EmptyResponseError`, `AllProvidersFailedError`, `get_provider_pool`
- Graceful degradation when ProviderPool unavailable

**Strategy 5 logic:**
1. Check `_provider_pool_available` and `get_provider_pool()`
2. Retry loop (max 3 attempts):
   - Build repair prompt with original text and error context
   - Call `provider_pool.call_with_fallback(task_type="json_repair", timeout=30.0)`
   - `EmptyResponseError` → continue (D019: immediate switch, no failure_count increment)
   - `AllProvidersFailedError` → break
   - Try parsing repaired response (3 variants: raw, stripped, markdown-removed)
3. Fall through to original `json.JSONDecodeError` if all fail

**`_remove_markdown_json()` helper:**
- Strips ` ```json ... ``` ` and ` ``` ... ``` ` wrapping

### `tests/conftest.py` — rdagent mock

Two-part mocking strategy to make `client.py` importable in test environments without `rdagent` installed:

1. **sys.modules pre-population**: Fake `rdagent`, `rdagent.log`, `rdagent.log.utils`, `rdagent.log.storage` modules
2. **`_AlphaAgentLoggerWrapper.__delattr__` monkey-patch**: Enables `mock.patch.object` cleanup to work correctly on logger wrapper instances

### `tests/test_json_repair.py` — 17 tests

| Category | Count | Key assertions |
|---|---|---|
| D019 constraints | 2 | `MAX_JSON_REPAIR_ATTEMPTS == 3`, `timeout == 30.0` |
| Strategy 5 not called on success | 2 | No call to ProviderPool when Strategy 1/2 succeeds |
| Strategy 5 called on failure | 1 | ProviderPool called when all Strategies 1-4 fail |
| Markdown stripping | 3 | ` ```json``` `, ` ``` ``` `, plain passthrough |
| Retry behavior | 2 | Retries 3 times, all fail → original error |
| Empty response (D019) | 2 | `consecutive_failures` unchanged, retries attempted |
| Graceful degradation | 2 | ProviderPool unavailable → original error |
| AllProvidersFailed | 1 | Falls through to original error |
| Timeout/task_type | 2 | `timeout=30.0`, `task_type="json_repair"` passed |

## Verification Results

| Check | Command | Result |
|---|---|---|
| Syntax | `python -m py_compile client.py` | ✅ pass |
| S05 tests | `pytest tests/test_json_repair.py -v` | ✅ 17/17 pass |
| Combined | `pytest tests/provider_pool.py tests/test_json_repair.py -v` | ✅ 43/43 pass (26 + 17) |

## Key Decisions

| Decision | Rationale |
|---|---|
| `_provider_pool_available` flag | Allows Strategy 5 to be skipped without crashing when ProviderPool unavailable |
| 3-variant parsing per attempt | Coding model may return raw/repr/stripped — try all before counting as failure |
| `EmptyResponseError` caught and retried | D019: empty response triggers switch, not treated as permanent failure |
| `AllProvidersFailedError` breaks loop | When no provider can serve `json_repair`, give up rather than infinite loop |

## Patterns Established

1. **ProviderPool lazy import guard**: `try/except ImportError` pattern for optional dependencies
2. **`_provider_pool_available` module flag**: Enables tests to skip when dependency unavailable
3. **D019 test pattern**: Verify `failure_count` unchanged after `EmptyResponseError`
4. **conftest.py mock strategy**: `sys.modules` pre-population + class method monkey-patch

## Integration Points

- **`experiment.yaml`**: Already has `json_repair: ["qwen-coder"]` routing (S04 delivery) — no config change needed
- **S09**: Strategy 5 is a concrete implementation of D019's coding model repair constraint; S09 will add regression tests for this behavior
- **S04 ProviderPool**: Strategy 5 depends on `provider_pool.call_with_fallback()` being correctly implemented (S04 ✅)

## Dependencies Consumed

- **S04**: `provider_pool.call_with_fallback()`, `get_provider_pool()`, `experiment.yaml` routing config
- **D019**: M001 lesson that coding model repair must have timeout and retry上限

## Known Limitations

- **HTTP-level timeout not enforced**: The `timeout=30.0` parameter is passed to `call_with_fallback`, but `APIBackend.build_messages_and_create_chat_completion` does not currently enforce per-call timeouts at the HTTP layer. The timeout is a best-effort bound.
- **rdagent dependency for tests**: `tests/conftest.py` mock is required to run S05 tests in environments without `rdagent` installed. This is a test-environment artifact, not a production issue.

## Reusable Test Patterns

```python
# Test D019: empty response retries without incrementing failure_count
mock_health = MagicMock()
mock_health.consecutive_failures = 0
mock_pool.health = {"qwen-coder": mock_health}
mock_pool.call_with_fallback.side_effect = [
    EmptyResponseError("empty"),
    '{"result": "ok"}',
]
with patch("quantaalpha.llm.client.get_provider_pool", return_value=mock_pool):
    with patch("quantaalpha.llm.client._provider_pool_available", True):
        result = robust_json_parse("invalid {json")
assert result == {"result": "ok"}
assert mock_health.consecutive_failures == 0  # D019 constraint
```
