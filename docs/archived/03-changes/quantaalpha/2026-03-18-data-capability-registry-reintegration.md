---
doc_type: change
module: quantaalpha
status: planned
owner: quan
created: 2026-03-18
updated: 2026-03-18
summary: Data Capability Registry 受控接回主链
priority: P1
depends_on:
  - docs/04-decisions/ADR-001-continuous-factor-research.md
  - docs/04-decisions/ADR-003-external-continuous-factor-research-modules.md
---

---

## 一、目标

将 `Data Capability Registry` 以**小模块、可回退、可控注入**的方式接回 `quantaalpha` 挖掘主链，使 LLM 在因子挖掘前就能获得当前可用数据维度、字段频率、滞后和对齐方式的统一描述。

本迭代解决的问题不是“再做一套大而全的数据目录系统”，而是把当前已存在但未进入主运行路径的注册表能力，重新接成一个可稳定复用的最小模块。

推荐落地方式：

- 保留 `data_capability.py` 作为单一注册表入口
- 增加显式开关，默认受控启用或可快速关闭
- 在 hypothesis / experiment 组装阶段注入精简描述
- 保留旧逻辑 fallback，避免 prompt 注入异常时整条主链不可运行

---

## 二、范围

包含：

- 数据能力注册表结构收敛
- 注册表渲染逻辑收敛
- 在挖掘前 prompt / scenario 组装阶段的受控注入
- 配置开关与 fallback 机制
- 对应自动化测试

不包含：

- 数据血缘追踪
- 数据 freshness 审计
- 自动字段发现
- 数据库或服务化 registry
- 回测阶段的数据加载重构

### 2.1 Downstream Consumer

- hypothesis generation 阶段的 LLM prompt
- factor construction / experiment assembly 阶段的场景上下文
- 后续 planning / constraint check 逻辑（如果后续扩展）

当前真实消费者应是挖掘主链前半段，而不是回测结果消费链。

### 2.2 Write Target / Source of Truth

- 注册表结构的 source-of-truth 应集中在：
  - `third_party/quantaalpha/quantaalpha/factors/data_capability.py`
  - 或一个单独配置文件，由 `data_capability.py` 统一加载
- 对模型可见的数据能力描述必须从统一入口渲染，不得重新散落到多个 prompt 文本中

### 2.3 Failure Semantics

- 注册表注入失败时，不应让整条挖掘链路直接不可用
- registry 配置缺失或部分字段不完整时，应回退到保守渲染，而不是抛出难以理解的异常
- 若配置开关关闭，应明确回到旧逻辑，而不是“看似启用、实际未注入”
- 不能因为 registry 注入而让 prompt 无控制膨胀，导致超时或主链退化

### 2.4 Caller Contract

- 场景组装调用方：应能拿到稳定、简洁、可预测的数据能力文本
- 配置调用方：应能显式开启或关闭 registry 注入
- reviewer：必须能从真实 prompt / scenario 路径确认注册表已被消费，而不是只存在 helper 函数

### 2.5 What Does Not Count As Done

- 只保留 `DATA_CAPABILITIES` 常量，不算完成
- 只新增渲染函数，但没有主链消费路径，不算完成
- 只在文档里说明将来会注入，不算完成
- 只做 helper 测试，不验证真实 scenario / prompt 已改变，不算完成
- 把所有字段一次性灌进 prompt，导致 prompt 体积显著膨胀，不算正确完成

---

## 三、代码落点

- `third_party/quantaalpha/quantaalpha/factors/data_capability.py`
- `third_party/quantaalpha/quantaalpha/factors/experiment.py`
- 如需补配置：
  - `third_party/quantaalpha/configs/experiment.yaml`
  - 或其他当前实际使用的挖掘配置

建议新增或补充测试：

- `third_party/quantaalpha/tests/test_data_capability_registry.py`
- 如复用现有测试文件，也可补到：
  - `third_party/quantaalpha/tests/test_continuous_factor_features.py`

---

## 四、开发方案

### 4.1 先固定最小 registry 形态

首版只支持最小结构：

- `fields`
- `freq`
- `lag_days`
- `join_mode`
- `factor_hints`

首版至少保留两个维度：

- `price_volume`
- `financial`

不在本迭代引入：

