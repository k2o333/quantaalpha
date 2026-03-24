# Change Doc System Simplification Proposal

Status: draft
Created: 2026-03-21
Owner: quan

---

## 一、问题背景

### 1.1 现状分析

当前 `docs/03-changes/` 目录结构：

```
docs/03-changes/
├── app4/                      # 27 docs at root (扁平)
│   ├── draft/                 # 0 docs
│   ├── planned/               # 0 docs
│   ├── in_progress/           # 0 docs
│   ├── ...                    # 其他状态目录均为空
│   └── *.md                   # 27 docs directly in root
├── quantaalpha/               # 0 docs at root (嵌套)
│   ├── planned/               # 33 docs
│   ├── implemented/           # 9 docs
│   ├── accepted/              # 3 docs
│   └── archived/              # 3 docs
├── common/
│   └── accepted/              # 3 docs
└── vnpy/                      # reserved, empty
```

**核心问题**：

1. **目录结构不一致**：app4 扁平，quantaalpha 嵌套
2. **状态目录层级过深**：8 个状态子目录（draft/planned/in_progress/blocked/implemented/tested/accepted/archived）
3. **状态变更成本高**：需要移动文件 + 修改 Status 字段，两处同步
4. **查询依赖目录遍历**：人工难以快速统计各状态文档数量

### 1.2 信息熵分析

| 操作 | 当前方案 | 问题 |
|------|----------|------|
| 查看所有进行中任务 | 遍历多个 `in_progress/` 目录 | 需要知道哪些模块存在 |
| 修改任务状态 | 移动文件 + 修改字段 | 两处修改，易遗漏 |
| 统计任务分布 | `find` + 手动统计 | 无标准化工具 |
| 查看某模块任务 | 遍历模块下 8 个子目录 | 目录结构不透明 |

---

## 二、简化方案

### 2.1 核心原则

1. **扁平化目录**：删除状态子目录，文档直接放在模块目录下
2. **状态内聚**：状态仅通过文档头部的 `Status:` 字段管理
3. **脚本驱动**：用脚本扫描状态，替代目录遍历

### 2.2 目标目录结构

```text
docs/03-changes/
├── app4/
│   ├── 2026-02-25-cyq-chips-offset-pagination-fix.md
│   ├── 2026-02-25-disclosure-date-fix-report.md
│   └── ...
├── quantaalpha/
│   ├── 2026-03-15-iterate2-01-revalidate-semantics.md
│   ├── 2026-03-15-iterate2-02-failed-factor-debug.md
│   └── ...
├── backtest/
│   └── ...
├── common/
│   └── ...
└── vnpy/                     # reserved for future use
```

**变化**：
- 删除所有状态子目录（draft/planned/in_progress/...）
- 文档直接放在模块根目录
- 状态通过文档头部字段管理

### 2.3 状态简化

**当前状态（8 个）**：
```
draft → planned → in_progress → blocked → implemented → tested → accepted → archived
```

**建议简化为（4-5 个）**：
```
draft → planned → doing → done → archived
         ↑
      blocked (可选，标记暂停)
```

**状态含义**：

| 状态 | 含义 | 对应旧状态 |
|------|------|-----------|
| draft | 探索中，未确定实施 | draft |
| planned | 已批准，待开始 | planned |
| doing | 实施中 | in_progress, blocked |
| done | 已完成 | implemented, tested, accepted |
| archived | 已归档 | archived |

**简化理由**：

1. `implemented` vs `tested` vs `accepted` 的区分对单个开发者/agent 意义不大
2. 减少状态可以减少心智负担
3. `blocked` 可作为 `doing` 的子状态，用 `Blocked-by:` 字段标记

### 2.4 文档头部格式

```yaml
# 任务标题

Status: planned
Module: quantaalpha
Created: 2026-03-21
Updated: 2026-03-22
Owner: quan

---
```

**新增字段**：
- `Updated`: 状态变更时间，便于追踪时间线
- `Module`: 冗余但有用，脚本可跨目录查询

### 2.5 状态查询脚本

**脚本位置**: `scripts/doc_status.py`

**使用方式**：

```bash
# 查看所有 doing 任务
python scripts/doc_status.py list --status doing

# 查看某模块的 planned 任务
python scripts/doc_status.py list --module quantaalpha --status planned

# 查看状态统计
python scripts/doc_status.py summary

# 输出 JSON 供其他工具使用
python scripts/doc_status.py list --status doing --json

# 查看某个 Owner 的任务
python scripts/doc_status.py list --owner quan

# 查看超过 N 天未更新的任务
python scripts/doc_status.py list --stale --days 7
```

**输出示例**：

