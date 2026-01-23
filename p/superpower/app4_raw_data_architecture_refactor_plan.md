# App4 原始数据 + 转化字段架构重构实施方案

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 重构App4架构中的数据类型处理机制，实现原始数据字段与转化字段分离的架构

**Architecture:** 采用原始数据保持API返回格式，通过配置化的衍生字段提供优化类型的设计

**Tech Stack:** Python, Polars, YAML, App4 Core Components

---

## 任务1: 分析App4架构现状与问题

**文件:**
- 阅读: `app4/core/schema_manager.py`
- 阅读: `app4/core/processor.py`
- 阅读: `app4/config/interfaces/trade_cal.yaml`
- 阅读: `app4/config/interfaces/daily.yaml`

**步骤 1: 分析当前SchemaManager实现**
```python
# 检查当前SchemaManager是否有加载完整字段类型的实现
# 检查是否存在强制类型转换的逻辑
# 检查YAML配置中的columns定义部分
```

**步骤 2: 分析当前配置文件格式**
```yaml
# 检查trade_cal.yaml和daily.yaml中columns部分的定义
# 确认当前columns是否有强制类型定义
```

**步骤 3: 理解当前数据处理流程**
- 了解从API获取数据到保存为Parquet的完整流程
- 识别类型转换发生的具体位置
- 确认当前处理方式带来的问题

**步骤 4: 总结问题点**
- 记录YAML中columns配置强制类型转换的问题
- 记录API返回类型与配置类型不一致的情况
- 记录存储时类型自动推断与配置不一致的问题

**步骤 5: 提交修改**
```bash
git add docs/plans/2026-01-19-app4-raw-data-refactor.md
git commit -m "docs: analyze current state and issues for app4 raw data refactor"
```

## 任务2: 设计新的SchemaManager架构

**文件:**
- 修改: `app4/core/schema_manager.py`
- 修改: `app4/config/interfaces/trade_cal.yaml` (示例)
- 修改: `app4/config/interfaces/daily.yaml` (示例)

**步骤 1: 设计新的SchemaManager类结构**
```python
# 定义新SchemaManager的类结构，专注于衍生字段生成
# 移除强制类型转换逻辑
# 添加衍生字段配置加载方法
```

**步骤 2: 实现衍生字段配置加载**
```python
def load_derived_fields_config(interface_name: str) -> Dict[str, Any]:
    """加载转化字段配置"""
    # 从对应YAML配置中读取derived_fields部分
```

**步骤 3: 实现衍生字段应用逻辑**
```python
def apply_derived_fields(df: pl.DataFrame, interface_name: str) -> pl.DataFrame:
    """应用转化字段到DataFrame"""
    # 根据配置生成衍生字段（如日期、布尔类型等）
```

**步骤 4: 实现DataFrame创建逻辑**
```python
def create_dataframe(data: List[Dict[str, Any]], interface_name: str) -> pl.DataFrame:
    """创建DataFrame - 保存原始数据，然后应用转化字段"""
    # 从原始数据创建DataFrame（自动推断类型）
    # 应用衍生字段
    # 添加系统字段
```

**步骤 5: 提交修改**
```bash
git add app4/core/schema_manager.py
git commit -m "feat: design new schema manager for raw data + derived fields architecture"
```

## 任务3: 实现新的SchemaManager代码

**文件:**
- 修改: `app4/core/schema_manager.py`

**步骤 1: 写失败测试验证**
```python
# 创建测试验证SchemaManager未实现前的行为
def test_schema_manager_before_implementation():
    # 尝试使用尚未实现的新功能
    pass
```

**步骤 2: 运行测试验证失败**
```bash
# 运行测试确认功能未实现
```