- 自动字段发现
- 动态元数据同步
- 复杂 schema 版本管理

### 4.2 统一渲染入口

通过单一渲染函数把 registry 转成给模型看的精简文本，要求：

- 文本长度受控
- 缺失可选字段时使用保守默认值
- 输出字段顺序稳定，便于测试
- 不暴露原始 Python dict 字符串

### 4.3 在主链前半段受控注入

接入点应选择在 hypothesis / experiment 组装阶段，而不是回测后阶段。

建议原则：

1. 在 scenario 或 source-data context 中拼接 registry 说明
2. 让模型在提出方向和构造表达式前看到可用维度说明
3. 不修改回测链的真实数据访问语义

### 4.4 增加配置开关与 fallback

必须有显式开关，例如：

- `data_capability_registry.enabled`

并约束：

- 开启时才注入 registry
- 关闭时恢复旧逻辑
- registry 渲染异常时优先 fallback，而不是中断主链

### 4.5 控制 prompt 体积

这是本迭代最关键的回归风险。

要求：

- 首版只注入精简维度说明
- 不把无关字段全面展开到 prompt
- 如后续维度变多，应优先支持按维度筛选或受控裁剪，而不是线性堆长文本

### 4.6 保留未来扩展位，但不偷跑

本迭代可以为后续外插 `data-capability-registry` 模块保留接口，例如：

- 从静态常量切换到配置文件加载
- 未来由外部模块生成 registry 再传入主链

但本次不做服务化，也不引入跨模块复杂协议。

### 4.7 实现顺序清单

下面的顺序按“先锁边界，再接主链，再补 fallback，最后补测试与验证”组织，避免重走上次“helper 做了，但主链没稳定保留”的老路。

#### Task 1: 固定 registry 模块接口

**目标：** 先把 `data_capability.py` 变成稳定单入口，避免后续在多处拼字段。

**修改文件：**

- `third_party/quantaalpha/quantaalpha/factors/data_capability.py`

**建议完成的函数/对象：**

1. `DATA_CAPABILITIES`
   - 保留为最小 registry 常量
   - 首版只保留 `price_volume` 与 `financial`

2. `render_data_capabilities(capabilities: dict | None = None) -> str`
   - 保证输出顺序稳定
   - 缺省字段有保守默认值
   - 输出长度受控

3. 建议新增：
   - `get_data_capabilities(capabilities: dict | None = None) -> dict[str, dict[str, Any]]`
   - `normalize_capability_spec(spec: dict[str, Any]) -> dict[str, Any]`

**本任务完成判据：**

- registry 有唯一入口
- 渲染输出稳定、可预测
- registry 缺省字段不会导致异常

**本任务测试：**

- 新增 `test_data_capability_registry.py`
- 覆盖：
  - 渲染包含 `fields/freq/lag_days/join_mode/factor_hints`
  - 缺少可选字段时仍能渲染
  - 输出顺序稳定

#### Task 2: 把 registry 接到 scenario 组装点

**目标：** 确保 registry 真正进入挖掘主链前半段，而不是只停留在 helper。

**修改文件：**

- `third_party/quantaalpha/quantaalpha/factors/experiment.py`

**建议完成的函数/对象：**

1. `QlibAlphaAgentScenario.__init__`
   - 当前这里直接使用 `get_data_folder_intro()`
   - 需要改成“旧 source_data 描述 + 可选 registry 注入”的组装逻辑

2. 建议新增辅助函数：
   - `_build_source_data_description(use_local: bool, registry_enabled: bool, capabilities: dict | None = None) -> str`
   - 或 `_merge_source_data_with_registry(base_source_data: str, registry_text: str | None) -> str`

**约束：**

- 默认 source_data 描述不能丢
- registry 注入要附加在已有 source_data 上，而不是完全替换
- 注入点只应有一处，避免后续多地维护

**本任务完成判据：**

- `self._source_data` 的真实内容可包含 registry 渲染结果
- 关闭开关时恢复旧描述
- 开启开关时主链能看到受控注入内容

**本任务测试：**

- 直接实例化 `QlibAlphaAgentScenario`
- 断言：
  - 开关开启时 `scenario.source_data` 含 registry 文本
  - 开关关闭时不含 registry 文本

#### Task 3: 增加配置开关与 fallback

