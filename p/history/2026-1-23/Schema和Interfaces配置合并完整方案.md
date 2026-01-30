# Schema 和 Interfaces 配置合并完整方案

## 目标
将 `app4/config/schemas/` 和 `app4/config/interfaces/` 的 YAML 配置文件合并，简化配置管理，只需维护一个配置文件。

---

## 一、当前架构分析

### 1.1 schemas 目录
- **位置**: `app4/config/schemas/`
- **内容**: 3个 VIP 财务报表接口
  - `balancesheet_vip.yaml`
  - `cashflow_vip.yaml`
  - `income_vip.yaml`
- **结构**:
  ```yaml
  fields:
    字段名: 类型
  derived_fields:
    派生字段名:
      source: 源字段
      type: 类型
      format: 格式
  ```

### 1.2 interfaces 目录
- **位置**: `app4/config/interfaces/`
- **内容**: 60+ 个接口配置文件
- **结构**:
  ```yaml
  api_name: 接口名
  name: 名称
  description: 描述
  derived_fields:
    派生字段名:
      source: 源字段
      type: 类型
      format: 格式
      description: 描述
  output:
    primary_key: [...]
    sort_by: [...]
  pagination: {...}
  parameters: {...}
  permissions: {...}
  request: {...}
  duplicate_detection: {...}  # 部分文件有
  fields: [...]  # 部分文件有（如 stock_basic.yaml）
  ```

### 1.3 代码引用
- 唯一引用: `app4/core/schema_manager.py`
  - `load_schema()` 方法从 `app4/config/schemas/` 读取 fields 定义
  - `load_derived_fields_config()` 从 `app4/config/interfaces/` 读取派生字段

---

## 二、合并方案

### 2.1 合并后的文件结构

将 schemas 的 `fields` 合并到 interfaces 文件中：

```yaml
# interfaces/balancesheet_vip.yaml (合并后)
api_name: balancesheet_vip
name: balancesheet_vip
description: 资产负债表(VIP) - 按季度获取全部上市公司数据

# 新增：精确字段类型定义
fields:
  ts_code: string
  ann_date: string
  end_date: string
  comp_type: Int64
  report_type: string
  total_share: Float64
  # ... 其他字段

# 派生字段（保留 interfaces 的完整定义，包含 description）
derived_fields:
  ann_date_dt:
    description: 日期类型的ann_date
    format: '%Y%m%d'
    source: ann_date
    type: date
  end_date_dt:
    description: 日期类型的end_date
    format: '%Y%m%d'
    source: end_date
    type: date
  f_ann_date_dt:
    description: 日期类型的f_ann_date
    format: '%Y%m%d'
    source: f_ann_date
    type: date

output:
  primary_key:
  - ts_code
  - ann_date
  - end_date
  sort_by:
  - ann_date
  - end_date

pagination:
  enabled: true
  mode: stock_loop
  window_size_days: 3650

parameters:
  ann_date:
    description: 公告日期 YYYYMMDD
    required: false
    type: string
  # ... 其他参数

permissions:
  min_points: 5000
  query_limit: 10000
  rate_limit: 60

request:
  extra_path: ''
  method: POST
  timeout: 30
```

### 2.2 需要修改的文件清单

| 文件路径 | 修改类型 | 说明 |
|---------|---------|------|
| `app4/core/schema_manager.py` | 代码修改 | 更新 `load_schema()` 方法 |
| `app4/config/interfaces/balancesheet_vip.yaml` | 配置合并 | 添加 fields 定义 |
| `app4/config/interfaces/cashflow_vip.yaml` | 配置合并 | 添加 fields 定义 |
| `app4/config/interfaces/income_vip.yaml` | 配置合并 | 添加 fields 定义 |
| `app4/config/schemas/` | 删除 | 合并后删除整个目录 |

---

## 三、代码修改说明

### 3.1 修改位置
文件: `app4/core/schema_manager.py`
方法: `load_schema()` (第 124-133 行)

### 3.2 修改前

