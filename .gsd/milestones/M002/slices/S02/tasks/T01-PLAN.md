# T01: 实现类型适配防御代码

**Slice:** S02  
**Milestone:** M002  

## Goal
在定位好的出错函数中，判断目标数据是否为字典，如果是，通过安全的解包或提取字段逻辑来避免调用字符串的方法。

## Must-Haves
### Truths
- 使用 `isinstance(data, dict)` 或是泛型鸭子类型判断。
- 未造成对原来 `str` 类型调用的破坏。

### Artifacts
- 新修改的 Python 源代码文件

## Steps
1. 定位到引起 `'dict' object has no attribute 'replace'` 的代码行。
2. 在其上方追加类型检测逻辑。
3. 对于 dict 的处理给出恰当的默认取值（如 `json.dumps` 或者是获取内层指定 key 的字符串值）。
