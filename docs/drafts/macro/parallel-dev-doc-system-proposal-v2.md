# 并行 Subagent 开发模式：文档系统改造方案 V2

**Status:** draft  
**Created:** 2026-03-18  
**Purpose:** 统一前三版方案，给出文档系统的最小可行改造，支持"需求拆分 → 4 并行开发 → 4 并行测试 → 4 并行 Debug → 1 主 Agent 收尾"流程  

> [!NOTE]
> 本文是对 `parallel-subagent-development-proposal-2026-03-18.md`、`parallel-agent-doc-system.md` 和 `parallel-subagent-orchestration-design.md` 三份草案的合并与精简。

---

## 一、目标流程回顾

```
需求文档(planned/*.md)
    │
    ▼
Phase 0 ─ 拆分 Agent（1个）
    │  产出：4 份 slice doc + slices_index.md
    ▼
Phase 1 ─ 开发（4 subagent 并行）
    │  约束：只改自己 slice 的代码
    ▼
Phase 2 ─ 测试（4 subagent 并行）
    │  约束：只写/运行自己 slice 的测试
    ▼
Phase 3 ─ Debug（4 subagent 并行）
    │  约束：只修自己 slice 的代码，跨 slice 问题上报
    ▼
Phase 4 ─ 收尾 Agent（1个）
       集成测试 → 契约验证 → 文档更新 → 交付
```

---

## 二、文档系统需要哪些改动

### 2.1 改动全景

| 层 | 现状 | 改动 |
|---|---|---|
| `00-governance/` | `rules.md` 无并行入口 | 新增并行模式路由条目 |
| `03-changes/<module>/` | 只有 `planned/`, `tested/` 等 | 新增 `slices/` 子目录 |
| `05-playbooks/` | 4 个 playbook | 新增 `parallel-subagent-playbook.md` |
| `automation/` | `runs/<run_id>/` 存报告 | 扩展 `stage_reports/` 结构 |
| `00-governance/doc-rules.md` 系列 | 无 slice 文档类型定义 | 追加 slice doc 类型 |

### 2.2 不改的部分

| 不动 | 原因 |
|---|---|
| `rules.md` 的整体结构 | 只追加条目，不重构 |
| `agent.md` 的路由逻辑 | 只追加 slice 路由 |
| `planned/*.md` 的格式 | 只追加 `split_info` 章节 |
| 串行流程 | 简单任务仍走串行，并行是可选路径 |

---

## 三、目录结构改动

### 3.1 `docs/03-changes/<module>/slices/`（新增）

```
docs/03-changes/quantaalpha/
├── planned/
│   └── 2026-03-15-iterate2-01-xxx.md     # 原始需求文档（不变）
├── slices/                                # ← 新增
│   └── <task-id>/                         # 按任务分目录
│       ├── slices_index.md                # 切片总览 + 依赖矩阵
│       ├── slice_1.md                     # 切片 1 定义
│       ├── slice_2.md
│       ├── slice_3.md
│       └── slice_4.md
└── tested/
```

### 3.2 `automation/runs/<run_id>/`（扩展）

```
automation/runs/<run_id>/
├── stage_reports/                         # ← 扩展
│   ├── dev_slice_1.md                     # 开发阶段×切片
│   ├── dev_slice_2.md
│   ├── dev_slice_3.md
│   ├── dev_slice_4.md
│   ├── test_slice_1.md                    # 测试阶段×切片
│   ├── test_slice_2.md
│   ├── test_slice_3.md
│   ├── test_slice_4.md
│   ├── debug_slice_1.md                   # Debug阶段×切片
│   ├── debug_slice_2.md
│   ├── debug_slice_3.md
│   ├── debug_slice_4.md
│   └── final_report.md                   # 收尾阶段
└── run_summary.txt
```

---

## 四、文档格式定义

### 4.1 `slices_index.md`（切片索引）

```yaml
---
parent_task: "2026-03-15-iterate2-01-revalidate"
status: "splitting"           # splitting | developing | testing | debugging | finalizing | done
parallel_count: 4
created_at: "2026-03-18"
---
```