```python
@staticmethod
def load_schema(interface_name: str) -> Optional[Dict[str, str]]:
    """加载预定义schema"""
    schema_file = f"app4/config/schemas/{interface_name}.yaml"
    if os.path.exists(schema_file):
        import yaml
        with open(schema_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
                return config.get('fields')
    return None
```

### 3.3 修改后

```python
@staticmethod
def load_schema(interface_name: str) -> Optional[Dict[str, str]]:
    """加载预定义schema - 从 interfaces 目录统一读取

    合并后，所有字段类型定义都保存在 interfaces 目录的配置文件中。
    该方法从接口配置中读取 fields 定义，用于创建精确类型的 DataFrame。
    """
    config_file = SchemaManager._get_config_file_path(interface_name)
    if os.path.exists(config_file):
        import yaml
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
                return config.get('fields')
    return None
```

### 3.4 变更说明

1. **路径变更**: 从 `app4/config/schemas/` 改为使用 `_get_config_file_path()` 方法（返回 `app4/config/interfaces/`）
2. **功能不变**: 仍然返回 `fields` 字典，用于 DataFrame 创建
3. **向后兼容**: 对于没有 `fields` 定义的接口，返回 `None`，系统会自动推断类型

### 3.5 其他方法无需修改

- `_get_config_file_path()`: 已经返回 interfaces 目录路径，无需修改
- `load_derived_fields_config()`: 已经从 interfaces 目录读取，无需修改
- `apply_derived_fields()`: 逻辑不变
- `create_dataframe()`: 逻辑不变，只是 `load_schema()` 的调用路径改变

### 3.6 完整方法代码

```python
@staticmethod
def _get_config_file_path(interface_name: str) -> str:
    """获取接口配置文件的路径"""
    # 假设配置文件在 config/interfaces/ 目录下
    config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', 'interfaces')
    config_file = os.path.join(config_dir, f"{interface_name}.yaml")
    return config_file

@staticmethod
def load_schema(interface_name: str) -> Optional[Dict[str, str]]:
    """加载预定义schema - 从 interfaces 目录统一读取

    合并后，所有字段类型定义都保存在 interfaces 目录的配置文件中。
    该方法从接口配置中读取 fields 定义，用于创建精确类型的 DataFrame。
    """
    config_file = SchemaManager._get_config_file_path(interface_name)
    if os.path.exists(config_file):
        import yaml
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
                return config.get('fields')
    return None
```

---

## 四、自动化合并脚本

### 4.1 脚本代码

