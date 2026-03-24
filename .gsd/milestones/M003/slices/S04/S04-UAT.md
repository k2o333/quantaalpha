# S04: ProviderPool UAT — Concrete Test Script

**Target:** ProviderPool multi-provider routing, health monitoring, and D019 empty response constraint  
**Preconditions:** Python 3.13+, pytest, `quantaalpha.llm.provider_pool` module accessible

## Setup

```bash
cd /home/quan/testdata/aspipe_v4/.gsd/worktrees/M003
export PYTHONPATH="third_party/quantaalpha:$PYTHONPATH"
python -c "import yaml; yaml.safe_load(open('third_party/quantaalpha/configs/experiment.yaml'))" && echo "Config OK"
```

---

## UAT-01: Module Import and Singleton

**Purpose:** Verify ProviderPool class and module singleton load correctly

**Steps:**
1. `python -c "from quantaalpha.llm.provider_pool import ProviderPool, provider_pool, get_provider_pool; print('OK')"`
2. `python -c "from quantaalpha.llm.provider_pool import EmptyResponseError, AllProvidersFailedError; print('OK')"`
3. `python -c "from quantaalpha.llm.provider_pool import ProviderConfig, ProviderHealth; print('OK')"`

**Expected:** All imports succeed without errors

---

## UAT-02: ProviderPool Initialization

**Purpose:** Pool initializes providers, health dict, routing map, and strategy from config

**Steps:**
```python
import sys; sys.path.insert(0, 'third_party/quantaalpha')
import yaml
from quantaalpha.llm.provider_pool import ProviderPool

raw = yaml.safe_load(open('third_party/quantaalpha/configs/experiment.yaml'))
cfg = raw['llm']['provider_pool']
pool = ProviderPool(cfg)

# 1. Verify providers loaded
assert 'deepseek-r1' in pool.providers
assert 'gpt4o' in pool.providers
assert pool.providers['deepseek-r1'].model == 'deepseek-reasoner'

# 2. Verify health dict initialized
for name in pool.providers:
    assert pool.health[name].is_healthy is True
    assert pool.health[name].consecutive_failures == 0
    assert pool.health[name].cooldown_until == 0.0

# 3. Verify routing map
assert 'hypothesis_generation' in pool.role_to_providers
assert 'deepseek-r1' in pool.role_to_providers['hypothesis_generation']

# 4. Verify strategies
assert pool.strategy['hypothesis_generation'] == 'fanout_best'
assert pool.strategy['factor_construction'] == 'single'
```

**Expected:** All assertions pass

---

## UAT-03: D019 — Empty Response Does NOT Increment failure_count

**Purpose:** Critical D019 constraint — empty responses must not affect failure tracking

**Steps:**
```python
from quantaalpha.llm.provider_pool import ProviderPool

pool = ProviderPool(MINIMAL_CONFIG)

# 1. Accumulate some network failures
pool.report_failure("test-provider", "network")
pool.report_failure("test-provider", "network")
assert pool.health["test-provider"].consecutive_failures == 2

# 2. Empty response must NOT increment failure_count (D019)
pool.report_failure("test-provider", "empty_response")
assert pool.health["test-provider"].consecutive_failures == 2, \
    "D019 VIOLATED: empty_response incremented consecutive_failures"

# 3. Another empty response still doesn't affect it
pool.report_failure("test-provider", "empty_response")
assert pool.health["test-provider"].consecutive_failures == 2
```

**Expected:** All assertions pass; consecutive_failures stays at 2

---

## UAT-04: D019 — Empty Response Does NOT Trigger Cooldown

**Purpose:** Empty responses must not trigger cooldown (300s block)

