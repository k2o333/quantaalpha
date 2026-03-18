# 并行 Subagent 开发模式方案

**Status:** draft
**Created:** 2026-03-18
**Purpose:** 支持 4 并行 subagent 的开发流程

---

## 一、目标流程

```
需求文档 → 拆分 → 4并行开发 → 4并行测试 → 4并行Debug → 主Agent收尾
```

### 阶段定义

| 阶段 | Agent 数量 | 职责 |
|------|-----------|------|
| Phase 0: 拆分 | 1 个 | 将需求文档拆分为 4 个独立任务切片 |
| Phase 1: 开发 | 4 并行 subagent | 各自独立实现，互不依赖 |
| Phase 2: 测试 | 4 并行 subagent | 各自负责自己切片的测试 |
| Phase 3: Debug | 4 并行 subagent | 各自修复自己切片的问题 |
| Phase 4: 收尾 | 1 个主 agent | 合并、集成测试、文档更新、交付验收 |

---

## 二、核心设计原则

### 2.1 独立性原则

4 个 subagent 必须满足：

| 维度 | 要求 |
|------|------|
| **代码落点** | 互不重叠，各自负责独立文件或模块 |
| **依赖关系** | 无相互调用，可独立编译/运行 |
| **测试范围** | 各自独立的测试文件，无交叉 |
| **写入路径** | 各自独立的写入目标 |

违反独立性原则的拆分是无效拆分。

### 2.2 边界契约原则

每个切片必须明确定义：

```yaml
slice_id: "slice_1"
code_targets:
  - "path/to/file_a.py"
  - "path/to/file_b.py"
write_targets:
  - "data/output_a.json"
read_targets:
  - "config/shared_config.yaml"  # 可共享只读资源
test_targets:
  - "tests/test_slice_1.py"
contract:
  input: "从 shared_config 读取配置"
  output: "生成 output_a.json，供 slice_2 消费"
  failure_surface: "若 output_a.json 格式错误，slice_2 会失败"
```

### 2.3 可验证原则

每个切片必须有独立的 Disproof Command：

```bash
# 切片 1 的验收命令
python -m pytest tests/test_slice_1.py -v

# 切片 2 的验收命令
python -m pytest tests/test_slice_2.py -v
```

主 agent 收尾时，必须验证所有 4 个切片的 Disproof Command 都通过。

---

## 三、需求文档拆分规范

### 3.1 拆分前置条件

需求文档必须包含：

| 字段 | 说明 |
|------|------|
| **代码落点清单** | 明确列出所有需要修改的文件 |
| **依赖关系图** | 明确哪些文件之间有依赖 |
| **写入目标清单** | 明确所有写入路径 |
| **验收标准** | 每个功能点的验收条件 |

如果需求文档不满足上述条件，不得开始拆分。

### 3.2 拆分策略

#### 策略 A: 按文件/模块拆分（推荐）

适用场景：不同文件之间依赖较少

```
需求: 修改 A.py, B.py, C.py, D.py

拆分:
- Slice 1: A.py + test_a.py
- Slice 2: B.py + test_b.py
- Slice 3: C.py + test_c.py
- Slice 4: D.py + test_d.py
```

#### 策略 B: 按功能边界拆分

适用场景：单文件较大，可按功能拆分

```
需求: 修改 cli.py，新增 4 个子命令

拆分:
- Slice 1: revalidate 子命令 + test_revalidate.py
- Slice 2: debug 子命令 + test_debug.py
- Slice 3: validate 子命令 + test_validate.py
- Slice 4: export 子命令 + test_export.py
```

#### 策略 C: 按数据流阶段拆分

适用场景：pipeline 类任务

```
需求: 数据下载 → 清洗 → 转换 → 存储

拆分:
- Slice 1: 数据下载模块
- Slice 2: 数据清洗模块
- Slice 3: 数据转换模块
- Slice 4: 数据存储模块
```

### 3.3 拆分产物

每个拆分产物必须包含：

