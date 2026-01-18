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
        创建DataFrame，保持原始数据类型，实现"接口给什么就保存什么"

        Args:
            data: 原始数据列表
            interface_name: 接口名称

        Returns:
            处理后的 DataFrame
        """
        if not data:
            return pl.DataFrame()

        # 新策略：优先使用智能推断，保持原始数据类型
        schema = cls._smart_infer_schema(data, interface_name)

        if schema:
            try:
                # 使用智能推断的schema创建DataFrame，保持原始类型
                df = pl.DataFrame(data, schema=schema)
                logger.info(f"Created DataFrame with smart schema for {interface_name}: {len(schema)} columns")
                return df
            except Exception as e:
                logger.warning(f"Failed to create DataFrame with smart schema for {interface_name}: {str(e)}")
                # 回退到完全自动推断
                return pl.DataFrame(data, infer_schema_length=len(data))
        else:
            # 使用完全自动推断，保持原始类型
            logger.debug(f"Using auto-inferred schema for {interface_name}")
            return pl.DataFrame(data, infer_schema_length=len(data))

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

    @classmethod
    def _smart_infer_schema(cls, data: List[Dict[str, Any]], interface_name: str) -> Optional[Dict[str, pl.DataType]]:
        """
        智能类型推断，结合配置和数据内容，实现"接口给什么就保存什么"
        
        Args:
            data: 原始数据
            interface_name: 接口名称
            
        Returns:
            智能推断的schema
        """
        if not data:
            return None
            
        # 收集所有字段名
        all_fields = set()
        for row in data:
            all_fields.update(row.keys())
        
        # 获取配置中的类型定义作为参考
        config_schema = cls._load_schema_from_config(interface_name) or {}
        
        # 智能推断每个字段的类型
        schema = {}
        for field_name in all_fields:
            # 跳过内部字段
            if field_name.startswith('_'):
                continue
                
            # 采样数据进行类型推断
            sample_values = []
            for row in data[:100]:  # 采样前100行
                if field_name in row and row[field_name] is not None:
                    sample_values.append(row[field_name])
            
            if not sample_values:
                # 没有非空值，使用字符串
                schema[field_name] = pl.Utf8
                continue
            
            # 智能类型选择
            schema[field_name] = cls._choose_best_type(field_name, sample_values, config_schema.get(field_name))
        
        return schema
    
    @staticmethod
    def _choose_best_type(field_name: str, sample_values: List[Any], config_type: Optional[pl.DataType]) -> pl.DataType:
        """
        为字段选择最佳数据类型，优先保持原始数据的自然类型
        
        Args:
            field_name: 字段名
            sample_values: 采样值
            config_type: 配置中定义的类型
            
        Returns:
            最佳数据类型
        """
        # 特殊字段的智能处理规则
        if field_name in ['is_open', 'list_status']:
            # 这些字段应该是整数，即使API返回字符串
            # 检查样本值是否为整数（字符串或整数类型）
            if all(isinstance(v, (int, str)) and str(v).isdigit() for v in sample_values):
                return pl.Int64
            else:
                return pl.Float64
        
        if field_name.endswith(('_date', 'time')):
            # 日期相关字段保持字符串，让后续处理决定
            return pl.Utf8
        
        # 基于样本值的类型推断
        first_value = sample_values[0]
        
        # 如果是整数
        if isinstance(first_value, int) and not isinstance(first_value, bool):
            return pl.Int64
        
        # 如果是浮点数
        if isinstance(first_value, float):
            return pl.Float64
        
        # 如果是字符串
        if isinstance(first_value, str):
            # 检查是否为数字字符串
            try:
                # 尝试转换为整数
                int(first_value)
                # 检查是否所有样本都是整数
                if all(isinstance(v, str) and v.isdigit() or (isinstance(v, (int, float)) and v == int(v)) for v in sample_values):
                    return pl.Int64
            except (ValueError, TypeError):
                pass
            
            try:
                # 尝试转换为浮点数
                float(first_value)
                # 检查是否所有样本都是数字
                if all((isinstance(v, str) and SchemaManager._is_number(v)) or isinstance(v, (int, float)) for v in sample_values):
                    return pl.Float64
            except (ValueError, TypeError):
                pass
            
            # 默认字符串
            return pl.Utf8
        
        # 其他类型保持原样或使用字符串
        return pl.Utf8
    
    @staticmethod
    def _is_number(s: str) -> bool:
        """检查字符串是否为数字"""
        try:
            float(s)
            return True
        except ValueError:
            return False