**步骤 3: 实现完整的SchemaManager**
```python
import yaml
import polars as pl
from typing import Dict, Any, List
import time
import logging

logger = logging.getLogger(__name__)

class SchemaManager:
    """简化的Schema管理器 - 专注于转化字段生成"""

    @staticmethod
    def load_derived_fields_config(interface_name: str) -> Dict[str, Any]:
        """加载转化字段配置"""
        config_file = f"app4/config/interfaces/{interface_name}.yaml"
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config.get('derived_fields', {})

    @staticmethod
    def apply_derived_fields(df: pl.DataFrame, interface_name: str) -> pl.DataFrame:
        """应用转化字段到DataFrame"""
        derived_config = SchemaManager.load_derived_fields_config(interface_name)

        if not derived_config:
            return df

        # 应用每个转化字段
        for field_name, field_config in derived_config.items():
            source_field = field_config['source']
            target_field = field_name  # 使用配置键作为目标字段名

            try:
                if field_config['type'] == 'date':
                    df = df.with_columns([
                        pl.col(source_field).str.strptime(
                            pl.Date,
                            field_config['format'],
                            strict=False
                        ).alias(target_field)
                    ])

                elif field_config['type'] == 'boolean':
                    # 字符串 "0"/"1" → 布尔值
                    df = df.with_columns([
                        pl.col(source_field).cast(pl.Boolean, strict=False).alias(target_field)
                    ])

                # 可以添加更多转化类型...

            except Exception as e:
                logger.warning(f"Failed to derive field {target_field}: {str(e)}")
                continue

        return df

    @staticmethod
    def create_dataframe(data: List[Dict[str, Any]], interface_name: str) -> pl.DataFrame:
        """创建DataFrame - 保存原始数据，然后应用转化字段"""
        if not data:
            return pl.DataFrame()

        # 1. 直接从原始数据创建DataFrame（自动推断）
        df = pl.DataFrame(data, infer_schema_length=min(len(data), 100))

        # 2. 应用转化字段
        df = SchemaManager.apply_derived_fields(df, interface_name)

        # 3. 添加系统字段
        current_time = int(time.time() * 1000)
        df = df.with_columns([
            pl.lit(current_time).alias('_update_time')
        ])

        return df
```

**步骤 4: 运行测试验证实现**
```bash
# 运行新实现的测试
```

**步骤 5: 提交修改**
```bash
git add app4/core/schema_manager.py
git commit -m "feat: implement new schema manager with raw data + derived fields support"
```

## 任务4: 更新DataProcessor以使用新架构

**文件:**
- 修改: `app4/core/processor.py`

**步骤 1: 分析当前DataProcessor实现**
```python
# 检查当前DataProcessor的数据处理逻辑
# 识别类型转换相关的代码
# 确定如何集成新的SchemaManager
```

**步骤 2: 设计更新后的DataProcessor**
```python
# 保留验证和去重逻辑
# 简化类型处理，使用SchemaManager的创建方法
```

**步骤 3: 实现新的DataProcessor逻辑**
```python
# 更新process_data方法以使用新的SchemaManager
# 确保验证逻辑使用原始字段
# 确保去重逻辑使用原始字段的主键
```

**步骤 4: 编写验证测试**
```python
# 创建测试验证DataProcessor能正确处理原始数据和衍生字段
```

**步骤 5: 提交修改**
```bash
git add app4/core/processor.py
git commit -m "feat: update data processor to use new raw data + derived fields architecture"
```

## 任务5: 重构YAML配置文件格式

**文件:**
- 修改: `app4/config/interfaces/trade_cal.yaml`
- 修改: `app4/config/interfaces/daily.yaml`
- 修改: `app4/config/interfaces/*.yaml`

**步骤 1: 备份现有配置**
```bash
mkdir -p app4/config/interfaces/backup
cp app4/config/interfaces/*.yaml app4/config/interfaces/backup/
```

**步骤 2: 设计配置转换脚本**
```python
# 创建脚本用于转换旧格式YAML到新格式
# 移除columns部分的强制类型定义
# 添加derived_fields部分
```

**步骤 3: 应用配置转换到trade_cal.yaml**
```yaml
# 转换trade_cal.yaml到新格式
# 保留基本配置：name, api_name, description, permissions, parameters, pagination
# 移除columns定义
# 添加derived_fields定义
```

