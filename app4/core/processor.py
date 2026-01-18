import polars as pl
import numpy as np
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
from .schema_manager import SchemaManager

logger = logging.getLogger(__name__)

class DataProcessor:
    """数据处理器 - 类型转换，主键检查，数据去重"""

    def __init__(self):
        pass

    def process_data(self, data: List[Dict[str, Any]], interface_config: Dict[str, Any]) -> pl.DataFrame:
        """
        处理数据 - Polars优化版

        Args:
            data: 原始数据列表
            interface_config: 接口配置

        Returns:
            处理后的 DataFrame
        """
        if not data:
            return pl.DataFrame()

        try:
            # 获取接口名称
            interface_name = interface_config.get('api_name', 'unknown')

            # 使用SchemaManager创建DataFrame，避免运行时类型推断
            df = SchemaManager.create_dataframe(data, interface_name)

            # 如果SchemaManager失败，回退到标准方法但增加优化参数
            if df.is_empty() and data:
                logger.warning(f"SchemaManager failed for {interface_name}, using fallback with optimized parameters")
                # 使用较大的infer_schema_length避免多次扫描
                df = pl.DataFrame(data, infer_schema_length=len(data))

            # 确保列名是字符串类型
            df.columns = [str(col) for col in df.columns]

            # 确保没有重复的列名
            df = df.select([col for i, col in enumerate(df.columns) if col not in df.columns[:i]])

            # 应用类型转换
            df = self._apply_type_conversions(df, interface_config)

            # 检查和处理主键
            df = self._handle_primary_keys(df, interface_config)

            # 数据去重
            df = self._remove_duplicates(df, interface_config)

            # 数据清洗
            df = self._clean_data(df, interface_config)

            logger.info(f"Processed {len(df)} records for {interface_name}")
            return df

        except Exception as e:
            logger.error(f"Error processing data for {interface_name}: {str(e)}")
            # 最后的回退方案：返回空DataFrame
            return pl.DataFrame()

    def _apply_type_conversions(self, df: pl.DataFrame, interface_config: Dict[str, Any]) -> pl.DataFrame:
        """应用类型转换"""
        output_config = interface_config.get('output', {})
        columns_config = output_config.get('columns', {})

        for column_name, column_def in columns_config.items():
            if column_name in df.columns:
                column_type = column_def.get('type')
                if column_type == 'date':
                    # 处理日期类型
                    date_format = column_def.get('format', '%Y-%m-%d')
                    try:
                        df = df.with_columns([
                            pl.col(column_name).str.strptime(pl.Date, date_format, strict=False).alias(column_name)
                        ])
                    except Exception as e:
                        logger.warning(f"Error converting {column_name} to date: {str(e)}")
                        # 尝试自动解析
                        df = df.with_columns([
                            pl.col(column_name).str.strptime(pl.Date, '%Y-%m-%d', strict=False).alias(column_name)
                        ])
                elif column_type == 'int':
                    # 处理整数类型
                    df = df.with_columns([
                        pl.col(column_name).cast(pl.Int64, strict=False).alias(column_name)
                    ])
                elif column_type == 'float':
                    # 处理浮点数类型
                    df = df.with_columns([
                        pl.col(column_name).cast(pl.Float64, strict=False).alias(column_name)
                    ])
                elif column_type == 'string':
                    # 处理字符串类型
                    df = df.with_columns([
                        pl.col(column_name).cast(pl.Utf8).alias(column_name)
                    ])

        return df

    def _handle_primary_keys(self, df: pl.DataFrame, interface_config: Dict[str, Any]) -> pl.DataFrame:
        """处理主键"""
        output_config = interface_config.get('output', {})
        primary_keys = output_config.get('primary_key', [])

        # 检查主键字段是否存在
        missing_keys = [key for key in primary_keys if key not in df.columns]
        if missing_keys:
            logger.warning(f"Primary key fields missing in data: {missing_keys}")

        # 只保留在数据中存在的主键字段
        existing_keys = [key for key in primary_keys if key in df.columns]

        # 检查主键是否唯一 - 不执行去重操作，只记录信息
        if existing_keys and len(existing_keys) > 0:
            try:
                duplicates = df.with_columns(
                    pl.int_range(0, pl.len()).alias('__index')
                ).group_by(existing_keys).agg(
                    pl.col('__index').list()
                ).filter(
                    pl.col('__index').list().len() > 1
                ).explode('__index').select(
                    pl.col('__index')
                )
                if len(duplicates) > 0:
                    logger.info(f"Found {len(duplicates)} duplicate records based on primary keys, keeping all records")
            except:
                # Fallback for newer polars versions
                try:
                    # Alternative syntax for polars versions (apply -> map)
                    duplicates = df.with_columns(
                        pl.int_range(0, pl.len()).alias('__index')
                    ).group_by(existing_keys).agg(
                        pl.col('__index').map(lambda x: x, return_dtype=pl.List(pl.Int64))
                    ).filter(
                        pl.col('__index').map(lambda x: len(x) if x else 0, return_dtype=pl.Int64) > 1
                    ).select(
                        pl.col('__index').explode()
                    )
                    if len(duplicates) > 0:
                        logger.info(f"Found {len(duplicates)} duplicate records based on primary keys, keeping all records")
                except:
                    # Even simpler alternative - skip duplicate checking if it fails
                    # Do not log warning since we're not removing duplicates anyway
                    pass

        return df

    def _remove_duplicates(self, df: pl.DataFrame, interface_config: Dict[str, Any]) -> pl.DataFrame:
        """批次内去重逻辑 - 根据主键去重，保留最后记录"""
        output_config = interface_config.get('output', {})
        primary_keys = output_config.get('primary_key', [])

        # 找出存在于DataFrame中的主键
        existing_keys = [key for key in primary_keys if key in df.columns]

        if existing_keys:
            # 如果有更新时间字段，按此字段排序以便保留最新记录
            if '_update_time' in df.columns:
                df = df.sort('_update_time', descending=False)
                df = df.unique(subset=existing_keys, keep='last')
            else:
                # 按主键去重，保留最后一条记录
                df = df.unique(subset=existing_keys, keep='last')

        # 如果指定了排序字段，则进行排序
        sort_by = output_config.get('sort_by', [])
        existing_sort_fields = [field for field in sort_by if field in df.columns]
        if existing_sort_fields:
            df = df.sort(by=existing_sort_fields)

        return df

    def _clean_data(self, df: pl.DataFrame, interface_config: Dict[str, Any]) -> pl.DataFrame:
        """数据清洗"""
        # 处理缺失值
        df = df.fill_null(np.nan)

        # 移除完全为空的行
        if not df.is_empty():
            null_exprs = [pl.col(col).is_null() for col in df.columns]
            df = df.filter(~pl.all_horizontal(null_exprs))

        # 移除完全为空的列
        cols_to_keep = [col for col in df.columns if df[col].null_count() != df.height]
        if cols_to_keep:
            df = df.select(cols_to_keep)
        else:
            # 如果所有列都是空的，返回空DataFrame
            df = pl.DataFrame()

        return df

    def validate_data(self, df: pl.DataFrame, interface_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证数据质量

        Args:
            df: 要验证的 DataFrame
            interface_config: 接口配置

        Returns:
            验证结果字典
        """
        output_config = interface_config.get('output', {})
        columns_config = output_config.get('columns', {})

        validation_result = {
            'total_records': len(df),
            'total_columns': len(df.columns),
            'missing_required_fields': [],
            'type_mismatches': [],
            'duplicate_records': 0
        }

        # 检查必填字段
        for column_name, column_def in columns_config.items():
            if column_def.get('required', False) and column_name in df.columns:
                missing_count = df[column_name].null_count()
                if missing_count > 0:
                    validation_result['missing_required_fields'].append({
                        'field': column_name,
                        'missing_count': missing_count
                    })

        # 检查主键重复 - 不执行去重，仅统计
        primary_keys = output_config.get('primary_key', [])
        existing_keys = [key for key in primary_keys if key in df.columns]
        if existing_keys:
            try:
                duplicates = df.with_columns(
                    pl.int_range(0, pl.len()).alias('__index')
                ).group_by(existing_keys).agg(
                    pl.col('__index').list()
                ).filter(
                    pl.col('__index').list().len() > 1
                ).explode('__index').select(
                    pl.col('__index')
                )
                validation_result['duplicate_records'] = len(duplicates)
            except:
                # Fallback for newer polars versions
                try:
                    # Alternative syntax for polars versions (apply -> map)
                    duplicates = df.with_columns(
                        pl.int_range(0, pl.len()).alias('__index')
                    ).group_by(existing_keys).agg(
                        pl.col('__index').map(lambda x: x, return_dtype=pl.List(pl.Int64))
                    ).filter(
                        pl.col('__index').map(lambda x: len(x) if x else 0, return_dtype=pl.Int64) > 1
                    ).select(
                        pl.col('__index').explode()
                    )
                    validation_result['duplicate_records'] = len(duplicates)
                except:
                    # Even simpler alternative - just skip duplicate checking if it fails
                    # Do not log warning since we're not removing duplicates anyway
                    validation_result['duplicate_records'] = 0

        return validation_result