```yaml
---
slice_id: "slice_1"
phase: "development"
status: "pending"
depends_on: []  # 本阶段内的依赖，应始终为空
produces: ["output_a.json"]
consumes: ["config/shared.yaml"]
---

# Slice 1: [切片名称]

## 目标
[一句话描述]

## 代码落点
- `path/to/file_a.py`
- `path/to/file_b.py`

## 写入目标
- `data/output_a.json`

## 输入契约
- 从 `config/shared.yaml` 读取配置
- 期望格式: ...

## 输出契约
- 生成 `data/output_a.json`
- 格式要求: ...

## 验收标准
1. [标准 1]
2. [标准 2]

## Disproof Command
```bash
python -m pytest tests/test_slice_1.py -v
```

## 禁止事项
- 不得修改 `path/to/file_c.py`（属于 Slice 2）
- 不得写入 `data/output_b.json`（属于 Slice 2）
```

---

## 四、阶段执行规范

### 4.1 Phase 0: 拆分阶段

**输入**：需求文档

**执行者**：1 个拆分 agent

**输出**：
- 4 个切片文档（`slice_1.md`, `slice_2.md`, `slice_3.md`, `slice_4.md`）
- 1 个切片索引文档（`slices_index.md`）

**验证**：
- 4 个切片的代码落点无重叠
- 4 个切片可独立运行（无相互调用）
- 每个切片有独立的 Disproof Command

### 4.2 Phase 1: 开发阶段

**输入**：4 个切片文档

**执行者**：4 个并行开发 subagent

**输出**：每个切片的代码实现

**执行方式**：
```
主 Agent 启动 4 个并行 Task:
- Task(slice_id="slice_1", phase="development", subagent_type="python-pro")
- Task(slice_id="slice_2", phase="development", subagent_type="python-pro")
- Task(slice_id="slice_3", phase="development", subagent_type="python-pro")
- Task(slice_id="slice_4", phase="development", subagent_type="python-pro")
```

**约束**：
- 每个 subagent 只能读取和修改自己切片的文件
- 每个 subagent 必须在完成后写入阶段报告
- 禁止跨切片修改

**阶段报告模板**：
```markdown
# Slice 1 开发阶段报告

## 实际修改的文件
- `path/to/file_a.py`: [修改内容摘要]
- `path/to/file_b.py`: [修改内容摘要]

## 未修改但检查过的文件
- `path/to/file_c.py`: 确认属于其他切片，未触碰

## 实际执行的命令
- [命令 1]: [结果]
- [命令 2]: [结果]

## 发现的问题
- [问题 1]: [处理方式]
- [问题 2]: [待测试阶段验证]

## 不确定项
- [不确定项 1]

## 报告路径
`__IFLOW_STAGE_REPORT_DIR__/dev_slice_1.md`
```

### 4.3 Phase 2: 测试阶段

**输入**：4 个切片的代码实现

**执行者**：4 个并行测试 subagent

**输出**：每个切片的测试代码和测试报告

**执行方式**：
```
主 Agent 启动 4 个并行 Task:
- Task(slice_id="slice_1", phase="testing", subagent_type="test-automator")
- Task(slice_id="slice_2", phase="testing", subagent_type="test-automator")
- Task(slice_id="slice_3", phase="testing", subagent_type="test-automator")
- Task(slice_id="slice_4", phase="testing", subagent_type="test-automator")
```

**约束**：
- 每个 subagent 只能创建和修改自己切片的测试文件
- 必须执行真实的 Disproof Command
- 必须区分 primary evidence 和 secondary evidence

**阶段报告模板**：
```markdown
# Slice 1 测试阶段报告

## 测试文件
- `tests/test_slice_1.py`: [测试数量]

## 执行的测试命令
```bash
python -m pytest tests/test_slice_1.py -v
```

## 测试结果
- 通过: X
- 失败: Y
- 跳过: Z

## Primary Evidence
- [证据 1]: 真实 CLI 入口验证
- [证据 2]: 真实模块边界验证

## Secondary Evidence
- [证据 3]: Mock-based 单元测试

## 发现的问题
- [问题 1]: 需要 Debug 阶段修复

## 报告路径
`__IFLOW_STAGE_REPORT_DIR__/test_slice_1.md`
```

