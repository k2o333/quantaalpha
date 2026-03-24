# Flat Migration Follow-ups — 第二轮修复报告

## 基本信息

- **执行人**: opencode agent
- **执行时间**: 2026-03-21
- **任务文档**: `docs/03-changes/quantaalpha/2026-03-21-flat-migration-followups.md`
- **状态**: done

## 修复来源

reviewer 对第一轮执行结果进行了审查，指出三个问题：

1. **validator 报错**：`status: done` 的 change doc 缺少 `validation` 字段，validator 报告 `done change doc missing validation`
2. **index 和工具行为未对齐**：README 和 .task.md 文件虽然在 frontmatter 中添加了 `classification` 标记，但 `doc_index.py` 仍将这些文件当作 change doc 计入列表和验证
3. **报告数据不准确**：文档声称 list 返回30条、validate 报告 quantaalpha 0 issues，但实际运行时 list 返回29条（follow-up doc 已被标记 done）、validate 报告 quantaalpha 1 issue

## 根本原因分析

### 问题1：遗漏 `validation` 字段

`doc_index.py` 第316-317行：
```python
if doc.status == "done" and not doc.validation_entries:
    issues.append(f"{doc.rel_path}: done change doc missing validation")
```

第一轮执行将任务文档标记为 `status: done` 后，遗漏了添加 `validation` 字段。规则明确但被忽视。

### 问题2：分类标记无法使 validator 跳过文件

README 和 .task.md 文件在第一轮中添加了 `classification: operational_artifact`，但 `doc_index.py` 的验证逻辑只看 `doc_type` 和 `status` 字段。`classification` 字段不影响验证行为。这些文件缺少 `doc_type: operational_artifact`，所以 validator 仍会：
- 从路径推断 `doc_type: change`（README 在 `03-changes/` 下；.task.md 文件也在 `03-changes/` 下）
- 要求 `module` 和 `status` 字段
- README 无 `module` → 报告 `missing module`（第一轮中被记录为"误索引"）
- .task.md 有 `module: quantaalpha` 和 `status: planned`（从 legacy path 推断）→ 被计入 planned 列表

### 问题3：记录数量偏差

第一轮执行时，follow-up 任务文档仍在 `planned` 状态，所以 `doc_index.py list --status planned` 返回30条。标记 done 后，文档退出 planned 过滤，列表变为29条（因 .task.md 文件从 legacy path 推断 `status: planned` 所以仍计入）。为 .task.md 添加 `doc_type: operational_artifact` 后，这些文件不再被识别为 change doc，列表最终为11条。

## 执行的修复

### 修复 1：为 done 文档补充 validation 字段

在 `2026-03-21-flat-migration-followups.md` 的 frontmatter 中添加：

```yaml
validation:
  - python3 scripts/doc_index.py list --type change --module quantaalpha --status planned --json
  - python3 scripts/doc_index.py validate
```

### 修复 2：为所有 legacy 运营工件添加 doc_type

两个 README 文件添加前置 frontmatter：

```yaml
---
doc_type: operational_artifact
classification: non_source_of_truth_index
---
```

所有16个 .task.md 文件，在已有 `classification: operational_artifact` 基础上添加 `doc_type: operational_artifact`：

```yaml
---
doc_type: operational_artifact
classification: operational_artifact
stage: dev
...
```

修改涉及18个文件（2个 README + 16个 .task.md）。

### 修复 3：更新执行报告

更新了 `docs/drafts/report/2026-03-21-flat-migration-followups-execution-report.md` 中的数据：列表记录数从30改为11，quantaalpha 验证状态从"0 issues"改为"初始1 issue 已修复"，并新增了"教训与建议"章节。

## 最终验证结果

```bash
python3 scripts/doc_index.py list --type change --module quantaalpha --status planned --json
# count: 11（均为 flat path change doc）

python3 scripts/doc_index.py validate
# quantaalpha: 0 issues
# app4: 26 issues (不在本次任务范围)
```

README 和 .task.md 文件不再出现在 planned 列表中，validator 完全跳过这些文件。

## 修改文件清单

| # | 文件 | 操作 |
|---|---|---|
| 1 | `docs/03-changes/quantaalpha/2026-03-21-flat-migration-followups.md` | 添加 `validation` 字段 |
| 2 | `docs/03-changes/quantaalpha/planned/README.md` | 添加 frontmatter + `doc_type: operational_artifact` |
| 3 | `docs/03-changes/quantaalpha/planned/parr2/README.md` | 添加 frontmatter + `doc_type: operational_artifact` |
| 4-7 | `planned/parr2/dev/*.task.md` (4个) | 添加 `doc_type: operational_artifact` |
| 8-11 | `planned/parr2/test/*.task.md` (4个) | 添加 `doc_type: operational_artifact` |
| 12-15 | `planned/parrelell/dev/*.task.md` (4个) | 添加 `doc_type: operational_artifact` |
| 16-19 | `planned/parrelell/review/*.task.md` (4个) | 添加 `doc_type: operational_artifact` |
| 20 | `docs/drafts/report/2026-03-21-flat-migration-followups-execution-report.md` | 更新数据 + 新增教训章节 |

共20个文件。

## 第三轮：收尾两点

### Task A：更新执行摘要数据

`docs/03-changes/quantaalpha/2026-03-21-flat-migration-followups.md` 中的执行摘要仍反映修复前状态（Item 6 写"30 documents found"，Item 7 写"0 issues"无初始问题说明）。更新如下：

- Item 2：补充 `doc_type: operational_artifact` 说明，注明同时处理了 source 字段清理
- Item 3：补充 `doc_type: operational_artifact` 说明
- Item 6：`30 documents` → `11 documents`，注明 README 和 .task.md 被 `doc_type: operational_artifact` 排除
- Item 7：补充初始运行有1条 issue（`done change doc missing validation`）的说明

### Task B：清理 legacy `.task.md` 中的 planned/ 路径引用

对所有16个 `.task.md` 文件的 `source_doc` / `source_slice_doc` / `source_dev_task_doc` 字段进行更新：

- `source_slice_doc`（4个，`planned/parrelell/dev/`）：路径从 `planned/parrelell/2026-03-18-*.md` 更新为 flat path `quantaalpha/2026-03-18-*.md`，附注 `# historical; flat path is the source of truth`
- `source_dev_task_doc`（4个，`planned/parrelell/review/`）：附注 `# historical artifact reference only`
- `source_doc`（8个，`planned/parr2/dev/` 和 `planned/parr2/test/`）：同上

验证：`grep -r "planned/parrelell/2026-03-18" docs/03-changes/quantaalpha/planned/*.task.md` → 0 matches。

### 最终验证

```bash
python3 scripts/doc_index.py list --type change --module quantaalpha --status planned --json
# count: 11（全部为 flat path planned change doc）

python3 scripts/doc_index.py validate
# quantaalpha: 0 issues
# app4: 26 issues (outside scope)
```

全部收尾完成。

## 教训

**`doc_index.py` 的验证逻辑与 frontmatter 分类字段完全解耦**：仅添加 `classification` 而不添加 `doc_type` 不会影响 validator 的行为。第一轮执行中误以为添加 `classification` 就能使文件脱离验证范围，但实际 validator 只关心 `doc_type` 和 `status`。正确的做法是始终添加 `doc_type: operational_artifact`，因为这是 validator 用来区分文档类型的依据。

这说明在修改 frontmatter 分类前，需要先理解工具的实际逻辑，不能假设字段名称的语义会自动生效。
