---
stage: test
task_key: parallel-03-debug-failure-filter
recommended_agent: kilocode
previous_stage: dev
next_stage: debug
source_doc: docs/03-changes/quantaalpha/planned/parrelell/2026-03-18-parallel-03-debug-failure-filter.md
handoff_docs:
  - ../dev/parallel-03-debug-failure-filter.task.md
---

# Test Task: Debug Failure Filter

先阅读：

- 同名 `dev` 阶段 task 文档
- `/home/quan/testdata/aspipe_v4/docs/03-changes/quantaalpha/planned/parr2/dev/batch.status.json`
- `/home/quan/testdata/aspipe_v4/auto/tasks/task-*-parallel-03-debug-failure-filter/runs/run-*/summary.md`
- `/home/quan/testdata/aspipe_v4/auto/tasks/task-*-parallel-03-debug-failure-filter/runs/run-*/*.result.md`
- `/home/quan/testdata/aspipe_v4/auto/tasks/task-*-parallel-03-debug-failure-filter/runs/run-*/status.json`

读取规则：

- 以上 `auto/tasks` 路径只读取最新一次 `dev` 阶段对应任务目录中的最新 `run-*`
- 不要去 `docs/.../dev/` 目录下查找 `summary.md` 或 `status.json`，那些运行产物不在该目录

目标：

- 验证第二轮是否真的只处理失败因子
- 验证成功因子不会重复进入高成本步骤
- 验证提前结束和最大轮次保护

本阶段可以执行相关测试，也可以补测试文件；不要修改生产代码。

阶段边界：

- 当前是 `test` 阶段，目标是验证 `dev` 结果，不是继续做功能开发
- 必须先阅读 `dev` 文档和 `dev` 产出，再决定测试范围
- 如果发现问题，优先形成可交接给 `debug` 的问题清单

禁止操作：

- 禁止修改生产代码
- 禁止安装任何包
- 禁止修改允许范围之外的文件
- 禁止把未验证的问题写成已确认缺陷

最终输出只保留：

- Findings
- Tests Run
- Files Checked
- Suggested Debug Scope
