# 修复方案：数据目录配置与移除 --force 参数

## 问题概述

### 问题1：数据目录配置不一致

**现状**：
- 测试脚本 `test_type_abcd.sh` 硬编码 `DATA_BASE_DIR="/home/quan/testdata/aspipe_v4/data"`
- 代码配置 `settings.yaml` 设置 `base_dir: "/home/quan/testdata/aspipe_v4/app4/data"`
- 导致脚本清空的数据目录与程序实际使用的目录不一致

**目标**：
- 统一由 `settings.yaml` 决定数据目录
- 将 `base_dir` 改为 `/home/quan/testdata/aspipe_v4/data`

### 问题2：--force 参数功能不完整

**现状**：
- `--force` 参数本意是强制覆盖已存在的数据
- 但实际使用时，数据仍被去重逻辑过滤掉
- 从输出日志可见：`Deduplication completed: input=117, output=0, removed=117`

**目标**：
- 移除 `--force` 参数及相关代码
- 简化代码逻辑，避免产生误导

---

## 修改方案

### 问题1：数据目录配置

#### 1.1 修改 settings.yaml

**文件**：`/home/quan/testdata/aspipe_v4/app4/config/settings.yaml`

**修改位置**：第32行

```yaml
# 修改前
storage:
  base_dir: "/home/quan/testdata/aspipe_v4/app4/data"

# 修改后
storage:
  base_dir: "/home/quan/testdata/aspipe_v4/data"
```

#### 1.2 修改测试脚本

**文件**：`/home/quan/testdata/aspipe_v4/p/interface5/test_type_abcd.sh`

**修改内容**：
- 移除硬编码的 `DATA_BASE_DIR` 变量
- 移除 `clear_interface_data()` 函数
- 程序会自动从 `settings.yaml` 读取数据目录

**修改前**（第9-14行）：
```bash
PYTHON_PATH="/root/miniforge3/envs/get/bin/python"
MAIN_PY="/home/quan/testdata/aspipe_v4/app4/main.py"
DATA_BASE_DIR="/home/quan/testdata/aspipe_v4/data"
OUTPUT_DIR="/home/quan/testdata/aspipe_v4/p/interface5/output"
TS_CODE="000001.SZ"
```

**修改后**：
```bash
PYTHON_PATH="/root/miniforge3/envs/get/bin/python"
MAIN_PY="/home/quan/testdata/aspipe_v4/app4/main.py"
OUTPUT_DIR="/home/quan/testdata/aspipe_v4/p/interface5/output"
TS_CODE="000001.SZ"
```

**删除函数**（第35-49行）：
```bash
# 删除整个 clear_interface_data() 函数
```

**修改测试函数调用**：
在每个 `test_type_x()` 函数中，删除 `clear_interface_data "$interface"` 调用。

例如 `test_type_a()` 函数修改：

```bash
# 修改前
for interface in "${TYPE_A_INTERFACES[@]}"; do
    echo ""
    echo "----------------------------------------"
    echo "测试接口: $interface"
    echo "----------------------------------------"

    # 清空数据
    clear_interface_data "$interface"

    # 测试1: 全量下载（小范围）
    ...
```

```bash
# 修改后
for interface in "${TYPE_A_INTERFACES[@]}"; do
    echo ""
    echo "----------------------------------------"
    echo "测试接口: $interface"
    echo "----------------------------------------"

    # 测试1: 全量下载（小范围）
    ...
```

---

### 问题2：移除 --force 参数

需要修改以下文件：

#### 2.1 main.py

**文件**：`/home/quan/testdata/aspipe_v4/app4/main.py`

**修改1**：移除参数定义（第634-635行）

```python
# 删除这两行
parser.add_argument('--force', action='store_true',
                    help='强制覆盖已存在的数据')
```

**修改2**：移除 `create_app_components` 调用中的 `force_download` 参数（第716行附近）

```python
# 修改前
components = create_app_components(
    config_loader=config_loader,
    args=args,
    force_download=args.force
)

# 修改后
components = create_app_components(
    config_loader=config_loader,
    args=args
)
```

**修改3**：修改 `create_app_components` 函数签名（第94行）

```python
# 修改前
def create_app_components(config_loader: ConfigLoader, args, force_download: bool = False) -> AppComponents:

# 修改后
def create_app_components(config_loader: ConfigLoader, args) -> AppComponents:
```

**修改4**：移除函数内部的 `force_download` 使用（第125行）

```python
# 修改前
downloader = GenericDownloader(
    config_loader=config_loader,
    storage_manager=storage_manager,
    trade_calendar_cache=trade_cal_cache,
    stock_list_cache=stock_list_cache,
    force_download=force_download
)

# 修改后
downloader = GenericDownloader(
    config_loader=config_loader,
    storage_manager=storage_manager,
    trade_calendar_cache=trade_cal_cache,
    stock_list_cache=stock_list_cache
)
```

**修改5**：移除 `build_params_list` 调用中的 `force_download` 参数（第850、863行）

```python
# 修改前
params_list, context = builder.build_params_list(result, stock_list, force_download=args.force)

# 修改后
params_list, context = builder.build_params_list(result, stock_list)
```