### 4.4 Phase 3: Debug 阶段

**输入**：4 个切片的测试报告和失败用例

**执行者**：4 个并行 debug subagent

**输出**：修复后的代码和重新通过的测试

**执行方式**：
```
主 Agent 启动 4 个并行 Task:
- Task(slice_id="slice_1", phase="debug", subagent_type="debugger")
- Task(slice_id="slice_2", phase="debug", subagent_type="debugger")
- Task(slice_id="slice_3", phase="debug", subagent_type="debugger")
- Task(slice_id="slice_4", phase="debug", subagent_type="debugger")
```

**约束**：
- 每个 subagent 只能修改自己切片的代码
- 修复后必须重新执行 Disproof Command
- 如果发现跨切片问题，必须上报而非自行跨切片修改

**阶段报告模板**：
```markdown
# Slice 1 Debug 阶段报告

## 接收的问题
- [问题 1]: [问题描述]

## 修复内容
- `path/to/file_a.py:123`: [修复内容]
- `tests/test_slice_1.py:45`: [修复内容]

## 重新执行的测试
```bash
python -m pytest tests/test_slice_1.py -v
```

## 修复结果
- [问题 1]: 已修复

## 残余问题
- [问题 2]: 需要跨切片协调，上报主 Agent

## 报告路径
`__IFLOW_STAGE_REPORT_DIR__/debug_slice_1.md`
```

### 4.5 Phase 4: 收尾阶段

**输入**：
- 4 个切片的代码实现
- 4 个切片的测试报告
- 4 个切片的 debug 报告

**执行者**：1 个主 agent

**输出**：
- 集成测试
- 文档更新
- 最终验收报告

**职责**：

| 任务 | 说明 |
|------|------|
| 合并检查 | 确认 4 个切片的代码无冲突 |
| 集成测试 | 执行跨切片的集成测试 |
| 契约验证 | 验证切片间的输入输出契约 |
| 文档更新 | 更新模块文档、变更文档 |
| 状态迁移 | 决定是否从 `planned` 迁移到 `tested` |

**阶段报告模板**：
```markdown
# 主 Agent 收尾报告

## 1. 切片完成状态

| 切片 | 开发 | 测试 | Debug | 状态 |
|------|------|------|-------|------|
| slice_1 | ✅ | ✅ | ✅ | 完成 |
| slice_2 | ✅ | ✅ | ✅ | 完成 |
| slice_3 | ✅ | ✅ | ⚠️ | 有残余问题 |
| slice_4 | ✅ | ✅ | ✅ | 完成 |

## 2. 集成测试

```bash
# 执行所有切片的测试
python -m pytest tests/ -v
# 结果: X passed, Y failed
```

## 3. 契约验证

- [ ] Slice 1 → Slice 2 契约: `output_a.json` 格式正确
- [ ] Slice 2 → Slice 3 契约: `output_b.json` 格式正确
- [ ] ...

## 4. 文档更新

- [ ] `docs/02-modules/xxx.md`: 已更新
- [ ] `docs/03-changes/xxx/planned/xxx.md`: 已更新

## 5. 验收结论

### Primary Evidence
- [证据清单]

### Secondary Evidence
- [证据清单]

### 迁移建议
- [ ] 建议迁移到 tested
- [ ] 建议停留在 planned（原因: ...）

## 6. 残余风险
- [风险 1]
- [风险 2]
```

---

## 五、文档系统改动

### 5.1 新增文档类型

| 类型 | 路径 | 用途 |
|------|------|------|
| 切片文档 | `docs/03-changes/<module>/slices/slice_N.md` | 单个切片的任务定义 |
| 切片索引 | `docs/03-changes/<module>/slices/slices_index.md` | 所有切片的概览和依赖关系 |
| 阶段报告 | `automation/runs/<run_id>/stage_reports/` | 每个切片每个阶段的报告 |

### 5.2 目录结构