**步骤 4: 应用配置转换到daily.yaml**
```yaml
# 转换daily.yaml到新格式
# 添加日期字段的衍生字段定义
```

**步骤 5: 提交修改**
```bash
git add app4/config/interfaces/trade_cal.yaml app4/config/interfaces/daily.yaml
git commit -m "feat: convert YAML configs to new raw data + derived fields format"
```

## 任务6: 编写配置转换工具

**文件:**
- 创建: `app4/utils/config_converter.py`

**步骤 1: 实现配置转换功能**
```python
# 实现migrate_yaml_config函数
# 实现generate_derived_fields函数
# 添加批量转换功能
```

**步骤 2: 实现迁移YAML配置的逻辑**
```python
import os
import yaml

def migrate_yaml_config(config_path: str):
    """迁移YAML配置到新格式"""
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # 1. 保留基本配置
    basic_keys = ['name', 'api_name', 'description', 'permissions', 'request', 'parameters', 'pagination']
    new_config = {k: v for k, v in config.items() if k in basic_keys}

    # 2. 提取output配置（移除columns）
    if 'output' in config:
        output_config = config['output']
        new_config['output'] = {
            'primary_key': output_config.get('primary_key', []),
            'sort_by': output_config.get('sort_by', [])
        }

    # 3. 根据接口类型生成derived_fields
    interface_name = config['name']
    derived_fields = generate_derived_fields(interface_name, config.get('output', {}))
    if derived_fields:
        new_config['derived_fields'] = derived_fields

    return new_config
```

**步骤 3: 实现衍生字段生成逻辑**
```python
def generate_derived_fields(interface_name: str, old_output: Dict) -> Dict:
    """根据接口类型生成转化字段配置"""
    derived_fields = {}

    # 日期字段转化
    date_fields = [ 'trade_date', 'cal_date', 'ann_date', 'end_date', 'period', 'pretrade_date']
    for field in date_fields:
        if field in old_output.get('columns', {}):
            derived_fields[f"{field}_dt"] = {
                'source': field,
                'type': 'date',
                'format': '%Y%m%d',
                'description': f"日期类型的{field}"
            }

    # 特殊字段转化 - 布尔类型
    if interface_name == 'trade_cal':
        derived_fields['is_open_bool'] = {
            'source': 'is_open',
            'type': 'boolean',
            'description': '布尔类型的is_open，Polars查询性能最优'
        }

    return derived_fields
```

**步骤 4: 测试配置转换工具**
```python
# 验证转换工具能正确处理trade_cal.yaml
# 验证转换结果符合新格式要求
```

**步骤 5: 提交修改**
```bash
git add app4/utils/config_converter.py
git commit -m "feat: add config converter tool for raw data architecture refactoring"
```

## 任务7: 更新Downloader以支持新架构

**文件:**
- 修改: `app4/core/downloader.py`

**步骤 1: 分析当前Downloader的数据处理逻辑**
```python
# 检查GenericDownloader如何创建DataFrame
# 识别需要更新的类型处理部分
```

**步骤 2: 更新DataFrame创建逻辑**
```python
# 更新Downloader中的数据处理逻辑以使用新的SchemaManager
# 确保DataFrame创建使用新架构
```

**步骤 3: 修改DataProcessor集成点**
```python
# 更新Downloader与DataProcessor的集成
# 确保数据流动符合新架构
```

**步骤 4: 更新查询逻辑（如交易日历查询）**
```python
# 确保Downloader中的查询逻辑能正确使用新的原始数据+衍生字段架构
```

**步骤 5: 提交修改**
```bash
git add app4/core/downloader.py
git commit -m "feat: update downloader to support raw data + derived fields architecture"
```

## 任务8: 更新CoverageManager以 support新架构

**文件:**
- 修改: `app4/core/coverage_manager.py`

**步骤 1: 分析当前CoverageManager的数据过滤逻辑**
```python
# 检查CoverageManager如何处理日期过滤
# 识别需要更新的类型处理部分
```

**步骤 2: 更新日期字段处理逻辑**
```python
# 确保CoverageManager能正确处理原始日期字符串和衍生日期字段
```

