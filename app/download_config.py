# 下载配置文件
# true表示下载，false表示不下载
DOWNLOAD_CONFIG = {
    # 设置为false的接口（不下载）
    'moneyflow_ths': False,
    'moneyflow_cnt_ths': False,
    'moneyflow_ind_ths': False,
    'broker_recommend': False,
    'report_rc': False,

    # 设置为true的接口（下载）
    'daily': True,
    'daily_basic': True,
    'moneyflow': True,
    'moneyflow_dc': True,
    'moneyflow_ind_dc': True,
    'moneyflow_mkt_dc': True,
    'stk_factor': True,
    'stk_factor_pro': True,
    'cyq_perf': True,
    'cyq_chips': False,  # 暂时禁用：cyq_chips接口因性能问题已重构优化
    'stock_basic': True,
    'trade_cal': True,
    'new_share': True,
    'stock_company': True,
    'stock_st': True,
    'bak_basic': True,
    'income': True,
    'balancesheet': True,
    'cashflow': True,
    'fina_indicator': True,
    'dividend': True,
    'forecast': True,  # 修改：forecast可以下载
    'express': True,   # 修改：express可以下载
    'top10_holders': True,
    'top10_floatholders': True,
    'stk_surv': True,
    'stk_rewards': True,
    'stk_managers': True,
    'namechange': True,
}