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

            # 检查源字段是否存在于DataFrame中
            if source_field not in df.columns:
                logger.warning(f"Failed to derive field {target_field}: unable to find column '{source_field}'; valid columns: {list(df.columns)}")
                continue

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
                logger.warning(f"Failed to derive field {target_field} from {source_field}: {str(e)}")
                continue

        return df

    @staticmethod
    def _clean_empty_strings(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """清理空字符串，将空字符串转换为 None"""
        cleaned_data = []
        for record in data:
            cleaned_record = {}
            for key, value in record.items():
                # 将空字符串转换为 None
                if value == '':
                    cleaned_record[key] = None
                else:
                    cleaned_record[key] = value
            cleaned_data.append(cleaned_record)
        return cleaned_data

    @staticmethod
    def create_dataframe(data: List[Dict[str, Any]], interface_name: str) -> pl.DataFrame:
        """混合策略：先尝试预定义schema，失败后回退到智能推断，再回退到宽松模式"""
        if not data:
            return pl.DataFrame()

        # 预处理：清理空字符串
        data = SchemaManager._clean_empty_strings(data)
        logger.debug(f"清理空字符串后，数据量: {len(data)}")

        try:
            # 尝试1：使用预定义schema
            predefined_schema = SchemaManager.load_schema(interface_name)
            if predefined_schema:
                logger.debug(f"使用预定义 schema，字段数: {len(predefined_schema)}")
                logger.debug(f"Schema 字段: {list(predefined_schema.keys())}")

                # 先尝试使用预定义schema创建DataFrame
                df = pl.DataFrame(data, schema=predefined_schema)
                logger.debug(f"成功创建 DataFrame，记录数: {len(df)}")

            else:
                # 尝试2：智能推断，根据数据量动态调整，增加推断长度
                data_length = len(data)
                infer_length = min(data_length, 10000 if data_length > 10000 else data_length)
                logger.debug(f"使用自动推断，推断长度: {infer_length}")
                df = pl.DataFrame(data, infer_schema_length=infer_length)
                logger.debug(f"成功创建 DataFrame，记录数: {len(df)}")

            # 应用衍生字段
            df = SchemaManager.apply_derived_fields(df, interface_name)

        except Exception as e:
            logger.error(f"Schema推断失败: {str(e)}")
            logger.error(f"尝试回退到宽松模式...")

            # 回退方案：先使用智能推断创建DataFrame，然后尝试应用schema
            try:
                # 使用更大的推断长度来更好地识别数据类型
                df = pl.DataFrame(data, infer_schema_length=min(len(data), 50000))
                logger.debug(f"使用智能推断创建 DataFrame 成功，记录数: {len(df)}")

                # 尝试将DataFrame转换为预定义schema的类型
                predefined_schema = SchemaManager.load_schema(interface_name)
                if predefined_schema:
                    # 对于每个字段，尝试转换类型，如果失败则跳过
                    for col_name, col_type in predefined_schema.items():
                        if col_name in df.columns:
                            try:
                                df = df.with_columns([
                                    pl.col(col_name).cast(col_type, strict=False).alias(col_name)
                                ])
                            except Exception as cast_error:
                                logger.warning(f"无法将列 '{col_name}' 转换为 {col_type}: {str(cast_error)}")
                                # 如果严格转换失败，尝试更宽松的方式
                                try:
                                    # 对于数值类型，先转为字符串再转为目标类型，可以处理一些特殊情况
                                    if col_type in [pl.Float64, pl.Int64]:
                                        df = df.with_columns([
                                            pl.col(col_name).cast(pl.String, strict=False)
                                            .str.replace('None', '')  # 处理字符串形式的None
                                            .str.replace('', 'null')  # 临时替换空字符串为null
                                            .cast(col_type, strict=False)
                                            .alias(col_name)
                                        ])
                                except Exception as loose_cast_error:
                                    logger.warning(f"宽松转换也失败 '{col_name}': {str(loose_cast_error)}")

                df = SchemaManager.apply_derived_fields(df, interface_name)

            except Exception as e2:
                logger.error(f"回退方案也失败: {str(e2)}")
                logger.error("警告：数据可能包含类型不匹配的情况，使用自动推断模式")

                # 最终回退：使用非常大的推断长度
                df = pl.DataFrame(data, infer_schema_length=len(data))
                df = SchemaManager.apply_derived_fields(df, interface_name)

        # 添加系统字段
        current_time = int(time.time() * 1000)
        df = df.with_columns([
            pl.lit(current_time).alias('_update_time')
        ])

        return df

    @staticmethod
    def create_dataframe_safe(data: List[Dict[str, Any]], interface_name: str) -> pl.DataFrame:
        """安全创建DataFrame的方法，专门用于处理类型不匹配问题"""
        if not data:
            return pl.DataFrame()

        # 预处理：清理空字符串
        data = SchemaManager._clean_empty_strings(data)
        logger.debug(f"安全模式：清理空字符串后，数据量: {len(data)}")

        try:
            # 尝试使用非常大的推断长度来避免类型冲突
            df = pl.DataFrame(data, infer_schema_length=min(len(data), 100000))
            logger.debug(f"安全模式：成功创建 DataFrame，记录数: {len(df)}")

            # 应用衍生字段
            df = SchemaManager.apply_derived_fields(df, interface_name)

            # 添加系统字段
            current_time = int(time.time() * 1000)
            df = df.with_columns([
                pl.lit(current_time).alias('_update_time')
            ])

            return df
        except Exception as e:
            logger.error(f"安全模式创建DataFrame也失败: {str(e)}")
            # 最后的最后的回退：逐行处理数据
            try:
                # 先创建一个空DataFrame，然后逐步添加数据
                if data:
                    # 获取第一行数据的列名
                    first_row = data[0]
                    # 创建一个包含所有列的空DataFrame
                    df = pl.DataFrame([first_row]).clear()

                    # 分批处理数据，避免一次性处理大量数据导致内存问题
                    batch_size = 1000
                    for i in range(0, len(data), batch_size):
                        batch = data[i:i+batch_size]
                        try:
                            batch_df = pl.DataFrame(batch, infer_schema_length=len(batch))
                            df = pl.concat([df, batch_df])
                        except Exception as batch_error:
                            logger.warning(f"处理批次 {i//batch_size} 时出错: {str(batch_error)}")
                            # 尝试使用更小的批次
                            for row in batch:
                                try:
                                    row_df = pl.DataFrame([row])
                                    df = pl.concat([df, row_df])
                                except Exception as row_error:
                                    logger.warning(f"跳过单行数据，因为错误: {str(row_error)}")
                                    continue

                    # 应用衍生字段
                    df = SchemaManager.apply_derived_fields(df, interface_name)

                    # 添加系统字段
                    current_time = int(time.time() * 1000)
                    df = df.with_columns([
                        pl.lit(current_time).alias('_update_time')
                    ])

                    return df
            except Exception as final_error:
                logger.error(f"最终回退方案也失败: {str(final_error)}")
                # 返回空DataFrame作为最后的回退
                return pl.DataFrame()

    @staticmethod
    def load_schema(interface_name: str) -> Optional[Dict[str, Any]]:
        """加载预定义schema - 从 interfaces 目录统一读取

        合并后，所有字段类型定义都保存在 interfaces 目录的配置文件中。
        该方法从接口配置中读取 fields 定义，用于创建精确类型的 DataFrame。
        """
        config_file = SchemaManager._get_config_file_path(interface_name)
        if os.path.exists(config_file):
            import yaml
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                fields = config.get('fields')
                # 如果配置中没有fields键，或者fields为None，或者fields为空字典，则返回None
                if fields is None or (isinstance(fields, dict) and len(fields) == 0):
                    return None

                # 将字符串类型转换为Polars类型
                converted_fields = {}
                type_mapping = {
                    'string': pl.String,
                    'String': pl.String,
                    'int': pl.Int64,
                    'Int': pl.Int64,
                    'Int64': pl.Int64,
                    'int64': pl.Int64,
                    'float': pl.Float64,
                    'Float': pl.Float64,
                    'Float64': pl.Float64,
                    'float64': pl.Float64,
                    'bool': pl.Boolean,
                    'Boolean': pl.Boolean,
                    'date': pl.Date,
                    'Date': pl.Date,
                    'datetime': pl.Datetime,
                    'Datetime': pl.Datetime,
                    'object': pl.Object,
                    'Object': pl.Object,
                    'binary': pl.Binary,
                    'Binary': pl.Binary,
                }

                for field_name, field_type in fields.items():
                    if isinstance(field_type, str):
                        if field_type in type_mapping:
                            converted_fields[field_name] = type_mapping[field_type]
                        else:
                            # 如果类型不匹配，使用String作为默认类型
                            logger.warning(f"Unknown field type '{field_type}' for field '{field_name}', using String")
                            converted_fields[field_name] = pl.String
                    else:
                        converted_fields[field_name] = field_type

                return converted_fields
        return None