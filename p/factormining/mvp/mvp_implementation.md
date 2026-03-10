# QuantaAlpha + vnpy MVP 实施部署方案

## 1. 方案概述

本文档描述如何使用 `uv` 部署和运行 QuantaAlpha + vnpy 的 MVP 集成方案。

**核心思路：**
- 使用 `uv` 管理 Python 版本和虚拟环境
- 浅克隆（`--depth 1`）获取最新代码，减少下载量
- 可编辑模式（`uv pip install -e`）安装，支持修改源码

**Python 版本：3.13**
- vnpy 官方推荐 Python 3.13
- QuantaAlpha 支持 Python 3.10+
- 统一使用 Python 3.13

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
└── mning/                         # uv 虚拟环境（名字：mning）
```

---

## 3. 前置要求

### 安装 uv

```bash
# 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 验证安装
uv --version
```

### 安装 Python 3.13

```bash
# 使用 uv 安装 Python 3.13
uv python install 3.13

# 验证安装
uv python find 3.13
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

### 步骤 2: 安装依赖

```bash
cd /home/quan/testdata/aspipe_v4

# 创建虚拟环境 mning
uv venv mning --python 3.13

# 可编辑模式安装（使用 mning 虚拟环境）
uv pip install -e ./third_party/quantaalpha --python 3.13 --venv mning
uv pip install -e ./third_party/vnpy --python 3.13 --venv mning

# 安装其他依赖
uv pip install polars pandas numpy --python 3.13 --venv mning
```

### 步骤 3: 生成依赖锁定文件

```bash
cd /home/quan/testdata/aspipe_v4/p/factormining/mvp
uv pip freeze --venv mning > requirements.txt
```

---

## 5. 自动化脚本

创建 `/home/quan/testdata/aspipe_v4/third_party/setup_env.sh`：

```bash
#!/bin/bash
set -e

echo "=== MVP 环境初始化 (uv) ==="

# 进入项目根目录
cd "$(dirname "$0")/.."

# 检查 uv
if ! command -v uv &> /dev/null; then
    echo "错误：未安装 uv"
    echo "安装命令: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# 检查 Python 3.13
if ! uv python find 3.13 &> /dev/null; then
    echo "错误：未找到 Python 3.13"
    echo "安装命令: uv python install 3.13"
    exit 1
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

# 创建虚拟环境
echo "[2/4] 创建虚拟环境 mning..."
uv venv mning --python 3.13

# 安装依赖
echo "[3/4] 安装依赖..."
uv pip install -e ./third_party/quantaalpha --python 3.13 --venv mning
uv pip install -e ./third_party/vnpy --python 3.13 --venv mning
uv pip install polars pandas numpy --python 3.13 --venv mning

# 锁定版本
echo "[4/4] 锁定版本..."
uv pip freeze --venv mning > p/factormining/mvp/requirements.txt

echo ""
echo "=== 环境初始化完成 ==="
echo "运行: uv run --python 3.13 --venv mning python p/factormining/mvp/glue_runner.py"
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

# 运行胶水代码（使用 mning 虚拟环境）
uv run --python 3.13 --venv mning python p/factormining/mvp/glue_runner.py

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

# 重新安装
uv pip install -e ./third_party/quantaalpha --python 3.13 --venv mning
uv pip install -e ./third_party/vnpy --python 3.13 --venv mning
```

---

## 7. 注意事项

| 事项 | 说明 |
|------|------|
| Python 版本 | 必须使用 Python 3.13 |
| uv 管理 | 所有 Python 操作通过 `uv` 命令完成 |
| 虚拟环境 | 使用 `mning` 作为虚拟环境名字，所有命令需加 `--venv mning` |
| 浅克隆限制 | `--depth 1` 无法查看历史提交，如需历史请重新完整克隆 |
| 源码修改 | 修改 `third_party/` 下的代码立即生效 |
| 版本锁定 | `requirements.txt` 用于复现环境 |
| 团队协作 | `.venv/` 和 `third_party/` 应加入 `.gitignore` |

---

## 8. .gitignore 配置

在 `/home/quan/testdata/aspipe_v4/.gitignore` 中添加：

```
# uv 虚拟环境
mning/

# 第三方源码（可选：如果要锁定版本可以提交，否则忽略）
# third_party/
```

---

## 9. 下一步

环境搭建完成后，参考 `mvp_quantaalpha_vnpy_glue_v2.md` 编写 `glue_runner.py`：

1. 表达式转换（处理 `$` 前缀、时序/截面函数映射）
2. 数据准备（符合 vnpy AlphaDataset 格式）
3. 因子计算与回测
4. 结果输出