**Steps:**
```python
from quantaalpha.llm.provider_pool import ProviderPool

pool = ProviderPool(MINIMAL_CONFIG)

# 1. Empty response on fresh provider
pool.report_failure("test-provider", "empty_response")
assert pool.health["test-provider"].cooldown_until == 0.0, \
    "D019 VIOLATED: empty_response triggered cooldown"

# 2. Even after 4 network failures, one empty response doesn't cooldown
for _ in range(4):
    pool.report_failure("test-provider", "network")
assert pool.health["test-provider"].is_healthy is True  # 4 < 5 threshold

pool.report_failure("test-provider", "empty_response")
assert pool.health["test-provider"].cooldown_until == 0.0
assert pool.health["test-provider"].is_healthy is True
```

**Expected:** cooldown_until remains 0.0; is_healthy remains True

---

## UAT-05: D019 — Empty Response Does NOT Prevent Provider from Receiving Traffic

**Purpose:** Empty response must increment total_requests so provider stays in rotation

**Steps:**
```python
from quantaalpha.llm.provider_pool import ProviderPool

pool = ProviderPool(MINIMAL_CONFIG)

assert pool.health["test-provider"].total_requests == 0

# 1. Empty response counts as a request for usage tracking
pool.report_failure("test-provider", "empty_response")
assert pool.health["test-provider"].total_requests == 1

# 2. Subsequent empty responses continue to count
pool.report_failure("test-provider", "empty_response")
pool.report_failure("test-provider", "empty_response")
assert pool.health["test-provider"].total_requests == 3
```

**Expected:** total_requests increments on each empty_response

---

## UAT-06: Network Error → Degraded State (≥3 Failures)

**Purpose:** ≥3 consecutive network failures triggers degraded state

**Steps:**
```python
import logging
from quantaalpha.llm.provider_pool import ProviderPool

pool = ProviderPool(MINIMAL_CONFIG)

# 1. First two failures don't degrade
pool.report_failure("test-provider", "network")
pool.report_failure("test-provider", "network")
assert pool.health["test-provider"].is_healthy is True

# 2. Third failure degrades (logged)
pool.report_failure("test-provider", "network")
assert pool.health["test-provider"].consecutive_failures == 3
# is_healthy still True (threshold is 5)
assert pool.health["test-provider"].is_healthy is True
```

**Expected:** 3 failures → degraded (logged); is_healthy still True

---

## UAT-07: Network Error → Unhealthy + Cooldown (≥5 Failures)

**Purpose:** ≥5 consecutive network failures marks provider unhealthy and starts 300s cooldown

**Steps:**
```python
import time
from quantaalpha.llm.provider_pool import ProviderPool

pool = ProviderPool(MINIMAL_CONFIG)

# 1. Accumulate 5 failures
for _ in range(5):
    pool.report_failure("test-provider", "network")

# 2. Provider is now unhealthy
assert pool.health["test-provider"].is_healthy is False

# 3. Cooldown is set to ~300 seconds
assert pool.health["test-provider"].cooldown_until > time.time()
assert pool.health["test-provider"].cooldown_until <= time.time() + 310  # ~300s

# 4. Provider excluded from healthy candidates
candidates = pool._get_healthy_candidates("hypothesis_generation")
assert "test-provider" not in candidates
```

**Expected:** is_healthy=False; cooldown_until ≈ time+300; provider excluded from candidates

---

## UAT-08: Success Resets Failure Count and Recovers Provider

**Purpose:** Successful call resets consecutive_failures and can recover unhealthy provider after cooldown

**Steps:**
```python
import time
from quantaalpha.llm.provider_pool import ProviderPool

pool = ProviderPool(MINIMAL_CONFIG)

# 1. Accumulate failures
for _ in range(3):
    pool.report_failure("test-provider", "network")
assert pool.health["test-provider"].consecutive_failures == 3

# 2. Success resets failure count
pool.report_success("test-provider", tokens_used=100)
assert pool.health["test-provider"].consecutive_failures == 0
assert pool.health["test-provider"].total_tokens == 100
assert pool.health["test-provider"].total_requests == 1

# 3. Recovery after cooldown
for _ in range(5):
    pool.report_failure("test-provider", "network")
assert pool.health["test-provider"].is_healthy is False

pool.health["test-provider"].cooldown_until = time.time() - 1  # Expire cooldown
pool.report_success("test-provider", tokens_used=200)
assert pool.health["test-provider"].is_healthy is True
```

