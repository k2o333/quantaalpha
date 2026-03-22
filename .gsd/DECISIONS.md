# Decisions Register

<!-- Append-only. Never edit or remove existing rows.
     To reverse a decision, add a new row that supersedes it.
     Read this file at the start of any planning or research phase. -->

| # | When | Scope | Decision | Choice | Rationale | Revisable? |
|---|------|-------|----------|--------|-----------|------------|
| D001 | 2025-03-22 | init | GSD structure initialized | Created PROJECT.md, STATE.md, REQUIREMENTS.md, DECISIONS.md, KNOWLEDGE.md | Project needs structured milestone tracking | Yes |
| D002 | 初始化 GSD 与现有文档系统集成 | architecture | GSD 与现有 docs 系统并存策略 | 采用 GSD SQLite 状态机 + 现有 docs/ 文档系统并存的混合架构 | 现有 docs/ 系统包含 197 个 Markdown 文件，涵盖治理规则、模块文档、变更记录等丰富内容。GSD 提供结构化状态管理能力。两者互补：GSD 管理需求/决策状态，docs/ 保留详细文档。通过 .gitignore 只保存 GSD 生成的 Markdown，不保存 gsd.db。 | Yes |
| D003 | GSD 初始化后补全项目信息 | architecture | GSD 项目初始化补全 | 通过读取现有 docs/ 系统逆向工程，补全 GSD 项目信息：识别三个模块（app4, quantaalpha, backtest），77个变更文档，3个ADR | GSD 自动检测只识别了 app4 模块。通过读取 docs/02-modules/*.md 和扫描 docs/03-changes/，发现项目实际包含三个核心模块：app4（数据管道）、quantaalpha（因子挖掘）、backtest（策略回测）。已有 77 个变更文档（4个完成，12个进行中/计划中），3个架构决策记录。 | Yes |
| D004 | 评估 ADR-003 完成度，决定模块边界设计 | architecture | ADR-003 外插模块边界与职责分离 | ADR-003 保持 draft 状态，待评估后决定接受、修改或拒绝 | ADR-003 定义了 quantaalpha 主链与外插模块（orchestrator、trigger、observability、test harness、registry）的边界。当前状态为 draft，需要评估：1) 模块边界是否清晰；2) 集成契约是否可行；3) 分阶段落地计划是否合理。此决策影响 24 小时连续运行系统的架构。 | Yes |
| D005 | 评估 ADR-001 完成度，决定架构方向 | architecture | ADR-001 持续因子研究系统演进架构方向 | ADR-001 保持 draft 状态，待评估后决定接受、修改或拒绝 | ADR-001 定义了多模型研究、多周期验证、因子知识库、数据能力注册表、持续运转调度五层架构。当前状态为 draft，需要评估：1) 哪些组件已部分实现；2) 哪些需要调整；3) 是否接受此架构方向。此决策影响 quantaalpha 模块的长期演进。 | Yes |
| D006 | M001 | process | QuantaAlpha Bug 修复里程碑存储位置 | 使用 GSD 标准里程碑目录结构存储修复计划 | 根据 GSD 规范，修复计划作为里程碑 M001 管理，文档存放在 .gsd/milestones/M001/ 下。包含 M001-CONTEXT.md（问题描述）、M001-ROADMAP.md（路线图）、slices/S01/S01-PLAN.md（切片计划）。 | Yes |
| D007 | M001 文档修正 | process | M001 文档修正内容 | 更新 M001 文档以反映工程师审查意见 | 根据4位工程师的审查报告，对 M001 文档进行了以下关键修正：1) 明确说明"4个高优先级Bug"而非"全部问题"，补充第5个Bug（'dict' object has no attribute 'replace'）将在M002处理；2) Bug 3 阶段改为 factor_construct（不是 proposal）；3) Bug 1 收缩范围为 client.py:69-74（主要触发点），client.py:667 和 universe.py:111 标注为"同类隐患"；4) 空响应检查移至 S02，与无限重试修复合并；5) 修正 S03 预期日志消息为 "Fixed JSON format issues"（与实际代码一致）；6) 修正 grep 验证命令，避免多行匹配问题。 | Yes |
