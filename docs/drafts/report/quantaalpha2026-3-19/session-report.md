# quantaalpha data_capability_registry reintegration session report

日期：2026-03-19
范围：记录本次 session 到目前为止在 `quantaalpha` data capability registry reintegration 上实际做了什么，尤其是具体改了哪些文件、怎么改的、跑了哪些验证、发现了哪些未解决问题。

---

## 1. 任务目标

本次 session 的主任务是实现并验证下面这份变更文档里的需求：

- `docs/03-changes/quantaalpha/planned/2026-03-18-data-capability-registry-reintegration.md`

目标是把 `Data Capability Registry` 以受控方式重新接回 `quantaalpha` 的 hypothesis / experiment prompt 主链，同时保留 fallback，不让注入失败直接打断整条因子挖掘链。

---

## 2. 本次 session 实际做了什么

### 2.1 前置阅读与定位

在开始实现前，读取并对齐了以下文档与代码：

- `docs/00-governance/agent.md`
- `docs/00-governance/rules.md`
- `docs/02-modules/quantaalpha.md`
- `docs/00-governance/doc-rules.md`
- `docs/03-changes/quantaalpha/planned/2026-03-18-data-capability-registry-reintegration.md`
- `third_party/quantaalpha/quantaalpha/factors/data_capability.py`
- `third_party/quantaalpha/quantaalpha/factors/experiment.py`
- `third_party/quantaalpha/configs/experiment.yaml`
- `third_party/quantaalpha/tests/test_continuous_factor_features.py`
- `third_party/quantaalpha/quantaalpha/factors/qlib_utils.py`

当时识别出的关键集成面如下：

- downstream consumer：`QlibAlphaAgentScenario` 组装的 `source_data`
- source-of-truth：`quantaalpha/factors/data_capability.py`
- failure surface：registry 渲染异常可能导致 prompt 注入链退化
- 可反证命令：`/root/miniforge3/envs/mining/bin/python -m pytest third_party/quantaalpha/tests -v`

### 2.2 设计确认

在实现前先收敛了一个最小设计，并得到确认：

- 只保留一个 registry 入口：`data_capability.py`
- 在 `experiment.py` 设置唯一注入点
- 默认保留旧的 `source_data` 文本
- 通过配置开关决定是否追加 registry 文本
- 注入失败时 fallback 到旧逻辑
- 先写测试，再写实现

### 2.3 先写测试，再实现

本次 session 是按 TDD 顺序推进的：

1. 先新增回归测试文件
2. 跑红灯，确认失败原因
3. 补生产代码
4. 再跑绿灯
5. 收到 review 后再补两条健壮性测试和对应修复

---

## 3. 本 session 实际改动了哪些文件

下面只记录本 session 明确动手创建或修改过的文件，不把工作区里原本就存在的其他脏改动算进来。

### 3.1 修改：`third_party/quantaalpha/configs/experiment.yaml`

改动目的：增加显式开关，控制是否向 prompt 的 `source_data` 注入 data capability registry。

具体改法：

- 在文件末尾新增配置段：

```yaml
data_capability_registry:
  enabled: true
```

影响：

- 让 registry 注入从“纯 helper 存在”变成“有配置门控的主链行为”
- 默认启用，但可以快速关闭

### 3.2 修改：`third_party/quantaalpha/quantaalpha/factors/data_capability.py`

改动目的：把 registry helper 收敛成稳定、可测试、可保守回退的单一入口。

具体改法：

1. 新增 `DEFAULT_CAPABILITY_SPEC`
   - 统一默认值：
     - `fields: []`
     - `freq: "daily"`
     - `lag_days: 0`
     - `join_mode: "same_day"`
     - `factor_hints: []`

2. 新增 `normalize_capability_spec(spec)`
   - 把 capability spec 规范化
   - 要求输入必须是 mapping
   - 对缺省字段补默认值
   - 对显式 `None` 也按默认值处理
   - 这样即使未来 YAML 写了 `fields: null` 也不会在这里炸掉

3. 新增 `get_data_capabilities(capabilities=None)`
   - 统一走规范化
   - 对 capability 名称做稳定排序
   - 便于测试和 prompt 输出可预测