**目标：** 保证 registry 是“受控接入”，而不是硬接入。

**修改文件：**

- `third_party/quantaalpha/configs/experiment.yaml` 或当前实际生效配置
- 如有需要，`third_party/quantaalpha/quantaalpha/factors/experiment.py`

**建议完成的配置与函数：**

1. 建议新增配置段：

```yaml
data_capability_registry:
  enabled: true
```

2. 在 scenario 组装逻辑中读取该配置或等价开关

3. 如渲染异常，fallback 到旧 `get_data_folder_intro()` 输出

**约束：**

- 开关语义必须清晰
- 未配置时应有稳定默认行为
- fallback 行为必须显式、可测试

**本任务完成判据：**

- registry 关闭时主链仍可运行
- registry 异常时不会让主链直接失败
- 配置语义清晰，不存在“看似开启、实际未生效”

**本任务测试：**

- mock/patch registry 渲染异常
- 断言 scenario 仍能构建
- 断言最终回退到旧 source_data 描述

#### Task 4: 控制注入文本体积

**目标：** 避免再次出现 prompt 体积膨胀导致主链退化。

**修改文件：**

- `third_party/quantaalpha/quantaalpha/factors/data_capability.py`
- 如有必要，`third_party/quantaalpha/quantaalpha/factors/experiment.py`

**建议完成的函数/策略：**

1. 在 `render_data_capabilities()` 内限制每个维度的输出粒度
2. 必要时增加：
   - `render_data_capabilities(capabilities=None, max_fields_per_dimension: int = 6) -> str`
   - 或 `select_capability_dimensions(...)`

**约束：**

- 首版不做复杂筛选系统
- 但要避免未来维度增多后 prompt 线性失控

**本任务完成判据：**

- 注入文本在测试中可预测、不过长
- 新增字段或维度时，渲染行为仍受控

**本任务测试：**

- 构造字段很多的 fake capability
- 断言输出仍保持受控格式
- 断言不会把全部字段无上限展开

#### Task 5: 补主链消费边界测试

**目标：** 证明 registry 被真实主链消费，而不是只在 helper 存在。

**修改文件：**

- `third_party/quantaalpha/tests/test_data_capability_registry.py`

**建议新增测试函数：**

1. `test_render_data_capabilities_includes_core_metadata()`
2. `test_render_data_capabilities_handles_missing_optional_fields()`
3. `test_scenario_injects_registry_text_when_enabled()`
4. `test_scenario_falls_back_to_legacy_source_data_when_disabled()`
5. `test_scenario_falls_back_when_registry_rendering_fails()`
6. `test_registry_render_output_is_length_controlled()`

**本任务完成判据：**

- helper、scenario 注入、fallback、长度控制四类边界均有测试

#### Task 6: 跑最小验证闭环

**目标：** 用最小命令验证这次变更不只在测试里成立。

**建议执行顺序：**

1. 编译检查

```bash
cd /home/quan/testdata/aspipe_v4
/root/miniforge3/envs/mining/bin/python -m compileall third_party/quantaalpha/quantaalpha
```

2. 定向测试

```bash
cd /home/quan/testdata/aspipe_v4
/root/miniforge3/envs/mining/bin/python -m pytest third_party/quantaalpha/tests/test_data_capability_registry.py -q
```

3. 如已有轻量入口可观察 source_data，补一次手工检查

**本任务完成判据：**

- compileall 通过
- registry 专项测试通过
- 至少确认一次真实 scenario 路径上的注入与 fallback 行为

#### Task 7: 文档闭环

**目标：** 避免“代码做了，文档仍停留在旧状态”。

**修改文件：**

- 当前文档 `2026-03-18-data-capability-registry-reintegration.md`
- 如当前真相改变，再更新：
  - `docs/02-modules/quantaalpha.md`

**需要回填的内容：**

- `Final Result`
- `Validation Evidence`
- `Lessons Learned`

**本任务完成判据：**

- change doc 记录与实际实现一致
- 若主运行路径已改变，模块文档同步更新

### 4.8 推荐实施提交边界

为了降低回归风险，建议按下面边界提交，而不是一次性大改：

1. `data_capability.py` 接口收敛 + helper 测试
2. `experiment.py` 注入主链 + scenario 测试
3. 配置开关 + fallback 测试
4. 长度控制 + 回归测试
5. 文档回填

