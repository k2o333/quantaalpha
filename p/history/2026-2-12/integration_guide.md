# Stock Loop 智能增量下载集成指南

## 一、文件说明

本目录包含以下文件：

1. **stock_loop_incremental_download_plan.md** - 详细设计方案文档
2. **stock_loop_planner.py** - 核心实现代码
3. **interface_config_examples.yaml** - 接口配置示例
4. **integration_guide.md** - 本集成指南

---

## 二、集成步骤

### 步骤 1: 复制核心文件

将 `stock_loop_planner.py` 复制到项目的 core 目录：

```bash
cp /home/quan/testdata/aspipe_v4/p/2026-2-12/stock_loop_planner.py \
   /home/quan/testdata/aspipe_v4/app4/core/stock_loop_planner.py
```

---

### 步骤 2: 修改 downloader.py

编辑 `/home/quan/testdata/aspipe_v4/app4/core/downloader.py`，修改 `download_single_stock` 方法：

#### 2.1 添加导入

在文件顶部添加：

```python
from .stock_loop_planner import StockLoopPlanner, DownloadTask
```

#### 2.2 修改 download_single_stock 方法

找到 `download_single_stock` 方法（约第 416 行），替换为：

```python
def download_single_stock(
    self,
    interface_config: Dict[str, Any],
    stock: Dict[str, Any],
    params: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    下载单只股票的数据 - 智能增量版本

    Args:
        interface_config: 接口配置
        stock: 股票信息字典
        params: 基础请求参数

    Returns:
        下载的数据列表
    """
    ts_code = stock['ts_code']
    interface_name = interface_config['api_name']

    # 检查是否需要使用新的智能增量逻辑
    date_params = interface_config.get('date_params', {})
    use_smart_incremental = bool(date_params)  # 如果配置了 date_params 则使用新逻辑

    if not use_smart_incremental:
        # 使用原有逻辑（保持向后兼容）
        return self._download_single_stock_legacy(
            interface_config, stock, params
        )

    # 使用新的智能增量逻辑
    try:
        planner = StockLoopPlanner(
            coverage_manager=self.coverage_manager,
            trade_calendar_provider=self.get_trade_calendar,
            config_loader=self.config_loader
        )

        # 生成下载计划
        tasks = planner.plan_download(
            interface_name=interface_name,
            ts_code=ts_code,
            interface_config=interface_config,
            user_params=params
        )

        if not tasks:
            logger.info(f"[{interface_name}/{ts_code}] 无需下载，数据已完整")
            return []

        # 执行下载任务
        all_data = []
        for task in tasks:
            logger.info(f"[{interface_name}/{ts_code}] {task.reason}: {task.params}")

            # 调用分页执行器下载数据
            data = self._execute_download_with_params(
                interface_config, task.params
            )

            if data:
                all_data.extend(data)

        # 保存数据到 buffer
        if all_data and self.storage_manager:
            self.storage_manager.add_to_buffer(interface_name, all_data)

        return all_data

    except Exception as e:
        logger.error(f"智能增量下载失败 [{interface_name}/{ts_code}]: {e}")
        # 失败时回退到原有逻辑
        return self._download_single_stock_legacy(
            interface_config, stock, params
        )


def _download_single_stock_legacy(
    self,
    interface_config: Dict[str, Any],
    stock: Dict[str, Any],
    params: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    原有的下载逻辑（保持向后兼容）
    """
    # 将原有的 download_single_stock 代码移到这里
    # ... 原有代码 ...
    pass


def _execute_download_with_params(
    self,
    interface_config: Dict[str, Any],
    params: Dict[str, Any]
) -> Optional[List[Dict[str, Any]]]:
    """
    使用指定参数执行下载

    Args:
        interface_config: 接口配置
        params: 请求参数

    Returns:
        下载的数据列表
    """
    try:
        # 使用分页执行器下载数据
        from .pagination import create_context_with_legacy_support
        from .pagination_executor import PaginationExecutor

        # 获取交易日历
        start_date = params.get('start_date', '20050101')
        end_date = params.get('end_date', datetime.now().strftime('%Y%m%d'))
        trade_calendar = self.get_trade_calendar(start_date, end_date)

        # 创建分页上下文
        pagination_context = create_context_with_legacy_support(
            interface_config=interface_config,
            trade_calendar=trade_calendar,
            stock_list=[{'ts_code': params.get('ts_code')}],
            coverage_manager=self.coverage_manager,
            force_download=self.force_download
        )

        # 创建分页执行器
        executor = PaginationExecutor()

        # 执行下载
        data = executor.execute(
            interface_config=interface_config,
            base_params=params,
            context=pagination_context,
            make_request=self._make_request,
            coverage_manager=self.coverage_manager
        )

        return data

    except Exception as e:
        logger.error(f"下载失败: {e}")
        return None
```

---

### 步骤 3: 为接口添加 date_params 配置

