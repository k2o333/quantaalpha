# T01: 编写正式单元测试案例

**Slice:** S03  
**Milestone:** M002  

## Goal
将修复验证固化到项目持续集成和单元测试中。

## Must-Haves
### Truths
- 全局可通过 `pytest` 等测试框架发现并扫描该测试用例。
- 测试用例名称明显与此次 Bug 及行为相挂钩。

### Artifacts
- 修改或新增包含 test 函数的代码 (`tests/*test*.py`)

## Steps
1. 找到合适的已有测试包或测试文件。
2. 添加 `def test_fix_dict_type_error_in_xxx():` 针对性测试。
3. 手动 `pytest tests/<target>` 确认通过。
