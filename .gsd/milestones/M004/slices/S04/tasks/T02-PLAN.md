# T02: 单元测试

**Slice:** S04
**Milestone:** M004

## Goal
为 `available_from` 和 `join_mode` 推断逻辑编写单元测试，验证字段推断的正确性。

## Must-Haves

### Truths
- 测试覆盖 available_from 推断（mock Parquet earliest date）
- 测试覆盖 join_mode 推断（不同 freq 对应不同模式）
- 测试覆盖 render 输出包含新字段

### Artifacts
- `third_party/quantaalpha/tests/test_data_capability_extensions.py` — 完整测试套件

### Key Links
- 依赖 S04/T01 完成的 data_capability.py 修改

## Steps
1. 创建测试文件，导入相关函数。
2. 使用 `pyfakefs` 或 `unittest.mock` mock 文件系统和 Parquet schema。
3. 编写测试用例:
   - `test_available_from_daily_data`: 日频数据推断
   - `test_available_from_minute_data`: 分钟数据推断
   - `test_join_mode_quarterly`: 季度 → forward_fill
   - `test_join_mode_daily`: 日频 → same_day
   - `test_render_includes_new_fields`: 渲染输出包含新字段
   - `test_join_mode_unknown_freq`: 未知 freq 的默认行为
4. 运行 pytest，确认 6+ 测试通过。

## Context
- 本任务依赖 T01 完成
- 使用 mock 而非真实 Parquet 文件，避免环境依赖