为需要启用智能增量下载的接口添加 `date_params` 配置。

#### 3.1 编辑接口配置文件

例如，编辑 `/home/quan/testdata/aspipe_v4/app4/config/interfaces/daily_basic.yaml`：

```yaml
api_name: daily_basic
# ... 原有配置 ...

# 添加以下配置
date_params:
  mode: "date_range"
  data_date_column: "trade_date"
  input_mapping:
    start_date: "start_date"
    end_date: "end_date"
  default_start_date: "20000101"
  lookback_days: 7

duplicate_detection:
  enabled: true
  date_column: "trade_date"
  threshold: 0.95
```

#### 3.2 优先配置的接口

建议按以下优先级为接口添加配置：

1. **高频使用接口**（优先）
   - `daily` - 日线行情
   - `daily_basic` - 每日指标
   - `moneyflow` - 个股资金流向

2. **财报类接口**
   - `income_vip` - 利润表
   - `balancesheet_vip` - 资产负债表
   - `cashflow_vip` - 现金流量表
   - `fina_indicator_vip` - 财务指标

3. **其他接口**
   - `disclosure_date` - 披露日期
   - `block_trade` - 大宗交易
   - 其他 stock_loop 模式的接口

---

### 步骤 4: 测试验证

#### 4.1 测试全历史下载

```bash
# 测试一个全新的股票（假设没有数据）
/root/miniforge3/envs/get/bin/python app4/main.py \
    --update --interface daily_basic --ts_code 000001.SZ
```

预期输出：
```
[daily_basic/000001.SZ] 日期参数模式: date_range
[daily_basic/000001.SZ] 已有数据: 0 天
[daily_basic/000001.SZ] 无现有数据，使用默认起始日期 20000101
[daily_basic/000001.SZ] 自动确定范围: 20000101 ~ 20260212
[daily_basic/000001.SZ] full_history: {'ts_code': '000001.SZ', 'start_date': '20000101', 'end_date': '20260212'}
```

#### 4.2 测试增量下载

再次运行相同命令：

```bash
/root/miniforge3/envs/get/bin/python app4/main.py \
    --update --interface daily_basic --ts_code 000001.SZ
```

预期输出：
```
[daily_basic/000001.SZ] 日期参数模式: date_range
[daily_basic/000001.SZ] 已有数据: 5000 天
[daily_basic/000001.SZ] 从最新日期 20250201 回溯至 20250125
[daily_basic/000001.SZ] 自动确定范围: 20250125 ~ 20260212
[daily_basic/000001.SZ] 发现 1 个缺失段
[daily_basic/000001.SZ] gap_fill: {'ts_code': '000001.SZ', 'start_date': '20250202', 'end_date': '20260212'}
```

#### 4.3 测试数据完整时跳过

如果数据已完整：

```
[daily_basic/000001.SZ] 日期参数模式: date_range
[daily_basic/000001.SZ] 已有数据: 5800 天
[daily_basic/000001.SZ] 数据已完整覆盖，无需下载
```

---

## 三、常见问题

### Q1: 现有接口没有 date_params 配置会怎样？

**A:** 会自动使用原有的下载逻辑，保持向后兼容，不会影响现有功能。

### Q2: 如何确定 data_date_column 的值？

**A:** 查看接口返回数据的日期字段名：
- 日线数据通常是 `trade_date`
- 财报数据通常是 `end_date` 或 `ann_date`
- 日历数据通常是 `cal_date`

### Q3: 如何处理特殊接口？

**A:** 对于特殊接口，可以在 `stock_loop_planner.py` 中创建子类：

```python
class DisclosureDatePlanner(StockLoopPlanner):
    """披露日期接口的特殊处理"""

    def _generate_anchor_dates(self, interface_name, start_date, end_date):
        # 自定义锚点日期生成逻辑
        pass
```

### Q4: 如何调试下载计划？

**A:** 可以添加 `--log-level DEBUG` 参数查看详细日志：

```bash
/root/miniforge3/envs/get/bin/python app4/main.py \
    --update --interface daily_basic --ts_code 000001.SZ \
    --log-level DEBUG
```

---

## 四、回滚方案

如果出现问题，可以：

1. **临时禁用智能增量**：删除接口配置中的 `date_params` 部分
2. **完全回滚**：恢复 `downloader.py` 的备份文件
3. **强制全量下载**：使用 `--force` 参数

---

## 五、性能优化建议

1. **批量查询**：对于 `trade_date` 模式的接口，考虑将多个日期合并为一个范围查询
2. **缓存优化**：已有日期查询结果可以缓存，避免重复读取
3. **并发控制**：缺口段较多时，可以并行下载多个段

---

## 六、后续优化方向

1. **自动配置生成**：根据接口返回数据自动推断 date_params 配置
2. **智能缺口合并**：将多个小缺口合并为一个大范围下载，减少 API 调用次数
3. **数据质量检测**：检测并修复数据异常（如某天的数据缺失）
