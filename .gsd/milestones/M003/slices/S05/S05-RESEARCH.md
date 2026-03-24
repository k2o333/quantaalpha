# S05: Coding 模型 JSON 修复闭环 — Research

**Milestone:** M003 | **Slice:** S05 | **Status:** Research | **Date:** 2026-03-23

## Context Summary

S05 implements the final strategy (Strategy 5) in `robust_json_parse()`: when all four rule-based repair strategies fail, call a dedicated coding model via ProviderPool to repair the malformed JSON. This closes the D019 loop — JSON parsing failures are no longer silent drops but trigger a recovery path with bounded retries and timeout.

## What Exists

### `robust_json_parse()` — current implementation
- **Location:** `third_party/quantaalpha/quantaalpha/llm/client.py:150`
- **Strategies 1–4:** direct parse → JSON code block extract → balanced object + conservative repairs → loose regex extraction
- **Final behavior:** raises `json.JSONDecodeError` when all fail
- **No retry loop, no timeout, no fallback model**

### ProviderPool — S04 delivery
- **Location:** `third_party/quantaalpha/quantaalpha/llm/provider_pool.py`
- `call_with_fallback(messages, task_type, **kwargs)` — routes to provider(s) by `task_type`
- `EmptyResponseError` raised on empty response (D019: immediate switch, no cooldown)
- `AllProvidersFailedError` raised when all providers fail
- `fanout_best()` uses 60s default timeout; per-call timeout configurable via `timeout=`

### `experiment.yaml` — json_repair routing
- **Location:** `third_party/quantaalpha/configs/experiment.yaml:192–219`
- `routing.json_repair: ["qwen-coder"]`
- `strategy.json_repair: "single"`
- Provider `qwen-coder`: role=`json_repair`, weight=1, max_rpm=30

### `provider_pool` singleton
- **Location:** `third_party/quantaalpha/quantaalpha/llm/provider_pool.py:598`
- `get_provider_pool()` → `ProviderPool | None`
- Returns `None` if `llm.provider_pool.enabled != True`
- All S05 callers must guard: `if pp: ... else: fallback`

## What S05 Must Add

### Strategy 5: Coding model repair

Signature of `robust_json_parse` does NOT change (still `def robust_json_parse(text: str, max_retries: int = 3) -> dict`).

The new logic is inserted after Strategy 4 fails and before `raise json.JSONDecodeError`:

```
Strategy 5 — Coding model repair:
  for attempt in range(3):           # D019: max 3 retries
    with timeout(30 seconds):        # D019: 30s timeout
      pp = get_provider_pool()
      if pp is None: break          # graceful degradation
      messages = [
        {"role": "system", "content": JSON_REPAIR_SYSTEM_PROMPT},
        {"role": "user",   "content": f"Raw response:\n{original_text}\n\nError: {last_error}"}
      ]
      try:
        repaired = pp.call_with_fallback(messages, task_type="json_repair", timeout=30.0)
      except EmptyResponseError:
        # D019: empty response → switch immediately (handled inside call_with_fallback)
        continue
      except AllProvidersFailedError:
        break                        # all providers exhausted, give up
      except TimeoutError:
        continue                    # timeout counts as attempt, try next
      # Try to parse the repaired text
      for variant in [repaired, repaired.strip(), _remove_markdown(repaired)]:
        try: return json.loads(variant)
        except: continue
  raise json.JSONDecodeError(...)    # fallback to original error
```

### Constants to add (top of `client.py` or near `robust_json_parse`)

```python
JSON_REPAIR_SYSTEM_PROMPT = """You are a JSON repair assistant.
The user will provide a raw LLM response that was supposed to be valid JSON.
Fix any syntax errors and return ONLY the corrected JSON — no explanation, no markdown, no code fences.
The JSON must be a single top-level object or array.
"""

MAX_JSON_REPAIR_ATTEMPTS = 3   # D019 constraint: max retries
JSON_REPAIR_TIMEOUT_SECONDS = 30.0  # D019 constraint: 30s timeout
JSON_REPAIR_TASK_TYPE = "json_repair"  # matches experiment.yaml routing
```

