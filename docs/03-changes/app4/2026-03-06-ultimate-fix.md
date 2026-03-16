# stk_factor_pro 数据不保存及 Worker 退出的终极修复方案

> 修复日期：2026-03-06

## 现象描述

运行 `--update --interface stk_factor_pro` 等涉及分页和大量数据的接口时，遇到两个核心异常：
1. **数据不存盘** / **非原子化存储**：要么全量下载完才一起存盘（导致中间如果断开所有数据丢失），要么如果是单批请求根本没触发存盘回调。
2. **Worker 退出的死锁**：数据跑完后，Python 进程无法退出（卡死在等待 `process_queue` 清空的代码上）。有时会出现部分数据还在内存中未来得及刷盘导致**数据丢失**。

---

## 根因与修复策略

本次修复结合了三个不同视角的分析，对两个独立的文件进行修改。

### 核心一：存储数据丢失及非原子化存盘 (`pagination_executor.py`)

**根因：**
1. **错误的分支判断导致并发乱入**：`stk_factor_pro` 等接口仍然在使用旧版配置字典，在 `_should_use_concurrency` 检查 `time_range.get('reverse')` 时因字典里没有这个键，错误地将其判断为“支持无序并发”。但在 `_execute_concurrent` 中却没有支持并调用 `save_callback`，**导致数据几十天全量积压在内存，最后才统一保存**。
2. **单批请求未接手柄**：在 `params_list <= 1` 时走 `_execute_single`，或是走串行的 `_execute_sequential` 时，由于这两个方法签名里没有接纳并调用 `save_callback`，使得逐批保存的功能失效。

**修复方案：**
1. **强行保证原子化**：在 `execute()` 方法的入口，**只要上层传了 `save_callback`，说明系统要求原子化（下一批存一批），必须强制降级走串行模式（`_execute_sequential`）**。
2. **串行与单批的存盘补齐**：把 `save_callback` 传递给 `_execute_single` 和 `_execute_sequential`。在这两个方法里，只要获取完数据，就立刻触发 `save_callback` 落盘，并在日志中打印进度，不再留存在内存。不修改最底层的 `_execute_single_request`（防止多层调用导致同一批数据存两遍的隐患）。

---

### 核心二：Storage Process Worker 退出死锁与数据漏刷 (`storage.py`)

### 核心二：Storage Process Worker 退出死锁与数据漏刷 (`storage.py`)

**根因：**
1. **主线程无限死等**：`stop_writer` 中 `while not self.process_queue.empty()` 是最大的死锁元凶。如果在极端情况下 `process_thread` 工作线程因为数据异常而崩溃退出，主线程就会永远卡在这里。或者因为多线程调度，导致队列看似空了实则还有数据，导致状态判断异常。
2. **排空满载丢失**：`flush_remaining_data` 在强行结束时使用 `block=False` 将内存中所有接口残留推入队列。如果队列已满，直接抛错，导致这部分剩余数据永久丢失。
3. **哨兵截断残留**：`_process_worker` 在收到停止标志位 `None` (哨兵) 后马上退出，它不去检查在收到标志位前后由于多线程并发争抢而进入队列的残留数据，导致队列最后几个合法数据被漏刷。

**修复方案（方案B：哨兵毒丸模式）：**
这是一套更简洁、责任更明确的关闭机制：
1. **主线程只发命令，不等待清空**：`stop_writer` 彻底移除死等的 `while not empty()`。只负责发送哨兵 `None` 给工作线程，并设置合理的 `join(timeout=120)` 作为最后的安全锁。
2. **完美接力，子线程自排空**：在 `_process_worker` 中引入 `pending_stop` 标志。在收到 `None` 哨兵后，不仅不立刻退出，反而启动一个内部循环，将 `process_queue` 中当前所有剩余的合法数据榨干消化，责任完全下放给工作线程。
3. **阻塞型排空缓存**：`flush_remaining_data` 改用 `block=True` 并赋予超时，确保极大概率把剩余数据送到下一级队列。由于主线程不再阻塞死等，后台工作线程依然会快速消费掉这些积压数据。
4. **拒绝僵尸写入**：在 `save_data` 第一句加上拦截，若 `self.running == False`（系统正停机时还有并发线程想写数据），强制切频转为同步直接写盘（降级为 `_write_interface_data`），不进入复杂队列。


---

## 实施计划

我将为您修改上述代码：

### 1. 修改 `app4/core/pagination_executor.py`

* 在 `execute` 方法：修改 `if save_callback or not self._should_use_concurrency(interface_config):` 强制走串行。
* 给 `_execute_sequential` 和 `_execute_single` 添加 `save_callback` 参数并在拿到结果后调用该回调。

### 2. 修改 `app4/core/storage.py`

### 2. 修改 `app4/core/storage.py` (已完成代码分析并采纳方案B)

* 在 `save_data` 添加 `not self.running` 并发脏写拦截。
* **(方案B) 主线程减负**：在 `stop_writer` 中移除 `while not empty` 死等，只下发哨兵。
* **(方案B) 子线程负责**：重写 `_process_worker` 支持 `pending_stop` 并负责自动排空内部队列剩余的所有数据。
* 在 `flush_remaining_data` 中加入 `block=True, timeout=30` 保驾护航，配合方案B让工作线程去动态消费。

请确认是否实施代码调整？
