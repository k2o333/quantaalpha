# 任务级 LLM 路由

Status: draft
Owner: QuantaAlpha team
Created: 2026-03-14
Outcome: pending
Phase: 2
Related-to: /home/quan/testdata/aspipe_v4/docs/drafts/自主挖掘因子回测和因子管理/2026-03-14-quantaalpha-continuous-factor-implementation-checklist.md

---

## Background

当前 `quantaalpha/llm/client.py` 主要基于调用方函数名或类名构造 `tag`，再用 `chat_model_map` 决定模型。这种方式能工作，但任务语义不清晰，配置也难维护：

- 相同业务任务可能因调用位置不同而路由到不同模型
- 新增任务时，配置项不直观
- 代码调用者必须知道内部 `tag` 细节

---

## Goal

把现有“按调用点 tag 路由”提升为“按任务类型路由”，同时保持对旧配置兼容。

建议首版任务类型：

- `hypothesis_generation`
- `factor_construction`
- `evaluation_screening`
- `feedback_summarization`

---

## Non-goals

- 不做多模型 fanout。
- 不做 provider fallback。
- 不做自动质量评估后再切模型。

---

## Acceptance Criteria

1. 调用方可以显式声明任务类型，不再依赖隐式 `tag`。
2. 未配置任务路由时，行为与现有 `reasoning_model` / `chat_model` / `chat_model_map` 兼容。
3. 配置错误会在启动或首次解析时给出明确报错。

---

## Design Decision

### 配置结构

```yaml
llm:
  routing:
    default: "deepseek-chat"
    tasks:
      hypothesis_generation: "claude-3-opus"
      factor_construction: "deepseek-coder"
      evaluation_screening: "gpt-4"
      feedback_summarization: "deepseek-chat"
```

### 调用约定

```python
model = get_model_for_task("hypothesis_generation")
response = client.build_messages_and_create_chat_completion(
    user_prompt=prompt,
    task_type="hypothesis_generation",
)
```

### 兼容策略

优先级建议如下：

1. 显式 `task_type`
2. `routing.tasks`
3. 旧 `chat_model_map`
4. `chat_model` 默认值

`reasoning_model` 保留给需要显式 reasoning 的调用，不强行并入任务路由。

---

## Affected Modules

- `third_party/quantaalpha/quantaalpha/llm/config.py`
- `third_party/quantaalpha/quantaalpha/llm/client.py`
- 各任务调用处

---

## Implementation Plan

1. 在配置模型中加入 `llm.routing` 字段，并定义解析与校验逻辑。
2. 在 `client.py` 中增加基于 `task_type` 的模型选择入口。
3. 逐步替换关键调用点，让业务代码显式传递任务类型。
4. 保留现有 `chat_model_map` 作为兼容 fallback。
5. 为未知任务类型输出明确报错或警告，避免静默退回错误模型。

---

## Test Plan

### 单元测试

1. 路由配置解析正确。
2. 未配置 `task_type` 时，仍可走旧 `chat_model_map`。
3. 未知任务类型在严格模式下报错，在兼容模式下退回默认模型。

### 集成测试

4. 配置任务路由后，不同任务使用不同模型。
5. 不配置任务路由时，现有工作流行为不回归。
6. `reasoning_model` 调用路径不被任务路由意外覆盖。

### 手工验收

7. 在 hypothesis 和 factor construction 两条链路分别打印最终选择模型，确认路由结果符合配置。

---

## Risk Points

1. 如果任务类型命名没有统一约束，最终仍会退化成另一种 `tag`。
2. 兼容旧配置时优先级不清晰，会造成排障困难。
3. 过快替换全部调用点会增加回归风险。

---

## Rollback Plan

- 保留 `chat_model_map` 逻辑不删。
- 新路由仅在显式配置后启用。
- 如果关键任务出现质量下降，可单独把该任务退回默认模型。

---

## Final Result

> 待实施后填写

---

## Validation Evidence

> 待实施后填写

---

## Lessons Learned

> 待实施后填写
