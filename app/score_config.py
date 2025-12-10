"""
Score-based configuration for Tushare API data access
Defines which data interfaces are available based on user's Tushare积分 (points)
"""
try:
    from .config import API_LIMITS
except ImportError:
    from config import API_LIMITS

# Define data interfaces by score requirements
SCORE_REQUIREMENTS = {
    120: {
        'basic': [
            'new_share',      # IPO新股列表
            'trade_cal',      # 交易日历
        ],
        'daily': [
            # Minimal daily data available at 120 points
        ],
        'financial': [
            # No financial data available at 120 points
        ],
        'others': [
            'namechange',     # 股票曾用名 (no points required)
        ]
    },
    2000: {
        'basic': [
            'stock_basic',    # 股票基本信息
            'stock_company',  # 上市公司基本信息
        ],
        'daily': [
            'daily',          # 日线行情
            'daily_basic',    # 每日指标
        ],
        'financial': [
            'income',         # 利润表
            'balancesheet',   # 资产负债表
            'cashflow',       # 现金流量表
            'fina_indicator', # 财务指标
        ],
        'holders': [
            'top10_holders',      # 前十大股东
            'top10_floatholders', # 前十大流通股东
        ],
        'events': [
            'dividend',       # 分红送股
            'forecast',       # 业绩预告
            'express',        # 业绩快报
        ],
        'others': [
            'stk_rewards',    # 管理层薪酬和持股
            'stk_managers',   # 上市公司管理层
            'moneyflow',      # 个股资金流向
            'broker_recommend', # 券商每月荐股
        ]
    },
    3000: {
        'basic': [
            'stock_st',       # ST股票列表
        ],
        'holders': [
            'top10_floatholders', # 前十大流通股东
        ],
        'others': [
            'stock_hsgt',     # 沪深港通股票列表
        ]
    },
    5000: {
        'basic': [
            'bak_basic',      # 备用基础数据
        ],
        'daily': [
            'pro_bar',        # 复权行情
            'bak_daily',      # 备用行情
            'stk_factor',     # 股票技术因子
            'stk_factor_pro', # 股票技术面因子(专业版)
        ],
        'financial': [
            'income_vip',         # 利润表VIP
            'balancesheet_vip',   # 资产负债表VIP
            'cashflow_vip',       # 现金流量表VIP
            'fina_indicator_vip', # 财务指标VIP
            'fina_mainbz',        # 主营业务构成
            'fina_audit',         # 财务审计意见
        ],
        'market_structure': [
            'cyq_perf',       # 每日筹码及胜率
            'cyq_chips',      # 每日筹码分布
        ],
        'funds': [
            'moneyflow_dc',   # 个股资金流向(东财)
            'moneyflow_ths',  # 个股资金流向(同花顺)
            'moneyflow_ind_dc', # 行业/概念资金流向（东财）
            'moneyflow_mkt_dc', # 大盘资金流向（东财）
            'moneyflow_cnt_ths', # 概念板块资金流向（同花顺）
            'moneyflow_ind_ths', # 行业板块资金流向（同花顺）
        ],
        'holders': [
            'pledge_stat',    # 股权质押统计
            'pledge_detail',  # 股权质押明细
            'repurchase',     # 股票回购
            'share_float',    # 限售股解禁
            'block_trade',    # 大宗交易
            'stk_holdertrade', # 股东增减持
        ],
        'research': [
            'stk_surv',       # 机构调研表
            'report_rc',      # 卖方盈利预测数据
            'broker_recommend', # 券商每月荐股
        ],
        'events': [
            'suspend_d',      # 每日停复牌信息
        ],
        'others': [
            'disclosure_date', # 财报披露计划
            'broker_recommend', # 券商每月荐股
        ]
    },
    8000: {
        'research': [
            'report_rc',      # 卖方盈利预测数据 (正式权限)
        ]
    }
}

def get_available_data_types(user_points):
    """
    Get all data types available for a specific score level
    """
    available_types = {
        'basic': set(),
        'daily': set(),
        'financial': set(),
        'holders': set(),
        'events': set(),
        'market_structure': set(),
        'funds': set(),
        'research': set(),
        'others': set()
    }
    
    # Collect all data types available for scores up to the user's score
    for score in sorted(SCORE_REQUIREMENTS.keys()):
        if score <= user_points:
            for category, types in SCORE_REQUIREMENTS[score].items():
                available_types[category].update(types)
    
    # Convert sets back to lists
    for category in available_types:
        available_types[category] = list(available_types[category])
    
    return available_types

def get_api_limits_for_score(user_points):
    """
    Get appropriate API limits based on user's score
    """
    limits = {
        'daily': {'calls_per_minute': 500 if user_points >= 5000 else 200},
        'stock_basic': {'calls_per_minute': 200},
        'daily_basic': {'calls_per_minute': 500 if user_points >= 5000 else 200},
        'income': {'calls_per_minute': 200 if user_points >= 5000 else 100},
        'balancesheet': {'calls_per_minute': 200 if user_points >= 5000 else 100},
        'cashflow': {'calls_per_minute': 200 if user_points >= 5000 else 100},
        'fina_indicator': {'calls_per_minute': 200 if user_points >= 5000 else 100},
    }
    
    # Add limits for higher-score APIs if available
    if user_points >= 5000:
        limits.update({
            'income_vip': {'calls_per_minute': 200},
            'balancesheet_vip': {'calls_per_minute': 200},
            'cashflow_vip': {'calls_per_minute': 200},
            'fina_indicator_vip': {'calls_per_minute': 200},
            'stk_factor': {'calls_per_minute': 100},
            'stk_factor_pro': {'calls_per_minute': 100},
            'cyq_perf': {'calls_per_minute': 100},
            'cyq_chips': {'calls_per_minute': 100},
            'moneyflow_dc': {'calls_per_minute': 100},
            'moneyflow_ths': {'calls_per_minute': 100},
            'moneyflow_ind_dc': {'calls_per_minute': 100},
            'moneyflow_mkt_dc': {'calls_per_minute': 100},
            'moneyflow_cnt_ths': {'calls_per_minute': 100},
            'moneyflow_ind_ths': {'calls_per_minute': 100},
            'top10_floatholders': {'calls_per_minute': 100},
            'report_rc': {'calls_per_minute': 100},
            'stk_surv': {'calls_per_minute': 100},
            'broker_recommend': {'calls_per_minute': 100},
        })
    elif user_points >= 2000:
        limits.update({
            'moneyflow': {'calls_per_minute': 100},
            'broker_recommend': {'calls_per_minute': 100},
        })
    
    return limits