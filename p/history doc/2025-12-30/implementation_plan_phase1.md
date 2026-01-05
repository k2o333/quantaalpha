# aspipe_v4 频率限制修复实施方案（阶段一：应急修复）

基于之前讨论达成的共识，本方案旨在通过最小的代码变动，快速解决 Tushare API 频率限制和进程中断清理问题。

## 1. 核心目标
1.  **降低并发**：减少同时发起的请求数量。
2.  **原子重试**：在下载器底层处理临时性网络错误和频率限制。
3.  **流量平滑**：引入随机延迟（Jitter）避免并发峰值。
4.  **资源清理**：确保中断时正确关闭线程池和存储。

---

## 2. 具体修改步骤

### 步骤 A: 配置文件调整

**文件**: `app4/config/settings.yaml`

需要在配置中明确并发限制，并新增重试策略参数。

```yaml
# 并发配置
concurrency:
  max_workers: 4      # [修改] 强烈建议从 8 降至 4，免费/低积分用户 8 并发极易被封
  max_queue_size: 1000

# [新增] 请求重试与限流配置
request:
  retries: 3          # 最大重试次数
  retry_delay: 2      # 基础等待时间(秒)
  retry_backoff: 2    # 指数退避因子
  jitter_min: 0.1     # 请求前随机延迟最小值(秒)
  jitter_max: 0.5     # 请求前随机延迟最大值(秒)
```

### 步骤 B: 下载器增强 (Downloader)

**文件**: `app4/core/downloader.py`

修改 `_make_request` 方法，不要创建新方法，直接增强原方法逻辑。

**伪代码逻辑**:
```python
def _make_request(self, interface_config, params):
    # 1. 读取配置
    req_config = self.global_config.get('request', {})
    max_retries = req_config.get('retries', 3)
    
    # 2. 随机延迟 (Traffic Smoothing)
    # 在发起请求前睡一小会儿，错开多个线程的请求时刻
    time.sleep(random.uniform(
        req_config.get('jitter_min', 0.1), 
        req_config.get('jitter_max', 0.5)
    ))

    # 3. 重试循环
    for attempt in range(max_retries + 1):
        try:
            # ... 执行 requests 请求 ...
            
            # 4. 检查业务限流
            if result.get('code') != 0:
                msg = result.get('msg', '')
                # 如果是频率限制，执行退避重试
                if '频繁' in msg or 'limit' in msg.lower():
                    if attempt < max_retries:
                        sleep_time = (req_config.get('retry_delay', 2) * 
                                     (req_config.get('retry_backoff', 2) ** attempt))
                        logger.warning(f"Rate limit hit. Retrying in {sleep_time}s...")
                        time.sleep(sleep_time)
                        continue
                # 其他错误直接返回空
                return []
            
            return converted_data

        except Exception as e:
            # 5. 网络异常重试
            if attempt < max_retries:
                logger.warning(f"Network error: {e}. Retrying...")
                time.sleep(2 ** attempt)
                continue
            return []
```

### 步骤 C: 主程序清理逻辑 (Main)

**文件**: `app4/main.py`

使用 Python 标准的 `try...finally` 结构，摒弃复杂的信号处理函数。

```python
def main():
    # ... 初始化 ...
    scheduler = TaskScheduler(...)
    storage_manager = StorageManager(...)
    
    try:
        # ... 启动组件 ...
        # ... 提交任务 ...
        # ... 等待任务完成 ...
        
    except KeyboardInterrupt:
        logger.warning("\n用户手动中断执行 (Ctrl+C detected)")
    except Exception as e:
        logger.error(f"发生未捕获异常: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # [关键] 无论成功、失败还是中断，都执行清理
        logger.info("正在停止调度器...")
        if 'scheduler' in locals(): scheduler.stop()
        
        logger.info("正在关闭存储写入...")
        if 'storage_manager' in locals(): storage_manager.stop_writer()
        
        logger.info("资源清理完毕，程序退出。")
```

---

## 3. 后续规划（阶段二）

本方案实施后，系统稳定性将大幅提升。后续将根据运行情况，考虑以下架构优化：
1.  **Scheduler集成**: 将重试逻辑上移，与 `RateLimiter` 结合，实现全局精准控流。
2.  **指标监控**: 添加 Prometheus 或本地统计日志，量化 API 失败率。
3.  **断点续传**: 利用 SQLite 或 Redis 记录 Task 状态，实现进程崩溃后的任务恢复。
