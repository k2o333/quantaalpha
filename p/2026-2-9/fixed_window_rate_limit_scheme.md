# 固定窗口限流方案

## 需求描述

将当前的令牌桶算法改为固定窗口限流：
- 从每分钟第1秒开始统计调用次数
- 达到上限（`rate_limit`，如250次）后暂停所有调用
- 终端输出暂停/恢复相关信息
- 等到下一分钟窗口开始时，重置计数器并恢复调用

## 当前实现（令牌桶算法）

**文件**: `app4/core/scheduler.py`

```python
class RateLimiter:
    """速率限制器 - 使用令牌桶算法"""

    def __init__(self, rate_limit: int, time_window: int = 60):
        self.rate_limit = rate_limit
        self.time_window = time_window
        self.tokens = rate_limit
        self.last_refill = time.time()
        self.lock = threading.Lock()

    def wait_for_tokens(self, tokens: int = 1):
        while not self.acquire(tokens):
            sleep_time = self.time_window / self.rate_limit
            random_jitter = random.uniform(0, sleep_time * 0.1)
            time.sleep(sleep_time + random_jitter)
```

**特点**:
- 平滑限流，令牌随时间补充
- 达到上限后等待一小段时间再重试
- 无固定窗口概念

## 新方案（固定窗口）

### 实现代码

**文件**: `app4/core/scheduler.py`

将 `RateLimiter` 类替换为 `FixedWindowRateLimiter`：

```python
class FixedWindowRateLimiter:
    """固定窗口速率限制器 - 每分钟固定窗口限流"""

    def __init__(self, rate_limit: int, time_window: int = 60):
        """
        初始化固定窗口速率限制器

        Args:
            rate_limit: 时间窗口内的最大请求数
            time_window: 时间窗口（秒），默认60秒
        """
        self.rate_limit = rate_limit
        self.time_window = time_window
        self.request_count = 0
        self.window_start = time.time()
        self.lock = threading.Lock()
        self.paused = False
        self.logger = logging.getLogger(__name__)

    def _is_new_window(self) -> bool:
        """检查是否进入新的时间窗口"""
        now = time.time()
        return (now - self.window_start) >= self.time_window

    def _reset_window(self):
        """重置时间窗口"""
        self.window_start = time.time()
        self.request_count = 0
        self.paused = False

    def wait_for_tokens(self, tokens: int = 1):
        """
        等待直到有足够的额度

        Args:
            tokens: 需要的请求数
        """
        import sys

        while True:
            with self.lock:
                # 检查是否进入新窗口
                if self._is_new_window():
                    if self.paused:
                        self.logger.info(f"✓ 新的时间窗口开始，恢复调用（重置计数器）")
                    self._reset_window()

                # 检查是否已达到限制
                if self.request_count + tokens > self.rate_limit:
                    if not self.paused:
                        remaining_time = self.time_window - (time.time() - self.window_start)
                        self.logger.warning(
                            f"⚠️  本分钟调用次数已达上限 ({self.rate_limit}次)，"
                            f"暂停所有调用，等待 {remaining_time:.1f} 秒后恢复..."
                        )
                        self.paused = True
                    # 退出锁，避免阻塞其他线程的检查
                    pass
                else:
                    # 有额度，增加计数并返回
                    self.request_count += tokens
                    return

            # 如果没有额度，等待一段时间后重试
            time.sleep(1)
```

### 关键特性

1. **固定窗口**: 以60秒为固定单位，从窗口开始时刻统计
2. **暂停机制**: 达到上限后暂停所有调用
3. **自动恢复**: 新窗口开始时重置计数器
4. **终端输出**: 暂停和恢复时输出提示信息
5. **线程安全**: 使用锁保护共享状态

### 终端输出示例

```
2026-02-11 12:00:59 - core.scheduler - WARNING - ⚠️  本分钟调用次数已达上限 (250次)，暂停所有调用，等待 2.3 秒后恢复...
2026-02-11 12:01:02 - core.scheduler - INFO - ✓ 新的时间窗口开始，恢复调用（重置计数器）
```

## 实施步骤

### 步骤1: 修改代码

在 `app4/core/scheduler.py` 中：

1. 找到 `RateLimiter` 类定义（约第87-140行）
2. 将整个类替换为新的固定窗口实现
3. 保持类名为 `RateLimiter`

### 步骤2: 验证测试

```bash
# 测试限流效果
python app4/main.py --interface daily_basic

# 观察日志
tail -f log/app4.log | grep "本分钟调用次数已达上限\|新的时间窗口开始"
```

## 配置兼容性

### 配置文件

**文件**: `app4/config/settings.yaml`

```yaml
request:
  rate_limit: 250  # 每分钟最大调用次数
  max_retries: 3
  retry_delay: 1.0
  timeout: 30
```

### 无需修改

- `downloader.py:526` 的调用代码无需修改
- `main.py:268` 的初始化代码无需修改
- 其他使用 `RateLimiter` 的地方无需修改

## 行为对比

### 令牌桶算法（旧）

- 平滑限流
- 令牌随时间补充
- 达到上限后等待短时间重试
- 无固定窗口概念

### 固定窗口（新）

- 突发限流
- 固定时间窗口（60秒）
- 达到上限后暂停到下一分钟
- 每分钟重置计数器

### 示例对比

假设 `rate_limit = 250`, 前半分钟已调用250次

| 时间点 | 令牌桶 | 固定窗口 |
|--------|--------|---------|
| 0-30秒 | 可正常调用（令牌充足） | 可正常调用 |
| 30秒时 | 令牌耗尽，等待补充 | 达到上限，**暂停** |
| 30-60秒 | 等待令牌恢复，间歇调用 | **完全暂停** |
| 60秒时 | 正常调用 | **恢复**，重置计数器 |
| 60-90秒 | 正常调用 | 可正常调用 |

## 优缺点分析

### 固定窗口优点

1. **简单直观**: 每分钟固定额度，易于理解
2. **清晰提示**: 暂停/恢复时输出明确信息
3. **避免抖动**: 达到上限后彻底暂停，避免重复失败
4. **便于监控**: 每分钟独立统计，便于配额管理

### 固定窗口缺点

1. **边界效应**: 窗口边缘可能有突发请求
2. **资源浪费**: 达到上限后剩余时间完全闲置
3. **不够平滑**: 突发式调用，可能导致服务端压力

### 适用场景

- API 有严格每分钟配额限制
- 需要清晰了解调用暂停状态
- 希望避免因频繁重试导致的账号风险

## 相关文件

1. `app4/core/scheduler.py` - RateLimiter 实现（需修改）
2. `app4/core/downloader.py:80` - 初始化 RateLimiter
3. `app4/core/downloader.py:526` - 调用 wait_for_tokens
4. `app4/main.py:268` - 初始化 global_rate_limiter
5. `app4/config/settings.yaml:19` - rate_limit 配置

## 总结

**核心改动**: 将令牌桶算法替换为固定窗口限流

**关键特性**:
- 每分钟固定窗口
- 达到上限暂停
- 新窗口恢复
- 终端输出提示

**实施难度**: 低（单文件修改）

**向后兼容**: 完全兼容（接口不变）

**推荐场景**: API 有严格每分钟配额限制，需要清晰的状态提示

---

**创建日期**: 2026-02-11
**相关配置**: `app4/config/settings.yaml` - `request.rate_limit: 250`
**影响范围**: 所有使用 RateLimiter 的接口
**实施状态**: 待实施