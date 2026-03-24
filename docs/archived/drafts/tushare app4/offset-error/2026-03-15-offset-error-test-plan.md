# reverse_date_range / offset / date_anchor 测试方案

## 测试目标

验证以下结论在代码和配置层都成立：

1. 非原子 offset 会保存半截数据
2. `commit_on_success: true` 能阻止当前窗口的半截数据落盘
3. 只有 `is_date_anchor: true + commit_on_success: true` 才能保证“单日完整或单日为空”
4. 稀疏接口保持 date range 时，不会因为原子 offset 产生错误保存

## 测试范围

覆盖三个层面：

- 单元测试：`PaginationExecutor` 的 offset 行为
- 组合测试：`PaginationComposer` 的 date_anchor 拆分行为
- 集成测试：下载到存储链路是否真的不保存中间结果

## 一、单元测试

### 1. 非原子 offset 异常时会产生部分保存

目标：

- 复现当前默认行为
- 证明问题真实存在

输入场景：

- 第 1 页返回数据
- 第 2 页抛出异常
- `commit_on_success = false`

断言：

- 已有页数据被回调或保存
- 异常继续向上抛出

说明：

仓库里已有相关测试，可继续保留并作为基线。

### 2. 原子 offset 异常时不保存当前窗口数据

输入场景：

- 第 1 页返回数据
- 第 2 页抛出异常
- `commit_on_success = true`

断言：

- `on_data_ready` 不被调用
- `save_callback` 不被调用
- 当前窗口没有任何数据落盘

### 3. 原子 offset 成功时只提交一次

输入场景：

- 多页成功
- 最后一页不足 `limit`

断言：

- 所有页数据聚合后只提交一次
- 提交总数正确

## 二、分页组合测试

### 4. `reverse_date_range + is_date_anchor` 会拆成逐日请求

目标：

- 验证分页器不是继续传 `start_date/end_date`
- 而是生成单独的日期锚点参数

输入场景：

- `start_date=20250101`
- `end_date=20250103`
- `trade_date.is_date_anchor = true`

断言：

- 生成 3 个请求
- 每个请求只包含一个 `trade_date`
- 不再带原始 `start_date/end_date`
- 顺序符合 reverse 语义

### 5. 非 date_anchor 接口继续按窗口生成请求

输入场景：

- `window_size_days = 30`
- 未配置 `is_date_anchor`

断言：

- 生成的是按窗口切分的 `start_date/end_date`
- 不会错误拆成逐日请求

## 三、集成测试

### 6. 非 date_anchor 多日窗口在非原子 offset 下会保存脏数据

目标：

- 从下载到存储整条链路验证真实风险

输入场景：

- 一个窗口覆盖多个日期
- API 返回数据顺序跨越多个日期
- offset 第 2 页失败
- `commit_on_success = false`

断言：

- 存储层收到的数据包含前几页
- 其中至少一个日期数据不完整

### 7. 非 date_anchor 多日窗口在原子 offset 下不保存当前窗口

输入场景：

- 同上
- `commit_on_success = true`

断言：

- 当前窗口零保存
- buffer / queue 中没有该窗口数据

说明：

- 这验证“窗口原子”
- 但不等于“单日原子”

### 8. date_anchor 单日窗口在原子 offset 下实现单日原子

输入场景：

- `trade_date.is_date_anchor = true`
- 连续 3 个交易日任务
- 第 2 天 offset 第 2 页失败

断言：

- 第 1 天完整保存
- 第 2 天完全不保存
- 第 3 天如果未执行则无数据，若执行成功则完整保存
- 不会出现“第 2 天只保存了部分股票”的情况

这是最重要的验收测试。

## 四、配置回归测试

### 9. A 类接口配置检查

目标：

- 确认高密度接口都已经配置 `is_date_anchor: true`
- 且 offset 已配置 `commit_on_success: true`

建议检查的接口至少包括：

- `daily`
- `daily_basic`
- `moneyflow`
- `moneyflow_dc`
- `moneyflow_cnt_ths`

### 10. B 类接口配置检查

目标：

- 确认稀疏接口没有被误改为 date_anchor
- 但已配置 `commit_on_success: true`

建议检查的接口至少包括：

- `repurchase`
- `stock_st`
- `suspend_d`
- `namechange`
- `block_trade`

## 五、覆盖率与重跑验证

### 11. 失败日期应在下次重跑时被重新下载

输入场景：

- 某个 date_anchor 单日任务失败
- 当天未落盘
- 第二次执行同一范围

断言：

- 失败日期不会被 coverage 误判为已完成
- 会重新生成该日期任务并正常下载

### 12. 已成功日期不会重复下载

输入场景：

- 第 1 天已完整成功
- 第 2 天失败
- 第二次执行相同范围

断言：

- 第 1 天被识别为已完成
- 第 2 天重新执行

## 六、性能验证

### 13. 高密度接口改为 date_anchor 后请求量应可接受

目标：

- 验证改造没有明显增加请求次数

比较对象：

- 改造前：`window_size_days=1` 或多日窗口 + offset
- 改造后：单日 `date_anchor` + offset

断言：

- 总请求页数大致同量级
- 不出现明显退化

### 14. 稀疏接口保持 range 时请求量明显少于逐日 anchor

目标：

- 验证不全量 date_anchor 的理由成立

断言：

- 同样时间区间下，range 模式请求次数远少于逐日模式

## 测试数据建议

建议构造两类 mock 数据：

### 高密度数据

- 单个交易日超过一页
- 多个股票覆盖同一天
- 能稳定复现“单日被 offset 截断”的问题

### 稀疏数据

- 多个日期合计数据不多
- 单天大多为空
- 用于证明逐日 anchor 会造成大量空请求

## 验收标准

最终验收以这三条为准：

1. 非原子 offset 的脏数据路径被测试稳定复现
2. 原子 offset 能确保当前窗口失败时零保存
3. `is_date_anchor + commit_on_success` 能确保失败时不会留下任何不完整日期

如果第 3 条没有被集成测试证明，就不能认为需求已经真正完成。