```markdown
# 切片索引

## 源需求文档
`docs/03-changes/quantaalpha/planned/2026-03-15-iterate2-01-xxx.md`

## 切片清单

| 切片 | 名称 | 目标文件 | 写入目标 | 状态 |
|------|------|----------|----------|------|
| slice_1 | ... | `path/a.py` | `data/x.json` | pending |
| slice_2 | ... | `path/b.py` | `data/y.json` | pending |
| slice_3 | ... | `path/c.py` | `data/z.json` | pending |
| slice_4 | ... | `path/d.py` | — | pending |

## 独立性验证

- [ ] 4 个切片的 **代码落点** 无重叠
- [ ] 4 个切片的 **写入目标** 无重叠
- [ ] 每个切片可独立编译/运行（无相互 import）

## 切片间契约（如有）

| 生产方 | 消费方 | 产物 | 格式 |
|--------|--------|------|------|
| slice_1 | slice_2 | `output_a.json` | `{...}` |
```

### 4.2 `slice_N.md`（单个切片定义）

```yaml
---
slice_id: "slice_1"
parent_task: "2026-03-15-iterate2-01-revalidate"
status: "pending"                       # pending | developing | testing | debugging | done | blocked
code_targets:
  - "path/to/a.py"
  - "path/to/b.py"
write_targets:
  - "data/output_a.json"
read_only:
  - "config/shared.yaml"
test_targets:
  - "tests/test_slice_1.py"
---
```

```markdown
# Slice 1: [名称]

## 目标
[一句话]

## 代码落点
- `path/to/a.py` — [做什么]
- `path/to/b.py` — [做什么]

## 输入契约
- 从 `config/shared.yaml` 读取 ...
- 期望格式: ...

## 输出契约
- 生成 `data/output_a.json`
- 格式: ...

## 验收标准
1. [标准 1]
2. [标准 2]

## Disproof Command
```bash
python -m pytest tests/test_slice_1.py -v
```

## 禁止事项
- 不得修改 `path/to/c.py`（属于 slice_2）
- 不得写入 `data/output_b.json`（属于 slice_2）
```

### 4.3 阶段报告格式（`stage_reports/`）

每个切片在每个阶段产出一份报告。模板统一为：

```yaml
---
slice_id: "slice_1"
phase: "development"           # development | testing | debug
status: "done"                 # done | blocked
---
```

```markdown
# Slice 1 — [Phase] 报告

## 实际修改文件
- `path/to/a.py`: [摘要]

## 执行的命令
```bash
[命令]: [结果]
```

## 发现的问题
- [问题 1]: [处理方式]

## 跨切片问题（需上报）
- [无 / 列出]

## 不确定项
- [无 / 列出]
```

---

## 五、`rules.md` / `agent.md` 的最小追加

### 5.1 `rules.md` 追加

在 `## Required Behavior` 之后，追加：

```markdown
## Parallel Subagent Mode

当任务被拆分为并行切片时：

- 每个 subagent 只能修改自己切片文档中列出的 `code_targets`
- 每个 subagent 完成后必须写入阶段报告
- 发现跨切片问题必须上报，不得跨切片修改
- 收尾 Agent 必须验证所有切片的 Disproof Command 都通过

入口文档：`docs/03-changes/<module>/slices/<task-id>/slices_index.md`
流程文档：`docs/05-playbooks/parallel-subagent-playbook.md`
```

### 5.2 `agent.md` 追加

在文档导航表中追加一行：

```markdown
| 并行切片任务 | `docs/03-changes/<module>/slices/<task-id>/slices_index.md` |
```

---

## 六、`05-playbooks/parallel-subagent-playbook.md`（新增）

完整 playbook 应包含：

| 章节 | 内容 |
|------|------|
| 1. 前置条件 | 需求文档必须有 code_targets、依赖关系图、验收标准 |
| 2. Phase 0 拆分 | 拆分策略（按模块/按功能/按 pipeline 阶段）+ 验证清单 |
| 3. Phase 1-3 并行执行 | 给 subagent 的 prompt 模板（开发/测试/debug 各一份） |
| 4. Phase 4 收尾 | 集成测试 + 契约验证 + 文档迁移 |
| 5. 决策树 | 什么时候用并行、什么时候回退串行 |
| 6. 风险与缓解 | 拆分失败 / 文件冲突 / 报告缺失 |

> [!IMPORTANT]  
> playbook 的详细内容已在 `parallel-subagent-development-proposal-2026-03-18.md` 第六至九章中完整定义，本方案不重复。正式创建 playbook 时从该文件提取即可。

---

