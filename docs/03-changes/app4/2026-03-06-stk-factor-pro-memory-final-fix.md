# stk_factor_pro 内存增长问题最终修复方案

## 1. 问题根因分析

在执行大数据量接口（如 `stk_factor_pro`，拥有 200+ 字段，且下载历史跨度长达 9000+ 天）时，`app4/core/pagination_executor.py` 中的分页执行逻辑存在内存累积缺陷。

即使接口配置了 `save_callback`（逐批保存模式），执行器在 `_execute_sequential` 和 `_execute_period_range_sequential` 方法中仍会将每一批下载的数据 `extend` 到 `all_data` 列表中。这导致数据在存入磁盘后，其引用仍被 Python 列表持有，无法被垃圾回收（GC）释放，最终导致内存随下载进度线性增长，甚至触发 OOM。

## 2. 修复逻辑详述

核心策略：**分离“累积模式”与“逐次保存模式”**。当检测到有效的 `save_callback` 时，执行器应立即保存数据并仅记录计数，不再向 `all_data` 列表追加数据。

### 2.1 修改范围：app4/core/pagination_executor.py

#### (1) `_execute_single` (处理单次请求)
统一返回类型。若有保存回调，直接保存并返回记录数（int），不再返回完整数据列表。
```python
# 修改后逻辑片段
if result and save_callback and not on_data_ready:
    interface_name = interface_config.get("name", "unknown")
    save_callback(interface_name, result)
    logger.info(f"[{interface_name}] 单次请求数据已保存 ({len(result)} 条)")
    return len(result) # 返回计数
return result # 原样返回列表或计数
```

#### (2) `_execute_sequential` (核心修复点：技术因子等接口)
重构循环内的数据处理逻辑，引入 `elif save_callback` 分支。
```python
# 修改后逻辑片段
if result:
    if on_data_ready:
        total_count += result
        consecutive_empty = 0
    elif save_callback:
        # 【修复点】逐次保存模式：立即保存，累加计数，不累积内存
        save_callback(interface_name, result)
        total_count += len(result)
        logger.info(f"[{interface_name}] 已保存 {len(result)} 条记录 (第{idx+1}/{len(params_list)}批)")
        consecutive_empty = 0
    else:
        # 普通模式：累积数据到列表
        all_data.extend(result)
        consecutive_empty = 0

# 返回逻辑统一
if on_data_ready or save_callback:
    return total_count
return all_data
```

#### (3) `_execute_period_range_sequential` (财务报表类接口)
同步应用上述逻辑，确保财务类大数据下载（如 `income_vip`）同样受益。
```python
# 修改后逻辑片段
if result:
    if on_data_ready:
        total_count += result
    elif save_callback:
        # 【修复点】立即保存并计数
        save_callback(interface_name, result)
        total_count += len(result)
    else:
        all_data.extend(result)
```

### 2.2 修改范围：app4/update/update_manager.py

#### (1) `_execute_download` (消费端兼容)
由于 `executor` 现在可能返回 `int`（计数）或 `list`（数据），需通过类型检查确保返回值处理正确。
```python
# 修改后逻辑片段 (约 L481)
if saved_by_callback[0]:
    # 兼容两种返回类型：直接计数(int) 或 列表长度(len)
    return result_data if isinstance(result_data, int) else len(result_data)
```

## 3. 影响分析与测试验证

### 3.1 模式兼容性表
| 运行模式 | save_callback 状态 | 预期行为 | 内存预期 |
| :--- | :--- | :--- | :--- |
| **普通下载** | None | 走 `else` 分支，累积数据，返回 `all_data` 列表 | 随数据量增长（正常） |
| **流式处理** | 有/无 | `on_data_ready` 优先，直接计数 | **极低 (单页级)** |
| **逐次保存** | **有** | **不再累积到 all_data，返回整数计数** | **极低 (单批次级)** |
| **并发模式** | None | 强制无 `save_callback`，行为保持不变 | 随数据量增长 |

### 3.2 预期效果
- **内存占用**：对于 `stk_factor_pro` 接口，内存占用将从 GB 级降低到单批次（约 8MB）的水平，且呈周期性波动（保存后即释放）。
- **执行效率**：由于减少了巨型 Python 列表的维护开销和潜在的 Swap 交换，执行速度将更加平稳。
- **鲁棒性**：消除了大数据量下载任务中因内存不足导致的进程崩溃风险。

## 4. 实施建议
该方案逻辑自洽且具备向后兼容性，建议优先在测试环境验证 `stk_factor_pro` 的全量更新流程，重点监控内存曲线的稳定性。

---
*文档生成日期：2026-03-07*
