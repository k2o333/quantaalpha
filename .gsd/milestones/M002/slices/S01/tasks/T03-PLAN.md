# T03: 创建最小复现测试脚本

**Slice:** S01 — 定位数据类型 Bug 触发位置
**Milestone:** M002

## Description

创建可执行的最小复现测试脚本，验证 dict 类型触发 `'dict' object has no attribute 'replace'` 错误的条件。

## Steps

1. **创建测试目录和文件**
   - 确保 `test/` 目录存在
   - 创建 `test/test_dict_replace_bug.py`

2. **编写复现脚本**
   ```python
   """
   测试脚本：复现 'dict' object has no attribute 'replace' Bug
   
   Bug 位置：consistency_checker.py:265 in ComplexityChecker.check()
   触发条件：expression 参数是 dict 类型而非 string
   """
   import sys
   import os
   
   # 添加 quantaalpha 路径
   sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'third_party', 'quantaalpha'))
   
   def test_dict_replace_bug():
       """测试 dict 类型触发 replace 错误"""
       from quantaalpha.factors.regulator.consistency_checker import ComplexityChecker
       
       checker = ComplexityChecker(enabled=True)
       
       # 模拟 LLM 返回 dict 类型的 corrected_expression
       dict_expression = {"code": "some_expression", "note": "from LLM"}
       
       try:
           checker.check(dict_expression)
           print("FAIL: Should have raised AttributeError")
           return False
       except AttributeError as e:
           if "'dict' object has no attribute 'replace'" in str(e):
               print(f"SUCCESS: Bug reproduced - {e}")
               return True
           else:
               print(f"FAIL: Unexpected AttributeError - {e}")
               return False
       except Exception as e:
           print(f"FAIL: Unexpected exception - {type(e).__name__}: {e}")
           return False
   
   def test_normalize_function():
       """测试 normalize_corrected_expression 函数"""
       from quantaalpha.factors.proposal import normalize_corrected_expression
       
       # 测试 dict 输入
       dict_input = {"code": "some_expression"}
       result = normalize_corrected_expression(dict_input)
       print(f"normalize_corrected_expression(dict) = {result}")
       assert isinstance(result, str), "Should return string"
       
       # 测试 string 输入
       str_input = "normal_expression"
       result = normalize_corrected_expression(str_input)
       print(f"normalize_corrected_expression(str) = {result}")
       assert result == str_input, "Should pass through unchanged"
       
       return True
   
   if __name__ == "__main__":
       print("=" * 60)
       print("Testing dict.replace() bug reproduction")
       print("=" * 60)
       
       test1 = test_dict_replace_bug()
       print()
       test2 = test_normalize_function()
       print()
       
       print("=" * 60)
       if test1 and test2:
           print("All tests passed!")
           sys.exit(0)
       else:
           print("Some tests failed!")
           sys.exit(1)
   ```

3. **运行测试验证复现**
   - 确保 quantaalpha submodule 已正确初始化
   - 运行 `python test/test_dict_replace_bug.py`
   - 确认输出包含 "SUCCESS: Bug reproduced"

4. **检查测试是否需要 quantaalpha submodule**
   - 如果 submodule 未初始化，测试将失败
   - 这是预期的，因为复现需要实际代码

## Must-Haves

- [ ] 创建 `test/test_dict_replace_bug.py` 测试脚本
- [ ] 测试脚本包含 dict 类型触发测试
- [ ] 测试脚本包含 normalize_corrected_expression 函数测试
- [ ] 运行测试验证 bug 可以复现

## Verification

- `test -f test/test_dict_replace_bug.py` — 测试文件存在
- `python test/test_dict_replace_bug.py` — 运行测试，输出包含 "SUCCESS: Bug reproduced"

## Inputs

- `test/test_dict_replace_bug.py` — New file (test script, no input dependencies)

## Observability Impact

After T03:
- **What changes**: Test script `test/test_dict_replace_bug.py` exists and produces structured output
- **How to inspect**: Run `python test/test_dict_replace_bug.py` - output shows pass/fail status
- **Failure visibility**: Script exits with code 0 if bug reproduced, code 1 if bug not reproduced
- **Inspection surfaces**: stdout contains test case results and bug location documentation

## Expected Output

- `test/test_dict_replace_bug.py` — 可执行的复现测试脚本