```
$ python scripts/doc_status.py list --status doing

Module: quantaalpha
├── 2026-03-15-iterate2-01-revalidate-semantics.md
│   Status: doing | Created: 2026-03-15 | Updated: 2026-03-18 | Owner: quan
└── 2026-03-15-iterate2-02-failed-factor-debug.md
    Status: doing | Created: 2026-03-15 | Updated: 2026-03-16 | Owner: quan

Total: 2 documents
```

```
$ python scripts/doc_status.py summary

Status Summary:
  draft:     5
  planned:   8
  doing:     3
  done:     12
  archived: 10

By Module:
  app4:       27 documents
  quantaalpha: 48 documents
  common:      3 documents
```

---

## 三、迁移策略

### 3.1 渐进式迁移（推荐）

**原则**：不一次性批量迁移，而是在文档状态变更时顺便迁移

**步骤**：

1. **创建脚本** `scripts/doc_status.py`
   - 支持扫描新旧两种目录结构
   - 自动检测文档位置和状态

2. **更新规范** `docs/00-governance/doc-standards.md`
   - 定义新的目录结构规范
   - 定义新的状态值
   - 保留对旧结构的兼容说明

3. **新文档按新规范创建**
   - 直接放在模块根目录
   - 使用简化的状态值

4. **旧文档渐进迁移**
   - 当文档状态变更时，顺便移动到根目录
   - 更新状态字段为简化值
   - 优先级：低

5. **清理空目录**
   - 确认所有文档迁移后
   - 删除空的状态子目录

### 3.2 不要做的事

❌ **不要一次性批量迁移 quantaalpha 的 48 个文档**

原因：
1. 可能破坏文档间引用链接
2. 风险高，收益不明显
3. 没有紧急性

❌ **不要立即删除状态子目录**

原因：
1. 旧文档仍在使用
2. 需要渐进迁移
3. 保留一段时间作为过渡期

---

## 四、需要修改的文件

### 4.1 新增文件

| 文件 | 说明 |
|------|------|
| `scripts/doc_status.py` | 状态查询脚本 |

### 4.2 修改文件

| 文件 | 修改内容 |
|------|----------|
| `docs/00-governance/doc-standards.md` | 更新目录结构说明，定义新状态值 |
| `docs/00-governance/doc-workflows.md` | 更新状态变更流程（改字段而非移动文件） |
| `docs/00-governance/agent.md` | 添加脚本使用说明 |

### 4.3 可删除内容（待迁移完成后）

- `docs/03-changes/<module>/draft/` 等子目录
- 相关的 `.gitkeep` 文件

---

## 五、信息熵对比

| 操作 | 旧方案 | 新方案 | 收益 |
|------|--------|--------|------|
| 查看所有进行中任务 | 遍历多个子目录 | `doc_status.py list --status doing` | 单一入口 |
| 修改任务状态 | 移动文件 + 修改字段 | 仅修改字段 | 减少 50% 操作 |
| 查看某模块任务 | 遍历模块下多个子目录 | `doc_status.py list --module X` | 无需知道目录结构 |
| 统计任务分布 | 手动统计 | `doc_status.py summary` | 自动化 |

---

## 六、风险与缓解

### 6.1 风险

1. **文档引用断裂**
   - 旧文档可能有相对路径引用
   - 移动后会失效

2. **Agent 不熟悉新规范**
   - 需要更新 agent.md
   - 需要在 system prompt 中强调

### 6.2 缓解措施

1. **渐进迁移**
   - 不批量移动
   - 在状态变更时顺便迁移

2. **脚本兼容新旧**
   - `doc_status.py` 同时支持两种结构
   - 平滑过渡

3. **明确迁移时间线**
   - 不设置硬性截止日期
   - 自然完成迁移

---

## 七、决策建议

### 7.1 推荐采纳

- ✅ 扁平化目录结构
- ✅ 状态内聚到文档字段
- ✅ 脚本驱动查询
- ✅ 渐进式迁移策略

### 7.2 需要确认

- ⏸️ 状态简化方案：`draft → planned → doing → done → archived`
  - 是否保留 `blocked` 作为子状态？
  - 是否需要更细粒度的状态？

### 7.3 不推荐

- ❌ 一次性批量迁移
- ❌ 立即删除旧目录结构

---

## 八、下一步行动

如果方案确认，建议执行顺序：

1. [ ] 创建 `scripts/doc_status.py`（支持新旧两种模式）
2. [ ] 更新 `docs/00-governance/doc-standards.md`
3. [ ] 更新 `docs/00-governance/doc-workflows.md`
4. [ ] 更新 `docs/00-governance/agent.md`
5. [ ] 新文档按新规范创建
6. [ ] 旧文档渐进迁移（低优先级）
