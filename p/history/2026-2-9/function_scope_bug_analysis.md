# 问题诊断报告：NameError: name '_prepare_stock_list' is not defined

## 问题现象

在执行增量更新模式时，程序抛出 `NameError` 异常：

```bash
$ /root/miniforge3/envs/get/bin/python app4/main.py --update --interface disclosure_date
...
2026-02-09 15:49:24,525 - __main__ - ERROR - Error processing interface disclosure_date: name '_prepare_stock_list' is not defined
Traceback (most recent call last):
  File "/home/quan/testdata/aspipe_v4/app4/main.py", line 307, in run_update_mode
    stock_list = _prepare_stock_list(downloader, args, params)
NameError: name '_prepare_stock_list' is not defined
```

**关键信息：**
- 错误发生在 `--update` 模式下
- 普通模式（不带 `--update`）工作正常
- 错误位置：`app4/main.py:307`

## 问题诊断

### 根本原因：函数定义顺序与作用域问题

在 Python 中，函数必须先定义后调用。问题出在 `app4/main.py` 的代码结构上：

1. **`run_update_mode()` 函数**（第 123-381 行）在第 **307 行**调用 `_prepare_stock_list()`
2. **`_prepare_stock_list()` 函数** 却在第 **825 行**才定义

**调用点（太早）：**
```python
# run_update_mode() 内部，第 307 行
stock_list = _prepare_stock_list(downloader, args, params)  # ❌ 函数尚未定义！
```

**定义点（太晚）：**
```python
# main() 函数内部，第 825 行
def _prepare_stock_list(downloader, args, params):
    """统一的股票列表准备方法"""
    # ... 函数实现
```

### 为什么普通模式能工作？

普通模式的代码执行路径：
1. 进入 `main()` 函数
2. 在 `main()` 中定义 `_prepare_stock_list()`（第 825 行）
3. 后续代码在 `main()` 中调用 `_prepare_stock_list()`（第 990 行）
4. 此时函数已定义，作用域内可见

### 为什么 `--update` 模式失败？

`--update` 模式的代码执行路径：
1. 进入 `main()` 函数
2. 检测到 `args.update` 为 True，立即调用 `run_update_mode(args)`（第 516 行）
3. 在 `run_update_mode()` 内部（第 307 行）尝试调用 `_prepare_stock_list()`
4. 此时程序还未执行到第 825 行，`_prepare_stock_list()` 尚未定义
5. 抛出 `NameError`

### 代码结构分析

```python
# 文件结构（简化）
def run_update_mode(args):  # 第 123 行
    # ...
    stock_list = _prepare_stock_list(...)  # 第 307 行 ❌ 调用过早
    # ...

def main():  # 第 426 行
    # ...
    if args.update:
        return run_update_mode(args)  # 第 516 行 - 提前进入 run_update_mode
    
    # ...
    
    def _prepare_stock_list(...):  # 第 825 行 - 定义过晚
        # ...
    
    # 普通模式在这里调用 _prepare_stock_list (第 990 行) ✓
```

## 解决方案

### 方案1：移动函数定义位置（推荐）

将 `_prepare_stock_list()` 函数的定义从 `main()` 内部移到 `run_update_mode()` 之前，使其成为模块级函数。

**修改位置：** `app4/main.py`

**修改步骤：**
1. 将第 825-849 行的 `_prepare_stock_list()` 函数定义剪切
2. 粘贴到第 122 行（`run_update_mode()` 定义之前）
3. 调整函数签名，将 `storage_manager` 和 `logger` 作为参数传递

**预期效果：**
- 两个模式都能正常访问该函数
- 函数在模块级别定义，作用域全局可见

### 方案2：提前函数定义

将 `_prepare_stock_list()` 的定义移动到 `main()` 函数的开头部分，确保在调用 `run_update_mode()` 之前已定义。

**缺点：**
- 代码逻辑不够清晰
- 仍然限制在 `main()` 的局部作用域内

### 方案3：重复代码

在 `run_update_mode()` 内部重新定义 `_prepare_stock_list()` 函数。

**缺点：**
- 代码重复，维护困难
- 违反 DRY 原则

## 建议

**强烈推荐方案1**，因为：
1. 符合 Python 最佳实践（函数定义在调用之前）
2. 避免代码重复
3. 提高代码可维护性
4. 两个模式共享同一函数实现

## 验证方法

修复后应验证：
1. `--update --interface disclosure_date` 能正常工作
2. `--interface disclosure_date` 仍然能正常工作
3. 其他接口在两种模式下都能正常工作
4. 无其他类似的函数作用域问题
