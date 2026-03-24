# S04: 运行因子挖掘验证修复效果 — UAT 测试脚本

## 前置条件
- M001 S01, S02, S03 的修复代码已就绪
- 已运行环境准备脚本，具有可用的测试环境

## 测试步骤

1. **环境连通性检查**
   ```bash
   # 测试 LLM api 连通性和依赖
   cd third_party/quantaalpha
   python -c "from quantaalpha.llm.client import APIBackend; print('LLM Client OK')"
   ```
   ✅ 预期：正常输出，无模块找不到错误

2. **完整因子挖掘全流程运行**
   ```bash
   cd third_party/quantaalpha
   ./run.sh "挖掘日频横截面因子，基于量价数据"
   ```
   ✅ 预期：
   - 不再出现 `TypeError: warning() takes 2 positional arguments`
   - 不再出现包含 `while True` 导致的无限挂起（卡死在 proposal 阶段）
   - 日志中如有解析错误能在重试（MAX_RETRIES=10）内自我恢复或抛出明确错误退出
   - 看到成功生成因子的输出，并且能够完成全流程走到最终评测（不包括 M002 dict 错误）

3. **异常处理覆盖验证**
   手动在 `quantaalpha/llm/client.py` 制造一个短暂的网络异常（或者使用断网测试），观察流式响应的处理。
   ✅ 预期：进入指定的重试和 fallback 逻辑，记录适当日志而非静默挂起。
