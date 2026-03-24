#!/usr/bin/env python
"""
进一步检查 rdagent 包结构
"""

import sys

print("=" * 60)
print("检查 rdagent 包结构")
print("=" * 60)

# 1. 检查 rdagent 包的基本信息
print("\n1. 检查 rdagent 包基本信息")
print("-" * 40)
try:
    import rdagent
    print(f"✅ import rdagent 成功")
    print(f"   模块文件: {rdagent.__file__}")
    print(f"   模块路径: {rdagent.__path__}")
    print(f"   包内容: {dir(rdagent)}")
except ImportError as e:
    print(f"❌ import rdagent 失败: {e}")

# 2. 检查 rdagent.log 是否存在
print("\n2. 检查 rdagent.log 模块")
print("-" * 40)
try:
    import rdagent.log
    print(f"✅ import rdagent.log 成功")
    print(f"   模块文件: {rdagent.log.__file__}")
    print(f"   包内容: {dir(rdagent.log)}")
except ImportError as e:
    print(f"❌ import rdagent.log 失败: {e}")

# 3. 尝试其他可能的 log 模块名
print("\n3. 检查 rdagent 包的子模块")
print("-" * 40)
try:
    import pkgutil
    import rdagent

    # 检查 rdagent 包的所有子模块
    if hasattr(rdagent, '__path__'):
        print(f"rdagent.__path__: {rdagent.__path__}")
        for importer, modname, ispkg in pkgutil.iter_modules(rdagent.__path__):
            print(f"  - {modname} {'(package)' if ispkg else ''}")
    else:
        print("rdagent 没有 __path__ 属性")

    # 检查 rdagent.log 的替代品
    print("\n尝试常见的 log 相关模块名称:")
    for name in ['log', 'logging', 'logger', 'loggers']:
        try:
            module = __import__(f"rdagent.{name}", fromlist=[name])
            print(f"  ✅ rdagent.{name}: {module.__file__}")
        except ImportError:
            print(f"  ❌ rdagent.{name}: 不存在")
except Exception as e:
    print(f"检查过程出错: {e}")

# 4. 检查 quantaalpha.log 的导入路径
print("\n4. 检查 quantaalpha.log 的导入")
print("-" * 40)
try:
    from quantaalpha.log import logger
    print(f"✅ quantaalpha.log 可导入")
except ImportError as e:
    print(f"❌ quantaalpha.log 导入失败: {e}")

    # 尝试找到具体是哪一行失败
    import traceback
    print("\n完整堆栈:")
    traceback.print_exc()

# 5. 检查 third_party/quantaalpha 的情况
print("\n5. 检查 third_party/quantaalpha 结构")
print("-" * 40)
import os
third_party_qa = "/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha"
if os.path.exists(third_party_qa):
    log_init = os.path.join(third_party_qa, "log/__init__.py")
    if os.path.exists(log_init):
        with open(log_init, 'r') as f:
            content = f.read()
        print(f"third_party/quantaalpha/log/__init__.py 内容:")
        for i, line in enumerate(content.split('\n')[:15], 1):
            print(f"  {i}: {line}")
        if len(content.split('\n')) > 15:
            print(f"  ... (共 {len(content.split(chr(10)))} 行)")
else:
    print(f"目录不存在: {third_party_qa}")

print("\n" + "=" * 60)
print("结论")
print("=" * 60)
print("""
问题分析:
1. rdagent 包存在，但可能没有 log 子模块
2. quantaalpha.log/__init__.py 尝试从 rdagent.log 导入
3. 这导致在没有 rdagent.log 子模块的环境中导入失败

可能的解决方案:
1. 确认 rdagent 包版本，可能需要特定版本才有 log 模块
2. 修改 quantaalpha/log/__init__.py 使用替代的 log 实现
3. 检查 rdagent_env_backup.py 是否有独立的 log 实现可以复用
""")
