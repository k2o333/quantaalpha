# API错误重试与分页批次保存需求文档

## 一、背景分析

### 1.1 问题现象（日志分析）

```
2026-03-07 00:00:00,527 - core.downloader - INFO - Downloaded 6000 records for daily_basic
2026-03-07 00:00:00,528 - core.pagination_executor - INFO - [daily_basic] 第139页完成 - offset=828000, 请求limit=6000, 实际返回=6000条
2026-03-07 00:00:02,484 - core.downloader - ERROR - API error for daily_basic: 查询数据失败，请确认参数！可以反馈管理员协助您排查问题
2026-03-07 00:00:02,484 - core.pagination_executor - INFO - [daily_basic] 第140页请求无数据 - offset=834000, limit=6000
2026-03-07 00:00:02,484 - core.pagination_executor - INFO - [daily_basic] Offset分页结束 - 总页数=139, 总记录数=834000
```

**问题**：
- 第140页请求返回API错误后，立即结束分页，无重试机制
- 所有834000条数据在内存中累积，直到分页结束才保存
- 若程序在分页过程中崩溃，将丢失所有已下载数据

### 1.2 当前代码逻辑

#### 重试机制（downloader.py `_make_request`方法）
- 当前仅对网络异常和频率限制进行重试
- 对于API返回的业务错误（code != 0），只有"频繁"相关错误才重试
- 其他业务错误（如"查询数据失败"）直接返回空列表，触发分页结束

#### 分页保存（pagination_executor.py `_execute_single_request`方法）
- offset分页模式下，所有数据累积到`all_data`列表
- 分页完成后才返回数据，由上层统一保存
- 无中间保存机制，存在内存压力和数据丢失风险

---

## 二、需求详述

### 2.1 API错误重试机制

#### 2.1.1 重试策略

| 重试次数 | 重试间隔 | 累计时间 |
|---------|---------|---------|
| 1-3次 | 10秒 | 30秒 |
| 4-10次 | 60秒 | 450秒（7.5分钟） |

**总计**：最多重试10次，总等待时间约8分钟

#### 2.1.2 适用场景

需要重试的API错误类型：
1. **网络错误**：连接超时、读取超时、连接重置
2. **服务端错误**：HTTP 500/502/503/504
3. **频率限制**：返回码包含"频繁"、"limit"关键字
4. **临时性业务错误**：返回码包含"查询数据失败"、"服务器繁忙"等临时性错误

**不需要重试的场景**：
1. **参数错误**：返回码明确指出参数无效（如日期格式错误）
2. **权限错误**：返回码指出无权限访问
3. **数据不存在**：正常的数据不存在情况（应正常结束分页）

#### 2.1.3 重试失败处理

当10次重试全部失败后：
1. 记录详细的失败日志（包含接口名、参数、错误信息、重试次数）
2. 触发批次保存流程，保存当前已下载的所有分页数据
3. 返回已保存的记录数，标记该批次为"部分成功"

### 2.2 分页批次保存机制

#### 2.2.1 保存触发条件

| 触发条件 | 说明 |
|---------|------|
| 每50页 | 正常分页过程中，每完成50页触发一次保存 |
| API错误重试失败 | 10次重试失败后，保存已下载数据 |
| 分页结束 | 正常结束（返回数据少于limit）时保存剩余数据 |

#### 2.2.2 保存流程

```
触发保存
    ↓
批次内去重（复用 processor._remove_duplicates）
    ↓
调用 save_callback（复用 storage.add_to_buffer）
    ↓
清空内存缓冲区
    ↓
记录保存日志
```

#### 2.2.3 去重策略

- **批次内去重**：每次保存前，对当前批次数据按主键去重
- **复用已有功能**：使用 `processor._remove_duplicates` 方法
- **保留最新记录**：去重时保留 `_update_time` 最大的记录

#### 2.2.4 数据结构

```python
# 分页执行过程中的状态
class PaginationState:
    batch_data: List[Dict]      # 当前批次累积的数据
    batch_page_count: int       # 当前批次已下载页数
    total_saved_records: int    # 已保存的总记录数
    save_interval: int = 50     # 每50页保存一次
```

---

## 三、代码修改范围

### 3.1 downloader.py

**修改方法**：`_make_request`

**修改内容**：
1. 增强错误分类逻辑，识别临时性业务错误
2. 实现分层重试策略（前3次10秒，后7次60秒）
3. 增加重试状态回调，通知上层当前重试进度

**新增方法**：
```python
def _should_retry_api_error(self, error_msg: str, code: int) -> bool:
    """判断API错误是否应该重试"""
    pass

def _calculate_retry_delay_v2(self, attempt: int) -> float:
    """计算重试延迟（分层策略）"""
    pass
```

### 3.2 pagination_executor.py

**修改方法**：`_execute_single_request`

**修改内容**：
1. 增加`save_callback`参数，支持中间保存
2. 增加`page_save_interval`参数（默认50）
3. 在分页循环中检查是否达到保存间隔
4. 达到间隔时调用`save_callback`并清空缓冲区

