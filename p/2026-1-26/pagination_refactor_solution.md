# 分页模块重构方案

## 当前问题分析

1. `downloader.py` 文件过大（超过1200行），包含了大量分页执行逻辑
2. 分页逻辑与下载执行逻辑耦合严重
3. `pagination.py` 目前只负责参数生成，但实际执行逻辑仍在 `downloader.py`

## 重构方案

### 1. 创建新的分页执行器模块 (`pagination_executor.py`)

将 `downloader.py` 中的分页执行逻辑提取到新模块：

```python
# app4/core/pagination_executor.py
"""
分页执行器 - 负责执行分页参数生成器产生的参数
实现"零回调"模式，只执行请求，不生成参数
"""

from typing import Dict, Any, List, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from .pagination import ParameterGenerator, PaginationContext

class PaginationExecutor:
    """分页执行器 - 专门负责执行分页请求，通过回调函数执行具体请求"""

    def execute_offset_pagination(self, interface_config: Dict[str, Any],
                                params: Dict[str, Any],
                                context: PaginationContext,
                                make_request_callback: Callable) -> List[Dict[str, Any]]:
        """执行offset分页，通过回调函数执行请求"""
        all_data = []
        limit = context.pagination_config.get('default_limit', 5000)
        param_gen = ParameterGenerator(context)

        for page_params in param_gen.generate_offset_params(params):
            page_data = make_request_callback(interface_config, page_params)

            if not page_data:
                break
            all_data.extend(page_data)

            if len(page_data) < limit:
                break

        return all_data

    def execute_date_range_pagination(self, interface_config: Dict[str, Any],
                                    params: Dict[str, Any],
                                    context: PaginationContext,
                                    make_request_callback: Callable) -> List[Dict[str, Any]]:
        """执行日期范围分页（并发），通过回调函数执行请求"""
        # 从downloader.py迁移此逻辑，使用回调函数执行请求
        pass

    def execute_stock_loop_pagination(self, interface_config: Dict[str, Any],
                                    params: Dict[str, Any],
                                    context: PaginationContext,
                                    make_request_callback: Callable) -> List[Dict[str, Any]]:
        """执行股票循环分页，通过回调函数执行请求"""
        # 从downloader.py迁移此逻辑，使用回调函数执行请求
        pass

    # 其他分页模式的执行方法...
```

### 2. 修改 `pagination.py` - 保持纯净的参数生成功能

当前 `pagination.py` 已经符合要求，只需微调文档说明。

### 3. 重构 `downloader.py` - 简化核心逻辑

```python
# 在downloader.py中
from .pagination_executor import PaginationExecutor

class GenericDownloader:
    def __init__(self, ...):
        # ...
        self.pagination_executor = PaginationExecutor()  # 不再注入downloader实例

    def _execute_pagination(self, interface_config: Dict[str, Any],
                          params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """执行分页/循环逻辑 - 控制器"""
        pagination_config = interface_config.get('pagination', {})
        if not pagination_config.get('enabled', False):
            return self._make_request(interface_config, params)

        mode = pagination_config.get('mode', 'offset')
        context = PaginationContext(
            interface_config=interface_config,
            force_download=self.force_download
        )

        # 委托给分页执行器，传递回调函数而非self实例
        if mode == 'offset':
            return self.pagination_executor.execute_offset_pagination(
                interface_config, params, context, self._make_request
            )
        elif mode == 'date_range':
            return self.pagination_executor.execute_date_range_pagination(
                interface_config, params, context, self._make_request
            )
        # ... 其他模式
```

## 依赖关系

```
downloader.py → pagination_executor.py → pagination.py
```

- `downloader.py` 依赖 `pagination_executor.py`（执行分页）
- `pagination_executor.py` 依赖 `pagination.py`（生成参数）
- `pagination_executor.py` 通过回调函数依赖 `downloader.py` 的 `_make_request` 方法（运行时依赖，非导入时依赖）
- `pagination.py` 不依赖其他模块（纯参数生成）

## 零回调模式实现

1. `pagination.py`：只生成参数，不执行请求
2. `pagination_executor.py`：接收参数并通过回调函数执行请求，不生成参数
3. `downloader.py`：协调两者，提供请求执行能力

## 预期效果

- `downloader.py` 代码量减少至500行以下
- 职责清晰分离：参数生成、请求执行、下载控制
- 单向依赖关系，易于测试和维护
- 保持现有功能不变