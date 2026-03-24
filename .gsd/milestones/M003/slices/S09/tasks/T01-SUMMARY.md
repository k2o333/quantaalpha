# T01-SUMMARY: 文档化 M001 教训检查清单

**Slice:** S09
**Milestone:** M003
**Date:** 2026-03-23

## 完成情况

- [x] 文档存在且非空 ✅ (213 行)
- [x] 包含所有 4 个 M001 Bug 的详细描述 ✅
- [x] 每个 Bug 有根因、约束位置、验证方法 ✅
- [x] 包含 DC-LOG-001、DC-LLM-001、DC-LOOP-001、DC-JSON-001、DC-TYPE-001 五个设计约束 ✅
- [x] 检查清单汇总表 ✅

## 输出文件

- `docs/constraints/m001_lessons.md`

## 内容覆盖

| Bug | 约束 ID | 描述 |
|-----|---------|------|
| #1 Logger 参数签名 | DC-LOG-001 | 自定义 Logger 必须使用 f-string |
| #2 LLM 空响应崩溃 | DC-LLM-001 | 响应立即检查空值 |
| #3 无限重试死循环 | DC-LOOP-001 | 重试循环必须有上限 |
| #4 JSON 控制字符 | DC-JSON-001 | JSON 解析前处理控制字符 |
| #5 dict AttributeError | DC-TYPE-001 | 字符串操作前做类型检查 |

## 遗留

T02-T04 待执行。
