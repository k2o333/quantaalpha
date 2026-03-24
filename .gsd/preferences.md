---
version: 1
mode:
always_use_skills: []
prefer_skills:
  - systematic-debugging
  - test
  - lint
prefer_skills_for_task_type:
  code: [lint, test, systematic-debugging]
  research: [systematic-debugging]
  simple: []
avoid_skills: []
skill_rules: []
custom_instructions: []
models: {}
skill_discovery:
skill_staleness_days:
auto_supervisor: {}
git:
  auto_push: false
  push_branches: []
  remote: origin
  snapshots: true
  pre_merge_check: true
  commit_type: conventional
  main_branch: main
  merge_strategy: squash
  isolation: worktree
  manage_gitignore: true
  worktree_post_create: []
unique_milestone_ids: true
budget_ceiling:
budget_enforcement: warn
context_pause_threshold:
token_profile: medium
phases:
  skip_research: false
  skip_reassess: false
  reassess_after_slice: true
  skip_slice_research: false
dynamic_routing:
  enabled: false
  tier_models: {}
  escalate_on_failure: false
  budget_pressure:
  cross_provider:
  hooks:
auto_visualize: false
auto_report: false
parallel:
  enabled: true
  max_workers: 10
  budget_ceiling: 0
  merge_strategy: per-milestone
  auto_merge: false
verification_commands: []
verification_auto_fix: false
verification_max_retries: 3
notifications:
  enabled: true
  on_complete: true
  on_error: true
  on_budget: false
  on_milestone: true
  on_attention: true
cmux:
  enabled: false
  notifications: false
  sidebar: false
  splits: []
  browser: false
remote_questions:
  channel:
  channel_id:
  timeout_minutes: 5
  poll_interval_seconds: 30
uat_dispatch: auto
post_unit_hooks: []
pre_dispatch_hooks: []
retry:
  enabled: true
  maxRetries: 30
  baseDelayMs: 2000
  maxDelayMs: 600000
---

# GSD Preferences

## Subagent 并行执行偏好

### parallel 配置

```yaml
parallel:
  enabled: true      # 启用并行执行
  max_workers: 10     # 最多 10 个并行 subagent
```

### 使用场景

- **推荐并行**：独立的 research、文件分析、代码审查任务
- **串行执行**：有依赖关系的任务（如 T01→T02→T03）
- **子任务分发**：一个大任务可以分解为多个独立子任务时使用 subagent

### 配置说明

| 字段 | 值 | 说明 |
|------|-----|------|
| `parallel.enabled` | `true` | 启用并行 |
| `parallel.max_workers` | `3` | 最多 3 个 subagent 并行 |
| `parallel.merge_strategy` | `first` | 保留第一个结果 |

### 查看完整文档

参考 `~/.gsd/agent/extensions/gsd/docs/preferences-reference.md`