```python
#!/usr/bin/env python3
"""合并 schemas 和 interfaces 配置文件

将 app4/config/schemas/ 中的 fields 定义合并到 app4/config/interfaces/ 对应文件中
"""

import yaml
import os
import shutil
from pathlib import Path
from datetime import datetime

def backup_directories():
    """备份现有配置目录"""
    base_dir = Path("app4/config")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 备份 schemas 目录
    if (base_dir / "schemas").exists():
        backup_schemas = base_dir / f"schemas.backup_{timestamp}"
        shutil.copytree(base_dir / "schemas", backup_schemas)
        print(f"✓ schemas 目录已备份到: {backup_schemas}")

    # 备份 interfaces 目录
    if (base_dir / "interfaces").exists():
        backup_interfaces = base_dir / f"interfaces.backup_{timestamp}"
        shutil.copytree(base_dir / "interfaces", backup_interfaces)
        print(f"✓ interfaces 目录已备份到: {backup_interfaces}")

    return timestamp

def merge_single_file(schema_file: Path, interface_file: Path):
    """合并单个配置文件"""
    print(f"\n处理文件: {schema_file.name}")

    if not schema_file.exists():
        print(f"  ✗ schemas 文件不存在: {schema_file}")
        return False

    if not interface_file.exists():
        print(f"  ✗ interfaces 文件不存在: {interface_file}")
        return False

    # 读取两个文件
    with open(schema_file, 'r', encoding='utf-8') as f:
        schema_config = yaml.safe_load(f)

    with open(interface_file, 'r', encoding='utf-8') as f:
        interface_config = yaml.safe_load(f)

    # 检查是否有 fields 定义
    if 'fields' not in schema_config:
        print(f"  ✗ schemas 文件中没有 fields 定义")
        return False

    # 检查 interfaces 文件是否已有 fields 定义
    if 'fields' in interface_config:
        print(f"  ⚠ interfaces 文件中已存在 fields 定义，将被覆盖")

    # 合并：将 fields 添加到 interface_config
    interface_config['fields'] = schema_config['fields']
    print(f"  ✓ 已合并 {len(schema_config['fields'])} 个字段定义")

    # 备份原 interfaces 文件
    backup_file = interface_file.with_suffix('.yaml.backup')
    if backup_file.exists():
        # 如果备份已存在，删除旧的
        backup_file.unlink()
    shutil.copy2(interface_file, backup_file)
    print(f"  ✓ 原文件已备份到: {backup_file.name}")

    # 写入合并后的文件
    with open(interface_file, 'w', encoding='utf-8') as f:
        yaml.dump(interface_config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    print(f"  ✓ 合并完成")
    return True

def merge_configs():
    """执行合并操作"""
    print("=" * 60)
    print("Schema 和 Interfaces 配置合并工具")
    print("=" * 60)

    # 获取项目根目录
    project_root = Path(__file__).parent.parent.parent
    os.chdir(project_root)

    print(f"\n工作目录: {os.getcwd()}")

    # 检查目录是否存在
    interfaces_dir = Path("app4/config/interfaces")
    schemas_dir = Path("app4/config/schemas")

    if not interfaces_dir.exists():
        print(f"✗ 错误: interfaces 目录不存在: {interfaces_dir}")
        return False

    if not schemas_dir.exists():
        print(f"✗ 错误: schemas 目录不存在: {schemas_dir}")
        return False

    # 备份配置
    print("\n步骤 1: 备份现有配置...")
    timestamp = backup_directories()

    # 需要合并的文件列表
    merge_files = [
        "balancesheet_vip.yaml",
        "cashflow_vip.yaml",
        "income_vip.yaml"
    ]

    print(f"\n步骤 2: 合并配置文件...")
    success_count = 0

    for filename in merge_files:
        schema_file = schemas_dir / filename
        interface_file = interfaces_dir / filename

        if merge_single_file(schema_file, interface_file):
            success_count += 1

    print("\n" + "=" * 60)
    print(f"合并完成: {success_count}/{len(merge_files)} 个文件成功")
    print("=" * 60)

    # 显示后续步骤
    print("\n后续步骤:")
    print("1. 检查合并后的配置文件:")
    for filename in merge_files:
        print(f"   - app4/config/interfaces/{filename}")
    print("\n2. 修改 app4/core/schema_manager.py 的 load_schema() 方法")
    print("\n3. 运行测试验证:")
    print("   cd app4")
    print("   python main.py --interface income_vip --start_date 20240101 --end_date 20240131")
    print("\n4. 测试通过后，删除 schemas 目录:")
    print("   rm -rf app4/config/schemas")

    return success_count == len(merge_files)

def verify_merge():
    """验证合并结果"""
    print("\n验证合并结果...")

    interfaces_dir = Path("app4/config/interfaces")
    merge_files = [
        "balancesheet_vip.yaml",
        "cashflow_vip.yaml",
        "income_vip.yaml"
    ]

    all_valid = True
    for filename in merge_files:
        file_path = interfaces_dir / filename
        with open(file_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        has_fields = 'fields' in config
        has_derived_fields = 'derived_fields' in config

        status = "✓" if has_fields else "✗"
        print(f"  {status} {filename}")
        print(f"     fields: {'是' if has_fields else '否'} ({len(config.get('fields', {}))} 个字段)")
        print(f"     derived_fields: {'是' if has_derived_fields else '否'} ({len(config.get('derived_fields', {}))} 个字段)")

        if not has_fields:
            all_valid = False

    return all_valid

if __name__ == "__main__":
    import sys

    # 执行合并
    if merge_configs():
        # 验证结果
        if verify_merge():
            print("\n✓ 所有验证通过！")
            sys.exit(0)
        else:
            print("\n✗ 验证失败，请检查配置文件")
            sys.exit(1)
    else:
        print("\n✗ 合并失败")
        sys.exit(1)
```

