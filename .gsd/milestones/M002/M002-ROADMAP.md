# M002: QuantaAlpha 数据类型 Bug 修复

**Vision:** 修复 consistency check 阶段的数据类型错误，确保因子验证流程稳定运行

## Success Criteria

- [ ] 定位到触发 `'dict' object has no attribute 'replace'` 的确切代码位置
- [ ] 添加类型检查/转换逻辑处理 dict 类型数据
- [ ] consistency check 能够正常完成不崩溃
- [ ] 运行因子挖掘流程时不再出现此错误

## Key Risks / Unknowns

- **多数据源类型** — quantaalpha 同时使用 Polars、Pandas 和原生 dict，类型边界模糊
- **LLM 输出不可预测** — 生成的因子表达式返回值类型可能变化
- **触发条件不明确** — 仅在特定数据条件下触发，需要复现

## Proof Strategy

- 通过日志追溯和代码审查定位问题位置 → retire in S01
- 构造最小复现用例确认触发条件 → retire in S01
- 实现类型检查/转换并验证修复 → retire in S02

## Verification Classes

- Contract verification: Python 语法检查、单元测试
- Integration verification: 运行因子挖掘流程验证
- Operational verification: 监控 consistency check 日志
- UAT / human verification: 检查修复后的代码逻辑

## Milestone Definition of Done

- [ ] 触发位置已定位并记录
- [ ] 类型检查逻辑已添加并通过测试
- [ ] 因子挖掘流程可完整运行不崩溃
- [ ] 修复文档已记录到 KNOWLEDGE.md
- [ ] 新增回归测试防止后续引入类似问题

## Requirement Coverage

- Covers: 因子挖掘数据处理的健壮性
- Partially covers: 类型安全
- Leaves for later: 上游 LLM prompt 优化
- Orphan risks: 其他隐式类型转换问题

## Slices

- [ ] **S01: 定位数据类型 Bug 触发位置** `risk:high` `depends:[]`
  > After this: 明确知道哪行代码触发错误，理解数据流向

- [ ] **S02: 实现类型检查与转换逻辑** `risk:medium` `depends:[S01]`
  > After this: consistency check 能正确处理 dict 类型，不再崩溃

- [ ] **S03: 添加回归测试和文档** `risk:low` `depends:[S02]`
  > After this: 有测试保护，修复记录在 KNOWLEDGE.md

## Boundary Map

### S01 → S02
Produces:
- 触发错误的精确代码位置（文件:行号）
- dict 类型数据来源分析（哪个函数返回的）
- 触发条件的最小复现步骤

Consumes:
- 来自终端日志的错误信息
- M001 修复经验中的代码搜索模式

### S02 → S03
Produces:
- 类型检查/防御性代码实现
- 修复通过单元测试的证据

Consumes:
- S01 提供的触发位置和原因分析
