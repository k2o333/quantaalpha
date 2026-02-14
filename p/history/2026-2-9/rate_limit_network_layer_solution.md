# Rate Limit 网络请求层级限流方案

## 核心思想

**限流发生在网络请求层级，删除所有中间层的冗余限流代码**

### 当前问题

1. **限流位置不当**：限流发生在 `downloader._make_request()`，处于网络请求层级，但并发任务已经创建
2. **冗余代码**：`main.py:run_concurrent_stock_download` 中注释说包含限流逻辑，但实际没有实现
3. **并发稀释**：多个线程同时调用 `wait_for_tokens`，限流效果被稀释

### 解决方案

**单一职责原则**：限流只发生在网络请求层级，删除所有其他位置的限流相关代码

---

## 实施步骤

### 步骤 1：强化 Downloader 中的限流（核心）

**文件**: `app4/core/downloader.py`

在 `_make_request` 方法中强化限流，添加日志输出：

```python
def _make_request(self, interface_config: Dict[str, Any], params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """发起实际的 API 请求 - 强化限流版"""
    api_name = interface_config['api_name']

    # 读取重试配置
    req_config = self.global_config.get('request', {})
    max_retries = req_config.get('max_retries', 3)

    # ===== 核心限流逻辑 =====
    # 在发起网络请求前进行限流
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🔄 等待令牌: {api_name}")
    wait_start = time.time()
    self.global_rate_limiter.wait_for_tokens(1)
    wait_end = time.time()
    wait_duration = wait_end - wait_start

    if wait_duration > 0.1:  # 如果等待时间超过100ms，说明被限流了
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ⏸️  限流等待: {wait_duration:.2f}s")
    else:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✅ 立即执行: {api_name}")

    # 随机延迟，错开多个线程的请求时刻
    time.sleep(random.uniform(
        req_config.get('jitter_min', 0.1),
        req_config.get('jitter_max', 0.5)
    ))
    # ======================

    start_time = time.time()
    retry_count = 0

    # 重试循环
    for attempt in range(max_retries + 1):
        try:
            # ... 原有请求逻辑 ...
            request_config = interface_config.get('request', {})
            method = request_config.get('method', 'POST')
            timeout_val = request_config.get('timeout', 30)
            timeout = (10, timeout_val)

            # 获取 API URL...
            api_url = self._get_api_url()

            # 构建请求参数...
            req_params = self._build_request_params(interface_config, params)

            # 发起请求
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 📡 发起请求: {api_name}")

            if method.upper() == 'POST':
                response = self.session.post(api_url, json=req_params, timeout=timeout)
            else:
                response = self.session.get(api_url, json=req_params, timeout=timeout)

            response.raise_for_status()
            result = response.json()

            # 检查 API 返回是否成功
            if result.get('code') != 0:
                msg = result.get('msg', '')
                # 如果是频率限制，执行退避重试
                if self._is_rate_limit_error(msg):
                    if attempt < max_retries:
                        retry_delay = self._calculate_retry_delay(req_config, attempt)
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ⚠️  API限流: {api_name}, {retry_delay:.2f}s后重试")
                        time.sleep(retry_delay)
                        retry_count = attempt + 1
                        continue

                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ❌ API错误: {api_name}, {msg}")
                self._record_failure_metrics(interface_config, start_time, params, retry_count)
                return []

            # 处理成功响应...
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✅ 请求成功: {api_name}, {len(converted_data)}条记录")

            # 记录指标...
            return converted_data

        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ❌ 请求异常: {api_name}, {str(e)}")
            if attempt < max_retries:
                retry_delay = self._calculate_retry_delay(req_config, attempt)
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🔄 重试: {api_name}, {retry_delay:.2f}s后")
                time.sleep(retry_delay)
                retry_count = attempt + 1
                continue

            self._record_failure_metrics(interface_config, start_time, params, retry_count)
            return []

def _is_rate_limit_error(self, msg: str) -> bool:
    """检查是否是限流错误"""
    rate_limit_keywords = ['limit', 'frequent', 'frequently', 'time', 'request', 'rate', '频繁', '限制']
    msg_lower = msg.lower()
    return any(keyword in msg_lower for keyword in rate_limit_keywords)
```

