#!/bin/bash
set -e

echo "=== MVP 环境初始化 (conda) ==="

# 进入项目根目录
cd "$(dirname "$0")/.."

# 设置 conda/mamba 路径
MAMBA_BIN="/root/miniforge3/bin/mamba"

# 检查 mamba
if [ ! -f "$MAMBA_BIN" ]; then
    echo "错误：未找到 mamba 命令: $MAMBA_BIN"
    exit 1
fi

echo "使用 mamba: $MAMBA_BIN"

# 创建第三方目录
mkdir -p third_party

# 浅克隆源码
echo "[1/3] 克隆源码..."
if [ ! -d "third_party/quantaalpha" ]; then
    git clone --depth 1 https://github.com/quantaalpha/quantaalpha.git third_party/quantaalpha
else
    echo "quantaalpha 已存在，跳过克隆"
fi

if [ ! -d "third_party/vnpy" ]; then
    git clone --depth 1 https://github.com/vnpy/vnpy.git third_party/vnpy
else
    echo "vnpy 已存在，跳过克隆"
fi

# 创建 mining 环境
echo "[2/3] 创建 mining 环境..."
if ! $MAMBA_BIN env list | grep -q "mining"; then
    $MAMBA_BIN create -n mining python=3.12 -y
fi

# 激活环境并安装依赖
echo "[3/3] 在 mining 环境中安装依赖..."
$MAMBA_BIN run -n mining pip install -e ./third_party/quantaalpha
$MAMBA_BIN run -n mining pip install -e ./third_party/vnpy
$MAMBA_BIN run -n mining pip install polars

# 锁定版本
echo "锁定版本..."
$MAMBA_BIN run -n mining pip freeze > p/factormining/mvp/requirements.txt

echo ""
echo "=== 环境初始化完成 ==="
echo "环境名称: mining"
echo "使用方法:"
echo "  1. 激活环境: /root/miniforge3/bin/mamba activate mining"
echo "  2. 运行代码: python p/factormining/mvp/glue_runner.py"
echo "  或直接运行: /root/miniforge3/bin/mamba run -n mining python p/factormining/mvp/glue_runner.py"
