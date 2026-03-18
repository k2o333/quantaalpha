---
status: draft
owner: Codex
created: 2026-03-18
purpose: 在现有 agent-oriented doc system 基础上，为“1 个拆分 agent + 4 个开发 subagent + 4 个测试 subagent + 4 个 debug subagent + 1 个收尾 agent”确定可落地的文档方向
related_to:
  - docs/04-decisions/ADR-002-agent-oriented-documentation-system.md
  - docs/03-changes/common/accepted/2026-03-15-agent-oriented-doc-system-refactor.md
---

# 并行 Subagent 文档系统定向方案

## 一、结论

建议采用“**在现有 `docs/03-changes/<module>/<status>/` 体系上增加并行切片层**”的方向，而不是另起一套 `docs/tasks/` 或 `docs/03-changes/<module>/subtasks/` 平行系统。

这条方向以 `parallel-dev-doc-system-proposal-v2.md` 为主干，吸收另外三份方案中的三项强约束：

1. 必须先冻结跨切片契约，再允许并行开发。
2. 每个切片在开发、测试、debug 阶段都必须留下阶段报告。
3. 主 agent 只做拆分、检查点推进、集成收尾，不直接吞掉 subagent 的边界责任。

## 二、为什么选这个方向

### 2.1 它最符合当前 doc 系统现状

仓库已经明确采用 ADR-002 定下的主链：

`draft -> change doc -> module doc / ADR / playbook / reference doc`

且 `docs/03-changes/` 已经稳定按模块和生命周期组织：

`docs/03-changes/<module>/{draft,planned,in_progress,blocked,implemented,tested,accepted,archived}/`

如果再新建 `docs/tasks/` 根目录，会直接引入第二套任务系统，和现有 change doc 生命周期并行竞争，后面会出现三个问题：

- agent 不知道“任务入口”到底先看 `planned/` 还是 `tasks/`
- 文档提升链会断开，parallel task 很难自然回流到模块文档和 ADR
- 历史任务与并行任务会分裂成两套检索路径

### 2.2 它比 `subtasks/` 独立大目录更稳

`docs/03-changes/<module>/subtasks/` 虽然比 `docs/tasks/` 好，但仍然会把“并行执行元信息”做成一种新的主文档类型。  
当前仓库的核心稳定对象还是 change doc，本次需要补的是“**change doc 如何承载并行执行**”，不是再发明一个一级对象。

### 2.3 它保留了最小增量改造的优点

这个方向第一版只要求：

- `planned/` 需求文档增加并行拆分入口字段
- 在模块下新增 `parallel/` 辅助目录承载切片定义
- 在 `automation/runs/` 下承载每次执行的阶段报告
- `rules.md`、`agent.md`、`doc-standards.md`、`playbook` 增加并行路由和约束

也就是“主链不变，附加并行执行层”。

## 三、放弃的方向

### 3.1 不选 `docs/tasks/<task-id>/`

不选原因：

- 与 ADR-002 的模块化 change-doc 主链冲突
- 新老任务查询路径不一致
- module ownership 被削弱，不利于后续归档和提升

### 3.2 不选“每个阶段一套 subtask 文档”的大而全设计

不选原因：

- 文档数量膨胀太快
- 对当前仓库来说，阶段差异主要体现在执行状态和报告，不值得把 `develop/test/debug` 都扩成独立任务文档
- 容易把一个切片拆成 3 份几乎重复的文档，降低 agent 路由效率

## 四、推荐结构

### 4.1 需求主文档仍然放在 `planned/`

例如：

`docs/03-changes/quantaalpha/planned/2026-03-15-iterate2-01-revalidate-semantics-and-real-backtest.md`

这份文档仍然是任务的唯一正式入口，但当它要进入并行模式时，追加一个并行拆分区块：

- `Parallel Mode: true`
- `Parallel Task ID`
- `Split Preconditions`
- `Frozen Shared Contract`
- `Integration Owner`
- `Parallel Artifact Path`

第一版建议直接使用 YAML frontmatter，让拆分 agent 和后续脚本都能机读：

```yaml
---
parallel_mode: true
parallel_task_id: "iterate2-01"
parallel_artifact_path: "docs/03-changes/quantaalpha/parallel/iterate2-01/"
parallel_run_report_root: "automation/runs/<run-id>/parallel/iterate2-01/"
split_preconditions:
  - code_targets_separable
  - write_targets_separable
  - frozen_contract_available
frozen_contract:
  shared_interface: "revalidate(...) -> dict"
  shared_schema: "factor library update payload v1"
  shared_file_ownership: "library.json owned by integration path only"
  integration_command: "/root/miniforge3/envs/mining/bin/python -m pytest third_party/quantaalpha/tests -v"
integration_owner: "main-agent"
---
```

