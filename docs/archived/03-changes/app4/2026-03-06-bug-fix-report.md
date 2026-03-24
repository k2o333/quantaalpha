---
doc_type: change
module: app4
status: archived
owner: quan
created: 2026-03-06
updated: 2026-03-06
summary: Bug Fix Report - stk_factor_pro 数据未保存问题
---

# Bug Fix Report: stk_factor_pro 数据未保存问题

## 问题现象

运行命令：
```bash
/root/miniforge3/envs/get/bin/python app4/main.py --update --interface stk_factor_pro --start_date 19900101
```

日志显示：
- 第1页成功下载 2945 条记录
- 第2页及后续页返回 0 条记录
- **没有 batch 内去重日志**
- **数据没有保存到磁盘**

关键日志：
```
2026-03-06 19:38:32,816 - core.downloader - INFO - Downloaded 2945 records for stk_factor_pro
2026-03-06 19:38:32,820 - core.pagination_executor - INFO - [stk_factor_pro] 第1页完成 - offset=0, 请求limit=6000, 实际返回=2945条
2026-03-06 19:38:35,269 - core.downloader - INFO - Downloaded 0 records for stk_factor_pro
```

## 问题代码分析

### 问题文件
`/home/quan/testdata/aspipe_v4/app4/core/pagination_executor.py`

### 问题1：`_execute_single_request` 方法未支持 `save_callback`

**代码位置**：第 379-481 行

**问题描述**：
该方法负责处理 offset 分页逻辑。当接口配置启用 offset 分页时（如 `stk_factor_pro` 使用 `reverse_date_range` 模式），数据会被下载并累积到 `all_data` 列表中，但**从未调用 `save_callback` 来保存数据**。

**原代码**（问题部分）：
```python
def _execute_single_request(
    self,
    interface_config: Dict[str, Any],
    params: Dict[str, Any],
    make_request: Callable,
    on_data_ready: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
) -> List[Dict[str, Any]]:
    # ... offset 分页逻辑 ...
    all_data = []
    while True:
        data = make_request(interface_config, request_params)
        if not data:
            break
        all_data.extend(data)  # 数据累积但不保存！
        # ...
    return all_data  # 只返回，不保存
```

### 问题2：`_execute_single` 方法未支持 `save_callback`

**代码位置**：第 139-169 行

**问题描述**：
该方法处理 `params_list <= 1` 的情况（即单批请求）。它调用 `_execute_single_request` 获取数据，但**没有调用 `save_callback` 来保存数据**。

**原代码**（问题部分）：
```python
def _execute_single(
    self,
    interface_config: Dict[str, Any],
    params: Dict[str, Any],
    make_request: Callable,
    on_data_ready: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
) -> List[Dict[str, Any]]:
    return self._execute_single_request(interface_config, params, make_request, on_data_ready)
    # 没有 save_callback 调用！
```

### 问题3：`execute` 方法调用 `_execute_single` 时未传递 `save_callback`

**代码位置**：第 112-114 行

**问题描述**：
当 `params_list <= 1` 时，`execute` 方法调用 `_execute_single`，但没有传递 `save_callback` 参数。

**原代码**（问题部分）：
```python
if len(params_list) <= 1:
    if params_list:
        return self._execute_single(
            interface_config, params_list[0], make_request, on_data_ready  # 缺少 save_callback
        )
```

## 修复方案

### 修复1：为 `_execute_single_request` 添加 `save_callback` 支持

**修改内容**：
1. 添加 `save_callback` 参数
2. 在 offset 分页完成后，如果有数据则调用 `save_callback`

**修复后代码**：
```python
def _execute_single_request(
    self,
    interface_config: Dict[str, Any],
    params: Dict[str, Any],
    make_request: Callable,
    on_data_ready: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
    save_callback: Optional[Callable[[str, List[Dict[str, Any]]], None]] = None,  # 新增
) -> List[Dict[str, Any]]:
    # ... 分页逻辑 ...
    
    # 新增：如果有save_callback且有数据，调用save_callback
    if save_callback:
        if on_data_ready:
            # 流式模式下不调用save_callback（因为数据已通过on_data_ready处理）
            pass
        elif all_data and len(all_data) > 0:
            save_callback(interface_name, all_data)
            logger.info(
                f"[{interface_name}] Offset分页完成后已保存 {len(all_data)} 条记录"
            )
    
    return all_data
```

### 修复2：为 `_execute_single` 添加 `save_callback` 支持

**修改内容**：
1. 添加 `save_callback` 参数
2. 在获取结果后调用 `save_callback` 保存数据

**修复后代码**：
```python
def _execute_single(
    self,
    interface_config: Dict[str, Any],
    params: Dict[str, Any],
    make_request: Callable,
    on_data_ready: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
    save_callback: Optional[Callable[[str, List[Dict[str, Any]]], None]] = None,  # 新增
) -> List[Dict[str, Any]]:
    result = self._execute_single_request(interface_config, params, make_request, on_data_ready, save_callback)
    
    # 新增：调用 save_callback
    if save_callback and result and isinstance(result, list) and len(result) > 0:
        interface_name = interface_config.get("name", "unknown")
        save_callback(interface_name, result)
        logger.info(
            f"[{interface_name}] 已保存 {len(result)} 条记录 (单批)"
        )
    
    return result
```

### 修复3：更新 `execute` 方法调用 `_execute_single` 时传递 `save_callback`

**修复后代码**：
```python
if len(params_list) <= 1:
    if params_list:
        return self._execute_single(
            interface_config, params_list[0], make_request, on_data_ready, save_callback  # 新增 save_callback
        )
```

### 修复4：更新 `_execute_sequential` 和 `_execute_period_range_sequential` 中的调用

确保这些方法调用 `_execute_single_request` 时也传递 `save_callback`：

```python
# _execute_sequential 中
result = self._execute_single_request(interface_config, params, make_request, on_data_ready, save_callback)

# _execute_period_range_sequential 中
result = self._execute_single_request(interface_config, params, make_request, on_data_ready, save_callback)
```

## 为什么这样修复

### 1. 数据流完整性
`save_callback` 是数据保存的关键机制。它由 `update_manager.py` 提供，负责：
- 调用 `storage_manager.save_data()` 保存数据
- 触发 `processor.py` 中的 batch 去重逻辑
- 记录保存状态

如果 `_execute_single_request` 和 `_execute_single` 不调用 `save_callback`，数据就会"丢失在内存中"，无法持久化。

### 2. 职责分离
- `_execute_single_request`: 负责执行请求和分页逻辑，现在增加保存职责
- `_execute_single`: 负责单批执行协调，现在增加保存职责
- `execute`: 负责整体执行策略，确保 `save_callback` 正确传递

### 3. 向后兼容
通过将 `save_callback` 设为可选参数（`Optional`），确保：
- 旧代码不传递 `save_callback` 时不会报错
- 新代码传递 `save_callback` 时能正确保存数据

### 4. 避免重复保存
在 `_execute_single_request` 中：
- 如果 `on_data_ready` 已处理数据（流式模式），则不调用 `save_callback`
- 只有在非流式模式下才调用 `save_callback`

## 验证方法

重新运行命令：
```bash
/root/miniforge3/envs/get/bin/python app4/main.py --update --interface stk_factor_pro --start_date 19900101
```

预期日志输出：
```
[stk_factor_pro] Offset分页完成后已保存 2945 条记录
Batch deduplication for stk_factor_pro: removed X duplicates within batch
```

并检查数据是否已写入磁盘。

---

**修复日期**: 2026-03-06  
**修复文件**: `/home/quan/testdata/aspipe_v4/app4/core/pagination_executor.py`