**修改6**：移除 update 模式中的 force 相关代码（第468行）

```python
# 修改前
force_download=args.update_force if hasattr(args, 'update_force') else False

# 修改后（直接删除此行或改为 False）
force_download=False
```

#### 2.2 core/downloader.py

**文件**：`/home/quan/testdata/aspipe_v4/app4/core/downloader.py`

**修改1**：移除 `__init__` 中的 `force_download` 参数（第88行）

```python
# 修改前
def __init__(
    self,
    config_loader: ConfigLoader,
    storage_manager=None,
    trade_calendar_cache=None,
    stock_list_cache=None,
    force_download=False,
):

# 修改后
def __init__(
    self,
    config_loader: ConfigLoader,
    storage_manager=None,
    trade_calendar_cache=None,
    stock_list_cache=None,
):
```

**修改2**：移除 `self.force_download` 属性（第102行）

```python
# 删除这一行
self.force_download = force_download
```

**修改3**：移除 `_download_for_single_stock` 调用中的 `force_download` 参数（第272行）

```python
# 修改前
force_download=self.force_download,

# 修改后（删除此参数）
```

**修改4**：移除 `_download_for_single_stock_v2` 调用中的 `force_download` 参数（第457行）

```python
# 修改前
force_download=self.force_download,

# 修改后（删除此参数）
```

**修改5**：移除缺口检测中的 `force_download` 判断（第520行）

```python
# 修改前
and not self.force_download

# 修改后
# 直接删除此条件，或保留缺口检测逻辑
```

#### 2.3 core/context.py

**文件**：`/home/quan/testdata/aspipe_v4/app4/core/context.py`

```python
# 修改前
@dataclass
class DownloadContext:
    user_provided_dates: bool = False
    force_download: bool = False
    date_range: Optional[Dict[str, str]] = None
    ...

# 修改后
@dataclass
class DownloadContext:
    user_provided_dates: bool = False
    date_range: Optional[Dict[str, str]] = None
    ...
```

#### 2.4 core/pagination.py

**文件**：`/home/quan/testdata/aspipe_v4/app4/core/pagination.py`

**修改1**：移除 `PaginationContext` 中的 `force_download` 字段（第27行）

```python
# 修改前
@dataclass
class PaginationContext:
    ...
    force_download: bool = False

# 修改后（删除 force_download 字段）
```

**修改2**：移除使用 `force_download` 的判断（第272行）

```python
# 修改前
if skip_existing and not self.context.force_download:

# 修改后
if skip_existing:
```

#### 2.5 core/params_builder.py

**文件**：`/home/quan/testdata/aspipe_v4/app4/core/params_builder.py`

**修改**：移除 `build_params_list` 中的 `force_download` 参数（第245行）

```python
# 修改前
def build_params_list(
    self,
    interface_config: Dict[str, Any],
    stock_list: Optional[List[Dict[str, Any]]] = None,
    force_download: bool = False,
) -> Tuple[List[Dict[str, Any]], DownloadContext]:

# 修改后
def build_params_list(
    self,
    interface_config: Dict[str, Any],
    stock_list: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[List[Dict[str, Any]], DownloadContext]:
```

同时删除函数内部对 `force_download` 的使用（第273行附近）。

#### 2.6 core/pagination_executor.py

**文件**：`/home/quan/testdata/aspipe_v4/app4/core/pagination_executor.py`

**修改1**：移除 `_force_download` 相关判断（第127行）

```python
# 修改前
if coverage_manager and not params.get('_force_download'):

# 修改后
if coverage_manager:
```

**修改2**：移除 `_force_download` 相关判断（第165行）

```python
# 修改前
if not (coverage_manager and not p.get('_force_download') and ...):

# 修改后
if not (coverage_manager and ...):
```

#### 2.7 update/update_manager.py

**文件**：`/home/quan/testdata/aspipe_v4/app4/update/update_manager.py`

**修改**：移除 `force_download` 参数（第459行）

```python
# 修改前
force_download=options.force

# 修改后（删除此参数）
```

---

## 修改文件清单

| 文件路径 | 修改类型 |
|---------|---------|
| `app4/config/settings.yaml` | 修改 base_dir |
| `p/interface5/test_type_abcd.sh` | 移除 DATA_BASE_DIR 和 clear_interface_data |
| `app4/main.py` | 移除 --force 参数及相关代码 |
| `app4/core/downloader.py` | 移除 force_download 属性 |
| `app4/core/context.py` | 移除 force_download 字段 |
| `app4/core/pagination.py` | 移除 force_download 字段 |
| `app4/core/params_builder.py` | 移除 force_download 参数 |
| `app4/core/pagination_executor.py` | 移除 _force_download 判断 |
| `app4/update/update_manager.py` | 移除 force_download 参数 |

---

## 验证方法

1. 修改 `settings.yaml` 中的 `base_dir` 为 `/home/quan/testdata/aspipe_v4/data`
2. 运行测试脚本，确认数据写入正确的目录
3. 确认 `--force` 参数已被移除，程序仍能正常运行
