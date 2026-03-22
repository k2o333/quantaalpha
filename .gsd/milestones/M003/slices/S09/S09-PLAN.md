# S09: M001 教训设计约束转化

**触发决策**: D019

**问题**: M001 Bug 修复经验需要转化为代码级设计约束，防止在新系统中重现。

**参考文档**:
- `docs/drafts/factormining/structure/2026-03-22-continuous-mining-plan-supplement.md` 第 6 节
- `.gsd/KNOWLEDGE.md` M001 修复经验
- D019: M001 历史故障经验转化为设计约束

---

## 目标

将 M001 教训转化为强制性代码约束：
1. ProviderPool 区分空响应和网络错误
2. Coding 模型 JSON 修复设置超时和重试上限
3. 数据能力注册表类型安全检查
4. Checkpoint 序列化换行符兼容性验证

---

## 成功标准

- [ ] M001 教训检查清单文档化
- [ ] 代码约束写入 S2/S3/S5/S6 实现
- [ ] 回归测试覆盖所有教训
- [ ] 设计约束合规性检查通过

---

## M001 教训检查清单

| 教训 | 约束位置 | 验证测试 |
|------|----------|----------|
| JSON 解析死循环 → 设置超时和重试上限 | S05 T01 | test_json_repair_timeout |
| 空响应无限重试 → 立即切换 Provider | S04 T01 | test_empty_response_switch |
| dict.replace 类型错误 → 类型安全检查 | S01 T01 | 代码审查 + 类型检查 |
| grep 多行匹配 → 换行符兼容性验证 | S06 T05 | test_checkpoint_newlines |

---

## 任务拆分

### T01: 文档化 M001 教训检查清单
**文件**: `docs/constraints/m001_lessons.md` (新建)
**估算**: 1h

内容：
- 每个 Bug 的详细描述
- 约束位置
- 验证方法
- 检查清单

**验收**:
- [ ] 文档化完整
- [ ] 检查清单可执行

### T02: 在 S04/S05/S06 实现中注入约束
**估算**: 2h

- S04 T01: report_failure 区分 empty_response 和 network
- S05 T01: robust_json_parse 设置 timeout=30, max_retries=3
- S06 T05: pickle 测试含换行符字段

**验收**:
- [ ] 约束代码实现
- [ ] 代码审查通过

### T03: 添加回归测试
**估算**: 2h

测试用例：
- test_empty_response_no_cooldown
- test_json_repair_timeout
- test_checkpoint_newline_compatibility

**验收**:
- [ ] 所有测试通过
- [ ] 覆盖 M001 所有教训

### T04: 设计约束合规性检查
**文件**: `.gsd/scripts/check_m001_constraints.py` (新建)
**估算**: 1h

脚本功能：
- 检查 S04 是否有 empty_response 处理
- 检查 S05 是否有 timeout/max_retries
- 检查 S06 是否有换行符测试

**验收**:
- [ ] 脚本可运行
- [ ] 检查结果准确

---

## 依赖

- **S04/S05/S06**: 需要先实现再注入约束
- **D019**: M001 教训转化决策
