# M001: QuantaAlpha 关键 Bug 修复 — 里程碑总结

**完成日期**: 2026-03-22（S01-S03 代码修复完成；S04 验证待执行）

## 里程碑交付

修复了导致因子挖掘工作流卡死的 4 个关键 Bug：

1. **Logger 参数签名不匹配** (S01) — 3 处 `logger.warning()` 调用改为 f-string
2. **无限重试死循环 + 空响应检查** (S02) — `while True` → `for attempt in range(10)`，添加空响应检测
3. **JSON 控制字符未转义** (S03) — 添加 `_escape_control_chars_in_json` 状态机

## 关键修改文件

| 文件 | 切片 | 修改摘要 |
|------|------|----------|
| `llm/client.py` | S01/S02/S03 | f-string 日志、空响应检查、控制字符转义 |
| `backtest/universe.py` | S01 | f-string 日志 |
| `factors/proposal.py` | S02 | 有限重试循环 |

## 关键决策

- D006: GSD 里程碑结构
- D007: 文档修正（工程师审查）
- D008: S01-S03 标记完成
- D009: 创建 KNOWLEDGE.md

## 遗留

- S04：运行因子挖掘验证修复效果（当前活跃切片）
- Bug #5 `'dict' object has no attribute 'replace'` → M002

## 切片详情

| 切片 | 状态 | 摘要 |
|------|------|------|
| S01 | ✅ 完成 | Logger f-string 修复 |
| S02 | ✅ 完成 | 有限重试 + 空响应检测 |
| S03 | ✅ 完成 | JSON 控制字符转义 |
| S04 | 🔄 Planning | 运行验证修复效果 |
