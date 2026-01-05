# TuShare API query_limit 参数详解

**创建日期**: 2026年1月2日
**适用范围**: aspipe_v4 项目配置文件

---

## 一、query_limit 是什么？

### 1.1 定义
`query_limit` 是 TuShare API 服务端对**单次请求**返回记录数的**上限限制**。

### 1.2 关键特征
- ✅ **单次请求限制**：限制的是一次 HTTP API 调用能够返回的最大记录数
- ✅ **服务端控制**：由 TuShare API 服务端强制执行，客户端无法突破
- ❌ **不是每天限制**：不限制每天可以调用多少次
- ❌ **不是总次数限制**：不限制整个脚本运行期间的总请求次数
- ❌ **不是请求数限制**：限制的是返回的记录数，不是请求的次数

---

## 二、实际使用场景分析

### 2.1 配置示例

```yaml
# income_vip.yaml
permissions:
  min_points: 5000
  rate_limit: 60
  query_limit: 10000  # ← 单次请求最多返回 10000 条记录
```

### 2.2 实际运行情况

从日志分析（income_vip 接口，2023年全年数据）：

```
配置参数：
- query_limit: 10000 (配置文件)
- window_size_days: 365 (配置文件)
- 日期范围: 20230103 - 20231229 (365天)

API 响应：
- 返回记录数: 9000 条
- query_limit 限制: 10000 条
- 占比: 9000/10000 = 90%

结论：
- 9000 < 10000，未达到 API 限制
- 数据完整，没有被截断
```

---

## 三、代码中的使用方式

### 3.1 配置读取

**位置**: `app4/core/downloader.py:347`

```python
# 从接口配置中读取 query_limit
query_limit = interface_config.get('permissions', {}).get('query_limit', 6000)
```

**说明**:
- 默认值为 6000 条
- 不同接口有不同的限制值（见下表）
- 仅用于监控和告警，不直接控制 API 调用

### 3.2 数据完整性检查

**位置**: `app4/core/downloader.py:345-350`

```python
if window_data:
    # 检查数据完整性
    query_limit = interface_config.get('permissions', {}).get('query_limit', 6000)

    # 记录数据量指标
    performance_monitor.record_metric('data_size', len(window_data), {
        'interface': interface_config['api_name'],
        'window': f"{window_start}-{window_end}",
        'ts_code': params.get('ts_code', 'unknown')
    })

    if len(window_data) >= query_limit:
        logger.warning(f"Window {window_start}-{window_end} returned {len(window_data)} "
                     f"records, which may be truncated (API limit: {query_limit})")
        performance_monitor.check_alerts('data_size', len(window_data), {
            'interface': interface_config['api_name'],
            'window': f"{window_start}-{window_end}",
            'ts_code': params.get('ts_code', 'unknown')
        })
```

**说明**:
- 如果返回数据量 `>= query_limit`，发出警告
- 提示可能存在数据截断
- 触发性能告警机制
- **注意**：这只是客户端的监控告警，实际限制由 API 服务端执行

---

## 四、各接口的 query_limit 配置

### 4.1 VIP 接口（高限额）

| 接口名称 | query_limit | 说明 |
|-----------|-------------|------|
| income_vip | 10000 | 利润表（VIP） |
| balancesheet_vip | 10000 | 资产负债表（VIP） |
| cashflow_vip | 10000 | 现金流量表（VIP） |
| fina_indicator_vip | 10000 | 财务指标（VIP） |
| forecast_vip | 10000 | 业绩预告（VIP） |
| express_vip | 10000 | 业绩快报（VIP） |
| fina_mainbz_vip | 100 | 主营业务构成（VIP） |

### 4.2 普通财务接口

| 接口名称 | query_limit | 说明 |
|-----------|-------------|------|
| income | 10000 | 利润表（普通） |
| balancesheet | 10000 | 资产负债表（普通） |
| cashflow | 10000 | 现金流量表（普通） |
| fina_indicator | 100 | 财务指标（普通） |
| fina_mainbz | 100 | 主营业务构成（普通） |
| forecast | 10000 | 业绩预告（普通） |
| express | 10000 | 业绩快报（普通） |

### 4.3 行情和基础数据接口

| 接口名称 | query_limit | 说明 |
|-----------|-------------|------|
| daily | 10000 | 日线行情 |
| daily_basic | 10000 | 每日基本面指标 |
| pro_bar | 6000 | Pro 日线行情 |
| trade_cal | 10000 | 交易日历 |
| stock_basic | 10000 | 股票基础信息 |
| stock_company | 10000 | 上市公司信息 |
| stock_st | 1000 | ST 股票列表 |
| stock_hsgt | 2000 | 沪港通数据 |

### 4.4 其他接口

| 接口名称 | query_limit | 说明 |
|-----------|-------------|------|
| top10_holders | 10000 | 前十大股东 |
| top10_floatholders | 10000 | 前十大流通股东 |
| pledge_detail | 1000 | 质押明细 |
| pledge_stat | 1000 | 质押统计 |
| dividend | 10000 | 分红送股 |
| broker_recommend | 1000 | 券商评级 |
| block_trade | 1000 | 大宗交易 |

---

## 五、与 window_size_days 的关系

### 5.1 参数对比

