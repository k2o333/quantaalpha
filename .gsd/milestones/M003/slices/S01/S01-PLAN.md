# S01: 数据能力注入最后一公里

**触发决策**: D014 (ADR-001 数据能力注册表)、D016 (ProviderPool 依赖数据注册表配置验证)

**问题**: `data_capability.py` 空有框架，未能送达 LLM 提示词。`proposal.py` 调用链中从未注入数据能力。

**参考文档**:
- `docs/drafts/factormining/structure/2026-03-22-continuous-mining-plan-supplement.md` 第 3.1 节
- `quantaalpha/factors/data_capability.py`
- `quantaalpha/factors/proposal.py`

---

## 目标

打通 `Data Registry` 与 LLM Context，使大模型每次生成因子时，自动获得可用 Parquet 数据的 Schema 摘要及字段使用契约（防未来函数时滞约束）。

---

## 成功标准

- [ ] `auto_discover_capabilities()` 实现 Parquet 目录自动扫描
- [ ] `render_data_capabilities()` 格式化为 LLM 可读的文本摘要
- [ ] `proposal.py:prepare_context()` 注入 `data_capabilities` 到 context_dict
- [ ] `prompts/prompts.yaml` 增加 `{{ data_capabilities }}` 占位符
- [ ] 因子挖掘时 LLM 生成的因子表达式只使用可用字段
- [ ] 财务数据字段自动带 lag_days 约束提示

---

## 任务拆分

### T01: 实现 auto_discover_capabilities()
**文件**: `quantaalpha/factors/data_capability.py`
**估算**: 4h

```python
def auto_discover_capabilities(
    data_dir: str = "/home/quan/testdata/aspipe_v4/data",
    output_path: str | None = None,
) -> dict[str, dict]:
    """扫描 Parquet 目录，自动生成数据能力注册表"""
    # 1. 遍历 data_dir 下的所有子目录
    # 2. 对每个包含 .parquet 文件的目录，读取第一个文件的 schema
    # 3. 推断频率、时滞、join_mode、pit_field
    # 4. 生成 factor_hints（基于目录名和字段名）
    # 5. 可选：写入 output_path（JSON 格式）
    # 返回：{source_name: capability_dict}
```

**验收**:
- [ ] 能正确扫描 /data/*.parquet 目录
- [ ] 识别财务数据（有 ann_date）和日频数据
- [ ] 推断的 lag_days: 财务数据 45 天，日频 0 天
- [ ] factor_hints 合理（income/balance/cashflow → fundamental/quality/value）

### T02: 修改 proposal.py 注入数据能力
**文件**: `quantaalpha/factors/proposal.py`
**估算**: 2h

修改 `AlphaAgentHypothesisGen.prepare_context()`:
1. 引入 `render_data_capabilities` 和 `get_data_capabilities`
2. 构建 context_dict 时加入 `"data_capabilities": data_capabilities_text`

**验收**:
- [ ] prepare_context 返回值包含 data_capabilities 字段
- [ ] 不破坏现有 context_dict 结构

### T03: 修改 prompts.yaml 增加占位符
**文件**: `quantaalpha/prompts/prompts.yaml`
**估算**: 1h

在 `hypothesis_gen.system_prompt` 模板中增加:
```yaml
{% if data_capabilities %}
## Available Data Dimensions
The following data sources are available for factor construction. 
You MUST only use fields from these sources.
For quarterly financial data, respect the lag_days constraint.
{{ data_capabilities }}
{% endif %}
```

**验收**:
- [ ] prompt 模板语法正确（Jinja2）
- [ ] 渲染后 LLM 能看到数据能力说明

### T04: 手动验证数据能力注入
**估算**: 2h

运行因子挖掘流程，检查:
1. 日志中 `prepare_context` 生成的 prompts
2. LLM 生成的因子表达式是否只使用可用字段
3. 财务数据字段是否有 lag_days 约束

**验收**:
- [ ] 日志显示 data_capabilities 已注入 prompt
- [ ] LLM 不再引用不存在的字段（如误用 balancesheet_vip 不存在字段）
- [ ] 连续运行 5 轮因子挖掘无数据字段错误

---

## 关键代码参考

### 当前 data_capability.py 结构
```python
DATA_CAPABILITIES = {
    "price_volume": {"fields": [...], "freq": "daily", "lag_days": 0},
    "financial": {"fields": [...], "freq": "quarterly", "lag_days": 45},
}  # 目前是硬编码，需要改为动态扫描

def render_data_capabilities() -> str:
    # 现有实现，将 DATA_CAPABILITIES 格式化为文本
```

### proposal.py 调用链
```
AlphaAgentHypothesisGen.generate_hypothesis()
  → prepare_context()  # 需要在这里注入 data_capabilities
    → build_messages_and_create_chat_completion()
```

### prompts.yaml 结构
```yaml
hypothesis_gen:
  system_prompt: | ...
  user_prompt: | ...
  # 需要在这里增加 data_capabilities 占位符
```

---

## 依赖关系

**输入**:
- `/data/*.parquet` 目录结构和文件
- Polars 库已安装

**输出到 S04**:
- `data_capability.py:auto_discover_capabilities()` 实现
- `registry.json` 格式约定（供 ProviderPool 配置验证使用）

---

## 风险缓解

- **风险**: 扫描大量 Parquet 文件耗时过长
  **缓解**: 只在初始化时扫描一次，结果缓存到 registry.json

- **风险**: schema 推断错误（如某些日频数据也有 ann_date 字段）
  **缓解**: 加手动覆盖配置，默认推断+exceptions 机制

---

## 验证命令

```bash
# 语法检查
python -m py_compile quantaalpha/factors/data_capability.py
python -m py_compile quantaalpha/factors/proposal.py

# 数据能力注册表生成测试
python -c "
from quantaalpha.factors.data_capability import auto_discover_capabilities
registry = auto_discover_capabilities()
print('Sources:', list(registry.keys()))
for name, spec in list(registry.items())[:3]:
    print(f'{name}: {len(spec[\"fields\"])} fields, freq={spec[\"freq\"]}, lag={spec[\"lag_days\"]}')
"

# 因子挖掘运行（检查 data_capabilities 注入）
cd third_party/quantaalpha
./run.sh "挖掘日频横截面因子" 2>&1 | grep -A 5 "Available Data"
```