### 4.2 脚本功能

- ✅ 自动备份现有配置（带时间戳）
- ✅ 合并 3 个 VIP 接口的配置文件
- ✅ 验证合并结果
- ✅ 显示后续操作步骤

---

## 五、实施前检查清单

在运行合并脚本前，请仔细检查以下关键事项：

### 5.1 代码缩进问题
**问题描述**：示例代码中 `return config.get('fields')` 有额外缩进，会导致 `IndentationError`

**错误示例**（第160行和第179行）：
```python
with open(schema_file, 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)
        return config.get('fields')  # ❌ 错误的额外缩进
```

**修正后**（确保与 `with` 语句同级）：
```python
with open(schema_file, 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)
    return config.get('fields')  # ✅ 正确的缩进
```

**检查文件**：`app4/core/schema_manager.py` 第 124-133 行（修改前）和第 208-221 行（修改后）

### 5.2 合并前验证
**检查内容**：确认 interfaces 目录中 3 个 VIP 文件是否已包含 fields 定义

**验证命令**：
```bash
# 检查 income_vip.yaml
grep -A 5 "^fields:" app4/config/interfaces/income_vip.yaml

# 检查 balancesheet_vip.yaml
grep -A 5 "^fields:" app4/config/interfaces/balancesheet_vip.yaml

# 检查 cashflow_vip.yaml
grep -A 5 "^fields:" app4/config/interfaces/cashflow_vip.yaml
```

**预期结果**：
- 如果已存在 `fields` 定义：合并脚本会提示 `⚠ interfaces 文件中已存在 fields 定义，将被覆盖`
- 如果不存在 `fields` 定义：正常执行合并

**建议**：在合并前备份原始文件，防止意外覆盖

### 5.3 全面测试要求
**必须测试的接口**：
1. `income_vip`（利润表）
2. `balancesheet_vip`（资产负债表）
3. `cashflow_vip`（现金流量表）

**测试命令**：
```bash
cd app4

# 测试 income_vip
python main.py --interface income_vip --start_date 20240101 --end_date 20240131

# 测试 balancesheet_vip
python main.py --interface balancesheet_vip --start_date 20240101 --end_date 20240131

# 测试 cashflow_vip
python main.py --interface cashflow_vip --start_date 20240101 --end_date 20240131
```

**验证要点**：
- [ ] 数据下载成功，无报错
- [ ] 检查日志输出，确认 `load_schema()` 方法正常加载配置
- [ ] 验证数据类型：数值字段应为 Float64，整数字段应为 Int64
- [ ] 检查派生字段（如 `ann_date_dt`、`end_date_dt`）是否正确生成
- [ ] 对比合并前后的数据文件，确保数据一致性

**测试数据验证**：
```python
import polars as pl

# 加载测试数据
df = pl.read_parquet("data/income_vip/20240101_20240131.parquet")

# 检查数据类型
print(df.schema)

# 验证关键字段类型
assert df.schema['total_revenue'] == pl.Float64, "total_revenue 应该是 Float64"
assert df.schema['comp_type'] == pl.Int64, "comp_type 应该是 Int64"
assert df.schema['ann_date_dt'].is_temporal(), "ann_date_dt 应该是日期类型"
```

---

## 六、快速执行步骤

### 步骤 1: 运行合并脚本

```bash
cd /home/quan/testdata/aspipe_v4
python p/2026-1-23/merge_configs.py
```

### 步骤 2: 修改代码

编辑 `app4/core/schema_manager.py`，找到 `load_schema()` 方法（约第 124 行），将：

```python
schema_file = f"app4/config/schemas/{interface_name}.yaml"
```

改为：

```python
config_file = SchemaManager._get_config_file_path(interface_name)
```

### 步骤 3: 测试验证

```bash
cd app4
python main.py --interface income_vip --start_date 20240101 --end_date 20240131
```

