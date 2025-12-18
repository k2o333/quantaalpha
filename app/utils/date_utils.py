"""
日期时间处理工具模块
提供统一的日期时间处理和验证功能
"""
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def validate_and_convert_datetime(df: pd.DataFrame, date_column: str) -> pd.DataFrame:
    """
    验证并转换DataFrame中的日期列为datetime类型

    Args:
        df: 输入的DataFrame
        date_column: 日期列名

    Returns:
        转换后的DataFrame
    """
    if df is None or df.empty:
        return df

    if date_column not in df.columns:
        logger.warning(f"日期列 {date_column} 不存在于DataFrame中")
        return df

    # 检查当前列的数据类型
    if pd.api.types.is_datetime64_any_dtype(df[date_column]):
        logger.debug(f"列 {date_column} 已经是datetime类型")
        return df
    else:
        # 尝试转换为datetime类型
        try:
            df[date_column] = pd.to_datetime(df[date_column])
            logger.debug(f"成功将列 {date_column} 转换为datetime类型")
        except Exception as e:
            logger.error(f"将列 {date_column} 转换为datetime类型失败: {e}")
        return df


def safe_apply_dt_accessor(df: pd.DataFrame, date_column: str, operation: str, *args, **kwargs):
    """
    安全地对DataFrame的日期列应用.dt访问器

    Args:
        df: 输入的DataFrame
        date_column: 日期列名
        operation: 要执行的操作（如 'strftime', 'year', 'date'等）
        *args, **kwargs: 传递给操作的参数

    Returns:
        操作结果或None（如果失败）
    """
    if df is None or df.empty:
        return None

    if date_column not in df.columns:
        logger.warning(f"日期列 {date_column} 不存在于DataFrame中")
        return None

    # 验证并转换日期列
    df = validate_and_convert_datetime(df, date_column)

    if not pd.api.types.is_datetime64_any_dtype(df[date_column]):
        logger.error(f"无法转换为datetime类型，无法应用.dt访问器")
        return None

    try:
        # 应用.dt访问器
        if hasattr(df[date_column].dt, operation):
            result = getattr(df[date_column].dt, operation)(*args, **kwargs)
            logger.debug(f"成功应用.dt.{operation}到列 {date_column}")
            return result
        else:
            logger.error(f".dt访问器不支持方法 {operation}")
            return None
    except Exception as e:
        logger.error(f"应用.dt访问器到列 {date_column} 时失败: {e}")
        return None


def format_date_column(df: pd.DataFrame, date_column: str, format_str: str = '%Y-%m-%d') -> pd.DataFrame:
    """
    格式化DataFrame中的日期列为指定格式的字符串

    Args:
        df: 输入的DataFrame
        date_column: 日期列名
        format_str: 日期格式字符串，默认为 '%Y-%m-%d'

    Returns:
        处理后的DataFrame
    """
    if df is None or df.empty:
        return df

    result = safe_apply_dt_accessor(df, date_column, 'strftime', format_str)
    if result is not None:
        df[f'{date_column}_formatted'] = result
        logger.debug(f"成功格式化列 {date_column} 为 {format_str} 格式")
    return df


def get_date_range_info(df: pd.DataFrame, date_column: str) -> dict:
    """
    获取DataFrame中日期列的范围信息

    Args:
        df: 输入的DataFrame
        date_column: 日期列名

    Returns:
        包含日期范围信息的字典
    """
    if df is None or df.empty:
        return {}

    if date_column not in df.columns:
        logger.error(f"列 {date_column} 不存在于DataFrame中")
        return {}

    # 验证并转换日期列
    df = validate_and_convert_datetime(df, date_column)

    if not pd.api.types.is_datetime64_any_dtype(df[date_column]):
        logger.error(f"列 {date_column} 无法转换为datetime类型")
        return {}

    try:
        min_date = df[date_column].min()
        max_date = df[date_column].max()
        count = len(df[date_column].dropna())

        return {
            'min_date': min_date,
            'max_date': max_date,
            'count': count,
            'range_days': (max_date - min_date).days if pd.notna(min_date) and pd.notna(max_date) else 0
        }
    except Exception as e:
        logger.error(f"获取日期范围信息失败: {e}")
        return {}