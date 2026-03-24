# S03: 修复 JSON 控制字符未转义 — UAT 测试脚本

## 前置条件
- quantaalpha 代码已更新
- S01, S02 修复已就位

## 测试步骤

1. **确认转义函数存在**
   ```bash
   grep -n "_escape_control_chars_in_json" third_party/quantaalpha/quantaalpha/llm/client.py
   ```
   ✅ 预期：找到函数定义和调用（2 处）

2. **语法检查**
   ```bash
   python -m py_compile third_party/quantaalpha/quantaalpha/llm/client.py
   ```
   ✅ 预期：无错误

3. **运行因子挖掘观察 JSON 解析**
   运行因子挖掘，检查日志中：
   - `"Invalid control character"` 错误应消失或大幅减少
   - `"Fixed JSON format issues"` 日志应出现（表示修复逻辑被触发）