**步骤 3: 更新数据去重逻辑**
```python
# 确保去重逻辑基于原始字段
```

**步骤 4: 测试覆盖率管理功能**
```python
# 验证新的架构不影响覆盖率检查功能
```

**步骤 5: 提交修改**
```bash
git add app4/core/coverage_manager.py
git commit -m "feat: update coverage manager for new raw data architecture"
```

## 任务9: 编写全面的测试套件

**文件:**
- 创建: `test/test_app4_raw_data_architecture.py`

**步骤 1: 实现新架构测试**
```python
def test_new_architecture():
    """测试新架构的正确性"""
    # 1. 测试trade_cal接口
    from app4.core.downloader import GenericDownloader
    from app4.core.schema_manager import SchemaManager

    downloader = GenericDownloader()

    # 下载数据
    data = downloader.download_interface('trade_cal', start_date='20240101', end_date='20240103')

    # 检查原始字段（保持字符串类型）
    assert all(isinstance(item['is_open'], str) for item in data)
    assert all(item['is_open'] in ['0', '1'] for item in data)

    # 创建DataFrame
    df = SchemaManager.create_dataframe(data, 'trade_cal')

    # 检查衍生字段
    assert 'is_open_bool' in df.columns
    assert 'cal_date_dt' in df.columns
    assert 'pretrade_date_dt' in df.columns

    # 检查类型
    assert df['is_open'].dtype == pl.Utf8  # 原始字段：字符串
    assert df['is_open_bool'].dtype == pl.Boolean  # 衍生字段：布尔
    assert df['cal_date_dt'].dtype == pl.Date

    print("✅ 新架构测试通过")

    # 2. 测试数据一致性
    original_count = len([item for item in data if item['is_open'] == "1"])
    derived_count = df.filter(pl.col('is_open_bool')).height

    assert original_count == derived_count
    print("✅ 数据一致性测试通过")
```

**步骤 2: 添加性能对比测试**
```python
def benchmark_performance():
    """性能对比测试"""
    import time

    # 测试旧方案
    start_time = time.time()
    # 旧方案代码...
    old_time = time.time() - start_time

    # 测试新方案
    start_time = time.time()
    # 新方案代码...
    new_time = time.time() - start_time

    print(f"旧方案耗时: {old_time:.3f}s")
    print(f"新方案耗时: {new_time:.3f}s")
    print(f"性能差异: {((new_time - old_time) / old_time * 100):.2f}%")
```

**步骤 3: 添加类型一致性测试**
```python
def test_type_consistency():
    """测试类型一致性"""
    # 验证API返回类型与保存类型一致
    # 验证衍生字段正确生成
```

**步骤 4: 运行测试验证**
```bash
# 运行完整的测试套件
```

**步骤 5: 提交修改**
```bash
git add test/test_app4_raw_data_architecture.py
git commit -m "test: add comprehensive test suite for raw data architecture"
```

## 任务10: 迁移所有YAML配置文件

**文件:**
- 修改: `app4/config/interfaces/*.yaml`

**步骤 1: 应用配置转换到所有接口**
```bash
python app4/utils/config_converter.py --migrate-all
```

**步骤 2: 验证转换后的配置文件**
```bash
# 检查所有配置文件是否符合新格式
# 验证derived_fields部分是否正确生成
```

**步骤 3: 手动检查重要接口配置**
```bash
# 检查trade_cal.yaml, income.yaml, balance.yaml等重要接口
# 确保derived_fields配置正确
```

**步骤 4: 更新配置验证逻辑**
```python
# 确保配置验证逻辑能正确处理新格式
```

**步骤 5: 提交修改**
```bash
git add app4/config/interfaces/*.yaml
git commit -m "feat: migrate all interface configs to new raw data format"
```

## 任务11: 更新文档和注释

**文件:**
- 修改: `app4/README.md`
- 修改: `app4/core/schema_manager.py` 注释
- 修改: `app4/core/processor.py` 注释

