# S02: 强化 normalize_corrected_expression

**Goal:** 增强 `normalize_corrected_expression` 函数，使其能处理更复杂的脏字符串。
**Demo:** 畸形的 corrected_expression（带注释、伪代码等）能够被成功解析为最终表达式。

## Must-Haves
- 必须能处理 dict payload, fenced blocks, `//` 和 `#` 注释, 多行输出, 变量赋值伪代码。
- 对于赋值语句不能简单地丢弃，需要提取右侧值。

## Tasks

- [ ] **T01: 强化 normalize 函数**
  支持正则表达式或 AST 解析以移除注释、markdown block 和提取最后赋值的右部。

## Files Likely Touched
- `quantaalpha/factors/proposal.py`
- `third_party/quantaalpha/quantaalpha/factors/proposal.py`