---

## 五、测试方案

### 5.1 单元测试

新增 `test_data_capability_registry.py`，至少覆盖：

1. 渲染函数能稳定输出 `fields/freq/lag_days/join_mode/factor_hints`
2. 可选字段缺失时使用保守默认值而不是报错
3. registry 开关关闭时，旧逻辑仍可工作
4. 新增一个维度后，渲染输出随之变化，但不需要改多个 prompt 文件

### 5.2 集成测试

至少有 1 个测试直接验证：

- hypothesis / experiment 组装阶段实际消费了 registry 渲染结果

建议断言：

- scenario 或 source-data context 中出现 registry 注入文本
- 开关关闭时，该注入文本消失或恢复旧内容

### 5.3 手工验收

执行一次最小挖掘链路或组装链路，检查：

- 开启开关时，prompt / scenario 中可看到精简的数据能力说明
- 关闭开关时，主链仍可运行
- registry 注入没有明显造成 prompt 爆炸式增长

### 5.4 Required Boundary Test

必须至少有 1 个测试直接证明：

- registry 渲染结果被真实主链消费，而不是只在 helper 层存在

并至少有 1 个测试直接证明：

- registry 关闭或异常时，旧链路仍能运行

### 5.5 Disproof Command

下面任一结果都应直接推翻“本迭代已完成”的说法：

```bash
cd /home/quan/testdata/aspipe_v4
/root/miniforge3/envs/mining/bin/python -m pytest third_party/quantaalpha/tests/test_data_capability_registry.py -q
```

```bash
cd /home/quan/testdata/aspipe_v4
/root/miniforge3/envs/mining/bin/python -m compileall third_party/quantaalpha/quantaalpha
```

### 5.6 Primary Evidence / Secondary Evidence

Primary evidence:

- 至少 1 个测试证明 registry 已进入真实 scenario / prompt 组装路径
- 至少 1 个测试证明关闭开关或 registry 异常时主链可 fallback
- 至少 1 个测试证明渲染内容稳定且字段完整

Secondary evidence:

- 只验证 helper 返回字符串
- 只验证文档说明
- 只检查常量结构存在

Secondary evidence 可以辅助说明意图，但不能单独支撑 `tested`。

---

## 六、验收标准

1. 数据能力描述来自统一入口，而不是继续散落在多处 prompt 文本中
2. registry 已进入真实挖掘前半段主链，而不是停留在 helper
3. 开关关闭时旧链路仍可运行
4. registry 注入不会明显放大 prompt 体积或让主链不可用
5. 新增维度时，不需要改多个 prompt 文件
6. 自动化测试已覆盖主链消费与 fallback 两类边界

### 6.1 Move Blockers / Move-to-Tested Conditions

出现以下任一情况，文档不得移到 `tested`：

- 只能证明 helper 正常，不能证明主链已消费 registry
- 开关关闭后链路无法恢复旧逻辑
- registry 注入造成 prompt 长度或运行稳定性明显退化
- 新维度接入仍需要改多处 prompt 文本

仅当以下条件同时满足时，才允许移到 `tested`：

- `Disproof Command` 已执行
- `Primary Evidence` 已满足
- 主链消费路径与 fallback 路径都已被验证

---

## 七、风险点

1. registry 内容与真实数据字段不一致，会系统性误导模型
2. 注入内容过长，会稀释 prompt 重点并增加超时风险
3. 若配置开关不清晰，会导致“以为启用、实际未生效”的假完成
4. 若主链消费点选错，可能只影响局部 prompt，而非真实挖掘决策路径

---

## 八、回退方案

- 保留旧逻辑作为 fallback
- 通过配置快速关闭 registry 注入
- 若某个维度描述不稳定，可只保留已验证维度
- 若主链运行质量退化，优先回退主链注入，而不是删除 registry 模块本身

---

## 九、为什么现在做

相对其他外插模块，`Data Capability Registry` 体量小、边界清晰、依赖少，适合作为持续研究体系的早期增强项。

它完成后，能为后续能力提供基础：

- 更稳定的数据维度提示
- 更明确的 future-leakage 约束提示
- 更容易扩展到基本面或其他低频数据
- 为外插式 registry 模块保留统一对接点
