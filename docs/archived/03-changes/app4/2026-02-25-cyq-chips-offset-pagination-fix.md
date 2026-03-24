---
doc_type: change
module: app4
status: archived
owner: quan
created: 2026-02-25
updated: 2026-02-25
summary: cyq_chips offset 分页在增量更新模式下失效问题
---

# cyq_chips offset 分页在增量更新模式下失效问题

## 问题描述

在增量更新模式 (`--update`) 下，`cyq_chips` 接口配置了 offset 分页（`limit: 6000`），但实际下载只返回了 6000 条记录，没有触发 offset 分页逻辑。

从日志可以看到：
- 没有任何 "Offset分页开始" / "Offset分页结束" 的日志
- 只发出了一次请求，直接返回了 6000 条
- 实际上该接口应该有多于 6000 条的数据

## 问题原因

### 代码流程分析

**标准下载流程（正常工作）**：
```
downloader.download() 
  → _execute_pagination() 
    → PaginationExecutor.execute() 
      → _execute_offset_pagination() (处理 offset 分页)
```

**增量更新流程（绕过 offset 分页）**：
```
update_manager._execute_gap_task() 
  → downloader._make_request()  ← 直接调用，绕过了分页逻辑
    → 单次请求，无 offset 分页
```

### 问题定位

在 `/home/quan/testdata/aspipe_v4/app4/update/update_manager.py:663`：

```python
def _execute_gap_task(...) -> int:
    # ...
    # 构建请求参数
    params = {k: v for k, v in task_params.items() if not k.startswith('_')}
    
    # 执行请求
    try:
        data = self.downloader._make_request(interface_config, params)  # ← 问题在这里
        # ...
```

`self.downloader._make_request()` 是底层单次请求方法，不包含任何分页逻辑。

而标准下载流程调用的是 `downloader._execute_pagination()`，它会：
1. 创建 PaginationContext
2. 调用 PaginationExecutor.execute()
3. 执行 offset 分页逻辑

## 解决方案

### 简洁方案（推荐）

**只需修改一行代码**：

```python
# 修改前 (update_manager.py:663)
data = self.downloader._make_request(interface_config, params)

# 修改后
data = self.downloader._execute_pagination(interface_config, params)
```

### 方案评估

| 评估项 | 结果 |
|--------|------|
| 问题定位 | ✅ 准确 |
| 方案可行性 | ✅ 可行 |
| 方法存在性 | ✅ `_execute_pagination` 在 `downloader.py:240` 已存在 |
| 参数兼容 | ✅ 两方法签名一致 |
| 返回值处理 | ✅ 都是 `List[Dict[str, Any]]`，兼容现有逻辑 |
| 异常处理 | ✅ 已有 try-except 包裹 |

### 原理说明

`_execute_pagination` 内部逻辑（`downloader.py:252-253`）：
```python
if not pagination_config.get("enabled", False):
    return self._make_request(interface_config, params)
```

即：如果 `pagination.enabled` 为 false，会自动降级为单次请求，不会影响非分页接口。

### 替代方案

如果上述方案在 gap task 场景不适用（参数结构不匹配），可考虑：
1. 在 `UpdateManager` 中实例化 `PaginationExecutor` 并直接调用
2. 复用 `downloader._execute_pagination` 的逻辑提取公共部分

## 影响范围

- **受影响的接口**: 所有在增量更新模式下使用 offset 分页的接口（如 `cyq_chips`、`cyq_perf` 等）
- **修复后的效果**: 增量更新时将正确触发 offset 分页逻辑，获取完整数据

## 测试验证

修复后运行：
```bash
python /home/quan/testdata/aspipe_v4/app4/main.py --update --interface cyq_chips --ts_code 000001.SZ
```

预期日志应包含：
- "[cyq_chips] Offset分页开始"
- 多页请求的日志
- "[cyq_chips] Offset分页结束"
