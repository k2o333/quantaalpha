# T02: 单元测试

**Slice:** S02
**Milestone:** M004

## Goal
为 `select_revalidation_candidates()` 方法编写单元测试，覆盖各种筛选场景，验证时间戳更新逻辑。

## Must-Haves

### Truths
- 测试覆盖: 无候选、部分候选、全部候选、不同 status 过滤
- 测试使用 mock 数据，不依赖真实因子库
- 所有测试用例通过后函数逻辑可信赖

### Artifacts
- `third_party/quantaalpha/tests/test_revalidation_candidates.py` — 完整测试套件

### Key Links
- 依赖 S02/T01 已完成的 `library.py` 修改

## Steps
1. 创建测试文件，导入 `select_revalidation_candidates` 和 `FactorLibraryManager`。
2. 使用 `@patch` 或 `MagicMock` mock 因子库数据。
3. 编写测试用例:
   - `test_no_candidates`: 所有因子近期验证过
   - `test_partial_candidates`: 部分因子超时
   - `test_all_candidates`: 所有因子都超时
   - `test_status_filter`: 只返回指定 status 的因子
   - `test_empty_library`: 空因子库
   - `test_last_validated_update`: 验证时间戳在 apply 后更新
4. 运行 pytest，确认 8+ 测试通过。
5. 确保测试覆盖新增的边缘场景。

## Context
- 本任务依赖 T01 完成
- 测试命名遵循 pytest 规范: `test_<function>_<scenario>`
