# API重试与批次保存实现方案（改进版）

## 背景

当前在使用 `--update` 且因 API 参数错误导致失败时，系统会立即丢弃下载、中断当前任务，并将进度视为 SUCCESS。为了增加鲁棒性并修复数据完整性问题，需要实装细粒度的 API 重试与多阶段保存策略。

---

## 核心变更概述

| 变更点 | 现有行为 | 新行为 |
|--------|----------|--------|
| API CLIENT_ERROR | 返回 `[]`，记录 SUCCESS | 立即抛出异常，快速失败 |
| API SERVER_ERROR/RATE_LIMIT | 最多3次重试 | 最多10次重试，分段延时 |
| offset 分页数据累积 | 全部累积到内存 | 每批次阈值保存并清空 |

---

## 一、重试机制改进

### 1.1 错误类型分类

利用现有 `APIErrorType` 枚举和 `_classify_api_error()` 方法区分错误类型：

```python
class APIErrorType(Enum):
    SUCCESS = "success"
    RATE_LIMIT = "rate_limit"
    SERVER_ERROR = "server_error"
    CLIENT_ERROR = "client_error"    # 参数错误、权限不足等
    NETWORK_ERROR = "network_error"
```

### 1.2 分策略重试逻辑

| 错误类型 | 处理策略 | 原因 |
|----------|----------|------|
| CLIENT_ERROR | 立即抛出 RuntimeError | 参数错误无法通过重试修复 |
| RATE_LIMIT | 重试10次，分段延时 | 频率限制是临时的 |
| SERVER_ERROR | 重试10次，分段延时 | 服务器故障可能恢复 |
| NETWORK_ERROR | 重试10次，分段延时 | 网络波动是临时的 |

### 1.3 重试延时策略

- **快速重试阶段**（前3次）：间隔 10 秒
- **慢速重试阶段**（后7次）：间隔 60 秒

总最大等待时间：3×10s + 7×60s = 7分30秒

### 1.4 配置外部化

在 `settings.yaml` 中新增配置项：

```yaml
request:
  api_retry:
    max_attempts: 10
    quick_retry_count: 3      # 前 N 次为快速重试
    quick_retry_delay: 10     # 快速重试间隔(秒)
    slow_retry_delay: 60      # 慢速重试间隔(秒)
    
  batch_save:
    enabled: true
    record_threshold: 50000   # 每 N 条记录保存一次
```

---

## 二、代码修改详情

### 2.1 downloader.py - `_make_request` 方法

**修改位置**：`app4/core/downloader.py` 的 `_make_request` 方法

**修改内容**：

```python
def _make_request(
    self, interface_config: Dict[str, Any], params: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """发起实际的 API 请求 - 改进版"""
    api_name = interface_config["api_name"]
    
    # 读取重试配置（支持新配置格式，向后兼容）
    req_config = self.global_config.get("request", {})
    retry_config = req_config.get("api_retry", {})
    
    max_retries = retry_config.get("max_attempts", 10)
    quick_retry_count = retry_config.get("quick_retry_count", 3)
    quick_retry_delay = retry_config.get("quick_retry_delay", 10)
    slow_retry_delay = retry_config.get("slow_retry_delay", 60)
    
    # ... 请求执行代码 ...
    
    # 检查 API 返回是否成功
    if result.get("code") != 0:
        msg = result.get("msg", "")
        error_type = self._classify_api_error(result)
        
        # CLIENT_ERROR: 快速失败，不重试
        if error_type == APIErrorType.CLIENT_ERROR:
            logger.error(f"API参数错误 [{api_name}]: {msg}")
            raise RuntimeError(f"API参数错误，无法通过重试修复: {msg}")
        
        # RATE_LIMIT / SERVER_ERROR / NETWORK_ERROR: 执行重试
        if error_type in (APIErrorType.RATE_LIMIT, APIErrorType.SERVER_ERROR, APIErrorType.NETWORK_ERROR):
            if attempt < max_retries:
                # 分段延时策略
                if attempt < quick_retry_count:
                    delay = quick_retry_delay
                else:
                    delay = slow_retry_delay
                
                logger.warning(
                    f"[{api_name}] {error_type.value} - 重试 {attempt+1}/{max_retries}，"
                    f"等待 {delay}s... (错误: {msg})"
                )
                time.sleep(delay)
                continue
            
            # 重试耗尽，抛出异常
            raise RuntimeError(
                f"[{api_name}] 重试 {max_retries} 次后仍然失败: {msg}"
            )
        
        # 未知错误类型，记录并返回空
        logger.error(f"API unknown error for {api_name}: {msg}")
        return []
```

### 2.2 pagination_executor.py - `_execute_single_request` 方法

**修改位置**：`app4/core/pagination_executor.py`

**修改内容**：

1. 增加 `save_callback` 参数
2. 增加批次保存逻辑
3. 增加异常处理与收尾保存

