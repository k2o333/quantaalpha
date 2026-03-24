# 文档系统优化方案（最终版）

**Status:** draft
**Created:** 2026-03-15
**Updated:** 2026-03-15
**Purpose:** 以 `rules.md` 为唯一入口，最小改动支持多 CLI Agent 协作

---

## 1. 核心设计原则

### 1.1 单一入口

```
Agent 启动 → 只读 rules.md → 由 rules.md 路由到其他文档
```

`rules.md` 必须具备四个功能：

| 功能 | 说明 |
|------|------|
| **入口** | 告诉 Agent 从哪里开始 |
| **路由** | 告诉 Agent 不同任务该读哪份文档 |
| **索引** | 告诉 Agent 代码、配置、测试、日志在哪 |
| **约束** | 告诉 Agent 哪些能做、哪些不能做、哪些必须停下等人 |

### 1.2 不增加 Agent 负担

| 原则 | 说明 |
|------|------|
| 不新增 Agent 专用目录 | `08-agents/` 不创建 |
| 不依赖 Agent 主动写文档 | 会话追溯靠 Git commit |
| 不强制微决策文档 | 小改动用轻量级变更文档或 commit message |

### 1.3 拆分过长文档

`doc-rules.md` 有 941 行，Agent 难以快速定位。需拆分为多个小文档。

### 1.4 增强机器可读性

所有文档应使用 **YAML Frontmatter**，便于 Agent 解析和脚本统计：

```yaml
---
status: "in_progress"
owner: "agent"
branch: "feature/app4-pagination"
created_at: "2026-03-15"
module: "app4"
---
```

**原因**：
- 纯 Markdown 解析时格式可能错乱
- YAML 数据块便于 Agent 快速提取关键信息
- 未来可写 Python 脚本批量统计任务进展

### 1.5 防幻觉：统一专用名词

| 术语 | 说明 |
|------|------|
| `app4` | 数据下载系统，唯一可修改的主系统 |
| `quantaalpha` | 因子挖掘系统，位于 `third_party/quantaalpha/` |
| `backtest` | 回测模块，位于 `backtest/` |
| `vnpy` | 位于 `third_party/vnpy/`，**不主动修改** |
| `glue` | 位于 `third_party/glue/`，**不主动修改** |

**原则**：所有文档中对系统的称呼必须全局唯一、完全一致。

---

## 2. 文档层级设计

```
第一层：唯一入口
└── docs/00-governance/rules.md

第二层：按需跳转
├── docs/01-overview/system-overview.md     # 系统概览
├── docs/00-governance/development-workflow.md  # 开发流程
├── docs/00-governance/testing-strategy.md  # 测试策略 [新增]
├── docs/00-governance/doc-types.md         # 文档类型 [拆分]
├── docs/00-governance/doc-naming.md        # 命名规则 [拆分]
├── docs/00-governance/doc-lifecycle.md     # 文档生命周期 [拆分]
├── docs/00-governance/task-handoff.md      # 任务交接模板 [新增]
└── docs/02-modules/*.md                    # 模块文档

第三层：任务与历史
├── docs/03-changes/...                     # 变更文档
├── docs/04-decisions/...                   # ADR
├── docs/07-technical/...                   # 技术流程
└── docs/drafts/...                         # 草稿
```

---

## 3. 目录调整方案

### 3.1 调整后的结构

```
docs/
├── 00-governance/           # 治理文档
│   ├── rules.md             # [重构] 唯一入口，增加导航
│   ├── development-workflow.md  # 保持
│   ├── doc-rules.md         # [重构] 缩减为总纲
│   ├── doc-types.md         # [拆分] 文档类型定义
│   ├── doc-naming.md        # [拆分] 命名规则
│   ├── doc-lifecycle.md     # [拆分] 文档生命周期
│   ├── testing-strategy.md  # [新增] 测试策略
│   └── task-handoff.md      # [新增] 任务交接模板
│
├── 01-overview/             # [新增] 系统概览
│   └── system-overview.md   # 30 秒快速认知
│
├── 02-modules/              # 模块文档
│   ├── app4.md              # [优化] 增加 TL;DR 和 Debug
│   ├── backtest.md          # [优化] 同上
│   └── quantaalpha.md       # [优化] 同上
│
├── 03-changes/              # 变更文档
│   ├── app4/
│   ├── quantaalpha/
│   ├── vnpy/
│   ├── common/
│   └── archive/             # [新增] 归档目录
│
├── 04-decisions/            # ADR（已存在）
├── 05-playbooks/            # 经验手册
├── 06-references/           # 参考文档
├── 07-technical/            # 技术流程
└── drafts/                  # 草稿
```

