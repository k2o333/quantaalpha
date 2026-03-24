# S03: 添加回归测试和文档

**Goal:** 固化修复成果，添加正式测试用例到测试套件中，并在 KNOWLEDGE.md 留下项目记录。
**Demo:** 测试集合 `pytest` 运行通过，不再畏惧因为此数据类型再次改变而导致的隐式回归。

## Must-Haves
- 项目主测试流程里含有专门用于重打此 Bug 的测试点。
- 文档记录。

## Tasks

- [x] **T01: 编写正式单元测试案例**
  将复现代码整合入 `quantaalpha` 或相关项目的单元测试架构内。

- [x] **T02: 更新项目知识库和总结**
  在 `.gsd/KNOWLEDGE.md` 中增加本次 Bug 应对。

## Files Likely Touched
- `tests/` 下的某个关联模块测试文件
- `.gsd/KNOWLEDGE.md`
