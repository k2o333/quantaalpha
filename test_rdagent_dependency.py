#!/usr/bin/env python
"""
验证 rdagent.log 依赖问题的脚本
"""

import sys
import subprocess

def check_rdagent_import():
    """检查 rdagent 包是否可导入"""
    print("=" * 60)
    print("1. 检查 rdagent 包是否可导入")
    print("=" * 60)

    try:
        import rdagent
        print(f"✅ rdagent 包可导入，版本: {getattr(rdagent, '__version__', 'unknown')}")
        return True
    except ImportError as e:
        print(f"❌ rdagent 包不可导入: {e}")
        return False

def check_quantaalpha_log_import():
    """检查 quantaalpha.log 是否可导入"""
    print("\n" + "=" * 60)
    print("2. 检查 quantaalpha.log 是否可导入")
    print("=" * 60)

    try:
        from quantaalpha.log import logger
        print(f"✅ quantaalpha.log 可导入，类型: {type(logger)}")
        return True
    except ImportError as e:
        print(f"❌ quantaalpha.log 不可导入: {e}")
        return False
    except Exception as e:
        print(f"❌ quantaalpha.log 导入时发生其他错误: {type(e).__name__}: {e}")
        return False

def check_source_code():
    """检查源码中的导入语句"""
    print("\n" + "=" * 60)
    print("3. 检查 quantaalpha/log/__init__.py 源码")
    print("=" * 60)

    import os
    log_init_path = None

    # 尝试多个可能的路径
    possible_paths = [
        os.path.join(os.path.dirname(__file__), "quantaalpha/log/__init__.py"),
        os.path.join(os.path.dirname(__file__), "third_party/quantaalpha/quantaalpha/log/__init__.py"),
    ]

    for path in possible_paths:
        if os.path.exists(path):
            log_init_path = path
            break

    if log_init_path is None:
        print("❌ 找不到 quantaalpha/log/__init__.py 文件")
        return False

    print(f"找到文件: {log_init_path}")

    with open(log_init_path, 'r') as f:
        content = f.read()

    # 检查关键导入语句
    has_rdagent_import = "from rdagent.log import" in content
    print(f"\n关键检查:")
    print(f"  - 包含 'from rdagent.log import': {has_rdagent_import}")

    if has_rdagent_import:
        print(f"\n⚠️  发现问题: quantaalpha.log 依赖 rdagent.log")
        print(f"   这意味着任何导入 quantaalpha.log 的代码都需要安装 rdagent 包")

    return has_rdagent_import

def check_rdagent_installed_environments():
    """检查 rdagent 在哪些 conda 环境已安装"""
    print("\n" + "=" * 60)
    print("4. 检查 conda 环境中的 rdagent 安装情况")
    print("=" * 60)

    conda_bases = [
        "/root/miniforge3",
        "/opt/miniconda3",
        "/opt/conda",
        os.path.expanduser("~/miniforge3"),
    ]

    import os
    found_envs = []

    for base in conda_bases:
        if not os.path.exists(base):
            continue

        envs_dir = os.path.join(base, "envs")
        if not os.path.exists(envs_dir):
            continue

        for env_name in os.listdir(envs_dir):
            env_python = os.path.join(envs_dir, env_name, "bin", "python")
            if os.path.exists(env_python):
                # 检查 rdagent 是否安装在这个环境
                result = subprocess.run(
                    [env_python, "-c", "import rdagent; print('ok')"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0 and "ok" in result.stdout:
                    found_envs.append((env_name, os.path.join(envs_dir, env_name)))

    if found_envs:
        print(f"✅ 找到 {len(found_envs)} 个已安装 rdagent 的 conda 环境:")
        for env_name, env_path in found_envs:
            print(f"   - {env_name}: {env_path}")
    else:
        print("❌ 未找到已安装 rdagent 的 conda 环境")

    return found_envs

def main():
    print("rdagent.log 依赖问题验证脚本")
    print(f"当前 Python: {sys.executable}")
    print(f"当前 Python 版本: {sys.version}")

    results = {}

    # 1. 检查 rdagent 是否可导入
    results['rdagent_importable'] = check_rdagent_import()

    # 2. 检查 quantaalpha.log 是否可导入
    results['quantaalpha_log_importable'] = check_quantaalpha_log_import()

    # 3. 检查源码
    results['has_dependency'] = check_source_code()

    # 4. 检查 conda 环境
    results['conda_envs'] = check_rdagent_installed_environments()

    # 总结
    print("\n" + "=" * 60)
    print("验证结果总结")
    print("=" * 60)

    if results['rdagent_importable']:
        print("✅ rdagent 包在当前环境中可用")
    else:
        print("❌ rdagent 包在当前环境中不可用")

    if results['quantaalpha_log_importable']:
        print("✅ quantaalpha.log 可以正常导入")
    else:
        print("❌ quantaalpha.log 导入失败 - 存在 rdagent.log 依赖问题！")

    if results['has_dependency']:
        print("⚠️  源码存在问题: quantaalpha.log 依赖外部 rdagent 包")
        print("   这会导致在没有安装 rdagent 的环境中无法使用")

    if results['conda_envs']:
        print(f"ℹ️  可通过 conda 环境 '{results['conda_envs'][0][0]}' 运行来解决此问题")
        print(f"   例如: conda activate {results['conda_envs'][0][0]}")

    print("\n建议的修复方案:")
    print("1. 将 rdagent.log 的实现内联到 quantaalpha/log/__init__.py 中")
    print("2. 或者在 setup.py/requirements.txt 中声明 rdagent 为依赖")
    print("3. 或者创建一个独立的 Logger 类，不依赖外部 rdagent 包")

if __name__ == "__main__":
    main()