4. 重写 `render_data_capabilities(capabilities=None)`
   - 渲染不再直接读原始 dict
   - 始终从规范化后的 registry 渲染
   - 输出顺序稳定
   - 缺省字段不会再渲染成 `unknown`
   - 缺省 `factor_hints` 渲染成 `general research`

这次实际解决的问题：

- registry 输出不稳定
- 缺省字段渲染过于粗糙
- 显式 `null` 输入会触发异常

### 3.3 修改：`third_party/quantaalpha/quantaalpha/factors/experiment.py`

改动目的：把 registry 真正接到 scenario 组装点，而不是停留在 helper 层。

具体改法：

1. 新增配置读取常量和辅助函数
   - `EXPERIMENT_CONFIG_PATH`
   - `DEFAULT_REGISTRY_ENABLED = True`
   - `_load_experiment_config(...)`
   - `_is_registry_enabled(...)`

2. 新增 source_data 组装辅助函数
   - `_merge_source_data_with_registry(base_source_data, registry_text)`
   - `_build_source_data_description(use_local, registry_enabled, capabilities=None)`

3. 修改 `QlibAlphaAgentScenario.__init__`
   - 新增可选参数：
     - `data_capability_registry_enabled`
     - `data_capabilities`
     - `experiment_config_path`
   - 原始 `source_data` 不再直接赋值
   - 改为：
     1. 解析开关
     2. 构造基础 source_data
     3. 开启时追加 registry 文本
     4. 失败时 fallback

4. 根据 review 再补可观测性
   - 在 fallback 的 `except Exception` 中增加：

```python
logger.warning(
    "Failed to inject data capability registry, falling back to basic source data.",
    exc_info=True,
)
```

这次实际解决的问题：

- registry 终于进入真实主链
- 可以通过配置关闭
- 渲染失败不会让 scenario 初始化直接崩溃
- fallback 不再是完全静默吞异常

### 3.4 新增：`third_party/quantaalpha/tests/test_data_capability_registry.py`

改动目的：给这次 reintegration 补一组独立、可运行、低耦合的回归测试。

具体改法：

1. 新建独立测试文件
2. 用 stub module 隔离 `rdagent`、`workspace`、`qlib_utils`、`logger`
3. 补了以下测试场景：

- `test_render_data_capabilities_uses_defaults_and_stable_order`
  - 验证渲染包含稳定顺序与保守默认值

- `test_normalize_capability_spec_applies_conservative_defaults`
  - 验证缺省字段被补默认值

- `test_normalize_capability_spec_treats_null_like_missing`
  - 验证显式 `None` 按缺省处理

- `test_scenario_injects_registry_when_enabled`
  - 验证开关开启时 `source_data` 真正包含 registry 文本

- `test_scenario_skips_registry_when_disabled`
  - 验证开关关闭时恢复旧逻辑

- `test_scenario_falls_back_to_base_source_data_on_registry_failure`
  - 验证异常时 fallback 到基础 `source_data`
  - 验证 `logger.warning(..., exc_info=True)` 被调用

这份测试文件是本次最关键的交付之一，因为它直接证明：

- helper 不只是存在
- scenario 的真实消费路径已经改变
- fallback 和可观测性也被纳入回归保护

### 3.5 新增：`docs/superpowers/plans/2026-03-18-data-capability-registry-reintegration.md`

改动目的：在实现前留下一个很短的执行计划文档，说明这次 reintegration 的执行顺序与验证路径。

内容概括：

- 先锁 registry 行为
- 再接 scenario 注入
- 最后补验证

备注：

- 这个文件在本地已创建
- 但当前根仓库 `git status --short` 没有显示它，说明它可能未被当前仓库追踪，或者受到现有 gitignore / 仓库结构影响
- 这里仍然如实记录：本 session 确实创建过这个文件

---

## 4. 本次没有改，但在验证中暴露出来的既有问题

下面这些不是本 session 为了 data capability registry reintegration 而修改的内容，但在更强验证时暴露出来，需要和“本次改动”明确区分。

### 4.1 全量测试收集失败

执行：

```bash
/root/miniforge3/envs/mining/bin/python -m pytest third_party/quantaalpha/tests -v
```

