---
doc_type: change
module: app4
status: done
owner: quan
created: 2026-03-21
updated: 2026-03-21
summary: app4 模块文档体系扁平化迁移与清理总计划
doc_refs:
  - docs/00-governance/agent.md
  - docs/00-governance/doc-standards.md
  - docs/00-governance/doc-workflows.md
  - docs/00-governance/doc-validation.md
  - docs/05-playbooks/03-changes-flat-migration-playbook.md
validation:
  - python3 scripts/doc_index.py list --type change --module app4 --json
  - python3 scripts/doc_index.py validate
---

# App4 Flat Migration And Cleanup Plan

## Purpose

本计划用于收敛 `docs/03-changes/app4/` 下现有 change docs 的元数据缺失、状态目录残留、文档角色混杂和校验不通过问题。

按 `docs/00-governance/agent.md`，这是一个模块范围内的具体执行任务，因此应放在 `docs/03-changes/app4/`，而不是治理层或通用 playbook。

## Scope

本计划覆盖：
- `docs/03-changes/app4/` 下现有 27 篇 change docs
- `docs/03-changes/app4/` 下 legacy 状态目录残留
- 与 app4 change docs 直接相关的高价值引用修正
- `doc_index.py` 对 app4 的索引与校验收口

本计划不覆盖：
- `docs/00-governance/` 规则重写
- `quantaalpha` 模块文档
- 代码实现本身的功能修复
- 全仓库其他模块的历史文档清理

## Current State

截至 2026-03-21，`app4` 的文档状态如下：

- `doc_index.py list --type change --module app4 --json` 当前识别出 27 篇 `change` 文档
- 其中 26 篇缺少 `status`，导致 `python3 scripts/doc_index.py validate` 失败
- `docs/03-changes/app4/` 已存在 module-flat 主文档，但仍保留 legacy 状态目录：
  - `accepted/`
  - `archived/`
  - `blocked/`
  - `draft/`
  - `implemented/`
  - `in_progress/`
  - `planned/`
  - `tested/`
- 当前这些 legacy 目录只剩 `.gitkeep`，但目录本身仍会误导 agent 继续按旧结构创建文档
- 现有 flat docs 的 frontmatter 一致性不足，除 [`2026-03-15-offset-atomic-fix.md`](/home/quan/testdata/aspipe_v4/docs/03-changes/app4/2026-03-15-offset-atomic-fix.md) 外，其余多数缺少标准字段

## Target State

完成后，`app4` 应满足以下状态：

- `docs/03-changes/app4/` 下所有 source-of-truth change docs 都采用 module-flat 路径
- 每篇 active change doc 都有完整 frontmatter，至少包含：
  - `doc_type: change`
  - `module: app4`
  - `status`
  - `created`
  - `updated`
  - `summary`
- 不再依赖 legacy 状态目录表达工作流状态
- 所有 residual 文件都被明确归类为 source-of-truth doc、operational artifact 或历史残留
- `doc_index.py validate` 对 app4 不再报结构性问题

## Workstreams

### A. Inventory And Classification

目标：先把 app4 现有文档分成稳定类别，避免一边修 metadata 一边改分类导致结果漂移。

责任：
- 盘点 27 篇现有 flat docs
- 对每篇文档判断其应属于：
  - active change doc
  - completed change record
  - draft material that should be demoted or archived
  - operational artifact

交付物：
- 一份 app4 文档清单
- 每篇文档的目标 `status`
- 需要归档或改类的候选列表

完成标准：
- 没有“先改字段、后改定位”的模糊文档
- 每篇文档都被赋予明确的目标角色

### B. Metadata Repair

目标：修复所有 app4 change docs 的 frontmatter，使索引和校验先恢复到可用状态。

责任：
- 为缺少 frontmatter 的文档补齐 YAML frontmatter
- 将已有非标准字段收敛到治理层标准字段
- 为每篇文档设置准确 `status`
- 补齐 `created`、`updated`、`summary`
- 对已完成文档补 `validation`

交付物：
- 27 篇文档的标准化 frontmatter
- `doc_index.py list --type change --module app4 --json` 可稳定输出结构化信息

完成标准：
- 当前 `validate` 中的 26 个 `missing status` 问题全部消失
- 没有 `doc_type`、`module`、`status` 与路径不一致的情况

### C. Legacy Status-Dir Retirement