```
docs/03-changes/
├── quantaalpha/
│   ├── planned/
│   │   └── 2026-03-15-iterate2-01-revalidate-semantics-and-real-backtest.md
│   ├── slices/                           # [新增]
│   │   ├── slices_index.md               # 切片索引
│   │   ├── slice_1_cli_revalidate.md     # 切片 1
│   │   ├── slice_2_cli_debug.md          # 切片 2
│   │   ├── slice_3_cli_validate.md       # 切片 3
│   │   └── slice_4_cli_export.md         # 切片 4
│   └── tested/
│
automation/
└── runs/
    └── 20260318_xxx/
        ├── slices_index.md               # 切片索引副本
        ├── stage_reports/
        │   ├── dev_slice_1.md            # 开发阶段报告
        │   ├── dev_slice_2.md
        │   ├── dev_slice_3.md
        │   ├── dev_slice_4.md
        │   ├── test_slice_1.md           # 测试阶段报告
        │   ├── test_slice_2.md
        │   ├── test_slice_3.md
        │   ├── test_slice_4.md
        │   ├── debug_slice_1.md          # Debug 阶段报告
        │   ├── debug_slice_2.md
        │   ├── debug_slice_3.md
        │   ├── debug_slice_4.md
        │   └── main_agent_final.md       # 主 Agent 收尾报告
        └── run_summary.txt               # 运行摘要
```

### 5.3 需求文档新增字段

需求文档（`planned/*.md`）必须新增：

```yaml
---
status: "planned"
split_ready: true  # [新增] 标记是否已准备好拆分
slices_dir: "slices/"  # [新增] 切片文档目录
---
```

并在正文新增章节：

```markdown
## 拆分信息

### 拆分状态
- [ ] 已拆分
- [ ] 拆分验证通过

### 切片清单
- Slice 1: [切片名称] → `slices/slice_1_xxx.md`
- Slice 2: [切片名称] → `slices/slice_2_xxx.md`
- Slice 3: [切片名称] → `slices/slice_3_xxx.md`
- Slice 4: [切片名称] → `slices/slice_4_xxx.md`

### 切片间依赖
```
slice_1 → slice_2 (output_a.json)
slice_2 → slice_3 (output_b.json)
...
```
```

---

## 六、Prompt 模板

### 6.1 拆分阶段 Prompt

```
你是一个需求拆分专家。

输入：
- 需求文档: __TASK_DOC__

任务：
1. 分析需求文档中的代码落点和依赖关系
2. 将需求拆分为 4 个独立的切片
3. 确保每个切片的代码落点无重叠
4. 确保每个切片可独立运行

输出：
- 在 `__SLICES_DIR__/` 目录下创建：
  - `slices_index.md`: 切片索引
  - `slice_1.md`, `slice_2.md`, `slice_3.md`, `slice_4.md`: 切片文档

验证：
- 执行 `__VALIDATION_SCRIPT__` 验证拆分正确性

禁止：
- 不得创建代码落点重叠的切片
- 不得创建相互调用的切片
```

### 6.2 开发阶段 Prompt（单切片）

```
你是 Slice __SLICE_ID__ 的开发专家。

输入：
- 切片文档: __SLICE_DOC__
- 代码落点: __CODE_TARGETS__

任务：
1. 阅读切片文档，理解目标
2. 只修改切片文档中列出的代码落点
3. 实现切片文档中定义的功能

输出：
- 修改后的代码文件
- 阶段报告: `__STAGE_REPORT_DIR__/dev___SLICE_ID__.md`

验证：
- 执行编译检查: `python -m compileall __CODE_TARGETS__`

禁止：
- 不得修改其他切片的代码落点
- 不得修改共享配置文件（除非切片文档明确允许）
- 不得跨切片调用

报告要求：
- 列出实际修改的文件
- 列出检查过但未修改的文件
- 列出执行的命令
- 列出发现的问题
- 列出不确定项
```

### 6.3 测试阶段 Prompt（单切片）

