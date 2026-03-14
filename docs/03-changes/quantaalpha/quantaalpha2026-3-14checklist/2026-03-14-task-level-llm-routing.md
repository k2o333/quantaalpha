# 任务级 LLM 路由

Status: draft
Owner: QuantaAlpha team
Created: 2026-03-14
Outcome: pending
Phase: 2
Related-to: /home/quan/testdata/aspipe_v4/docs/drafts/自主挖掘因子回测和因子管理/2026-03-14-quantaalpha-continuous-factor-implementation-checklist.md

---

## Background

当前 `chat_model_map` 基于"调用类名/tag"路由，存在：
- 路由粒度不够语义化
- 难以针对不同任务类型优化模型选择
- 配置与代码耦合较紧

---

## Goal

将现有路由机制提升为"按任务类型路由"：
- `hypothesis_generation` - 假设生成
- `factor_construction` - 因子构造
- `evaluation_screening` - 评估筛选
- `feedback_summarization` - 反馈总结

---

## Non-goals

- 不支持 fanout > 1（多模型并行）
- 不支持 provider pool
- 不支持 repair chain

---

## Acceptance Criteria

1. 能通过配置控制不同任务的模型选择
2. 不破坏现有 `reasoning_model` / `chat_model` 逻辑

---

## Test Plan

### 单元测试

1. 路由配置解析函数输出正确
2. 未配置任务路由时返回默认模型

### 集成测试

3. 不配置任务路由时，行为与现有逻辑一致
4. 配置任务路由后，不同任务使用不同模型
5. routing 配置错误时有明确报错

---

## Implementation Plan

### 主要修改点

- `quantaalpha/llm/config.py`
- `quantaalpha/llm/client.py`
- 各任务调用处

### 配置结构

```yaml
llm:
  routing:
    # 默认模型
    default: "deepseek-chat"
    
    # 任务级路由
    tasks:
      hypothesis_generation: "claude-3-opus"
      factor_construction: "deepseek-coder"
      evaluation_screening: "gpt-4"
      feedback_summarization: "deepseek-chat"
```

### 代码调用示例

```python
from quantaalpha.llm import get_model_for_task

model = get_model_for_task("hypothesis_generation")
response = model.generate(prompt)
```

---

## Risk Points

1. 新旧配置格式需要兼容过渡
2. 任务类型命名需要与代码保持一致
3. 模型切换可能影响生成结果一致性

---

## Rollback Plan

- 保留现有 `chat_model_map` 机制作为 fallback
- 未配置 `routing.tasks` 时使用 `default` 或旧逻辑
- 配置验证在启动时执行，错误时快速失败

---

## Final Result

> 待实施后填写

---

## Validation Evidence

> 待实施后填写

---

## Lessons Learned

> 待实施后填写
