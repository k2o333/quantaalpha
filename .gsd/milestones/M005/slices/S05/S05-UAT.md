# S05 UAT: 移除 proposal.yaml prompt 配置歧义

**Milestone:** M005
**Date:** 2026-03-24
**Executor:** Closer

## Preconditions

- 工作目录: `/home/quan/testdata/aspipe_v4/.gsd/worktrees/M005`
- Python 环境可用
- `ripgrep` (rg) 可用

## Test Cases

### TC01: 验证死赋值已删除

**Purpose:** 确认 `proposal.py` 中仅剩一个 `qa_prompt_dict` 赋值

**Steps:**
1. 运行 `rg -n "qa_prompt_dict = Prompts" quantaalpha/factors/proposal.py`
2. 计数输出行数

**Expected:**
- 仅 1 行输出（指向 `prompts.yaml`）
- 行号应为 304（删除原第 159 行后行号调整）
- 内容应为 `qa_prompt_dict = Prompts(file_path=Path(__file__).parent / "prompts" / "prompts.yaml")`

**Pass Criteria:** 输出行数 == 1 且指向 `prompts.yaml`

---

### TC02: 验证 proposal.yaml 已归档

**Purpose:** 确认原始 `proposal.yaml` 不再存在于运行时路径

**Steps:**
1. 运行 `ls quantaalpha/factors/prompts/proposal.yaml`
2. 检查退出码

**Expected:**
- 命令失败（退出码非 0）
- 错误信息包含 "No such file or directory"

**Pass Criteria:** 文件不存在

---

### TC03: 验证 proposal.yaml.archived 存在

**Purpose:** 确认废弃配置文件已归档而非删除

**Steps:**
1. 运行 `ls -la quantaalpha/factors/prompts/proposal.yaml.archived`
2. 检查文件大小 > 0

**Expected:**
- 文件存在
- 文件大小 > 0
- 文件可读

**Pass Criteria:** 文件存在且非空

---

### TC04: 验证 proposal.py 语法正确

**Purpose:** 确认删除操作未引入语法错误

**Steps:**
1. 运行 `python -m py_compile quantaalpha/factors/proposal.py`
2. 检查退出码

**Expected:**
- 退出码 0
- 无错误输出

**Pass Criteria:** 编译成功，退出码 0

---

### TC05: 验证 remaining 赋值指向正确配置文件

**Purpose:** 确认唯一的 `qa_prompt_dict` 赋值指向 `prompts.yaml`

**Steps:**
1. 运行 `rg "qa_prompt_dict = Prompts" quantaalpha/factors/proposal.py`
2. 检查输出包含 `prompts.yaml`

**Expected:**
- 输出行包含 `"prompts.yaml"`
- 不包含 `proposal.yaml`

**Pass Criteria:** 赋值指向 `prompts.yaml`

---

### TC06: 验证无其他文件引用 proposal.yaml（非 archived）

**Purpose:** 确认无其他运行时代码引用废弃的 `proposal.yaml`

**Steps:**
1. 运行 `rg "proposal\.yaml" quantaalpha/factors/ --glob "!*.archived"`
2. 检查输出

**Expected:**
- 无输出（无匹配）
- 或仅有注释中的历史引用

**Pass Criteria:** 无运行时代码引用 `proposal.yaml`

---

## Edge Cases

### EC01: 确认 archived 文件不影响运行时

**Purpose:** 归档文件不应被 Python 导入系统加载

**Steps:**
1. 检查 `quantaalpha/factors/prompts/__init__.py` 是否导入 `proposal.yaml`
2. 或确认无此类文件

**Expected:**
- prompts 包不主动加载 `proposal.yaml`

**Pass Criteria:** 无导入语句引用 `proposal.yaml`

---

### EC02: 验证 proposal.py 中其他 Prompts 引用

**Purpose:** 确认其他 Prompts 引用未受影响

**Steps:**
1. 运行 `rg "Prompts\(" quantaalpha/factors/proposal.py`
2. 确认均为有效配置

**Expected:**
- 所有 Prompts 调用指向 `prompts.yaml` 或其他有效配置文件

**Pass Criteria:** 所有 Prompts 调用有效

---

## Verification Summary

| Test Case | Status | Notes |
|-----------|--------|-------|
| TC01: 死赋值删除 | ✅ | 仅剩 1 行指向 prompts.yaml |
| TC02: proposal.yaml 不存在 | ✅ | 已归档 |
| TC03: archived 存在 | ✅ | 文件非空 |
| TC04: 语法检查 | ✅ | 编译成功 |
| TC05: 赋值指向正确 | ✅ | prompts.yaml |
| TC06: 无其他引用 | ✅ | 无运行时引用 |
| EC01: archived 不加载 | ✅ | 无导入语句 |
| EC02: 其他引用有效 | ✅ | 无回归 |

**Result:** 8/8 PASSED

---

## Failure Signals

如果以下检查失败，说明实现有问题：
- `rg` 返回行数 > 1 → 死赋值未删除
- `proposal.yaml` 仍存在 → 未正确归档
- `py_compile` 失败 → 语法错误
- 任何 Prompts 调用指向 `proposal.yaml` → 配置歧义未消除

---

## Rollback Procedure

如需回滚，执行：
```bash
mv quantaalpha/factors/prompts/proposal.yaml.archived quantaalpha/factors/prompts/proposal.yaml
# 重新添加第 159 行的死赋值（需要从 git 历史恢复）
```
