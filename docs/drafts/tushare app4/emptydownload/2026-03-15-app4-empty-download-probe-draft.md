# App4 空结果探测记录方案总览

## 目标

把原先的一份总草案拆成分批实施文档，便于按风险和收益逐步落地。

拆分原则：

- 优先处理当前最容易重复空下载、且最适合同表占位的接口
- 保留现有 `CoverageManager.detect_stock_gaps()` 体系，把空占位作为补充，而不是替代
- 只采纳与当前代码结构、当前 parquet 使用习惯一致的建议

## 已采纳的关键建议

- 空占位方案是对现有缺口检测的补充，不替代现有 `stock_level_detection`
- “检测键”与 `output.primary_key` 必须区分
- 需要新增比当前 `stock` 更细的检测策略，例如 `stock_date`、`stock_anchor`
- `StorageManager.read_interface_data()` 应增加默认过滤空占位的参数
- 空结果写入 probe 的位置应放在下载执行层，而不是 `processor.py`

## 不采纳或暂不采纳

- 不把独立状态表作为第一版主方案
- 不先统一修改所有接口的 `dedup_enabled`
- 不在第一阶段对 `reverse_date_range` 和 `period_range` 大面积推广同表空占位
- 不把 `pledge_detail` 简单按存储里的 `ann_date` 反推成 `ts_code + ann_date` 请求键

## 分批文档

### 第一批

文件：

- [2026-03-15-app4-empty-download-probe-batch1-stock-loop.md](/home/quan/testdata/aspipe_v4/docs/drafts/tushare%20app4/emptydownload/2026-03-15-app4-empty-download-probe-batch1-stock-loop.md)

范围：

- `stock_loop`
- 且 `duplicate_detection.stock_level_detection = true`

接口：

- `cyq_chips`
- `fina_audit`
- `stk_rewards`
- `pledge_detail`

### 第二批

文件：

- [2026-03-15-app4-empty-download-probe-batch2-candidate-extensions.md](/home/quan/testdata/aspipe_v4/docs/drafts/tushare%20app4/emptydownload/2026-03-15-app4-empty-download-probe-batch2-candidate-extensions.md)

范围：

- 语义上接近股票级单键判断，但当前代码还不是这个检测路径的接口

接口：

- `stk_factor_pro`
- `moneyflow_dc`

### 第三批

文件：

- [2026-03-15-app4-empty-download-probe-batch3-deferred-interfaces.md](/home/quan/testdata/aspipe_v4/docs/drafts/tushare%20app4/emptydownload/2026-03-15-app4-empty-download-probe-batch3-deferred-interfaces.md)

范围：

- 当前不建议实施空占位的接口与模式

包括：

- 大多数 `reverse_date_range`
- 当前按全局 `period` 判定的 `period_range`
- `offset`
- `type_split`
- `trade_cal`

## 当前推荐实施顺序

1. 先实现第一批文档
2. 只打通 `cyq_chips`
3. 验证真实记录覆盖占位、删除 parquet 后可重下、默认读取过滤三条链路
4. 再扩到 `fina_audit`、`stk_rewards`、`pledge_detail`
5. 第二批和第三批只保留设计，不抢先编码
