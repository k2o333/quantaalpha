# M002: QuantaAlpha 数据类型 Bug 修复

**触发原因**: 因子挖掘时在 `consistency check` 阶段出现 `'dict' object has no attribute 'replace'` 错误

**问题来源**: `docs/drafts/factormining/bug/` 下的 Bug #5 分析报告，在 M001 中推迟处理

**日志来源**: `third_party/facotors/terminal/20260321_214610.txt`

---

## 核心问题

系统在**因子一致性检查**阶段因数据类型不匹配导致代码崩溃。

### Bug 5: consistency check 数据类型问题

**位置**: `quantaalpha/factors/validator.py` 或 `consistency.py`（待确认）

**问题**: 
- 代码期望的数据类型（DataFrame/Series）接收到字典类型
- 调用 `.replace()` 方法时触发 `AttributeError`
- 可能原因：
  1. LLM 返回的因子表达式在某些数据条件下返回字典而非 Series
  2. 数据过滤/转换逻辑未正确处理边界情况

**错误日志**:
```python
'dict' object has no attribute 'replace'
```

**影响**: 
- consistency check 无法完成，影响因子质量评估
- 导致部分因子无法进入回测阶段

---

## 修复优先级

1. **确认触发位置** - 找到具体调用 `.replace()` 的位置
2. **分析数据流向** - 追溯 dict 类型的来源
3. **添加类型检查** - 在进入 replace 前验证并转换数据类型

---

## 成功标准

- [ ] 定位到触发 `'dict' object has no attribute 'replace'` 的确切代码位置
- [ ] 理解并记录 dict 类型数据的来源和原因
- [ ] 添加防御性代码，在进入 .replace() 前进行类型检查/转换
- [ ] consistency check 能够正常处理 dict 类型的返回值
- [ ] 运行因子挖掘流程时不再出现此错误

---

## 关键风险

- **数据类型复杂性** — quantaalpha 使用多种数据类型（Polars DataFrame、Pandas Series、dict），需要仔细分析
- **LLM 输出不确定性** — 因子表达式返回值类型可能因输入数据而变化
- **测试覆盖** — 需要构造能触发 dict 返回值的测试用例

---

## 现有代码/参考

- **M001 修复位置**: `third_party/quantaalpha/quantaalpha/factors/`
- **相关模块**: 
  - `validator.py` - 一致性检查验证器
  - `consistency.py` - consistency check 实现
  - `proposal.py` - 因子提案（可能与数据转换相关）
- **日志位置**: `third_party/facotors/terminal/`