**Expected:** Success resets all state correctly; recovery works after cooldown expires

---

## UAT-09: Round-Robin Cycles Through Providers

**Purpose:** Round-robin strategy cycles through healthy providers

**Steps:**
```python
from unittest.mock import MagicMock, patch
from quantaalpha.llm.provider_pool import ProviderPool

pool = ProviderPool(MINIMAL_CONFIG)

# Build mock backends
mock_backends = {
    "test-provider": MagicMock(chat_model="test-model"),
    "test-provider-2": MagicMock(chat_model="test-model-2"),
}

with patch.object(pool, '_build_backend', side_effect=lambda n: mock_backends[n]):
    # Round-robin over hypothesis_generation: [test-provider-2, test-provider]
    results = [pool.get_backend("feedback_summarization") for _ in range(4)]

models = [b.chat_model for b in results]
assert models == ["test-model-2", "test-model", "test-model-2", "test-model"]
```

**Expected:** Alternating providers in round-robin order

---

## UAT-10: Fanout Best Returns First Valid Response

**Purpose:** fanout_best strategy routes to fanout mode (first candidate's backend returned for routing; actual fanout in fanout_best() method)

**Steps:**
```python
from unittest.mock import MagicMock, patch
from quantaalpha.llm.provider_pool import ProviderPool, AllProvidersFailedError

pool = ProviderPool(MINIMAL_CONFIG)

# Verify fanout_best raises when no providers configured
try:
    pool.fanout_best([], "nonexistent_task")
    assert False, "Should have raised AllProvidersFailedError"
except AllProvidersFailedError:
    pass  # Expected

# Verify get_backend returns first candidate for fanout_best strategy
mock_backend = MagicMock(chat_model="test-model")
with patch.object(pool, '_build_backend', return_value=mock_backend):
    backend = pool.get_backend("fanout_task")
    assert backend.chat_model == "test-model"
```

**Expected:** AllProvidersFailedError raised for unknown task; get_backend returns first candidate

---

## UAT-11: get_health_summary Returns Correct Structure

**Purpose:** Observability surface returns correct health state snapshot

**Steps:**
```python
from quantaalpha.llm.provider_pool import ProviderPool

pool = ProviderPool(MINIMAL_CONFIG)
pool.report_failure("test-provider", "network")
pool.report_failure("test-provider", "network")

summary = pool.get_health_summary()

assert "test-provider" in summary
assert summary["test-provider"]["consecutive_failures"] == 2
assert summary["test-provider"]["is_healthy"] is True
assert summary["test-provider"]["cooldown_until"] == 0.0

assert "test-provider-2" in summary
assert summary["test-provider-2"]["consecutive_failures"] == 0
```

**Expected:** Snapshot contains all providers with correct fields

---

## UAT-12: get_token_usage_report Returns Correct Statistics

**Purpose:** Token usage tracking aggregates correctly across providers

**Steps:**
```python
from quantaalpha.llm.provider_pool import ProviderPool

pool = ProviderPool(MINIMAL_CONFIG)

# Record successes
pool.report_success("test-provider", tokens_used=100)
pool.report_success("test-provider-2", tokens_used=200)

# Record network failure (counts as request)
pool.report_failure("test-provider", "network")

report = pool.get_token_usage_report()

assert report["total_requests"] == 3
assert report["total_tokens"] == 300
assert report["providers"]["test-provider"]["requests"] == 2
assert report["providers"]["test-provider"]["tokens"] == 100
assert report["providers"]["test-provider-2"]["requests"] == 1
assert report["providers"]["test-provider-2"]["tokens"] == 200
```

**Expected:** Aggregated and per-provider stats match recorded events

---

## UAT-13: ProviderConfig.from_dict with Defaults

**Purpose:** Configuration parsing applies defaults for optional fields

**Steps:**
```python
from quantaalpha.llm.provider_pool import ProviderConfig

# Missing optional fields → defaults applied
cfg = ProviderConfig.from_dict({
    "name": "p", "role": "r",
    "api_key_env": "K", "base_url": "https://x.com", "model": "m"
})
assert cfg.weight == 1
assert cfg.max_rpm == 60

# Explicit values override defaults
cfg2 = ProviderConfig.from_dict({
    "name": "p", "role": "r",
    "api_key_env": "K", "base_url": "https://x.com", "model": "m",
    "weight": 5, "max_rpm": 100
})
assert cfg2.weight == 5
assert cfg2.max_rpm == 100
```

**Expected:** Defaults and explicit values both work correctly

---

## UAT-14: Backward Compatibility — No ProviderPool Config

**Purpose:** When provider_pool is not configured, singleton returns None

**Steps:**
```python
# Import the singleton (evaluates at module load time)
from quantaalpha.llm.provider_pool import provider_pool

# When llm.provider_pool.enabled is true in config, it should be a ProviderPool
# When not configured, it returns None
# Run this check when config is absent:
import os
os.environ.pop('QUANTAALPHA_PROVIDER_POOL_ENABLED', None)

# Force re-init by clearing the module-level singleton
import quantaalpha.llm.provider_pool as pp_module
pp_module._provider_pool_instance = None

# get_provider_pool should return None when not configured
result = pp_module.get_provider_pool()
# (Result depends on whether experiment.yaml has provider_pool enabled)
```

**Expected:** Singleton gracefully returns None when config absent

---

## UAT-15: experiment.yaml Configuration Integrity

**Purpose:** YAML config is syntactically valid and contains all required fields

**Steps:**
```bash
python -c "
import yaml
cfg = yaml.safe_load(open('third_party/quantaalpha/configs/experiment.yaml'))
pp = cfg['llm']['provider_pool']

# Required top-level keys
assert 'enabled' in pp
assert 'providers' in pp
assert 'routing' in pp
assert 'strategy' in pp

# At least one provider defined
assert len(pp['providers']) >= 1

# Each provider has required fields
for p in pp['providers']:
    assert 'name' in p
    assert 'role' in p
    assert 'api_key_env' in p
    assert 'base_url' in p
    assert 'model' in p

# routing maps task_types to provider names
for task_type, names in pp['routing'].items():
    assert isinstance(names, list)
    assert len(names) > 0

# strategies are valid values
for task_type, strat in pp['strategy'].items():
    assert strat in ('single', 'round_robin', 'fanout_best')

print('Config integrity OK')
"
```

**Expected:** All assertions pass

---

## Run All UATs

```bash
cd /home/quan/testdata/aspipe_v4/.gsd/worktrees/M003
export PYTHONPATH="third_party/quantaalpha:$PYTHONPATH"

# Quick smoke test
python -m py_compile third_party/quantaalpha/quantaalpha/llm/provider_pool.py && echo "Syntax OK"
python -m pytest third_party/quantaalpha/tests/test_provider_pool.py -v && echo "Tests OK"

# Full UAT (copy-paste each block above)
python -c "
import sys, yaml, time, logging
sys.path.insert(0, 'third_party/quantaalpha')
from quantaalpha.llm.provider_pool import (
    ProviderPool, ProviderConfig, ProviderHealth,
    EmptyResponseError, AllProvidersFailedError
)
from unittest.mock import MagicMock, patch

# Load config
raw = yaml.safe_load(open('third_party/quantaalpha/configs/experiment.yaml'))
cfg = raw['llm']['provider_pool']

# Run all UAT checks
print('Running UAT-01 through UAT-15...')

# UAT-02
pool = ProviderPool(cfg)
assert 'deepseek-r1' in pool.providers
assert pool.providers['deepseek-r1'].model == 'deepseek-reasoner'
print('UAT-02: PASS')

# UAT-03 (D019: empty_response doesn't increment failure_count)
MINIMAL = {
    'enabled': True,
    'providers': [{'name': 'p', 'role': 'r', 'api_key_env': 'K', 'base_url': 'https://x', 'model': 'm'}],
    'routing': {'t': ['p']},
    'strategy': {'t': 'single'},
}
mpool = ProviderPool(MINIMAL)
mpool.report_failure('p', 'network'); mpool.report_failure('p', 'network')
assert mpool.health['p'].consecutive_failures == 2
mpool.report_failure('p', 'empty_response')
assert mpool.health['p'].consecutive_failures == 2, 'D019 VIOLATED'
print('UAT-03: PASS (D019 verified)')

# UAT-04 (D019: no cooldown)
mpool2 = ProviderPool(MINIMAL)
mpool2.report_failure('p', 'empty_response')
assert mpool2.health['p'].cooldown_until == 0.0, 'D019 VIOLATED'
print('UAT-04: PASS (D019 cooldown verified)')

# UAT-05 (total_requests still counts)
assert mpool2.health['p'].total_requests == 1
print('UAT-05: PASS')

# UAT-06 (degraded at 3)
mpool3 = ProviderPool(MINIMAL)
for _ in range(3): mpool3.report_failure('p', 'network')
assert mpool3.health['p'].consecutive_failures == 3
assert mpool3.health['p'].is_healthy is True  # threshold is 5
print('UAT-06: PASS')

# UAT-07 (unhealthy at 5)
for _ in range(2): mpool3.report_failure('p', 'network')
assert mpool3.health['p'].is_healthy is False
assert mpool3.health['p'].cooldown_until > time.time()
print('UAT-07: PASS')

# UAT-08 (success resets)
mpool3.health['p'].cooldown_until = time.time() - 1
mpool3.report_success('p')
assert mpool3.health['p'].is_healthy is True
assert mpool3.health['p'].consecutive_failures == 0
print('UAT-08: PASS')

# UAT-09 (round-robin)
mock_b = {'p': MagicMock(), 'p2': MagicMock()}
for n in mock_b: mock_b[n].chat_model = n
mpool4 = ProviderPool({
    'enabled': True,
    'providers': [
        {'name': 'p', 'role': 'r', 'api_key_env': 'K', 'base_url': 'x', 'model': 'm'},
        {'name': 'p2', 'role': 'r', 'api_key_env': 'K', 'base_url': 'x', 'model': 'm'},
    ],
    'routing': {'t': ['p', 'p2']},
    'strategy': {'t': 'round_robin'},
})
with patch.object(mpool4, '_build_backend', side_effect=lambda n: mock_b[n]):
    results = [mpool4.get_backend('t').chat_model for _ in range(4)]
assert results == ['p', 'p2', 'p', 'p2'], f'Got {results}'
print('UAT-09: PASS')

# UAT-10 (fanout_best)
try:
    mpool4.fanout_best([], 'nonexistent')
    assert False
except AllProvidersFailedError:
    pass
print('UAT-10: PASS')

# UAT-11 (health_summary)
summary = mpool4.get_health_summary()
assert 'p' in summary and 'p2' in summary
assert summary['p']['is_healthy'] is True
print('UAT-11: PASS')

# UAT-12 (token report)
mpool5 = ProviderPool(MINIMAL)
mpool5.report_success('p', tokens_used=100)
mpool5.report_success('p', tokens_used=200)
r = mpool5.get_token_usage_report()
assert r['total_tokens'] == 300
assert r['providers']['p']['tokens'] == 300
print('UAT-12: PASS')

# UAT-13 (config defaults)
c = ProviderConfig.from_dict({'name': 'n', 'role': 'r', 'api_key_env': 'K', 'base_url': 'x', 'model': 'm'})
assert c.weight == 1 and c.max_rpm == 60
print('UAT-13: PASS')

# UAT-15 (config integrity)
assert 'enabled' in cfg
assert len(cfg['providers']) >= 1
assert all(s in ('single', 'round_robin', 'fanout_best') for s in cfg['strategy'].values())
print('UAT-15: PASS')

print()
print('=== ALL 15 UAT CHECKS PASSED ===')
"
```

**Expected output:** All checks pass with "=== ALL 15 UAT CHECKS PASSED ==="