检查：
- 数据下载成功
- 日志无错误
- 数据类型正确（Float64, Int64）

### 步骤 4: 清理（测试通过后）

```bash
# 删除 schemas 目录
rm -rf app4/config/schemas

# 删除备份文件（可选）
rm -rf app4/config/interfaces.backup_*
rm -rf app4/config/schemas.backup_*
```

---

## 七、验证清单

- [ ] 合并脚本执行成功
- [ ] 3 个配置文件包含 fields 定义
- [ ] schema_manager.py 代码修改完成
- [ ] income_vip 接口测试通过
- [ ] balancesheet_vip 接口测试通过
- [ ] cashflow_vip 接口测试通过
- [ ] 其他接口（如 daily）正常工作
- [ ] schemas 目录已删除

---

## 八、回滚方案

如果出现问题：

```bash
# 恢复配置文件
cp app4/config/interfaces.backup_*/balancesheet_vip.yaml app4/config/interfaces/
cp app4/config/interfaces.backup_*/cashflow_vip.yaml app4/config/interfaces/
cp app4/config/interfaces.backup_*/income_vip.yaml app4/config/interfaces/

# 恢复代码
git checkout app4/core/schema_manager.py

# 删除备份
rm -rf app4/config/interfaces.backup_*
rm -rf app4/config/schemas.backup_*
```

---

## 九、优势

1. **简化配置**: 只需维护一个配置文件
2. **减少错误**: 避免 schemas 和 interfaces 配置不一致
3. **易于维护**: 字段类型定义和接口配置在同一文件
4. **向后兼容**: 其他接口（无 fields 定义）继续使用自动推断

---

## 十、风险与注意事项

1. **测试覆盖**: 必须测试所有 3 个 VIP 接口
2. **数据验证**: 确认合并后数据类型正确，无精度丢失
3. **备份**: 执行前务必备份所有配置文件
4. **回滚计划**: 如果出现问题，可以快速恢复

---

## 十一、常见问题

### Q: 合并后，其他接口会受影响吗？
A: 不会。只有 3 个 VIP 接口有 fields 定义，其他接口继续使用自动推断。

### Q: 如何验证数据类型是否正确？
A: 查看下载的数据文件，检查数值字段是否为 Float64，整数字段是否为 Int64。

### Q: 可以只合并部分文件吗？
A: 可以。修改 `merge_configs.py` 中的 `merge_files` 列表。

### Q: 备份文件在哪里？
A: 在 `app4/config/` 目录下，格式为 `*.backup_YYYYMMDD_HHMMSS`

### Q: 如果修改后出现问题怎么办？
A: 使用回滚方案，恢复配置文件和代码。

---

## 十二、后续优化建议

1. 为其他重要接口添加 `fields` 定义
2. 添加配置验证工具，检查字段类型定义的完整性
3. 考虑使用 JSON Schema 进行配置验证
4. 文档化字段类型定义规范

---

## 十三、总结

通过将 schemas 合并到 interfaces，我们将配置文件从 2 个目录减少到 1 个，简化了维护工作。核心改动是修改 `schema_manager.py` 的 `load_schema()` 方法，从 interfaces 目录统一读取配置。实施时需要仔细测试，确保数据类型正确性。

### 关键要点

- **只需修改 1 处代码**: `app4/core/schema_manager.py` 的 `load_schema()` 方法
- **自动化脚本**: `merge_configs.py` 处理配置合并
- **测试验证**: 确保所有 VIP 接口正常工作
- **安全回滚**: 完整的备份和回滚方案

---

## 附录：修改步骤清单

1. 阅读**五、实施前检查清单**，确认所有注意事项
2. 运行合并脚本: `python p/2026-1-23/merge_configs.py`
3. 修改 `app4/core/schema_manager.py` 的 `load_schema()` 方法（修正缩进问题）
4. 测试验证: `python app4/main.py --interface income_vip --start_date 20240101 --end_date 20240131`
5. 测试所有 3 个 VIP 接口（income_vip, balancesheet_vip, cashflow_vip）
6. 清理: `rm -rf app4/config/schemas`

完成！