# T01: 添加控制字符转义逻辑
**Slice:** S03  **Milestone:** M001
## Goal
在 JSON fix 逻辑中添加 `_escape_control_chars_in_json` 状态机函数。
## Must-Haves
### Truths
- `grep -n "_escape_control_chars_in_json" client.py` 找到函数定义和调用
### Artifacts
- `third_party/quantaalpha/quantaalpha/llm/client.py` line 1078-1102 已修改
## Steps
1. 实现状态机跟踪 JSON 字符串边界
2. 只转义字符串内部的控制字符，不破坏结构
3. 放在 LaTeX 修复之后、第二次 json.loads 之前
