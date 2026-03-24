# T01: 添加 last_validated 字段 + select_revalidation_candidates 方法

**Slice:** S02
**Milestone:** M004

## Goal
在 FactorLibraryManager 中添加 `last_validated` 时间戳字段和 `select_revalidation_candidates()` 筛选方法，使系统能够自动选出超过指定天数未验证的因子。

## Must-Haves

### Truths
- 因子条目在 `_normalize_factor_entry()` 中初始化 `last_validated` 为当前时间
- `select_revalidation_candidates(days, status)` 返回符合条件（超时 + 指定状态）的因子列表
- `apply_validation_result()` 调用时自动更新对应因子的 `last_validated`

### Artifacts
- `third_party/quantaalpha/quantaalpha/factors/library.py` — 字段和方法实现

### Key Links
- S02/T02 单元测试依赖本任务完成
- S05 状态机依赖 `last_validated` 字段

## Steps
1. 阅读 `library.py`，找到 `_normalize_factor_entry()` 方法位置。
2. 添加 `last_validated: datetime = field(default_factory=datetime.now)` 字段。
3. 实现 `select_revalidation_candidates(days: int, status: str = "active") -> List[dict]` 方法。
4. 在 `apply_validation_result()` 中添加 `entry.last_validated = datetime.now()` 更新逻辑。
5. 用 `py_compile` 验证语法。

## Context
- 上游来源: `docs/drafts/mining/factor_mining_requirements.md §C.3.2`
- M003 S06 已实现 `versions` 字段和 `apply_validation_result()` 方法
- 本任务不创建测试文件（测试在 T02）
