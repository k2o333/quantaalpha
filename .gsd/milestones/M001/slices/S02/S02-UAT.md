# S02: 修复无限重试死循环和空响应检查 — UAT 测试脚本

## 前置条件
- quantaalpha 代码已更新
- S01 修复已就位

## 测试步骤

1. **确认 while True 已消除**
   ```bash
   grep -n "while True" third_party/quantaalpha/quantaalpha/factors/proposal.py
   ```
   ✅ 预期：无输出

2. **确认 MAX_RETRIES 常量存在**
   ```bash
   grep -n "MAX_RETRIES" third_party/quantaalpha/quantaalpha/factors/proposal.py
   ```
   ✅ 预期：找到常量定义

3. **确认空响应检查存在**
   ```bash
   grep -c "Empty LLM response" third_party/quantaalpha/quantaalpha/llm/client.py
   ```
   ✅ 预期：输出 2（流式 + 非流式）

4. **运行因子挖掘观察重试行为**
   运行因子挖掘，如果遇到空响应，日志应显示重试次数，最终应在 10 次后退出而非卡死。
