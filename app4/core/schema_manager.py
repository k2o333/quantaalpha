import yaml
import polars as pl
from typing import Dict, Any, List, Optional
import time
import logging
import os

logger = logging.getLogger(__name__)

class SchemaManager:
    """简化的Schema管理器 - 专注于转化字段生成，保留原始数据格式

    新架构特点：
    - 保留API返回的原始数据格式，确保数据完整性
    - 通过derived_fields配置提供优化的衍生字段（如日期类型、布尔类型等）
    - 分离原始数据和转化字段，实现灵活的数据访问模式
    - 原始字段保持API返回的类型，衍生字段提供查询优化类型
    """

    @staticmethod
    def _get_config_file_path(interface_name: str) -> str:
        """获取接口配置文件的路径"""
        # 假设配置文件在 config/interfaces/ 目录下
        config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', 'interfaces')
        config_file = os.path.join(config_dir, f"{interface_name}.yaml")
        return config_file

    @staticmethod
    def load_derived_fields_config(interface_name: str) -> Dict[str, Any]:
        """加载转化字段配置"""
        config_file = SchemaManager._get_config_file_path(interface_name)
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
                        pl.when(pl.col(source_field).cast(pl.String, strict=False) == "1")
                        .then(True)
                        .otherwise(False)
                        .alias(target_field)
                    ])

                # 可以添加更多转化类型...

            except Exception as e:
                logger.warning(f"Failed to derive field {target_field}: {str(e)}")
                continue

        return df

    @staticmethod
    def create_dataframe(data: List[Dict[str, Any]], interface_name: str) -> pl.DataFrame:
        """混合策略：先尝试预定义schema，失败后回退到智能推断，再回退到宽松模式"""
        if not data:
            return pl.DataFrame()

        try:
            # 尝试1：使用预定义schema
            predefined_schema = SchemaManager.load_schema(interface_name)
            if predefined_schema:
                df = pl.DataFrame(data, schema=predefined_schema)
            else:
                # 尝试2：智能推断，根据数据量动态调整，增加推断长度
                data_length = len(data)
                infer_length = min(data_length, 10000 if data_length > 10000 else data_length)
                df = pl.DataFrame(data, infer_schema_length=infer_length)

            # 应用衍生字段
            df = SchemaManager.apply_derived_fields(df, interface_name)

        except Exception as e:
            logger.error(f"Schema推断失败: {str(e)}")
            logger.error(f"尝试回退到宽松模式...")

            # 回退方案：全部转为字符串，后续再处理类型转换
            # 先尝试增加推断长度
            try:
                df = pl.DataFrame(data, infer_schema_length=min(len(data), 20000))
                df = SchemaManager.apply_derived_fields(df, interface_name)
            except Exception as e2:
                logger.error(f"回退方案也失败: {str(e2)}")
                logger.error("警告：数据可能包含类型不匹配的情况")
                # 继续使用完整的数据长度以确保所有数据都被包含
                df = pl.DataFrame(data, infer_schema_length=len(data))
                df = SchemaManager.apply_derived_fields(df, interface_name)

            # 应用衍生字段
            df = SchemaManager.apply_derived_fields(df, interface_name)

        # 添加系统字段
        current_time = int(time.time() * 1000)
        df = df.with_columns([
            pl.lit(current_time).alias('_update_time')
        ])

        return df

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