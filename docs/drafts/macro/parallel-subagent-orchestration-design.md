# 并行 Subagent 编排文档系统设计

**Status:** draft  
**Created:** 2026-03-18  
**Purpose:** 支持需求拆分后多 subagent 并行开发、测试、调试的文档系统

---

## 1. 核心变化

### 1.1 从串行到并行

**原模式（串行）:**
```
Python-Pro → Code-Reviewer → Test-Automator → Debugger → Main-Agent
```

**新模式（并行）:**
```
需求文档
    ├── Subagent A (并行开发)
    ├── Subagent B (并行开发)
    ├── Subagent C (并行开发)
    └── Subagent D (并行开发)
         ↓
    合并检查点
         ↓
    ├── Test Subagent A (并行测试)
    ├── Test Subagent B (并行测试)
    ├── Test Subagent C (并行测试)
    └── Test Subagent D (并行测试)
         ↓
    测试合并检查点
         ↓
    ├── Debug Subagent A (并行调试)
    ├── Debug Subagent B (并行调试)
    ├── Debug Subagent C (并行调试)
    └── Debug Subagent D (并行调试)
         ↓
    最终验收
         ↓
    Main Agent 收尾
```

### 1.2 关键设计原则

| 原则 | 说明 |
|------|------|
| **需求可拆分** | 需求文档必须明确定义 4 个独立工作包 |
| **工作包隔离** | 每个 subagent 只读自己的子任务，不读其他 |
| **检查点强制** | 每个阶段结束后必须人工/脚本确认才能进入下一阶段 |
| **冲突可检测** | 并行修改的文件必须有冲突检测机制 |

---

## 2. 文档系统改造

### 2.1 新增文档类型：Subtask Doc

在 `docs/03-changes/<module>/subtasks/` 目录下存放子任务文档。

**目录结构:**
```
docs/03-changes/quantaalpha/subtasks/
├── 2026-03-18-revalidate-iterate2/
│   ├── README.md              # 父任务总览
│   ├── subtask-A-develop.md   # 子任务 A：开发
│   ├── subtask-B-develop.md   # 子任务 B：开发
│   ├── subtask-C-develop.md   # 子任务 C：开发
│   ├── subtask-D-develop.md   # 子任务 D：开发
│   ├── subtask-A-test.md      # 子任务 A：测试
│   ├── subtask-B-test.md      # 子任务 B：测试
│   ├── subtask-C-test.md      # 子任务 C：测试
│   ├── subtask-D-test.md      # 子任务 D：测试
│   ├── subtask-A-debug.md     # 子任务 A：调试
│   ├── subtask-B-debug.md     # 子任务 B：调试
│   ├── subtask-C-debug.md     # 子任务 C：调试
│   ├── subtask-D-debug.md     # 子任务 D：调试
│   └── reports/               # 各阶段报告目录
│       ├── develop/
│       │   ├── subagent-A-report.md
│       │   ├── subagent-B-report.md
│       │   ├── subagent-C-report.md
│       │   └── subagent-D-report.md
│       ├── test/
│       └── debug/
```

### 2.2 父任务文档格式 (README.md)