---

### 步骤 2：删除 main.py 中的冗余限流代码

**文件**: `app4/main.py`

**删除内容** (第 151-157 行):

```python
# ❌ 删除这部分冗余代码

def run_concurrent_stock_download(downloader, scheduler, interface_name, interface_config, base_params, stock_list, storage_manager, processor, logger):
    """运行并发股票下载 - 统一使用buffer机制"""
    logger.info(f"Starting concurrent download for {interface_name} with {len(stock_list)} stocks")

    # ❌ 删除：创建包装函数，包含限流逻辑
    # ❌ 删除：def download_single_stock_with_rate_limit(interface_config, stock, params):
    # ❌ 删除：    return downloader.download_single_stock(interface_config, stock, params)

    # 统一使用buffer机制，不再在主线程批量处理
    total_records = 0
    # ... 后续代码保持不变
```

**修改为**:

```python
def run_concurrent_stock_download(downloader, scheduler, interface_name, interface_config, base_params, stock_list, storage_manager, processor, logger):
    """运行并发股票下载 - 限流由 downloader._make_request 处理"""
    logger.info(f"Starting concurrent download for {interface_name} with {len(stock_list)} stocks")

    # 限流由 downloader._make_request 统一处理，这里不需要额外限流
    total_records = 0

    # 构建任务列表
    tasks = []
    for stock in stock_list:
        task = {
            'func': downloader.download_single_stock,  # ✅ 直接调用，不限流
            'args': (interface_config, stock, base_params),
            'kwargs': {}
        }
        tasks.append(task)

        # 每批提交一定数量的任务，避免内存溢出
        if len(tasks) >= 100:
            logger.info(f"Submitting batch of {len(tasks)} tasks")
            results = scheduler.submit_tasks(tasks)

            # buffer机制会自动处理数据
            for result in results:
                if result:
                    total_records += len(result)

            logger.info(f"Completed batch, total records: {total_records}")
            tasks = []

    # 提交剩余任务...
    # 代码保持不变
```

---

### 步骤 3：更新 RateLimiter 实现（固定窗口）

**文件**: `app4/core/scheduler.py`

替换 `RateLimiter` 类为 `FixedWindowRateLimiter`:

