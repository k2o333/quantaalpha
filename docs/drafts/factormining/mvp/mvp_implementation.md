# QuantaAlpha + vnpy MVP 实施部署方案

## 1. 方案概述

本文档描述如何使用 `conda` (miniforge) 部署和运行 QuantaAlpha + vnpy 的 MVP 集成方案。

**核心思路：**
- 使用 `conda` 管理 Python 版本和虚拟环境
- 新建 `mining` conda 环境
- 浅克隆（`--depth 1`）获取最新代码，减少下载量
- 可编辑模式（`pip install -e`）安装，支持修改源码

**Python 版本：3.12**
- vnpy 支持 Python 3.10+
- QuantaAlpha 支持 Python 3.10+
- 统一使用 Python 3.12

---

## 2. 目录结构

```
aspipe_v4/
├── p/factormining/mvp/            # 纯文档目录
│   ├── mvp_implementation.md      # 本文档（实施方案）
│   ├── mvp_quantaalpha_vnpy_glue_v2.md  # 问题分析文档
│   └── requirements.txt           # 依赖列表（生成）
├── third_party/                   # 第三方源码目录
│   ├── setup_env.sh               # 环境初始化脚本
│   ├── quantaalpha/               # 浅克隆的 quantaalpha
│   └── vnpy/                      # 浅克隆的 vnpy
└── 使用 conda 环境（mining）       # 虚拟环境由 conda 管理
```

---

## 3. 前置要求

### 检查 miniforge/conda 安装

```bash
# 检查 conda 是否可用
conda --version

# 如果不可用，检查 miniforge 路径
ls /root/miniforge3/bin/conda

# 初始化 conda（如需）
/root/miniforge3/bin/conda init bash
source ~/.bashrc
```

---

## 4. 环境搭建步骤

### 步骤 1: 浅克隆源码

```bash
cd /home/quan/testdata/aspipe_v4/third_party

# 浅克隆 quantaalpha（只下载最新版本）
git clone --depth 1 https://github.com/quantaalpha/quantaalpha.git

# 浅克隆 vnpy（只下载最新版本）
git clone --depth 1 https://github.com/vnpy/vnpy.git
```

### 步骤 2: 创建 mining conda 环境

```bash
# 创建新环境
conda create -n mining python=3.12 -y

# 激活环境
conda activate mining

# 可编辑模式安装
cd /home/quan/testdata/aspipe_v4
pip install -e ./third_party/quantaalpha
pip install -e ./third_party/vnpy

# 安装其他依赖
pip install polars pandas numpy
```

### 步骤 3: 生成依赖锁定文件

```bash
cd /home/quan/testdata/aspipe_v4/p/factormining/mvp
pip freeze > requirements.txt
```

---

## 5. 自动化脚本

创建 `/home/quan/testdata/aspipe_v4/third_party/setup_env.sh`：

```bash
#!/bin/bash
set -e

echo "=== MVP 环境初始化 (conda) ==="

# 进入项目根目录
cd "$(dirname "$0")/.."

# 检查 conda
if ! command -v conda &> /dev/null; then
    echo "错误：未找到 conda 命令"
    echo "尝试使用 miniforge 路径..."
    if [ -f "/root/miniforge3/bin/conda" ]; then
        export PATH="/root/miniforge3/bin:$PATH"
        eval "$('/root/miniforge3/bin/conda' 'shell.bash' 'hook' 2> /dev/null)"
    else
        echo "错误：未找到 miniforge 安装"
        exit 1
    fi
fi

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
if ! conda env list | grep -q "mining"; then
    conda create -n mining python=3.12 -y
fi

# 激活环境并安装依赖
echo "[3/3] 在 mining 环境中安装依赖..."
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate mining

pip install -e ./third_party/quantaalpha
pip install -e ./third_party/vnpy
pip install polars pandas numpy

# 锁定版本
echo "锁定版本..."
pip freeze > p/factormining/mvp/requirements.txt

echo ""
echo "=== 环境初始化完成 ==="
echo "环境名称: mining"
echo "运行: conda activate mining && python p/factormining/mvp/glue_runner.py"
```

赋予执行权限：
```bash
chmod +x /home/quan/testdata/aspipe_v4/third_party/setup_env.sh
```

---

## 6. 使用方式

### 首次部署

```bash
cd /home/quan/testdata/aspipe_v4
./third_party/setup_env.sh
```

### 日常开发

```bash
cd /home/quan/testdata/aspipe_v4

# 激活 mining 环境
conda activate mining

# 运行胶水代码
python p/factormining/mvp/glue_runner.py

# 修改源码（在 third_party/ 目录下）
# 修改立即生效，无需重新安装
```

### 更新第三方库

```bash
cd /home/quan/testdata/aspipe_v4/third_party/quantaalpha
git pull
cd ../vnpy
git pull
cd ../..

# 重新安装（在激活的 conda 环境中）
conda activate mining
pip install -e ./third_party/quantaalpha
pip install -e ./third_party/vnpy
```

---

## 7. 注意事项

| 事项 | 说明 |
|------|------|
| Python 版本 | 3.12 |
| 环境管理 | 使用 conda 管理，环境名称为 `mining` |
| 可编辑安装 | 使用 `pip install -e` 模式，修改源码立即生效 |
| 浅克隆限制 | `--depth 1` 无法查看历史提交，如需历史请重新完整克隆 |
| 版本锁定 | `requirements.txt` 用于复现环境 |
| 团队协作 | `third_party/` 应加入 `.gitignore`（可选） |

---

## 8. .gitignore 配置

在 `/home/quan/testdata/aspipe_v4/.gitignore` 中添加：

```
# Python 缓存
__pycache__/
*.py[cod]
*$py.class
*.so

# 第三方源码（可选：如果要锁定版本可以提交，否则忽略）
# third_party/

# Jupyter
.ipynb_checkpoints/

# IDE
.vscode/
.idea/
```

---

## 9. 下一步

环境搭建完成后，参考 `mvp_quantaalpha_vnpy_glue_v2.md` 编写 `glue_runner.py`：

1. 表达式转换（处理 `$` 前缀、时序/截面函数映射）
2. 数据准备（符合 vnpy AlphaDataset 格式）
3. 因子计算与回测
4. 结果输出
