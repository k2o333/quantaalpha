# T01: 扩展 auto_discover_capabilities() + render_data_capabilities()

**Slice:** S04
**Milestone:** M004

## Goal
扩展数据能力注册表，新增 `available_from`（数据起始日期）和 `join_mode`（same_day / forward_fill）字段，使 LLM 能感知数据的时间范围和 join 方式。

## Must-Haves

### Truths
- `auto_discover_capabilities()` 返回结构包含 `available_from` 和 `join_mode`
- `available_from` 从 Parquet 文件最早日期推断
- `join_mode` 根据 freq 推断: quarterly → forward_fill, daily → same_day
- `render_data_capabilities()` 输出包含新字段

### Artifacts
- `third_party/quantaalpha/quantaalpha/factors/data_capability.py` — 字段扩展

### Key Links
- S04/T02 单元测试依赖本任务完成
- 回测 prompt 注入依赖 render 输出

## Steps
1. 阅读 `data_capability.py`，找到 `auto_discover_capabilities()` 和 `render_data_capabilities()` 函数。
2. 在 `auto_discover_capabilities()` 中添加:
   - 扫描 Parquet 文件时读取最早日期作为 `available_from`
   - 根据 `freq` 推断 `join_mode`
3. 在 `render_data_capabilities()` 模板中添加新字段渲染。
4. 用 `py_compile` 验证语法。
5. `grep "available_from\|join_mode" data_capability.py` 确认 >= 2 处引用。

## Context
- 上游来源: `docs/drafts/mining/factor_mining_requirements.md §E.3.1`
- M003 S01 已实现 data_capability.py 基础注册表
- 本任务不创建测试文件（留给 T02）