```python
import threading
import time
from datetime import datetime

class FixedWindowRateLimiter:
    """固定窗口速率限制器 - 每分钟固定窗口限流

    实现原理：
    - 时间按固定窗口分割（默认60秒一个窗口）
    - 每个窗口内允许 rate_limit 次请求
    - 达到上限后，必须等待到下一个窗口开始
    - 新窗口开始时，计数器重置

    优点：
    - 实现简单，易于理解
    - 严格控制在 rate_limit 以内
    - 易于监控和调试

    缺点：
    - 窗口切换时可能出现突发流量
    - 不够平滑（但对于我们的场景更合适）
    """

    def __init__(self, rate_limit: int, time_window: int = 60):
        """
        初始化固定窗口速率限制器

        Args:
            rate_limit: 每个时间窗口内允许的最大请求数
            time_window: 时间窗口（秒），默认60秒
        """
        self.rate_limit = rate_limit
        self.time_window = time_window
        self.current_window = self._get_current_window()
        self.request_count = 0
        self.lock = threading.Lock()
        self.total_wait_time = 0  # 统计总等待时间
        self.total_requests = 0   # 统计总请求数

    def _get_current_window(self) -> int:
        """获取当前时间窗口"""
        return int(time.time()) // self.time_window

    def _get_next_window_start(self) -> float:
        """获取下一个窗口开始时间（秒）"""
        now = time.time()
        next_window = (self._get_current_window() + 1) * self.time_window
        return next_window - now

    def acquire(self, tokens: int = 1) -> bool:
        """
        尝试获取令牌

        Args:
            tokens: 需要的令牌数

        Returns:
            True: 获取成功，可以立即执行
            False: 获取失败，需要等待
        """
        with self.lock:
            now_window = self._get_current_window()

            # 如果是新窗口，重置计数器
            if now_window != self.current_window:
                self.current_window = now_window
                self.request_count = 0
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🔄 新窗口开始，计数器重置")

            # 检查是否超过限制
            if self.request_count + tokens <= self.rate_limit:
                self.request_count += tokens
                self.total_requests += tokens
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✅ 令牌获取成功: {self.request_count}/{self.rate_limit}")
                return True
            else:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ❌ 令牌不足: {self.request_count}/{self.rate_limit}, 需要 {tokens}")
                return False

    def wait_for_tokens(self, tokens: int = 1):
        """
        等待直到有足够的令牌

        Args:
            tokens: 需要的令牌数
        """
        import random

        wait_start = time.time()

        while not self.acquire(tokens):
            # 计算到下一个窗口的时间
            sleep_time = self._get_next_window_start()

            if sleep_time > 0:
                # 添加随机抖动，避免所有线程同时唤醒
                jitter = random.uniform(0, min(1.0, sleep_time * 0.1))  # 最多1秒的抖动
                actual_sleep = sleep_time + jitter

                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ⏸️  达到限流上限，暂停 {actual_sleep:.2f}秒")
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]    当前: {self.request_count}/{self.rate_limit}, 需要: {tokens}")
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]    预计恢复: {(datetime.now().timestamp() + actual_sleep).strftime('%Y-%m-%d %H:%M:%S')}")

                time.sleep(actual_sleep)

        wait_end = time.time()
        wait_duration = wait_end - wait_start

        if wait_duration > 0.5:  # 如果等待时间超过500ms，记录统计
            self.total_wait_time += wait_duration
            avg_wait = self.total_wait_time / self.total_requests if self.total_requests > 0 else 0
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 📊 限流统计: 等待={wait_duration:.2f}s, 平均={avg_wait:.2f}s, 总计={self.total_requests}次")

    def get_stats(self) -> dict:
        """获取限流统计信息"""
        with self.lock:
            avg_wait = self.total_wait_time / self.total_requests if self.total_requests > 0 else 0
            return {
                'rate_limit': self.rate_limit,
                'time_window': self.time_window,
                'current_count': self.request_count,
                'total_requests': self.total_requests,
                'total_wait_time': self.total_wait_time,
                'average_wait_time': avg_wait,
                'current_window': self.current_window,
                'current_time': time.time()
            }
```

---

### 步骤 4：清理其他限流相关代码

**删除文件**: `app4/core/scheduler.py` 中的旧 `RateLimiter` 类

**删除文件**: `app4/main.py` 中所有 `rate_limiter` 参数传递（因为不再需要在 main 中处理限流）

```python
# ❌ 删除前：
def run_update_mode(..., global_rate_limiter):
    # ...
    downloaded_count = run_concurrent_stock_download(
        downloader, scheduler, interface_name, interface_config,
        params, stock_list, storage_manager, processor, logger
    )

# ✅ 修改后：
def run_update_mode(...):  # 移除 global_rate_limiter 参数
    # ...
    downloaded_count = run_concurrent_stock_download(
        downloader, scheduler, interface_name, interface_config,
        params, stock_list, storage_manager, processor, logger
    )
```

---

## 限流效果示例

### 正常运行时：

```
[2026-02-11 10:30:15] ✅ 令牌获取成功: 1/250
[2026-02-11 10:30:15] 📡 发起请求: daily_basic
[2026-02-11 10:30:16] ✅ 请求成功: daily_basic, 100条记录
[2026-02-11 10:30:16] ✅ 令牌获取成功: 2/250
[2026-02-11 10:30:16] 📡 发起请求: daily_basic
[2026-02-11 10:30:17] ✅ 请求成功: daily_basic, 100条记录
```

### 达到限流上限时：