**步骤 1: 更新README文档**
```markdown
# 更新README说明新的原始数据+衍生字段架构
# 说明如何使用衍生字段进行查询优化
```

**步骤 2: 更新SchemaManager文档字符串**
```python
# 为SchemaManager类和方法添加详细文档
```

**步骤 3: 更新处理器文档**
```python
# 为DataProcessor更新文档说明新架构
```

**步骤 4: 添加使用示例**
```python
# 添加如何使用衍生字段的示例代码
```

**步骤 5: 提交修改**
```bash
git add app4/README.md app4/core/schema_manager.py app4/core/processor.py
git commit -m "docs: update documentation for new raw data architecture"
```

## 任务12: 进行完整集成测试

**文件:**
- 创建: `test/integration_test_app4_new_architecture.py`

**步骤 1: 实现端到端测试**
```python
def test_end_to_end_flow():
    """端到端测试验证新架构"""
    # 测试从配置加载到数据保存的完整流程
    # 验证数据类型的正确性
    # 验证衍生字段的生成
```

**步骤 2: 测试多个接口类型**
```python
def test_multiple_interfaces():
    """测试多个接口是否都能正确处理"""
    # 测试trade_cal, daily, income等不同接口
```

**步骤 3: 验证查询性能**
```python
def test_query_performance():
    """验证衍生字段查询性能提升"""
    # 比较使用原始字段和衍生字段的查询性能
```

**步骤 4: 测试错误处理**
```python
def test_error_handling():
    """测试新架构的错误处理能力"""
    # 测试无效衍生字段配置的处理
    # 测试类型转换失败的处理
```

**步骤 5: 提交修改**
```bash
git add test/integration_test_app4_new_architecture.py
git commit -m "test: add integration tests for new architecture"
```

## 任务13: 性能基准测试

**文件:**
- 创建: `benchmark/benchmark_new_architecture.py`

**步骤 1: 实现性能基准测试**
```python
# 实现新旧架构的性能对比测试
# 包括数据处理速度、内存使用、查询性能等
```

**步骤 2: 比较数据处理性能**
```python
# 对比新旧架构在数据处理方面的性能差异
```

**步骤 3: 比较查询性能**
```python
# 验证衍生字段（如is_open_bool）的查询性能提升
```

**步骤 4: 总结性能报告**
```python
# 生成性能基准测试报告
```

**步骤 5: 提交修改**
```bash
git add benchmark/benchmark_new_architecture.py
git commit -m "perf: add performance benchmarks for new architecture"
```

## 任务14: 创建迁移指南文档

**文件:**
- 创建: `docs/migration_guide_raw_data_architecture.md`

**步骤 1: 编写架构变化说明**
```markdown
# 详细说明新旧架构的差异
# 解释为什么需要这次重构
```

**步骤 2: 提供查询使用指南**
```markdown
# 说明如何使用新架构的衍生字段
# 提供优化查询的示例
```

**步骤 3: 提供开发者指南**
```markdown
# 指导开发者如何适应新架构
# 说明配置文件的变化
```

**步骤 4: 提供回滚方案**
```markdown
# 说明如果需要回滚的步骤
# 提供回滚脚本
```

**步骤 5: 提交修改**
```bash
git add docs/migration_guide_raw_data_architecture.md
git commit -m "docs: add migration guide for new raw data architecture"
```

## 任务15: 最终验证和部署准备

**文件:**
- 检查: 所有相关文件

**步骤 1: 运行完整测试套件**
```bash
# 运行所有测试确保新架构正常工作
```

**步骤 2: 验证数据完整性**
```bash
# 验证转换后的数据与原始数据一致性
```

**步骤 3: 性能验证**
```bash
# 验证性能提升是否达到预期
```

**步骤 4: 文档完整性检查**
```bash
# 确保所有相关文档都已更新
```

**步骤 5: 提交最终修改**
```bash
git add .
git commit -m "feat: complete app4 raw data architecture refactoring"
```

---

**更新记录:**
- v1.0 (2026-01-19)：初始版本，创建App4原始数据+转化字段架构重构实施方案