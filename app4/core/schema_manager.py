import polars as pl
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

class SchemaManager:
    """Schema管理器 - 预定义数据类型，避免运行时推断开销"""

    # 预定义的财务数据schema
    FINANCIAL_SCHEMAS = {
        'income_vip': {
            'ts_code': pl.Utf8,
            'ann_date': pl.Utf8,  # 保持字符串格式，后续需要时再转换
            'f_ann_date': pl.Utf8,
            'end_date': pl.Utf8,
            'report_type': pl.Utf8,
            'comp_type': pl.Utf8,
            'basic_eps': pl.Float64,
            'diluted_eps': pl.Float64,
            'total_revenue': pl.Float64,
            'revenue': pl.Float64,
            'int_income': pl.Float64,
            'prem_earned': pl.Float64,
            'comm_income': pl.Float64,
            'n_comm_income': pl.Float64,
            'n_oth_income': pl.Float64,
            'n_oth_b_income': pl.Float64,
            'total_cogs': pl.Float64,
            'oper_exp': pl.Float64,
            'admin_exp': pl.Float64,
            'fin_exp': pl.Float64,
            'impa_taxes': pl.Float64,
            'disp_ral': pl.Float64,
            'credit_impair': pl.Float64,
            'assets_impair': pl.Float64,
            'invest_income': pl.Float64,
            'ass_invest_income': pl.Float64,
            'oper_profit': pl.Float64,
            'non_oper_income': pl.Float64,
            'non_oper_exp': pl.Float64,
            'nca_disploss': pl.Float64,
            'total_profit': pl.Float64,
            'income_tax': pl.Float64,
            'n_income': pl.Float64,
            'n_income_attr_p': pl.Float64,
            'minority_gain': pl.Float64,
            'oth_compr_income': pl.Float64,
            't_compr_income': pl.Float64,
            'compr_inc_attr_p': pl.Float64,
            'compr_inc_attr_m_s': pl.Float64,
        }
    }

    @classmethod
    def get_schema(cls, interface_name: str) -> Optional[Dict[str, pl.DataType]]:
        """获取接口的预定义schema"""
        return cls.FINANCIAL_SCHEMAS.get(interface_name)

    @classmethod
    def create_dataframe(cls, data: List[Dict[str, Any]], interface_name: str) -> pl.DataFrame:
        """使用预定义schema创建DataFrame，避免类型推断"""
        if not data:
            return pl.DataFrame()

        # 获取预定义schema
        schema = cls.get_schema(interface_name)

        if schema:
            # 使用预定义schema创建DataFrame
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
                logger.debug(f"Created DataFrame with predefined schema for {interface_name}")
                return df
            except Exception as e:
                logger.warning(f"Failed to create DataFrame with predefined schema: {str(e)}, falling back to auto inference")

        # 回退到自动推断
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