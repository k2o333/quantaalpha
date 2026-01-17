"""
Data quality validation for aspipe_v4
"""
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def validate_stock_basic_data(df: pd.DataFrame) -> bool:
    """
    Validate stock basic data quality
    """
    logger.info("🔍 开始股票基本信息质量验证...")
    
    if df is None or df.empty:
        logger.error("❌ 股票基本信息数据为空")
        return False
    
    issues = []
    
    # Check for required columns
    required_columns = ['ts_code', 'symbol', 'name', 'list_date']
    missing_cols = [col for col in required_columns if col not in df.columns]
    if missing_cols:
        issues.append(f"缺少必要列: {missing_cols}")
    
    # Check for duplicates
    duplicate_count = df.duplicated(subset=['ts_code']).sum()
    if duplicate_count > 0:
        issues.append(f"发现 {duplicate_count} 条重复记录")
    
    # Check for null values in critical fields
    critical_fields = ['ts_code', 'symbol', 'name']
    for field in critical_fields:
        if field in df.columns:
            null_count = df[field].isnull().sum()
            if null_count > 0:
                issues.append(f"字段 {field} 发现 {null_count} 个空值")
    
    # Check list_date format
    if 'list_date' in df.columns:
        invalid_dates = df[df['list_date'].astype(str).str.len() != 8]
        if len(invalid_dates) > 0:
            issues.append(f"发现 {len(invalid_dates)} 个日期格式错误")
    
    if issues:
        for issue in issues:
            logger.warning(f"⚠️ {issue}")
        logger.info(f"📊 股票基本信息质量验证完成，发现 {len(issues)} 个问题")
        return False
    else:
        logger.info(f"✅ 股票基本信息质量验证通过，{len(df)} 条记录")
        return True


def validate_daily_data(df: pd.DataFrame) -> bool:
    """
    Validate daily data quality
    """
    logger.info("🔍 开始日线数据质量验证...")
    
    if df is None or df.empty:
        logger.error("❌ 日线数据为空")
        return False
    
    issues = []
    
    # Check for required columns
    required_columns = ['ts_code', 'trade_date', 'open', 'high', 'low', 'close', 'vol', 'amount']
    missing_cols = [col for col in required_columns if col not in df.columns]
    if missing_cols:
        issues.append(f"缺少必要列: {missing_cols}")
    
    # Check for duplicates
    if 'ts_code' in df.columns and 'trade_date' in df.columns:
        duplicate_count = df.duplicated(subset=['ts_code', 'trade_date']).sum()
        if duplicate_count > 0:
            issues.append(f"发现 {duplicate_count} 条重复记录")
    
    # Check for null values in critical fields
    critical_fields = ['ts_code', 'trade_date', 'open', 'high', 'low', 'close']
    for field in critical_fields:
        if field in df.columns:
            null_count = df[field].isnull().sum()
            if null_count > 0:
                issues.append(f"字段 {field} 发现 {null_count} 个空值")
    
    # Validate price relationships (high >= open/close >= low)
    if all(col in df.columns for col in ['open', 'high', 'low', 'close']):
        invalid_high_low = df[df['high'] < df['low']]
        if len(invalid_high_low) > 0:
            issues.append(f"发现 {len(invalid_high_low)} 条high < low的记录")
        
        invalid_open = df[(df['open'] > df['high']) | (df['open'] < df['low'])]
        if len(invalid_open) > 0:
            issues.append(f"发现 {len(invalid_open)} 条open不在[low, high]范围内的记录")
        
        invalid_close = df[(df['close'] > df['high']) | (df['close'] < df['low'])]
        if len(invalid_close) > 0:
            issues.append(f"发现 {len(invalid_close)} 条close不在[low, high]范围内的记录")
    
    # Check trade_date format
    if 'trade_date' in df.columns:
        invalid_dates = df[df['trade_date'].astype(str).str.len() != 8]
        if len(invalid_dates) > 0:
            issues.append(f"发现 {len(invalid_dates)} 个日期格式错误")
    
    if issues:
        for issue in issues:
            logger.warning(f"⚠️ {issue}")
        logger.info(f"📊 日线数据质量验证完成，发现 {len(issues)} 个问题")
        return False
    else:
        logger.info(f"✅ 日线数据质量验证通过，{len(df)} 条记录")
        return True


def validate_data_quality(stock_basic_df: pd.DataFrame = None, daily_df: pd.DataFrame = None) -> dict:
    """
    Run comprehensive data quality validation
    """
    logger.info("🔍 开始数据质量验证...")
    
    results = {
        'stock_basic_valid': True,
        'daily_valid': True,
        'issues_found': 0
    }
    
    if stock_basic_df is not None:
        results['stock_basic_valid'] = validate_stock_basic_data(stock_basic_df)
    
    if daily_df is not None:
        results['daily_valid'] = validate_daily_data(daily_df)
    
    results['issues_found'] = not (results['stock_basic_valid'] and results['daily_valid'])
    
    if results['stock_basic_valid'] and results['daily_valid']:
        logger.info("✅ 所有数据质量验证通过")
    else:
        logger.warning("⚠️ 部分数据质量验证未通过")
    
    return results