```markdown
---
status: "in_progress"
stage: "develop"  # develop | develop-checkpoint | test | test-checkpoint | debug | debug-checkpoint | final
type: "parallel-parent"
module: "quantaalpha"
created_at: "2026-03-18"
parallel_count: 4
---

# 父任务：revalidate 语义澄清与真实复验链路

## 任务总览

本任务拆分为 4 个独立子任务并行执行。

## 子任务清单

| 子任务 | 类型 | 目标文件 | 依赖 |
|--------|------|----------|------|
| A | develop | cli.py --dry-run 模式 | 无 |
| B | develop | cli.py --status-refresh 模式 | 无 |
| C | develop | cli.py --real-backtest 模式 | 无 |
| D | develop | factors/library.py 扩展 | 无 |

## 阶段状态

| 阶段 | 状态 | 完成时间 |
|------|------|----------|
| Develop | 🔄 in_progress | - |
| Develop Checkpoint | ⏸️ pending | - |
| Test | ⏸️ pending | - |
| Test Checkpoint | ⏸️ pending | - |
| Debug | ⏸️ pending | - |
| Final | ⏸️ pending | - |

## 冲突检测

| 文件 | 被修改的子任务 | 冲突风险 |
|------|----------------|----------|
| cli.py | A, B, C | ⚠️ 高 |
| factors/library.py | D | ✅ 低 |

## 检查点通过标准

### Develop Checkpoint
- [ ] 所有 4 个 develop subagent 完成
- [ ] 检查 cli.py 三段修改是否冲突
- [ ] 如有冲突，人工解决或分配给 debug 阶段

### Test Checkpoint
- [ ] 所有 4 个 test subagent 完成
- [ ] 所有子任务测试通过
- [ ] 集成测试通过

### Debug Checkpoint
- [ ] 所有 4 个 debug subagent 完成
- [ ] 无遗留 blocker

---

## Agent 指令

如果你是 **Develop Subagent**，读取你的 `subtask-X-develop.md`，忽略其他子任务。

如果你是 **Test Subagent**，读取你的 `subtask-X-test.md`，同时检查父任务中定义的集成测试要求。

如果你是 **Debug Subagent**，读取你的 `subtask-X-debug.md` 和对应 develop/test 报告。

如果你是 **Main Agent**，读取父任务和所有子任务报告，做最终收尾。
```

### 2.3 子任务文档格式 (subtask-X-{stage}.md)

```markdown
---
status: "planned"
type: "subtask"
stage: "develop"  # develop | test | debug
parent_task: "2026-03-18-revalidate-iterate2"
subtask_id: "A"
assigned_agent: "subagent-A-develop"
target_files:
  - "third_party/quantaalpha/quantaalpha/cli.py"
created_at: "2026-03-18"
---

# 子任务 A：实现 --dry-run 模式

## 父任务上下文

本子是任务 `2026-03-18-revalidate-iterate2` 的子任务 A。

**不要读其他子任务的文档**，你的范围仅限本文件定义的内容。

## 你的任务

### 目标

实现 `revalidate --dry-run` 模式：
- 只输出候选列表
- 不写库
- 返回结构化 JSON

### 代码落点

`third_party/quantaalpha/quantaalpha/cli.py`

### 接口契约

```python
# 输入
revalidate(library_path, dry_run=True)

# 输出
{
  "mode": "dry_run",
  "total_candidates": 368,
  "candidates": [...]
}
```

### 不要做的

- 不要实现 --status-refresh 或 --real-backtest（其他子任务负责）
- 不要修改 factors/library.py（子任务 D 负责）
- 不要写集成测试（test 阶段负责）

## 完成标准

- [ ] 代码实现
- [ ] 单元测试（至少3个）
- [ ] 本地验证通过
- [ ] 写入阶段报告到 `reports/develop/subagent-A-report.md`

## 阶段报告要求

报告必须包含：
1. 实际读取的文件
2. 实际修改的文件
3. 实际执行的命令及结果
4. 发现的问题
5. 与其他子任务的潜在冲突
```

---

## 3. 自动化脚本改造

### 3.1 并行执行脚本

```bash
#!/bin/bash
# run_parallel_subagents.sh

PARENT_TASK="$1"  # e.g., 2026-03-18-revalidate-iterate2
STAGE="$2"        # develop | test | debug

SUBTASK_DIR="docs/03-changes/quantaalpha/subtasks/${PARENT_TASK}"
REPORTS_DIR="${SUBTASK_DIR}/reports/${STAGE}"
mkdir -p "${REPORTS_DIR}"

# 读取父任务，获取并行数量
PARALLEL_COUNT=$(grep "parallel_count:" "${SUBTASK_DIR}/README.md" | awk '{print $2}')

# 并行启动 subagents
for i in $(seq 1 ${PARALLEL_COUNT}); do
  SUBTASK_ID=$(printf '%s' "$i" | tr '1234' 'ABCD')
  SUBTASK_DOC="${SUBTASK_DIR}/subtask-${SUBTASK_ID}-${STAGE}.md"
  REPORT_FILE="${REPORTS_DIR}/subagent-${SUBTASK_ID}-report.md"
  
  echo "启动 subagent ${SUBTASK_ID} for ${STAGE}..."
  
  # 后台启动 iflow
  iflow -p "读取 ${SUBTASK_DOC} 并按指令执行，报告写入 ${REPORT_FILE}" -y \
    > "${REPORTS_DIR}/subagent-${SUBTASK_ID}-log.txt" 2>&1 &
  
  # 记录 PID
  echo $! > "${REPORTS_DIR}/subagent-${SUBTASK_ID}.pid"
done

echo "所有 ${STAGE} subagents 已启动，PID 文件在 ${REPORTS_DIR}/"
echo "等待完成..."
wait

echo "所有 ${STAGE} subagents 完成"

# 生成汇总报告
./scripts/aggregate_subagent_reports.sh "${PARENT_TASK}" "${STAGE}"
```

