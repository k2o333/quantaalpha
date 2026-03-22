# Decisions Register

<!-- Append-only. Never edit or remove existing rows.
     To reverse a decision, add a new row that supersedes it.
     Read this file at the start of any planning or research phase. -->

| # | When | Scope | Decision | Choice | Rationale | Revisable? |
|---|------|-------|----------|--------|-----------|------------|
| D001 | 2025-03-22 | init | GSD structure initialized | Created PROJECT.md, STATE.md, REQUIREMENTS.md, DECISIONS.md, KNOWLEDGE.md | Project needs structured milestone tracking | Yes |
| D002 | 初始化 GSD 与现有文档系统集成 | architecture | GSD 与现有 docs 系统并存策略 | 采用 GSD SQLite 状态机 + 现有 docs/ 文档系统并存的混合架构 | 现有 docs/ 系统包含 197 个 Markdown 文件，涵盖治理规则、模块文档、变更记录等丰富内容。GSD 提供结构化状态管理能力。两者互补：GSD 管理需求/决策状态，docs/ 保留详细文档。通过 .gitignore 只保存 GSD 生成的 Markdown，不保存 gsd.db。 | Yes |
| D003 | GSD 初始化后补全项目信息 | architecture | GSD 项目初始化补全 | 通过读取现有 docs/ 系统逆向工程，补全 GSD 项目信息：识别三个模块（app4, quantaalpha, backtest），77个变更文档，3个ADR | GSD 自动检测只识别了 app4 模块。通过读取 docs/02-modules/*.md 和扫描 docs/03-changes/，发现项目实际包含三个核心模块：app4（数据管道）、quantaalpha（因子挖掘）、backtest（策略回测）。已有 77 个变更文档（4个完成，12个进行中/计划中），3个架构决策记录。 | Yes |
