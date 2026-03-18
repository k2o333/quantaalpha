# App4 空结果探测记录方案 第一批

## 范围

只覆盖：

- `stock_loop`
- 且 `duplicate_detection.stock_level_detection = true`

接口：

- `cyq_chips`
- `fina_audit`
- `stk_rewards`
- `pledge_detail`

## 目标

在保留现有 `CoverageManager.detect_stock_gaps()` 的前提下，为“API 返回空结果”的情况写入同表空占位，避免下次继续下载同一查询键。

这个方案是补充，不替代现有缺口检测。

现有体系负责：

- 识别哪些键缺失，需要下载

空占位负责：

- 某个键已被下载过，但 Tushare 返回空
- 下次缺口检测或存在性检测时，将该键视为“已探测”

## 统一字段

所有第一批接口统一增加：

- `tushare_download`
- `is_empty_probe`

字段含义：

- `tushare_download = 1`: 该记录代表某个查询键已请求过
- `is_empty_probe = 1`: 该记录是空结果占位
- `is_empty_probe = 0`: 该记录是真实业务数据

## 实现原则

### 1. 同表占位

不新增独立状态表。

原因：

- 你会直接删业务 parquet
- 同表占位可随 parquet 一起删除，不会不同步

### 2. 检测键与存储主键分离

空占位使用的是“检测键”，不是 `output.primary_key`。

例子：

- `cyq_chips` 的存储主键包含 `price`、`percent`
- 但空占位检测键仍应是 `ts_code + trade_date`

### 3. 写入点在下载执行层

空结果 probe 不应放在 `processor.py`。

建议插入点：

- `PaginationExecutor._execute_single_request()`
- 或其上层调用点，在 `make_request()` 返回空列表后决定是否写入 probe

### 4. 读取默认过滤

`StorageManager.read_interface_data()` 需要新增参数，默认过滤掉空占位。

建议参数：

- `exclude_empty_probe: bool = True`

## 接口逐个方案

## 1. cyq_chips

### 检测模式

- 现有缺口检测类型：交易日型
- 现有入口：`detect_stock_gaps()` -> `_detect_trade_date_gaps()`

### 检测键

- `ts_code + trade_date`

### 占位字段

- `ts_code`
- `trade_date`
- `tushare_download`
- `is_empty_probe`

### 说明

`cyq_chips` 同一日会有多行 `price + percent` 明细，因此：

- 存储主键不是检测键
- 空占位只表示“该股票该交易日已经探测过，没有返回任何明细”

### 需要新增的检测策略

建议新增：

- `stock_date`

语义：

- 检查 `ts_code + trade_date` 是否已有真实记录
- 若无真实记录，但有同键 `is_empty_probe = 1`，也视为已覆盖

## 2. fina_audit

### 检测模式

- 现有缺口检测类型：报告期型
- 现有入口：`detect_stock_gaps()` -> `_detect_report_period_gaps()`

### 检测键

- `ts_code + end_date`

### 占位字段

- `ts_code`
- `end_date`
- `tushare_download`
- `is_empty_probe`

### 说明

这里的空占位表示：

- 该股票该报告期已经请求过
- Tushare 对应请求未返回任何审计记录

建议新增检测策略：

- `stock_period`

## 3. stk_rewards

### 检测模式

- 现有缺口检测类型：日期锚定型
- `end_date.is_date_anchor = true`
- 现有入口：`detect_stock_gaps()` -> `_detect_date_anchor_gaps()`

### 检测键

- `ts_code + end_date`

### 占位字段

- `ts_code`
- `end_date`
- `tushare_download`
- `is_empty_probe`

### 说明

虽然键上看与 `fina_audit` 很像，但语义不同：

- `fina_audit` 更接近报告期缺口
- `stk_rewards` 是日期锚定遍历

因此建议不要简单复用 `stock_period`，而是保留独立策略名：

- `stock_anchor`

## 4. pledge_detail

### 检测模式

- 现有缺口检测类型：无日期过滤型
- 现有入口：`detect_stock_gaps()` -> `_detect_no_date_filter_gaps()`

### 检测键

- `ts_code`

### 占位字段

- `ts_code`
- `tushare_download`
- `is_empty_probe`

### 说明

虽然存储数据里有 `ann_date`，但请求参数只有 `ts_code`。

所以对空占位而言，请求键仍应是：

- `ts_code`

这里空占位表示：

- 这只股票的 pledge_detail 已请求过
- Tushare 没有返回任何质押记录

## 代码改动建议

### CoverageManager

新增或扩展以下策略：

- `stock_date`
- `stock_period`
- `stock_anchor`

不要继续把所有股票级判断都塞进当前粗粒度的 `stock`。

### StorageManager

新增：

- `read_interface_data(..., exclude_empty_probe: bool = True)`
- `write_empty_probe()` 或等价辅助方法

### PaginationExecutor

新增：

- 空结果时判断是否写入 probe 的逻辑
- `should_write_empty_probe()` 或等价判断

### 配置项

建议第一批接口在 `duplicate_detection` 下新增：

- `empty_probe_enabled: true`
- `empty_probe_key: stock_date | stock_period | stock_anchor | stock`

## 去重规则

必须满足：

- 真实记录优先于空占位
- 同键真实记录写入后，应删除或覆盖同键空占位

否则会出现：

- 占位顶掉真实记录
- 后续查询误读占位

## 读取规则

默认业务读取必须排除：

- `is_empty_probe = 1`

只有覆盖率检测、probe 检测、调试工具可以显式读取空占位。

## 实施顺序

1. 先只做 `cyq_chips`
2. 打通 `stock_date` 检测策略
3. 补 `read_interface_data(... exclude_empty_probe=True)`
4. 验证真实记录覆盖 probe
5. 再扩到 `fina_audit`、`stk_rewards`、`pledge_detail`