**新增状态跟踪**：
```python
batch_data = []          # 当前批次数据
batch_page_count = 0     # 当前批次页数
total_saved_count = 0    # 已保存记录数
```

### 3.3 storage.py

**复用现有方法**：
- `add_to_buffer()` - 添加数据到缓冲区
- `flush_remaining_data()` - 刷新剩余数据

**无需修改**，现有功能已满足需求

### 3.4 processor.py

**复用现有方法**：
- `_remove_duplicates()` - 批次内去重

**无需修改**，现有功能已满足需求

---

## 四、接口设计

### 4.1 配置项

在 `config/settings.yaml` 中增加：

```yaml
request:
  retry:
    max_attempts: 10          # 最大重试次数
    quick_retry_count: 3      # 快速重试次数（前N次用短间隔）
    quick_retry_delay: 10     # 快速重试间隔（秒）
    slow_retry_delay: 60      # 慢速重试间隔（秒）
  
pagination:
  batch_save_interval: 50     # 每50页保存一次
  enable_batch_save: true     # 是否启用批次保存
```

### 4.2 回调接口

```python
# 分页执行器的保存回调
def save_callback(
    interface_name: str,
    data: List[Dict[str, Any]],
    is_final: bool = False  # 是否最终保存
) -> int:
    """
    保存数据的回调函数
    
    Returns:
        保存的记录数
    """
    pass

# 重试状态回调（可选）
def retry_callback(
    interface_name: str,
    attempt: int,
    max_attempts: int,
    delay: float,
    error_msg: str
) -> None:
    """重试状态通知回调"""
    pass
```

---

## 五、测试场景

### 5.1 API错误重试测试

| 场景 | 预期行为 |
|-----|---------|
| 第1次请求返回"频繁" | 10秒后重试 |
| 连续3次返回"频繁" | 每次间隔10秒重试 |
| 第4次返回"频繁" | 60秒后重试 |
| 连续10次失败 | 保存已下载数据，标记部分成功 |
| 返回"参数无效" | 不重试，正常结束 |

### 5.2 批次保存测试

| 场景 | 预期行为 |
|-----|---------|
| 下载50页正常 | 第50页后保存一次 |
| 下载100页正常 | 第50页、第100页各保存一次 |
| 第75页API错误且重试失败 | 保存前50页+后25页数据 |
| 分页正常结束 | 保存剩余数据 |

### 5.3 内存测试

| 场景 | 预期行为 |
|-----|---------|
| 下载100万条数据 | 内存不超过50页数据量 |
| 程序崩溃 | 已保存的数据不丢失 |

---

## 六、风险评估

### 6.1 兼容性风险

- **风险**：修改`_execute_single_request`签名可能影响现有调用
- **缓解**：新增参数使用默认值，保持向后兼容

### 6.2 性能风险

- **风险**：频繁保存可能增加IO开销
- **缓解**：每50页保存一次，IO开销可控；内存释放收益更大

### 6.3 数据一致性风险

- **风险**：批次保存的数据可能与后续数据有重复
- **缓解**：依赖`processor._remove_duplicates`的批次内去重；存储层的主键约束提供最终保障

---

## 七、实现优先级

| 优先级 | 功能 | 原因 |
|-------|------|------|
| P0 | API错误重试机制 | 避免因临时性错误导致数据丢失 |
| P0 | 批次保存机制 | 减少内存压力，提高数据安全性 |
| P1 | 配置项支持 | 提供灵活的参数调整能力 |
| P2 | 重试状态回调 | 便于监控和日志追踪 |

---

## 八、潜在风险与解决方案

### 8.1 返回值类型冲突（致命问题）

**问题描述**：

当前代码中，`_execute_single_request` 方法的返回值类型取决于 `on_data_ready` 参数：
- 有 `on_data_ready`：返回整数计数
- 无 `on_data_ready`：返回 `List[Dict]`

如果按需求文档设计，在 `_execute_single_request` 内部每50页保存一次，会导致：

```python
# _execute_sequential 中的问题代码
result = self._execute_single_request(...)

if result:
    if on_data_ready:
        total_count += result  # result 是 int，正确
    elif save_callback:
        save_callback(interface_name, result)  # result 是 int，错误！期望 List[Dict]
        total_count += len(result)  # int 没有 len() 方法，崩溃！
```

**解决方案**：

**方案A：扩展回调参数**

在 `_execute_single_request` 中增加 `batch_save_callback` 参数，专门用于批次保存：

```python
def _execute_single_request(
    self,
    interface_config: Dict[str, Any],
    params: Dict[str, Any],
    make_request: Callable,
    on_data_ready: Optional[Callable] = None,
    batch_save_callback: Optional[Callable] = None,  # 新增：批次保存回调
    batch_save_interval: int = 50,  # 新增：保存间隔
) -> List[Dict[str, Any]]:
    """
    返回值类型保持不变：
    - 有 on_data_ready：返回整数计数
    - 无 on_data_ready：返回 List[Dict]（累积所有数据）
    
    批次保存通过 batch_save_callback 回调完成，不影响返回值类型
    """
```

**方案B：使用状态对象**

