# S04: ProviderPool 核心实现 (S2/D016)

**Goal:** 实现 ProviderPool 封装层，支持多 Provider 并存、健康监控、自动降级，兼容现有 APIBackend 调用模式，并严格落实 D019 设计约束（空响应立即切换）。
**Demo:** `python -c "from quantaalpha.llm.provider_pool import ProviderPool, provider_pool; print('ProviderPool loaded:', provider_pool is not None)"` 通过；单元测试全部通过。

## Must-Haves

- ProviderPool 类支持 single、round_robin、fanout_best 三种路由策略
- ProviderHealth 状态机：healthy → degraded → unhealthy，自动冷却和恢复
- D019 约束：空响应（response.strip() == ""）立即切换 Provider，不增加 failure_count
- 网络错误：failure_count += 1，连续失败 >= 3 进入 cooldown
- experiment.yaml 支持 `llm.provider_pool.providers` 和 `llm.provider_pool.routing` 配置
- 向后兼容：无 `llm.provider_pool` 配置时，现有 `APIBackend()` 调用不受影响
- Token 使用追踪：每次调用记录 tokens_used，汇总到 `get_token_usage_report()`
- 单元测试覆盖所有路由策略和健康状态转换

## Proof Level

- This slice proves: **contract** — ProviderPool 类的 API 合约和健康状态机行为通过单元测试验证
- Real runtime required: **no** — 单元测试验证行为，无需实际 LLM API 调用
- Human/UAT required: **no**

## Verification

- `python -m py_compile third_party/quantaalpha/quantaalpha/llm/provider_pool.py` — 无语法错误
- `python -m pytest tests/test_provider_pool.py -v` — 所有测试通过
- `python -c "from quantaalpha.llm.provider_pool import ProviderPool, provider_pool; print('OK')"` — 导入成功

## Observability / Diagnostics

- **Runtime signals**: ProviderPool 内部 logger 输出健康状态转换（healthy→degraded→unhealthy）、cooldown 触发、空响应切换事件
- **Inspection surfaces**: `provider_pool.get_token_usage_report()` 返回各 Provider 的请求数、成功数、tokens 统计；`provider_pool.get_health_summary()` 返回健康状态快照
- **Failure visibility**: 日志记录 `Provider X returned empty, switching immediately`（空响应）；`Provider X failed (attempt N/M), cooldown until T`（网络错误）
- **Redaction constraints**: 日志不输出 API key，仅记录 provider name 和 error type

## Integration Closure

- **Upstream surfaces consumed**: `quantaalpha/llm/client.py`（APIBackend 类）、`quantaalpha/llm/config.py`（LLMSettings）
- **New wiring introduced in this slice**: 新建 `provider_pool.py`，导出 `ProviderPool`、`provider_pool` 单例；无运行时自动 hookup（proposal.py 集成由 S05 完成）
- **What remains before the milestone is truly usable end-to-end**: S05 将 proposal.py 的 `APIBackend()` 调用替换为 `provider_pool.call_*()`；S08 将 `get_token_usage_report()` 接入 ResourceManager

## Tasks

- [x] **T01: ProviderPool 核心类实现** `est:45m`
  - Why: ProviderPool 是 S04 的核心交付物，必须包含完整的健康状态机、三种路由策略、Token 追踪和 D019 空响应约束
  - Files: `third_party/quantaalpha/quantaalpha/llm/provider_pool.py`
  - Do: 实现 Provider、ProviderHealth dataclass；实现 ProviderPool 类，包含 get_backend()、fanout()、call_with_fallback()、fanout_best()、report_success()、report_failure()；实现健康状态机（degraded≥3 failures, unhealthy≥5 failures, cooldown=300s）；严格区分空响应和网络错误的处理逻辑（D019）；实现 get_token_usage_report() 和 get_health_summary()
  - Verify: `python -m py_compile provider_pool.py` 通过；单元测试验证所有路由策略和状态转换
  - Done when: ProviderPool 可独立实例化，所有方法签名正确，空响应立即切换逻辑可测试

- [x] **T02: 配置格式 + 单元测试** `est:30m`
  - Why: 需要通过配置驱动 ProviderPool 行为，并建立可重复的验收测试
  - Files: `third_party/quantaalpha/configs/experiment.yaml`、`third_party/quantaalpha/tests/test_provider_pool.py`
  - Do: 在 experiment.yaml 添加 `llm.provider_pool` 配置段（providers、routing、health、strategy）；编写 10+ 单元测试覆盖：初始化、空响应立即切换、网络错误增加 failure_count、冷却期机制、round_robin 均衡、fanout_best 并发取最优、Token 追踪
  - Verify: `python -m pytest tests/test_provider_pool.py -v` 全部通过；YAML 语法验证通过
  - Done when: 所有测试用例通过，配置可被正常解析

---

## Files Likely Touched

- `third_party/quantaalpha/quantaalpha/llm/provider_pool.py` — **新建**，ProviderPool 核心实现
- `third_party/quantaalpha/configs/experiment.yaml` — **修改**，添加 provider_pool 配置段
- `third_party/quantaalpha/tests/test_provider_pool.py` — **新建**，单元测试

---
estimated_steps: 6
estimated_files: 3
skills_used:
  - review
  - test
  - best-practices
