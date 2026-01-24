# Stock Loop接口错误根本原因分析与改进方案实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复18个stock_loop接口错误，提升系统稳定性和数据完整性

**Architecture:** 基于App4配置驱动架构，通过修复schema推断、缓存机制、分页逻辑等8大类问题

**Tech Stack:** Python, Polars, YAML配置, 多线程, 缓存管理

---

## 预备任务：创建目录和基础文件

### Task 1: 创建superpower目录

**Files:**
- Create: `/home/quan/testdata/aspipe_v4/p/superpower/README.md`

**Step 1: Write the README file**

```markdown
# Superpower Implementation Plans

This directory contains implementation plans for system improvements and optimizations.
```

**Step 2: Run to create the directory**

执行创建命令

**Step 3: Commit**

提交创建的目录和文件

### Task 2: 创建schema管理改进计划

**Files:**
- Create: `/home/quan/testdata/aspipe_v4/p/superpower/schema_manager_improvement_plan.md`

**Step 1: Write the failing test**

此任务是创建计划文档，不需要测试

**Step 2: Write minimal implementation**

```markdown
# Schema Manager 改进实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复schema推断长度不足导致的类型冲突问题，特别是balancesheet_vip接口的151条记录丢失问题

**Architecture:** 混合策略 - 优先使用预定义schema，回退到智能推断，再回退到宽松模式

**Tech Stack:** Python, Polars, YAML

---

### Task 1: 创建SchemaManager增强版本

**Files:**
- Modify: `app4/core/schema_manager.py:80-120`

**Step 1: Write the failing test**

```python
# test_schema_manager.py
import pytest
import polars as pl
from app4.core.schema_manager import SchemaManager

def test_create_dataframe_with_mixed_types():
    """测试混合类型数据的DataFrame创建，前100行是整数，第101行是小数"""
    data = []
    # 前100行是整数
    for i in range(100):
        data.append({'ts_code': '000002.SZ', 'value': 100})
    # 第101行是小数，模拟balancesheet_vip问题
    data.append({'ts_code': '000002.SZ', 'value': 1.2488e7})

    # 旧版本会失败，新版本应该成功
    df = SchemaManager.create_dataframe(data, 'balancesheet_vip')
    assert df.height == len(data)
    assert df.schema['value'] in [pl.Float64, pl.Float32]  # 应该是浮点类型
```

**Step 2: Run test to verify it fails**

运行: `pytest test_schema_manager.py::test_create_dataframe_with_mixed_types -v`
Expected: FAIL with schema inference error

**Step 3: Write minimal implementation**

修改 `app4/core/schema_manager.py` 中的 `create_dataframe` 函数:

```python
@staticmethod
def create_dataframe(data: List[Dict[str, Any]], interface_name: str) -> pl.DataFrame:
    """混合策略：先尝试预定义schema，失败后回退到智能推断，再回退到宽松模式"""
    if not data:
        return pl.DataFrame()

    try:
        # 尝试1：使用预定义schema
        predefined_schema = SchemaManager.load_schema(interface_name)
        if predefined_schema:
            df = pl.DataFrame(data, schema=predefined_schema)
        else:
            # 尝试2：智能推断，根据数据量动态调整，增加推断长度
            data_length = len(data)
            infer_length = min(data_length, 10000 if data_length > 10000 else data_length)
            df = pl.DataFrame(data, infer_schema_length=infer_length)

        # 应用衍生字段
        df = SchemaManager.apply_derived_fields(df, interface_name)

    except Exception as e:
        logger.error(f"Schema推断失败: {str(e)}")
        logger.error(f"尝试回退到宽松模式...")

        # 回退方案：全部转为字符串，后续再处理类型转换
        # 先尝试增加推断长度
        try:
            df = pl.DataFrame(data, infer_schema_length=min(len(data), 20000))
            df = SchemaManager.apply_derived_fields(df, interface_name)
        except Exception as e2:
            logger.error(f"回退方案也失败: {str(e2)}")
            logger.error("警告：数据可能包含类型不匹配的情况")
            # 继续使用完整的数据长度以确保所有数据都被包含
            df = pl.DataFrame(data, infer_schema_length=len(data))
            df = SchemaManager.apply_derived_fields(df, interface_name)

        # 应用衍生字段
        df = SchemaManager.apply_derived_fields(df, interface_name)

    # 添加系统字段
    current_time = int(time.time() * 1000)
    df = df.with_columns([
        pl.lit(current_time).alias('_update_time')
    ])

    return df
```

**Step 4: Run test to verify it passes**

运行: `pytest test_schema_manager.py::test_create_dataframe_with_mixed_types -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app4/core/schema_manager.py
git commit -m "feat: enhance schema inference with mixed strategy"
```

### Task 2: 为财务接口创建预定义schema配置

**Files:**
- Create: `app4/config/schemas/balancesheet_vip.yaml`
- Create: `app4/config/schemas/income_vip.yaml`
- Create: `app4/config/schemas/cashflow_vip.yaml`

**Step 1: Write the failing test**

```python
# test_predefined_schemas.py
import os
import yaml
from app4.core.schema_manager import SchemaManager