### Helper: `_remove_markdown()`

Strip markdown code fences that some coding models add despite instructions:

```python
def _remove_markdown_json(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` wrapping."""
    text = text.strip()
    m = re.match(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text
```

### Guard: ProviderPool availability check

`get_provider_pool()` can return `None` if config not set. The Strategy 5 block must check this and gracefully fall back to raising the original error (not crashing). The `robust_json_parse` function should NEVER crash due to a missing dependency — it always either returns a parsed dict or raises `json.JSONDecodeError`.

## Integration Points

1. **`client.py` imports** — must add:
   ```python
   try:
       from quantaalpha.llm.provider_pool import get_provider_pool, EmptyResponseError, AllProvidersFailedError
   except ImportError:
       get_provider_pool = None  # type: ignore
       EmptyResponseError = Exception
       AllProvidersFailedError = Exception
   ```

2. **`_remove_markdown_json` helper** — defined before `robust_json_parse` or as a nested helper.

3. **D019 empty response** — `EmptyResponseError` from ProviderPool means immediate switch (handled inside `call_with_fallback`); caller just retries the outer loop. No cooldown, no failure count increment.

4. **Timeout handling** — the inner `with timeout()` is implemented using `signal` (Unix) or `threading.Timer` (cross-platform). Prefer `signal` if on Unix, with a fallback to no-timeout on Windows (log a warning).

## Key Constraints from D019

| Constraint | Value | Implementation |
|---|---|---|
| Coding model timeout | 30 seconds | `timeout=30.0` on `call_with_fallback` |
| Max repair attempts | 3 | `for attempt in range(3)` loop |
| Empty response | Immediate switch | `EmptyResponseError` caught, continue loop |
| Failure count | NOT incremented | ProviderPool handles this internally |

## T01 Task Scope

**File to modify:** `third_party/quantaalpha/quantaalpha/llm/client.py`

**New code:**
1. Add `JSON_REPAIR_SYSTEM_PROMPT`, `MAX_JSON_REPAIR_ATTEMPTS`, `JSON_REPAIR_TIMEOUT_SECONDS` constants
2. Add `_remove_markdown_json()` helper
3. Add `try/except` block for `get_provider_pool` import
4. Insert Strategy 5 block in `robust_json_parse()` between Strategy 4 and `raise json.JSONDecodeError`

**No new files in T01.**

## T02 Task Scope

**File to create:** `third_party/quantaalpha/tests/test_json_repair.py`

**Tests to write:**
1. Strategy 5 called only after Strategies 1–4 fail
2. Coding model returns valid JSON → parsed and returned
3. Coding model returns markdown-wrapped JSON → stripped and parsed
4. Coding model returns empty response → next attempt tried (up to 3)
5. All 3 repair attempts fail → original `json.JSONDecodeError` raised
6. ProviderPool unavailable → original `json.JSONDecodeError` raised (graceful degradation)
7. Timeout → treated as attempt failure, retries up to 3
8. `EmptyResponseError` does NOT increment failure_count (verified via mock)

## Risks

1. **Signal-based timeout not cross-platform** — use `signal.SIGALRM` on Unix, `threading.Timer` on Windows. If neither works, log warning and proceed without timeout (fallback to ProviderPool's built-in 30s timeout on `call_with_fallback`).
2. **Coding model returns non-JSON even with instructions** — the outer retry loop handles this (up to 3 times).
3. **ProviderPool returns `None`** — must gracefully degrade to original error, not crash.
4. **Import of ProviderPool symbols in client.py** — wrap in try/except to avoid hard import failure.

## Verification

```bash
# Syntax check
python -m py_compile third_party/quantaalpha/quantaalpha/llm/client.py

# Unit tests (T02)
python -m pytest third_party/quantaalpha/tests/test_json_repair.py -v

# No new regressions
python -m pytest third_party/quantaalpha/tests/test_provider_pool.py -v
```
