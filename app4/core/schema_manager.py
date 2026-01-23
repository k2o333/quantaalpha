import yaml
import polars as pl
from typing import Dict, Any, List
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