# M002 缺失的切片计划 (S02 & S03)

根据 `.gsd/milestones/M002/M002-ROADMAP.md` 的路线图，M002（QuantaAlpha 数据类型 Bug 修复）切片 S01 已经存在，但缺失了用于实际修复代码和回填测试的 S02 与 S03。以下为补充的 Slice Plans 定稿，供后续实施使用。

---

# S02: 实现类型检查与转换逻辑

**Goal:** 修复 `'dict' object has no attribute 'replace'` 错误，确保 consistency check 阶段能够安全处理任何类型的因子表达式返回值。

**Demo:** M001/M002遗留的导致崩溃的因子输入进入 validator 时，系统不再抛出异常，而是能够自动将 dict 等非规范格式转换为 Series 或 DataFrame，或者优雅降级输出合规的不及格分数。

## Must-Haves
- [ ] 在调用 `.replace()` 前加入防御性的类型检查（`isinstance`）
- [ ] 实现针对 `dict` 结构的回退解析或类型转换逻辑
- [ ] 确保处理未预见的奇异数据类型的兜底容错（如返回 `None` 或直接丢弃并打上失效标签）

## Verification
- [ ] 编写一个 mock 脚本，人为注入 `dict` 类型因子输出进入 `validator.py`
- [ ] 执行一次完整（包含错误因子）的因子生成 Pipeline 不因为此问题中断
- [ ] 输出：修改后的代码 Diff 以及成功跳过/修正错误的执行日志

## Observability / Diagnostics
- Runtime signals: 如果触发了对 `dict` 的数据转换，输出显式的警告日志，如 `[WARN] Factor val returned dict instead of Series/DataFrame, attempting conversion...`
- Inspection surfaces: 可通过 `logger.debug` 追踪转化前后的数据结构（keys, columns）。

## Integration Closure
- Upstream surfaces consumed: S01 提供的精确崩溃点与触发条件
- New wiring introduced: `validator.py` / `consistency.py` 内的数据预处理钩子
- What remains: S03 的回归测试与经验归档

## Tasks

### T01: 编写预检防御与类型守卫逻辑
**Est:** 30m
**Why:** 防止未格式化的数据“裸奔”进入 Pandas/Polars 专属方法的执行流。
**Files:** S01 定位的触发问题的文件（如 `quantaalpha/factors/validator.py` 或 `quantaalpha/factors/consistency.py`）
**Do:** 
1. 在变量调用 `.replace(...)` 之前，加入类型守卫：`if isinstance(factor_val, dict): ...`
2. 根据具体业务逻辑实现转换机制，若字典包含的是股票代码映射则转 Series，若是无效结构则返回 `pd.Series(dtype=float)`。

### T02: 全局验证与管道试错
**Est:** 30m
**Why:** 需要确认修改后，由于类型错误被跳过的因子不会污染下游环节。
**Files:** Pipeline 相关模块
**Do:** 运行因子评估 pipeline 的局部测试功能，人工植入会导致生成 dict 的假说 DSL。

---

# S03: 添加回归测试和文档

**Goal:** 封堵漏洞，确保未来的代码重构或更换底层库时不会再次让 dict 注入到 replace 中；同时将教训沉淀入知识库。

**Demo:** 一个能够稳定抛出 Mock 假数据并跑通断言的 pytest 测试用例；以及在项目 `KNOWLEDGE.md` 中记录下的一笔开发规范教训。

## Must-Haves
- [ ] 在 `tests/` 目录下新增关于 validator 数据类型的专门测试用例
- [ ] 在 M002 Milestone 目录写入 S03 的完成验收总结
- [ ] 更新根目录外的 `KNOWLEDGE.md`

## Verification
- [ ] 运行 `pytest` 看到关于 consistency dict check 的新用例 pass
- [ ] `KNOWLEDGE.md` 被正确 commit 提交记录

## Integration Closure
- Upstream surfaces consumed: S02 具体落地的代码形式
- New wiring introduced: Pytest 回归集合中的新测试套件
- What remains: M002 整体封板完毕（Done) 

## Tasks

### T01: 编写类型约束单元测试
**Est:** 20m
**Why:** 这是软件工程闭环的标准动作，用 TDD/回归的思路彻底杀掉这个 Bug 复发的几率。
**Files:** 类似 `tests/factors/test_validator.py`
**Do:**
构造测试，包含 `def test_validator_with_dict_output()`，断言不再抛出 AttributeError。

### T02: 将类型规范录入 KNOWLEDGE.md
**Est:** 15m
**Why:** 防止其他 Agent 在写新的 `factor_calculator.py` 环节时，忘记转换输入输出。
**Files:** `/home/quan/testdata/aspipe_v4/.gsd/KNOWLEDGE.md`
**Do:**
追加一条教训记录：关于在使用 LLM 生成代码动态算出因子值后，强制清洗类型为 Pandas/Polars DataFrame 的重要性。