### 3.2 检查点脚本

```bash
#!/bin/bash
# checkpoint.sh

PARENT_TASK="$1"
STAGE="$2"  # develop | test | debug

SUBTASK_DIR="docs/03-changes/quantaalpha/subtasks/${PARENT_TASK}"
REPORTS_DIR="${SUBTASK_DIR}/reports/${STAGE}"

echo "=== ${STAGE} Checkpoint ==="
echo ""

# 1. 检查所有报告是否存在
echo "1. 检查报告完整性..."
ALL_REPORTS_EXIST=true
for i in A B C D; do
  REPORT="${REPORTS_DIR}/subagent-${i}-report.md"
  if [[ -f "$REPORT" ]]; then
    echo "  ✓ Subagent ${i} 报告存在"
  else
    echo "  ✗ Subagent ${i} 报告缺失"
    ALL_REPORTS_EXIST=false
  fi
done

if [[ "$ALL_REPORTS_EXIST" == "false" ]]; then
  echo "错误：并非所有 subagent 都完成了报告"
  exit 1
fi

# 2. 检查冲突
echo ""
echo "2. 检查文件冲突..."
# 提取每个 subagent 修改的文件
# 检测重叠

# 3. 汇总结果
echo ""
echo "3. 结果汇总："
for i in A B C D; do
  REPORT="${REPORTS_DIR}/subagent-${i}-report.md"
  # 提取关键信息
  echo "  Subagent ${i}: $(grep '状态:' "$REPORT" | head -1)"
done

echo ""
echo "检查点完成。请人工审核后决定是否进入下一阶段。"
echo "如果通过，运行：./scripts/promote_stage.sh ${PARENT_TASK} ${STAGE}"
```

---

## 4. 冲突处理策略

### 4.1 自动检测

每个 develop subagent 报告必须包含：
```markdown
## 修改的文件
- cli.py (第 45-67 行)

## 潜在冲突
- cli.py 也被 subtask B 和 C 修改
- 建议：三段代码按顺序合并，或分配给 debug 阶段处理
```

### 4.2 冲突解决选项

| 场景 | 处理方式 |
|------|----------|
| 修改不重叠 | 自动合并 |
| 修改重叠但逻辑独立 | 分配给 Debug Subagent 专门合并 |
| 修改重叠且逻辑冲突 | 人工介入，重新设计子任务边界 |

---

## 5. 迁移路径

### 从现有系统迁移

1. **保留现有文档**：`docs/03-changes/<module>/planned/` 继续存在
2. **新增子任务目录**：当任务需要并行时，在 `subtasks/` 下创建
3. **渐进采用**：不是所有任务都需要并行，简单任务保持串行

### 决策树

```
新任务
  ├── 简单、单文件修改？
  │     └── 使用现有串行流程
  │
  └── 复杂、可多文件并行？
        └── 使用并行 subagent 流程
              └── 拆分为 2-4 个子任务
```

---

## 6. 风险提示

| 风险 | 缓解措施 |
|------|----------|
| 子任务边界划分不清 | 父任务文档必须明确定义每个子任务的输入输出 |
| 并行 subagent 超时 | 每个 subagent 设置独立超时，超时后标记为失败 |
| 冲突检测遗漏 | 强制要求每个 subagent 报告修改的文件范围 |
| 测试覆盖不足 | test 阶段必须有集成测试 subagent 验证整体 |

---

## 7. 下一步行动

1. 选择一个小任务试用并行流程
2. 创建第一个父任务和子任务文档
3. 测试并行脚本
4. 根据结果调整模板
