# S01: 定位数据类型 Bug 触发位置

**Goal:** 找到触发 `'dict' object has no attribute 'replace'` 的确切代码位置和数据流向

**Demo:** 能够指出具体文件和行号，并解释 dict 是从哪个函数/表达式传入的

## Must-Haves

- [ ] 定位到触发 `.replace()` 调用的准确位置
- [ ] 追溯 dict 类型数据的来源（哪个变量、哪个函数返回）
- [ ] 记录触发此错误的条件和上下文
- [ ] 编写最小复现步骤

## Verification

- [ ] 代码搜索确认 `.replace()` 在因子相关文件中的调用位置
- [ ] 日志分析对齐错误堆栈与实际代码
- [ ] 输出：触发位置 + dict 来源分析文档

## Observability / Diagnostics

- Runtime signals: 错误堆栈包含文件名和行号
- Inspection surfaces: 代码搜索结果、变量类型追踪
- Failure visibility: 如果能复现，确认是 dict 而非预期 DataFrame/Series

## Integration Closure

- Upstream surfaces consumed: M001 修复经验、现有日志文件
- New wiring introduced: 无（纯分析任务）
- What remains: S02 的类型检查和转换实现

## Tasks

### T01: 搜索 .replace() 的调用位置

**Est:** 15m

**Why:** 需要找到代码中所有调用 `.replace()` 的位置，缩小排查范围

**Files:** 主要搜索 `third_party/quantaalpha/` 下的 factors 模块

**Do:**
```bash
# 搜索所有 .replace() 调用
grep -rn "\.replace(" third_party/quantaalpha/quantaalpha/factors/ --include="*.py"

# 重点关注返回类型可能是 dict 的地方
```

**Verify:** 输出调用位置列表

**Done when:** 列出所有相关 .replace() 调用的文件和行号

---

### T02: 分析一致性检查代码流程

**Est:** 20m

**Why:** consistency check 阶段会处理因子表达式结果，需要理解数据流向

**Files:** 
- `third_party/quantaalpha/quantaalpha/factors/consistency.py`
- `third_party/quantaalpha/quantaalpha/factors/validator.py`

**Do:**
1. 阅读 consistency.py 的主流程
2. 标记所有涉及数据转换/验证的函数
3. 关注从因子表达式到 validation 的数据流转

**Verify:** 输出数据流转图，标记可能的类型转换点

**Done when:** 理解 dict 类型如何进入 validation 流程

---

### T03: 对齐日志与代码定位

**Est:** 15m

**Why:** 终端日志 `20260321_214610.txt` 中的错误堆栈能精确定位问题

**Files:** `third_party/facotors/terminal/20260321_214610.txt`

**Do:**
1. 读取日志中的错误堆栈
2. 找到最靠近 `.replace()` 调用的代码位置
3. 标记触发函数和调用链

**Verify:** 能从日志中精确定位文件和行号

**Done when:** 记录触发位置和调用链

---

### T04: 分析 LLM 因子表达式返回类型

**Est:** 15m

**Why:** 需要确认 dict 是否来自 LLM 生成的因子表达式执行结果

**Files:**
- `third_party/quantaalpha/quantaalpha/factors/proposal.py`
- M001 中提到的 consistency check 相关代码

**Do:**
1. 检查因子表达式执行后的返回值类型
2. 确认是否某些条件下会返回 dict 而非 Series
3. 对比正常情况和异常情况的数据差异

**Verify:** 确认 dict 的可能来源

**Done when:** 记录 dict 来源的假设和验证方法

---

## Files Likely Touched

无（本切片为纯分析任务，不修改代码）

分析目标文件：
- `third_party/quantaalpha/quantaalpha/factors/consistency.py`
- `third_party/quantaalpha/quantaalpha/factors/validator.py`
- `third_party/quantaalpha/quantaalpha/factors/proposal.py`

## Notes

- 保持与 M001 相同的代码风格
- 如果定位困难，可以尝试在本地复现一遍错误流程
- 任务 T03 依赖于日志文件内容，如果无法获取堆栈，需要调整策略