引入 `PaginationState` 对象，统一管理返回值类型：

```python
@dataclass
class PaginationResult:
    data: List[Dict[str, Any]] = field(default_factory=list)
    total_count: int = 0
    saved_count: int = 0  # 已保存的记录数
    is_streaming: bool = False  # 是否流式模式
```

**推荐方案A**，改动最小，向后兼容。

---

### 8.2 ~~跨批次重复数据问题~~（已确认不存在）

**经分析确认**：此问题不存在。

原因分析：
- **offset分页**：每个请求使用不同的 offset，数据区间完全互斥
- **time_range窗口**：每个窗口是不同的日期范围，数据完全不重叠
- **stock_loop**：每个请求是不同的 ts_code，数据完全不重叠
- **date_anchor**：每个请求是单个日期值，数据完全不重叠

以 `daily_basic` 为例，offset=0 返回第1-6000条，offset=6000 返回第6001-12000条，数据完全不重叠。

**结论**：除非 API 本身返回重复数据（那是上游问题），否则不会出现跨批次重复。

---

### 8.3 ~~并发阻塞风险~~（已确认不存在）

**经分析确认**：`--update` 模式是串行执行的，不存在并发阻塞。

代码证据（`update_manager.py`）：
```python
# 逐个接口执行更新（串行）
for idx, interface_name in enumerate(interfaces, 1):
    result = self.update_interface(interface_name, options)
```

一次只处理一个接口，重试等待只会影响当前接口，不会阻塞其他接口。

---

### 8.4 is_date_anchor 模式的错误处理

**问题描述**：

用户指出：在 `--update` 时，`reverse_date_range` 模式中，如果 `is_date_anchor` 接口没有启用 `offset` 分页，一次 API error 就直接跳过，没有任何重试。

以 `cyq_perf.yaml` 为例：
- 配置了 `mode: reverse_date_range`
- 配置了 `is_date_anchor: true`
- **没有**配置 `offset` 分页

当某个日期的请求返回错误时：
1. `_make_request` 返回空列表 `[]`
2. `_execute_single_request` 直接返回空列表
3. `_execute_sequential` 将其视为"无数据"，继续下一个日期
4. 该日期的数据永久丢失

**解决方案**：

**方案A：为 is_date_anchor 模式添加错误重试**

在 `_execute_sequential` 中，对 `is_date_anchor` 模式的空结果进行特殊处理：

```python
# 在 _execute_sequential 中
result = self._execute_single_request(...)

if not result:
    # 检查是否是日期锚定模式
    if self._is_date_anchor_interface(interface_config):
        # 检查上次请求是否是错误导致的空结果
        if last_request_was_error:
            logger.warning(f"[{interface_name}] Date anchor request failed for {params}, skipping date")
            # 记录失败日期，后续可手动重试
            self._record_failed_date_anchor(params)
    consecutive_empty += 1
```

**方案B：启用 offset 分页作为兜底**

为 `is_date_anchor` 接口默认启用 offset 分页（即使只有1页）：

```yaml
# cyq_perf.yaml
pagination:
  enabled: true
  mode: reverse_date_range
  offset:
    enabled: true  # 启用 offset 分页作为兜底
    limit: 5000    # 单次请求限制
```

这样即使返回错误，也会经过 offset 分页的重试逻辑。

**推荐方案A**，不需要修改配置，更加灵活。

---

## 九、修订后的实现方案

### 9.1 修改文件清单

| 文件 | 修改内容 | 风险等级 |
|------|---------|---------|
| `downloader.py` | 增强错误分类和重试策略 | 中 |
| `pagination_executor.py` | 添加 `batch_save_callback` 参数 | 低 |
| `settings.yaml` | 新增配置项 | 低 |

### 9.2 配置项修订

```yaml
request:
  retry:
    max_attempts: 10           # 最大重试次数
    quick_retry_count: 3       # 快速重试次数
    quick_retry_delay: 10      # 快速重试间隔（秒）
    medium_retry_count: 3      # 中等重试次数
    medium_retry_delay: 30     # 中等重试间隔（秒）
    slow_retry_delay: 60       # 慢速重试间隔（秒）
  
pagination:
  batch_save_interval: 50      # 每50页保存一次
  enable_batch_save: true      # 是否启用批次保存
```

### 9.3 实现优先级修订

| 优先级 | 功能 | 原因 |
|-------|------|------|
| P0 | API错误精准分类与重试 | 避免临时性错误导致数据丢失 |
| P0 | is_date_anchor 模式错误处理 | 修复用户报告的具体问题 |
| P1 | 批次保存机制（修复返回值冲突） | 减少内存压力 |

---

## 十、验收标准

1. API返回临时性错误时，能够按照分层策略重试
2. API返回永久性错误时，不进行重试，直接失败
3. 10次重试失败后，能够保存已下载数据
4. is_date_anchor 模式下，错误不会直接跳过，有重试和日志记录
5. 每下载50页，能够自动保存并清空内存缓冲区
6. 保存前能够进行批次内去重
7. 所有修改保持向后兼容
8. 单元测试覆盖率 > 80%