| 参数 | 含义 | 作用 | 位置 |
|------|------|------|------|
| `query_limit` | **单次请求返回记录数上限** | API 服务端限制 | `permissions.query_limit` |
| `window_size_days` | **日期分页的窗口大小** | 客户端控制请求范围 | `pagination.window_size_days` |

### 5.2 相互影响

```yaml
# income_vip.yaml 配置
pagination:
  enabled: true
  mode: "date_range"
  window_size_days: 365  # 每次请求 365 天的数据

permissions:
  query_limit: 10000  # 单次最多返回 10000 条
```

**实际运行情况**:
- 请求范围：365 天 × 约 242 个交易日
- API 返回：9000 条记录
- query_limit: 10000 条上限
- 结果：9000 < 10000，未达限制，数据完整

**如果 window_size_days 设置过大**:
- 可能导致返回记录数接近 query_limit
- 可能触发数据截断警告
- 影响性能（单次请求时间过长）

**如果 window_size_days 设置过小**:
- 需要多次请求才能覆盖全部日期范围
- 增加总请求次数
- 提高失败重试的灵活性

---

## 六、最佳实践建议

### 6.1 如何避免达到 query_limit

**原则**: 确保单次请求的返回记录数 `<= query_limit * 90%`

**方法**:
1. **合理设置窗口大小**：
   ```yaml
   # 推荐：根据接口特性调整
   income_vip: window_size_days: 60  # 约 42 个交易日
   daily: window_size_days: 365       # 交易日历可以更大
   ```

2. **监控返回数据量**：
   ```python
   # 代码会自动检查并发出警告
   if len(window_data) >= query_limit:
       logger.warning("Data may be truncated")
   ```

3. **使用分页机制**：
   - 系统会自动按窗口分多次请求
   - 避免单次请求返回过多数据

### 6.2 不同场景的推荐配置

| 场景 | window_size_days | query_limit | 说明 |
|-------|----------------|-------------|------|
| 全量历史数据下载 | 30-60 | 10000 | 平衡性能和完整性 |
| 增量更新（最近1年） | 90-180 | 10000 | 可以使用较大窗口 |
| 单只股票历史数据 | 365 | 10000 | 单股票数据量小，窗口可大 |
| 全市场即时数据 | 1-7 | 10000 | 最小窗口，保证时效性 |

### 6.3 性能优化建议

**问题场景**（从实际日志）：
```
请求时间：94.61 秒（超过 30 秒阈值）
返回记录：9000 条
警告：数据量接近 API 限制
```

**优化方案**：
1. **减小窗口大小**：从 365 天改为 60 天
   - 单次请求数据量减少
   - 请求时间预计降至 20-30 秒
   - 总时间可能更短（因为并行请求）

2. **调整并发策略**：
   - 虽然总请求次数增加，但并发执行
   - 总耗时 = 单次时间 + 请求次数 × 并发间隔

3. **监控和告警**：
   - 设置合理的告警阈值（30秒）
   - 记录详细性能数据
   - 动态调整窗口大小

---

## 七、常见问题解答

### Q1: query_limit 可以修改吗？

**A**: 不能。`query_limit` 是 TuShare API 服务端的强制限制，客户端无法修改。配置文件中的值仅用于客户端监控和告警。

### Q2: 如果返回数据 = query_limit 怎么办？

**A**:
- 说明可能存在数据截断
- 系统会自动发出警告
- 建议减小 `window_size_days`
- 或者检查日期范围是否过大

### Q3: 不同接口的 query_limit 为什么不同？

**A**: TuShare 根据以下因素设定不同限制：
- 数据复杂度（字段数量）
- 数据计算成本
- 服务器负载考虑
- 用户积分等级

### Q4: query_limit 和 rate_limit 有什么区别？

| 参数 | 限制对象 | 单位 | 作用 |
|------|---------|------|------|
| `query_limit` | 单次请求返回记录数 | 条 | 防止单次请求返回过多数据 |
| `rate_limit` | 单位时间请求次数 | 次/分钟 | 防止请求过于频繁 |

### Q5: 如何查询某个接口的 query_limit？

**A**:
1. 查看配置文件：`config/interfaces/{interface_name}.yaml`
2. 查看第 8 行左右的 `query_limit` 值
3. 或者查看 TuShare 官方文档（但可能需要账号权限）

---

## 八、总结

### 8.1 核心要点

1. **query_limit 是单次请求的返回记录数上限**
   - 不是每天限制
   - 不是总次数限制
   - 不是请求数限制

2. **由 TuShare API 服务端控制**
   - 客户端无法突破
   - 配置文件中的值用于监控
   - 不同接口有不同限制

3. **配合 window_size_days 使用**
   - 合理设置窗口大小
   - 避免数据截断
   - 优化性能

### 8.2 实际应用

**当前问题（income_vip）**:
- 配置：query_limit = 10000
- 实际返回：9000 条
- 状态：未达限制，数据完整
- 问题：请求时间过长（94秒）

**优化方向**:
- 减小窗口：365 天 → 60 天
- 单次数据量减少：9000 → 约 1500 条
- 请求时间降低：94 秒 → 20-30 秒
- 并发请求效率提升

---

**文档版本**: 1.0
**最后更新**: 2026年1月2日
**维护者**: aspipe_v4 开发团队
