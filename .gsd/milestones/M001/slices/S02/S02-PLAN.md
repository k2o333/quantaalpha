# S02: 修复无限重试死循环和空响应检查

**Goal:** 为 factor_construct 阶段添加最大重试次数，防止无限循环卡死；在重试循环内检测空响应
**Demo:** 当 LLM 持续返回空响应或无效 JSON 时，程序在 10 次重试后优雅退出，而非无限循环

## Must-Haves

- `proposal.py` 中的 `while True` 循环改为有上限的重试
- **空响应检查放在重试循环内部**：检测到空响应时记录日志并 `continue`，而非直接抛异常
- 每次重试记录当前次数/最大次数
- 达到最大重试次数后抛出明确异常

## Verification

- `python -m py_compile third_party/quantaalpha/quantaalpha/factors/proposal.py` 通过
- `python -m py_compile third_party/quantaalpha/quantaalpha/llm/client.py` 通过
- 代码审查确认 `while True` 已被替换为 `for attempt in range(MAX_RETRIES)`
- 代码审查确认空响应检查逻辑在循环内部

## Observability / Diagnostics

- Runtime signals: 每次重试记录 `attempt X/MAX_RETRIES`
- Inspection surfaces: 日志显示重试进度和空响应检测
- Failure visibility: 达到最大重试后抛出 `RuntimeError` 包含失败原因

## Integration Closure

- Upstream surfaces consumed: S01 修复后的日志系统
- New wiring introduced: 有限重试逻辑 + 空响应检测
- What remains: 需要 S03 修复控制字符以提高成功率

## Tasks

- [ ] **T01: 在 client.py 添加空响应检测函数** `est:15m`
  - Why: 空响应检测需要统一逻辑，供 proposal.py 调用
  - Files: `third_party/quantaalpha/quantaalpha/llm/client.py`
  - Do: 在 `_create_chat_completion_inner_function` 中流式/非流式路径后添加空响应检测，返回空字符串而非抛异常（让调用方决定如何处理）
    ```python
    # 流式路径后（约 line 1027）
    if not resp or not resp.strip():
        logger.warning(f"Empty LLM response for model {model}, returning empty string")
        resp = ""
    
    # 非流式路径后（约 line 1033）
    if resp is None:
        resp = ""
    ```
  - Verify: `grep -n "Empty LLM response" third_party/quantaalpha/quantaalpha/llm/client.py` 找到检测逻辑
  - Done when: 空响应被检测并返回空字符串

- [ ] **T02: 修复 proposal.py 的无限重试循环** `est:25m`
  - Why: `while True` 循环在 LLM 返回空响应或无效 JSON 时导致无限重试
  - Files: `third_party/quantaalpha/quantaalpha/factors/proposal.py`
  - Do: 
    1. 将 `while True:`（约 line 483，`_convert_with_history_limit` 方法）改为 `MAX_RETRIES = 10; for attempt in range(MAX_RETRIES):`
    2. 在循环开始处添加空响应检测：
       ```python
       if not resp or not resp.strip():
           logger.warning(f"Empty response at attempt {attempt+1}/{MAX_RETRIES}, retrying...")
           continue
       ```
    3. 保留原有的 `robust_json_parse` 异常处理
    4. 达到最大次数后抛出 `RuntimeError(f"Factor proposal failed after {MAX_RETRIES} retries")`
  - Verify: 
    - `grep -n "MAX_RETRIES" third_party/quantaalpha/quantaalpha/factors/proposal.py` 找到常量定义
    - `grep -n "for attempt in range" third_party/quantaalpha/quantaalpha/factors/proposal.py` 找到有限循环
  - Done when: 循环有明确的最大重试次数，空响应被检测，超限后抛出异常

## Files Likely Touched

- `third_party/quantaalpha/quantaalpha/factors/proposal.py`
- `third_party/quantaalpha/quantaalpha/llm/client.py`

## Notes

- **阶段说明**: 死循环发生在 `factor_construct` 阶段（`_convert_with_history_limit` 方法），不是 `factor_propose` 阶段
- **触发条件**: 对任意持续的 JSON 解析失败（包括空响应、控制字符导致的解析错误）都会触发重试
- **与 S01 的关系**: S01 修复日志参数，本切片修复重试逻辑，两者独立但互补
