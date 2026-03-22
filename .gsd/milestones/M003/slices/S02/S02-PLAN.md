# S02: 因子库 Few-shot 导出与智能采样

**触发决策**: D014 (ADR-001 因子知识库)

**问题**: library.py 已有基础能力，但缺少将 Active 因子导出为 LLM few-shot 示例的接口，无法让历史优良因子指导新因子生成。

**参考文档**:
- `docs/drafts/factormining/structure/2026-03-22-continuous-mining-plan-supplement.md` 第 3.4 节
- `quantaalpha/factors/library.py`

---

## 目标

实现因子库 Few-shot 导出功能，支持：
1. 按相关度智能采样 Active 因子
2. 控制 token 预算（默认 2000 tokens）
3. 导出为 LLM prompt 可读格式

---

## 成功标准

- [ ] `export_few_shot_examples()` 方法实现
- [ ] 支持按方向关键词匹配相关度
- [ ] 稳定性分数过滤（默认 min_stability=0.5）
- [ ] Token 预算控制（默认 max_token_budget=2000）
- [ ] 排除指定 factor_id（避免重复）
- [ ] proposal.py 成功注入 few_shot_examples
- [ ] prompt 模板包含 few_shot_examples 占位符

---

## 任务拆分

### T01: 实现 export_few_shot_examples()
**文件**: `quantaalpha/factors/library.py`
**估算**: 3h

```python
def export_few_shot_examples(
    self,
    direction: str | None = None,
    max_examples: int = 3,
    min_stability: float = 0.5,
    max_token_budget: int = 2000,
    exclude_factor_ids: set[str] | None = None,
) -> str:
    """导出 Active 因子作为 LLM 的 few-shot 示例"""
    # 1. 筛选 Active 状态且 stability >= min_stability 的因子
    # 2. 如有 direction，计算相关度（关键词重叠）
    # 3. 按 (相关度, 稳定性) 排序
    # 4. 在 token_budget 范围内选取 top-N
    # 5. 格式化输出为 Markdown 格式
```

**验收**:
- [ ] 只返回 Active 状态的因子
- [ ] stability 过滤正确
- [ ] direction 关键词匹配实现
- [ ] token 预算控制生效

### T02: 实现 _format_factor_example()
**文件**: `quantaalpha/factors/library.py`
**估算**: 1h

```python
def _format_factor_example(entry: dict) -> str:
    """格式化单个因子为 few-shot 示例"""
    # 格式：
    # **FactorName**
    # - Expression: `$roe + $pe_ratio`
    # - Description: 盈利能力与估值综合因子
    # - Metrics: IC=0.05, Rank IC=0.08, Stability=0.75
```

**验收**:
- [ ] 输出格式规范
- [ ] 包含关键字段：name, expression, description, metrics

### T03: 修改 proposal.py 注入 few-shot
**文件**: `quantaalpha/factors/proposal.py`
**估算**: 2h

修改 `prepare_context()`:
```python
try:
    from quantaalpha.factors.library import FactorLibraryManager
    manager = FactorLibraryManager(str(library_path))
    few_shot_text = manager.export_few_shot_examples(
        direction=self.potential_direction,
        max_examples=3,
        min_stability=0.5,
    )
except Exception:
    few_shot_text = ""

context_dict["few_shot_examples"] = few_shot_text
```

**验收**:
- [ ] prepare_context 返回值包含 few_shot_examples
- [ ] 因子库不存在时优雅降级

### T04: 修改 prompts.yaml 增加占位符
**文件**: `quantaalpha/prompts/prompts.yaml`
**估算**: 1h

```yaml
hypothesis_gen:
  system_prompt: |
    ...
    {% if few_shot_examples %}
    ## Reference: Active High-Quality Factors
    These factors have proven stable across multiple market periods.
    {{ few_shot_examples }}
    {% endif %}
```

**验收**:
- [ ] 模板语法正确
- [ ] few_shot_examples 成功注入 prompt

---

## 验证

```python
# 单元测试
from quantaalpha.factors.library import FactorLibraryManager

manager = FactorLibraryManager("/path/to/library")
text = manager.export_few_shot_examples(
    direction="fundamental value",
    max_examples=3,
    min_stability=0.6,
)
print(text)
# 应输出格式化的 few-shot 示例
```
