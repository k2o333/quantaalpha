import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class DataProcessor:
    """数据处理器 - 类型转换，主键检查，数据去重"""

    def __init__(self):
        pass

    def process_data(self, data: List[Dict[str, Any]], interface_config: Dict[str, Any]) -> pd.DataFrame:
        """
        处理数据

        Args:
            data: 原始数据列表
            interface_config: 接口配置

        Returns:
            处理后的 DataFrame
        """
        if not data:
            return pd.DataFrame()

        try:
            # 转换为 DataFrame
            df = pd.DataFrame(data)

            # 确保列名是字符串类型
            df.columns = df.columns.astype(str)

            # 确保没有重复的列名
            df = df.loc[:, ~df.columns.duplicated()]

            # 应用类型转换
            df = self._apply_type_conversions(df, interface_config)

            # 检查和处理主键
            df = self._handle_primary_keys(df, interface_config)

            # 数据去重
            df = self._remove_duplicates(df, interface_config)

            # 数据清洗
            df = self._clean_data(df, interface_config)

            logger.info(f"Processed {len(df)} records")
            return df

        except Exception as e:
            logger.error(f"Error processing data: {str(e)}")
            return pd.DataFrame()

    def _apply_type_conversions(self, df: pd.DataFrame, interface_config: Dict[str, Any]) -> pd.DataFrame:
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
                        df[column_name] = pd.to_datetime(df[column_name], format=date_format, errors='coerce')
                    except Exception as e:
                        logger.warning(f"Error converting {column_name} to date: {str(e)}")
                        # 尝试自动解析
                        df[column_name] = pd.to_datetime(df[column_name], errors='coerce')
                elif column_type == 'int':
                    # 处理整数类型
                    df[column_name] = pd.to_numeric(df[column_name], errors='coerce').astype('Int64')
                elif column_type == 'float':
                    # 处理浮点数类型
                    df[column_name] = pd.to_numeric(df[column_name], errors='coerce')
                elif column_type == 'string':
                    # 处理字符串类型
                    df[column_name] = df[column_name].astype(str)

        return df

    def _handle_primary_keys(self, df: pd.DataFrame, interface_config: Dict[str, Any]) -> pd.DataFrame:
        """处理主键"""
        output_config = interface_config.get('output', {})
        primary_keys = output_config.get('primary_key', [])

        # 检查主键字段是否存在
        missing_keys = [key for key in primary_keys if key not in df.columns]
        if missing_keys:
            logger.warning(f"Primary key fields missing in data: {missing_keys}")

        # 只保留在数据中存在的主键字段
        existing_keys = [key for key in primary_keys if key in df.columns]

        # 检查主键是否唯一
        if existing_keys and len(existing_keys) > 0:
            duplicates = df.duplicated(subset=existing_keys, keep=False)
            if duplicates.any():
                logger.info(f"Found {duplicates.sum()} duplicate records based on primary keys")

        return df

    def _remove_duplicates(self, df: pd.DataFrame, interface_config: Dict[str, Any]) -> pd.DataFrame:
        """去除重复数据"""
        output_config = interface_config.get('output', {})
        primary_keys = output_config.get('primary_key', [])
        sort_by = output_config.get('sort_by', [])

        # 只保留在数据中存在的主键字段
        existing_keys = [key for key in primary_keys if key in df.columns]

        if existing_keys:
            # 根据主键去重，保留最后一条记录
            df = df.drop_duplicates(subset=existing_keys, keep='last')

        # 如果指定了排序字段，则进行排序
        existing_sort_fields = [field for field in sort_by if field in df.columns]
        if existing_sort_fields:
            df = df.sort_values(by=existing_sort_fields)

        return df

    def _clean_data(self, df: pd.DataFrame, interface_config: Dict[str, Any]) -> pd.DataFrame:
        """数据清洗"""
        # 处理缺失值
        df = df.fillna(value=np.nan)

        # 移除完全为空的行
        df = df.dropna(how='all')

        # 移除完全为空的列
        df = df.dropna(axis=1, how='all')

        return df

    def validate_data(self, df: pd.DataFrame, interface_config: Dict[str, Any]) -> Dict[str, Any]:
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
                missing_count = df[column_name].isna().sum()
                if missing_count > 0:
                    validation_result['missing_required_fields'].append({
                        'field': column_name,
                        'missing_count': missing_count
                    })

        # 检查主键重复
        primary_keys = output_config.get('primary_key', [])
        existing_keys = [key for key in primary_keys if key in df.columns]
        if existing_keys:
            duplicates = df.duplicated(subset=existing_keys, keep=False)
            validation_result['duplicate_records'] = duplicates.sum()

        return validation_result