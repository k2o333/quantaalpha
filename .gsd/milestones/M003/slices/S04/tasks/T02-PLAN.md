# T02: 配置格式 + 单元测试

**Slice:** S04 — ProviderPool 核心实现 (S2/D016)
**Milestone:** M003

## Description

在 experiment.yaml 中添加 `llm.provider_pool` 配置段，并编写完整的单元测试覆盖所有 ProviderPool 行为，包括 D019 空响应约束。

## Steps

1. **更新 experiment.yaml — 添加 provider_pool 配置段**
   在 `llm:` section 下添加：
   ```yaml
   provider_pool:
     enabled: true

     # Provider definitions
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
         max_rpm: 60

       - name: "qwen-coder"
         role: "json_repair"
         api_key_env: "QWEN_API_KEY"
         base_url: "http://localhost:8000/v1"
         model: "qwen-coder-plus"
         weight: 1
         max_rpm: 30

       - name: "glm4-flash"
         role: "screening"
         api_key_env: "GLM_API_KEY"
         base_url: "https://open.bigmodel.cn/api/paas/v4"
         model: "glm-4-flash"
         weight: 5
         max_rpm: 60

     # Role-based routing: task_type → [provider_names]
     routing:
       hypothesis_generation: ["deepseek-r1", "gpt4o"]
       factor_construction: ["deepseek-r1"]
       json_repair: ["qwen-coder"]
       evaluation_screening: ["glm4-flash"]
       feedback_summarization: ["gpt4o", "deepseek-r1"]

     # Strategy per task_type: single | round_robin | fanout_best
     strategy:
       hypothesis_generation: "fanout_best"
       factor_construction: "single"
       json_repair: "single"
       evaluation_screening: "single"
       feedback_summarization: "round_robin"

     # Health config
     health:
       failure_threshold: 5      # mark unhealthy after N failures
       degradation_threshold: 3  # mark degraded after N failures
       cooldown_seconds: 300      # 5 minutes cooldown
   ```
   验证 YAML 语法：`python -c "import yaml; yaml.safe_load(open('configs/experiment.yaml'))"`

2. **创建 tests/test_provider_pool.py**
   在 `third_party/quantaalpha/tests/` 下创建测试文件，使用 pytest 框架（参考现有 test_data_capability_registry.py 的 fixture 设置方式）

3. **测试：ProviderPool 初始化**
   ```python
   def test_provider_pool_init():
       config = {...}  # minimal valid config
       pool = ProviderPool(config)
       assert pool.providers["deepseek-r1"].model == "deepseek-reasoner"
       assert pool.role_to_providers["hypothesis"] == ["deepseek-r1", "gpt4o"]
   ```

4. **测试：get_backend 路由正确**
   验证 task_type 正确映射到配置的 provider

5. **测试：round_robin 轮询均衡**
   多次调用 get_backend("feedback_summarization")，验证各 Provider 轮流被选中（加权轮询）

6. **测试：D019 空响应约束（核心）**
   ```python
   def test_empty_response_no_cooldown():
       pool = ProviderPool(minimal_config)
       pool.report_failure("test-provider", "empty_response")
       health = pool.health["test-provider"]
       assert health.consecutive_failures == 0  # D019: 不增加failure_count
       assert health.cooldown_until == 0.0      # D019: 不触发cooldown
       assert health.is_healthy == True
   ```

7. **测试：网络错误增加 failure_count**
   ```python
   def test_network_error_increments_failure():
       pool = ProviderPool(minimal_config)
       for i in range(3):
           pool.report_failure("test-provider", "network")
       assert pool.health["test-provider"].consecutive_failures == 3
       # not yet unhealthy
       for i in range(2):
           pool.report_failure("test-provider", "network")
       # now unhealthy
       assert pool.health["test-provider"].is_healthy == False
       assert pool.health["test-provider"].cooldown_until > time.time()
   ```

8. **测试：cooldown 冷却期机制**
   验证 unhealthy provider 在 cooldown 期内被 _get_healthy_candidates 过滤

9. **测试：report_success 重置状态**
   ```python
   def test_success_resets_failure_count():
       pool = ProviderPool(minimal_config)
       pool.report_failure("test-provider", "network")
       pool.report_failure("test-provider", "network")
       assert pool.health["test-provider"].consecutive_failures == 2
       pool.report_success("test-provider")
       assert pool.health["test-provider"].consecutive_failures == 0
       assert pool.health["test-provider"].is_healthy == True
   ```

10. **测试：get_token_usage_report**
    调用 report_success 后验证 token 统计正确

11. **运行所有测试**
    ```bash
    python -m pytest third_party/quantaalpha/tests/test_provider_pool.py -v
    ```
    确保 10 个测试全部通过

## Must-Haves

- [ ] experiment.yaml 包含完整的 `llm.provider_pool` 配置段，YAML 语法正确
- [ ] test_provider_pool.py 包含 ≥10 个测试用例，覆盖所有路由策略和健康状态转换
- [ ] `test_empty_response_no_cooldown` 验证 D019 约束：空响应不增加 failure_count、不触发 cooldown
- [ ] `test_network_error_cooldown` 验证网络错误触发 cooldown
- [ ] 所有 pytest 测试通过

## Verification

```bash
# YAML 语法验证
python -c "import yaml; yaml.safe_load(open('third_party/quantaalpha/configs/experiment.yaml')); print('YAML OK')"

# 运行单元测试
python -m pytest third_party/quantaalpha/tests/test_provider_pool.py -v
```

## Observability Impact

- 测试框架本身即为诊断工具：失败的测试精确指出哪个行为不符合预期
- 无额外运行时信号（测试阶段不调用真实 LLM API）

## Inputs

- `third_party/quantaalpha/quantaalpha/llm/provider_pool.py` — T01 的输出，作为测试目标
- `third_party/quantaalpha/configs/experiment.yaml` — 在此文件中添加 provider_pool 配置段
- `third_party/quantaalpha/tests/test_data_capability_registry.py` — 参考测试 fixture 设置模式

## Expected Output

- `third_party/quantaalpha/configs/experiment.yaml` — 添加 `llm.provider_pool` 配置段（providers、routing、strategy、health 子段）
- `third_party/quantaalpha/tests/test_provider_pool.py` — 完整的单元测试文件（≥10 个测试用例）