## 七、需求文档（`planned/*.md`）的追加

在需求文档中追加一个可选章节：

```markdown
## 拆分信息

### 拆分状态
- [ ] 已拆分
- [ ] 独立性验证通过

### 切片目录
`docs/03-changes/<module>/slices/<task-id>/`

### 切片间依赖
[依赖图或"无"]
```

此章节仅在任务走并行流程时填写，串行任务无需关心。

---

## 八、决策树：何时用并行

```
收到任务
  │
  ├── 涉及 ≤2 个文件？
  │     └── 串行流程（现有方式）
  │
  ├── 涉及 3+ 个文件，但强耦合？
  │     └── 串行流程（无法独立拆分）
  │
  └── 涉及 3+ 个文件，且可独立拆分？
        │
        ├── 能拆为 4 个无重叠切片？
        │     └── ✅ 使用并行流程
        │
        └── 能拆为 2-3 个切片？
              └── ✅ 使用并行流程（空闲 slot 留空）
```

---

## 九、与前三版方案的关系

| 前版文件 | 本版态度 | 保留/废弃 |
|----------|----------|-----------|
| `parallel-subagent-development-proposal-2026-03-18.md` (861行) | 最详细的参考，prompt 模板和阶段报告模板直接复用 | **保留为参考** |
| `parallel-agent-doc-system.md` (129行) | "shard" 概念与 "slice" 等价；`docs/tasks/` 路径被替换为 `03-changes/<module>/slices/` 以融入现有结构 | **废弃，内容已合并** |
| `parallel-subagent-orchestration-design.md` (400行) | "subtask" 概念等价；冲突检测和检查点逻辑已提取 | **废弃，内容已合并** |

---

## 十、改动清单与优先级

### P0：最小可用（创建 slices 目录 + playbook 骨架）

| # | 改动 | 文件 |
|---|------|------|
| 1 | 创建 `docs/03-changes/quantaalpha/slices/` 目录 | 新目录 |
| 2 | 新建 `docs/05-playbooks/parallel-subagent-playbook.md` | 新文件，从 proposal-2026-03-18 提取 |
| 3 | `rules.md` 追加 "Parallel Subagent Mode" 章节 | 追加 ~10 行 |
| 4 | `agent.md` 追加并行路由行 | 追加 1 行 |

### P1：首次试用（选一个任务跑完整流程）

| # | 改动 |
|---|------|
| 5 | 选一个 `planned/*.md` 作为试点，填写拆分信息 |
| 6 | 创建 4 份 slice doc + slices_index.md |
| 7 | 执行完整的 Phase 0-4 流程，收集反馈 |

### P2：固化（根据试用反馈）

| # | 改动 |
|---|------|
| 8 | 更新 `doc-standards.md` / `doc-rules.md` 追加 slice doc 类型定义 |
| 9 | 编写拆分验证脚本 `scripts/validate_slices.py` |
| 10 | 编写并行执行脚本 `automation/run_parallel_task.sh` |

---

## 十一、关键设计决定

### 为什么用 `slices/` 而不是 `tasks/` 或 `subtasks/`？

- `tasks/` 是一个全新的顶层目录，与现有 `03-changes/` 体系脱节
- `subtasks/` 语义偏通用，不能体现"独立切片"的含义
- `slices/` 放在 `03-changes/<module>/` 下，与 `planned/` / `tested/` 同级，融入现有生命周期

### 为什么不强制 4 个切片？

- 有些任务自然只能拆为 2-3 个独立部分
- 强制凑 4 个会导致人为耦合或空任务
- 允许 2-4 个切片，但 prompt 和报告模板保持统一

### 检查点是否需要人工介入？

- Phase 0（拆分后）：**必须**人工确认独立性
- Phase 1→2（开发→测试）：可选，建议自动
- Phase 2→3（测试→debug）：可选，建议自动
- Phase 4（收尾）：**必须**人工确认终态

---

## 十二、总结

本方案的核心改动：

1. **新增 `slices/` 目录**在 `03-changes/<module>/` 下，存放切片文档
2. **新增 playbook** 定义完整的并行流程
3. **`rules.md` 追加** 并行模式的约束条目
4. **需求文档追加** 可选的"拆分信息"章节

**不增加的负担**：
- 不创建新的顶层目录
- 不改变现有串行流程
- 不强制所有任务走并行
- 不要求额外的 agent 配置
