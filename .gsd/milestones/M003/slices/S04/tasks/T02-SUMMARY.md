---
id: T02
parent: S04
milestone: M003
provides:
  - complete provider_pool config in experiment.yaml and 26-unit test suite
key_files:
  - third_party/quantaalpha/configs/experiment.yaml
  - third_party/quantaalpha/tests/test_provider_pool.py
  - third_party/quantaalpha/quantaalpha/llm/provider_pool.py
key_decisions:
  - Mock _build_backend in get_backend tests to avoid rdagent dependency in unit tests; routing logic verified via mock assertions
patterns_established:
  - D019 constraint test pattern: assert failure_count unchanged after empty_response call
observability_surfaces:
  - pytest test suite serves as diagnostic tool; get_token_usage_report() and get_health_summary() provide runtime inspection surfaces (covered by tests)
duration: ~8 minutes
verification_result: passed
completed_at: 2026-03-23
blocker_discovered: false
---

# T02: 配置格式 + 单元测试

**Added `llm.provider_pool` configuration section to `experiment.yaml` and created a 26-test suite covering all ProviderPool behaviors including the D019 empty-response constraint.**

## What Happened

1. **YAML config added** — Appended a complete `llm.provider_pool` block to `experiment.yaml` inside the existing `llm:` section. Includes four providers (deepseek-r1, gpt4o, qwen-coder, glm4-flash) with routing rules for five task types and three strategies (single, round_robin, fanout_best), plus health thresholds (failure_threshold=5, degradation_threshold=3, cooldown_seconds=300).

2. **Test suite written** — `test_provider_pool.py` with 26 tests across 7 classes: `TestProviderPoolInit`, `TestGetBackend`, `TestRoundRobin`, `TestD019EmptyResponse`, `TestNetworkErrors`, `TestReportSuccess`, `TestTokenUsageReport`, `TestHealthSummary`, `TestFanoutBest`, `TestProviderConfig`. All tests pass.

3. **D019 tests verified** — Four dedicated tests confirm `empty_response` error type: does NOT increment `consecutive_failures`, does NOT trigger `cooldown_until`, does NOT mark provider unhealthy, but DOES increment `total_requests`.

4. **Mock isolation** — Tests that call `get_backend()` mock `_build_backend` to avoid the `rdagent` import chain, keeping tests fast and environment-independent.

## Verification

All slice verification checks passed:
- YAML syntax validation via `yaml.safe_load()`
- 26/26 pytest tests pass (0.22s)
- `python -m py_compile` confirms no syntax errors in provider_pool.py
- Module import check confirms `ProviderPool` and `provider_pool` singleton load correctly

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -c "import yaml; yaml.safe_load(open('third_party/quantaalpha/configs/experiment.yaml')); print('YAML OK')"` | 0 | ✅ pass | <1s |
| 2 | `python -m pytest third_party/quantaalpha/tests/test_provider_pool.py -v` | 0 | ✅ pass (26/26) | 0.22s |
| 3 | `python -m py_compile third_party/quantaalpha/quantaalpha/llm/provider_pool.py` | 0 | ✅ pass | <1s |
| 4 | `python -c "from quantaalpha.llm.provider_pool import ProviderPool, provider_pool; print('OK')"` | 0 | ✅ pass | <1s |

## Diagnostics

- Run `pytest -v` on `test_provider_pool.py` to inspect any regression
- Call `pool.get_token_usage_report()` at runtime for token/request stats per provider
- Call `pool.get_health_summary()` for health state snapshot (consecutive_failures, is_healthy, cooldown_until)
- D019 empty switching events are logged as `Provider X returned empty, switching immediately` at WARNING level

## Deviations

None — implementation matches the task plan exactly.

## Known Issues

None.

## Files Created/Modified

- `third_party/quantaalpha/configs/experiment.yaml` — Added `llm.provider_pool` config section with providers, routing, strategy, and health blocks
- `third_party/quantaalpha/tests/test_provider_pool.py` — 26-unit test suite covering initialization, routing, D019 constraint, network errors, cooldown, success, reporting, and fanout
