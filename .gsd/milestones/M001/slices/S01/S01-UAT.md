# S01: 修复 Logger 参数签名不匹配 — UAT 测试脚本

## 前置条件
- quantaalpha 代码已更新

## 测试步骤

1. **运行语法检查**
   ```bash
   python -m py_compile third_party/quantaalpha/quantaalpha/llm/client.py
   python -m py_compile third_party/quantaalpha/quantaalpha/backtest/universe.py
   ```
   ✅ 预期：无错误输出

2. **确认无 %s 格式残留**
   ```bash
   grep -n "logger.warning" third_party/quantaalpha/quantaalpha/llm/client.py | grep "%s,"
   grep -n "logger.warning" third_party/quantaalpha/quantaalpha/backtest/universe.py | grep "%s,"
   ```
   ✅ 预期：无输出（0 匹配）

3. **运行因子挖掘观察日志**
   运行一次因子挖掘，检查终端日志中是否还有：
   ```
   TypeError: warning() takes 2 positional arguments but X were given
   ```
   ✅ 预期：无此错误
