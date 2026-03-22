# S05: Coding 模型 JSON 修复闭环

**触发决策**: D019 (M001 教训转化)、S04 ProviderPool

**问题**: 当前 `client.py` 的 `robust_json_parse()` 有 4 层规则修复，但 JSON 修复失败后直接抛出异常。

**参考文档**:
- `docs/drafts/factormining/structure/2026-03-22-continuous-mining-plan-supplement.md` 第 3.3 节
- `quantaalpha/llm/client.py`
- D019 设计约束

---

## 目标

实现 Coding 模型 JSON 修复闭环：
1. 规则修复失败后触发 coding 模型修复
2. 设置超时和重试上限（D019 约束）
3. 集成 ProviderPool 的 json_repair 路由

---

## 成功标准

- [ ] `robust_json_parse()` 策略 5 实现
- [ ] coding 模型修复设置 30 秒超时
- [ ] 重试次数 ≤ 3 次（D019 约束）
- [ ] 空响应立即切换 Provider（D019 约束）
- [ ] ProviderPool 的 get_backend("json_repair") 可用
- [ ] JSON 修复成功率提升

---

## 设计约束（来自 D019）

**必须遵守的 M001 教训**：
1. **超时**: coding 模型修复必须设置 30 秒超时
2. **重试上限**: 最多 3 次重试
3. **空响应处理**: 空响应立即切换 Provider

---

## 任务拆分

### T01: 修改 robust_json_parse() 增加策略 5
**文件**: `quantaalpha/llm/client.py`
**估算**: 3h

在现有策略 1-4 之后增加策略 5：coding 模型修复。

**验收**:
- [ ] 策略 5 在规则修复失败后触发
- [ ] 使用 provider_pool.get_backend("json_repair")
- [ ] 30 秒超时设置
- [ ] 最多 3 次重试
- [ ] 空响应立即切换 Provider

### T02: 添加单元测试
**文件**: `tests/llm/test_json_repair.py` (新建)
**估算**: 2h

测试：
1. 正常 JSON 修复
2. 超时触发
3. 重试上限
4. 空响应切换

**验收**:
- [ ] 所有测试通过
- [ ] D019 约束验证

---

## 依赖

- **S04**: ProviderPool 必须实现 get_backend("json_repair")
- **D019**: M001 教训转化为代码约束