```
你是 Slice __SLICE_ID__ 的测试专家。

输入：
- 切片文档: __SLICE_DOC__
- 开发阶段报告: __DEV_REPORT__

任务：
1. 阅读切片文档的验收标准
2. 创建测试文件 `tests/test___SLICE_ID__.py`
3. 执行 Disproof Command
4. 区分 primary evidence 和 secondary evidence

输出：
- 测试文件
- 阶段报告: `__STAGE_REPORT_DIR__/test___SLICE_ID__.md`

验证：
- 执行 `python -m pytest tests/test___SLICE_ID__.py -v`

Primary Evidence 要求：
- 必须命中真实入口或真实模块边界
- 不得依赖 fallback 或 mirrored logic

Secondary Evidence：
- Mock-based 单元测试
- Helper 级测试

禁止：
- 不得创建跨切片的测试
- 不得将 secondary evidence 标记为 primary
```

### 6.4 Debug 阶段 Prompt（单切片）

```
你是 Slice __SLICE_ID__ 的 Debug 专家。

输入：
- 切片文档: __SLICE_DOC__
- 开发阶段报告: __DEV_REPORT__
- 测试阶段报告: __TEST_REPORT__

任务：
1. 分析测试失败用例
2. 只修复本切片的代码
3. 重新执行测试
4. 如果发现跨切片问题，上报而非自行修复

输出：
- 修复后的代码
- 阶段报告: `__STAGE_REPORT_DIR__/debug___SLICE_ID__.md`

验证：
- 重新执行 `python -m pytest tests/test___SLICE_ID__.py -v`

禁止：
- 不得修改其他切片的代码
- 不得跳过失败的测试
- 不得修改测试断言来"修过"问题

上报条件：
- 发现问题根源在其他切片
- 发现需要修改共享资源
- 发现需求文档有歧义
```

### 6.5 收尾阶段 Prompt

```
你是主 Agent，负责收尾和验收。

输入：
- 切片索引: __SLICES_INDEX__
- 所有开发阶段报告: __DEV_REPORTS__
- 所有测试阶段报告: __TEST_REPORTS__
- 所有 Debug 阶段报告: __DEBUG_REPORTS__

任务：
1. 检查所有切片的完成状态
2. 执行集成测试
3. 验证切片间的契约
4. 更新文档
5. 决定是否迁移到 tested

输出：
- 阶段报告: `__STAGE_REPORT_DIR__/main_agent_final.md`

验收标准：
- 所有 4 个切片的 Disproof Command 通过
- 集成测试通过
- 契约验证通过
- Primary Evidence 充分

迁移条件：
- 所有条件满足 → 建议迁移到 tested
- 任一条件不满足 → 建议停留在 planned 并说明原因

禁止：
- 不得自行执行文档迁移
- 不得掩盖残余问题
- 不得将未完成的切片标记为完成
```

---

## 七、自动化脚本

### 7.1 拆分验证脚本

```python
# scripts/validate_slices.py

import yaml
from pathlib import Path

def validate_slices(slices_dir: Path) -> dict:
    """验证切片是否满足独立性原则"""
    
    slices = list(slices_dir.glob("slice_*.md"))
    if len(slices) != 4:
        return {"valid": False, "error": f"期望 4 个切片，找到 {len(slices)} 个"}
    
    code_targets = []
    write_targets = []
    
    for slice_file in slices:
        # 解析 YAML frontmatter
        content = slice_file.read_text()
        # ... 提取 code_targets 和 write_targets
        
    # 检查重叠
    code_overlap = set(code_targets[0]) & set(code_targets[1])
    if code_overlap:
        return {"valid": False, "error": f"代码落点重叠: {code_overlap}"}
    
    return {"valid": True}
```

### 7.2 运行脚本