目标：让 agent 不再把 `docs/03-changes/app4/<status>/` 当成现行写入入口。

责任：
- 确认 legacy 状态目录中是否只剩 `.gitkeep`
- 如果目录已无业务文档，删除空目录或至少补明显说明，禁止继续使用
- 检查 `app4` 相关文档中是否还有把这些目录当标准结构的叙述

交付物：
- 不再承担工作流语义的 legacy 状态目录
- 一份 app4 范围内的 residual legacy path 说明

完成标准：
- agent 不会再从 app4 本地结构中推断“应该把新文档写到 `planned/` 或 `tested/`”
- app4 内不存在仍被当成现行标准的状态目录说明

### D. Reference Cleanup

目标：修正 app4 相关高价值文档里的旧路径或旧状态语义，避免后续 agent 继续走偏。

责任：
- 搜索 `docs/02-modules/`、`docs/04-decisions/`、`docs/05-playbooks/` 中直接引用 app4 legacy path 的内容
- 优先修正高价值引用：
  - 模块文档
  - ADR
  - 复用性 playbook
- 对历史记录性质的旧引用，只需加历史说明，不强行重写叙事

交付物：
- app4 相关高价值 legacy 链接清单
- 已修正引用的变更记录

完成标准：
- 当前仍被 agent 依赖的高价值文档，不再把 app4 legacy 状态目录当成当前标准

### E. Validation And Closure

目标：用固定脚本证明 app4 文档体系已经达到新标准，而不是靠人工主观判断。

责任：
- 运行：
  - `python3 scripts/doc_index.py list --type change --module app4 --json`
  - `python3 scripts/doc_index.py validate`
- 记录 app4 剩余问题与跨模块问题
- 若全仓库仍有其他模块报错，必须把 app4 和非 app4 问题分开报告

交付物：
- 一份 app4 收尾报告
- 最终剩余问题列表

完成标准：
- `validate` 不再报 app4 结构问题
- 报告中明确区分：
  - app4 已解决问题
  - 非 app4 既有问题

## Batch Plan

推荐按以下批次推进，避免一次性大改 27 篇文档导致回归难以定位：

### Batch 1: Baseline Repair

- 补齐 26 篇缺失 `status` 的文档
- 统一最小 frontmatter
- 跑一次 `list` 与 `validate`

目标：
- 先把 app4 从“校验全面报红”恢复到“可继续治理”的状态

### Batch 2: Status Normalization

- 为每篇文档确定正确 `status`
- 把历史报告类文档和实施类文档分开
- 对明显已完成但无验证的文档补 `validation` 或降级状态

目标：
- 消除“名字像 report，状态却仍不明”的混乱状态

### Batch 3: Legacy Cleanup

- 处理空状态目录
- 清理 app4 范围内残余 legacy 叙述
- 确认新文档创建入口只剩 module-flat 路径

目标：
- 从结构上阻断旧习惯复发

### Batch 4: Reference Closure

- 修正高价值引用
- 生成 app4 收尾报告
- 明确 app4 与其他模块的剩余边界

目标：
- 让后续 agent 只读少量文档就能理解 app4 的真实状态

## Agent Constraints For This Plan

- 不允许修改 `docs/00-governance/`，除非另有明确授权
- 不允许把 `app4` 文档重新移入 `planned/`、`implemented/`、`tested/` 等状态目录
- 不允许只提交报告而不做结构修正
- 不允许把 `README.md`、临时输出或执行辅助文件默认为 `change doc`
- 不允许把全仓库 validator 报错都算到 app4 任务未完成

## Done Criteria

只有同时满足以下条件，本计划才可改为 `status: done`：

- app4 所有 source-of-truth change docs 都具备标准 frontmatter
- `python3 scripts/doc_index.py validate` 不再报告 app4 结构问题
- app4 范围内不存在继续指向 legacy 状态目录的高价值当前引用
- legacy 状态目录不再被本地结构或文档暗示为现行入口
- 收尾报告准确区分 app4 问题与其他模块残余问题

## Validation

在每一批次结束后至少运行：

- `python3 scripts/doc_index.py list --type change --module app4 --json`
- `python3 scripts/doc_index.py validate`

如需抽查单篇文档，应补充：

- frontmatter 字段完整性检查
- 路径与 `doc_type` / `module` 一致性检查
- 历史报告类文档的 `status` 与 `validation` 合法性检查