```python
def _execute_single_request(
    self,
    interface_config: Dict[str, Any],
    params: Dict[str, Any],
    make_request: Callable,
    on_data_ready: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
    save_callback: Optional[Callable[[str, List[Dict[str, Any]]], None]] = None,  # 新增
) -> List[Dict[str, Any]]:
    """
    执行单个请求，处理offset分页

    Args:
        interface_config: 接口配置
        params: 请求参数
        make_request: 请求执行回调函数
        on_data_ready: 流式处理回调
        save_callback: 批次保存回调 (新增)

    Returns:
        请求结果或记录数
    """
    offset_config = params.get("_offset_pagination", {})

    if not offset_config.get("enabled"):
        clean_params = {k: v for k, v in params.items() if not k.startswith("_")}
        try:
            data = make_request(interface_config, clean_params)
            if on_data_ready and data:
                on_data_ready(data)
                return len(data)
            return data
        except RuntimeError as e:
            # API错误向上传播
            logger.error(f"请求失败: {e}")
            raise

    # 执行offset分页
    all_data = []
    total_count = 0
    limit = offset_config["limit"]
    offset = 0
    base_params = {k: v for k, v in params.items() if not k.startswith("_")}
    interface_name = interface_config.get("name", "unknown")
    
    # 批次保存阈值（从配置读取或使用默认值）
    batch_threshold = 50000  # 可配置化

    logger.info(f"[{interface_name}] Offset分页开始 - 配置限额: limit={limit}")
    page_num = 0

    try:
        while True:
            request_params = base_params.copy()
            request_params["limit"] = limit
            request_params["offset"] = offset

            data = make_request(interface_config, request_params)
            
            if not data:
                logger.info(
                    f"[{interface_name}] 第{page_num + 1}页请求无数据 - offset={offset}"
                )
                break

            data_count = len(data)
            
            if on_data_ready:
                # 流式处理：每页数据立即回调
                on_data_ready(data)
                total_count += data_count
            else:
                # 累积数据
                all_data.extend(data)
                
                # 批次保存：达到阈值时保存并清空
                if save_callback and len(all_data) >= batch_threshold:
                    save_callback(interface_name, all_data)
                    logger.info(
                        f"[{interface_name}] 批次保存 {len(all_data)} 条记录 "
                        f"(累计 {total_count + len(all_data)} 条)"
                    )
                    all_data = []
            
            page_num += 1
            total_count += data_count if on_data_ready else 0

            logger.info(
                f"[{interface_name}] 第{page_num}页完成 - offset={offset}, 返回={data_count}条"
            )

            if data_count < limit:
                logger.info(
                    f"[{interface_name}] 分页完成 - 最后1页返回{data_count}条 < 限额{limit}"
                )
                break

            offset += limit
            if offset > limit * 10000:  # 安全限制
                logger.warning(f"[{interface_name}] Offset分页超过安全限制，停止请求")
                break

    except RuntimeError as e:
        # 异常时先保存已累积的数据，再向上抛出
        if save_callback and all_data:
            save_callback(interface_name, all_data)
            logger.warning(
                f"[{interface_name}] 异常中断，已保存 {len(all_data)} 条残留数据"
            )
        raise

    # 循环结束后保存剩余数据
    if save_callback and all_data:
        save_callback(interface_name, all_data)
        logger.info(f"[{interface_name}] 最终批次保存 {len(all_data)} 条记录")

    if on_data_ready:
        logger.info(
            f"[{interface_name}] Offset分页结束 - 总页数={page_num}, 总记录数={total_count}"
        )
        return total_count
    else:
        logger.info(
            f"[{interface_name}] Offset分页结束 - 总页数={page_num}, 总记录数={len(all_data)}"
        )
        return all_data
```

### 2.3 调用链参数传递

确保 `save_callback` 从顶层正确传递到底层：

```
execute() 
  -> _execute_sequential() / _execute_period_range_sequential()
    -> _execute_single_request(save_callback=...)
```

---

## 三、验证计划

### 3.1 自动化测试

无需新增测试脚本，使用现有测试框架。

### 3.2 手动验证

#### 验证1：CLIENT_ERROR 快速失败

```bash
# 构造参数错误场景
python app4/main.py --update --interface daily_basic --ts_code INVALID_CODE
```

**预期结果**：
- 终端立即输出错误信息
- 无重试等待
- 进程退出并显示错误状态

#### 验证2：RATE_LIMIT 重试机制

```bash
# 正常请求，可能触发频率限制
python app4/main.py --update --interface daily_basic --start_date 20240101
```

**预期结果**：
- 遇到频率限制时，终端显示 `重试 1/10，等待 10s...`
- 成功后继续执行

#### 验证3：批次保存机制

```bash
# 下载大数据量接口
python app4/main.py --update --interface stk_factor_pro --start_date 20200101
```

**预期结果**：
- 每 50000 条记录输出一次 `批次保存 XXX 条记录`
- 内存使用稳定，不随数据量线性增长

#### 验证4：异常中断数据保留

```bash
# 运行中手动中断 (Ctrl+C)
python app4/main.py --update --interface stk_factor_pro
# 中断后检查数据目录
ls -la data/stk_factor_pro/
```

**预期结果**：
- 已保存的批次数据保留在 parquet 文件中

---

## 四、风险评估

| 风险点 | 影响等级 | 缓解措施 |
|--------|----------|----------|
| CLIENT_ERROR 导致更新中断 | 中 | 区分错误类型，仅 CLIENT_ERROR 快速失败 |
| 配置项缺失导致行为变化 | 低 | 提供默认值，向后兼容 |
| save_callback 未正确传递 | 中 | 完整的参数传递链检查 |

---

## 五、实施步骤

1. **Phase 1**：修改 `downloader.py` 重试逻辑
2. **Phase 2**：修改 `pagination_executor.py` 批次保存逻辑
3. **Phase 3**：更新 `settings.yaml` 配置项
4. **Phase 4**：执行验证计划

---

## 六、与原方案差异

| 项目 | 原方案 | 改进方案 |
|------|--------|----------|
| 重试条件 | 所有 code != 0 都重试 | 仅 SERVER_ERROR/RATE_LIMIT 重试 |
| CLIENT_ERROR 处理 | 重试10次后失败 | 立即失败，无重试 |
| 批次保存触发 | page_num % 50 == 0 | len(all_data) >= threshold |
| 配置方式 | 硬编码 | 配置文件驱动 |
