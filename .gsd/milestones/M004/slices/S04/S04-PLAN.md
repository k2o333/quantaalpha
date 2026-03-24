# S04: 数据能力注册表扩展

**Goal:** 扩展 S01 数据能力注册表，新增 `available_from`（数据起始日期）和 `join_mode`（same_day / forward_fill）字段。
**Demo:** LLM prompt 中注入的数据能力描述包含数据起始日期和 join 模式信息。

## Must-Haves
- `auto_discover_capabilities()` 返回结构新增 `available_from` 字段（从 Parquet 文件最早日期推断）
- `auto_discover_capabilities()` 返回结构新增 `join_mode` 字段（根据 freq 推断: quarterly → forward_fill, daily → same_day）
- `render_data_capabilities()` 输出中包含 available_from 和 join_mode
- 单元测试覆盖字段推断逻辑

## Proof Level
- This slice proves: **contract**
- Real runtime required: no (mock Parquet schema)
- Human/UAT required: no

## Verification
- `python -m py_compile quantaalpha/factors/data_capability.py`
- `pytest quantaalpha/tests/test_data_capability_extensions.py -v`
- `grep "available_from\|join_mode" quantaalpha/factors/data_capability.py` returns >= 2

## Tasks

- [x] **T01: 扩展 auto_discover_capabilities() + render_data_capabilities()** `est:25m`
  - Why: 字段推断和渲染是核心交付物
  - Files: `quantaalpha/factors/data_capability.py`
  - Do: 在扫描逻辑中推断 available_from（读取 Parquet 首行日期）和 join_mode（根据 freq 推断）；在渲染模板中添加新字段
  - Verify: py_compile 通过, grep 字段名
  - Done when: 新字段在注册表和渲染输出中可见

- [x] **T02: 单元测试** `est:15m`
  - Why: 验证推断逻辑正确性
  - Files: `quantaalpha/tests/test_data_capability_extensions.py`
  - Do: Mock Parquet schema 测试 available_from 推断和 join_mode 推断
  - Verify: pytest 通过
  - Done when: 6+ 测试通过

## Files Likely Touched
- `quantaalpha/factors/data_capability.py` (modify)
- `quantaalpha/tests/test_data_capability_extensions.py` (new)

---
estimated_steps: 6
estimated_files: 2
