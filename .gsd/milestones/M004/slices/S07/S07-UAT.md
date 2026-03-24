# S07 UAT: Ensemble 聚合层

**Preconditions:** `mining` conda environment activated (`/root/miniforge3/envs/mining/bin/python`)

## Test Cases

### TC-01: EnsembleAggregator — union_dedup 策略

**Setup:** Import EnsembleAggregator and ModelResponse
**Steps:**
1. Create aggregator: `agg = EnsembleAggregator(strategy='union_dedup')`
2. Aggregate two responses with partial overlap:
   ```
   ModelResponse('gpt4', ['f1', 'f2', 'f3'])
   ModelResponse('claude', ['f2', 'f3', 'f4'])
   ```
3. Assert `result.output` contains all 4 unique factors: `['f1', 'f2', 'f3', 'f4']`
4. Assert `result.num_models == 2`
**Expected:** Pass. union_dedup deduplicates and merges.
**Edge:** Model returns empty list → empty output preserved.

---

### TC-02: EnsembleAggregator — intersection 策略

**Setup:** Create aggregator with `strategy='intersection'`
**Steps:**
1. Aggregate: `ModelResponse('m1', ['a', 'b'])` + `ModelResponse('m2', ['b', 'c'])`
2. Assert `result.output == ['b']`
3. Add third model: `ModelResponse('m3', ['b', 'x'])`
4. Re-aggregate, assert `set(result.output) == {'b'}`
**Expected:** Only common elements survive.
**Edge:** No intersection → empty output.

---

### TC-03: EnsembleAggregator — voting 策略

**Setup:** `agg = EnsembleAggregator(strategy='voting', voting_threshold=2)`
**Steps:**
1. Aggregate 3 responses:
   - `ModelResponse('m1', ['f1', 'f2'])`
   - `ModelResponse('m2', ['f2', 'f3'])`
   - `ModelResponse('m3', ['f2', 'f1'])`
2. Assert `result.source_counts['f2'] == 3`
3. Assert `result.source_counts['f1'] == 2`
4. Assert `result.source_counts['f3'] == 1`
5. Assert `result.output` contains `['f2', 'f1']` (f3 filtered by threshold=2)
**Expected:** f2 appears in all 3, f1 in 2 of 3, f3 in only 1.
**Edge:** `threshold=None` → defaults to majority `ceil(n/2)`.

---

### TC-04: EnsembleAggregator — fusion_score 策略

**Setup:** `agg = EnsembleAggregator(strategy='fusion_score')`
**Steps:**
1. Aggregate with quality scores:
   ```
   ModelResponse('gpt4', ['f1', 'f2'], quality_score=0.9)
   ModelResponse('claude', ['f2', 'f3'], quality_score=0.5)
   ```
2. Assert `result.fusion_scores` is not None
3. Assert `result.fusion_scores['f2'] > result.fusion_scores['f3']` (f2 gets votes from both models)
4. Assert `result.fusion_scores['f1'] > result.fusion_scores['f3']` (f1 from high-quality model)
**Expected:** fusion_score reflects both vote count and quality weight.

---

### TC-05: EnsembleAggregator — accumulate 流式积累

**Setup:** `agg = EnsembleAggregator(strategy='voting', voting_threshold=2)`
**Steps:**
1. `agg.accumulate(ModelResponse('m1', ['f1', 'f2']))`
2. `agg.accumulate(ModelResponse('m2', ['f2', 'f3']))`
3. `agg.accumulate(ModelResponse('m3', ['f2', 'f1']))`
4. Assert `agg.get_accumulated_count() == 3`
5. `result = agg.aggregate()`
6. Assert `result.num_models == 3`
7. `agg.reset()`
8. Assert `agg.get_accumulated_count() == 0`
**Expected:** accumulate accumulates responses; reset clears them.

---

### TC-06: ProviderPool — round_robin 多 Key 轮询

**Setup:** `pool = ProviderPool(routing='round_robin')`
**Steps:**
1. Add provider with 3 keys: `pool.add_provider('p1', api_keys=['k1', 'k2', 'k3'])`
2. Call `get_key_and_provider('p1')` 9 times in a loop
3. Assert sequence: `['k1', 'k2', 'k3', 'k1', 'k2', 'k3', 'k1', 'k2', 'k3']`
**Expected:** Keys cycle evenly.
**Edge:** Single key → always returns that key.

