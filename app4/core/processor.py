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

        按照以下顺序处理：
        1. 数据下载（从TuShare API获取原始数据）
        2. 应用派生字段（SchemaManager中完成）
        3. 主键空值过滤（删除主键字段中含有空值的记录）
        4. 检查和处理主键
        5. 数据去重
        6. 数据清洗

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

            # 使用SchemaManager创建DataFrame，应用派生字段
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

            # 关键步骤：在应用派生字段后，过滤主键中的空值
            df = self._filter_primary_key_nulls(df, interface_config)

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

    def _filter_primary_key_nulls(self, df: pl.DataFrame, interface_config: Dict[str, Any]) -> pl.DataFrame:
        """过滤主键中的空值 - 这一步必须在应用派生字段后执行"""
        output_config = interface_config.get('output', {})
        primary_keys = output_config.get('primary_key', [])

        # 过滤掉主键字段中存在空值的行
        if primary_keys and not df.is_empty():
            # 构建过滤条件：所有主键字段都不为空
            conditions = []
            existing_keys = [key for key in primary_keys if key in df.columns]

            for key in existing_keys:
                conditions.append(pl.col(key).is_not_null())

            if conditions:
                # 使用所有主键字段都不为空的条件进行过滤
                filter_expr = pl.all_horizontal(conditions)
                original_count = len(df)
                df = df.filter(filter_expr)
                filtered_count = len(df)

                if original_count != filtered_count:
                    logger.info(f"Filtered {original_count - filtered_count} records with null primary keys "
                               f"for interface {interface_config.get('api_name', 'unknown')}, "
                               f"kept {filtered_count}/{original_count}")

        return df

    def _apply_type_conversions(self, df: pl.DataFrame, interface_config: Dict[str, Any]) -> pl.DataFrame:
        """应用类型转换 - 现在主要依赖SchemaManager的衍生字段功能"""
        # 保留此方法以向后兼容，但实际类型转换已在SchemaManager中完成
        # 这里只处理不在derived_fields中定义的特殊转换需求
        return df

    def _detect_duplicates_fast(self, data: List[Dict[str, Any]], interface_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Unified fast duplicate detection using primary keys.

        Args:
            data: List of data records to check for duplicates
            interface_config: Configuration containing primary key information

        Returns:
            Dictionary with 'duplicates' and 'unique' lists
        """
        primary_keys = interface_config.get('output', {}).get('primary_key', [])

        if not primary_keys:
            # If no primary keys defined, treat all as unique
            return {'duplicates': [], 'unique': data}

        seen_keys = set()
        unique_records = []
        duplicate_records = []

        for record in data:
            # Create a key tuple from primary key values
            key_values = tuple(record.get(pk) for pk in primary_keys)

            if key_values in seen_keys:
                duplicate_records.append(record)
            else:
                seen_keys.add(key_values)
                unique_records.append(record)

        return {
            'duplicates': duplicate_records,
            'unique': unique_records
        }

    def _handle_primary_keys(self, df: pl.DataFrame, interface_config: Dict[str, Any]) -> pl.DataFrame:
        """处理主键"""
        primary_keys = interface_config.get('output', {}).get('primary_key', [])

        # Use the unified duplicate detection method
        data_list = df.to_dicts()
        detection_result = self._detect_duplicates_fast(data_list, interface_config)

        # Process unique records only
        unique_df = pl.DataFrame(detection_result['unique'])

        if detection_result['duplicates']:
            logger.warning(f"Found {len(detection_result['duplicates'])} duplicate records for interface {interface_config.get('name', 'unknown')}")

        return unique_df

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
        验证数据质量 - 使用原始字段进行验证

        Args:
            df: 要验证的 DataFrame
            interface_config: 接口配置

        Returns:
            验证结果字典
        """
        output_config = interface_config.get('output', {})
        # 现在从接口配置中获取原始字段定义（从derived_fields推断原始字段）
        # 为了兼容性，仍检查columns配置
        columns_config = output_config.get('columns', {})

        validation_result = {
            'total_records': len(df),
            'total_columns': len(df.columns),
            'missing_required_fields': [],
            'type_mismatches': [],
            'duplicate_records': 0
        }

        # 检查必填字段 - 现在基于primary_key字段和其他原始字段
        # 从primary_key配置中获取需要检查的字段
        primary_keys = output_config.get('primary_key', [])
        for column_name in primary_keys:
            if column_name in df.columns:
                missing_count = df[column_name].null_count()
                if missing_count > 0:
                    validation_result['missing_required_fields'].append({
                        'field': column_name,
                        'missing_count': missing_count
                    })

        # Use unified duplicate detection
        data_list = df.to_dicts()
        detection_result = self._detect_duplicates_fast(data_list, interface_config)

        stats = {
            'total': len(data_list),
            'unique': len(detection_result['unique']),
            'duplicates': len(detection_result['duplicates']),
            'duplicate_rate': len(detection_result['duplicates']) / len(data_list) if data_list else 0
        }

        if detection_result['duplicates']:
            logger.warning(f"Duplicate detection: {stats['duplicates']} duplicates found out of {stats['total']} records")

        # Return validation stats
        validation_result.update(stats)

        return validation_result