def test_predefined_schema_exists():
    """测试预定义schema配置文件存在"""
    assert os.path.exists("app4/config/schemas/balancesheet_vip.yaml")
    assert os.path.exists("app4/config/schemas/income_vip.yaml")
    assert os.path.exists("app4/config/schemas/cashflow_vip.yaml")

    # 检查schema是否能正确加载
    balancesheet_schema = SchemaManager.load_schema('balancesheet_vip')
    assert balancesheet_schema is not None
    assert 'total_assets' in balancesheet_schema
    assert balancesheet_schema['total_assets'] in ['Float64', 'Float32']
```

**Step 2: Run test to verify it fails**

运行: `pytest test_predefined_schemas.py::test_predefined_schema_exists -v`
Expected: FAIL with file not found

**Step 3: Write minimal implementation**

创建 `app4/config/schemas/balancesheet_vip.yaml`:

```yaml
# balancesheet_vip schema定义
fields:
  ts_code: string
  ann_date: string
  end_date: string
  # 主要财务字段，全部指定为Float64避免溢出
  comp_type: Int64
  report_type: string
  total_share: Float64
  total_assets: Float64
  quick_assets: Float64
  fixed_assets: Float64
  const_materials: Float64
  intang_assets: Float64
  r_and_d: Float64
  good_will: Float64
  lt_equity_inv: Float64
  total_liab: Float64
  total_cur_liab: Float64
  total_non_cur_liab: Float64
  total_sharehol_eq: Float64
  treasury_share: Float64
  other_equity: Float64
  assets_liquidation: Float64
  deferred_tax_assets: Float64
  st_borrow: Float64
  st_loan: Float64
  total_hldr_eq_exc_min_int: Float64
  total_assets_yoy: Float64
  update_flag: string

# 需要转换的字段
derived_fields:
  ann_date_dt:
    source: ann_date
    type: date
    format: '%Y%m%d'
  end_date_dt:
    source: end_date
    type: date
    format: '%Y%m%d'
```

创建 `app4/config/schemas/income_vip.yaml`:

```yaml
# income_vip schema定义
fields:
  ts_code: string
  ann_date: string
  f_ann_date: string
  end_date: string
  # 主要财务字段，全部指定为Float64避免溢出
  comp_type: Int64
  report_type: string
  basic_eps: Float64
  diluted_eps: Float64
  total_revenue: Float64
  revenue: Float64
  int_income: Float64
  prem_earned: Float64
  comm_income: Float64
  n_commis_income: Float64
  n_oth_income: Float64
  n_oth_b_income: Float64
  prem_income: Float64
  out_prem: Float64
  une_prem_reser: Float64
  reins_income: Float64
  n_sec_tb_income: Float64
  n_sec_uw_income: Float64
  n_asset_mg_income: Float64
  oth_b_income: Float64
  fv_value_chg: Float64
  invest_income: Float64
  ass_invest_income: Float64
  forex_income: Float64
  total_cogs: Float64
  oper_cost: Float64
  int_exp: Float64
  comm_exp: Float64
  biz_tax_surchg: Float64
  sell_exp: Float64
  admin_exp: Float64
  fin_exp: Float64
  assets_impair: Float64
  prem_refund: Float64
  compens_payout: Float64
  reser_insur_liab: Float64
  div_payt: Float64
  reins_exp: Float64
  oper_exp: Float64
  compens_payout_refu: Float64
  insur_reser_refu: Float64
  reins_cost_refund: Float64
  other_bus_cost: Float64
  operate_profit: Float64
  non_oper_income: Float64
  non_oper_exp: Float64
  nca_disploss: Float64
  total_profit: Float64
  income_tax: Float64
  n_income: Float64
  n_income_attr_p: Float64
  minority_gain: Float64
  oth_compr_income: Float64
  t_compr_income: Float64
  compr_inc_attr_p: Float64
  compr_inc_attr_m_s: Float64
  ebit: Float64
  ebitda: Float64
  insurance_exp: Float64
  undist_profit: Float64
  dist_to_d_continu_oper: Float64
  dist_to_p_fix_int_payable: Float64
  dist_to_min_inter: Float64
  update_flag: string

# 需要转换的字段
derived_fields:
  ann_date_dt:
    source: ann_date
    type: date
    format: '%Y%m%d'
  f_ann_date_dt:
    source: f_ann_date
    type: date
    format: '%Y%m%d'
  end_date_dt:
    source: end_date
    type: date
    format: '%Y%m%d'