---

### TC-07: ProviderPool — least_latency 智能选择

**Setup:** `pool = ProviderPool(routing='least_latency', min_latency_samples=2)`
**Steps:**
1. Add two providers: `fast` (k1) and `slow` (k2)
2. Record latencies: `slow` → 500ms (×5), `fast` → 30ms (×5)
3. Call `get_key_and_provider()` — should pick `fast`/`k1`
4. Record 1 sample for new key: `pool.record_latency('new_provider', 'new_key', 20.0)`
5. Assert no error when selecting from unvisited provider
**Expected:** least_latency selects fastest after sufficient samples. Falls back to RR without enough data.

---

### TC-08: ProviderPool — 延迟统计

**Setup:** `pool = ProviderPool()`
**Steps:**
1. Add provider `p1` with key `k1`
2. Record: 100ms, 200ms, 300ms
3. Get stats: `stats = pool.get_latency_stats('p1')`
4. Assert `stats['k1'].sample_count == 3`
5. Assert `stats['k1'].avg_latency_ms == 200.0`
6. Assert `stats['k1'].min_latency_ms == 100.0`
7. Assert `stats['k1'].max_latency_ms == 300.0`
**Expected:** Running statistics update correctly.
**Edge:** `get_latency_stats('nonexistent')` → None (not empty dict).

---

### TC-09: ProviderPool — reset_latency_stats

**Setup:** `pool = ProviderPool()`
**Steps:**
1. Add provider `p1` with key `k1`
2. Record: 100ms (×3)
3. `pool.reset_latency_stats('p1')`
4. `stats = pool.get_latency_stats('p1')`
5. Assert `stats['k1'].sample_count == 0` (key still present, stats reset)
6. `pool.reset_latency_stats()` (reset all)
7. Verify both providers' keys have sample_count == 0
**Expected:** Keys preserved, stats zeroed. Full reset clears all providers.

---

### TC-10: ProviderPool — 线程安全

**Setup:** 4 threads simultaneously
**Steps:**
1. Create pool with `round_robin`, add 4 keys to `p1`
2. Launch 4 threads, each calling `get_key_and_provider('p1')` 50 times
3. Launch 4 threads, each recording 100 latency samples
4. Wait for all threads to complete
5. Assert no exceptions raised
6. Assert total key accesses == 200, total latency records == 400
**Expected:** No race conditions. Thread-safe under concurrent load.

---

### TC-11: ProviderPool — multi-provider least_latency

**Setup:** `pool = ProviderPool(routing='least_latency', min_latency_samples=1)`
**Steps:**
1. Add providers `fast` and `slow` (1 key each)
2. Record slow: 500ms (×5), fast: 30ms (×5)
3. Call `get_key_and_provider()` (no specific provider)
4. Assert selected key is from `fast` provider
**Expected:** least_latency evaluates across all providers, not just within one.

---

### TC-12: EnsembleAggregator — dict 输入转换

**Setup:** `agg = EnsembleAggregator(strategy='union_dedup')`
**Steps:**
1. Call `agg.aggregate([{'model_name': 'm1', 'raw_output': ['x']}, {'model_name': 'm2', 'raw_output': ['y']}])`
2. Assert `result.num_models == 2`
3. Assert `result.output == ['x', 'y']`
4. Assert `result.strategy == 'union_dedup'`
**Expected:** Dicts auto-converted to ModelResponse using field mapping.

---

### TC-13: 配置完整性验证

**Steps:**
1. Read `configs/experiment.yaml`
2. Assert `provider_pool` section exists with keys: `routing`, `min_latency_samples`, `providers`
3. Assert `ensemble` section exists with keys: `default_strategy`, `voting`, `fusion_score`, `strategies`
4. Assert `ensemble.strategies.intersection` and `ensemble.strategies.union_dedup` exist
**Expected:** Both config sections present with required fields.

---

### TC-14: py_compile 全部通过

**Steps:**
1. `python -m py_compile quantaalpha/llm/ensemble.py`
2. `python -m py_compile quantaalpha/llm/provider_pool.py`
**Expected:** Both exit code 0, no output.

---

## Run Command

```bash
cd /home/quan/testdata/aspipe_v4/third_party/quantaalpha
/root/miniforge3/envs/mining/bin/python -m pytest quantaalpha/tests/test_ensemble.py -v
# Expected: 54 passed in <1s
```
