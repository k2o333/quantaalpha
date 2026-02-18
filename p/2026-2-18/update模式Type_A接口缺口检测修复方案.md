# --update 模式 Type A 接口缺口检测修复方案

## 问题描述

### 当前行为

执行 `python app4/main.py --update --interface stk_factor_pro --ts_code 000001.SZ` 时：

```
2026-02-18 20:46:37,211 - core.coverage_manager - INFO - [stk_factor_pro/000001.SZ] 交易日历缺口检测 (20230101 ~ 20260218)
2026-02-18 20:46:37,235 - core.coverage_manager - INFO - [000001.SZ] 用户未提供日期，只检测 20260213 之后的缺失日期
2026-02-18 20:46:37,235 - core.coverage_manager - INFO - [000001.SZ] 交易日数据已完整
```

**问题**：只检测 `20260213` 之后的新日期，不检测历史缺失日期。

### 期望行为

| 命令 | 期望行为 |
|------|---------|
| `--update --ts_code 000001.SZ` | 从股票上市日开始，检测**所有**缺失日期并补全 |
| `--ts_code 000001.SZ`（不带 --update） | 只下载已有数据**之后**的新数据（增量模式） |

---

## 根因分析

### 代码位置

`app4/core/coverage_manager.py:982-989`

```python
if not user_provided_dates:
    # 用户未提供日期，只检测现有数据之后的缺失日期（增量下载）
    if existing_dates:
        max_existing_date = max(existing_dates)
        trade_days = [d for d in trade_days if d > max_existing_date]
        logger.info(
            f"[{ts_code}] 用户未提供日期，只检测 {max_existing_date} 之后的缺失日期"
        )
```

### 问题链路

1. 用户执行 `--update --ts_code 000001.SZ`（不提供 `--start_date`/`--end_date`）
2. `update_manager.py:568` 设置 `user_provided_dates = False`
3. `coverage_manager` 判断 `user_provided_dates == False`
4. 只检测已有数据 `max_existing_date` 之后的新日期

### 语义混淆

当前 `user_provided_dates` 的语义是："用户是否显式提供了日期参数"

但 `--update` 模式的语义应该是："全量缺口检测，补全所有缺失数据"

---

## 修复方案

### 修改文件

`app4/update/update_manager.py`

### 修改位置

方法 `_update_with_stock_gap_detection()`，约第 568-581 行

### 修改内容

```python
# ============ 修改前 ============
user_provided_dates = options.start_date is not None and options.end_date is not None

for stock in stock_list:
    ts_code = stock.get('ts_code')

    # 检测该股票的数据缺口
    gap_tasks = self.coverage_manager.detect_stock_gaps(
        interface_name=interface_name,
        ts_code=ts_code,
        start_date=date_range.start_date,  # 接口级别日期，可能是 20230101
        end_date=date_range.end_date,
        interface_config=interface_config,
        user_provided_dates=user_provided_dates,
        stock_info=stock
    )

# ============ 修改后 ============
from core.constants import DEFAULT_STOCK_START_DATE

# --update 模式：始终进行全量缺口检测（从股票上市日开始）
user_provided_dates = True

for stock in stock_list:
    ts_code = stock.get('ts_code')
    
    # --update 模式：从股票上市日开始检测
    stock_start_date = stock.get('list_date') or DEFAULT_STOCK_START_DATE

    # 检测该股票的数据缺口
    gap_tasks = self.coverage_manager.detect_stock_gaps(
        interface_name=interface_name,
        ts_code=ts_code,
        start_date=stock_start_date,  # 使用股票上市日
        end_date=date_range.end_date,
        interface_config=interface_config,
        user_provided_dates=user_provided_dates,  # True
        stock_info=stock
    )
```

### 关键修改点

1. **`user_provided_dates = True`**
   - 让 `coverage_manager` 检测从 `start_date` 开始的所有缺失日期
   - 不再只检测 `max_existing_date` 之后的新日期

2. **`start_date = stock.get('list_date') or DEFAULT_STOCK_START_DATE`**
   - 使用每只股票的上市日期作为起始点
   - 无上市日则使用默认值 `20050101`

---

## 影响范围

### 受影响场景

| 场景 | 修改前 | 修改后 |
|------|--------|--------|
| `--update --ts_code xxx` | 只检测最新数据之后 | 从上市日全量检测 |
| `--update`（所有股票） | 只检测最新数据之后 | 从上市日全量检测 |

### 不受影响场景

| 场景 | 行为 |
|------|------|
| `--ts_code xxx`（不带 --update） | 保持原有增量逻辑（通过 `download_single_stock`） |
| `--start_date xxx --end_date xxx` | 按用户指定范围下载 |

---

## 涉及的 Type A 接口

以下接口使用交易日历缺口检测模式：

| 接口 | 数据日期字段 | 配置文件 |
|------|-------------|----------|
| `cyq_chips` | `trade_date` | cyq_chips.yaml |
| `moneyflow_dc` | `trade_date` | moneyflow_dc.yaml |
| `stk_factor_pro` | `trade_date` | stk_factor_pro.yaml |

配置特征：
```yaml
duplicate_detection:
  enabled: true
  date_column: trade_date
  stock_level_detection: true
```

---

## 测试验证

### 测试命令

```bash
# 测试单只股票的全量缺口检测
python app4/main.py --update --interface stk_factor_pro --ts_code 000001.SZ

# 预期结果：从 19910403（平安银行上市日）开始检测所有缺失日期
```

### 验证日志

修改后应看到：
```
[stk_factor_pro/000001.SZ] 交易日历缺口检测 (19910403 ~ 20260218)
[000001.SZ] 缺失 XX 个交易日
```

而非：
```
[000001.SZ] 用户未提供日期，只检测 20260213 之后的缺失日期
```

---

## 实施步骤

1. 修改 `app4/update/update_manager.py` 的 `_update_with_stock_gap_detection()` 方法
2. 添加 `from core.constants import DEFAULT_STOCK_START_DATE` 导入
3. 测试验证

---

## 文档信息

- 创建日期：2026-02-18
- 作者：Claude
- 相关问题：`--update` 模式不检测历史缺口
