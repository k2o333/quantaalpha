import polars as pl
from typing import Dict, Any, List, Optional, Set
import logging
import yaml
import os

logger = logging.getLogger(__name__)

class SchemaManager:
    """Schema管理器 - 从接口配置动态读取schema，或从数据推断"""

    @staticmethod
    def _get_config_file_path(interface_name: str) -> Optional[str]:
        """获取接口配置文件的路径"""
        # 假设配置文件在 config/interfaces/ 目录下
        config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', 'interfaces')
        config_file = os.path.join(config_dir, f"{interface_name}.yaml")

        if os.path.exists(config_file):
            return config_file
        return None

    @staticmethod
    def _load_schema_from_config(interface_name: str) -> Optional[Dict[str, pl.DataType]]:
        """从接口配置文件动态加载schema"""
        config_file = SchemaManager._get_config_file_path(interface_name)

        if not config_file:
            logger.debug(f"Config file not found for {interface_name}")
            return None

        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            # 获取output.columns配置
            columns_config = config.get('output', {}).get('columns', {})

            if not columns_config:
                logger.debug(f"No columns defined in config for {interface_name}")
                return None

            # 将配置中的类型映射到Polars类型
            schema = {}
            for col_name, col_config in columns_config.items():
                # 跳过内部字段（以_开头）
                if col_name.startswith('_'):
                    continue

                col_type = col_config.get('type', 'string')
                # 映射类型
                if col_type == 'string':
                    schema[col_name] = pl.Utf8
                elif col_type == 'float':
                    schema[col_name] = pl.Float64
                elif col_type == 'int':
                    schema[col_name] = pl.Int64
                elif col_type == 'date':
                    schema[col_name] = pl.Utf8  # 日期保持字符串格式
                else:
                    # 默认使用字符串
                    schema[col_name] = pl.Utf8

            logger.debug(f"Loaded schema from config for {interface_name}: {len(schema)} columns")
            return schema

        except Exception as e:
            logger.warning(f"Failed to load schema from config for {interface_name}: {str(e)}")
            return None

    @staticmethod
    def _infer_schema_from_data(data: List[Dict[str, Any]]) -> Optional[Dict[str, pl.DataType]]:
        """从实际数据推断schema（当YAML中没有定义schema时）"""
        if not data:
            return None

        try:
            # 收集所有字段名
            all_fields: Set[str] = set()
            for row in data:
                all_fields.update(row.keys())

            # 推断每个字段的类型
            schema = {}
            for field_name in all_fields:
                # 跳过内部字段（以_开头）
                if field_name.startswith('_'):
                    continue

                # 从前100行推断类型
                sample_values = []
                for row in data[:100]:
                    if field_name in row and row[field_name] is not None:
                        sample_values.append(row[field_name])

                if not sample_values:
                    # 没有非空值，使用字符串
                    schema[field_name] = pl.Utf8
                    continue

                # 推断类型
                field_type = type(sample_values[0])
                is_float = any(isinstance(v, float) for v in sample_values)
                is_int = any(isinstance(v, int) for v in sample_values)
                is_str = any(isinstance(v, str) for v in sample_values)

                if is_float and not is_str:
                    schema[field_name] = pl.Float64
                elif is_int and not is_str:
                    schema[field_name] = pl.Int64
                else:
                    # 默认使用字符串（包括混合类型）
                    schema[field_name] = pl.Utf8

            logger.info(f"Inferred schema from data for {len(schema)} columns (YAML schema not defined)")
            return schema

        except Exception as e:
            logger.warning(f"Failed to infer schema from data: {str(e)}")
            return None

    @classmethod
    def get_schema(cls, interface_name: str, data: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, pl.DataType]]:
        """
        获取接口的schema

        优先级：
        1. 从YAML配置文件读取（如果有定义）
        2. 从实际数据推断（如果YAML中没有定义）

        Args:
            interface_name: 接口名称
            data: 实际数据（用于schema推断）

        Returns:
            schema字典，如果无法获取则返回None
        """
        # 方案1：从YAML配置加载
        schema = cls._load_schema_from_config(interface_name)
        if schema:
            return schema

        # 方案2：从数据推断（当YAML中没有定义schema时）
        if data:
            schema = cls._infer_schema_from_data(data)
            if schema:
                return schema

        # 两种方式都失败
        logger.warning(f"Failed to get schema for {interface_name}")
        return None

    @classmethod
    def create_dataframe(cls, data: List[Dict[str, Any]], interface_name: str) -> pl.DataFrame:
        """
        创建DataFrame，优先使用预定义schema，没有则从数据推断

        Args:
            data: 原始数据列表
            interface_name: 接口名称

        Returns:
            处理后的 DataFrame
        """
        if not data:
            return pl.DataFrame()

        # 获取schema（优先从YAML，否则从数据推断）
        schema = cls.get_schema(interface_name, data)

        if schema:
            # 使用预定义schema或推断的schema创建DataFrame
            try:
                # 只保留schema中定义的列
                filtered_data = []
                for row in data:
                    filtered_row = {}
                    for col_name, col_type in schema.items():
                        if col_name in row:
                            filtered_row[col_name] = row[col_name]
                        else:
                            # 缺失列使用null填充
                            filtered_row[col_name] = None
                    filtered_data.append(filtered_row)

                # 使用schema创建DataFrame
                df = pl.DataFrame(filtered_data, schema=schema)

                # 记录schema来源
                if cls._load_schema_from_config(interface_name):
                    logger.debug(f"Created DataFrame with YAML-defined schema for {interface_name}: {len(schema)} columns")
                else:
                    logger.info(f"Created DataFrame with inferred schema for {interface_name}: {len(schema)} columns")

                return df
            except Exception as e:
                logger.warning(f"Failed to create DataFrame with schema: {str(e)}, falling back to auto inference")

        # 回退到完全自动推断
        logger.debug(f"Using auto-inferred schema for {interface_name}")
        return pl.DataFrame(data)

    @classmethod
    def create_dataframe_lazy(cls, data: List[Dict[str, Any]], interface_name: str) -> pl.DataFrame:
        """延迟创建DataFrame - 先保持原始数据格式，需要时再转换"""
        if not data:
            return pl.DataFrame()

        # 对于大数据集，先使用轻量级方式创建
        if len(data) > 1000:
            # 分批处理，避免一次性类型推断
            batch_size = 1000
            batches = []
            for i in range(0, len(data), batch_size):
                batch = data[i:i+batch_size]
                batch_df = pl.DataFrame(batch, infer_schema_length=len(batch))
                batches.append(batch_df)

            # 合并所有批次
            if batches:
                return pl.concat(batches)
            else:
                return pl.DataFrame()
        else:
            # 小数据集直接使用预定义schema
            return cls.create_dataframe(data, interface_name)