```

创建 `app4/config/schemas/cashflow_vip.yaml`:

```yaml
# cashflow_vip schema定义
fields:
  ts_code: string
  ann_date: string
  f_ann_date: string
  end_date: string
  comp_type: Int64
  report_type: string
  net_profit: Float64
  finan_exp: Float64
  minus_finance_cost: Float64
  sale_goods_cash: Float64
  recp_tax_rends: Float64
  net_deposit_increase: Float64
  net_borr_oth_fi: Float64
  net_borr_securities: Float64
  net_loan_adv: Float64
  net_disp_tfa: Float64
  other_cash_recp_ral_oper: Float64
  st_cash_out_act: Float64
  pay_goods_cash: Float64
  pay_beh_empl: Float64
  pay_tax: Float64
  net_incr_clients_loan_adv: Float64
  net_incr_dep_co_borr: Float64
  other_cash_out_act: Float64
  net_incr_dep: Float64
  cash_recp_prem_orig_inco: Float64
  pay_claims_orig_inco: Float64
  pay_handling_chrg: Float64
  pay_comm_insur_plcy: Float64
  oth_cash_recp_ral_ins: Float64
  st_cash_in_ins: Float64
  cash_pay_sg: Float64
  oth_cash_out_ins: Float64
  st_cash_out_ins: Float64
  reinsurance_ceded_prem: Float64
  oth_earn: Float64
  dep_withdrwl_reser: Float64
  rescq_insur_cont_rsrv: Float64
  independent_acct_eci: Float64
  oth_compr_income: Float64
  total_compr_income: Float64
  paid_invest_cash: Float64
  impawned_loan_net: Float64
  cash_recp_disp_sobu: Float64
  cash_recp_return_inv: Float64
  gross_cash_in_finv: Float64
  dispos_fix_assets: Float64
  dispos_comp_assets: Float64
  oth_cash_recp_ral_finv: Float64
  st_cash_out_finv: Float64
  add_inv_property: Float64
  cash_paid_invest: Float64
  impawn_loan: Float64
  cash_paid_disp_shre: Float64
  sub_to_central_bank: Float64
  lend_capital: Float64
  oth_cash_out_finv: Float64
  net_cash_flows_oper_act: Float64
  net_cash_flows_inv_act: Float64
  net_cash_flows_fnc_act: Float64
  cash_net_incr: Float64
  cash_net_incr_undis: Float64
  fx_vars_chg: Float64
  cash_equ_end_period: Float64
  cash_equ_end_period_undis: Float64
  working_cap: Float64
  net_operate_cashflow: Float64
  net_invest_cashflow: Float64
  net_finance_cashflow: Float64
  gross_cash_short: Float64
  gross_cash_long: Float64
  update_flag: string

# 需要转换的字段
derived_fields:
  ann_date_dt:
    source: ann_date
    type: date
    format: '%Y%m%d'
  f_ann_date_dt:
    source: f_ann_date
    type: date
    format: '%Y%m%d'
  end_date_dt:
    source: end_date
    type: date
    format: '%Y%m%d'
```

**Step 4: Run test to verify it passes**

运行: `pytest test_predefined_schemas.py::test_predefined_schema_exists -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app4/config/schemas/
git commit -m "feat: add predefined schemas for financial interfaces"
```

### Task 3: 实现SchemaManager的load_schema方法

**Files:**
- Modify: `app4/core/schema_manager.py:120-140`

**Step 1: Write the failing test**

```python
# test_schema_loading.py
import os
from app4.core.schema_manager import SchemaManager

def test_load_schema_method():
    """测试SchemaManager.load_schema方法"""
    # 确保配置目录存在
    os.makedirs("app4/config/schemas", exist_ok=True)

    # 创建测试schema文件
    test_schema = {
        'fields': {'ts_code': 'string', 'value': 'Float64'},
        'derived_fields': {}
    }

    import yaml
    with open("app4/config/schemas/test_interface.yaml", 'w') as f:
        yaml.dump(test_schema, f)

    # 测试加载
    loaded_schema = SchemaManager.load_schema('test_interface')
    assert loaded_schema is not None
    assert 'ts_code' in loaded_schema
    assert loaded_schema['value'] == 'Float64'

    # 清理
    os.remove("app4/config/schemas/test_interface.yaml")
```

**Step 2: Run test to verify it fails**

运行: `pytest test_schema_loading.py::test_load_schema_method -v`
Expected: FAIL with method not found or schema not found

**Step 3: Write minimal implementation**

在 `app4/core/schema_manager.py` 中添加以下方法：

```python
@staticmethod
def load_schema(interface_name: str) -> Optional[Dict[str, str]]:
    """加载预定义schema"""
    schema_file = f"app4/config/schemas/{interface_name}.yaml"
    if os.path.exists(schema_file):
        import yaml
        with open(schema_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            return config.get('fields')
    return None
```

**Step 4: Run test to verify it passes**

运行: `pytest test_schema_loading.py::test_load_schema_method -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app4/core/schema_manager.py
git commit -m "feat: implement load_schema method in SchemaManager"
```