```
[2026-02-11 10:31:00] ✅ 令牌获取成功: 249/250
[2026-02-11 10:31:00] 📡 发起请求: daily_basic
[2026-02-11 10:31:01] ✅ 请求成功: daily_basic, 100条记录
[2026-02-11 10:31:01] ✅ 令牌获取成功: 250/250
[2026-02-11 10:31:01] 📡 发起请求: daily_basic
[2026-02-11 10:31:02] ✅ 请求成功: daily_basic, 100条记录
[2026-02-11 10:31:02] ❌ 令牌不足: 250/250, 需要 1
[2026-02-11 10:31:02] ⏸️  达到限流上限，暂停 58.35秒
[2026-02-11 10:31:02]    当前: 250/250, 需要: 1
[2026-02-11 10:31:02]    预计恢复: 2026-02-11 10:32:00
[2026-02-11 10:32:00] 🔄 新窗口开始，计数器重置
[2026-02-11 10:32:00] ✅ 令牌获取成功: 1/250
[2026-02-11 10:32:00] 📡 发起请求: daily_basic
[2026-02-11 10:32:01] ✅ 请求成功: daily_basic, 100条记录
```

---

## 删除的无用代码清单

### 1. `app4/core/scheduler.py`

**删除**: `class RateLimiter` (旧版令牌桶实现)

**原因**: 被 `FixedWindowRateLimiter` 替代

### 2. `app4/main.py`

**删除**:
- `run_concurrent_stock_download` 中的 `download_single_stock_with_rate_limit` 包装函数
- 所有 `global_rate_limiter` 参数传递
- 所有 `rate_limiter` 参数传递

**删除前代码**:
```python
def run_concurrent_stock_download(...):
    """运行并发股票下载"""
    # ❌ 删除：创建包装函数，包含限流逻辑
    def download_single_stock_with_rate_limit(...):
        return downloader.download_single_stock(...)  # 没有限流！

    # 构建任务列表
    tasks = []
    for stock in stock_list:
        task = {
            'func': download_single_stock_with_rate_limit,  # ❌ 使用包装函数
            ...
        }
```

**删除后代码**:
```python
def run_concurrent_stock_download(...):
    """运行并发股票下载"""
    # 限流由 downloader._make_request 统一处理

    # 构建任务列表
    tasks = []
    for stock in stock_list:
        task = {
            'func': downloader.download_single_stock,  # ✅ 直接调用
            ...
        }
```

### 3. `app4/update/update_manager.py`

**删除**: `global_rate_limiter` 参数及相关代码

**删除前**:
```python
class UpdateManager:
    def __init__(self, config_loader, storage_manager, downloader, scheduler, processor, global_rate_limiter=None, rate_limiter=None):
        ...
        self.global_rate_limiter = global_rate_limiter or rate_limiter
```

**删除后**:
```python
class UpdateManager:
    def __init__(self, config_loader, storage_manager, downloader, scheduler, processor):
        ...
        # 不需要存储 rate_limiter，限流由 downloader 处理
```

---

## 总结

### 核心优势

1. **单一职责**：限流只发生在网络请求层级，职责清晰
2. **代码简化**：删除所有中间层的冗余限流代码
3. **易于调试**：限流逻辑集中，日志输出详细
4. **严格限流**：固定窗口算法，确保不超过 rate_limit
5. **用户友好**：终端输出暂停/恢复信息，用户体验好

### 影响范围

**修改文件**:
- `app4/core/scheduler.py` - 替换 RateLimiter 实现
- `app4/core/downloader.py` - 强化 _make_request 限流
- `app4/main.py` - 删除冗余限流代码
- `app4/update/update_manager.py` - 删除 rate_limiter 参数

**配置不变**:
- `app4/config/settings.yaml` - rate_limit 配置保持不变

### 验证方法

```bash
# 1. 运行简单测试
python -c "
from app4.core.config_loader import ConfigLoader
from app4.core.downloader import GenericDownloader

config = ConfigLoader()
downloader = GenericDownloader(config)

# 测试10次请求
for i in range(10):
    result = downloader.download('stock_basic', {'list_status': 'L'})
    print(f'Request {i+1}: {len(result)} records')
"

# 2. 观察终端输出
# 应该看到限流等待信息

# 3. 检查日志
tail -f log/app4.log
```

---

**创建日期**: 2026-02-11
**相关配置**: `app4/config/settings.yaml` - `request.rate_limit: 250`
**影响范围**: 所有 API 请求
**实施状态**: 待实施