结果：

- 在 test collection 阶段就报错，没进入完整执行
- 暴露了 3 个既有导入错误：
  - `tests/test_continuous_orchestrator.py` 无法从 `quantaalpha.continuous` 导入 `ContinuousOrchestrator`
  - `tests/test_revalidate_boundary.py` 无法从 `quantaalpha.cli` 导入 `REVALIDATE_MODE_DRY_RUN`
  - `tests/test_scheduler_summary.py` 无法从 `quantaalpha.pipeline.factor_backtest` 导入 `run_real_backtest`

结论：

- 当前不能声称 `quantaalpha` 全量测试通过
- 这 3 个错误不属于本 session 针对 registry reintegration 的直接修改范围

### 4.2 health_check 受环境权限限制失败

执行：

```bash
/root/miniforge3/envs/mining/bin/quantaalpha health_check
```

结果：

- Docker API 访问报 `PermissionError(1, 'Operation not permitted')`
- socket 端口检测也报 `PermissionError: [Errno 1] Operation not permitted`

结论：

- 这是当前运行环境权限问题
- 不能把它算成 data capability registry reintegration 本身的功能性失败

---

## 5. 本次跑过哪些验证

以下命令都实际执行过：

### 5.1 新增测试文件红灯验证

执行：

```bash
/root/miniforge3/envs/mining/bin/python -m pytest third_party/quantaalpha/tests/test_data_capability_registry.py -v
```

最初结果：

- 先失败，暴露出缺失实现和一个测试桩问题
- 修正测试桩后，继续失败在真正缺口上

意义：

- 证明测试不是假阳性
- 证明新增测试确实覆盖到了缺失行为

### 5.2 registry reintegration 绿灯验证

执行：

```bash
/root/miniforge3/envs/mining/bin/python -m pytest third_party/quantaalpha/tests/test_data_capability_registry.py -v
```

后续结果：

- 第一次实现后：`5 passed`
- 接受 code review 建议并追加健壮性修复后：`6 passed`

### 5.3 兼容已有 helper 回归测试

执行：

```bash
/root/miniforge3/envs/mining/bin/python -m pytest third_party/quantaalpha/tests/test_continuous_factor_features.py -k data_capability_and_llm_routing_helpers -v
```

结果：

- `1 passed`

意义：

- 证明旧的 helper 回归测试仍可通过

### 5.4 编译检查

执行：

```bash
/root/miniforge3/envs/mining/bin/python -m compileall \
  third_party/quantaalpha/quantaalpha/factors/data_capability.py \
  third_party/quantaalpha/quantaalpha/factors/experiment.py
```

结果：

- 退出码 `0`

意义：

- 证明核心改动文件可正常编译

---

## 6. 本 session 的 code review 处理

在 session 中途收到两条 review 建议，并确认后纳入实现：

1. `experiment.py` 的 fallback 不应完全静默吞异常
   - 已加 `logger.warning(..., exc_info=True)`

2. `data_capability.py` 应防御 YAML 显式 `null`
   - 已将 `None` 输入统一按默认值收口
   - 并新增专门测试覆盖

---

## 7. 到目前为止的结论

如果只看这次 data capability registry reintegration：

- 主链注入已经完成
- 配置门控已经加上
- fallback 已经存在且不再完全静默
- 针对本次改动的定向回归测试通过

如果看 `quantaalpha` 模块整体：

- 当前不能宣称全量测试通过
- 原因不是本次 reintegration 单点测试失败
- 而是仓库内已有其他测试文件在收集阶段就存在导入错误

---

## 8. 本次 session 产出的“精确文件清单”

本 session 明确修改 / 新增过的文件如下：

- `third_party/quantaalpha/configs/experiment.yaml`
- `third_party/quantaalpha/quantaalpha/factors/data_capability.py`
- `third_party/quantaalpha/quantaalpha/factors/experiment.py`
- `third_party/quantaalpha/tests/test_data_capability_registry.py`
- `docs/superpowers/plans/2026-03-18-data-capability-registry-reintegration.md`
- `docs/drafts/report/quantaalpha2026-3-19/session-report.md`

其中，与功能实现直接相关的核心文件是前 4 个。