### 4.2 在模块下新增 `parallel/<task-id>/`

推荐结构：

```text
docs/03-changes/<module>/parallel/<task-id>/
├── slices_index.md
├── slice_1.md
├── slice_2.md
├── slice_3.md
├── slice_4.md
```

这里的 `parallel/` 是 change doc 的辅助执行层，不替代 `planned/implemented/tested/...` 生命周期目录。

### 4.3 阶段报告放到 `automation/runs/`

第一版建议把阶段报告视为运行时产物，而不是正式 change doc：

```text
automation/runs/<run-id>/parallel/<task-id>/
├── slices_index.snapshot.md
└── stage_reports/
    ├── dev_slice_1.md
    ├── dev_slice_2.md
    ├── dev_slice_3.md
    ├── dev_slice_4.md
    ├── test_slice_1.md
    ├── test_slice_2.md
    ├── test_slice_3.md
    ├── test_slice_4.md
    ├── debug_slice_1.md
    ├── debug_slice_2.md
    ├── debug_slice_3.md
    ├── debug_slice_4.md
    └── final_integration.md
```

这样分层更稳：

- `docs/03-changes/.../parallel/` 放任务定义
- `automation/runs/...` 放执行记录

第一版不要求把这里做成复杂自动化系统，但路径应该先定下来，避免后面把大量运行日志写进 `docs/`。

## 五、文档职责划分

### 5.1 `planned/<task>.md`

负责：

- 业务目标
- 模块归属
- 高风险 seam
- 是否适合并行
- 冻结共享契约
- 最终集成验收标准

不负责：

- 每个 subagent 的详细落点清单
- 每个阶段的执行报告

### 5.2 `slices_index.md`

负责：

- 4 个切片总览
- 代码落点去重检查
- 写入目标去重检查
- 切片状态推进
- 跨切片契约矩阵
- 哪些问题必须升级给主 agent

它是并行阶段的总控板，但不是新的 source of truth；真正的任务语义仍以 `planned/<task>.md` 为准。

### 5.3 `slice_N.md`

负责定义单个切片的：

- allowed write paths
- read-only inputs
- output contract
- test target
- disproof command
- forbidden targets

切片文档的目标是让 subagent 有可执行边界，而不是再重复背景故事。

第一版应强制保持极简，优先数据驱动而不是叙述驱动。  
推荐使用 YAML frontmatter + 很短的正文，避免把 `planned/*.md` 里的业务背景再讲一遍。

### 5.4 `stage_reports/*.md`

负责记录每个切片每个阶段的：

- 实际改动
- 执行命令
- 结果
- blocker
- 跨切片问题

阶段报告是审计材料，不是需求文档。  
第一版就应尽量结构化，避免主 agent 在收尾时处理 12 份小作文。

## 六、并行流程

### Phase 0: 拆分

输入：`planned/<task>.md`

输出：

- `parallel/<task-id>/slices_index.md`
- `parallel/<task-id>/slice_1.md` 到 `slice_4.md`

准入条件：

- 代码落点可分离
- 写路径可分离
- 共享接口可以提前冻结
- 至少能为每个切片定义一个独立 `Disproof Command`

如果做不到，就不应进入并行模式。

检查点：

| 检查点 | 是否需要人工确认 | 说明 |
|---|---|---|
| Phase 0 -> Phase 1 | 必须 | 必须确认独立性验证和冻结契约成立 |
| Phase 1 -> Phase 2 | 可选 | 第一版可自动推进 |
| Phase 2 -> Phase 3 | 可选 | 仅失败切片进入 debug |
| Phase 4 完成后 | 必须 | 最终验收和生命周期推进必须人工确认 |

### Phase 1: 开发

4 个开发 subagent 各自只读：

- 对应 `slice_N.md`
- 需求主文档中的冻结契约区块

4 个开发 subagent 各自只写：

- 自己切片允许的代码路径
- 自己的运行报告 `automation/runs/<run-id>/.../dev_slice_N.md`

### Phase 2: 测试

4 个测试 subagent 并行执行：

- 自己切片的边界测试
- 契约一致性检查
- 文件变更白名单检查
- 自己的运行报告 `automation/runs/<run-id>/.../test_slice_N.md`

