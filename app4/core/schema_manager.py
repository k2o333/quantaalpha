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
            'n_commis_income': pl.Float64,
            'n_oth_income': pl.Float64,
            'n_oth_b_income': pl.Float64,
            'prem_income': pl.Float64,
            'out_prem': pl.Float64,
            'une_prem_reser': pl.Float64,
            'reins_income': pl.Float64,
            'n_sec_tb_income': pl.Float64,
            'n_sec_uw_income': pl.Float64,
            'n_asset_mg_income': pl.Float64,
            'oth_b_income': pl.Float64,
            'fv_value_chg_gain': pl.Float64,
            'invest_income': pl.Float64,
            'ass_invest_income': pl.Float64,
            'forex_gain': pl.Float64,
            'total_cogs': pl.Float64,
            'oper_cost': pl.Float64,
            'int_exp': pl.Float64,
            'comm_exp': pl.Float64,
            'biz_tax_surchg': pl.Float64,
            'sell_exp': pl.Float64,
            'admin_exp': pl.Float64,
            'fin_exp': pl.Float64,
            'assets_impair_loss': pl.Float64,
            'prem_refund': pl.Float64,
            'compens_payout': pl.Float64,
            'reser_insur_liab': pl.Float64,
            'div_payt': pl.Float64,
            'reins_exp': pl.Float64,
            'oper_exp': pl.Float64,
            'compens_payout_refu': pl.Float64,
            'insur_reser_refu': pl.Float64,
            'reins_cost_refund': pl.Float64,
            'other_bus_cost': pl.Float64,
            'operate_profit': pl.Float64,
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
            'ebit': pl.Float64,
            'ebitda': pl.Float64,
            'insurance_exp': pl.Float64,
            'undist_profit': pl.Float64,
            'distable_profit': pl.Float64,
            'rd_exp': pl.Float64,
            'fin_exp_int_exp': pl.Float64,
            'fin_exp_int_inc': pl.Float64,
            'transfer_surplus_rese': pl.Float64,
            'transfer_housing_imprest': pl.Float64,
            'transfer_oth': pl.Float64,
            'adj_lossgain': pl.Float64,
            'withdra_legal_surplus': pl.Float64,
            'withdra_legal_pubfund': pl.Float64,
            'withdra_biz_devfund': pl.Float64,
            'withdra_rese_fund': pl.Float64,
            'withdra_oth_ersu': pl.Float64,
            'workers_welfare': pl.Float64,
            'distr_profit_shrhder': pl.Float64,
            'prfshare_payable_dvd': pl.Float64,
            'comshare_payable_dvd': pl.Float64,
            'capit_comstock_div': pl.Float64,
            'net_after_nr_lp_correct': pl.Float64,
            'credit_impa_loss': pl.Float64,
            'net_expo_hedging_benefits': pl.Float64,
            'oth_impair_loss_assets': pl.Float64,
            'total_opcost': pl.Float64,
            'amodcost_fin_assets': pl.Float64,
            'oth_income': pl.Float64,
            'asset_disp_income': pl.Float64,
            'continued_net_profit': pl.Float64,
            'end_net_profit': pl.Float64,
            'update_flag': pl.Utf8,
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