```bash
# automation/run_parallel_task.sh

#!/usr/bin/env bash

SLICES_DIR="$1"
TASK_DOC="$2"

# Phase 0: 拆分
echo "Phase 0: Splitting task..."
iflow -p "$(render_split_prompt "$TASK_DOC")" -y

# 验证拆分
python scripts/validate_slices.py "$SLICES_DIR"
if [[ $? -ne 0 ]]; then
    echo "Split validation failed"
    exit 1
fi

# Phase 1: 并行开发
echo "Phase 1: Parallel development..."
for i in 1 2 3 4; do
    iflow -p "$(render_dev_prompt "$SLICES_DIR/slice_$i.md")" -y &
done
wait

# Phase 2: 并行测试
echo "Phase 2: Parallel testing..."
for i in 1 2 3 4; do
    iflow -p "$(render_test_prompt "$SLICES_DIR/slice_$i.md")" -y &
done
wait

# Phase 3: 并行 Debug
echo "Phase 3: Parallel debug..."
for i in 1 2 3 4; do
    iflow -p "$(render_debug_prompt "$SLICES_DIR/slice_$i.md")" -y &
done
wait

# Phase 4: 收尾
echo "Phase 4: Finalizing..."
iflow -p "$(render_final_prompt "$SLICES_DIR")" -y

echo "All phases completed"
```

---

## 八、与现有系统的整合

### 8.1 与现有 Playbook 的关系

| Playbook | 本方案的关系 |
|----------|-------------|
| `planned-doc-hardening-playbook.md` | 需求文档必须先 hardened 再拆分 |
| `agent-delivery-audit-playbook.md` | 收尾阶段按此 playbook 审计 |
| `normal-agent-todo-hardening-lessons.md` | 每个 subagent 遵循相同 todo 规范 |

### 8.2 与现有目录结构的关系

| 目录 | 用途变化 |
|------|----------|
| `docs/03-changes/<module>/planned/` | 保持不变，存放原始需求文档 |
| `docs/03-changes/<module>/slices/` | [新增] 存放切片文档 |
| `automation/runs/<run_id>/stage_reports/` | 扩展，按切片组织阶段报告 |
| `automation/templates/` | [新增] 并行模式的 prompt 模板 |

### 8.3 迁移路径

1. **第一阶段**：在 `docs/drafts/` 下试验新流程
2. **第二阶段**：验证流程可行后，迁移到 `docs/03-changes/<module>/slices/`
3. **第三阶段**：更新 `rules.md` 和 `agent.md`，添加并行模式入口

---

## 九、风险与缓解

### 9.1 拆分失败

**风险**：需求文档无法拆分为 4 个独立切片

**缓解**：
- 拆分前检查 `split_ready` 标记
- 如果无法拆分为 4 个，允许 2-3 个切片
- 提供"单切片模式"回退方案

### 9.2 切片间契约冲突

**风险**：切片间输入输出契约不一致

**缓解**：
- 拆分阶段明确定义契约
- 收尾阶段强制验证契约
- 发现契约问题时停止流程，等待人工介入

### 9.3 并行执行冲突

**风险**：多个 subagent 同时修改同一文件

**缓解**：
- 拆分验证脚本检查代码落点重叠
- 每个 subagent 只能修改自己切片的文件
- Git lock 机制（未来增强）

### 9.4 阶段报告缺失

**风险**：subagent 未写入阶段报告

**缓解**：
- Prompt 中强制要求写入报告
- 下一阶段开始前检查上一阶段报告
- 报告缺失时停止流程

---

## 十、总结

### 核心改动

| 改动 | 说明 |
|------|------|
| 新增切片文档类型 | 支持需求拆分 |
| 新增切片目录 | `docs/03-changes/<module>/slices/` |
| 扩展阶段报告 | 按切片组织，每个切片 3 份报告 |
| 新增 Prompt 模板 | 5 个阶段的专用模板 |
| 新增验证脚本 | 拆分验证、契约验证 |

### 文档改动量

| 文档 | 改动类型 |
|------|----------|
| `rules.md` | 新增"并行模式"章节 |
| `agent.md` | 新增路由到切片文档 |
| 需求文档模板 | 新增"拆分信息"章节 |
| 新增 playbook | `parallel-subagent-playbook.md` |

### 下一步行动

1. 创建 `docs/03-changes/quantaalpha/slices/` 目录
2. 编写 Prompt 模板到 `automation/templates/`
3. 更新 `automation/run_parallel_task.sh` 脚本
4. 试验一个完整流程