### Phase 3: Debug

只允许修复本切片问题。  
如果问题需要改共享契约、改别人的落点、或涉及集成接口冲突，必须回报主 agent，而不是跨切片直接修。

### Phase 4: 收尾

主 agent 负责：

- 汇总阶段报告
- 解决真正的跨切片冲突
- 跑集成验收
- 把正式 change doc 从 `planned/` 推进到后续生命周期目录

主 agent 最低限度必须做 4 件事：

1. 契约一致性检查
2. 总改动范围检查
3. 集成级 `Disproof Command`
4. 审计所有 blocker 和跨切片问题是否已关闭

### 补充：切片状态推进规则

第一版不需要把状态机做得很复杂，但至少要有以下最小状态：

| 当前状态 | 可推进到 | 推进条件 |
|---|---|---|
| pending | dev_done | 开发完成且 dev 报告已写入 |
| dev_done | test_done | 测试通过且 test 报告已写入 |
| test_done | debug_needed | 存在失败或白名单越界 |
| debug_needed | ready_for_integration | debug 完成且复测通过 |
| test_done | ready_for_integration | 无需 debug |
| ready_for_integration | integrated | 主 agent 完成集成验收 |

不允许跳阶段推进。

## 七、必须新增的硬规则

### 7.1 契约冻结先于并行开发

任何并行任务在切片下发前，必须先把以下内容冻结在主需求文档中：

- shared interface
- shared schema
- shared file ownership
- integration command

subagent 不得私自改这些内容。

### 7.2 代码落点和写入目标都必须去重

只检查“代码文件是否不同”还不够。  
如果两个切片都写同一个结果文件、状态文件、库文件或 summary 文件，也应判定为无效拆分。

### 7.3 跨切片问题只能上报，不能顺手修

这是并行模式最关键的纪律之一。  
否则最后会回到“多个 agent 在隐式共享上下文里串行乱改”的旧模式。

第一版至少要定义一个粗粒度上报格式，统一写进阶段报告：

```text
Cross-Slice Issue
Issue ID: CSI-001
Type: contract_conflict | shared_resource_conflict | integration_conflict
Severity: blocker | warning
Related Slices: [slice_1, slice_3]
Needs Main Agent Decision: yes | no
Description: ...
```

### 7.4 完成标准以可推翻命令为准

每个切片至少一个 `Disproof Command`，总任务至少一个 `Integration Disproof Command`。  
没有这两个层次的可推翻验证，并行文档只是任务分配表，不足以支撑交付。

### 7.5 冻结契约的熔断机制

如果 subagent 发现冻结契约本身有问题：

1. 立即停止继续扩写实现范围
2. 在阶段报告中标记 `CONTRACT_ISSUE`
3. 由主 agent 判断是局部修订，还是暂停并行后重新拆分

第一版不需要把契约变更流程做成复杂审批流，但必须有“发现契约问题就熔断上报”的机制。

## 八、建议落地顺序

第一步，先补文档规范，不急着写自动化脚本：

1. 在 `docs/00-governance/doc-standards.md` 增加并行切片文档类型和命名规则。
2. 在 `docs/00-governance/rules.md` 增加 `Parallel Subagent Mode` 约束。
3. 在 `docs/00-governance/agent.md` 增加并行任务入口路由。
4. 新增 `docs/05-playbooks/parallel-subagent-playbook.md`。
5. 选一个 `quantaalpha/planned/` 任务做试点。

第二步，再决定是否补脚本化支持：

- 自动生成 `slice_1..4.md`
- 自动检查 `code_targets` / `write_targets` 冲突
- 自动检查白名单路径越界
- 自动汇总 `stage_reports`

第三步，再补更细的工程配套，而不是一开始就写满：

- 坏切片 vs 好切片示例
- prompt 模板
- 影子集成测试
- 更细的切片状态机

## 九、最终建议

如果目标是服务你当前这套 doc system，而不是重建一套新系统，最佳方向就是：

**保留 ADR-002 已经建立的模块化 change-doc 主链，把“并行 subagent”定义成 `planned` 任务的一种执行模式，并通过 `parallel/<task-id>/` 承载切片与阶段报告。**

这样做的收益最大：

- 不破坏现有入口和真值层级
- 能直接服务你说的“4 开发 + 4 测试 + 4 debug + 1 收尾”
- 后续可以渐进式加自动化，不需要一次性重构 `docs/`