### 3.2 doc-rules.md 拆分方案

| 原章节 | 内容 | 行数 | 拆分后位置 |
|--------|------|------|------------|
| Section 1 | 目的、原则 | ~30 | 保留在 `doc-rules.md` |
| Section 2 | 文档类型定义 | ~200 | `doc-types.md` |
| Section 3-4 | 目录结构、放置规则 | ~80 | `doc-types.md` |
| Section 5 | 当前真值 vs 历史 | ~30 | 保留在 `doc-rules.md` |
| Section 6-7 | 命名规则、状态头 | ~100 | `doc-naming.md` |
| Section 8-12 | 更新规则、生命周期 | ~200 | `doc-lifecycle.md` |
| Section 13 | Reference Doc 规则 | ~80 | `doc-lifecycle.md` |
| Section 14-18 | Git 规则、AI 规则 | ~150 | 保留在 `doc-rules.md` |

**拆分后各文档行数**：

| 文档 | 预计行数 | Agent 阅读时间 |
|------|----------|----------------|
| `doc-rules.md`（缩减后） | ~150 | 1 分钟 |
| `doc-types.md` | ~280 | 2 分钟 |
| `doc-naming.md` | ~100 | 1 分钟 |
| `doc-lifecycle.md` | ~280 | 2 分钟 |
| `task-handoff.md`（新增） | ~50 | 30 秒 |

---

## 4. rules.md 重构方案

### 4.0 开头指令型语言

在 `rules.md` **第一行**使用指令型语言（Instructional Language），对底层 LLM 的注意力唤醒效果显著：

```markdown
# aspipe_v4 开发规则 (Global Entry for All Agents)

⚠️ **CRITICAL INSTRUCTION FOR AI AGENTS**:

You MUST read this document carefully before executing any other tool or modifying any file.
Do NOT guess the architecture. Use the routing tables below to locate the correct context.

---
```

**为什么用英文大写**：
- 大写关键词（MUST, NOT）对 LLM 的注意力机制有更强的激活效果
- 英文指令在底层模型训练数据中出现频率更高，响应更稳定

### 4.1 新增内容

在 `rules.md` **顶部**增加以下章节：

```markdown
# aspipe_v4 开发规则

## Agent Task Entry

开始任何任务前，必须按顺序执行：

1. 阅读本文档
2. 根据"文档导航"定位需要的文档
3. 根据"代码入口导航"定位需要的代码与配置
4. 根据"操作规范索引"选择分支、测试和提交方式
5. 在未完成上下文注入前，不得直接修改代码

---

## 文档导航

根据任务类型继续阅读以下文档：

| 任务类型 | 读这份文档 |
|----------|-----------|
| 需要理解整体系统 | `docs/01-overview/system-overview.md` |
| 需要修改某个模块行为 | `docs/02-modules/<module>.md` |
| 需要理解详细调用链 | `docs/07-technical/<topic>.md` |
| 需要了解开发/分支规则 | `docs/00-governance/development-workflow.md` |
| 需要决定测试范围 | `docs/00-governance/testing-strategy.md` |
| 需要了解文档类型和命名 | `docs/00-governance/doc-types.md` |
| 需要继续未完成任务 | `docs/03-changes/...` 或对应分支 |
| 草稿文档 | `docs/drafts/...` **只可参考，不可当作当前事实** |

---

## 代码入口导航

按任务类型优先检查以下位置：

### app4 数据下载系统
| 类型 | 路径 |
|------|------|
| CLI 入口 | `app4/main.py` |
| 全局配置 | `app4/config/settings.yaml` |
| 接口配置 | `app4/config/interfaces/*.yaml` |
| 核心逻辑 | `app4/core/*.py` |
| 增量更新 | `app4/update/` |

### quantaalpha 因子挖掘系统
| 类型 | 路径 |
|------|------|
| CLI 入口 | `third_party/quantaalpha/quantaalpha/cli.py` |
| 配置 | `third_party/quantaalpha/configs/` |
| 因子库 | `third_party/quantaalpha/data/factorlib/` |

### backtest 回测系统
| 类型 | 路径 |
|------|------|
| 入口脚本 | `backtest/start/*.py` |
| 数据 | `data/stk_factor_pro/` |

### 数据与运行输出
| 类型 | 路径 |
|------|------|
| 数据目录 | `data/` |
| 缓存目录 | `cache/` |
| 日志目录 | `log/` |
| 测试目录 | `test/` |

### 不维护的范围
- `third_party/vnpy/` - 仅 vendor 存在，不主动修改
- `third_party/glue/` - 仅 vendor 存在，不主动修改

---

## 操作规范索引

| 规范类型 | 文档位置 |
|----------|----------|
| 分支策略、原子化提交、人工审核边界 | `docs/00-governance/development-workflow.md` |
| 测试等级、验证入口、冒烟命令 | `docs/00-governance/testing-strategy.md` |
| 文档类型、命名规则、生命周期 | `docs/00-governance/doc-types.md` |
| 任务交接、多步任务上下文 | `docs/00-governance/task-handoff.md` |

---

## 风险等级判定

| 风险级别 | 判定条件 | 要求 |
|----------|----------|------|
| **低** | 文档、日志、注释、小修复 | 可直接改，最小验证 |
| **中** | 新接口、新配置、小范围行为改动 | 分支 + 定向测试 |
| **高** | 存储、分页、去重、并发、更新语义 | 分支 + 强验证 + 人工审核 |

---

## 人工审核触发条件

以下情况**必须停下来等待人工审查**：

| 触发条件 | 说明 |
|----------|------|
| 改变并发模型 | max_workers、队列大小、线程池行为 |
| 改变存储落地 | 文件格式、分区策略、写入模式 |
| 改变 Schema 语义 | 字段类型、主键定义、衍生字段 |
| 影响主库稳定性 | 大范围重构、删除代码、修改核心路径 |
| 跨模块改动 | 同时修改 app4 + quantaalpha + backtest |

---

## 必须行为

1. 修改代码前必须先完成文档导航和代码入口定位
2. 不确定或实验性改动必须在分支上进行
3. 有意义的改动必须进行原子化提交
4. 修改行为逻辑后必须执行对应级别验证
5. 涉及核心语义变更时必须停下来等待人工审查
6. 跨多步任务提交前必须更新变更文档的当前进展

---

## 禁止行为

1. 禁止未读文档就直接修改代码
2. 禁止默认将 `docs/drafts/` 视为当前事实
3. 禁止因为测试通过就自动视为可合入 main
4. 禁止修改超出当前任务范围的大块代码
5. 禁止把临时文件和调试产物提交进正式代码路径
6. 禁止自动合并到 main 分支

---

## ...（后续保持现有内容）
```

---

## 5. 新增文档内容

### 5.1 `01-overview/system-overview.md`

```markdown
# System Overview

## 一句话描述
aspipe_v4 是配置驱动的金融数据下载 → 因子挖掘 → 策略回测完整链路。

## 三大子系统
| 子系统 | 职责 | 入口 | 数据目录 |
|--------|------|------|----------|
| app4 | 数据下载与存储 | `python app4/main.py` | `data/` |
| quantaalpha | LLM 驱动因子挖掘 | `quantaalpha mine` | `third_party/quantaalpha/data/` |
| backtest | Alpha101 因子回测 | `python backtest/start/*.py` | `backtest/start/` |

## 数据流向
Tushare API → app4 (Parquet) → quantaalpha (因子库) → backtest (策略验证)

## 关键依赖
| 依赖 | 用途 | 配置 |
|------|------|------|
| Tushare Pro API | 数据源 | `TUSHARE_TOKEN` 环境变量 |
| Qlib | 回测框架 | quantaalpha 依赖 |
| Polars | 数据处理 | - |

## 不维护的范围
- `third_party/vnpy/` - 仅 vendor 存在
- `third_party/glue/` - 仅 vendor 存在

## 快速开始
```bash
# 验证 app4 环境
python -c "from app4.core.config_loader import ConfigLoader; ConfigLoader().validate_config()"

# 下载测试数据
python app4/main.py --interface trade_cal --start_date 20240101 --end_date 20240131
```

## 文档导航
见 `docs/00-governance/rules.md` 的"文档导航"章节。
```

### 5.2 `00-governance/testing-strategy.md`

```markdown
# Testing Strategy

## 测试分级

| 级别 | 触发条件 | 验证方式 | 人工审查 |
|------|----------|----------|----------|
| L0 | 文档、注释、日志级别 | 人工检查 | 不需要 |
| L1 | 配置调整、小修复 | 相关模块单测 | 不需要 |
| L2 | 新功能、接口行为变更 | 全量测试 + 集成测试 | 可选 |
| L3 | 存储/分页/去重/并发/更新语义 | 全量测试 + 手动冒烟 | **必须** |

## 各模块标准命令

### app4
```bash
# 单元测试
pytest test/test/test_*.py -v

# 单接口冒烟
python app4/main.py --interface trade_cal --start_date 20240101 --end_date 20240131

# 配置验证
python -c "from app4.core.config_loader import ConfigLoader; ConfigLoader().validate_config()"

# 增量更新预览
python app4/main.py --update --update-dry-run
```

### quantaalpha
```bash
cd third_party/quantaalpha
conda activate mining

# 单元测试
pytest tests/ -v

# 健康检查
quantaalpha health_check
```

### backtest
```bash
# 回测验证
python backtest/start/backtest_alpha101_polars.py

# 短期调试
python backtest/start/debug_pure_polars_fixed.py
```

## 必须人工审查的测试结果

- 数据完整性验证（记录数、日期范围）
- 性能回归验证（执行时间对比）
- 核心路径冒烟（真实 API 请求）
- 多日/多股票并发验证

## 测试覆盖率要求

| 模块 | 最低覆盖率 | 关键路径 |
|------|-----------|----------|
| app4/core/ | 60% | downloader, storage, pagination |
| quantaalpha/backtest/ | 50% | runner, validation |
| backtest/ | 无要求 | 因子计算正确性 |
```

### 5.3 `00-governance/task-handoff.md`

```markdown
# Task Handoff Template

## 适用场景

- 多步任务
- 分支任务
- 需要后续 Agent 接手的任务
- 需要 subagent 协作的任务
- 无头模式执行的任务

## YAML Frontmatter 规范

所有交接文档必须使用 YAML Frontmatter，便于 Agent 解析和脚本统计：

```yaml
---
status: "in_progress"  # in_progress | blocked | completed | handed_off
owner: "agent"         # agent-id | human-name
branch: "feature/app4-pagination"
created_at: "2026-03-15"
updated_at: "2026-03-15"
module: "app4"         # app4 | quantaalpha | backtest | common
---
```

**为什么用 YAML Frontmatter**：
- 纯 Markdown 解析时格式可能错乱
- Agent 可以快速提取关键元数据
- 未来可写 Python 脚本批量统计任务进展

## 最小交接模板

```markdown
---
status: "in_progress"
owner: "agent"
branch: "feature/app4-pagination"
created_at: "2026-03-15"
updated_at: "2026-03-15"
module: "app4"
---

# [任务标题]

## Goal
[一句话描述目标]

## Current Progress
- [x] 已完成项 1
- [x] 已完成项 2
- [ ] 进行中项 3
- [ ] 待办项 4

## Constraints
- [不可触碰的边界]
- [必须遵守的约束]

## Validation Done
- [已通过的验证]
- [验证命令或方法]

## Next Step
[下一步具体行动]

## Blockers（如有）
[阻塞原因和需要的帮助]
```

## 交接规则

1. **提交前更新**：跨多步、跨分支、未一次完成的任务，提交前必须更新 Current Progress / Next Step
2. **状态同步**：状态变化时同步更新 Branch 和 Updated 字段
3. **阻塞标记**：遇到阻塞必须标记 Status 为 blocked 并填写 Blockers
4. **交接确认**：handed_off 状态必须有明确的接手方

## 存放位置

- 正式变更：`docs/03-changes/<module>/YYYY-MM-DD-topic.md`
- 轻量任务：可在变更文档中使用简化格式
```

---

## 6. 优化现有文档

### 6.1 `02-modules/*.md` 增加 TL;DR

每个模块文档开头增加：

```markdown
## TL;DR

- **职责**：[一句话描述]
- **入口**：[CLI 入口文件]
- **关键配置**：[配置文件路径]
- **常改代码**：[最常修改的代码路径]
- **易错点**：[修改此模块最容易出错的地方]
```

### 6.2 `02-modules/*.md` 增加 Debug Guide

每个模块文档末尾增加：

```markdown
## Debug Guide

### 常见问题

| 问题 | 排查步骤 |
|------|----------|
| [问题 1] | [排查步骤] |
| [问题 2] | [排查步骤] |

### 调试命令

```bash
# [场景 1]
[命令]

# [场景 2]
[命令]
```

### 日志位置

- 运行日志：`log/...`
- 性能报告：`log/reports/...`
```

---

## 7. 变更文档归档机制

### 7.1 归档规则

- 每季度归档一次
- 归档到 `docs/03-changes/archive/YYYY-QN/`
- 保留索引文件 `INDEX.md`

### 7.2 归档命令

```bash
# 归档 2026-Q1
mkdir -p docs/03-changes/archive/2026-Q1
mv docs/03-changes/2026/2026-0[123]-*.md docs/03-changes/archive/2026-Q1/

# 创建索引
cat > docs/03-changes/archive/2026-Q1/INDEX.md << 'EOF'
# 2026-Q1 归档索引

归档时间：2026-04-01

## 按主题分类
- 分页相关：...
- 内存相关：...
EOF
```

---

## 8. Git 流程与文档关联

### 8.1 Commit Message 规范

```bash
# 格式
<type>(<scope>): <subject>

[optional body]

Refs: docs/03-changes/<module>/<file>.md

# 示例
feat(app4): 添加 commit_on_success 配置

Refs: docs/03-changes/app4/2026-03-15-offset-atomic-fix.md
```

### 8.2 分支命名

```bash
feature/<module>-<brief>   # 功能
fix/<module>-<brief>       # 修复
refactor/<module>-<brief>  # 重构
```

---

## 10. 预期收益

| 维度 | 改进前 | 改进后 |
|------|--------|--------|
| Agent 上手时间 | 需要阅读多份文档，猜测该看什么 | 从 `rules.md` 开始，按导航直达 |
| 文档阅读量 | `doc-rules.md` 941 行 | 单个文档 100-300 行 |
| 任务交接 | 无标准格式，信息丢失 | 有最小模板，上下文完整 |
| 测试决策 | 不知道测什么、测多深 | 有分级表，按风险级别执行 |
| 人工审查 | 不知道什么时候需要 | 有触发条件表，自动判断 |
| 任务统计 | 手动翻阅文档 | YAML Frontmatter 支持脚本批量统计 |
| Agent 注意力 | 文档开头无重点提示 | 指令型语言激活注意力 |
| 术语一致性 | 可能出现幻觉 | 全局唯一术语，防止混淆 |

---

## 11. 有头模式 vs 无头模式

### 11.1 核心差异

| 维度 | 有头模式 | 无头模式 |
|------|----------|----------|
| **人类在场** | 是，可交互确认 | 否，独立执行 |
| **决策方式** | 遇到不确定可以问人类 | 必须靠文档提前规定 |
| **文档重点** | 上下文解释、背景信息 | 精确指令、验收标准 |
| **容错空间** | 高，人类可以纠正 | 低，必须一次性做对 |
| **阻塞处理** | 询问人类 | 标记 blocked，等待处理 |

### 11.2 文档需求差异

#### 有头模式需要的文档

| 文档 | 用途 |
|------|------|
| `rules.md` 导航 | 人类和 Agent 共同理解"该看什么" |
| 模块 TL;DR | 快速建立上下文，便于人类和 Agent 沟通 |
| 变更文档的背景/原因 | 人类审查时理解"为什么要这样改" |
| `development-workflow.md` | 人类决定分支策略、人工审核边界 |

**核心**：有头模式可以随时停下来问人类，所以文档可以更"解释性"，不需要面面俱到。

#### 无头模式需要的文档

| 文档 | 用途 |
|------|------|
| **风险等级表** | Agent 自己判断"这个改动风险多大，要不要等人" |
| **测试策略** | Agent 自己判断"测什么、测多深" |
| **人工审核触发条件** | Agent 自己判断"这个要不要停下来等人审" |
| **任务交接模板** | 无头任务中断后，下一个 Agent 能接手 |
| **验收标准** | 明确"做到什么程度算完成" |

**核心**：无头模式人类不在场，所以文档必须"规定性"，精确到可执行。

### 11.3 场景示例

#### 场景：修改分页逻辑

**有头模式**：
```
Agent 读模块文档 → 发现分页逻辑复杂 → 问人类：
"这个分页逻辑改动会影响存储，要继续吗？"
人类：继续，但要开分支
Agent：好的，开分支继续
```
文档只需提供**上下文**，决策靠交互。

**无头模式**：
```
Agent 读 rules.md → 查风险等级表：
"分页改动 = 高风险" → 查人工审核触发条件：
"存储/分页/并发 = 必须人工审核" → 
标记任务为 blocked，等待人类
```
文档必须**精确规定**，决策靠规则。

### 11.4 共同点

两种模式都需要从 `rules.md` 开始，按导航找文档。

### 11.5 关键差异总结

| 差异点 | 有头模式 | 无头模式 |
|--------|----------|----------|
| 文档风格 | 解释性 | 规定性 |
| 决策来源 | 文档 + 人类交互 | 文档规则表 |
| 关键文档 | 导航、TL;DR、背景说明 | 风险表、触发条件、验收标准 |

---

## 12. 支持的协作模式

| 模式 | 说明 | 关键文档 |
|------|------|----------|
| 有头模式 | 人类实时参与，可交互确认 | `rules.md` 导航、模块 TL;DR、变更文档背景 |
| 无头模式 | Agent 自主执行，靠规则判断 | 风险等级表、测试策略、人工审核触发条件、验收标准 |
| 多 Agent 并行 | 不同 Agent 不同任务 | Git 分支 + 变更文档记录范围 |
| 任务接力 | Agent A → Agent B | `task-handoff.md` 模板 |
| Subagent 协作 | 主 Agent 调子 Agent | 同一交接模板，上下文传递 |
| 自反思 | Agent 自己回顾 | Git commit + 变更文档引用 |

---

## 13. 总结

### 核心改动

1. **`rules.md` 作为唯一入口**：增加导航、索引、约束
2. **拆分 `doc-rules.md`**：从 941 行拆为 4 个小文档
3. **新增 `system-overview.md`**：30 秒快速认知
4. **新增 `testing-strategy.md`**：明确测试边界
5. **新增 `task-handoff.md`**：支持任务交接
6. **优化模块文档**：增加 TL;DR 和 Debug Guide

### 机器可读性增强

| 增强项 | 说明 |
|--------|------|
| YAML Frontmatter | 所有文档使用统一的元数据头，便于解析和统计 |
| 指令型语言 | `rules.md` 开头使用英文大写指令，激活 LLM 注意力 |
| 术语一致性 | 全局唯一术语，防止 Agent 幻觉 |

### 不做的事

- 不创建 `08-agents/` 目录
- 不要求 Agent 额外写 session log
- 不创建微决策专用目录
- 不增加 Agent 认知负担

### 最终文档层级

```
第一层：rules.md（唯一入口）
    ↓
第二层：system-overview / testing-strategy / doc-types / task-handoff / modules
    ↓
第三层：changes / decisions / technical / drafts
```

这样 Agent 只需要从 `rules.md` 开始，按导航找到所需文档，完成上下文注入后开始工作。

---

## 14. 下一步行动

### P0（立即执行）

| 序号 | 任务 | 产出物 |
|------|------|--------|
| 1 | 新建 `docs/01-overview/system-overview.md` | 系统概览文档 |
| 2 | 重构 `docs/00-governance/rules.md` | 增加导航、约束、指令型语言 |
| 3 | 拆分 `docs/00-governance/doc-rules.md` | doc-types.md, doc-naming.md, doc-lifecycle.md |

### P1（本周完成）

| 序号 | 任务 | 产出物 |
|------|------|--------|
| 4 | 新增 `docs/00-governance/testing-strategy.md` | 测试策略文档 |
| 5 | 新增 `docs/00-governance/task-handoff.md` | 任务交接模板 |
| 6 | 优化 `docs/02-modules/*.md` | 增加 TL;DR 和 Debug Guide |

### P2（后续迭代）

| 序号 | 任务 | 产出物 |
|------|------|--------|
| 7 | 归档 `docs/03-changes/` 历史变更 | 减少噪音 |
| 8 | 补充 `docs/04-decisions/` ADR | 记录架构决策 |
| 9 | 整理 `docs/06-references/` | 改善查找体验 |